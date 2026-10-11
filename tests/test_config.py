"""Tests for the Config manager using standard unittest."""

import os
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.tmpdir, "config.json")
        
    def _make_config(self):
        config = Config.__new__(Config)
        import threading
        config._lock = threading.Lock()
        config.config_dir = Path(self.tmpdir)
        config.config_file = Path(self.config_file)
        config._config_data = {
            "api_key": "",
            "model": "deepseek-chat",
            "last_input_dir": "",
            "last_output_dir": "",
            "theme": "dark"
        }
        return config
    
    def test_default_values(self):
        config = self._make_config()
        self.assertEqual(config.api_key, "")
        self.assertEqual(config.model, "deepseek-chat")
        self.assertEqual(config.theme, "dark")
    
    def test_set_api_key(self):
        config = self._make_config()
        config.api_key = "sk-test-key-123"
        self.assertEqual(config.api_key, "sk-test-key-123")
    
    def test_set_empty_api_key_raises(self):
        config = self._make_config()
        with self.assertRaises(ValueError):
            config.api_key = ""
    
    def test_set_model(self):
        config = self._make_config()
        config.model = "deepseek-reasoner"
        self.assertEqual(config.model, "deepseek-reasoner")
    
    def test_save_and_load(self):
        config = self._make_config()
        config.api_key = "sk-save-test"
        config.model = "deepseek-reasoner"
        config.save()
        
        self.assertTrue(os.path.exists(self.config_file))
        
        config2 = self._make_config()
        config2.load()
        self.assertEqual(config2.api_key, "sk-save-test")
        self.assertEqual(config2.model, "deepseek-reasoner")
    
    def test_load_nonexistent_file(self):
        config = self._make_config()
        config.load()
        self.assertEqual(config.api_key, "")
    
    def test_theme_property(self):
        config = self._make_config()
        config.theme = "light"
        self.assertEqual(config.theme, "light")
    
    def test_last_dirs(self):
        config = self._make_config()
        config.last_input_dir = "/some/input/path"
        config.last_output_dir = "/some/output/path"
        self.assertEqual(config.last_input_dir, "/some/input/path")
        self.assertEqual(config.last_output_dir, "/some/output/path")


if __name__ == "__main__":
    unittest.main()
