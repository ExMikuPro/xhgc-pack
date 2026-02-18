import struct
from typing import Dict, Optional

class Header:
    """
    Header对象，负责序列化
    """
    
    def __init__(self, pack_spec: Dict):
        """
        初始化Header对象
        
        Args:
            pack_spec (Dict): 配置数据
        """
        self.pack_spec = pack_spec
        self.header_size = 4096
    
    def pack(self, verbose: bool = False) -> bytes:
        """
        序列化Header对象
        
        Args:
            verbose (bool): 是否打印详细信息
        
        Returns:
            bytes: 序列化后的二进制数据
        """
        # 创建4KB的header
        header = bytearray(self.header_size)
        
        # 字段偏移表
        fields = []
        
        # 写入magic
        magic = b'XHGC_PACK'
        struct.pack_into('<8s', header, 0, magic)
        fields.append(('magic', 0, 8, magic))
        
        # 写入version
        pack_version = self.pack_spec.get('pack_version', 1)
        struct.pack_into('<I', header, 8, pack_version)
        fields.append(('pack_version', 8, 4, pack_version))
        
        # 写入meta信息
        meta = self.pack_spec.get('meta', {})
        
        # 写入title
        title = meta.get('title', '').encode('utf-8')
        if len(title) > 64:
            raise ValueError("meta.title exceeds 64 bytes")
        title_padded = title.ljust(64, b'\x00')
        struct.pack_into('<64s', header, 12, title_padded)
        fields.append(('meta.title', 12, 64, title.decode('utf-8')))
        
        # 写入title_zh
        title_zh = meta.get('title_zh', '').encode('utf-8')
        if len(title_zh) > 64:
            raise ValueError("meta.title_zh exceeds 64 bytes")
        title_zh_padded = title_zh.ljust(64, b'\x00')
        struct.pack_into('<64s', header, 76, title_zh_padded)
        fields.append(('meta.title_zh', 76, 64, title_zh.decode('utf-8')))
        
        # 写入publisher
        publisher = meta.get('publisher', '').encode('utf-8')
        if len(publisher) > 64:
            raise ValueError("meta.publisher exceeds 64 bytes")
        publisher_padded = publisher.ljust(64, b'\x00')
        struct.pack_into('<64s', header, 140, publisher_padded)
        fields.append(('meta.publisher', 140, 64, publisher.decode('utf-8')))
        
        # 写入version
        version = meta.get('version', '').encode('utf-8')
        if len(version) > 32:
            raise ValueError("meta.version exceeds 32 bytes")
        version_padded = version.ljust(32, b'\x00')
        struct.pack_into('<32s', header, 204, version_padded)
        fields.append(('meta.version', 204, 32, version.decode('utf-8')))
        
        # 写入cart_id
        cart_id = meta.get('cart_id')
        if cart_id.startswith('0x'):
            cart_id_int = int(cart_id, 16)
        else:
            cart_id_int = int(cart_id, 16)
        struct.pack_into('<Q', header, 236, cart_id_int)
        fields.append(('meta.cart_id', 236, 8, hex(cart_id_int)))
        
        # 写入entry
        entry = meta.get('entry', '').encode('utf-8')
        if len(entry) > 128:
            raise ValueError("meta.entry exceeds 128 bytes")
        entry_padded = entry.ljust(128, b'\x00')
        struct.pack_into('<128s', header, 244, entry_padded)
        fields.append(('meta.entry', 244, 128, entry.decode('utf-8')))
        
        # 写入min_fw
        min_fw = meta.get('min_fw', '0.0.0').encode('utf-8')
        if len(min_fw) > 16:
            raise ValueError("meta.min_fw exceeds 16 bytes")
        min_fw_padded = min_fw.ljust(16, b'\x00')
        struct.pack_into('<16s', header, 372, min_fw_padded)
        fields.append(('meta.min_fw', 372, 16, min_fw.decode('utf-8')))
        
        # 写入预留字段（填0）
        reserved_fields = [
            ('icon_offset', 388, 4),
            ('icon_size', 392, 4),
            ('manifest_offset', 396, 4),
            ('manifest_size', 400, 4),
            ('entry_offset', 404, 4),
            ('entry_size', 408, 4),
            ('index_offset', 412, 4),
            ('index_size', 416, 4),
            ('image_size', 420, 4),
        ]
        
        for field_name, offset, size in reserved_fields:
            if size == 4:
                struct.pack_into('<I', header, offset, 0)
            fields.append((field_name, offset, size, 0))
        
        # 计算CRC32（先将crc字段置为0）
        crc_offset = 424
        struct.pack_into('<I', header, crc_offset, 0)
        
        # 计算CRC32
        from utils.hashing import calculate_crc32
        crc_value = calculate_crc32(header)
        
        # 写入CRC32
        struct.pack_into('<I', header, crc_offset, crc_value)
        fields.append(('header_crc32', crc_offset, 4, crc_value))
        
        # 打印详细信息
        if verbose:
            print("Header fields:")
            print("-" * 80)
            print(f"{'Field':<25} {'Offset':<10} {'Size':<10} {'Value':<30}")
            print("-" * 80)
            for field_name, offset, size, value in fields:
                print(f"{field_name:<25} 0x{offset:08X} {size:<10} {str(value):<30}")
            print("-" * 80)
        
        return bytes(header)