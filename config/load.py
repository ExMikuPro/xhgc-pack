class ConfigError(Exception):
    """配置错误异常"""
    pass

def load_pack_spec(pack_json):
    """
    读取并校验JSON文件，返回PackSpec对象
    
    Args:
        pack_json (str): pack.json文件路径
    
    Returns:
        dict: 校验后的配置数据
    
    Raises:
        ConfigError: 配置错误时抛出
    """
    import json
    
    with open(pack_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 校验必填字段
    _validate_required_fields(data)
    
    # 校验build.header_size
    build = data.get('build', {})
    header_size = build.get('header_size', 4096)
    if header_size != 4096:
        raise ConfigError("build.header_size must be 4096")
    
    return data

def _validate_required_fields(data):
    """
    校验必填字段
    
    Args:
        data (dict): 配置数据
    
    Raises:
        ConfigError: 缺少必填字段时抛出
    """
    # 校验meta字段
    meta = data.get('meta')
    if not meta:
        raise ConfigError("meta missing")
    
    # 校验meta下的必填字段
    required_meta_fields = ['title', 'publisher', 'version', 'entry', 'cart_id']
    for field in required_meta_fields:
        if field not in meta:
            raise ConfigError(f"meta.{field} missing")
    
    # 校验cart_id格式
    cart_id = meta.get('cart_id')
    try:
        # 尝试解析cart_id为u64
        if cart_id.startswith('0x'):
            int(cart_id, 16)
        else:
            int(cart_id, 16)
    except ValueError:
        raise ConfigError(f"meta.cart_id invalid: {cart_id}")
    
    # 校验build字段
    build = data.get('build')
    if not build:
        raise ConfigError("build missing")
    
    # 校验build下的必填字段
    if 'output' not in build:
        raise ConfigError("build.output missing")