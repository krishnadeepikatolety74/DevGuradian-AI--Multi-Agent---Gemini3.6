"""
DevGuardian AI — Code Screenshot Service
Generates crisp, high-resolution, syntax-highlighted code screenshot images for documentation.
Embeds an editor window frame with macOS window buttons, active filename tab, line numbers,
VS Code / One Dark syntax colors, and 300 DPI print quality.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from pygments.lexers import (
    PythonLexer, SqlLexer, HtmlLexer, JsonLexer, BashLexer, IniLexer, get_lexer_by_name
)
from pygments import lex
from pygments.token import Token

ROOT_DIR = Path(__file__).resolve().parent.parent

# VS Code / One Dark Theme Token Colors
TOKEN_COLORS = {
    Token.Keyword: (86, 156, 214),            # #569CD6 blue
    Token.Keyword.Constant: (86, 156, 214),
    Token.Keyword.Declaration: (86, 156, 214),
    Token.Keyword.Namespace: (197, 134, 192),   # #C586C0 purple
    Token.Name.Class: (78, 201, 176),         # #4EC9B0 teal
    Token.Name.Function: (220, 220, 170),     # #DCDCAA light yellow
    Token.Name.Decorator: (220, 220, 170),
    Token.Name.Builtin: (78, 201, 176),
    Token.String: (206, 145, 120),            # #CE9178 orange-brown
    Token.String.Doc: (106, 153, 85),         # #6A9955 green docstring
    Token.Number: (181, 206, 168),            # #B5CEA8 light green
    Token.Comment: (106, 153, 85),            # #6A9955 green comment
    Token.Operator: (212, 212, 212),
    Token.Punctuation: (212, 212, 212),
    Token.Generic: (212, 212, 212),
    Token.Text: (212, 212, 212),              # default text
}

def get_lexer_for_filename(filename: str, fallback_lang: str = "python"):
    """Select the most suitable Pygments lexer based on filename extension."""
    ext = os.path.splitext(filename)[1].lower()
    ext_map = {
        ".py": PythonLexer,
        ".sql": SqlLexer,
        ".html": HtmlLexer,
        ".jinja": HtmlLexer,
        ".jinja2": HtmlLexer,
        ".json": JsonLexer,
        ".sh": BashLexer,
        ".env": IniLexer,
        ".ini": IniLexer,
        ".txt": PythonLexer,
    }
    lexer_cls = ext_map.get(ext)
    if lexer_cls:
        return lexer_cls()
    try:
        return get_lexer_by_name(fallback_lang)
    except Exception:
        return PythonLexer()

def redact_code_secrets(text: str) -> str:
    """Detect and redact API keys, tokens, and passwords with safe placeholders."""
    if not text:
        return ""
    # Google API Key
    text = re.sub(r'AIzaSy[0-9A-Za-z-_]{33}', 'YOUR_GEMINI_API_KEY_HERE', text)
    # xAI API Key
    text = re.sub(r'xai-[0-9A-Za-z-_]{20,}', 'YOUR_XAI_API_KEY_HERE', text)
    # OpenAI API Key
    text = re.sub(r'sk-[0-9A-Za-z-_]{20,}', 'YOUR_OPENAI_API_KEY_HERE', text)
    # Anthropic API Key
    text = re.sub(r'sk-ant-[0-9A-Za-z-_]{20,}', 'YOUR_ANTHROPIC_API_KEY_HERE', text)
    # Ngrok Authtoken
    text = re.sub(r'(?:ngrok\.set_auth_token|add_authtoken|authtoken)\s*\(\s*["\'](?!YOUR_)[^"\']+["\']\s*\)', 'ngrok.set_auth_token("YOUR_NGROK_AUTHTOKEN")', text, flags=re.IGNORECASE)
    text = re.sub(r'((?:NGROK_AUTHTOKEN|AUTHTOKEN)\s*=\s*["\']?)(?!YOUR_)[a-zA-Z0-9_\-\.]{20,}(["\']?)', r'\1YOUR_NGROK_AUTHTOKEN\2', text, flags=re.IGNORECASE)
    # Generic secret assignments like secret_key = "..."
    text = re.sub(r'((?:api_key|secret_key|password|token)\s*=\s*["\'])(?!your_|YOUR_)[^"\']+(["\'])', r'\1YOUR_SECRET_KEY_HERE\2', text, flags=re.IGNORECASE)
    return text

def render_code_screenshot(
    code_text: str,
    filename: str,
    section_title: str,
    output_path: str,
    lang: str = "python",
    max_lines: int = 40,
    start_line_num: int = 1,
    part_info: Optional[str] = None
) -> str:
    """
    Renders high-resolution, syntax-highlighted code screenshot with an editor window frame,
    window controls, filename tab, line numbers, and crisp font rendering.
    """
    cleaned_code = redact_code_secrets(code_text)
    raw_lines = cleaned_code.expandtabs(4).splitlines()
    if not raw_lines:
        raw_lines = ["# No code content available"]

    # Limit to reasonable length to keep image crisp and readable
    lines = raw_lines[:max_lines]
    if len(raw_lines) > max_lines:
        lines.append(f"# ... [{len(raw_lines) - max_lines} additional lines in source file] ...")

    lexer = get_lexer_for_filename(filename, lang)

    # High resolution font sizing (rendered at 2x scaling for 300 DPI output)
    font_size = 26
    header_font_size = 20
    
    font_candidates = [
        "C:\\Windows\\Fonts\\consola.ttf",
        "C:\\Windows\\Fonts\\consolab.ttf",
        "C:\\Windows\\Fonts\\cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    ]
    header_candidates = [
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    code_font = None
    for fc in font_candidates:
        if os.path.exists(fc):
            try:
                code_font = ImageFont.truetype(fc, font_size)
                break
            except Exception:
                pass
    if not code_font:
        code_font = ImageFont.load_default()

    header_font = None
    for hc in header_candidates:
        if os.path.exists(hc):
            try:
                header_font = ImageFont.truetype(hc, header_font_size)
                break
            except Exception:
                pass
    if not header_font:
        header_font = ImageFont.load_default()

    line_height = int(font_size * 1.52)
    line_count = len(lines)

    # Measure width accurately
    dummy_img = Image.new("RGB", (100, 100))
    dummy_draw = ImageDraw.Draw(dummy_img)

    longest_line = max(lines, key=len) if lines else ""
    line_width = int(dummy_draw.textlength(longest_line + "        ", font=code_font))

    max_line_label = str(start_line_num + line_count + 1)
    gutter_width = int(dummy_draw.textlength(f"{max_line_label}  ", font=code_font)) + 32
    content_width = max(line_width + gutter_width + 60, 1100)

    header_height = 60
    padding_bottom = 28
    content_height = header_height + (line_count * line_height) + padding_bottom

    # Editor Theme Colors (VS Code Dark Modern / One Dark)
    bg_color = (30, 30, 30)            # #1E1E1E
    header_bg = (37, 37, 38)           # #252526
    gutter_text_color = (133, 133, 133) # line numbers
    border_color = (68, 68, 68)        # #444444
    tab_active_bg = (30, 30, 30)
    tab_text_color = (255, 255, 255)

    img = Image.new("RGB", (content_width, content_height), bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Title bar
    draw.rectangle([(0, 0), (content_width, header_height)], fill=header_bg)
    draw.line([(0, header_height), (content_width, header_height)], fill=border_color, width=1)

    # Window traffic light buttons (macOS style)
    dot_y = header_height // 2
    draw.ellipse([(18, dot_y - 7), (32, dot_y + 7)], fill=(255, 95, 86))   # Close (Red)
    draw.ellipse([(40, dot_y - 7), (54, dot_y + 7)], fill=(255, 189, 46))  # Minimize (Yellow)
    draw.ellipse([(62, dot_y - 7), (76, dot_y + 7)], fill=(39, 201, 63))   # Expand (Green)

    # Active Editor Tab
    tab_text = f"  {filename} {part_info}  " if part_info else f"  {filename}  "
    tab_width = int(draw.textlength(tab_text, font=header_font)) + 34
    tab_x0 = 98
    tab_x1 = tab_x0 + tab_width
    draw.rectangle([(tab_x0, 8), (tab_x1, header_height)], fill=tab_active_bg)
    draw.line([(tab_x0, 8), (tab_x0, header_height)], fill=border_color, width=1)
    draw.line([(tab_x1, 8), (tab_x1, header_height)], fill=border_color, width=1)
    draw.text((tab_x0 + 16, 18), tab_text, fill=tab_text_color, font=header_font)

    # Subtitle / Section description in title bar
    if section_title:
        sub_text = f"// {section_title}"
        draw.text((tab_x1 + 24, 18), sub_text, fill=(145, 145, 145), font=header_font)

    # Line numbers separator line
    draw.line([(gutter_width, header_height), (gutter_width, content_height)], fill=(45, 45, 45), width=1)

    # 2. Render code lines with line numbers and syntax highlighting
    y = header_height + 14
    for idx, line in enumerate(lines, start=start_line_num):
        # Line number
        line_num_str = str(idx)
        num_len = draw.textlength(line_num_str, font=code_font)
        draw.text((gutter_width - num_len - 14, y), line_num_str, fill=gutter_text_color, font=code_font)

        # Tokenized line syntax highlighting
        clean_line = line.rstrip("\r\n")
        x = gutter_width + 20
        tokens = lex(clean_line, lexer)
        for ttype, tvalue in tokens:
            tval_clean = tvalue.replace("\r", "").replace("\n", "")
            if not tval_clean:
                continue

            # Token color resolution
            color = TOKEN_COLORS.get(ttype)
            if not color:
                for parent_token in TOKEN_COLORS:
                    if ttype in parent_token:
                        color = TOKEN_COLORS[parent_token]
                        break
            if not color:
                color = (212, 212, 212)

            draw.text((x, y), tval_clean, fill=color, font=code_font)
            x += int(draw.textlength(tval_clean, font=code_font))

        y += line_height

    # Outer border
    draw.rectangle([(0, 0), (content_width - 1, content_height - 1)], outline=border_color, width=1)

    # Save to file
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), format="PNG", dpi=(300, 300))
    return str(out.resolve())

def render_code_screenshots_multi(
    code_text: str,
    filename: str,
    section_title: str,
    output_base_path: str,
    lang: str = "python",
    max_lines_per_image: int = 40
) -> List[str]:
    """
    Renders code into one or more high-resolution screenshot images.
    If the code exceeds max_lines_per_image (+5 buffer), cleanly splits into multiple
    sequential images with continuing line numbers and '(Part X of Y)' indicators,
    preventing any unreadable shrinking or arbitrary line drops.
    """
    cleaned_code = redact_code_secrets(code_text)
    raw_lines = cleaned_code.expandtabs(4).splitlines()
    if not raw_lines:
        raw_lines = ["# No code content available"]

    if len(raw_lines) <= max_lines_per_image + 5:
        p = render_code_screenshot(
            code_text=cleaned_code,
            filename=filename,
            section_title=section_title,
            output_path=output_base_path,
            lang=lang,
            max_lines=max_lines_per_image + 5,
            start_line_num=1
        )
        return [p]

    # Split into chunks of max_lines_per_image
    chunks = []
    for i in range(0, len(raw_lines), max_lines_per_image):
        chunks.append(raw_lines[i:i + max_lines_per_image])

    total_parts = len(chunks)
    output_paths = []
    base_dir = os.path.dirname(output_base_path)
    base_name, base_ext = os.path.splitext(os.path.basename(output_base_path))

    for idx, chunk in enumerate(chunks, start=1):
        chunk_text = "\n".join(chunk)
        start_ln = (idx - 1) * max_lines_per_image + 1
        part_str = f"(Part {idx} of {total_parts})"
        part_path = os.path.join(base_dir, f"{base_name}_part{idx}{base_ext}")
        rendered = render_code_screenshot(
            code_text=chunk_text,
            filename=filename,
            section_title=f"{section_title} {part_str}",
            output_path=part_path,
            lang=lang,
            max_lines=max_lines_per_image + 5,
            start_line_num=start_ln,
            part_info=part_str
        )
        output_paths.append(rendered)

    return output_paths

def generate_project_code_screenshots(
    project_id: str,
    workspace_path: Optional[str],
    code_snippets: Dict[str, Any],
    target_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate all required high-resolution code screenshots for a project and
    return dictionary mapping snippet keys to local image paths.
    """
    if target_dir:
        out_base = Path(target_dir)
    elif workspace_path and os.path.exists(workspace_path):
        out_base = Path(workspace_path) / "documentation" / "assets" / "code"
    else:
        out_base = ROOT_DIR / "generated_projects" / project_id / "documentation" / "assets" / "code"

    out_base.mkdir(parents=True, exist_ok=True)
    results = {}

    # Define the core code sections to capture
    sections_map = [
        ("app_entry", "app.py", "Application Initialization & Configuration", "python"),
        ("routing", "app.py", "Route Handlers & Endpoint Dispatching", "python"),
        ("business_logic", "services.py", "Domain Business Rules & Evaluation Engine", "python"),
        ("database_models", "model.py", "Persistence Schema & Data Access Layer", "python"),
        ("ai_integration", "services.py", "AI Provider Client & Autonomous Workflow", "python"),
        ("tests", "test_app.py", "Automated Regression Test Suite", "python"),
        ("frontend_template", "templates/dashboard.html", "Responsive SaaS Presentation Interface", "html"),
        ("env_config", ".env.example", "Environment & API Key Configuration Template", "ini"),
        ("smoke_test", "verify_engine.py", "Service Verification & Health Smoke Test", "python"),
        ("dependencies", "requirements.txt", "Pinned Dependencies & Runtime Specification", "python"),
        ("config", "config.py", "Application Environment Configuration", "python"),
        ("run_public", "run_public.py", "Public Deployment Script via Ngrok", "python"),
        ("exec_commands", "terminal_commands.sh", "Local Execution & Verification Commands", "sh"),
    ]

    for key, filename, title, lang in sections_map:
        code_text = code_snippets.get(key)
        if not code_text:
            continue

        out_file = out_base / f"{key}_code.png"
        try:
            rendered_paths = render_code_screenshots_multi(
                code_text=code_text,
                filename=filename,
                section_title=title,
                output_base_path=str(out_file),
                lang=lang,
                max_lines_per_image=40
            )
            if rendered_paths:
                results[key] = rendered_paths[0]
        except Exception as e:
            print(f"[CodeScreenshotService] Error rendering {key}: {e}")

    return results
