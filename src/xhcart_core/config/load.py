import json
from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec, MetaSpec, BuildSpec, HashSpec
from src.xhcart_core.domain.errors import ConfigError

def load_pack_json(pack_json_path: str) -> PackSpec:
    """
    读取并校验pack.json文件，返回PackSpec对象
    
    Args:
        pack_json_path (str): pack.json文件路径
    
    Returns:
        PackSpec: 校验后的配置对象
    
    Raises:
        ConfigError: 配置错误时抛出
    """
    # 读取文件
    path = Path(pack_json_path)
    if not path.exists():
        raise ConfigError(f"File not found: {pack_json_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 解析meta字段
    meta_data = data.get('meta')
    if not meta_data:
        raise ConfigError("meta missing")
    
    # 校验必填字段
    required_meta_fields = ['title', 'version', 'cart_id', 'entry']
    for field in required_meta_fields:
        if field not in meta_data:
            raise ConfigError(f"meta.{field} missing")
    
    # 创建MetaSpec
    meta = MetaSpec(
        title=meta_data.get('title'),
        title_zh=meta_data.get('title_zh', ''),
        publisher=meta_data.get('publisher', ''),
        version=meta_data.get('version'),
        cart_id=meta_data.get('cart_id'),
        entry=meta_data.get('entry'),
        min_fw=meta_data.get('min_fw', '0.0.0')
    )
    
    # 解析build字段
    build_data = data.get('build', {})
    
    # 校验header_size
    header_size = build_data.get('header_size', 4096)
    if header_size != 4096:
        raise ConfigError("build.header_size must be 4096")
    
    # 校验align
    align = build_data.get('align', 4096)
    if align != 4096:
        raise ConfigError("build.align must be 4096")
    
    # 创建BuildSpec
    build = BuildSpec(
        output=build_data.get('output'),
        header_size=header_size,
        align=align
    )
    
    # 解析hash字段
    hash_data = data.get('hash', {})
    hash_spec = HashSpec(
        header_crc32=hash_data.get('header_crc32', True),
        image_crc32=hash_data.get('image_crc32', False)
    )
    
    # 解析icon字段
    icon_data = data.get('icon')
    if icon_data:
        # 校验icon必填字段
        if 'path' not in icon_data:
            raise ConfigError("icon.path missing")
        
        # 校验icon格式和尺寸
        # 允许icon.format为RGB888或ARGB8888
        if icon_data.get('format') not in ['RGB888', 'ARGB8888']:
            raise ConfigError("icon.format must be RGB888 or ARGB8888")

        
        if icon_data.get('width') != 200:
            raise ConfigError("icon.width must be 200")
        
        if icon_data.get('height') != 200:
            raise ConfigError("icon.height must be 200")
    
    # 创建PackSpec
    pack_spec = PackSpec(
        meta=meta,
        build=build,
        icon=icon_data,
        hash=hash_spec,
        pack_version=data.get('pack_version', 1),
        pack_json_path=pack_json_path
    )
    
    return pack_spec