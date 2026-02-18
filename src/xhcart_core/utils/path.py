from pathlib import Path

def resolve_relative_path(relative_path: str, base_path: str) -> Path:
    """
    解析相对路径，相对于base_path所在目录
    
    Args:
        relative_path (str): 相对路径
        base_path (str): 基础路径（通常是pack.json的路径）
    
    Returns:
        Path: 解析后的绝对路径
    """
    base_dir = Path(base_path).parent
    return (base_dir / relative_path).resolve()