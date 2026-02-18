import argparse
from pathlib import Path
from src.xhcart_core.api import pack_header, pack_header_icon, inspect_header, verify_header

def main():
    """
    命令行入口
    """
    parser = argparse.ArgumentParser(description='XHGC Cart Header Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # pack-header 命令
    pack_parser = subparsers.add_parser('pack-header', help='Generate header.bin from pack.json')
    pack_parser.add_argument('pack_json', help='pack.json file path')
    pack_parser.add_argument('out_path', help='Output header.bin file path')
    
    # pack-header-icon 命令
    pack_icon_parser = subparsers.add_parser('pack-header-icon', help='Generate cart.bin with header and icon')
    pack_icon_parser.add_argument('pack_json', help='pack.json file path')
    pack_icon_parser.add_argument('-o', '--output', dest='out_path', help='Output cart.bin file path', required=True)
    
    # inspect-header 命令
    inspect_parser = subparsers.add_parser('inspect-header', help='Inspect header.bin fields')
    inspect_parser.add_argument('header_path', help='header.bin file path')
    
    # verify-header 命令
    verify_parser = subparsers.add_parser('verify-header', help='Verify header.bin CRC32')
    verify_parser.add_argument('header_path', help='header.bin file path')
    
    args = parser.parse_args()
    
    if args.command == 'pack-header':
        pack_header(args.pack_json, args.out_path)
        print(f"Successfully generated header: {args.out_path}")
    
    elif args.command == 'pack-header-icon':
        pack_header_icon(args.pack_json, args.out_path)
    
    elif args.command == 'inspect-header':
        info = inspect_header(args.header_path)
        print("Header Inspection:")
        print("-" * 80)
        print(f"Magic: {info['magic']}")
        print(f"Header Version: {info['header_version']}")
        print(f"Header Size: {info['header_size']}")
        print(f"Flags: {info['flags']}")
        print(f"Cart ID: {info['cart_id']}")
        print(f"Title: {info['title']}")
        print(f"Title (ZH): {info['title_zh']}")
        print(f"Publisher: {info['publisher']}")
        print(f"Version: {info['version']}")
        print(f"Entry: {info['entry']}")
        print(f"Min FW: {info['min_fw']}")
        print(f"CRC32: 0x{info['crc32']:08X}")
        print(f"Address Table Range: {info['addr_table_range']}")
        print(f"CRC32 Range: {info['crc32_range']}")
        print("\nAddress Table Slots:")
        print("-" * 80)
        print(f"{'Name':<10} {'Offset':<10} {'Data Offset':<15} {'Size':<10} {'CRC32':<10}")
        print("-" * 80)
        # 显示所有固定槽位
        slot_names = ['ICON', 'THMB', 'MANF', 'ENTRY', 'INDEX', 'DATA']
        for i, slot in enumerate(info['addr_table'][:6]):
            if i < len(slot_names):
                print(f"{slot['name']:<10} 0x{slot['offset']:04X} 0x{slot['data_offset']:08X} {slot['size']:<10} 0x{slot['crc32']:08X}")
    
    elif args.command == 'verify-header':
        result = verify_header(args.header_path)
        if result:
            print("Header CRC32 verification PASSED")
        else:
            print("Header CRC32 verification FAILED")

if __name__ == '__main__':
    main()