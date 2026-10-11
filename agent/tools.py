import os
import json
from typing import Dict, Any, List

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a file with specified content at a relative path within the output directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path where the file should be created."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content of the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory at a relative path within the output directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the directory to create."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read an existing file's content from the output directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the file to read."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a specified path within the output directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to list contents of. Defaults to '.' (root of output directory)."
                    }
                }
            }
        }
    }
]

class ToolExecutor:
    """Executes tool calls requested by the agent."""
    
    def __init__(self, output_dir: str):
        """Initialize with base output directory"""
        self.output_dir = os.path.abspath(output_dir)
        self.created_files: List[str] = []
        
        # Ensure output dir exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
    def _validate_path(self, rel_path: str) -> str:
        """Validates that a path is within the output directory (prevents path traversal).
        Returns the absolute path if valid, raises ValueError if not.
        """
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise ValueError("Path must be a non-empty string.")
        abs_path = os.path.abspath(os.path.join(self.output_dir, rel_path))
        base = os.path.normcase(self.output_dir)
        target = os.path.normcase(abs_path)
        # Require exact match or a real child (os.sep suffix check prevents the
        # 'C:\\out' matching 'C:\\out-evil' prefix bug).
        if target != base and not target.startswith(base + os.sep):
            raise ValueError(f"Path traversal detected: {rel_path}")
        return abs_path

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call. Returns result message string."""
        try:
            if tool_name == "create_file":
                return self._create_file(arguments.get("path"), arguments.get("content"))
            elif tool_name == "create_directory":
                return self._create_directory(arguments.get("path"))
            elif tool_name == "read_file":
                return self._read_file(arguments.get("path"))
            elif tool_name == "list_directory":
                return self._list_directory(arguments.get("path") or ".")
            else:
                return f"Error: Unknown tool {tool_name}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
            
    def _create_file(self, path: str, content: str) -> str:
        if not path or content is None:
            return "Error: Missing 'path' or 'content' arguments."
            
        try:
            abs_path = self._validate_path(path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.created_files.append(path)
            return f"Successfully created file: {path}"
        except Exception as e:
            return f"Failed to create file {path}: {str(e)}"
            
    def _create_directory(self, path: str) -> str:
        if not path:
            return "Error: Missing 'path' argument."
            
        try:
            abs_path = self._validate_path(path)
            os.makedirs(abs_path, exist_ok=True)
            return f"Successfully created directory: {path}"
        except Exception as e:
            return f"Failed to create directory {path}: {str(e)}"
            
    def _read_file(self, path: str) -> str:
        if not path:
            return "Error: Missing 'path' argument."
            
        try:
            abs_path = self._validate_path(path)
            if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
                return f"Error: File not found at {path}"
                
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Failed to read file {path}: {str(e)}"
            
    def _list_directory(self, path: str) -> str:
        try:
            abs_path = self._validate_path(path)
            if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
                return f"Error: Directory not found at {path}"
                
            items = os.listdir(abs_path)
            if not items:
                return f"Directory {path} is empty."
            return json.dumps(items)
        except Exception as e:
            return f"Failed to list directory {path}: {str(e)}"
