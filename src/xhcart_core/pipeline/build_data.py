from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.utils.align import align_to
from src.xhcart_core.utils.hashing import calculate_crc32
from src.xhcart_core.format.xhgc.addr_table import AddrTable
import struct

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
                    'size': file_size,
                    'crc32': file_crc32
                })

        # 计算DATA区大小和CRC32
        data_size = len(data_content)
        data_crc32 = calculate_crc32(data_content) if data_size > 0 else 0

        # 构建INDEX表（slot4）
        index_content = self.build_index(index_entries, data_content)

        # 计算INDEX大小和CRC32
        index_size = len(index_content)
        index_crc32 = calculate_crc32(index_content) if index_size > 0 else 0

        # 计算INDEX偏移量（4KB对齐，在LUA之后）
        index_offset = align_to(len(cart_data), self.ALIGN_SIZE)

        # 计算DATA偏移量（4KB对齐，在INDEX之后）
        data_offset = align_to(index_offset + index_size, self.ALIGN_SIZE)

        # 写入slot4 (INDEX)
        AddrTable.write_slot(header_data, AddrTable.SLOT_INDEX, index_offset, index_size, index_crc32)

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

        # 组装完整数据（包含更新后的header）- 顺序：INDEX在DATA之前
        cart_data = header_data_with_crc + cart_data[self.HEADER_SIZE:] + index_content + data_content + padding

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
            cart_data = final_header_data + cart_data[self.HEADER_SIZE:] + index_content + data_content + padding

        # 原子写入文件
        atomic_write(out_path, cart_data)

        # 输出JSON格式结果
        import json, sys
        result = {
            "step": "data",
            "status": "ok",
            "file_size": len(cart_data),
            "index_offset": index_offset,
            "index_size": index_size,
            "index_crc32": f"0x{index_crc32:08X}",
            "data_offset": data_offset,
            "data_size": data_size,
            "data_crc32": f"0x{data_crc32:08X}",
            "padding_size": len(padding),
            "files_in_data": len(index_entries)
        }
        print(json.dumps(result))
        sys.stdout.flush()

    def build_index(self, index_entries, data_content):
        """
        构建INDEX表

        Args:
            index_entries (list): 索引条目列表
            data_content (bytearray): DATA区内容

        Returns:
            bytearray: INDEX表内容
        """
        import struct

        # 按路径字典序升序排列
        index_entries.sort(key=lambda x: x['path'])

        # 创建INDEX内容
        index_content = bytearray()

        # 写入Header (8 bytes)
        entry_count = len(index_entries)
        reserved = 0
        index_content.extend(struct.pack('<I', entry_count))  # entry_count
        index_content.extend(struct.pack('<I', reserved))     # reserved

        # 计算每个文件在DATA段中的偏移
        current_offset = 0
        for entry in index_entries:
            # 更新偏移量（相对DATA段起点）
            entry['offset'] = current_offset
            current_offset += entry['size']

        # 写入每个Entry
        for entry in index_entries:
            # 写入16字节定长头
            data_offset = entry['offset']
            data_size = entry['size']
            crc32 = entry['crc32']
            name_len = len(entry['path'])

            # 确保路径长度不超过255
            if name_len > 255:
                raise ValueError(f"Path length exceeds 255 bytes: {entry['path']}")

            # 构建16字节定长头
            header = struct.pack('<I', data_offset)  # data_offset (4 bytes)
            header += struct.pack('<I', data_size)   # data_size (4 bytes)
            header += struct.pack('<I', crc32)       # crc32 (4 bytes)
            header += struct.pack('<B', name_len)    # name_len (1 byte)
            header += b'\x00\x00\x00'                # reserved[3] (3 bytes)

            # 确保头长度为16字节
            assert len(header) == 16, f"Header length should be 16 bytes, got {len(header)}"

            # 写入定长头
            index_content.extend(header)

            # 写入变长路径（UTF-8，不含\0）
            index_content.extend(entry['path'].encode('utf-8'))

        return index_content

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
