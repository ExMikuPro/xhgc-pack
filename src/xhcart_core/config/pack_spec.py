from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

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
    id: Optional[str] = None
    description: Optional[Any] = None
    category: str = "app"
    tags: List[str] = field(default_factory=list)
    author: Optional[Dict[str, Any]] = None

@dataclass
class BuildSpec:
    """
    构建配置
    """
    output: Optional[str] = None
    header_size: int = 4096
    align: int = 4096
    entry_compile: bool = True
    alignment_bytes: int = 4096
    deterministic: bool = True
    fail_on_conflict: bool = True

@dataclass
class HashSpec:
    """
    哈希配置
    """
    header_crc32: bool = True
    image_crc32: bool = False
    per_chunk_crc32: bool = False
    per_file_crc32: bool = False

@dataclass
class PackSpec:
    """
    打包配置
    """
    meta: MetaSpec
    build: BuildSpec
    icon: Optional[Dict[str, Any]] = None
    icons: Optional[Dict[str, Any]] = None
    hash: Optional[HashSpec] = None
    chunks: Optional[List[Dict[str, Any]]] = None
    pack_version: int = 1
    pack_json_path: Optional[str] = None  # 存储pack.json的路径，用于解析相对路径
