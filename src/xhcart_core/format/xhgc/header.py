import struct
from typing import Dict, Optional
from src.xhcart_core.config.pack_spec import PackSpec

class HeaderV2:
    """
    Header V2 实现
    """
    
    # 固定常量
    HEADER_SIZE = 4096
    MAGIC = b"XHGC_PAC"
    HEADER_VERSION = 2
    
    # 字段偏移量
    OFFSET_MAGIC = 0
    OFFSET_HEADER_VERSION = 8
    OFFSET_HEADER_SIZE = 12
    OFFSET_FLAGS = 16
    OFFSET_CART_ID = 20
    OFFSET_TITLE = 28
    OFFSET_TITLE_ZH = 92
    OFFSET_PUBLISHER = 156
    OFFSET_VERSION = 220
    OFFSET_ENTRY = 252
    OFFSET_MIN_FW = 380
    
    # 地址表区域
    HEADER_SIZE = 4096
    ADDR_TABLE_BASE = 0x0F00  # 3840
    SLOT_SIZE = 0x10  # 16 bytes per slot
    SLOT_COUNT = 15  # 252 bytes / 16 bytes per slot
    
    # CRC32 区域
    CRC_OFFSET = 0x0FFC  # 4092
    
    # 槽位定义
    SLOT_ICON = 0
    SLOT_THMB = 1
    SLOT_MANF = 2
    SLOT_ENTRY = 3
    SLOT_INDEX = 4
    SLOT_DATA = 5
    
    # 兼容性别名
    OFFSET_ADDR_TABLE = ADDR_TABLE_BASE
    OFFSET_CRC32 = CRC_OFFSET
    
    # 字符串长度
    STRING_LENGTH_TITLE = 64
    STRING_LENGTH_TITLE_ZH = 64
    STRING_LENGTH_PUBLISHER = 64
    STRING_LENGTH_VERSION = 32
    STRING_LENGTH_ENTRY = 128
    STRING_LENGTH_MIN_FW = 16
    
    def __init__(self, pack_spec: PackSpec):
        """
        初始化HeaderV2对象
        
        Args:
            pack_spec (PackSpec): 配置数据
        """
        self.pack_spec = pack_spec
    
    def slot_offset(self, i: int) -> int:
        """
        计算槽位偏移量
        
        Args:
            i (int): 槽位索引
        
        Returns:
            int: 槽位偏移量
        """
        return self.ADDR_TABLE_BASE + i * self.SLOT_SIZE
    
    def pack(self) -> bytes:
        """
        序列化Header
        
        Returns:
            bytes: 序列化后的二进制数据
        """
        # 创建4KB的header
        header = bytearray(self.HEADER_SIZE)
        
        # 写入magic
        struct.pack_into('<8s', header, self.OFFSET_MAGIC, self.MAGIC)
        
        # 写入header_version
        struct.pack_into('<I', header, self.OFFSET_HEADER_VERSION, self.HEADER_VERSION)
        
        # 写入header_size
        struct.pack_into('<I', header, self.OFFSET_HEADER_SIZE, self.HEADER_SIZE)
        
        # 写入flags
        struct.pack_into('<I', header, self.OFFSET_FLAGS, 0)
        
        # 写入cart_id
        cart_id_str = self.pack_spec.meta.cart_id
        try:
            if cart_id_str.startswith('0x'):
                cart_id = int(cart_id_str, 16)
            else:
                cart_id = int(cart_id_str, 16)
        except ValueError:
            raise ValueError(f"Invalid cart_id: {cart_id_str}")
        struct.pack_into('<Q', header, self.OFFSET_CART_ID, cart_id)
        
        # 写入title
        title = self.pack_spec.meta.title.encode('utf-8')
        if len(title) > self.STRING_LENGTH_TITLE - 1:
            raise ValueError(f"meta.title exceeds {self.STRING_LENGTH_TITLE - 1} bytes")
        title_padded = title.ljust(self.STRING_LENGTH_TITLE, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_TITLE}s', header, self.OFFSET_TITLE, title_padded)
        
        # 写入title_zh
        title_zh = self.pack_spec.meta.title_zh.encode('utf-8')
        if len(title_zh) > self.STRING_LENGTH_TITLE_ZH - 1:
            raise ValueError(f"meta.title_zh exceeds {self.STRING_LENGTH_TITLE_ZH - 1} bytes")
        title_zh_padded = title_zh.ljust(self.STRING_LENGTH_TITLE_ZH, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_TITLE_ZH}s', header, self.OFFSET_TITLE_ZH, title_zh_padded)
        
        # 写入publisher
        publisher = self.pack_spec.meta.publisher.encode('utf-8')
        if len(publisher) > self.STRING_LENGTH_PUBLISHER - 1:
            raise ValueError(f"meta.publisher exceeds {self.STRING_LENGTH_PUBLISHER - 1} bytes")
        publisher_padded = publisher.ljust(self.STRING_LENGTH_PUBLISHER, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_PUBLISHER}s', header, self.OFFSET_PUBLISHER, publisher_padded)
        
        # 写入version
        version = self.pack_spec.meta.version.encode('utf-8')
        if len(version) > self.STRING_LENGTH_VERSION - 1:
            raise ValueError(f"meta.version exceeds {self.STRING_LENGTH_VERSION - 1} bytes")
        version_padded = version.ljust(self.STRING_LENGTH_VERSION, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_VERSION}s', header, self.OFFSET_VERSION, version_padded)
        
        # 写入entry
        entry = self.pack_spec.meta.entry.encode('utf-8')
        if len(entry) > self.STRING_LENGTH_ENTRY - 1:
            raise ValueError(f"meta.entry exceeds {self.STRING_LENGTH_ENTRY - 1} bytes")
        entry_padded = entry.ljust(self.STRING_LENGTH_ENTRY, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_ENTRY}s', header, self.OFFSET_ENTRY, entry_padded)
        
        # 写入min_fw
        min_fw = self.pack_spec.meta.min_fw.encode('utf-8')
        if len(min_fw) > self.STRING_LENGTH_MIN_FW - 1:
            raise ValueError(f"meta.min_fw exceeds {self.STRING_LENGTH_MIN_FW - 1} bytes")
        min_fw_padded = min_fw.ljust(self.STRING_LENGTH_MIN_FW, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_MIN_FW}s', header, self.OFFSET_MIN_FW, min_fw_padded)
        
        # 清空地址表区域
        for i in range(self.SLOT_COUNT):
            slot_off = self.slot_offset(i)
            # struct AddrSlot { u64 offset; u32 size; u32 crc32; }
            struct.pack_into('<Q', header, slot_off, 0)         # offset
            struct.pack_into('<I', header, slot_off + 8, 0)     # size
            struct.pack_into('<I', header, slot_off + 12, 0)    # crc32
        
        # 清空CRC32区域
        struct.pack_into('<I', header, self.CRC_OFFSET, 0)
        
        # 计算CRC32
        from src.xhcart_core.utils.hashing import calculate_crc32
        crc_value = calculate_crc32(header)
        
        # 写入CRC32
        struct.pack_into('<I', header, self.CRC_OFFSET, crc_value)
        
        return bytes(header)
    
    def pack_without_crc(self) -> bytes:
        """
        序列化Header但不计算CRC32
        
        Returns:
            bytes: 序列化后的二进制数据（CRC32字段为0）
        """
        # 创建4KB的header
        header = bytearray(self.HEADER_SIZE)
        
        # 写入magic
        struct.pack_into('<8s', header, self.OFFSET_MAGIC, self.MAGIC)
        
        # 写入header_version
        struct.pack_into('<I', header, self.OFFSET_HEADER_VERSION, self.HEADER_VERSION)
        
        # 写入header_size
        struct.pack_into('<I', header, self.OFFSET_HEADER_SIZE, self.HEADER_SIZE)
        
        # 写入flags
        struct.pack_into('<I', header, self.OFFSET_FLAGS, 0)
        
        # 写入cart_id
        cart_id_str = self.pack_spec.meta.cart_id
        try:
            if cart_id_str.startswith('0x'):
                cart_id = int(cart_id_str, 16)
            else:
                cart_id = int(cart_id_str, 16)
        except ValueError:
            raise ValueError(f"Invalid cart_id: {cart_id_str}")
        struct.pack_into('<Q', header, self.OFFSET_CART_ID, cart_id)
        
        # 写入title
        title = self.pack_spec.meta.title.encode('utf-8')
        if len(title) > self.STRING_LENGTH_TITLE - 1:
            raise ValueError(f"meta.title exceeds {self.STRING_LENGTH_TITLE - 1} bytes")
        title_padded = title.ljust(self.STRING_LENGTH_TITLE, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_TITLE}s', header, self.OFFSET_TITLE, title_padded)
        
        # 写入title_zh
        title_zh = self.pack_spec.meta.title_zh.encode('utf-8')
        if len(title_zh) > self.STRING_LENGTH_TITLE_ZH - 1:
            raise ValueError(f"meta.title_zh exceeds {self.STRING_LENGTH_TITLE_ZH - 1} bytes")
        title_zh_padded = title_zh.ljust(self.STRING_LENGTH_TITLE_ZH, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_TITLE_ZH}s', header, self.OFFSET_TITLE_ZH, title_zh_padded)
        
        # 写入publisher
        publisher = self.pack_spec.meta.publisher.encode('utf-8')
        if len(publisher) > self.STRING_LENGTH_PUBLISHER - 1:
            raise ValueError(f"meta.publisher exceeds {self.STRING_LENGTH_PUBLISHER - 1} bytes")
        publisher_padded = publisher.ljust(self.STRING_LENGTH_PUBLISHER, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_PUBLISHER}s', header, self.OFFSET_PUBLISHER, publisher_padded)
        
        # 写入version
        version = self.pack_spec.meta.version.encode('utf-8')
        if len(version) > self.STRING_LENGTH_VERSION - 1:
            raise ValueError(f"meta.version exceeds {self.STRING_LENGTH_VERSION - 1} bytes")
        version_padded = version.ljust(self.STRING_LENGTH_VERSION, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_VERSION}s', header, self.OFFSET_VERSION, version_padded)
        
        # 写入entry
        entry = self.pack_spec.meta.entry.encode('utf-8')
        if len(entry) > self.STRING_LENGTH_ENTRY - 1:
            raise ValueError(f"meta.entry exceeds {self.STRING_LENGTH_ENTRY - 1} bytes")
        entry_padded = entry.ljust(self.STRING_LENGTH_ENTRY, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_ENTRY}s', header, self.OFFSET_ENTRY, entry_padded)
        
        # 写入min_fw
        min_fw = self.pack_spec.meta.min_fw.encode('utf-8')
        if len(min_fw) > self.STRING_LENGTH_MIN_FW - 1:
            raise ValueError(f"meta.min_fw exceeds {self.STRING_LENGTH_MIN_FW - 1} bytes")
        min_fw_padded = min_fw.ljust(self.STRING_LENGTH_MIN_FW, b'\x00')
        struct.pack_into(f'<{self.STRING_LENGTH_MIN_FW}s', header, self.OFFSET_MIN_FW, min_fw_padded)
        
        # 清空地址表区域
        for i in range(self.SLOT_COUNT):
            slot_off = self.slot_offset(i)
            # struct AddrSlot { u64 offset; u32 size; u32 crc32; }
            struct.pack_into('<Q', header, slot_off, 0)         # offset
            struct.pack_into('<I', header, slot_off + 8, 0)     # size
            struct.pack_into('<I', header, slot_off + 12, 0)    # crc32
        
        # 清空CRC32区域
        struct.pack_into('<I', header, self.CRC_OFFSET, 0)
        
        return bytes(header)
    
    def inspect(self, header_data: bytes) -> Dict:
        """
        解析header数据并返回字段信息
        
        Args:
            header_data (bytes): header二进制数据
        
        Returns:
            Dict: 字段信息
        """
        if len(header_data) != self.HEADER_SIZE:
            raise ValueError(f"Invalid header size: {len(header_data)}, expected {self.HEADER_SIZE}")
        
        # 解析基础字段
        magic = struct.unpack_from('<8s', header_data, self.OFFSET_MAGIC)[0].rstrip(b'\x00')
        header_version = struct.unpack_from('<I', header_data, self.OFFSET_HEADER_VERSION)[0]
        header_size = struct.unpack_from('<I', header_data, self.OFFSET_HEADER_SIZE)[0]
        flags = struct.unpack_from('<I', header_data, self.OFFSET_FLAGS)[0]
        cart_id = struct.unpack_from('<Q', header_data, self.OFFSET_CART_ID)[0]
        
        # 解析字符串字段
        title = struct.unpack_from(f'<{self.STRING_LENGTH_TITLE}s', header_data, self.OFFSET_TITLE)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        title_zh = struct.unpack_from(f'<{self.STRING_LENGTH_TITLE_ZH}s', header_data, self.OFFSET_TITLE_ZH)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        publisher = struct.unpack_from(f'<{self.STRING_LENGTH_PUBLISHER}s', header_data, self.OFFSET_PUBLISHER)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        version = struct.unpack_from(f'<{self.STRING_LENGTH_VERSION}s', header_data, self.OFFSET_VERSION)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        entry = struct.unpack_from(f'<{self.STRING_LENGTH_ENTRY}s', header_data, self.OFFSET_ENTRY)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        min_fw = struct.unpack_from(f'<{self.STRING_LENGTH_MIN_FW}s', header_data, self.OFFSET_MIN_FW)[0].rstrip(b'\x00').decode('utf-8', errors='replace')
        
        # 解析CRC32
        crc32 = struct.unpack_from('<I', header_data, self.CRC_OFFSET)[0]
        
        # 解析地址表
        addr_table = []
        slot_names = ['ICON', 'THMB', 'MANF', 'ENTRY', 'INDEX', 'DATA']
        
        for i in range(self.SLOT_COUNT):
            slot_off = self.slot_offset(i)
            offset = struct.unpack_from('<Q', header_data, slot_off)[0]
            size = struct.unpack_from('<I', header_data, slot_off + 8)[0]
            crc = struct.unpack_from('<I', header_data, slot_off + 12)[0]
            
            slot_name = slot_names[i] if i < len(slot_names) else f"SLOT{i}"
            addr_table.append({
                'name': slot_name,
                'offset': slot_off,
                'data_offset': offset,
                'size': size,
                'crc32': crc
            })
        
        return {
            'magic': magic,
            'header_version': header_version,
            'header_size': header_size,
            'flags': flags,
            'cart_id': hex(cart_id),
            'title': title,
            'title_zh': title_zh,
            'publisher': publisher,
            'version': version,
            'entry': entry,
            'min_fw': min_fw,
            'crc32': crc32,
            'addr_table': addr_table,
            'addr_table_range': f"0x{self.ADDR_TABLE_BASE:04X}..0x{self.CRC_OFFSET-1:04X}",
            'crc32_range': f"0x{self.CRC_OFFSET:04X}..0x{self.HEADER_SIZE-1:04X}"
        }