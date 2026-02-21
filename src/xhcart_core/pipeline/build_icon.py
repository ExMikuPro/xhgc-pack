from pathlib import Path
from src.xhcart_core.config.pack_spec import PackSpec
from src.xhcart_core.utils.io import atomic_write
from src.xhcart_core.utils.align import align_to
from src.xhcart_core.tools.img_pillow import process_image
from src.xhcart_core.utils.hashing import calculate_crc32


class BuildIcon:
    """
    构建Icon的类
    """

    # 固定常量
    ICON_WIDTH = 200
    ICON_HEIGHT = 200
    ICON_CHANNELS = 4
    ICON_SIZE = ICON_WIDTH * ICON_HEIGHT * ICON_CHANNELS
    HEADER_SIZE = 4096
    ALIGN_SIZE = 4096

    def __init__(self, pack_spec: PackSpec):
        """
        初始化BuildIcon

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
        header_copy[HeaderV2.CRC_OFFSET:HeaderV2.CRC_OFFSET + 4] = b'\x00\x00\x00\x00'

        # 计算CRC32
        crc = calculate_crc32(header_copy)

        # 以little-endian方式写入CRC32到0x0FFC..0x0FFF
        struct.pack_into('<I', header_bytes, HeaderV2.CRC_OFFSET, crc)

        return header_bytes

    def build(self, out_path: str):
        """
        构建包含header和icon的cart.bin

        Args:
            out_path (str): 输出文件路径
        """
        # 生成header
        from src.xhcart_core.format.xhgc.header import HeaderV2
        from src.xhcart_core.format.xhgc.addr_table import AddrTable

        # 创建HeaderV2对象
        header = HeaderV2(self.pack_spec)

        # 序列化header（不计算CRC32）
        header_data = bytearray(header.pack_without_crc())

        # 计算icon偏移量和大小
        icon_offset = self.HEADER_SIZE
        icon_size = self.ICON_SIZE

        # 写入slot0 (ICON)
        AddrTable.write_slot(header_data, AddrTable.SLOT_ICON, icon_offset, icon_size, 0)

        # 读取和处理icon
        icon_path = self._resolve_icon_path()
        icon_data = self._load_and_process_icon(icon_path)

        # 计算总大小并对齐
        total_size = icon_offset + icon_size
        aligned_size = align_to(total_size, self.ALIGN_SIZE)
        padding_size = aligned_size - total_size
        padding = b'\x00' * padding_size

        # 从配置中读取CRC32设置
        image_crc32 = False  # 默认不计算整个镜像的CRC32

        if self.pack_spec.hash:
            image_crc32 = self.pack_spec.hash.image_crc32

        # 如果需要计算整个镜像的CRC32
        if image_crc32:
            # 先组装完整数据（不包含CRC）
            temp_cart_data = header_data + icon_data + padding

            # 计算并写入Header CRC32
            header_data_with_crc = self.calculate_and_write_header_crc(header_data)

            # 重新组装数据（包含更新后的header）
            cart_data = header_data_with_crc + icon_data + padding

            # 计算整个镜像的CRC32
            image_crc = calculate_crc32(cart_data)

            # 创建新的header副本，写入镜像CRC32
            final_header_data = header_data_with_crc.copy()
            AddrTable.write_slot(final_header_data, 6, 0, len(cart_data), image_crc)

            # 再次计算Header CRC32（因为修改了slot6）
            final_header_data = self.calculate_and_write_header_crc(final_header_data)

            # 最终组装数据
            cart_data = final_header_data + icon_data + padding
        else:
            # 计算并写入Header CRC32
            header_data_with_crc = self.calculate_and_write_header_crc(header_data)

            # 组装完整数据（包含更新后的header）
            cart_data = header_data_with_crc + icon_data + padding

        # 原子写入文件
        atomic_write(out_path, cart_data)

        # 验证CRC32是否正确写入
        self._verify_header_crc(out_path)

        # 输出JSON格式结果
        import json, sys
        result = {
            "step": "icon",
            "status": "ok",
            "file_size": len(cart_data),
            "icon_size": icon_size,
            "padding_size": len(padding),
            "header_crc32": f"0x{calculate_crc32(header_data_with_crc):08X}"
        }
        print(json.dumps(result))
        sys.stdout.flush()

    def _verify_header_crc(self, cart_path: str):
        """
        验证Header CRC32

        Args:
            cart_path (str): cart.bin文件路径
        """
        import struct
        from src.xhcart_core.format.xhgc.header import HeaderV2

        # 读取cart.bin文件
        with open(cart_path, 'rb') as f:
            cart_data = f.read()

        # 提取header数据
        header_data = cart_data[:4096]

        # 提取存储的CRC32
        stored_crc = struct.unpack_from('<I', header_data, HeaderV2.CRC_OFFSET)[0]

        # 创建一个副本，将CRC区域置为0
        header_copy = bytearray(header_data)
        header_copy[HeaderV2.CRC_OFFSET:HeaderV2.CRC_OFFSET + 4] = b'\x00\x00\x00\x00'

        # 计算CRC32
        calculated_crc = calculate_crc32(header_copy)

        # 验证存储的CRC32是否与重新计算的CRC32一致
        if stored_crc != calculated_crc:
            print(f"Debug: stored_crc=0x{stored_crc:08X}, calculated_crc=0x{calculated_crc:08X}")
            print(f"Debug: Header length: {len(header_data)}")
            print(f"Debug: CRC offset: {HeaderV2.CRC_OFFSET}")
            print(f"Debug: First 10 bytes: {header_data[:10].hex()}")
            print(
                f"Debug: CRC area before calculation: {header_copy[HeaderV2.CRC_OFFSET:HeaderV2.CRC_OFFSET + 4].hex()}")
            # 输出错误信息
            import json, sys
            error_result = {
                "step": "icon",
                "status": "error",
                "message": f"Header CRC32 verification failed: stored=0x{stored_crc:08X}, calculated=0x{calculated_crc:08X}"
            }
            print(json.dumps(error_result))
            sys.stdout.flush()
            raise ValueError(
                f"Header CRC32 verification failed: stored=0x{stored_crc:08X}, calculated=0x{calculated_crc:08X}")

        # 验证通过，不输出额外信息

    def _resolve_icon_path(self) -> Path:
        """
        解析icon路径

        Returns:
            Path: icon文件路径
        """
        icon_config = self.pack_spec.icon
        if not icon_config:
            raise ValueError("icon configuration missing")

        icon_path = icon_config.get('path')
        if not icon_path:
            raise ValueError("icon.path missing")

        # 解析为绝对路径（相对于pack.json所在目录）
        from src.xhcart_core.utils.path import resolve_relative_path
        return resolve_relative_path(icon_path, self.pack_spec.pack_json_path)

    def _load_and_process_icon(self, icon_path: Path) -> bytes:
        """
        加载并处理icon

        Args:
            icon_path (Path): icon文件路径

        Returns:
            bytes: 处理后的icon数据
        """
        # 检查文件是否存在
        if not icon_path.exists():
            raise ValueError(f"Icon file not found: {icon_path}")

        # 获取icon配置
        icon_config = self.pack_spec.icon

        # 解析preprocess配置
        preprocess = icon_config.get('preprocess', {})
        mode = preprocess.get('mode', 'contain')
        background = preprocess.get('background', '#000000')
        resample = preprocess.get('resample', 'lanczos')

        # 处理图片
        try:
            icon_data = process_image(
                image_path=icon_path,
                width=self.ICON_WIDTH,
                height=self.ICON_HEIGHT,
                mode=mode,
                background=background,
                resample=resample
            )
        except Exception as e:
            raise ValueError(f"Failed to process icon: {str(e)}")

        # 验证处理后的icon数据长度
        if len(icon_data) != self.ICON_SIZE:
            raise ValueError(
                f"Processed icon size mismatch: expected {self.ICON_SIZE} bytes, got {len(icon_data)} bytes")

        return icon_data