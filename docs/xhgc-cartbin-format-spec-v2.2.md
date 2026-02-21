# XHGC 卡带镜像（cart.bin）格式规范 v2.2（中文）

> 适用范围：本规范描述 `cart.bin` 的**固定 Header + 固定映射表（地址表）+ 若干数据段**的二进制布局。  
> 目标：让 **PC 打包器**与各端解析保持一致；并为后续扩展（MANF/INDEX/DATA/A8 等）预留空间。

---

## 1. 总览

`cart.bin` 是一份"卡带镜像"，由以下部分组成：

1. **Header（固定 4096 bytes）**：元信息、映射表（地址表）、Header CRC。
2. **数据段（Segments）**：ICON / THMB / MANF / ENTRY / INDEX / DATA / …（通过映射表定位）。
3. **Padding（对齐填充）**：用于让后续段从 4KB 边界开始写入。

> 本规范默认偏移均为**相对镜像起点（文件起点）**的字节偏移（byte offset）。  
> 无论 `cart.bin` 放在 SD 文件系统还是 eMMC 裸区，解析逻辑一致。

---

## 2. 端序与编码

- 所有整数类型字段 **必须（MUST）** 为 **Little-Endian**。
- 字符串字段 **必须（MUST）** 为 **UTF-8**，并采用定长写法：
  - 以 `\0` 终止（如果不足定长）
  - 剩余字节填 `0x00`
  - 若字符串正好填满且无 `\0`，解析端按定长截断处理

---

## 3. 文件整体布局

### 3.1 完整镜像布局

| 区段 | 起始偏移 | 大小 | 用途 |
|---|---:|---:|---|
| HEADER | `0x0000_0000` | 4096 | 元信息 + 映射表 + Header CRC |
| ICON（ARGB8888, 200×200） | `0x0000_1000` | 160000 | launcher 图标原始像素 |
| PADDING | after ICON | 到 4KB 对齐 | 补齐到下一段起点 |
| MANF | 4KB 对齐起点 | 变长 | manifest JSON（由 pack.json meta 生成） |
| PADDING | after MANF | 到 4KB 对齐 | 补齐 |
| INDEX | 4KB 对齐起点 | 变长 | 文件索引表（打包器自动生成） |
| PADDING | after INDEX | 到 4KB 对齐 | 补齐 |
| DATA | 4KB 对齐起点 | 变长 | 所有 LUA / RES 文件数据 |
| PADDING | after DATA | 到 4KB 对齐 | 文件末尾补齐 |

### 3.2 最小镜像（仅 ICON）

最小镜像只包含 Header + ICON，其余 slot 全 0，向后兼容：

| 区段 | 起始偏移 | 结束偏移 | 大小 |
|---|---:|---:|---:|
| HEADER | `0x0000_0000` | `0x0000_0FFF` | 4096 |
| ICON | `0x0000_1000` | `0x0002_80FF` | 160000 |
| PADDING | `0x0002_8100` | `…` | 到 4KB 对齐 |

### 3.3 对齐规则

- Header 长度固定：`4096` bytes。
- 各段 `offset` **建议（SHOULD）** 4KB 对齐（`4096` 对齐），便于裸写/扩展。
- 文件末尾 **建议（SHOULD）** pad 到 4KB 对齐。
- Padding 字节填 `0x00`。

---

## 4. Header（固定 4096 bytes）

### 4.1 Header 基本字段（固定偏移）

| 字段 | 偏移 | 类型 | 长度 | 说明 |
|---|---:|---|---:|---|
| `magic` | `0x0000` | bytes | 8 | 固定 `"XHGC_PAC"` |
| `header_version` | `0x0008` | u32 | 4 | 固定 `2` |
| `header_size` | `0x000C` | u32 | 4 | 固定 `4096` |
| `flags` | `0x0010` | u32 | 4 | 预留，当前填 0 |
| `cart_id` | `0x0014` | u64 | 8 | 卡带唯一 ID（对应 pack.json `meta.cart_id`，little-endian u64） |
| `title` | `0x001C` | char[64] | 64 | 主标题（UTF-8，对应 `meta.title`） |
| `title_zh` | `0x005C` | char[64] | 64 | 中文标题（UTF-8，对应 `meta.title_zh`，可为空） |
| `publisher` | `0x009C` | char[64] | 64 | 发行方/作者（对应 `meta.publisher`，可为空） |
| `version_str` | `0x00DC` | char[32] | 32 | 版本号字符串（对应 `meta.version`） |
| `entry` | `0x00FC` | char[128] | 128 | 入口脚本路径（对应 `meta.entry`，如 `app/main.lua`） |
| `min_fw` | `0x017C` | char[32] | 32 | 最低固件版本（对应 `meta.min_fw`，可为空） |
| `reserved` | `0x019C..0x0EFF` | bytes | - | 预留区，**必须填 0** |
| `addr_table` | `0x0F00..0x0FFB` | bytes | 252 | 固定地址表（映射表） |
| `header_crc32` | `0x0FFC..0x0FFF` | u32 | 4 | Header CRC32/IEEE（见第 6 节） |

---

## 5. 固定地址表（映射表 / Address Table）

### 5.1 位置与大小（固定）

- 地址表区域 **必须（MUST）** 固定：`0x0F00 .. 0x0FFB`（252 bytes）
- 槽位数：`252 / 16 = 15` 个槽（slot0..slot14）
- 每槽固定 16 bytes：

```c
// 16 bytes, little-endian
typedef struct __attribute__((packed)) {
  uint64_t offset;  // 段在镜像内的 byte offset（相对镜像起点）
  uint32_t size;    // 段长度（bytes）
  uint32_t crc32;   // 可选：该段 CRC32/IEEE；未启用填 0
} XhgcAddrSlot;
```

### 5.2 槽位定义（固定编号）

| slot | 表内偏移 | 名称 | 用途 |
|---:|---:|---|---|
| 0 | `0x0F00` | ICON | 200×200 ARGB8888 图标（对应 pack.json `icon`） |
| 1 | `0x0F10` | THMB | 缩略图（可选） |
| 2 | `0x0F20` | MANF | manifest JSON（对应 pack.json `meta` 全量内容） |
| 3 | `0x0F30` | ENTRY | 入口脚本数据块（可选：若不走文件路径） |
| 4 | `0x0F40` | INDEX | 文件索引表（打包器自动生成，DATA 区的文件目录） |
| 5 | `0x0F50` | DATA | 数据区（LUA + RES 文件数据，对应 pack.json `chunks` 中 LUA/RES） |
| 6 | `0x0F60` | BNR | banner（可选） |
| 7 | `0x0F70` | COVR | cover（可选） |
| 8 | `0x0F80` | TITLE_A8 | 应用名 A8 mask（可选） |
| 9..14 | `0x0F90..0x0FE0` | RESV | 预留 |

### 5.3 未使用槽位填写规则

- 未使用的槽位：`offset = 0`，`size = 0`，`crc32 = 0`。
- 解析端：`size == 0` 表示该段不存在，应跳过。

---

## 6. CRC 规则

### 6.1 Header CRC（推荐启用）

- CRC 字段位置：Header 最后 4 bytes：`0x0FFC..0x0FFF`
- 算法：**CRC-32/IEEE**（等价 Python `zlib.crc32`）
  - Poly: `0x04C11DB7`
  - Init: `0xFFFFFFFF`
  - RefIn/RefOut: true
  - XorOut: `0xFFFFFFFF`

**计算规则（必须一致）：**

1. 计算时将 `0x0FFC..0x0FFF` 视为 `0x00000000`
2. 对整段 4096 bytes Header 计算 CRC32/IEEE
3. 将结果以 little-endian 写回 `0x0FFC..0x0FFF`

### 6.2 段 CRC（可选）

- 地址表每槽里的 `crc32` 字段可用于保存该段的 CRC32/IEEE。
- 当前未启用时 **必须（MUST）** 填 0。
- 对应 pack.json `hash.per_chunk_crc32 = true` 时打包器写入。

---

## 7. 段格式定义

### 7.1 ICON（slot0）

- 来源：pack.json `icon` 字段，经打包器预处理后写入。
- 尺寸固定：`200 × 200`
- 像素格式：`ARGB8888`
- 存储顺序：row-major，从上到下、从左到右
- 每像素 4 bytes：`A, R, G, B`（建议 A=0xFF 表示不透明）
- 大小固定：`200 × 200 × 4 = 160000` bytes

### 7.2 MANF（slot2）

- 来源：pack.json `chunks` 中 `type = "MANF"` 且 `source = "inline_meta"` 的条目，由打包器从 `meta` 字段自动生成。
- 格式：**UTF-8 JSON**，无 BOM，不保证 pretty-print（打包器可压缩输出）。
- 内容：`meta` 下所有字段的完整导出（包括 `id`、`description`、`category`、`tags`、`author` 等 v1.1 新增字段）。
- 大小：变长，由实际 JSON 内容决定。
- 段内无额外 framing，解析端按地址表 `size` 字段读取后直接解析 JSON。

> Header 里的 `title` / `entry` 等字段是为**快速读取**而设的定长副本，MANF 是完整结构化元数据，两者内容必须一致。

**MANF JSON 示例（由打包器生成）：**

```json
{
  "title": "Hatsune Miku",
  "title_zh": "演示游戏",
  "publisher": "Nixie Studio",
  "version": "0.1.0",
  "cart_id": "0x0123456789ABCDEF",
  "entry": "app/main.lua",
  "min_fw": "0.8.0",
  "id": "com.nixie.studio.hatsune-miku",
  "description": {
    "default": "A demo game featuring Hatsune Miku",
    "zh-CN": "一个以初音未来为主题的演示游戏"
  },
  "category": "game",
  "tags": ["demo", "game", "hatsune-miku"],
  "author": {
    "name": "Nixie Studio",
    "contact": "contact@nixie.studio"
  }
}
```

### 7.3 INDEX（slot4）

- 来源：打包器根据 DATA 区内容**自动生成**，pack.json 中无需声明。
- 用途：DATA 区的文件目录，解析端通过 INDEX 定位 DATA 内某个文件。

**INDEX Header（8 bytes）：**

```c
typedef struct __attribute__((packed)) {
  uint32_t entry_count;   // 文件条目数量
  uint32_t reserved;      // 预留，填 0
} XhgcIndexHeader;
```

**INDEX Entry（每条目 16 bytes 定长头 + 变长路径名）：**

```c
typedef struct __attribute__((packed)) {
  uint32_t data_offset;   // 相对 DATA 段起点的字节偏移
  uint32_t data_size;     // 文件数据长度（bytes）
  uint32_t crc32;         // 文件 CRC32/IEEE（未启用填 0，对应 pack.json hash.per_file_crc32）
  uint8_t  name_len;      // 包内路径字符串长度（bytes，不含 \0）
  uint8_t  reserved[3];   // 预留，填 0
  // 紧跟：name_len bytes 的 UTF-8 包内路径（不含 \0）
} XhgcIndexEntry;
```

**INDEX 整体内存布局：**

```
[ XhgcIndexHeader (8B)       ]
[ XhgcIndexEntry #0 头 (16B) ][ name #0 ]
[ XhgcIndexEntry #1 头 (16B) ][ name #1 ]
...
[ XhgcIndexEntry #N-1 头     ][ name #N-1 ]
```

- 所有条目按包内路径**字典序升序**排列（与 pack.json `order = "lex"` 对应），支持二分查找。

### 7.4 DATA（slot5）

- 来源：pack.json `chunks` 中 `type = "LUA"` 和 `type = "RES"` 的条目，按 chunks 列表顺序、同一 chunk 内字典序写入。
- 格式：所有文件数据**连续拼接**，无额外 framing。
- 文件边界由 INDEX 条目的 `data_offset` + `data_size` 定位，DATA 段本身无分隔符。
- 压缩：若 pack.json 对应 chunk 设置 `compress = "lz4"`，则该文件在 DATA 中存储压缩后数据，`data_size` 为压缩后大小；`crc32` 计算对象为**压缩后数据**。

> 当前 `compress` 仅支持 `"none"` 和 `"lz4"`。  
> 读取流程：INDEX 查找路径 → 得到 `data_offset` / `data_size` → 从 DATA 段偏移读取 → 若压缩则解压。

### 7.5 TITLE_A8（slot8，可选）

- 高度固定：`20 px`
- 宽度不固定：`w`
- 像素格式：`A8`（每像素 1 byte alpha）
- 存储顺序：row-major
- 段大小：`size = w × 20`

> A8 仅提供 alpha 遮罩，颜色由渲染端在运行时指定（tint）。

---

## 8. Quick Reference（速查表）

**Header（4096B）关键偏移：**

- magic：`0x0000`（8B）
- version：`0x0008`（u32）
- header_size：`0x000C`（u32）
- flags：`0x0010`（u32）
- cart_id：`0x0014`（u64）
- title：`0x001C`（64B）
- title_zh：`0x005C`（64B）
- publisher：`0x009C`（64B）
- version_str：`0x00DC`（32B）
- entry：`0x00FC`（128B）
- min_fw：`0x017C`（32B）
- addr_table：`0x0F00`（252B）
- header_crc32：`0x0FFC`（u32）

**地址表槽位：**

- slot_size：`0x10`（16B）
- slot0 (ICON)：`0x0F00`
- slot1 (THMB)：`0x0F10`
- slot2 (MANF)：`0x0F20`
- slot3 (ENTRY)：`0x0F30`
- slot4 (INDEX)：`0x0F40`
- slot5 (DATA)：`0x0F50`
- slot6 (BNR)：`0x0F60`
- slot7 (COVR)：`0x0F70`
- slot8 (TITLE_A8)：`0x0F80`

**pack.json → bin 对应关系：**

| pack.json | bin |
|---|---|
| `meta.*` | Header 定长字段 + slot2(MANF) JSON |
| `icon` | slot0(ICON) 160000B ARGB8888 |
| `chunks[MANF]` | slot2(MANF) |
| `chunks[LUA]` / `chunks[RES]` | slot5(DATA)，目录在 slot4(INDEX) |

---

## 9. 版本记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v2.1 | - | 修订 ICON 段为 ARGB8888（200×200，160000B） |
| v2.2 | 2026-02-21 | 补全 slot2(MANF) / slot4(INDEX) / slot5(DATA) 格式定义；补充完整镜像布局表；新增 INDEX 结构体定义；新增 pack.json → bin 对应关系速查；更新槽位说明与 pack.json 字段对应 |
