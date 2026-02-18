import tempfile
import os
import json
import hashlib
from src.xhcart_core.api import pack_header_icon, inspect_header
from src.xhcart_core.domain.errors import ConfigError

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
        
        # 创建基础的pack.json
        self.base_pack_json = {
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
                "path": "icon.rgb888",
                "format": "RGB888",
                "width": 200,
                "height": 200
            },
            "build": {
                "output": "build/demo_game.cart.bin",
                "header_size": 4096,
                "align": 4096
            }
        }
    
    def teardown_method(self):
        """
        测试后的清理
        """
        self.temp_dir.cleanup()
    
    def write_pack_json(self, data):
        """
        写入pack.json文件
        """
        with open(self.pack_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def create_test_raw_icon(self, path):
        """
        创建测试用的raw icon文件
        """
        # 200x200 RGB888 = 120000 bytes
        icon_data = b'\x00' * 120000
        with open(path, 'wb') as f:
            f.write(icon_data)
    
    def test_raw_icon(self):
        """
        测试输入raw icon (120000 bytes) -> 输出文件大小正确（pad 到 4096）
        """
        # 创建测试用的raw icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.rgb888')
        self.create_test_raw_icon(icon_path)
        
        # 写入pack.json
        self.write_pack_json(self.base_pack_json)
        
        # 生成cart.bin
        pack_header_icon(self.pack_json_path, self.cart_bin_path)
        
        # 检查文件大小
        file_size = os.path.getsize(self.cart_bin_path)
        assert file_size % 4096 == 0, f"File size should be aligned to 4096, got {file_size}"
        assert file_size >= 4096 + 120000, f"File size should be at least 4096 + 120000, got {file_size}"
    
    def test_icon_slot(self):
        """
        测试slot0 ICON offset==4096, size==120000, crc32==0
        """
        # 创建测试用的raw icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.rgb888')
        self.create_test_raw_icon(icon_path)
        
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
        assert icon_slot['size'] == 120000, f"ICON size should be 120000, got {icon_slot['size']}"
        assert icon_slot['crc32'] == 0, f"ICON crc32 should be 0, got {icon_slot['crc32']}"
    
    def test_icon_not_found(self):
        """
        测试icon文件不存在 -> 抛错误
        """
        # 写入pack.json（引用不存在的icon文件）
        pack_json = self.base_pack_json.copy()
        pack_json['icon']['path'] = 'non_existent.rgb888'
        self.write_pack_json(pack_json)
        
        try:
            pack_header_icon(self.pack_json_path, self.cart_bin_path)
            assert False, "Should raise error for non-existent icon file"
        except Exception as e:
            assert "not found" in str(e)
    
    def test_icon_invalid_size(self):
        """
        测试icon文件尺寸不对 -> 抛错误
        """
        # 创建尺寸不对的raw icon（小于120000 bytes）
        icon_path = os.path.join(self.temp_dir.name, 'icon.rgb888')
        with open(icon_path, 'wb') as f:
            f.write(b'\x00' * 100000)  # 只有100000 bytes
        
        # 写入pack.json
        self.write_pack_json(self.base_pack_json)
        
        try:
            pack_header_icon(self.pack_json_path, self.cart_bin_path)
            assert False, "Should raise error for invalid icon size"
        except Exception as e:
            assert "invalid" in str(e)
    
    def test_deterministic(self):
        """
        测试deterministic：同一个输入图片与pack.json生成的输出一致
        """
        # 创建测试用的raw icon
        icon_path = os.path.join(self.temp_dir.name, 'icon.rgb888')
        self.create_test_raw_icon(icon_path)
        
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
    
    def teardown_method(self):
        """
        测试后的清理
        """
        self.temp_dir.cleanup()