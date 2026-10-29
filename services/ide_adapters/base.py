import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

class BaseIDEAdapter:
    """Abstract base adapter for development environment integration."""
    key: str = "base"
    name: str = "Base IDE"
    icon_svg: str = ""
    description: str = ""

    @property
    def icon(self) -> str:
        return self.icon_svg

    def detect(self, custom_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect whether this IDE is installed and available.
        States: Installed, Ready, Configured, Not Detected, Not Configured, Launch Failed
        """
        raise NotImplementedError

    def launch(self, project_dir: Path, custom_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Launch the IDE opening the generated project directory.
        Returns (success: bool, message: str).
        """
        raise NotImplementedError

    def get_manual_instructions(self, project_dir: Path) -> str:
        """Provide clear manual instructions when launching fails or IDE is not detected."""
        raise NotImplementedError

    def validate_executable(self, path_str: str) -> Tuple[bool, str]:
        """Validate if a custom executable path exists and is an executable file."""
        if not path_str or not path_str.strip():
            return False, "Executable path cannot be empty."
        
        clean_path = path_str.strip().strip('"').strip("'")
        target = Path(clean_path).resolve()
        
        if not target.exists():
            return False, f"File does not exist at specified path: {target}"
        if not target.is_file():
            return False, f"Specified path is a directory, not an executable file: {target}"
            
        # Basic extension check on Windows
        if os.name == "nt":
            valid_exts = {".exe", ".cmd", ".bat", ".ps1"}
            if target.suffix.lower() not in valid_exts:
                return False, f"File extension '{target.suffix}' is not a recognized executable format ({', '.join(valid_exts)})."
                
        return True, str(target)
