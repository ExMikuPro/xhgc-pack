# XHGC_PACK · pack.json 规范（IDE → 打包器输入）v1.1

> 适用范围：本规范定义 `pack.json` 的**结构与语义**，用于 **IDE 生成/编辑 → 打包器读取**。  
> 重点：`pack.json` **只描述规则**（要打哪些内容、如何映射包内路径、如何预处理图标等），**不存放构建结果**（offset/size/CRC/索引表位置等）。  
> 日期：2026-02-21

---

## 0. 设计原则

1. **输入与输出分离**
   - `pack.json`：构建**输入规则**（可读、可维护、适合版本管理）
   - `pack.lock.json`（或任意 lock 文件）：构建**输出结果**（可重复构建、固件/工具读取偏移、CRC 等）

2. **只增不破坏（向后兼容）**
   - 继续保持 `pack_version = 1`
   - v1.1 仅新增字段与更明确的约束

3. **确定性构建**
   - 同一输入目录与同一配置应产生相同输出（排序、忽略临时文件、冲突直接报错）

---

## 1. 顶层结构（Top-level）

`pack.json` 顶层必须是一个 JSON Object，关键字段如下：

- `format`：包格式标识（固定 `XHGC_PACK`）
- `pack_version`：结构版本（固定 `1`）
- `meta`：元信息（标题、版本、入口、cart_id 等）
- `icon`：应用图标（唯一图标字段，对应 cart.bin slot0 ICON，固定 200×200 ARGB8888）
- `hash`：校验策略开关
- `build`：构建行为开关（不触及 bin 规范）
- `chunks`：装包规则（核心）

---

## 2. 字段表（v1.1）

> 说明：  
> - **必填**：表示该路径必须存在（或满足条件时必须存在）。  
> - **默认/固定值**：打包器未提供时的建议默认值。  
> - **兼容/备注**：描述约束、迁移建议、注意事项。

| JSON 路径 | 类型 | 必填 | 默认/固定值 | 说明 | 兼容/备注 |
|---|---|---:|---|---|---|
| `/format` | string | ✅ | `"XHGC_PACK"` | 包格式标识，用于识别 | v1 已存在 |
| `/pack_version` | int | ✅ | `1` | `pack.json` 结构版本（非应用版本） | v1 已存在 |
| `/meta` | object | ✅ |  | 应用/卡带元信息 | v1 已存在 |
| `/meta/title` | string | ✅ |  | 默认标题（≤ 64 字节 UTF-8，对应 bin Header `title[64]`，超出打包器报错） | v1 已存在 |
| `/meta/title_zh` | string | ⭕ |  | 中文标题（≤ 64 字节 UTF-8，对应 bin Header `title_zh[64]`） | v1 已存在 |
| `/meta/publisher` | string | ⭕ |  | 发行/作者（≤ 64 字节 UTF-8，对应 bin Header `publisher[64]`） | v1 已存在 |
| `/meta/version` | string | ✅ |  | 应用版本（建议 SemVer，≤ 32 字节，对应 bin Header `version_str[32]`） | v1 已存在 |
| `/meta/cart_id` | string | ✅ |  | 唯一 ID，格式为 `"0x"` + 16 位十六进制（u64 语义，IDE 自动生成随机值，打包器转换为 little-endian u64 写入 bin，溢出报错） | v1 已存在（用字符串避免 JSON 数字精度问题） |
| `/meta/entry` | string | ✅ |  | 运行入口（包内路径，≤ 128 字节，对应 bin Header `entry[128]`，必须存在于 chunks 输出集合，否则报错） | v1 已存在 |
| `/meta/min_fw` | string | ⭕ |  | 最低固件版本（≤ 32 字节，对应 bin Header `min_fw[32]`） | v1 已存在 |
| `/meta/id` | string | ⭕ |  | **新增建议**：反域名包名（如 `com.xxx.app`），用于商店/依赖/签名 | v1.1 新增 |
| `/meta/description` | object 或 string | ⭕ |  | **新增建议**：简介（可多语言），推荐 `{ "default": "...", "zh-CN": "..." }` | v1.1 新增 |
| `/meta/category` | string | ⭕ | `"app"` | **新增建议**：分类（game / tool / demo / app） | v1.1 新增 |
| `/meta/tags` | string[] | ⭕ | `[]` | **新增建议**：标签列表 | v1.1 新增 |
| `/meta/author` | object | ⭕ |  | **新增建议**：作者信息，格式 `{ "name": "...", "contact": "..." }` | v1.1 新增 |
| `/icon` | object | ✅ |  | 应用图标，对应 cart.bin **slot0(ICON)**，输出固定为 200×200 ARGB8888（160000 bytes） | 唯一图标字段，v1.1 正式字段 |
| `/icon/path` | string | ✅ |  | 源图路径（相对路径） | v1 已存在 |
| `/icon/format` | string | ✅ | `"ARGB8888"` | 输出像素格式，当前仅允许 `"ARGB8888"` | v1 已存在 |
| `/icon/width` | int | ✅ | `200` | 输出宽度，**必须为 200**，否则打包器报错 | v1 已存在，v1.1 锁定值 |
| `/icon/height` | int | ✅ | `200` | 输出高度，**必须为 200**，否则打包器报错 | v1 已存在，v1.1 锁定值 |
| `/icon/preprocess` | object | ⭕ |  | 预处理策略（缩放/补底色/采样） | v1 已存在 |
| `/icon/preprocess/mode` | string | ⭕ | `"contain"` | contain / cover / stretch | v1 已存在 |
| `/icon/preprocess/background` | string | ⭕ | `"#000000"` | 背景/补边色（`#RRGGBB` 或 `#AARRGGBB`） | v1 已存在 |
| `/icon/preprocess/resample` | string | ⭕ | `"bilinear"` | nearest / bilinear / bicubic / lanczos | v1 已存在 |
| `/hash` | object | ⭕ |  | 校验策略开关 | v1 已存在 |
| `/hash/header_crc32` | bool | ⭕ | `true` | 关键结构 CRC32（CRC-32/IEEE，计算范围见 bin 规范第 6 节） | v1 已存在 |
| `/hash/image_crc32` | bool | ⭕ | `false` | 图像段 CRC32 | v1 已存在 |
| `/hash/per_chunk_crc32` | bool | ⭕ | `false` | **新增建议**：每个 chunk CRC32，写入地址表槽 `crc32` 字段 | v1.1 新增 |
| `/hash/per_file_crc32` | bool | ⭕ | `false` | **新增建议**：每个文件条目 CRC32 | v1.1 新增 |
| `/build` | object | ⭕ |  | **新增建议**：构建行为（不涉及 bin 规范） | v1.1 新增 |
| `/build/alignment_bytes` | int | ⭕ | `4096` | 数据段对齐字节数，**必须为 2 的幂次，且 ≥ 512**，与 bin 规范 4KB 对齐一致；设置不合法值打包器报错 | v1.1 新增 |
| `/build/deterministic` | bool | ⭕ | `true` | 强制确定性构建（排序/忽略时间戳等） | v1.1 新增 |
| `/build/fail_on_conflict` | bool | ⭕ | `true` | 包内路径冲突直接报错 | v1.1 新增 |
| `/chunks` | array | ✅ |  | 装包规则列表（顺序决定 bin 中物理写入顺序，`MANF` 建议排第一） | v1 已存在 |
| `/chunks[i]/type` | string | ✅ |  | chunk 类型，合法值：`"MANF"` / `"LUA"` / `"RES"`（打包器内部映射为 bin slot，见第 3 节） | v1 已存在，v1.1 规范化合法值 |
| `/chunks[i]/compress` | string | ⭕ | `"none"` | 压缩方式（none / lz4） | v1 已存在 |
| `/chunks[i]/source` | string | ⭕ |  | `MANF` 专用：`"inline_meta"`（由 meta 字段自动生成 manifest 内容） | v1 已存在 |
| `/chunks[i]/name` | string | ⭕ |  | `MANF` 输出的包内路径 | v1 已存在 |
| `/chunks[i]/glob` | string | ⭕ |  | 文件匹配模式（支持 `**/*`） | v1 已存在 |
| `/chunks[i]/name_prefix` | string | ⭕ |  | 包内路径前缀 | v1 已存在 |
| `/chunks[i]/strip_prefix` | string | ⭕ |  | **新增建议**：显式剪掉输入路径前缀，防止重复前缀 | v1.1 新增 |
| `/chunks[i]/exclude` | string[] | ⭕ | `[]` | **新增建议**：排除模式列表，如 `["**/.DS_Store", "**/*.psd"]` | v1.1 新增 |
| `/chunks[i]/order` | string | ⭕ | `"lex"` | **新增建议**：排序策略（当前仅支持 `"lex"` 字典序），用于可重复构建 | v1.1 新增 |

---

## 3. chunk type → bin slot 映射

| chunk type | 写入 bin slot | 说明 |
|---|---|---|
| `MANF` | slot2 (MANF) | manifest 二进制，由 `inline_meta` 从 meta 字段生成 |
| `LUA` | slot5 (DATA) | Lua 脚本数据块 |
| `RES` | slot5 (DATA) | 资源文件数据块（与 LUA 合并写入 DATA 区） |

> `MANF` **建议排在 `chunks` 列表第一位**，以保证 bin 中 manifest 优先写入，便于固件端快速读取元信息。  
> INDEX（slot4）由打包器根据 DATA 区内容自动生成，**不需要**在 `pack.json` 中声明。

### 3.1 MANF 二进制格式

MANF 不使用 JSON，采用带偏移表的自定义二进制格式，解析端直接按 field_id 查表读取，无需 JSON 解析器。

**结构体定义：**

```c
// MANF Header（固定 16 bytes）
typedef struct __attribute__((packed)) {
    uint32_t magic;        // 固定 0x464E414D ("MANF")
    uint32_t version;      // 固定 1
    uint32_t total_size;   // 整个 MANF 段字节数
    uint32_t field_count;  // 字段数量（只写入有值的字段）
} XhgcManfHeader;

// 偏移表条目（每条 8 bytes，紧跟 Header 后）
typedef struct __attribute__((packed)) {
    uint8_t  field_id;     // 字段 ID（见下表）
    uint8_t  reserved[3];  // 填 0
    uint32_t offset;       // 相对 MANF 段起点的字节偏移
} XhgcManfFieldEntry;

// 字段数据（变长，紧跟偏移表后）
typedef struct __attribute__((packed)) {
    uint16_t size;         // 数据长度 bytes
    // 紧跟 size bytes 的实际数据（UTF-8 字符串或二进制）
} XhgcManfField;
```

**字段 ID 表：**

| field_id | 字段 | 类型 | 对应 meta 字段 |
|---|---|---|---|
| `0x01` | title | UTF-8 字符串 | `meta.title` |
| `0x02` | title_zh | UTF-8 字符串 | `meta.title_zh` |
| `0x03` | publisher | UTF-8 字符串 | `meta.publisher` |
| `0x04` | version | UTF-8 字符串 | `meta.version` |
| `0x05` | cart_id | u64 little-endian | `meta.cart_id`（字符串转 u64） |
| `0x06` | entry | UTF-8 字符串 | `meta.entry` |
| `0x07` | min_fw | UTF-8 字符串 | `meta.min_fw` |
| `0x08` | id | UTF-8 字符串 | `meta.id` |
| `0x09` | description_default | UTF-8 字符串 | `meta.description.default` |
| `0x0A` | description_zh | UTF-8 字符串 | `meta.description["zh-CN"]` |
| `0x0B` | category | UTF-8 字符串 | `meta.category` |
| `0x0C` | tags | UTF-8 字符串，多个 tag 用 `\n` 分隔 | `meta.tags` |
| `0x0D` | author_name | UTF-8 字符串 | `meta.author.name` |
| `0x0E` | author_contact | UTF-8 字符串 | `meta.author.contact` |

**内存布局：**

```
[ XhgcManfHeader (16B)              ]
[ XhgcManfFieldEntry #0 (8B)        ]
[ XhgcManfFieldEntry #1 (8B)        ]
...
[ XhgcManfFieldEntry #N-1 (8B)      ]
[ XhgcManfField #0: size(2B) + data ]
[ XhgcManfField #1: size(2B) + data ]
...
```

**打包规则：**
- 只写入有值的字段，空字段跳过
- `cart_id` 字符串（如 `"0x0123456789ABCDEF"`）转换为 little-endian u64 写入
- 偏移表中的 `offset` 是相对 MANF 段起点的字节偏移

---

## 4. `chunks` 路径映射规则

对每个 `glob` 匹配到的文件：

1. 先应用 `exclude`（如果有）
2. 计算输入相对路径：
   - 若存在 `strip_prefix`：从文件路径中剪掉该前缀后得到 `relpath`
   - 否则：使用"glob 根目录"的相对路径（打包器内部推导）
3. 生成包内路径：`pack_path = name_prefix + relpath`
4. 同一 chunk 内按 `order`（默认字典序）排序写入
5. 若两个条目生成同一 `pack_path`：
   - `build.fail_on_conflict = true` 时**必须报错退出**（推荐默认值）

---

## 5. `meta.entry` 一致性规则（强制）

- `meta.entry` 指向的包内路径必须存在于 `chunks` 生成的输出集合中。
- 若不存在，打包器**必须报错退出**。

---

## 6. 错误等级表

| 场景 | 等级 | 行为 |
|---|---|---|
| `meta.entry` 在 chunks 输出中不存在 | ERROR | 报错退出 |
| `icon.width` 或 `icon.height` 不为 200 | ERROR | 报错退出 |
| `icon.format` 不为 `"ARGB8888"` | ERROR | 报错退出 |
| 包内路径冲突（`fail_on_conflict = true`） | ERROR | 报错退出 |
| `build.alignment_bytes` 不是 2 的幂次或 < 512 | ERROR | 报错退出 |
| `meta.cart_id` 格式非法（非 `0x` + 16 位十六进制） | ERROR | 报错退出 |
| `meta.cart_id` 值溢出 u64 | ERROR | 报错退出 |
| `meta.title` / `publisher` 等超出 bin Header 字段长度 | ERROR | 报错退出 |
| `chunk.type` 为未知值 | ERROR | 报错退出 |
| `glob` 匹配不到任何文件 | WARNING | 打印警告，继续构建 |
| `icon` 源文件不存在 | ERROR | 报错退出 |
| `compress` 值非法 | ERROR | 报错退出 |
| 遇到未知字段（新版字段在旧工具中） | IGNORE | 静默忽略，不失败 |

---

## 7. 最小示例

```json
{
  "format": "XHGC_PACK",
  "pack_version": 1,
  "meta": {
    "title": "Gallery",
    "title_zh": "相册",
    "publisher": "Nixie",
    "version": "0.1.0",
    "cart_id": "0x0000000000000001",
    "entry": "app/main.lua",
    "min_fw": "0.1.0"
  },
  "icon": {
    "path": "assets/icon.png",
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
    { "type": "MANF", "source": "inline_meta", "name": "meta/manifest.json" },
    {
      "type": "LUA",
      "glob": "script/**/*.lua",
      "strip_prefix": "script/",
      "name_prefix": "app/",
      "compress": "none"
    },
    {
      "type": "RES",
      "glob": "assets/lvgl/**/*",
      "strip_prefix": "assets/lvgl/",
      "name_prefix": "assets/lvgl/",
      "compress": "none",
      "exclude": ["**/.DS_Store"]
    }
  ]
}
```

---

## 8. IDE 配置建议（可选）

- `meta.cart_id` 建议由 IDE 在新建项目时**自动生成随机 u64**，开发者不应手动填写，避免碰撞。
- `chunks` 做成"规则列表"UI：
  - 选择类型（MANF / LUA / RES）
  - 选择输入（inline_meta 或 glob）
  - 选择输出前缀（name_prefix）
  - 可选：strip_prefix / exclude / compress / order
- 图标选择器限制只能选图片文件，preprocess 参数提供可视化预览。

---

## 9. 版本记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v1.0 | - | 初始版本 |
| v1.1 | 2026-02-21 | 移除 `icons` 多变体容器，`icon` 升为正式唯一图标字段并锁定 200×200；新增 `build` 对象；新增 chunk `strip_prefix` / `exclude` / `order`；新增 chunk type → bin slot 映射表；新增 MANF 二进制格式定义（字段 ID 表、结构体、内存布局）；新增错误等级表；补全 meta 字段与 bin Header 长度约束对齐；规范 `cart_id` 转换规则；规范 `alignment_bytes` 合法值约束 |