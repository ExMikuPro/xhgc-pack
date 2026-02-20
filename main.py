import argparse
from src.xhcart_core.api import pack_header_icon

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='XHGC 卡带镜像打包工具')
    parser.add_argument('pack_json', help='pack.json文件路径')
    parser.add_argument('out_path', help='输出cart.bin文件路径')
    parser.add_argument('--verbose', action='store_true', help='打印详细信息')
    
    args = parser.parse_args()
    
    print(f"XHGC 卡带镜像打包工具")
    print(f"Pack JSON: {args.pack_json}")
    print(f"Output: {args.out_path}")
    print(f"Building...")
    
    pack_header_icon(args.pack_json, args.out_path)

if __name__ == '__main__':
    main()