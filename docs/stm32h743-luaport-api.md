# LuaPort（STM32H743 裸机）接口文档

> 目标：在裸机主循环中以**非阻塞**方式周期调用 Lua 的 `start()` / `update(dt)`，并在 Lua 侧控制硬件（GPIO/延时/微秒计时/SD FatFs）。  
> **输入系统 v1（新增）**：引入 Defold 风格的 `input/game.input_binding`，以及模板提供的 `board/pins.json`（引脚下拉列表）。硬件触发输入后，运行时查表得到 `action`，并调用 Lua 的 `input(action, event)`。

---

## 1. 快速上手（裸机主循环）

### 1.1 Lua 脚本约定（boot.lua / main.lua）

运行时会尝试调用（若存在）：

```lua
function start()
  -- 初始化（只调用一次）
end

function update(dt)
  -- dt: 秒（float），默认固定 0.010
end
```

---

### 1.2 输入系统（Input Bindings）与 Lua 回调约定（新增）

本工程采用 Defold 风格的输入绑定文件：

- `input/game.input_binding`：用户通过 IDE 面板编辑（Input → Action）
- `board/pins.json`：由项目模板提供的**引脚下拉列表数据源**（用户无需维护）

#### 1.2.1 Lua 侧回调（新增）

运行时除 `start()` / `update(dt)` 外，还会尝试调用（若存在）：

```lua
function input(action, event)
  -- action: 例如 "ok" / "back" / "up"
  -- event:  "press" / "release"
end
```

语义：
- 硬件触发某输入（例如 pin="PA0", event="press"）
- 运行时查 `game.input_binding` 得到 action（例如 "ok"）
- 调用 Lua：`input("ok", "press")`

> 注意：Lua 回调只接收 `action/event`，不接收引脚名/手柄键名，以保持脚本层业务语义清晰。

#### 1.2.2 运行时输入 API（C 侧，新增）

建议新增输入系统对外 API（建议放 `lua_input.h/.c`）：

- `int lua_input_init(void);`
  - 读取并解析 `input/game.input_binding`
  - 读取并解析 `board/pins.json`（仅用于校验 pin 输入合法性）
  - 建立查表：`(source, input, event) -> action`

- `void lua_input_emit_pin(const char* pin_name, const char* event);`
- `void lua_input_emit_touch(const char* touch_input, const char* event);`
- `void lua_input_emit_gamepad(const char* pad_input, const char* event);`

约束：
- emit 必须是**非阻塞**：只把事件写入 ring buffer 队列
- 事件由 `lua_update_task()` 在主循环中消费并派发给 Lua（见下节）

#### 1.2.3 `lua_update_task()` 的输入派发顺序（新增）

`lua_update_task()` 每次调用时建议执行顺序：
1) 先消费输入队列：对每个事件查 action 并调用 `input(action,event)`
2) 若达到 update 周期，再调用 `update(dt)`（保持原 10ms 逻辑不变）

> 这样可以保证：输入延迟低，同时不破坏主循环“非阻塞 update”模型。

---

### 1.3 推荐的 C 侧初始化顺序

**关键点：一定要在执行脚本前把 `gpio/tim/sd/delay` 注册进 Lua。**  
否则会出现：`attempt to index a nil value (global 'gpio')`

推荐把 `lua_port_bind()` 放进 `lua_init()` 里（`luaL_loadbuffer()` 之前）。

伪代码（示意）：

```c
int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_SDMMC1_SD_Init();
  MX_FATFS_Init();
  // ...

  lua_init();      // 内部会加载 boot 脚本，并调用 start()

  while (1) {
    lua_update_task();  // 非阻塞：每 10ms 执行一次 update()
    // 你的其他轮询逻辑…
  }
}
```

---

## 2. Lua 运行时（lua_vm.h / lua_vm.c）

### 2.1 对外 API

#### `int lua_init(void);`

- **作用**：创建 Lua 虚拟机 `lua_State`，加载并执行 boot 脚本，随后调用一次 `start()`（如果脚本里定义了）。
- **返回值**：
  - `0`：成功
  - `<0`：失败（会通过 `lua_rt_log()` 打印原因）

> 当前实现中：脚本内容来自 `lua_get_boot_script()`（弱符号，可由你在工程里覆盖）。

#### `void lua_update_task(void);`

- **作用**：在主循环里反复调用。内部根据 `lua_rt_time_ms()` 的时间差，**每到 10ms** 调用一次 `update(dt)`。
- **非阻塞策略**：未到周期直接 `return`，不会卡住主循环。
- **dt**：默认固定 `0.010f` 秒（由 `LUA_RT_PERIOD_MS` 控制）。

> 输入系统扩展建议：在 `lua_update_task()` 中先消费输入队列并调用 `input(action,event)`，再按原周期调用 `update(dt)`。

---

### 2.2 可覆盖的弱符号（weak hooks）

这三个函数在 `lua_vm.c` 中标记为 `__attribute__((weak))`，你可以在工程任意位置实现同名函数覆盖默认行为。

#### `uint32_t lua_rt_time_ms(void);`

- 默认实现：返回 `HAL_GetTick()`（1ms tick）
- 用途：为 `lua_update_task()` 提供时间基准

#### `void lua_rt_log(const char *s);`

- 默认实现：空实现（注释了 `printf`）
- 用途：输出 Lua 加载/运行错误信息
- 建议：替换为 RTT / 串口 / ITM 输出

#### `const char* lua_get_boot_script(size_t *out_len);`

- 默认实现：返回内置字符串（含 `start()` / `update(dt)`），并在 `update()` 里调用 `gpio.toggle('B', 1)`
- 用途：提供 boot.lua 内容来源
- 你可以做：
  - 返回编译进固件的脚本（const char[]）
  - 或返回从 QSPI/SD 读取的脚本（如果你愿意在 init 阶段阻塞加载）

---

### 2.3 周期配置宏

#### `LUA_RT_PERIOD_MS`

- 默认值：`10`
- 作用：控制 `lua_update_task()` 调用 `update()` 的周期

---

### 2.4 常见错误码说明（`luaL_loadbuffer`）

`luaL_loadbuffer()` 的返回值 `rc`：
- `LUA_OK (0)`：成功
- `LUA_ERRSYNTAX (3)`：语法错误（最常见）
- `LUA_ERRMEM (4)`：内存不足
- `LUA_ERRGCMM (5)`：GC 元方法错误（较少见）

---

## 3. 端口绑定（lua_port.h / lua_port.c）

### 3.1 C API

#### `void lua_port_bind(lua_State* L, const lua_port_config_t* cfg);`

- 作用：把硬件相关的 Lua 模块注册到全局环境：
  - 全局表 `gpio`
  - 全局表 `tim`
  - 全局表 `sd`
  - 全局函数 `delay(ms)`
- 参数：
  - `L`：Lua 虚拟机实例
  - `cfg`：端口配置（当前 `lua_port.c` 会把它塞进 registry 的 `"port.cfg"`，用于“单 LED 版 gpio 模块”读取端口/引脚；如果你用“全 GPIO 版模块”，可传 `NULL`。）

> 建议：如果你已经切到全 GPIO 版（见下文 4.1），`lua_port_config_t` 可以保留但不必使用。

---

## 4. Lua 模块：gpio

工程里存在两种 gpio 模块实现：

- A. 单 pin 版（根目录 `lua_gpio.c`）：只控制 `cfg->gpio.led_port/led_pin`
- B. 全 GPIO 版（推荐）（`LuaPort/modules/lua_gpio.c`）：可控制 A~H（以及 I/J/K 若芯片有）所有端口的 0~15 引脚

### 4.1 gpio（全 GPIO 版，推荐）

#### `gpio.write(port, pin, value)`

- 参数：
  - `port`：端口标识（字符串），支持 `"B"` / `"PB"` / `"GPIOB"` 等（内部会提取 A~K 的第一个字母）
  - `pin`：0~15
  - `value`：任意 Lua 真值（建议 `1/0` 或 `true/false`）
- 行为：使用 `BSRR` 原子写（置位/复位不会影响同端口其他 pin）

示例：

```lua
gpio.write("B", 1, 1)        -- PB1 = HIGH
gpio.write("GPIOB", 1, 0)    -- PB1 = LOW
```

#### `gpio.toggle(port, pin)`

```lua
gpio.toggle("B", 1)
```

#### `gpio.read(port, pin) -> boolean`

```lua
local v = gpio.read("B", 1)  -- true=高, false=低
```

#### 端口常量（可选）

模块可导出：
- `gpio.PORTA = "A"`
- `gpio.PORTB = "B"`
- ...
- `gpio.PORTH = "H"`
- （若存在）`gpio.PORTI/J/K`

因此你想写的“不加引号端口名”风格，可以这样写：

```lua
gpio.write(gpio.PORTB, 1, 1)      -- ✅
-- gpio.write(B, 1, 1)            -- ❌ B 会被当成变量（通常是 nil）
```

#### HIGH / LOW 常量（可选）

当前实现用 `lua_toboolean()`，推荐：

```lua
gpio.write(gpio.PORTB, 1, true)
gpio.write(gpio.PORTB, 1, false)
```

如果你想要 `gpio.HIGH / gpio.LOW` 常量，建议在 `luaopen_gpio()` 末尾加：

```c
lua_pushinteger(L, 1); lua_setfield(L, -2, "HIGH");
lua_pushinteger(L, 0); lua_setfield(L, -2, "LOW");
```

---

### 4.2 gpio（单 pin 版：cfg->gpio.led_port/led_pin）

> 这一版只适合最开始“只控 PB1 LED”的阶段；你现在想控全 GPIO，建议用 4.1。

- `gpio.write(value)`
- `gpio.toggle()`
- `gpio.read() -> boolean`

---

## 5. Lua 全局函数：delay（LuaPort/modules/lua_delay.c）

### `delay(ms)`

- 参数：毫秒（整数）
- 行为：调用 `HAL_Delay(ms)`（阻塞）

示例：

```lua
delay(100)
```

> 提醒：想“非阻塞”时，主循环里尽量不要在 `update()` 里频繁使用 `delay()`；更推荐用 `tim.us()` 做时间差，自己写状态机。

---

## 6. Lua 模块：tim（LuaPort/modules/lua_tim.c）

基于 DWT->CYCCNT（不占用 TIM 外设）。

### `tim.us() -> integer`

- 返回：当前时间（微秒），从 DWT 启动后累计

```lua
local t = tim.us()
```

### `tim.delay_us(us)`

- 忙等微秒延时（阻塞）

```lua
tim.delay_us(50)
```

---

## 7. Lua 模块：sd（LuaPort/modules/lua_sd.c，FatFs）

### 7.1 初始化与挂载

模块内部会在第一次 `sd.open()` 时 `f_mount()` 自动挂载；也提供手动接口（若你实现）：
- `sd.mount() -> boolean`
- `sd.umount() -> boolean`

### 7.2 打开文件

#### `sd.open(path, mode?) -> file`

- `path`：例如 `"test.txt"` 或 `"/dir/a.txt"`
- `mode`：`"r"` / `"r+"` / `"w"` / `"w+"` / `"a"` / `"a+"`

示例：

```lua
local f = sd.open("log.txt", "a")
```

### 7.3 文件对象方法（`file:`）

- `file:close()`
- `file:write(data) -> written_len`
- `file:read(n) -> string`
- `file:seek(pos) -> new_pos`
- `file:size() -> size`

示例：

```lua
local f = sd.open("hello.txt", "w")
f:write("hello
")
f:close()
```

### 7.4 模块级包装函数（`sd.xxx(f, ...)`）

- `sd.close(f)` 等价 `f:close()`
- `sd.write(f, data)` 等价 `f:write(data)`
- `sd.read(f, n)` 等价 `f:read(n)`
- `sd.seek(f, pos)` 等价 `f:seek(pos)`
- `sd.size(f)` 等价 `f:size()`

---

## 8. 输入绑定文件与板级引脚列表（新增：运行时侧）

> 这一节用于说明运行时读取的工程资产格式，以及运行时应做的校验与派发。

### 8.1 `board/pins.json`（模板提供，引脚下拉列表）

- 路径：`board/pins.json`
- 由项目模板提供，用户无需维护
- 运行时用途：作为“安全网”校验集合（IDE 已强制下拉选择，但运行时仍建议校验）

格式：

```json
{
  "format": "CART_BOARD_PINS",
  "version": 1,
  "name": "Board Template Pins",
  "pins": [
    { "id": "PA0", "label": "PA0", "tags": ["gpio", "exti"] },
    { "id": "PC13", "label": "PC13", "tags": ["gpio", "wkup"] }
  ]
}
```

约束：
- `pins[].id` 唯一
- `pins[].id` 是 `game.input_binding` 中 `pin_triggers[].input` 的合法取值集合

---

### 8.2 `input/game.input_binding`（用户编辑，Input → Action）

- 路径：`input/game.input_binding`
- 用户通过 IDE 面板编辑
- v1 输入源：引脚 / 触摸 / 手柄按键（不含摇杆）

格式（示例）：

```json
{
  "format": "CART_INPUT_BINDING",
  "version": 1,
  "name": "默认输入绑定（v1）",
  "pin_triggers": [
    { "input": "PA0", "action": "ok", "event": "press" },
    { "input": "PC13", "action": "back", "event": "press" }
  ],
  "touch_triggers": [
    { "input": "TOUCH_TAP", "action": "touch", "event": "press" }
  ],
  "gamepad_triggers": [
    { "input": "PAD_X", "action": "ok", "event": "press" }
  ]
}
```

约束：
- `format == "CART_INPUT_BINDING"`
- `version == 1`
- 每条 trigger 必须有 `input/action/event`
- `event` 只能是 `press` 或 `release`
- 所有 `pin_triggers[].input` 必须存在于 `board/pins.json` 的 `pins[].id`

---

### 8.3 运行时校验建议

初始化 `lua_input_init()` 时建议校验：
1. `pins.json` 与 `game.input_binding` JSON 可解析
2. `format/version` 正确
3. `pin_triggers[].input` 全部在 pins 列表内（否则打印日志并忽略该条）
4. 同一来源表内不允许重复 `(input,event)`（冲突建议日志提示并按“后者覆盖”或“拒绝重复”策略固定下来）

---

## 9. 如何在 C 里新增一个 Lua 库（模块/常量/函数）

### 9.1 C 函数签名规则

```c
static int myfunc(lua_State* L)
{
  // 从栈取参数：luaL_checkinteger / luaL_checkstring / lua_toboolean ...
  // 往栈压返回值：lua_pushinteger / lua_pushboolean / lua_pushlstring ...
  // return 返回值数量
  return 1;
}
```

### 9.2 导出成模块（`luaopen_xxx`）

```c
static const luaL_Reg lib[] = {
  {"foo", l_foo},
  {"bar", l_bar},
  {NULL, NULL}
};

int luaopen_my(lua_State* L)
{
  luaL_newlib(L, lib);
  // 可在这里 lua_setfield 导出常量
  return 1; // 返回这个 table
}
```

在 `lua_port_bind()` 里注册：

```c
luaopen_my(L);
lua_setglobal(L, "my");
```

---

## 10. 文件索引（建议结构）

- `lua_vm.h / lua_vm.c`：裸机运行时（init + 10ms update）
- `lua_port.h / lua_port.c`：把模块注册进 Lua（gpio/tim/sd + delay）
- `LuaPort/modules/lua_gpio.c`：全 GPIO 版模块（推荐）
- `LuaPort/modules/lua_tim.c`：DWT 微秒计时与延时
- `LuaPort/modules/lua_delay.c`：全局 delay(ms)
- `LuaPort/modules/lua_sd.c`：FatFs 文件读写
- （新增建议）`lua_input.h / lua_input.c`：输入系统（读取 `input/game.input_binding` + `board/pins.json`，输入事件队列，调用 Lua `input(action,event)`）
- 工程资产（模板提供/用户编辑）
  - `board/pins.json`：引脚下拉列表数据源（合法引脚集合）
  - `input/game.input_binding`：输入绑定（触摸/引脚/手柄按键 → action）
