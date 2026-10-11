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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
