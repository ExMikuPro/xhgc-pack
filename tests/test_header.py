import tempfile
import os
import json
from src.xhcart_core.api import pack_header, inspect_header, verify_header
from src.xhcart_core.config.load import ConfigError

class TestHeader:
    """
    Header 测试类
    """
    
    def setup_method(self):
        """
        测试前的设置
        """
        # 创建临时目录
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pack_json_path = os.path.join(self.temp_dir.name, 'pack.json')
        self.header_bin_path = os.path.join(self.temp_dir.name, 'header.bin')
        
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
            "build": {
                "output": "build/demo_game.cart.bin",
                "header_size": 4096
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
    
    def test_header_size(self):
        """
        测试header大小是否为4096
        """
        self.write_pack_json(self.base_pack_json)
        pack_header(self.pack_json_path, self.header_bin_path)
        
        # 检查文件大小
        assert os.path.getsize(self.header_bin_path) == 4096
    
    def test_header_fields(self):
        """
        测试header字段是否正确
        """
        self.write_pack_json(self.base_pack_json)
        pack_header(self.pack_json_path, self.header_bin_path)
        
        # 检查字段
        info = inspect_header(self.header_bin_path)
        assert info['magic'] == b'XHGC_PAC'
        assert info['header_version'] == 2
        assert info['header_size'] == 4096
        assert info['cart_id'] == '0x123456789abcdef'
        assert info['title'] == 'Demo Game'
        assert info['title_zh'] == '演示游戏'
        assert info['publisher'] == 'Nixie Studio'
        assert info['version'] == '0.1.0'
        assert info['entry'] == 'app/main.lua'
        assert info['min_fw'] == '0.8.0'
    
    def test_string_too_long(self):
        """
        测试字符串超长会抛异常
        """
        # 测试title超长
        long_title_pack_json = self.base_pack_json.copy()
        long_title_pack_json['meta']['title'] = 'A' * 65  # 超过64字节
        self.write_pack_json(long_title_pack_json)
        
        try:
            pack_header(self.pack_json_path, self.header_bin_path)
            assert False, "Should raise ValueError for long title"
        except ValueError as e:
            assert "meta.title exceeds" in str(e)
    
    def test_cart_id_parsing(self):
        """
        测试cart_id解析正确
        """
        # 测试带0x前缀的cart_id
        pack_json_with_0x = self.base_pack_json.copy()
        pack_json_with_0x['meta']['cart_id'] = "0x123456789ABCDEF"
        self.write_pack_json(pack_json_with_0x)
        pack_header(self.pack_json_path, self.header_bin_path)
        info = inspect_header(self.header_bin_path)
        assert info['cart_id'] == '0x123456789abcdef'
        
        # 测试不带0x前缀的cart_id
        pack_json_without_0x = self.base_pack_json.copy()
        pack_json_without_0x['meta']['cart_id'] = "123456789ABCDEF"
        self.write_pack_json(pack_json_without_0x)
        pack_header(self.pack_json_path, self.header_bin_path)
        info = inspect_header(self.header_bin_path)
        assert info['cart_id'] == '0x123456789abcdef'
    
    def test_verify_header(self):
        """
        测试verify_header通过
        """
        self.write_pack_json(self.base_pack_json)
        pack_header(self.pack_json_path, self.header_bin_path)
        
        # 验证CRC32
        assert verify_header(self.header_bin_path) is True
    
    def test_invalid_header_size(self):
        """
        测试无效的header_size
        """
        invalid_pack_json = self.base_pack_json.copy()
        invalid_pack_json['build']['header_size'] = 8192
        self.write_pack_json(invalid_pack_json)
        
        try:
            pack_header(self.pack_json_path, self.header_bin_path)
            assert False, "Should raise ConfigError for invalid header_size"
        except ConfigError as e:
            assert "build.header_size must be 4096" in str(e)
    
    def test_missing_required_fields(self):
        """
        测试缺少必填字段
        """
        # 测试缺少title
        missing_title_pack_json = self.base_pack_json.copy()
        del missing_title_pack_json['meta']['title']
        self.write_pack_json(missing_title_pack_json)
        
        try:
            pack_header(self.pack_json_path, self.header_bin_path)
            assert False, "Should raise ConfigError for missing title"
        except ConfigError as e:
            assert "meta.title missing" in str(e)