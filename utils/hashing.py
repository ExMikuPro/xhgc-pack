import zlib

def calculate_crc32(data):
    """
    计算CRC32校验值（IEEE标准）
    
    Args:
        data (bytes or bytearray): 要计算校验值的数据
    
    Returns:
        int: CRC32校验值（little-endian格式）
    """
    return zlib.crc32(data) & 0xFFFFFFFF