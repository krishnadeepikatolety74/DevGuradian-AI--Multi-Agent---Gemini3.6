import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from services.ide_adapters.base import BaseIDEAdapter

class KiroAdapter(BaseIDEAdapter):
    key = "kiro"
    name = "Kiro"
    icon_svg = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path><circle cx="12" cy="10" r="3"></circle></svg>"""
    description = "Spec-driven autonomous AI development environment designed for structured architectural planning, execution, and verification."

    def detect(self, custom_path: Optional[str] = None) -> Dict[str, Any]:
        # 1. Custom path configured by user or environment variable
        configured_path = custom_path or os.environ.get("KIRO_PATH") or os.environ.get("KIRO_BIN")
        if configured_path and configured_path.strip():
            valid, msg_or_path = self.validate_executable(configured_path)
            if valid:
                return {
                    "status": "Configured",
                    "executable_path": msg_or_path,
                    "is_available": True,
                    "message": f"Configured Kiro executable verified: {msg_or_path}",
                    "instructions": ""
                }
            elif custom_path:
                return {
                    "status": "Not Configured",
                    "executable_path": None,
                    "is_available": False,
                    "message": f"Custom path invalid: {msg_or_path}",
                    "instructions": "Please provide the full path to kiro.exe or kiro.cmd on your system."
                }

        # 2. Check PATH
        for bin_name in ["kiro", "kiro.cmd", "kiro.exe", "kiro.bat"]:
            path_kiro = shutil.which(bin_name)
            if path_kiro:
                p = Path(path_kiro).resolve()
                if p.name.lower() in ("kiro.cmd", "kiro.bat"):
                    parent_exe = p.parent.parent / "Kiro.exe"
                    if parent_exe.exists():
                        path_kiro = str(parent_exe)
                return {
                    "status": "Installed",
                    "executable_path": str(path_kiro),
                    "is_available": True,
                    "message": f"Kiro detected automatically in system PATH: {path_kiro}",
                    "instructions": ""
                }

        # 3. Check standard OS install paths
        candidates = []
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("ProgramFiles", "")
            user_profile = os.environ.get("USERPROFILE", "")
            candidates = [
                Path(local_app_data) / "Programs" / "Kiro" / "Kiro.exe",
                Path(local_app_data) / "Programs" / "Kiro" / "bin" / "kiro.cmd",
                Path(prog_files) / "Kiro" / "Kiro.exe",
                Path(user_profile) / ".kiro" / "bin" / "kiro.exe",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/kiro"),
                Path("/usr/bin/kiro"),
                Path.home() / ".kiro" / "bin" / "kiro",
                Path("/Applications/Kiro.app/Contents/MacOS/Kiro"),
            ]

        for cand in candidates:
            if cand.exists():
                return {
                    "status": "Installed",
                    "executable_path": str(cand),
                    "is_available": True,
                    "message": f"Kiro detected at installation path: {cand}",
                    "instructions": ""
                }

        return {
            "status": "Not Detected",
            "executable_path": None,
            "is_available": False,
            "message": "Kiro was not detected in system PATH or standard directories.",
            "instructions": (
                "To use Kiro, install it from https://kiro.dev and ensure it is added to your PATH, "
                "or specify the executable path (e.g. C:\\Users\\<user>\\AppData\\Local\\Programs\\Kiro\\Kiro.exe) below."
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
            return True, f"Successfully launched Kiro with workspace: {target_dir}"
        except Exception as e:
            return False, f"Failed to launch Kiro process: {str(e)}"

    def get_manual_instructions(self, project_dir: Path) -> str:
        resolved = str(project_dir.resolve())
        return f"""### Manual Opening Instructions for Kiro:
1. Open terminal and run:
   kiro "{resolved}"
2. Or launch Kiro IDE, click **File &rarr; Open Project**, and select:
   {resolved}"""
