from pipeline.build_header import build_header

def pack_header(pack_json, out_path, verbose=False):
    """
    外部调用入口，生成header文件
    
    Args:
        pack_json (str): pack.json文件路径
        out_path (str): 输出文件路径
        verbose (bool): 是否打印详细信息
    """
    build_header(pack_json, out_path, verbose=verbose)