from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.utils.align import align_to
from src.xhcart_core.utils.hashing import calculate_crc32
from src.xhcart_core.format.xhgc.addr_table import AddrTable
import struct

class BuildManf:
    """
    构建MANF段的类
    """
    
    # 固定常量
    HEADER_SIZE = 4096
    ALIGN_SIZE = 4096
    
    # MANF Header 固定值
    MANF_MAGIC = 0x464E414D  # "MANF"
    MANF_VERSION = 1
    
    # 字段ID映射
    FIELD_IDS = {
        'title': 0x01,
        'title_zh': 0x02,
        'publisher': 0x03,
        'version': 0x04,
        'cart_id': 0x05,
        'entry': 0x06,
        'min_fw': 0x07,
        'id': 0x08,
        'description_default': 0x09,
        'description_zh': 0x0A,
        'category': 0x0B,
        'tags': 0x0C,
        'author_name': 0x0D,
        'author_contact': 0x0E
    }
    
    def __init__(self, pack_spec: PackSpec):
        """
        初始化BuildManf
        
        Args:
            pack_spec (PackSpec): 配置数据
        """
        self.pack_spec = pack_spec
    
    def build(self, out_path: str):
        """
        构建包含MANF段的cart.bin
        
        Args:
            out_path (str): 输出文件路径
        """
        # 读取现有的cart.bin文件
        with open(out_path, 'rb') as f:
            cart_data = bytearray(f.read())
        
        # 提取header数据
        header_data = bytearray(cart_data[:self.HEADER_SIZE])
        
        # 构建MANF段数据
        manf_content = self._build_manf_content()
        
        # 计算MANF大小和CRC32
        manf_size = len(manf_content)
        manf_crc32 = calculate_crc32(manf_content) if manf_size > 0 else 0
        
        # 计算MANF偏移量（4KB对齐）
        manf_offset = align_to(len(cart_data), self.ALIGN_SIZE)
        
        # 写入slot2 (MANF)
        AddrTable.write_slot(header_data, AddrTable.SLOT_MANF, manf_offset, manf_size, manf_crc32)
        
        # 计算总大小并对齐
        total_size = manf_offset + manf_size
        aligned_size = align_to(total_size, self.ALIGN_SIZE)
        padding_size = aligned_size - total_size
        padding = b'\x00' * padding_size
        
        # 从配置中读取CRC32设置
        header_crc32 = True  # 默认计算header的CRC32
        image_crc32 = False  # 默认不计算整个镜像的CRC32
        
        if self.pack_spec.hash:
            header_crc32 = self.pack_spec.hash.header_crc32
            image_crc32 = self.pack_spec.hash.image_crc32
        
        # 计算并写入Header CRC32
        if header_crc32:
            header_data_with_crc = self.calculate_and_write_header_crc(header_data)
        else:
            header_data_with_crc = header_data
        
        # 组装完整数据（包含更新后的header）
        cart_data = header_data_with_crc + cart_data[self.HEADER_SIZE:] + manf_content + padding
        
        # 如果需要计算整个镜像的CRC32
        if image_crc32:
            # 计算整个镜像的CRC32
            image_crc = calculate_crc32(cart_data)
            
            # 创建新的header副本，写入镜像CRC32到slot6
            final_header_data = header_data_with_crc.copy()
            AddrTable.write_slot(final_header_data, 6, 0, len(cart_data), image_crc)
            
            # 再次计算Header CRC32（因为修改了slot6）
            if header_crc32:
                final_header_data = self.calculate_and_write_header_crc(final_header_data)
            
            # 最终组装数据
            cart_data = final_header_data + cart_data[self.HEADER_SIZE:] + manf_content + padding
        
        # 原子写入文件
        atomic_write(out_path, cart_data)
        
        # 输出JSON格式结果
        import json, sys
        result = {
            "step": "manf",
            "status": "ok",
            "file_size": len(cart_data),
            "manf_offset": manf_offset,
            "manf_size": manf_size,
            "manf_crc32": f"0x{manf_crc32:08X}",
            "padding_size": len(padding)
        }
        print(json.dumps(result))
        sys.stdout.flush()

    def _build_manf_content(self):
        """
        构建MANF段内容

        Returns:
            bytearray: MANF段内容
        """
        manf_content = bytearray()
        field_entries = []
        field_data = bytearray()

        # 收集字段数据
        fields = self._collect_fields()

        # 计算字段数据偏移
        current_offset = 16  # Header 16B
        current_offset += len(fields) * 8  # 每个entry 8B

        # 构建字段条目和数据
        for field_name, field_value in fields.items():
            if field_value is None:
                continue

            # 获取字段ID
            field_id = self.FIELD_IDS.get(field_name)
            if not field_id:
                continue

            # 构建字段数据
            if field_name == 'cart_id':
                # 转换cart_id为u64 little-endian
                try:
                    cart_id_value = int(field_value, 0)  # 支持0x前缀
                    field_bytes = struct.pack('<Q', cart_id_value)
                except ValueError:
                    continue
            else:
                # 其他字段为UTF-8字符串
                field_bytes = field_value.encode('utf-8')

            # 写入字段大小和数据
            field_size = len(field_bytes)
            field_data.extend(struct.pack('<H', field_size))
            field_data.extend(field_bytes)

            # 构建字段条目
            entry = struct.pack('<B', field_id)  # field_id
            entry += b'\x00\x00\x00'  # reserved[3]
            entry += struct.pack('<I', current_offset)  # offset
            field_entries.append(entry)

            # 更新偏移
            current_offset += 2 + field_size  # size(2B) + data

        # 构建MANF Header
        entry_count = len(field_entries)
        header = struct.pack('<I', self.MANF_MAGIC)  # magic
        header += struct.pack('<I', self.MANF_VERSION)  # version
        header += struct.pack('<I', current_offset)  # total_size
        header += struct.pack('<I', entry_count)  # field_count

        # 组装MANF内容
        manf_content.extend(header)
        for entry in field_entries:
            manf_content.extend(entry)
        manf_content.extend(field_data)

        return manf_content

    def _collect_fields(self):
        """
        从meta收集字段数据

        Returns:
            dict: 字段数据字典
        """
        meta = self.pack_spec.meta
        fields = {}

        # 基本字段
        fields['title'] = getattr(meta, 'title', None)
        fields['title_zh'] = getattr(meta, 'title_zh', None)
        fields['publisher'] = getattr(meta, 'publisher', None)
        fields['version'] = getattr(meta, 'version', None)
        fields['cart_id'] = getattr(meta, 'cart_id', None)
        fields['entry'] = getattr(meta, 'entry', None)
        fields['min_fw'] = getattr(meta, 'min_fw', None)
        fields['id'] = getattr(meta, 'id', None)

        # 描述字段
        if hasattr(meta, 'description') and meta.description:
            if isinstance(meta.description, dict):
                fields['description_default'] = meta.description.get('default', None)
                fields['description_zh'] = meta.description.get('zh-CN', None)
            else:
                fields['description_default'] = meta.description

        # 类别和标签
        fields['category'] = getattr(meta, 'category', None)

        if hasattr(meta, 'tags') and meta.tags:
            if isinstance(meta.tags, list):
                fields['tags'] = '\n'.join(meta.tags)
            else:
                fields['tags'] = meta.tags

        # 作者信息
        if hasattr(meta, 'author') and meta.author:
            if isinstance(meta.author, dict):
                fields['author_name'] = meta.author.get('name', None)
                fields['author_contact'] = meta.author.get('contact', None)
            else:
                fields['author_name'] = meta.author

        # 过滤空值
        return {k: v for k, v in fields.items() if v is not None}

    def calculate_and_write_header_crc(self, header_bytes):
        """
        计算并写入Header CRC32

        Args:
            header_bytes (bytearray): 原始header数据（长度为4096）

        Returns:
            bytearray: 包含CRC32的header数据
        """
        import struct
        from src.xhcart_core.format.xhgc.header import HeaderV2

        # 确保输入数据长度为4096
        if len(header_bytes) != 4096:
            raise ValueError("Header length must be 4096 bytes")

        # 创建一个副本，将CRC区域置为0
        header_copy = header_bytes.copy()
        header_copy[HeaderV2.CRC_OFFSET:HeaderV2.CRC_OFFSET+4] = b'\x00\x00\x00\x00'

        # 计算CRC32
        crc = calculate_crc32(header_copy)

        # 以little-endian方式写入CRC32到0x0FFC..0x0FFF
        struct.pack_into('<I', header_bytes, HeaderV2.CRC_OFFSET, crc)

        return header_bytes
