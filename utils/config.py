import os
import json
import threading
from pathlib import Path
from typing import Dict, Any

class Config:
    """Manages application settings and configuration."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.config_dir = Path.home() / ".codeagent"
        self.config_file = self.config_dir / "config.json"
        
        self._config_data: Dict[str, Any] = {
            "api_key": "",
            "model": "deepseek-chat",
            "last_input_dir": "",
            "last_output_dir": "",
            "theme": "dark"
        }
        
        self._ensure_config_dir()
        self.load()
        
    def _ensure_config_dir(self):
        with self._lock:
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True, exist_ok=True)
                
    def load(self) -> None:
        """Load configuration from file."""
        with self._lock:
            if self.config_file.exists():
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._config_data.update(data)
                except (json.JSONDecodeError, IOError):
                    pass
                    
    def save(self) -> None:
        """Save configuration to file."""
        with self._lock:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4)
                
    @property
    def api_key(self) -> str:
        with self._lock:
            return self._config_data.get("api_key", "")
            
    @api_key.setter
    def api_key(self, value: str):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("API key must be a non-empty string.")
        with self._lock:
            self._config_data["api_key"] = value.strip()
            
    @property
    def model(self) -> str:
        with self._lock:
            return self._config_data.get("model", "deepseek-chat")
            
    @model.setter
    def model(self, value: str):
        with self._lock:
            self._config_data["model"] = value
            
    @property
    def last_input_dir(self) -> str:
        with self._lock:
            return self._config_data.get("last_input_dir", "")
            
    @last_input_dir.setter
    def last_input_dir(self, value: str):
        with self._lock:
            self._config_data["last_input_dir"] = value
            
    @property
    def last_output_dir(self) -> str:
        with self._lock:
            return self._config_data.get("last_output_dir", "")
            
    @last_output_dir.setter
    def last_output_dir(self, value: str):
        with self._lock:
            self._config_data["last_output_dir"] = value
            
    @property
    def theme(self) -> str:
        with self._lock:
            return self._config_data.get("theme", "dark")
            
    @theme.setter
    def theme(self, value: str):
        with self._lock:
            self._config_data["theme"] = value
