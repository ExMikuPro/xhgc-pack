# XHGC 卡带镜像打包工具

XHGC 卡带镜像打包工具是一个用于构建 XHGC 卡带镜像（cart.bin）的命令行工具，支持将 Lua 脚本、资源文件和元数据打包成符合 XHGC 卡带镜像格式规范的二进制文件。

## 功能特点

- **多段构建**：支持构建 ICON、MANF、ENTRY、DATA 和 INDEX 段
- **二进制 MANF 格式**：采用高效的二进制格式存储元数据，便于 STM32 端快速读取
- **资源打包**：支持将 Lua 脚本和资源文件打包到 DATA 区
- **文件索引**：自动生成 INDEX 表，支持按文件名查找资源
- **JSON 输出**：实时输出构建过程的 JSON 格式日志，便于 IDE 集成
- **CRC32 校验**：支持 Header、段和整个镜像的 CRC32 校验

## 安装

### 依赖项

- Python 3.8+
- Pillow (用于图像处理)
- st-luac (用于 Lua 脚本编译，需单独安装)

### 安装步骤

1. 克隆项目仓库：
   ```bash
   git clone https://github.com/your-username/xhgc-pack.git
   cd xhgc-pack
   ```

2. 安装 Python 依赖：
   ```bash
   pip install -e .
   ```

3. 安装 st-luac：
   - 按照 `docs/st-luac-compilation-guide.md` 中的说明编译并安装 st-luac
   - 确保 st-luac 可执行文件位于 `tool/bin/st-luac`

## 使用方法


### 编译为可执行文件

```shell
.venv/bin/pip install pyinstaller  
```

```shell
.venv/bin/pyinstaller \
  --onefile \
  --name xhgc-pack \
  --add-binary "tool/bin/st-luac:tool/bin" \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import PIL.ImageOps \
  main.py
```

### 基本用法

```bash
python main.py <pack.json> <output/cart.bin>
```

### 配置文件格式

`pack.json` 是打包工具的配置文件，用于指定卡带的元数据、图标和打包规则。

#### 示例配置

```json
{
  "format": "XHGC_PACK",
  "pack_version": 1,

  "meta": {
    "title": "Hatsune Miku",
    "title_zh": "演示游戏",
    "publisher": "ExMikuPro",
    "version": "0.1.0",
    "cart_id": "0x0123456789ABCDEF",
    "entry": "app/main.lua",
    "min_fw": "0.8.0",
    "id": "com.exmikupro.studio.hatsune-miku",
    "description": {
      "default": "A demo game featuring Hatsune Miku",
      "zh-CN": "一个以初音未来为主题的演示游戏"
    },
    "category": "game",
    "tags": ["demo", "game", "hatsune-miku"],
    "author": {
      "name": "ExMikuPro",
      "contact": "contact@nixie.studio"
    }
  },

  "icon": {
    "path": "meta/icon.png",
    "format": "ARGB8888",
    "width": 200,
    "height": 200,
    "preprocess": {
      "mode": "contain",
      "background": "#000000",
      "resample": "lanczos"
    }
  },

  "hash": {
    "header_crc32": true,
    "image_crc32": false,
    "per_chunk_crc32": false,
    "per_file_crc32": false
  },

  "build": {
    "alignment_bytes": 4096,
    "deterministic": true,
    "fail_on_conflict": true
  },

  "chunks": [
    {
      "type": "MANF",
      "source": "inline_meta",
      "name": "meta/manifest.json"
    },
    {
      "type": "LUA",
      "glob": "script/main.lua",
      "strip_prefix": "script/",
      "name_prefix": "app/",
      "compress": "none",
      "exclude": ["**/.DS_Store"],
      "order": "lex"
    },
    {
      "type": "RES",
      "glob": "assets/**/*",
      "strip_prefix": "assets/",
      "name_prefix": "assets/",
      "compress": "none",
      "exclude": ["**/.DS_Store"],
      "order": "lex"
    }
  ]
}
```

## 构建流程

打包工具按照以下顺序构建卡带镜像：

1. **ICON 段**：处理图标文件，转换为 ARGB8888 格式
2. **MANF 段**：从 meta 字段生成二进制格式的元数据
3. **ENTRY 段**：编译 Lua 脚本，生成字节码
4. **DATA 段**：打包资源文件，生成文件数据
5. **INDEX 段**：生成文件索引表，支持按文件名查找

## 输出格式

构建过程中，打包工具会输出 JSON 格式的日志，每条日志独占一行：

### 成功日志示例

```json
{"step": "icon", "status": "ok", "file_size": 167936, "icon_size": 160000, "padding_size": 3840, "header_crc32": "0xABBF403C"}
```
```json
{"step": "manf", "status": "ok", "file_size": 172032, "manf_offset": 167936, "manf_size": 388, "manf_crc32": "0x02948D1C", "padding_size": 3708}
```
```json
{"step": "entry", "status": "ok", "file_size": 184320, "entry_offset": 172032, "entry_size": 8270, "entry_crc32": "0x43FF22E4", "padding_size": 4018}
```
```json
{"step": "data", "status": "ok", "file_size": 4903080, "index_offset": 184320, "index_size": 168, "index_crc32": "0xE061AF88", "data_offset": 188416, "data_size": 4715726, "data_crc32": "0x44CDBB31", "padding_size": 2866, "files_in_data": 3}
```

### 错误日志示例

```json
{"step": "entry", "status": "error", "message": "st-luac not found"}
```

## 卡带镜像格式

生成的 cart.bin 文件结构如下：

| 区段 | 偏移 | 大小 | 用途 |
|------|------|------|------|
| HEADER | 0x00000000 | 4096 | 元信息 + 地址表 + CRC32 |
| ICON | 0x00001000 | 160000 | 图标数据 |
| MANF | 4KB 对齐 | 变长 | 元数据 |
| ENTRY | 4KB 对齐 | 变长 | Lua 字节码 |
| INDEX | 4KB 对齐 | 变长 | 文件索引表 |
| DATA | 4KB 对齐 | 变长 | 资源文件数据 |

## 开发指南

### 主要模块

- **build_icon.py**：处理图标构建
- **build_manf.py**：处理元数据构建
- **build_entry.py**：处理 Lua 脚本编译和构建
- **build_data.py**：处理资源文件打包和索引生成
- **api.py**：提供命令行接口

### 扩展功能

要扩展打包工具的功能，可以修改以下文件：

1. **添加新的段类型**：在 `pipeline` 目录下创建新的构建模块
2. **修改输出格式**：修改各构建模块中的 JSON 输出部分
3. **添加新的配置选项**：修改 `config/pack_spec.py` 和 `config/load.py`
