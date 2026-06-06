# XHGC Pack 命令行使用说明

本文记录在仓库根目录下使用打包器的常用命令。

除非特别说明，下面的命令都假设当前目录是项目根目录：

```bash
/Volumes/Sector0/AppData/PyCharm/xhgc-pack
```

## 1. 准备环境

进入项目目录：

```bash
cd /Volumes/Sector0/AppData/PyCharm/xhgc-pack
```

安装运行依赖：

```bash
.venv/bin/python -m pip install -e '.[image]'
```

如果需要运行测试，也可以安装开发依赖：

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

确认 Lua 编译器存在：

```bash
ls -l tool/bin/st-luac
```

如果当前在 `docs/` 目录下，可以先回到项目根目录：

```bash
cd ..
```

也可以使用相对上级路径执行命令，例如：

```bash
../.venv/bin/python -m xhcart_core pack-header-icon ../tests/pack.json -o ../build/cart.bin
```

## 2. 一键生成 cart.bin

推荐使用根目录的 `main.py` 入口生成完整卡带镜像：

```bash
.venv/bin/python main.py tests/pack.json build/cart.bin
```

参数说明：

- `tests/pack.json`：打包配置文件路径。
- `build/cart.bin`：输出的卡带镜像路径。

构建过程中会按行输出 JSON 日志，例如：

```json
{"step": "icon", "status": "ok", "file_size": 167936, "icon_size": 160000}
```

## 3. 使用模块 CLI

也可以通过 Python 模块入口调用子命令：

```bash
.venv/bin/python -m xhcart_core --help
```

### 3.1 生成完整 cart.bin

```bash
.venv/bin/python -m xhcart_core pack-header-icon tests/pack.json -o build/cart.bin
```

这个命令会生成包含 Header、ICON、MANF、ENTRY、INDEX、DATA 的完整镜像。

### 3.2 只生成 header.bin

```bash
.venv/bin/python -m xhcart_core pack-header tests/pack.json build/header.bin
```

这个命令只生成 4096 字节的 Header 文件，适合调试 Header 字段。

### 3.3 查看 Header 和地址表

可以直接检查完整 `cart.bin`：

```bash
.venv/bin/python -m xhcart_core inspect-header build/cart.bin
```

也可以检查单独的 `header.bin`：

```bash
.venv/bin/python -m xhcart_core inspect-header build/header.bin
```

输出会包含基础字段和非空地址表槽位，例如 `ICON`、`MANF`、`ENTRY`、`INDEX`、`DATA`、`IMAGE_CRC`。

### 3.4 校验 Header CRC32

校验完整 `cart.bin`：

```bash
.venv/bin/python -m xhcart_core verify-header build/cart.bin
```

校验单独 `header.bin`：

```bash
.venv/bin/python -m xhcart_core verify-header build/header.bin
```

成功时输出：

```text
Header CRC32 verification PASSED
```

## 4. 启用整镜像 CRC32

在 `pack.json` 中设置：

```json
{
  "hash": {
    "header_crc32": true,
    "image_crc32": true,
    "per_chunk_crc32": false,
    "per_file_crc32": false
  }
}
```

然后重新打包：

```bash
.venv/bin/python main.py tests/pack.json build/cart.bin
```

检查地址表时会看到 `IMAGE_CRC` 槽位：

```bash
.venv/bin/python -m xhcart_core inspect-header build/cart.bin
```

## 5. 构建单文件可执行程序

安装 PyInstaller：

```bash
.venv/bin/python -m pip install pyinstaller
```

生成可执行文件：

```bash
.venv/bin/pyinstaller \
  --onefile \
  --name xhgc-pack \
  --add-binary "tool/bin/st-luac:tool/bin" \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import PIL.ImageOps \
  main.py
```

生成后可用：

```bash
dist/xhgc-pack tests/pack.json build/cart.bin
```

## 6. 常用验证组合

完整构建并校验：

```bash
.venv/bin/python main.py tests/pack.json build/cart.bin
.venv/bin/python -m xhcart_core inspect-header build/cart.bin
.venv/bin/python -m xhcart_core verify-header build/cart.bin
```

运行测试：

```bash
.venv/bin/python -m pytest -q
```
