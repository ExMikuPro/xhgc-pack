from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class MetaSpec:
    """
    元数据配置
    """
    title: str
    version: str
    cart_id: str
    entry: str
    title_zh: Optional[str] = ""
    publisher: Optional[str] = ""
    min_fw: Optional[str] = "0.0.0"

@dataclass
class BuildSpec:
    """
    构建配置
    """
    output: Optional[str] = None
    header_size: int = 4096
    align: int = 4096

@dataclass
class HashSpec:
    """
    哈希配置
    """
    header_crc32: bool = True
    image_crc32: bool = False

@dataclass
class PackSpec:
    """
    打包配置
    """
    meta: MetaSpec
    build: BuildSpec
    icon: Optional[Dict[str, Any]] = None
    hash: Optional[HashSpec] = None
    pack_version: int = 1
    pack_json_path: Optional[str] = None  # 存储pack.json的路径，用于解析相对路径