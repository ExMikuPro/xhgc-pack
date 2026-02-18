import argparse
from api import pack_header

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='Header生成工具')
    parser.add_argument('pack_json', help='pack.json文件路径')
    parser.add_argument('out_path', help='输出header文件路径')
    parser.add_argument('--verbose', action='store_true', help='打印详细信息')
    
    args = parser.parse_args()
    
    pack_header(args.pack_json, args.out_path, verbose=args.verbose)

if __name__ == '__main__':
    main()