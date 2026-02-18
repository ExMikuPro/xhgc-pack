from PIL import Image, ImageDraw, ImageFont
import json
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from src.xhcart_core.domain.errors import ToolError

def render_text_a8(text: str, font_path: str, height_px: int = 20, pad_x: int = 2, trim_x: bool = True, resample: Optional[int] = None) -> Tuple[bytes, int, int, int, float]:
    """
    将文本渲染为A8单色图片
    
    Args:
        text (str): 要渲染的文本
        font_path (str): 字体文件路径
        height_px (int): 目标高度（默认20px）
        pad_x (int): 左右边距（默认2px）
        trim_x (bool): 是否裁剪左右空白（默认True）
        resample (Optional[int]): 重采样方法（默认None）
    
    Returns:
        Tuple[bytes, int, int, int, float]: (a8_bytes, width, height, baseline, advance)
    """
    # 检查字体文件是否存在
    font_path = Path(font_path)
    if not font_path.exists():
        raise ToolError(f"Font file not found: {font_path}")
    
    # 搜索合适的字体大小
    font_size = _find_optimal_font_size(font_path, height_px)
    
    # 加载字体
    font = ImageFont.truetype(str(font_path), font_size, layout_engine=ImageFont.Layout.BASIC)
    
    # 获取字体度量
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    
    # 创建临时画布以测量文本宽度
    temp_img = Image.new("L", (1, 1), 0)
    draw = ImageDraw.Draw(temp_img)
    
    # 计算文本边界框
    bbox = draw.textbbox((0, 0), text, font=font)
    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    
    # 计算初始画布宽度
    initial_width = bbox_width + 2 * pad_x
    if initial_width < 1:
        initial_width = 1  # 确保最小宽度为1
    
    # 创建最终画布
    img = Image.new("L", (initial_width, height_px), 0)
    draw = ImageDraw.Draw(img)
    
    # 计算文本绘制位置
    # y=0 对应文字顶端，baseline在ascent位置
    x_offset = pad_x - bbox[0]  # 修正bbox_left可能为负的情况
    
    # 绘制文本
    draw.text((x_offset, 0), text, font=font, fill=255)
    
    # 裁剪左右空白
    if trim_x:
        bbox = img.getbbox()
        if bbox:
            # 只在X方向裁剪，保持高度不变
            img = img.crop((bbox[0], 0, bbox[2], height_px))
    
    # 获取最终尺寸
    width, height = img.size
    
    # 计算advance
    advance = font.getlength(text)
    
    # 转换为A8原始数据
    a8_bytes = img.tobytes()
    
    return a8_bytes, width, height, ascent, advance

def _find_optimal_font_size(font_path: Path, target_height: int) -> int:
    """
    搜索最优字体大小，使得line_height最接近且不超过target_height
    
    Args:
        font_path (Path): 字体文件路径
        target_height (int): 目标高度
    
    Returns:
        int: 最优字体大小
    """
    # 二分搜索
    low = 1
    high = 100
    best_size = 1
    best_line_height = float('inf')
    
    while low <= high:
        mid = (low + high) // 2
        try:
            font = ImageFont.truetype(str(font_path), mid, layout_engine=ImageFont.Layout.BASIC)
            ascent, descent = font.getmetrics()
            line_height = ascent + descent
            
            if line_height <= target_height:
                # 找到一个可行的大小，继续搜索更大的
                if line_height > best_line_height:
                    best_line_height = line_height
                    best_size = mid
                low = mid + 1
            else:
                # 太大了，搜索更小的
                high = mid - 1
        except Exception:
            # 如果字体加载失败，尝试更小的大小
            high = mid - 1
    
    return best_size

def write_a8_file(a8_bytes: bytes, out_path: str) -> None:
    """
    写入A8原始数据文件
    
    Args:
        a8_bytes (bytes): A8原始数据
        out_path (str): 输出文件路径
    """
    # 确保输出目录存在
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入文件
    with open(out_path, 'wb') as f:
        f.write(a8_bytes)

def write_json_metadata(out_path: str, text: str, font_path: str, width: int, height: int, baseline: int, advance: float) -> None:
    """
    写入JSON元数据文件
    
    Args:
        out_path (str): 输出文件路径
        text (str): 渲染的文本
        font_path (str): 字体文件路径
        width (int): 输出宽度
        height (int): 输出高度
        baseline (int): 基线位置
        advance (float): 文本宽度
    """
    # 生成JSON路径
    json_path = Path(out_path).with_suffix('.json')
    
    # 准备元数据
    metadata = {
        "text": text,
        "font": Path(font_path).name,
        "width": width,
        "height": height,
        "baseline": baseline,
        "advance": advance
    }
    
    # 写入JSON文件
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def write_header_metadata(out_path: str, text: str, font_path: str, width: int, height: int, baseline: int, a8_bytes: bytes) -> None:
    """
    写入C头文件元数据
    
    Args:
        out_path (str): 输出文件路径
        text (str): 渲染的文本
        font_path (str): 字体文件路径
        width (int): 输出宽度
        height (int): 输出高度
        baseline (int): 基线位置
        a8_bytes (bytes): A8原始数据
    """
    # 生成头文件路径
    header_path = Path(out_path).with_suffix('.h')
    
    # 生成宏名称（去除特殊字符，转换为大写）
    base_name = Path(out_path).stem
    macro_name = ''.join(c if c.isalnum() else '_' for c in base_name).upper()
    array_name = ''.join(c if c.isalnum() else '_' for c in base_name).lower()
    
    # 生成数组内容
    array_lines = []
    for i, byte in enumerate(a8_bytes):
        if i % 16 == 0:
            array_lines.append('    ')
        array_lines.append(f'{byte}, ')
        if (i + 1) % 16 == 0:
            array_lines.append('\n')
    
    array_content = ''.join(array_lines).rstrip(', \n') + '\n'
    
    # 生成头文件内容
    header_content = f"""#ifndef {macro_name}_H
#define {macro_name}_H

#include <stdint.h>

// Generated from text: "{text}"
// Font: {Path(font_path).name}

#define {macro_name}_W {width}
#define {macro_name}_H {height}
#define {macro_name}_BASELINE {baseline}

static const uint8_t {array_name}_a8[{width * height}] = {{
{array_content}}};

#endif // {macro_name}_H
"""
    
    # 写入头文件
    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(header_content)


def process_text_a8(text: str, font_path: str, out_path: str, height_px: int = 20, pad_x: int = 2, trim_x: bool = True, emit_json: bool = False, emit_header: bool = False, emit_jpg: bool = False) -> Dict[str, Any]:
    """
    处理文本A8渲染并输出文件
    
    Args:
        text (str): 要渲染的文本
        font_path (str): 字体文件路径
        out_path (str): 输出文件路径
        height_px (int): 目标高度（默认20px）
        pad_x (int): 左右边距（默认2px）
        trim_x (bool): 是否裁剪左右空白（默认True）
        emit_json (bool): 是否输出JSON元数据（默认False）
        emit_header (bool): 是否输出C头文件（默认False）
        emit_jpg (bool): 是否输出JPG预览文件（默认False）
    
    Returns:
        Dict[str, Any]: 元数据
    """
    # 渲染文本
    a8_bytes, width, height, baseline, advance = render_text_a8(
        text, font_path, height_px, pad_x, trim_x
    )
    
    # 写入A8文件
    write_a8_file(a8_bytes, out_path)
    
    # 写入JSON元数据
    if emit_json:
        write_json_metadata(out_path, text, font_path, width, height, baseline, advance)
    
    # 写入C头文件
    if emit_header:
        write_header_metadata(out_path, text, font_path, width, height, baseline, a8_bytes)
    
    # 写入JPG预览文件
    if emit_jpg:
        write_jpg_preview(out_path, a8_bytes, width, height)
    
    # 返回元数据
    return {
        "text": text,
        "font": Path(font_path).name,
        "width": width,
        "height": height,
        "baseline": baseline,
        "advance": advance
    }

def write_jpg_preview(out_path: str, a8_bytes: bytes, width: int, height: int) -> None:
    """
    写入JPG预览文件
    
    Args:
        out_path (str): 输出文件路径
        a8_bytes (bytes): A8原始数据
        width (int): 宽度
        height (int): 高度
    """
    from PIL import Image
    
    # 生成JPG路径
    jpg_path = Path(out_path).with_suffix('.jpg')
    
    # 从A8数据创建Image对象
    img = Image.new('L', (width, height))
    img.frombytes(a8_bytes, 'raw', 'L')
    
    # 转换为RGB模式（JPG不支持灰度模式）
    rgb_img = Image.new('RGB', (width, height), color='white')
    for y in range(height):
        for x in range(width):
            # 计算像素位置
            pos = y * width + x
            alpha = a8_bytes[pos]
            # 如果alpha > 0，设置为黑色（根据alpha值调整亮度）
            if alpha > 0:
                # 计算亮度：alpha越大，颜色越深
                brightness = 255 - int(alpha * 0.9)  # 稍微调整亮度，使文字更清晰
                rgb_img.putpixel((x, y), (brightness, brightness, brightness))
    
    # 写入JPG文件
    rgb_img.save(jpg_path, 'JPEG', quality=90)
    
    print(f"JPG preview written to: {jpg_path}")