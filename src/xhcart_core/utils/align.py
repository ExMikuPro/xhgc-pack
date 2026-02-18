def align_to(value: int, align: int) -> int:
    """
    将值对齐到指定大小
    
    Args:
        value (int): 原始值
        align (int): 对齐大小
    
    Returns:
        int: 对齐后的值
    """
    if align <= 0:
        return value
    return (value + align - 1) & ~(align - 1)