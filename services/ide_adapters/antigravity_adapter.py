import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from services.ide_adapters.base import BaseIDEAdapter

class AntigravityAdapter(BaseIDEAdapter):
    key = "antigravity"
    name = "Antigravity"
    icon_svg = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>"""
    description = "Google DeepMind's advanced agentic coding environment with autonomous subagents, deep repository knowledge, and live browser testing."

    def detect(self, custom_path: Optional[str] = None) -> Dict[str, Any]:
        # 1. Custom path configured by user or environment variable
        configured_path = custom_path or os.environ.get("ANTIGRAVITY_PATH") or os.environ.get("ANTIGRAVITY_BIN")
        if configured_path and configured_path.strip():
            valid, msg_or_path = self.validate_executable(configured_path)
            if valid:
                return {
                    "status": "Configured",
                    "executable_path": msg_or_path,
                    "is_available": True,
                    "message": f"Configured Antigravity executable verified: {msg_or_path}",
                    "instructions": ""
                }
            elif custom_path:
                return {
                    "status": "Not Configured",
                    "executable_path": None,
                    "is_available": False,
                    "message": f"Custom path invalid: {msg_or_path}",
                    "instructions": "Please provide the full path to agy or antigravity.exe on your system."
                }

        # 2. Check PATH for agy CLI or antigravity
        for bin_name in ["agy", "agy.cmd", "antigravity", "antigravity.exe", "antigravity.cmd"]:
            found = shutil.which(bin_name)
            if found:
                return {
                    "status": "Installed",
                    "executable_path": str(found),
                    "is_available": True,
                    "message": f"Antigravity CLI detected in system PATH: {found}",
                    "instructions": ""
                }

        # 3. Check standard locations
        candidates = []
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("ProgramFiles", "")
            user_profile = os.environ.get("USERPROFILE", "")
            candidates = [
                Path(local_app_data) / "Programs" / "Antigravity" / "Antigravity.exe",
                Path(local_app_data) / "Programs" / "Antigravity" / "bin" / "agy.cmd",
                Path(local_app_data) / "Programs" / "Google" / "Antigravity" / "Antigravity.exe",
                Path(user_profile) / ".gemini" / "antigravity-ide" / "antigravity.exe",
                Path(prog_files) / "Antigravity" / "Antigravity.exe",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/agy"),
                Path("/usr/bin/agy"),
                Path.home() / ".local" / "bin" / "agy",
                Path("/Applications/Antigravity.app/Contents/MacOS/Antigravity"),
            ]

        for cand in candidates:
            if cand.exists():
                return {
                    "status": "Installed",
                    "executable_path": str(cand),
                    "is_available": True,
                    "message": f"Antigravity detected at installation path: {cand}",
                    "instructions": ""
                }

        return {
            "status": "Not Detected",
            "executable_path": None,
            "is_available": False,
            "message": "Antigravity was not detected in system PATH or standard directories.",
            "instructions": (
                "To use Antigravity, ensure the 'agy' CLI is installed and available in your PATH, "
                "or specify the path to your Antigravity launcher/executable in Project Settings."
            )
        }

    def launch(self, project_dir: Path, custom_path: Optional[str] = None) -> Tuple[bool, str]:
        det = self.detect(custom_path)
        if not det["is_available"] or not det["executable_path"]:
            return False, det["message"]

        exe_path = det["executable_path"]
        target_dir = str(project_dir.resolve())

        try:
            if exe_path.lower().endswith((".cmd", ".bat")):
                subprocess.Popen(["cmd.exe", "/c", exe_path, target_dir], close_fds=True)
            else:
                subprocess.Popen([exe_path, target_dir], close_fds=True)
            return True, f"Successfully launched Antigravity with workspace: {target_dir}"
        except Exception as e:
            return False, f"Failed to launch Antigravity process: {str(e)}"

    def get_manual_instructions(self, project_dir: Path) -> str:
        resolved = str(project_dir.resolve())
        return f"""### Manual Opening Instructions for Antigravity:
1. Open terminal and run:
   agy "{resolved}"
2. Or launch Antigravity IDE, select **Open Workspace**, and navigate to:
   {resolved}"""
