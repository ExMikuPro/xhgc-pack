from src.xhcart_core.config.load import load_pack_json
from src.xhcart_core.format.xhgc.header import HeaderV2
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.pipeline.build_icon import BuildIcon
from src.xhcart_core.pipeline.build_manf import BuildManf
from src.xhcart_core.pipeline.build_entry import BuildEntry
from src.xhcart_core.pipeline.build_data import BuildData

# 尝试导入Pillow，如果不可用则设置标志
try:
    import PIL
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

def pack_header(pack_json: str, out_path: str) -> None:
    """
    生成header.bin文件

    Args:
        pack_json (str): pack.json文件路径
        out_path (str): 输出文件路径
    """
    # 加载配置
    pack_spec = load_pack_json(pack_json)

    # 创建HeaderV2对象
    header = HeaderV2(pack_spec)

    # 序列化Header
    header_data = header.pack()

    # 原子写入文件
    atomic_write(out_path, header_data)

def pack_header_icon(pack_json: str, out_path: str) -> None:
    """
    生成包含header和icon的cart.bin文件

    Args:
        pack_json (str): pack.json文件路径
        out_path (str): 输出文件路径
    """
    # 检查Pillow是否可用
    if not PILLOW_AVAILABLE:
        raise ImportError("Pillow is required for image processing. Please install it with 'pip install Pillow'")

    # 加载配置
    pack_spec = load_pack_json(pack_json)

    # 检查是否有icon配置
    if not pack_spec.icon:
        raise ValueError("icon configuration missing in pack.json")

    # 创建BuildIcon对象并构建
    builder = BuildIcon(pack_spec)
    builder.build(out_path)

    # 创建BuildManf对象并构建
    manf_builder = BuildManf(pack_spec)
    manf_builder.build(out_path)

    # 创建BuildEntry对象并构建
    entry_builder = BuildEntry(pack_spec)
    entry_builder.build(out_path)

    # 创建BuildData对象并构建
    data_builder = BuildData(pack_spec)
    data_builder.build(out_path)

def inspect_header(header_path: str) -> dict:
    """
    解析header.bin文件并返回字段信息

    Args:
        header_path (str): header.bin文件路径

    Returns:
        dict: 字段信息
    """
    with open(header_path, 'rb') as f:
        header_data = f.read()

    # 创建HeaderV2对象（空配置）
    from .config.pack_spec import PackSpec, MetaSpec, BuildSpec
    dummy_spec = PackSpec(
        meta=MetaSpec(
            title='',
            version='',
            cart_id='0x0',
            entry=''
        ),
        build=BuildSpec()
    )
    header = HeaderV2(dummy_spec)

    # 解析header
    return header.inspect(header_data)

def verify_header(header_path: str) -> bool:
    """
    验证header.bin文件的CRC32

    Args:
        header_path (str): header.bin文件路径

    Returns:
        bool: 验证结果
    """
    with open(header_path, 'rb') as f:
        header_data = f.read()

    # 确保header大小正确
    if len(header_data) != 4096:
        return False

    # 提取存储的CRC32
    import struct
    stored_crc = struct.unpack_from('<I', header_data, 4092)[0]

    # 创建一个副本，将CRC区域置为0
    header_copy = bytearray(header_data)
    header_copy[4092:4096] = b'\x00\x00\x00\x00'

    # 计算CRC32
    from src.xhcart_core.utils.hashing import calculate_crc32
    calculated_crc = calculate_crc32(header_copy)

    # 比较CRC32
    return stored_crc == calculated_crc
