from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.utils.align import align_to
from src.xhcart_core.utils.hashing import calculate_crc32
from src.xhcart_core.format.xhgc.addr_table import AddrTable
import subprocess
import tempfile
import sys
import os

def get_st_luac_path():
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，资源在 sys._MEIPASS 下
        return os.path.join(sys._MEIPASS, 'tool', 'bin', 'st-luac')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tool', 'bin', 'st-luac')

class BuildEntry:
    """
    构建ENTRY的类
    """

    # 固定常量
    HEADER_SIZE = 4096
    ALIGN_SIZE = 4096

    def __init__(self, pack_spec: PackSpec):
        """
        初始化BuildEntry

        Args:
            pack_spec (PackSpec): 配置数据
        """
        self.pack_spec = pack_spec

    def calculate_and_write_header_crc(self, header_bytes):
        """
        计算并写入Header CRC32

        Args:
            header_bytes (bytearray): 原始header数据（长度为4096）

        Returns:
            bytearray: 包含CRC32的header数据
        """
        import struct
        from src.xhcart_core.format.xhgc.header import HeaderV2

        # 确保输入数据长度为4096
        if len(header_bytes) != 4096:
            raise ValueError("Header length must be 4096 bytes")

        # 创建一个副本，将CRC区域置为0
        header_copy = header_bytes.copy()
        header_copy[HeaderV2.CRC_OFFSET:HeaderV2.CRC_OFFSET+4] = b'\x00\x00\x00\x00'

        # 计算CRC32
        crc = calculate_crc32(header_copy)

        # 以little-endian方式写入CRC32到0x0FFC..0x0FFF
        struct.pack_into('<I', header_bytes, HeaderV2.CRC_OFFSET, crc)

        return header_bytes

    def build(self, out_path: str):
        """
        构建包含ENTRY的cart.bin

        Args:
            out_path (str): 输出文件路径
        """
        # 读取现有的cart.bin文件
        with open(out_path, 'rb') as f:
            cart_data = bytearray(f.read())

        # 提取header数据
        header_data = bytearray(cart_data[:self.HEADER_SIZE])

        # 解析entry路径
        lua_path = self._resolve_entry_path()

        # 编译Lua文件
        try:
            luac_data = self._compile_lua(lua_path)
        except Exception as e:
            # 输出错误信息
            import json, sys
            error_result = {
                "step": "entry",
                "status": "error",
                "message": str(e)
            }
            print(json.dumps(error_result))
            sys.stdout.flush()
            raise

        # 计算ENTRY偏移量（4KB对齐）
        entry_offset = align_to(len(cart_data), self.ALIGN_SIZE)

        # 计算ENTRY大小和CRC32
        entry_size = len(luac_data)
        entry_crc32 = calculate_crc32(luac_data) if entry_size > 0 else 0

        # 写入slot3 (ENTRY)
        AddrTable.write_slot(header_data, AddrTable.SLOT_ENTRY, entry_offset, entry_size, entry_crc32)

        # 计算总大小并对齐
        total_size = entry_offset + entry_size
        aligned_size = align_to(total_size, self.ALIGN_SIZE)
        padding_size = aligned_size - total_size
        padding = b'\x00' * padding_size

        # 从配置中读取CRC32设置
        header_crc32 = True  # 默认计算header的CRC32
        image_crc32 = False  # 默认不计算整个镜像的CRC32

        if self.pack_spec.hash:
            header_crc32 = self.pack_spec.hash.header_crc32
            image_crc32 = self.pack_spec.hash.image_crc32

        # 计算并写入Header CRC32
        if header_crc32:
            header_data_with_crc = self.calculate_and_write_header_crc(header_data)
        else:
            header_data_with_crc = header_data

        # 组装完整数据（包含更新后的header）
        cart_data = header_data_with_crc + cart_data[self.HEADER_SIZE:] + luac_data + padding

        # 如果需要计算整个镜像的CRC32
        if image_crc32:
            # 计算整个镜像的CRC32
            image_crc = calculate_crc32(cart_data)

            # 创建新的header副本，写入镜像CRC32到slot6
            final_header_data = header_data_with_crc.copy()
            AddrTable.write_slot(final_header_data, 6, 0, len(cart_data), image_crc)

            # 再次计算Header CRC32（因为修改了slot6）
            if header_crc32:
                final_header_data = self.calculate_and_write_header_crc(final_header_data)

            # 最终组装数据
            cart_data = final_header_data + cart_data[self.HEADER_SIZE:] + luac_data + padding

        # 原子写入文件
        atomic_write(out_path, cart_data)

        # 输出JSON格式结果
        import json, sys
        result = {
            "step": "entry",
            "status": "ok",
            "file_size": len(cart_data),
            "entry_offset": entry_offset,
            "entry_size": len(luac_data),
            "entry_crc32": f"0x{entry_crc32:08X}",
            "padding_size": len(padding)
        }
        print(json.dumps(result))
        sys.stdout.flush()

    def _resolve_entry_path(self) -> Path:
        """
        解析entry路径

        Returns:
            Path: entry文件路径
        """
        # 从chunks数组中查找type为"LUA"的条目
        lua_chunks = [chunk for chunk in self.pack_spec.chunks if chunk.get('type', '').strip() == 'LUA']

        if not lua_chunks:
            raise ValueError("No LUA chunk found in pack.json")

        # 获取第一个LUA条目的glob字段
        lua_chunk = lua_chunks[0]
        glob_pattern = lua_chunk.get('glob')

        if not glob_pattern:
            raise ValueError("glob field missing in LUA chunk")

        # 查找匹配的文件
        pack_json_dir = Path(self.pack_spec.pack_json_path).parent
        files = list(pack_json_dir.glob(glob_pattern))

        if not files:
            raise ValueError(f"No files found matching glob: {glob_pattern}")

        # 获取第一个匹配的文件
        lua_path = files[0]

        # 解析为绝对路径
        return lua_path

    def _compile_lua(self, lua_path: Path) -> bytes:
        """
        编译Lua文件

        Args:
            lua_path (Path): Lua文件路径

        Returns:
            bytes: 编译后的字节码
        """
        if not lua_path.exists():
            raise ValueError(f"Lua file not found: {lua_path}")

        # 确保文件是.lua结尾
        if lua_path.suffix.lower() != '.lua':
            raise ValueError(f"Entry file must be a .lua file: {lua_path}")

        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.luac', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # 构建编译命令
            luac_path = Path(get_st_luac_path())
            if not luac_path.exists():
                raise ValueError(f"st-luac not found: {luac_path}")

            cmd = [str(luac_path), "-o", tmp_path, str(lua_path)]

            # 执行编译命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            # 检查编译是否成功
            if result.returncode != 0:
                raise ValueError(f"Failed to compile Lua file: {result.stderr}")

            # 读取编译后的字节码
            with open(tmp_path, 'rb') as f:
                luac_data = f.read()

            return luac_data
        finally:
            # 清理临时文件
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
