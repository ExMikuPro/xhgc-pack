from pathlib import Path
from xhcart_core.config.pack_spec import PackSpec
from xhcart_core.utils.io import atomic_write
from xhcart_core.utils.align import align_to
from xhcart_core.utils.hashing import calculate_crc32
from xhcart_core.format.xhgc.addr_table import AddrTable
import struct

class BuildData:
    """
    构建DATA区的类
    """

    # 固定常量
    HEADER_SIZE = 4096
    ALIGN_SIZE = 4096
    INDEX_MAGIC = b'XHGCIDX2'
    INDEX_VERSION = 1
    INDEX_HEADER_SIZE = 32
    INDEX_ENTRY_SIZE = 32
    XHGC_RES_IMAGE = 1
    XHGC_RES_SCRIPT = 2
    XHGC_IMG_NONE = 0
    XHGC_IMG_BGRA8888 = 1
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    RES_IMAGE_MAGIC = b'XIMG'
    RES_IMAGE_FORMAT_BGRA8888 = 1
    RES_IMAGE_HEADER_SIZE = 24

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

                # 读取文件内容，RES图片可按配置转换为BGRA8888 raw数据
                file_content, file_meta = self._read_chunk_file(file_path, chunk_type, chunk)

                # 计算文件大小和CRC32
                file_size = len(file_content)
                file_crc32 = calculate_crc32(file_content)
                file_offset = len(data_content)

                # 添加到DATA区
                data_content.extend(file_content)

                # 记录索引条目
                index_entries.append({
                    'path': pack_path,
                    'offset': file_offset,
                    'size': file_size,
                    'crc32': file_crc32,
                    'type': file_meta.get('type', self._resource_type_for_chunk(chunk_type)),
                    'format': file_meta.get('format', self.XHGC_IMG_NONE),
                    'width': file_meta.get('width', 0),
                    'height': file_meta.get('height', 0)
                })

        # 计算DATA区大小和CRC32
        data_size = len(data_content)
        data_crc32 = calculate_crc32(data_content) if data_size > 0 else 0

        # 构建INDEX表（slot4）
        index_content = self.build_index(index_entries)

        # 计算INDEX大小和CRC32
        index_size = len(index_content)
        index_crc32 = calculate_crc32(index_content) if index_size > 0 else 0

        # 计算INDEX偏移量（4KB对齐，在LUA之后）
        index_offset = align_to(len(cart_data), self.ALIGN_SIZE)

        # 计算DATA偏移量（4KB对齐，在INDEX之后）
        data_offset = align_to(index_offset + index_size, self.ALIGN_SIZE)
        index_padding_size = data_offset - (index_offset + index_size)
        index_padding = b'\x00' * index_padding_size

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

        existing_payload = cart_data[self.HEADER_SIZE:]
        cart_data = (
            header_data
            + existing_payload
            + index_content
            + index_padding
            + data_content
            + padding
        )
        AddrTable.write_present_slot_payload_crcs(header_data, cart_data)

        # 计算并写入Header CRC32
        if header_crc32:
            header_data_with_crc = self.calculate_and_write_header_crc(header_data)
        else:
            header_data_with_crc = header_data

        # 组装完整数据（包含更新后的header）- 顺序：INDEX在DATA之前
        cart_data = (
            header_data_with_crc
            + existing_payload
            + index_content
            + index_padding
            + data_content
            + padding
        )

        # 如果需要计算整个镜像的CRC32
        if image_crc32:
            # 计算整个镜像的CRC32
            image_crc = calculate_crc32(cart_data)

            # 创建新的header副本，写入镜像CRC32到slot14
            final_header_data = header_data_with_crc.copy()
            AddrTable.write_slot(final_header_data, AddrTable.SLOT_IMAGE_CRC, 0, len(cart_data), image_crc)

            # 再次计算Header CRC32（因为修改了slot6）
            if header_crc32:
                final_header_data = self.calculate_and_write_header_crc(final_header_data)

            # 最终组装数据
            cart_data = (
                final_header_data
                + existing_payload
                + index_content
                + index_padding
                + data_content
                + padding
            )

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
            "index_padding_size": index_padding_size,
            "padding_size": len(padding),
            "files_in_data": len(index_entries)
        }
        print(json.dumps(result))
        sys.stdout.flush()

    def build_index(self, index_entries):
        """
        构建INDEX表

        Args:
            index_entries (list): 索引条目列表

        Returns:
            bytearray: INDEX表内容
        """
        import struct

        # 按路径字典序升序排列
        index_entries.sort(key=lambda x: x['path'])

        # 创建INDEX内容
        index_content = bytearray()

        entry_count = len(index_entries)
        entries_off = self.INDEX_HEADER_SIZE
        strings_off = entries_off + entry_count * self.INDEX_ENTRY_SIZE

        entries_content = bytearray()
        strings_content = bytearray()
        for entry in index_entries:
            path_bytes = entry['path'].encode('utf-8') + b'\x00'
            path_off = len(strings_content)
            strings_content.extend(path_bytes)

            data_offset = entry['offset']
            data_size = entry['size']
            crc32 = entry['crc32']
            entry_data = struct.pack(
                '<IIIII BB H H H I',
                self._fnv1a_32(entry['path']),
                path_off,
                data_offset,
                data_size,
                crc32,
                entry.get('type', 0),
                entry.get('format', 0),
                entry.get('width', 0),
                entry.get('height', 0),
                0,  # flags
                0   # reserved
            )
            assert len(entry_data) == self.INDEX_ENTRY_SIZE, (
                f"INDEX entry length should be {self.INDEX_ENTRY_SIZE} bytes, got {len(entry_data)}"
            )
            entries_content.extend(entry_data)

        strings_size = len(strings_content)
        index_content.extend(struct.pack(
            '<8sHHIIIII',
            self.INDEX_MAGIC,
            self.INDEX_VERSION,
            self.INDEX_ENTRY_SIZE,
            entry_count,
            entries_off,
            strings_off,
            strings_size,
            0
        ))
        index_content.extend(entries_content)
        index_content.extend(strings_content)

        return index_content

    def _fnv1a_32(self, value: str) -> int:
        h = 0x811C9DC5
        for byte in value.encode('utf-8'):
            h ^= byte
            h = (h * 0x01000193) & 0xFFFFFFFF
        return h

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

    def _read_chunk_file(self, file_path: str, chunk_type: str, chunk: dict) -> tuple:
        """
        读取chunk文件内容。RES图片可选转换为BGRA8888 raw数据。
        """
        if chunk_type == 'RES' and self._should_convert_res_image(file_path, chunk):
            return self._convert_res_image(file_path, chunk)

        with open(file_path, 'rb') as f:
            return f.read(), {
                'type': self._resource_type_for_chunk(chunk_type),
                'format': self.XHGC_IMG_NONE,
                'width': 0,
                'height': 0
            }

    def _resource_type_for_chunk(self, chunk_type: str) -> int:
        if chunk_type == 'LUA':
            return self.XHGC_RES_SCRIPT
        return 0

    def _should_convert_res_image(self, file_path: str, chunk: dict) -> bool:
        image_format = chunk.get('image_format', 'none')
        if not isinstance(image_format, str):
            raise ValueError("RES image_format must be a string")

        if image_format.lower() in ('none', ''):
            return False

        if image_format.upper() != 'BGRA8888':
            raise ValueError(f"Unsupported RES image_format: {image_format}")

        return Path(file_path).suffix.lower() in self.IMAGE_EXTENSIONS

    def _convert_res_image(self, file_path: str, chunk: dict) -> tuple:
        preprocess = chunk.get('image_preprocess', {})
        if preprocess is None:
            preprocess = {}
        if not isinstance(preprocess, dict):
            raise ValueError("RES image_preprocess must be an object")

        width = preprocess.get('width')
        height = preprocess.get('height')
        mode = preprocess.get('mode', 'contain')
        background = preprocess.get('background', '#000000')
        resample = preprocess.get('resample', 'lanczos')

        try:
            from xhcart_core.tools.img_pillow import process_resource_image_with_metadata
        except ImportError as e:
            raise ImportError("Pillow is required for RES image conversion. Please install it with 'pip install Pillow'") from e

        try:
            raw_data, actual_width, actual_height = process_resource_image_with_metadata(
                image_path=Path(file_path),
                width=width,
                height=height,
                mode=mode,
                background=background,
                resample=resample
            )
            if chunk.get('image_metadata', False):
                raw_data = self._build_res_image_container(raw_data, actual_width, actual_height)
            return raw_data, {
                'type': self.XHGC_RES_IMAGE,
                'format': self.XHGC_IMG_BGRA8888,
                'width': actual_width,
                'height': actual_height
            }
        except Exception as e:
            raise ValueError(f"Failed to convert RES image to BGRA8888: {file_path}: {str(e)}") from e

    def _build_res_image_container(self, raw_data: bytes, width: int, height: int) -> bytes:
        stride = width * 4
        expected_size = stride * height
        if len(raw_data) != expected_size:
            raise ValueError(f"BGRA8888 data size mismatch: expected {expected_size}, got {len(raw_data)}")

        header = struct.pack(
            '<4sHHHHBBHII',
            self.RES_IMAGE_MAGIC,
            1,  # version
            self.RES_IMAGE_HEADER_SIZE,
            width,
            height,
            self.RES_IMAGE_FORMAT_BGRA8888,
            4,  # bytes_per_pixel
            0,  # flags
            stride,
            len(raw_data)
        )
        return header + raw_data

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
        from xhcart_core.format.xhgc.header import HeaderV2

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
