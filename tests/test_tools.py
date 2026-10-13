"""Tests for the ToolExecutor."""

import os
import json
import pytest
import tempfile
from agent.tools import ToolExecutor, TOOL_DEFINITIONS


class TestToolDefinitions:
    """Test tool definitions are properly formatted."""
    
    def test_tool_definitions_not_empty(self):
        assert len(TOOL_DEFINITIONS) > 0
        
    def test_tool_definitions_format(self):
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            
    def test_required_tools_present(self):
        names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        assert "create_file" in names
        assert "create_directory" in names
        assert "read_file" in names
        assert "list_directory" in names


class TestToolExecutor:
    """Tests for ToolExecutor."""
    
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.executor = ToolExecutor(self.tmpdir)
        
    def test_create_file(self):
        result = self.executor.execute("create_file", {
            "path": "test.txt",
            "content": "Hello World"
        })
        assert "Successfully" in result
        assert os.path.exists(os.path.join(self.tmpdir, "test.txt"))
        
        with open(os.path.join(self.tmpdir, "test.txt"), 'r') as f:
            assert f.read() == "Hello World"
    
    def test_create_file_nested(self):
        result = self.executor.execute("create_file", {
            "path": "src/utils/helper.py",
            "content": "# helper module"
        })
        assert "Successfully" in result
        assert os.path.exists(os.path.join(self.tmpdir, "src", "utils", "helper.py"))
    
    def test_create_directory(self):
        result = self.executor.execute("create_directory", {"path": "src/models"})
        assert "Successfully" in result
        assert os.path.isdir(os.path.join(self.tmpdir, "src", "models"))
        
    def test_read_file(self):
        # Create a file first
        filepath = os.path.join(self.tmpdir, "read_test.txt")
        with open(filepath, 'w') as f:
            f.write("test content")
        
        result = self.executor.execute("read_file", {"path": "read_test.txt"})
        assert result == "test content"
    
    def test_read_nonexistent_file(self):
        result = self.executor.execute("read_file", {"path": "nonexistent.txt"})
        assert "Error" in result
    
    def test_list_directory(self):
        # Create some files
        self.executor.execute("create_file", {"path": "a.txt", "content": "a"})
        self.executor.execute("create_file", {"path": "b.txt", "content": "b"})
        
        result = self.executor.execute("list_directory", {"path": "."})
        items = json.loads(result)
        assert "a.txt" in items
        assert "b.txt" in items
    
    def test_path_traversal_blocked(self):
        result = self.executor.execute("create_file", {
            "path": "../../etc/passwd",
            "content": "malicious"
        })
        assert "Error" in result or "traversal" in result.lower()
    
    def test_unknown_tool(self):
        result = self.executor.execute("unknown_tool", {})
        assert "Error" in result
        
    def test_created_files_tracking(self):
        self.executor.execute("create_file", {"path": "f1.txt", "content": "1"})
        self.executor.execute("create_file", {"path": "f2.txt", "content": "2"})
        assert "f1.txt" in self.executor.created_files
        assert "f2.txt" in self.executor.created_files

    @pytest.mark.parametrize("content", [None, 1, [], {}, False])
    def test_invalid_content_does_not_damage_existing_file(self, content):
        self.executor.execute("create_file", {"path": "game.py", "content": "original"})
        self.executor.created_files.clear()
        result = self.executor.execute_result("create_file", {"path": "game.py", "content": content})
        assert result.is_error
        assert "'content' must be a string" in result.content
        with open(os.path.join(self.tmpdir, "game.py")) as f:
            assert f.read() == "original"
        assert self.executor.created_files == []

    def test_missing_content_reports_target_and_required_field(self):
        result = self.executor.execute_result("create_file", {"path": "ui_scenes.py"})
        assert result.is_error
        assert "ui_scenes.py" in result.content and "Missing required 'content'" in result.content
        assert not os.path.exists(os.path.join(self.tmpdir, "ui_scenes.py"))

    def test_empty_content_is_allowed_for_package_marker(self):
        result = self.executor.execute_result("create_file", {"path": "__init__.py", "content": ""})
        assert not result.is_error
        assert os.path.isfile(os.path.join(self.tmpdir, "__init__.py"))

    @pytest.mark.parametrize("path", [None, 7, [], "", "   "])
    def test_invalid_path_has_no_side_effects(self, path):
        result = self.executor.execute_result("create_file", {"path": path, "content": "text"})
        assert result.is_error
        assert os.listdir(self.tmpdir) == []

    def test_list_directory_without_path_still_defaults_to_root(self):
        self.executor.execute("create_file", {"path": "a.txt", "content": "a"})
        result = self.executor.execute_result("list_directory", {})
        assert not result.is_error
        assert json.loads(result.content) == ["a.txt"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
