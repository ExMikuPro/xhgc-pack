import os
import tempfile
from pathlib import Path

def atomic_write(path: str, data: bytes) -> None:
    """
    原子写入文件
    
    Args:
        path (str): 输出文件路径
        data (bytes): 要写入的数据
    """
    # 获取目录
    path_obj = Path(path)
    dir_path = path_obj.parent
    
    if dir_path and not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    
    try:
        # 重命名临时文件到目标路径
        os.replace(tmp_path, path)
    except Exception:
        # 发生错误时删除临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise