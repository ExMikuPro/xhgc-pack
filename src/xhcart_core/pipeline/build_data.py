from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.utils.align import align_to
from src.xhcart_core.utils.hashing import calculate_crc32
from src.xhcart_core.format.xhgc.addr_table import AddrTable

class BuildData:
    """
    构建DATA区的类
    """

    # 固定常量
    HEADER_SIZE = 4096
    ALIGN_SIZE = 4096

    def __init__(self, pack_spec: PackSpec):
        """
        初始化BuildData

        Args:
            pack_spec (PackSpec): 配置数据
        """
        self.pack_spec = pack_spec

    def build(self, out_path: str):
        """
        构建包含DATA区的cart.bin

        Args:
            out_path (str): 输出文件路径
        """
        # 读取现有的cart.bin文件
        with open(out_path, 'rb') as f:
            cart_data = bytearray(f.read())

        # 提取header数据
        header_data = bytearray(cart_data[:self.HEADER_SIZE])

        # 计算DATA偏移量（4KB对齐）
        data_offset = align_to(len(cart_data), self.ALIGN_SIZE)

        # 构建DATA区数据
        data_content = bytearray()
        index_entries = []

        # 处理LUA和RES chunks
        for chunk in self.pack_spec.chunks:
            chunk_type = chunk.get('type', '').strip()

            if chunk_type not in ['LUA', 'RES']:
                continue

            # 获取chunk配置
            glob_pattern = chunk.get('glob', '')
            if not glob_pattern:
                continue

            strip_prefix = chunk.get('strip_prefix', '')
            name_prefix = chunk.get('name_prefix', '')
            exclude_patterns = chunk.get('exclude', [])
            order = chunk.get('order', 'lex')

            # 查找匹配的文件
            files = self._find_files(glob_pattern, exclude_patterns)

            # 排序文件
            if order == 'lex':
                files.sort()

            # 处理每个文件
            for file_path in files:
                # 计算相对路径
                rel_path = self._calculate_relative_path(file_path, strip_prefix)

                # 生成包内路径
                pack_path = name_prefix + rel_path

                # 读取文件内容
                with open(file_path, 'rb') as f:
                    file_content = f.read()

                # 计算文件大小和CRC32
                file_size = len(file_content)
                file_crc32 = calculate_crc32(file_content)

                # 添加到DATA区
                data_content.extend(file_content)

                # 记录索引条目
                index_entries.append({
                    'path': pack_path,
                    'offset': data_offset + len(data_content) - file_size,
                    'size': file_size,
                    'crc32': file_crc32
                })

        # 计算DATA区大小和CRC32
        data_size = len(data_content)
        data_crc32 = calculate_crc32(data_content) if data_size > 0 else 0

        # 写入slot5 (DATA)
        AddrTable.write_slot(header_data, AddrTable.SLOT_DATA, data_offset, data_size, data_crc32)

        # 计算总大小并对齐
        total_size = data_offset + data_size
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
        cart_data = header_data_with_crc + cart_data[self.HEADER_SIZE:] + data_content + padding

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
            cart_data = final_header_data + cart_data[self.HEADER_SIZE:] + data_content + padding

        # 原子写入文件
        atomic_write(out_path, cart_data)

        print(f"Successfully built cart.bin with data: {out_path}")
        print(f"File size: {len(cart_data)} bytes")
        print(f"Header size: {len(header_data_with_crc)} bytes")
        print(f"Data offset: {data_offset} bytes (0x{data_offset:08X})")
        print(f"Data size: {len(data_content)} bytes (0x{len(data_content):08X})")
        print(f"Data CRC32: 0x{data_crc32:08X}")
        print(f"Padding size: {len(padding)} bytes")
        print(f"Header CRC32 enabled: {header_crc32}")
        print(f"Image CRC32 enabled: {image_crc32}")
        print(f"Files in data: {len(index_entries)}")

    def _find_files(self, glob_pattern: str, exclude_patterns: list) -> list:
        """
        查找匹配的文件

        Args:
            glob_pattern (str): 匹配模式
            exclude_patterns (list): 排除模式列表

        Returns:
            list: 匹配的文件路径列表
        """
        # 获取pack.json所在目录
        pack_json_dir = Path(self.pack_spec.pack_json_path).parent

        # 查找匹配的文件
        files = []
        for file_path in pack_json_dir.glob(glob_pattern):
            if file_path.is_file():
                # 检查是否需要排除
                exclude = False
                for exclude_pattern in exclude_patterns:
                    if file_path.match(exclude_pattern):
                        exclude = True
                        break

                if not exclude:
                    files.append(str(file_path))

        return files

    def _calculate_relative_path(self, file_path: str, strip_prefix: str) -> str:
        """
        计算相对路径

        Args:
            file_path (str): 文件路径
            strip_prefix (str): 要移除的前缀

        Returns:
            str: 相对路径
        """
        # 获取pack.json所在目录
        pack_json_dir = Path(self.pack_spec.pack_json_path).parent

        # 计算相对路径
        rel_path = str(Path(file_path).relative_to(pack_json_dir))

        # 移除前缀
        if strip_prefix and rel_path.startswith(strip_prefix):
            rel_path = rel_path[len(strip_prefix):]

        # 确保路径以正斜杠开头
        if rel_path.startswith('/'):
            rel_path = rel_path[1:]

        return rel_path

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
