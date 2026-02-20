-- Test main.lua entry point
print("Hello, XHGC!")

function start()
    -- 初始化（只调用一次）
    -- print("Initializing game...")
    -- 测试 GPIO 功能
    if gpio then
        print("GPIO module available")
    end
    -- 测试 SD 功能
    if sd then
        print("SD module available")
    end
end

function update(dt)
    -- dt: 秒（float），默认固定 0.010
    print("Updating game... dt = " .. dt)
end
-- ============================================================
-- LuaPort STM32H743 功能测试脚本
-- 测试范围：gpio / tim / delay / sd / 基础 Lua 语言特性
-- 使用前请按实际硬件修改下方 CONFIG 区域
-- ============================================================

-- ---- CONFIG（按你的硬件修改）----
local LED_PORT = "B"   -- LED 所在 GPIO 端口
local LED_PIN  = 0     -- LED 引脚号

local BTN_PORT = "C"   -- 按键端口（没有可注释掉 Test 4）
local BTN_PIN  = 13    -- 按键引脚（低电平触发）

local LOG_FILE = "test_log.txt"   -- SD 卡上的日志文件名
-- ----------------------------------

-- 全局计数器（update 里用）
local tick       = 0
local blink_cnt  = 0
local last_us    = 0
local btn_last   = false


-- ============================================================
-- 工具：向串口+SD 同时输出一行日志
-- ============================================================
local log_file = nil

local function log(msg)
    -- 如果 SD 可用，写文件
    if log_file then
        log_file:write(msg .. "\n")
    end
    -- （如果你接了串口/RTT，可以在这里加打印；裸机先靠 SD 看结果）
end

local function log_close()
    if log_file then
        log_file:close()
        log_file = nil
    end
end


-- ============================================================
-- Test 1 : 基础 Lua 语言特性（整数 / 浮点 / 字符串 / table）
-- ============================================================
local function test_language()
    local ok = true

    -- 整数（lua_Integer = int 32位）
    local a = 0x7FFFFFFF   -- 2147483647，32位有符号最大值
    assert(a == 2147483647, "int32 max failed")

    -- 浮点（lua_Number = double）
    local pi = 3.141592653589793
    assert(math.abs(pi - math.pi) < 1e-10, "double precision failed")

    -- 字符串
    local s = "STM32H743"
    assert(#s == 9, "string len failed")
    assert(string.sub(s, 1, 3) == "STM", "string.sub failed")

    -- table
    local t = {10, 20, 30, key = "val"}
    assert(#t == 3, "table len failed")
    assert(t.key == "val", "table field failed")

    -- 闭包
    local function counter(start)
        local n = start
        return function() n = n + 1; return n end
    end
    local c = counter(0)
    assert(c() == 1 and c() == 2, "closure failed")

    -- 可变参数
    local function sum(...) local s=0; for _,v in ipairs({...}) do s=s+v end; return s end
    assert(sum(1,2,3,4,5) == 15, "vararg failed")

    log("[1] language: PASS")
    return ok
end


-- ============================================================
-- Test 2 : GPIO 读写 / toggle（LED 闪烁验证）
-- ============================================================
local function test_gpio()
    -- 写高/低
    gpio.write(LED_PORT, LED_PIN, 1)
    tim.delay_us(500000)   -- 亮 500ms（阻塞，测试用）

    gpio.write(LED_PORT, LED_PIN, 0)
    tim.delay_us(500000)   -- 灭 500ms

    -- toggle 5次，肉眼可见
    for i = 1, 5 do
        gpio.toggle(LED_PORT, LED_PIN)
        tim.delay_us(200000)
    end

    -- read 回读（LED 当前状态）
    local v = gpio.read(LED_PORT, LED_PIN)
    -- v 是 boolean，只要不报错就算通过
    assert(type(v) == "boolean", "gpio.read type failed")

    log("[2] gpio: PASS  (LED should have blinked)")
    return true
end


-- ============================================================
-- Test 3 : tim.us() 计时精度（误差 < 5%）
-- ============================================================
local function test_tim()
    local TARGET_US = 100000   -- 100ms

    local t0 = tim.us()
    tim.delay_us(TARGET_US)
    local t1 = tim.us()

    local elapsed = t1 - t0
    local err_pct = math.abs(elapsed - TARGET_US) / TARGET_US * 100

    local pass = err_pct < 5.0
    local msg = string.format(
        "[3] tim: elapsed=%dus target=%dus err=%.1f%% %s",
        elapsed, TARGET_US, err_pct, pass and "PASS" or "FAIL")
    log(msg)
    return pass
end


-- ============================================================
-- Test 4 : delay(ms) 阻塞延时
-- ============================================================
local function test_delay()
    local t0 = tim.us()
    delay(200)             -- HAL_Delay 200ms
    local t1 = tim.us()

    local elapsed_ms = (t1 - t0) / 1000.0
    local pass = math.abs(elapsed_ms - 200) < 10   -- ±10ms 容差

    local msg = string.format(
        "[4] delay: elapsed=%.1fms pass=%s",
        elapsed_ms, tostring(pass))
    log(msg)
    return pass
end


-- ============================================================
-- Test 5 : SD 卡读写
-- ============================================================
local function test_sd()
    -- 写
    local wf = sd.open(LOG_FILE, "w")
    if not wf then
        log("[5] sd: SKIP (open write failed)")
        return false
    end
    local written = wf:write("LuaPort SD test\nline2\nline3\n")
    wf:close()

    -- 读回验证
    local rf = sd.open(LOG_FILE, "r")
    if not rf then
        log("[5] sd: FAIL (open read failed)")
        return false
    end
    local content = rf:read(64)
    local sz = rf:size()
    rf:close()

    local pass = (string.find(content, "LuaPort") ~= nil) and (sz > 0)
    local msg = string.format(
        "[5] sd: size=%d content_ok=%s %s",
        sz, tostring(string.find(content, "LuaPort") ~= nil),
        pass and "PASS" or "FAIL")
    log(msg)
    return pass
end


-- ============================================================
-- Test 6 : math 库
-- ============================================================
local function test_math()
    assert(math.floor(3.9) == 3,  "floor")
    assert(math.ceil(3.1)  == 4,  "ceil")
    assert(math.abs(-7)    == 7,  "abs")
    assert(math.max(1,5,3) == 5,  "max")
    assert(math.min(1,5,3) == 1,  "min")
    assert(math.type(1)    == "integer",  "type int")
    assert(math.type(1.0)  == "float",    "type float")

    local sq = math.sqrt(2.0)
    assert(math.abs(sq * sq - 2.0) < 1e-10, "sqrt precision")

    log("[6] math: PASS")
    return true
end


-- ============================================================
-- Test 7 : string 库
-- ============================================================
local function test_string()
    assert(string.format("%d", 42)         == "42",      "format int")
    assert(string.format("%.2f", 3.14159)  == "3.14",   "format float")
    assert(string.upper("hello")           == "HELLO",  "upper")
    assert(string.rep("ab", 3)             == "ababab", "rep")

    local found, e = string.find("STM32H743", "H7")
    assert(found == 6, "find")

    local result = {}
    for w in string.gmatch("a,b,c", "[^,]+") do
        result[#result+1] = w
    end
    assert(#result == 3 and result[2] == "b", "gmatch")

    log("[7] string: PASS")
    return true
end


-- ============================================================
-- Test 8 : table / coroutine 简单测试
-- ============================================================
local function test_table_coro()
    -- table.sort
    local arr = {5, 3, 1, 4, 2}
    table.sort(arr)
    assert(arr[1]==1 and arr[5]==5, "sort")

    table.insert(arr, 6)
    assert(arr[6] == 6, "insert")

    table.remove(arr, 1)
    assert(arr[1] == 2, "remove")

    -- coroutine
    local function gen(max)
        return coroutine.wrap(function()
            for i = 1, max do coroutine.yield(i) end
        end)
    end
    local g = gen(3)
    assert(g()==1 and g()==2 and g()==3, "coroutine wrap")

    log("[8] table+coroutine: PASS")
    return true
end


-- ============================================================
-- start()：运行全部单次测试
-- ============================================================
function start()
    -- 尝试打开 SD 日志（失败不影响其他测试）
    local ok_sd_log, f = pcall(sd.open, LOG_FILE, "a")
    if ok_sd_log and f then log_file = f end

    log("===== LuaPort test START =====")

    local tests = {
        {"language",     test_language},
        {"gpio",         test_gpio},
        {"tim",          test_tim},
        {"delay",        test_delay},
        {"sd",           test_sd},
        {"math",         test_math},
        {"string",       test_string},
        {"table+coro",   test_table_coro},
    }

    local pass_cnt = 0
    local fail_cnt = 0

    for _, item in ipairs(tests) do
        local name, fn = item[1], item[2]
        local ok, err = pcall(fn)
        if ok and err ~= false then
            pass_cnt = pass_cnt + 1
        else
            fail_cnt = fail_cnt + 1
            log(string.format("  [FAIL] %s: %s", name, tostring(err)))
            -- 失败后继续跑其他测试
        end
    end

    log(string.format("===== RESULT: %d pass, %d fail =====", pass_cnt, fail_cnt))
    log_close()

    -- 结束后 LED 用闪烁次数指示：全通过快闪3下，有失败慢闪fail_cnt下
    if fail_cnt == 0 then
        for _ = 1, 6 do gpio.toggle(LED_PORT, LED_PIN); tim.delay_us(100000) end
    else
        for _ = 1, fail_cnt * 2 do gpio.toggle(LED_PORT, LED_PIN); tim.delay_us(500000) end
    end
end


-- ============================================================
-- update(dt)：周期任务（10ms 调一次）
-- 在 start() 跑完后继续演示非阻塞 LED 呼吸 + 按键检测
-- ============================================================
function update(dt)
    tick = tick + 1

    -- 每 50 tick (约500ms) 翻转一次 LED（非阻塞呼吸灯）
    blink_cnt = blink_cnt + 1
    if blink_cnt >= 50 then
        blink_cnt = 0
        gpio.toggle(LED_PORT, LED_PIN)
    end

    -- 每 100 tick 记录一次 tim.us() 戳（演示周期测量）
    if tick % 100 == 0 then
        local now = tim.us()
        if last_us ~= 0 then
            local interval_ms = (now - last_us) / 1000.0
            -- 期望约 1000ms（100 * 10ms），打到 SD 需要自己再开文件
            _ = interval_ms  -- 在这里加 sd.write 或 RTT 输出
        end
        last_us = now
    end

    -- 按键检测（下降沿）
    local btn_now = not gpio.read(BTN_PORT, BTN_PIN)   -- 低电平=按下=true
    if btn_now and not btn_last then
        -- 按键刚按下：写一条 SD 日志
        local f = sd.open("btn_log.txt", "a")
        if f then
            f:write(string.format("btn press at tick=%d\n", tick))
            f:close()
        end
        gpio.write(LED_PORT, LED_PIN, 1)   -- 按下时 LED 常亮
    elseif not btn_now and btn_last then
        gpio.write(LED_PORT, LED_PIN, 0)   -- 松开时 LED 灭
    end
    btn_last = btn_now
end