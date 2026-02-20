#!/usr/bin/env python3
"""
测试 ENTRY 段构建功能
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.xhcart_core.api import pack_header_icon, inspect_header

def test_entry_build():
    """
    测试 ENTRY 段构建功能
    """
    print("=== 测试 ENTRY 段构建功能 ===")
    
    # 定义测试路径
    test_dir = Path(__file__).parent
    pack_json_path = test_dir / "pack.json"
    output_dir = test_dir / "output"
    output_path = output_dir / "cart.bin"
    
    # 确保输出目录存在
    output_dir.mkdir(exist_ok=True)
    
    try:
        # 构建包含 header、icon 和 entry 的 cart.bin
        print(f"构建 cart.bin 中...")
        print(f"Pack JSON: {pack_json_path}")
        print(f"Output: {output_path}")
        
        pack_header_icon(str(pack_json_path), str(output_path))
        
        # 验证输出文件存在
        if not output_path.exists():
            print("错误: 输出文件不存在")
            return False
        
        # 检查文件大小
        file_size = output_path.stat().st_size
        print(f"\n=== 输出文件信息 ===")
        print(f"文件大小: {file_size} bytes (0x{file_size:08X})")
        
        # 解析 header 信息
        print(f"\n=== Header 信息 ===")
        header_info = inspect_header(str(output_path))
        
        # 打印基本信息
        print(f"Magic: {header_info['magic']}")
        print(f"Header Version: {header_info['header_version']}")
        print(f"Header Size: {header_info['header_size']} bytes")
        print(f"Cart ID: {header_info['cart_id']}")
        print(f"Title: {header_info['title']}")
        print(f"Title ZH: {header_info['title_zh']}")
        print(f"Publisher: {header_info['publisher']}")
        print(f"Version: {header_info['version']}")
        print(f"Entry: {header_info['entry']}")
        print(f"Min FW: {header_info['min_fw']}")
        print(f"Header CRC32: 0x{header_info['crc32']:08X}")
        
        # 打印地址表信息
        print(f"\n=== 地址表信息 ===")
        for slot in header_info['addr_table']:
            if slot['data_offset'] > 0 or slot['size'] > 0:
                print(f"{slot['name']}: offset=0x{slot['data_offset']:08X}, size=0x{slot['size']:08X}, crc32=0x{slot['crc32']:08X}")
        
        # 验证 ENTRY 段信息
        print(f"\n=== ENTRY 段验证 ===")
        entry_slot = None
        for slot in header_info['addr_table']:
            if slot['name'] == 'ENTRY':
                entry_slot = slot
                break
        
        if entry_slot:
            print(f"ENTRY 段存在: offset=0x{entry_slot['data_offset']:08X}, size=0x{entry_slot['size']:08X}, crc32=0x{entry_slot['crc32']:08X}")
            
            # 验证偏移量是否 4KB 对齐
            if entry_slot['data_offset'] % 4096 == 0:
                print("✓ ENTRY 段偏移量 4KB 对齐")
            else:
                print("✗ ENTRY 段偏移量未 4KB 对齐")
                return False
            
            # 验证大小是否合理
            if entry_slot['size'] > 0:
                print("✓ ENTRY 段大小大于 0")
            else:
                print("✗ ENTRY 段大小为 0")
                return False
        else:
            print("✗ ENTRY 段不存在")
            return False
        
        print(f"\n=== 测试完成 ===")
        print("所有测试通过!")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print(f"\n测试结束")

if __name__ == "__main__":
    success = test_entry_build()
    sys.exit(0 if success else 1)