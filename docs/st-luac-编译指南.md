# st-luac 编译指南
**STM32H743 · Lua 5.4 交叉编译器构建与验证**

---

## 1. 前置条件

- macOS + Xcode Command Line Tools（提供 `clang`）
- 项目目录结构：
  ```
  LuaPort/
    src/          ← 所有 .c 源文件及 luaconf.h
    tool/bin/     ← st-luac 输出位置
  ```

---

## 2. luaconf.h 关键配置

STM32H743 的最优组合：

| 配置项 | 正确值 | 字节大小 | 原因 |
|---|---|---|---|
| `LUA_INT_TYPE` | `LUA_INT_INT` | 4 bytes | M7 原生 32 位，单周期整数运算 |
| `LUA_FLOAT_TYPE` | `LUA_FLOAT_DOUBLE` | 8 bytes | H743 硬件双精度 FPU，double 与 float 速度相同 |

### else 分支必须加 `#ifndef` 保护

否则编译命令里的 `-D` 参数会被 `luaconf.h` 里的裸 `#define` 覆盖：

```c
#else           /* }{ */
/* STM32H743: int(32) + double(H743 has hw double FPU) */

#ifndef LUA_INT_TYPE
#define LUA_INT_TYPE    LUA_INT_INT
#endif
#ifndef LUA_FLOAT_TYPE
#define LUA_FLOAT_TYPE  LUA_FLOAT_DOUBLE
#endif

#endif                          /* } */
```

> ⚠️ `LUA_32BITS` 必须为 `0`，否则强制走 float 分支，`LUA_FLOAT_TYPE` 直接被设为 `LUA_FLOAT_FLOAT`。

---

## 3. 编译命令

在 `LuaPort/src/` 目录下执行：

```bash
clang -I. -o ../tool/bin/st-luac \
  -DLUA_32BITS=0 \
  -DLUA_INT_TYPE=1 \
  -DLUA_FLOAT_TYPE=2 \
  luac.c lapi.c lauxlib.c lbaselib.c lcode.c lcorolib.c \
  lctype.c ldebug.c ldo.c ldump.c lfunc.c lgc.c \
  llex.c lmathlib.c lmem.c lobject.c lopcodes.c lparser.c \
  lstate.c lstring.c lstrlib.c ltable.c ltablib.c ltm.c \
  lundump.c lutf8lib.c lvm.c lzio.c -lm
```

**参数说明：**

| 参数 | 作用 |
|---|---|
| `-I.` | 强制优先使用当前目录的 `luaconf.h`，防止用到系统 Lua 的配置 |
| `-DLUA_32BITS=0` | 禁用 32 位模式，进入 else 分支 |
| `-DLUA_INT_TYPE=1` | 对应 `LUA_INT_INT`（32 位整数） |
| `-DLUA_FLOAT_TYPE=2` | 对应 `LUA_FLOAT_DOUBLE`（64 位双精度） |

> ⚠️ 编译时会出现 `macro redefined` warning，这是正常的（`-D` 与 `#ifndef` 之间的冲突提示），不影响结果。

---

## 4. 编译后验证

编译完成后立即验证，**不要只看打印输出**，要直接检查字节码头部：

```bash
echo 'x=1.0' > /tmp/t.lua
./st-luac -o /tmp/t.luac /tmp/t.lua

python3 -c "
d = open('/tmp/t.luac', 'rb').read()
print('sizeof(Instruction):', d[12], 'bytes')  # 期望: 4
print('lua_Integer:        ', d[13], 'bytes')  # 期望: 4
print('lua_Number:         ', d[14], 'bytes')  # 期望: 8
"
```

**期望输出：**
```
sizeof(Instruction): 4 bytes
lua_Integer:         4 bytes
lua_Number:          8 bytes
```

---

## 5. 用二进制查看器检查 .luac 头部

### 5.1 Lua 5.4 字节码头部结构

用任意十六进制查看器打开 `.luac` 文件，对照下表逐字节核对：

| Index（十进制） | 偏移（十六进制） | 期望值 | 含义 |
|---|---|---|---|
| 0–3 | `00`–`03` | `1B 4C 75 61` | 魔数 `\x1bLua` |
| 4 | `04` | `54` | 版本号 Lua 5.4 |
| 5 | `05` | `00` | 格式号 |
| 6–11 | `06`–`0B` | `19 93 0D 0A 1A 0A` | LUAC_DATA 校验段（固定值） |
| **12** | `0C` | **`04`** | **sizeof(Instruction) = 4** |
| **13** | `0D` | **`04`** | **sizeof(lua_Integer) = 4** ✅ |
| **14** | `0E` | **`08`** | **sizeof(lua_Number) = 8** ✅ |

### 5.2 正确的头部十六进制示例

```
偏移: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E ...
值:   1B 4C 75 61 54 00 19 93 0D 0A 1A 0A 04 04 08 ...
                                               ↑  ↑  ↑
                                   Instruction   Int  Number
                                       (4B)     (4B)  (8B)
```

### 5.3 常见错误对照

| index 14 的值 | 含义 | 状态 |
|---|---|---|
| `08` | lua_Number = 8 bytes（double） | ✅ 正确 |
| `04` | lua_Number = 4 bytes（float） | ❌ 错误，st-luac 未用正确配置编译 |

### 5.4 推荐的二进制查看工具

- **macOS**：[Hex Fiend](https://hexfiend.com/)（免费，App Store 可下载）
- **命令行**：`xxd test.luac | head -2`

  正确输出示例：
  ```
  00000000: 1b4c 7561 5400 1993 0d0a 1a0a 0404 0878  .LuaT..........x
  ```
  其中第 15 个字节（`0E` 偏移）= `08` 即为 lua_Number = 8 bytes ✅

- **Python 快速检查**（最可靠）：
  ```python
  d = open('your.luac', 'rb').read()
  print(d[12], d[13], d[14])  # 期望: 4 4 8
  ```

---

## 6. 打包后验证 cart.bin

重新编译 `st-luac` 并用 xhgc-pack 打包后，用以下脚本验证 ENTRY slot：

```python
import struct, zlib

data = open('cart.bin', 'rb').read()

# 读取 ENTRY slot（slot3，偏移 0x0F30）
off, sz, crc = struct.unpack_from('<QII', data, 0x0F30)
seg = data[off:off+sz]
h = seg[:16]

print(f'ENTRY offset : {off:#010x}')
print(f'ENTRY size   : {sz} bytes')
print(f'magic        : {"✅" if h[0:4]==b"\\x1bLua" else "❌"}')
print(f'Lua version  : {"✅ 5.4" if h[4]==0x54 else "❌"}')
print(f'lua_Integer  : {h[13]} bytes  {"✅" if h[13]==4 else "❌"}')
print(f'lua_Number   : {h[14]} bytes  {"✅" if h[14]==8 else "❌ 期望8"}')
print(f'段 CRC32     : {"✅" if (zlib.crc32(seg)&0xFFFFFFFF)==crc else "❌"}')
```

**全部 ✅ 才可烧录到 STM32H743。**

---

## 7. 修改 Lua VM 后的完整流程

```
修改 luaconf.h 或 Lua VM 源码
        ↓
重新编译 st-luac（第3节）
        ↓
验证编译产物字节码头部（第4节）
        ↓
同步更新 STM32 固件中的 Lua VM（同一份 luaconf.h）
        ↓
xhgc-pack 重新打包 cart.bin
        ↓
验证 cart.bin 的 ENTRY slot（第6节）
        ↓
烧录测试
```

> ⚠️ **重要**：`st-luac`（打包器）和 STM32 固件中的 Lua VM 必须使用**同一份** `luaconf.h`，字节码头部的类型信息才能匹配。任何一方修改后，另一方必须同步更新并重新编译。
