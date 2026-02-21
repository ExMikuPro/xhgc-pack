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
    
    # 校验顶层必填字段
    if data.get('format') != 'XHGC_PACK':
        raise ConfigError('format must be XHGC_PACK')

    if data.get('pack_version') != 1:
        raise ConfigError('pack_version must be 1')

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
        min_fw=meta_data.get('min_fw', '0.0.0'),
        id=meta_data.get('id'),
        description=meta_data.get('description'),
        category=meta_data.get('category', 'app'),
        tags=meta_data.get('tags', []),
        author=meta_data.get('author')
    )

    # 解析build字段
    build_data = data.get('build', {})

    # 校验header_size
    header_size = build_data.get('header_size', 4096)
    if header_size != 4096:
        raise ConfigError("build.header_size must be 4096")

    # 解析alignment_bytes
    alignment_bytes = build_data.get('alignment_bytes', 4096)
    if alignment_bytes != 4096:
        raise ConfigError("build.alignment_bytes must be 4096")

    # 创建BuildSpec
    build = BuildSpec(
        output=build_data.get('output'),
        header_size=header_size,
        align=alignment_bytes,
        alignment_bytes=alignment_bytes,
        deterministic=build_data.get('deterministic', True),
        fail_on_conflict=build_data.get('fail_on_conflict', True)
    )

    # 解析hash字段
    hash_data = data.get('hash', {})
    hash_spec = HashSpec(
        header_crc32=hash_data.get('header_crc32', True),
        image_crc32=hash_data.get('image_crc32', False),
        per_chunk_crc32=hash_data.get('per_chunk_crc32', False),
        per_file_crc32=hash_data.get('per_file_crc32', False)
    )

    # 解析icon/icons字段
    icon_data = data.get('icon')
    icons_data = data.get('icons')

    # 实现回退策略：若缺/icons，将/icon视为main_200
    if not icons_data and icon_data:
        icons_data = {
            'main_200': icon_data
        }

    # 解析chunks字段
    chunks_data = data.get('chunks', [])

    # 创建PackSpec
    pack_spec = PackSpec(
        meta=meta,
        build=build,
        icon=icon_data,
        icons=icons_data,
        hash=hash_spec,
        chunks=chunks_data,
        pack_version=data.get('pack_version', 1),
        pack_json_path=pack_json_path
    )

    return pack_spec
