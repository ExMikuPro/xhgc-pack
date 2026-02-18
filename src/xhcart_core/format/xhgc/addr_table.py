import struct

class AddrTable:
    """
    地址表操作类
    """
    
    # 固定常量
    ADDR_TABLE_BASE = 0x0F00
    SLOT_SIZE = 0x10
    SLOT_COUNT = 15
    
    # 槽位定义
    SLOT_ICON = 0
    SLOT_THMB = 1
    SLOT_MANF = 2
    SLOT_ENTRY = 3
    SLOT_INDEX = 4
    SLOT_DATA = 5
    
    @classmethod
    def slot_offset(cls, i: int) -> int:
        """
        计算槽位偏移量
        
        Args:
            i (int): 槽位索引
        
        Returns:
            int: 槽位偏移量
        """
        return cls.ADDR_TABLE_BASE + i * cls.SLOT_SIZE
    
    @classmethod
    def write_slot(cls, header: bytearray, slot_index: int, offset: int, size: int, crc32: int = 0):
        """
        写入槽位数据
        
        Args:
            header (bytearray): header数据
            slot_index (int): 槽位索引
            offset (int): 偏移量
            size (int): 大小
            crc32 (int): CRC32校验值，默认0
        """
        if slot_index < 0 or slot_index >= cls.SLOT_COUNT:
            raise ValueError(f"Invalid slot index: {slot_index}")
        
        slot_off = cls.slot_offset(slot_index)
        
        # 写入offset (u64, little-endian)
        struct.pack_into('<Q', header, slot_off, offset)
        
        # 写入size (u32, little-endian)
        struct.pack_into('<I', header, slot_off + 8, size)
        
        # 写入crc32 (u32, little-endian)
        struct.pack_into('<I', header, slot_off + 12, crc32)
    
    @classmethod
    def clear_all_slots(cls, header: bytearray):
        """
        清空所有槽位
        
        Args:
            header (bytearray): header数据
        """
        for i in range(cls.SLOT_COUNT):
            cls.write_slot(header, i, 0, 0, 0)