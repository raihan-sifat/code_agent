import os
import json
from dataclasses import dataclass
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

@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False


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
        return self.execute_result(tool_name, arguments).content

    def execute_result(self, tool_name: str, arguments: Any) -> ToolResult:
        """Validate before touching files and report failures separately from content."""
        try:
            definition = next((tool["function"] for tool in TOOL_DEFINITIONS
                               if tool["function"]["name"] == tool_name), None)
            if definition is None:
                raise ValueError(f"Unknown tool {tool_name}")
            if not isinstance(arguments, dict):
                raise ValueError("Arguments must be a JSON object, not a list, scalar or null.")
            schema = definition["parameters"]
            for name in schema.get("required", []):
                if name not in arguments:
                    raise ValueError(f"Missing required '{name}' argument. Retry with all required fields: "
                                     + ", ".join(schema["required"]) + ".")
            for name in schema["properties"]:
                if name in arguments and not isinstance(arguments[name], str):
                    raise ValueError(f"'{name}' must be a string.")
            if "path" in arguments:
                self._validate_path(arguments["path"])

            if tool_name == "create_file":
                result = self._create_file(arguments["path"], arguments["content"])
            elif tool_name == "create_directory":
                result = self._create_directory(arguments["path"])
            elif tool_name == "read_file":
                result = self._read_file(arguments["path"])
            else:
                result = self._list_directory(arguments.get("path", "."))
            return ToolResult(result)
        except Exception as e:
            path = arguments.get("path") if isinstance(arguments, dict) else None
            target = f" for {path!r}" if isinstance(path, str) else ""
            return ToolResult(f"Error executing {tool_name}{target}: {e}", is_error=True)
            
    def _create_file(self, path: str, content: str) -> str:
        abs_path = self._validate_path(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.created_files.append(path)
        return f"Successfully created file: {path}"
            
    def _create_directory(self, path: str) -> str:
        abs_path = self._validate_path(path)
        os.makedirs(abs_path, exist_ok=True)
        return f"Successfully created directory: {path}"
            
    def _read_file(self, path: str) -> str:
        abs_path = self._validate_path(path)
        with open(abs_path, 'r', encoding='utf-8') as f:
            return f.read()
            
    def _list_directory(self, path: str) -> str:
        abs_path = self._validate_path(path)
        items = os.listdir(abs_path)
        if not items:
            return f"Directory {path} is empty."
        return json.dumps(items)
