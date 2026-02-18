import os
import tempfile
from config.load import load_pack_spec
from format.header import Header

def build_header(pack_json, out_path, verbose=False):
    """
    组装Header并写文件
    
    Args:
        pack_json (str): pack.json文件路径
        out_path (str): 输出文件路径
        verbose (bool): 是否打印详细信息
    """
    # 读取并校验配置
    pack_spec = load_pack_spec(pack_json)
    
    # 创建Header对象
    header = Header(pack_spec)
    
    # 序列化Header
    header_data = header.pack(verbose=verbose)
    
    # 原子写入文件
    _atomic_write(out_path, header_data)
    
    print(f"成功生成header文件: {out_path}")
    print(f"文件大小: {len(header_data)} 字节")

def _atomic_write(path, data):
    """
    原子写入文件
    
    Args:
        path (str): 输出文件路径
        data (bytes): 要写入的数据
    """
    # 获取目录
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    
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