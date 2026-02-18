from PIL import Image, ImageOps
from pathlib import Path

def _hex_to_rgb(hex_color: str) -> tuple:
    """
    将十六进制颜色转换为RGB元组

    Args:
        hex_color (str): 十六进制颜色字符串，如'#FF0000'

    Returns:
        tuple: RGB元组
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def process_image(image_path: Path, width: int, height: int, mode: str = 'cover', background: str = '#000000', resample: str = 'lanczos') -> bytes:
    """
    处理图片并转换为ARGB8888 raw格式

    Args:
        image_path (Path): 图片路径
        width (int): 目标宽度
        height (int): 目标高度
        mode (str): 缩放模式，'cover'或'contain'
        background (str): 背景颜色，仅在'contain'模式下使用
        resample (str): 重采样方法

    Returns:
        bytes: ARGB8888 raw数据
    """
    # 打开图片
    with Image.open(image_path) as img:
        # 转换为RGBA模式（保留或添加alpha通道）
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 选择重采样方法
        resample_method = {
            'lanczos': Image.LANCZOS,
            'bicubic': Image.BICUBIC,
            'bilinear': Image.BILINEAR,
            'nearest': Image.NEAREST
        }.get(resample.lower(), Image.LANCZOS)

        # 根据模式处理图片
        if mode == 'cover':
            # 等比缩放到至少覆盖目标尺寸，然后居中裁剪
            # 兼容旧版本Pillow，不使用resample参数
            try:
                # 尝试使用resample参数
                img = ImageOps.fit(img, (width, height), resample=resample_method)
            except TypeError:
                # 旧版本Pillow不支持resample参数
                img = ImageOps.fit(img, (width, height))
        elif mode == 'contain':
            # 等比缩放到不超过目标尺寸
            # 兼容旧版本Pillow，使用正确的参数顺序
            try:
                # 尝试使用resample参数
                img.thumbnail((width, height), resample=resample_method)
            except TypeError:
                # 旧版本Pillow使用不同的参数顺序
                img.thumbnail((width, height), resample_method)

            # 创建背景画布（RGBA模式）
            bg_color = _hex_to_rgb(background) + (255,)  # 添加完全不透明的alpha值
            bg = Image.new('RGBA', (width, height), bg_color)

            # 计算居中位置
            offset_x = (width - img.width) // 2
            offset_y = (height - img.height) // 2

            # 将图片粘贴到画布中央
            bg.paste(img, (offset_x, offset_y), img)  # 使用img作为mask以保留alpha通道
            img = bg
        else:
            raise ValueError(f"Invalid mode: {mode}")

        # 确保尺寸正确
        if img.width != width or img.height != height:
            raise ValueError(f"Image resizing failed: expected {width}x{height}, got {img.width}x{img.height}")

        # 转换为BGRA字节序的ARGB8888 raw格式
        # 注意：Pillow的RGBA格式是RGBA顺序，我们需要转换为BGRA顺序
        # 并确保每个32位像素的字节序正确（小端）
        raw_data = bytearray()
        pixels = img.load()
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                # 转换为BGRA顺序
                raw_data.extend(bytes([b, g, r, a]))

        # 验证数据长度
        expected_length = width * height * 4
        if len(raw_data) != expected_length:
            raise ValueError(f"Raw data length mismatch: expected {expected_length}, got {len(raw_data)}")

        return bytes(raw_data)