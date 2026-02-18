import os
import tempfile
import hashlib
from pathlib import Path
import pytest
from src.xhcart_core.tools.text_a8 import render_text_a8, process_text_a8
from src.xhcart_core.domain.errors import ToolError


def test_output_height():
    """测试输出高度恒为20"""
    # 使用系统默认字体进行测试
    # 注意：这里假设系统有默认字体，实际测试时可能需要指定具体字体路径
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    text = "Test"
    a8_bytes, width, height, baseline, advance = render_text_a8(text, font_path)
    
    assert height == 20
    assert len(a8_bytes) == width * height


def test_width_varies_with_text():
    """测试宽度随text变化"""
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    # 测试短文本
    text_short = "A"
    _, width_short, _, _, _ = render_text_a8(text_short, font_path)
    
    # 测试长文本
    text_long = "Settings"
    _, width_long, _, _, _ = render_text_a8(text_long, font_path)
    
    assert width_short < width_long


def test_output_bytes_length():
    """测试输出bytes长度 == w*20"""
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    text = "Test"
    a8_bytes, width, height, _, _ = render_text_a8(text, font_path)
    
    assert len(a8_bytes) == width * height
    assert height == 20


def test_deterministic():
    """测试确定性：同输入输出一致"""
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    text = "Test"
    
    # 两次渲染
    a8_bytes1, _, _, _, _ = render_text_a8(text, font_path)
    a8_bytes2, _, _, _, _ = render_text_a8(text, font_path)
    
    # 计算哈希值
    hash1 = hashlib.sha256(a8_bytes1).hexdigest()
    hash2 = hashlib.sha256(a8_bytes2).hexdigest()
    
    assert hash1 == hash2


def test_font_not_found():
    """测试字体文件不存在时抛异常"""
    text = "Test"
    non_existent_font = "/path/to/non/existent/font.ttf"
    
    with pytest.raises(ToolError) as excinfo:
        render_text_a8(text, non_existent_font)
    
    assert "Font file not found" in str(excinfo.value)
    assert "non/existent/font.ttf" in str(excinfo.value)


def test_empty_text():
    """测试空字符串"""
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    text = ""
    a8_bytes, width, height, _, _ = render_text_a8(text, font_path)
    
    assert height == 20
    assert width >= 1  # 确保最小宽度为1
    assert len(a8_bytes) == width * height


def test_process_text_a8():
    """测试process_text_a8函数"""
    font_path = _get_default_font_path()
    if not font_path:
        pytest.skip("No default font found")
    
    text = "Test"
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        out_path = os.path.join(temp_dir, "test.a8")
        
        # 处理文本
        result = process_text_a8(
            text=text,
            font_path=font_path,
            out_path=out_path,
            height_px=20,
            pad_x=2,
            trim_x=True,
            emit_json=True,
            emit_header=True
        )
        
        # 验证结果
        assert result["text"] == text
        assert result["height"] == 20
        
        # 验证文件存在
        assert os.path.exists(out_path)
        assert os.path.exists(os.path.join(temp_dir, "test.json"))
        assert os.path.exists(os.path.join(temp_dir, "test.h"))


def _get_default_font_path():
    """获取系统默认字体路径"""
    # 尝试常见字体路径
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "C:\\Windows\\Fonts\\Arial.ttf",  # Windows
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            return path
    
    return None


if __name__ == "__main__":
    pytest.main([__file__])