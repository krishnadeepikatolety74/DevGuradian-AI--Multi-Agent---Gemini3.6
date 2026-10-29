import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from services.ide_adapters.base import BaseIDEAdapter

class VSCodeAdapter(BaseIDEAdapter):
    key = "vscode"
    name = "Visual Studio Code"
    icon_svg = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3l5 3v12l-5 3-7-6.5L3 18l-1-1V7l1-1 6 3.5L16 3z"></path><path d="M16 3v18"></path><path d="M9 8.5l7 6.5"></path><path d="M9 15.5l7-6.5"></path></svg>"""
    description = "Industry standard, highly extensible code editor with integrated terminal, debugging, and extensions."

    def detect(self, custom_path: Optional[str] = None) -> Dict[str, Any]:
        # 1. Custom path configured by user
        if custom_path and custom_path.strip():
            valid, msg_or_path = self.validate_executable(custom_path)
            if valid:
                return {
                    "status": "Configured",
                    "executable_path": msg_or_path,
                    "is_available": True,
                    "message": f"Configured custom executable verified: {msg_or_path}",
                    "instructions": ""
                }
            else:
                return {
                    "status": "Not Configured",
                    "executable_path": None,
                    "is_available": False,
                    "message": f"Custom path invalid: {msg_or_path}",
                    "instructions": "Please provide the full path to code.exe or code.cmd on your system."
                }

        # 2. Check PATH
        path_code = shutil.which("code") or shutil.which("code.cmd")
        if path_code:
            # Check if underlying Code.exe exists next to bin/
            p = Path(path_code).resolve()
            if p.name.lower() in ("code.cmd", "code.bat"):
                parent_exe = p.parent.parent / "Code.exe"
                if parent_exe.exists():
                    path_code = str(parent_exe)
            return {
                "status": "Installed",
                "executable_path": str(path_code),
                "is_available": True,
                "message": f"VS Code detected automatically in system PATH: {path_code}",
                "instructions": ""
            }

        # 3. Check standard OS install paths
        candidates = []
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("ProgramFiles", "")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", "")
            candidates = [
                Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe",
                Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
                Path(prog_files) / "Microsoft VS Code" / "Code.exe",
                Path(prog_files_x86) / "Microsoft VS Code" / "Code.exe",
            ]
        else:
            candidates = [
                Path("/usr/bin/code"),
                Path("/usr/local/bin/code"),
                Path("/snap/bin/code"),
                Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
            ]

        for cand in candidates:
            if cand.exists():
                return {
                    "status": "Installed",
                    "executable_path": str(cand),
                    "is_available": True,
                    "message": f"VS Code detected at standard installation path: {cand}",
                    "instructions": ""
                }

        return {
            "status": "Not Detected",
            "executable_path": None,
            "is_available": False,
            "message": "Visual Studio Code was not detected in system PATH or standard directories.",
            "instructions": (
                "To use VS Code, install it from https://code.visualstudio.com/ and ensure 'Add to PATH' is checked, "
                "or specify the executable path (e.g. C:\\Users\\<user>\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe) below."
            )
        }

    def launch(self, project_dir: Path, custom_path: Optional[str] = None) -> Tuple[bool, str]:
        det = self.detect(custom_path)
        if not det["is_available"] or not det["executable_path"]:
            return False, det["message"]

        exe_path = det["executable_path"]
        target_dir = str(project_dir.resolve())

        try:
            # Safe subprocess execution without running arbitrary shell
            if exe_path.lower().endswith((".cmd", ".bat")):
                # On Windows, invoke cmd /c with safe argument list
                subprocess.Popen(["cmd.exe", "/c", exe_path, target_dir], close_fds=True)
            else:
                subprocess.Popen([exe_path, target_dir], close_fds=True)
            return True, f"Successfully launched Visual Studio Code with workspace: {target_dir}"
        except Exception as e:
            return False, f"Failed to launch Visual Studio Code process: {str(e)}"

    def get_manual_instructions(self, project_dir: Path) -> str:
        resolved = str(project_dir.resolve())
        return f"""### Manual Opening Instructions for Visual Studio Code:
1. Open your terminal or Command Prompt.
2. Run the command:
   code "{resolved}"
3. Alternatively, launch VS Code manually, click **File &rarr; Open Folder...**, and select:
   {resolved}"""
