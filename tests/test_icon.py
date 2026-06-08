import tempfile
import os
import json
import hashlib
import copy
import zlib
from PIL import Image
from xhcart_core.api import pack_header_icon, inspect_header, verify_header
from xhcart_core.utils.align import align_to

class TestIcon:
    """
    Icon 测试类
    """
    
    def setup_method(self):
        """
        测试前的设置
        """
        # 创建临时目录
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack_json_path = os.path.join(self.temp_dir.name, 'pack.json')
        self.cart_bin_path = os.path.join(self.temp_dir.name, 'cart.bin')
        self.create_test_lua()
        
        # 创建基础的pack.json
        self.base_pack_json = {
            "format": "XHGC_PACK",
            "pack_version": 1,
            "meta": {
                "title": "Demo Game",
                "title_zh": "演示游戏",
                "publisher": "Nixie Studio",
                "version": "0.1.0",
                "cart_id": "0x0123456789ABCDEF",
                "entry": "app/main.lua",
                "min_fw": "0.8.0"
            },
            "icon": {
                "path": "icon.png",
                "format": "ARGB8888",
                "width": 200,
                "height": 200,
                "preprocess": {
                    "mode": "contain",
                    "background": "#000000",
                    "resample": "lanczos"
                }
            },
            "build": {
                "output": "build/demo_game.cart.bin",
                "header_size": 4096,
                "alignment_bytes": 4096
            },
            "chunks": [
                {
                    "type": "LUA",
                    "glob": "script/main.lua",
                    "strip_prefix": "script/",
                    "name_prefix": "app/",
                    "compress": "none",
                    "exclude": ["**/.DS_Store"],
                    "order": "lex"
                }
            ]
        }
    
    def write_pack_json(self, data):
        """
        写入pack.json文件
        """
        with open(self.pack_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def create_test_lua(self):
        """
        创建完整打包流水线需要的Lua入口。
        """
        script_dir = os.path.join(self.temp_dir.name, 'script')
        os.makedirs(script_dir, exist_ok=True)
        with open(os.path.join(script_dir, 'main.lua'), 'w', encoding='utf-8') as f:
            f.write("print('hello xhgc')\n")

    def create_test_icon(self, path):
        """
        创建测试用的PNG icon文件。
        """
        img = Image.new('RGBA', (200, 200), (0, 128, 255, 255))
        img.save(path)
    
    def test_png_icon(self):
        """
        测试输入PNG icon -> 输出文件大小正确（pad 到 4096）
        """
        # 创建测试用的PNG icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.png')
        self.create_test_icon(icon_path)
        
        # 写入pack.json
        self.write_pack_json(self.base_pack_json)
        
        # 生成cart.bin
        pack_header_icon(self.pack_json_path, self.cart_bin_path)
        
        # 检查文件大小
        file_size = os.path.getsize(self.cart_bin_path)
        assert file_size % 4096 == 0, f"File size should be aligned to 4096, got {file_size}"
        assert file_size >= 4096 + 160000, f"File size should be at least 4096 + 160000, got {file_size}"
    
    def test_icon_slot(self):
        """
        测试slot0 ICON offset==4096, size==160000, crc32等于payload IEEE CRC32
        """
        # 创建测试用的PNG icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.png')
        self.create_test_icon(icon_path)
        
        # 写入pack.json
        self.write_pack_json(self.base_pack_json)
        
        # 生成cart.bin
        pack_header_icon(self.pack_json_path, self.cart_bin_path)
        
        # 检查slot0
        info = inspect_header(self.cart_bin_path)
        icon_slot = None
        for slot in info['addr_table']:
            if slot['name'] == 'ICON':
                icon_slot = slot
                break
        
        assert icon_slot is not None, "ICON slot not found"
        assert icon_slot['data_offset'] == 4096, f"ICON offset should be 4096, got {icon_slot['data_offset']}"
        assert icon_slot['size'] == 160000, f"ICON size should be 160000, got {icon_slot['size']}"
        with open(self.cart_bin_path, 'rb') as f:
            cart_data = f.read()
        start = icon_slot['data_offset']
        end = start + icon_slot['size']
        expected_crc32 = zlib.crc32(cart_data[start:end]) & 0xFFFFFFFF
        assert icon_slot['crc32'] != 0, "ICON crc32 should be written"
        assert icon_slot['crc32'] == expected_crc32, (
            f"ICON crc32 should be 0x{expected_crc32:08X}, got 0x{icon_slot['crc32']:08X}"
        )
        assert verify_header(self.cart_bin_path), "Header CRC32 should verify after slot CRC update"
    
    def test_icon_not_found(self):
        """
        测试icon文件不存在 -> 抛错误
        """
        # 写入pack.json（引用不存在的icon文件）
        pack_json = copy.deepcopy(self.base_pack_json)
        pack_json['icon']['path'] = 'non_existent.png'
        self.write_pack_json(pack_json)
        
        try:
            pack_header_icon(self.pack_json_path, self.cart_bin_path)
            assert False, "Should raise error for non-existent icon file"
        except Exception as e:
            assert "not found" in str(e)
    
    def test_icon_invalid_size(self):
        """
        测试icon配置尺寸不对 -> 抛错误
        """
        # 创建测试用的PNG icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.png')
        self.create_test_icon(icon_path)
        
        # 写入pack.json
        pack_json = copy.deepcopy(self.base_pack_json)
        pack_json['icon']['width'] = 128
        self.write_pack_json(pack_json)
        
        try:
            pack_header_icon(self.pack_json_path, self.cart_bin_path)
            assert False, "Should raise error for invalid icon size"
        except Exception as e:
            assert "icon.width must be 200" in str(e)
    
    def test_deterministic(self):
        """
        测试deterministic：同一个输入图片与pack.json生成的输出一致
        """
        # 创建测试用的PNG icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.png')
        self.create_test_icon(icon_path)
        
        # 写入pack.json
        self.write_pack_json(self.base_pack_json)
        
        # 生成第一次cart.bin
        cart_bin_path1 = os.path.join(self.temp_dir.name, 'cart1.bin')
        pack_header_icon(self.pack_json_path, cart_bin_path1)
        
        # 生成第二次cart.bin
        cart_bin_path2 = os.path.join(self.temp_dir.name, 'cart2.bin')
        pack_header_icon(self.pack_json_path, cart_bin_path2)
        
        # 比较两个文件的hash
        with open(cart_bin_path1, 'rb') as f1, open(cart_bin_path2, 'rb') as f2:
            hash1 = hashlib.sha256(f1.read()).hexdigest()
            hash2 = hashlib.sha256(f2.read()).hexdigest()
        
        assert hash1 == hash2, "Output should be deterministic"

    def test_image_crc_uses_slot14_without_duplicating_segments(self):
        """
        测试整镜像CRC写入slot14，且不会重复追加已有段。
        """
        icon_path = os.path.join(self.temp_dir.name, 'icon.png')
        self.create_test_icon(icon_path)

        pack_json = copy.deepcopy(self.base_pack_json)
        pack_json['hash'] = {
            'header_crc32': True,
            'image_crc32': True,
            'per_chunk_crc32': False,
            'per_file_crc32': False,
        }
        self.write_pack_json(pack_json)

        pack_header_icon(self.pack_json_path, self.cart_bin_path)
        info = inspect_header(self.cart_bin_path)
        slots = {slot['name']: slot for slot in info['addr_table']}
        file_size = os.path.getsize(self.cart_bin_path)

        assert slots['MANF']['data_offset'] == align_to(
            slots['ICON']['data_offset'] + slots['ICON']['size'], 4096
        )
        assert slots['ENTRY']['data_offset'] == align_to(
            slots['MANF']['data_offset'] + slots['MANF']['size'], 4096
        )
        assert slots['INDEX']['data_offset'] == align_to(
            slots['ENTRY']['data_offset'] + slots['ENTRY']['size'], 4096
        )
        assert slots['DATA']['data_offset'] == align_to(
            slots['INDEX']['data_offset'] + slots['INDEX']['size'], 4096
        )
        assert file_size == align_to(slots['DATA']['data_offset'] + slots['DATA']['size'], 4096)
        assert slots['IMAGE_CRC']['data_offset'] == 0
        assert slots['IMAGE_CRC']['size'] == file_size
        assert slots['IMAGE_CRC']['crc32'] != 0

        with open(self.cart_bin_path, 'rb') as f:
            cart_data = f.read()
        for slot_name in ['ICON', 'MANF', 'ENTRY', 'INDEX', 'DATA']:
            slot = slots[slot_name]
            start = slot['data_offset']
            end = start + slot['size']
            expected_crc32 = zlib.crc32(cart_data[start:end]) & 0xFFFFFFFF
            assert slot['crc32'] == expected_crc32, (
                f"{slot_name} crc32 should be 0x{expected_crc32:08X}, got 0x{slot['crc32']:08X}"
            )
    
    def teardown_method(self):
        """
        测试后的清理
        """
        self.temp_dir.cleanup()
