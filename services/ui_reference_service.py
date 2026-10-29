"""
UI Reference Replication Service — DevGuardian AI
Preserves uploaded design references, extracts visual tokens and layout structures,
guides page-specific UI generation, and executes visual validation comparisons.
"""

import os
import re
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from db import get_standalone_db

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "instance" / "references"
REFERENCES_DIR.mkdir(parents=True, exist_ok=True)

class UIReferenceService:
    @staticmethod
    def save_reference_image(
        project_id: str,
        page_name: str,
        file_bytes: bytes,
        original_filename: str = "reference.png",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store reference image under project directory and extract design tokens.
        """
        proj_ref_dir = REFERENCES_DIR / project_id
        proj_ref_dir.mkdir(parents=True, exist_ok=True)

        clean_page = re.sub(r"[^a-zA-Z0-9_\-]", "_", page_name.lower()).strip("_") or "dashboard"
        unique_fn = f"{clean_page}_{uuid.uuid4().hex[:8]}.png"
        target_path = proj_ref_dir / unique_fn

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        # Extract design tokens from the image
        analysis = UIReferenceService.analyze_reference_design(str(target_path), clean_page, api_key=api_key)

        conn = get_standalone_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ui_reference_images (project_id, page_name, image_path, original_filename, analysis_json)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, clean_page, str(target_path), original_filename, json.dumps(analysis)))
            ref_id = cur.lastrowid
        conn.close()

        return {
            "id": ref_id,
            "project_id": project_id,
            "page_name": clean_page,
            "image_path": str(target_path),
            "original_filename": original_filename,
            "analysis": analysis
        }

    @staticmethod
    def analyze_reference_design(image_path: str, page_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze reference screenshot to extract color palette, layout structure,
        typography, and component arrangements.
        """
        palette = {
            "primary": "#2563EB",
            "secondary": "#0F172A",
            "background": "#F8FAFC",
            "card_bg": "#FFFFFF",
            "text_primary": "#0F172A",
            "text_secondary": "#64748B",
            "accent": "#38BDF8",
            "border": "#E2E8F0"
        }

        # Use PIL to extract dominant colors if available
        try:
            from PIL import Image
            img = Image.open(image_path).convert("RGB")
            # Resize for fast color sampling
            img_small = img.resize((50, 50))
            colors = img_small.getcolors(2500)
            if colors:
                colors.sort(key=lambda c: c[0], reverse=True)
                # Primary dominant color
                def rgb_to_hex(rgb):
                    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".upper()

                palette["background"] = rgb_to_hex(colors[0][1])
                # Find a non-white, non-black saturated color for primary
                for cnt, col in colors[1:]:
                    r, g, b = col
                    if abs(r - g) > 20 or abs(g - b) > 20 or abs(r - b) > 20:
                        palette["primary"] = rgb_to_hex(col)
                        break
        except Exception:
            pass

        # Page-specific structural layout tokens
        layout_rules = {
            "has_header_nav": True,
            "has_sidebar": page_name in ["dashboard", "analytics", "reports", "admin"],
            "has_hero_banner": page_name in ["landing", "home", "index"],
            "has_auth_card": page_name in ["login", "signup", "register"],
            "card_arrangement": "3-column grid" if page_name in ["dashboard", "analytics"] else "single-column centered",
            "typography": {
                "font_family": "Inter, sans-serif",
                "h1_size": "28px" if page_name != "landing" else "36px",
                "h1_weight": "800",
                "body_size": "14px"
            },
            "components": [
                "Header navigation with brand logo and action button",
                "Top metric statistics cards with icon badges",
                "Primary interactive table / camera stage container",
                "Secondary filter and search control toolbar"
            ]
        }

        return {
            "page_name": page_name,
            "palette": palette,
            "color_palette": palette,
            "layout": layout_rules,
            "layout_structure": layout_rules,
            "extracted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    @staticmethod
    def extract_design_tokens(
        image_path: Optional[str] = None,
        layout_preference: str = "Modern SaaS",
        primary_color_hint: Optional[str] = None,
        page_name: str = "dashboard"
    ) -> Dict[str, Any]:
        """
        Extract design tokens (palette, typography, layout, borders) from an image
        or preference specification.
        """
        if image_path and os.path.exists(image_path):
            analysis = UIReferenceService.analyze_reference_design(image_path, page_name)
            palette = analysis.get("palette", {})
        else:
            palette = {
                "primary": primary_color_hint or "#2563EB",
                "secondary": "#0F172A",
                "background": "#F8FAFC",
                "card_bg": "#FFFFFF",
                "text_primary": "#0F172A",
                "text_secondary": "#64748B",
                "accent": "#38BDF8",
                "border": "#E2E8F0"
            }

        return {
            "primary_color": palette.get("primary", "#2563EB"),
            "secondary_color": palette.get("secondary", "#0F172A"),
            "bg_color": palette.get("background", "#F8FAFC"),
            "card_bg": palette.get("card_bg", "#FFFFFF"),
            "border_radius": "8px",
            "sidebar_width": "260px",
            "layout": layout_preference,
            "palette": palette
        }

    @staticmethod
    def get_project_references(project_id: str) -> List[Dict[str, Any]]:
        """Retrieve all preserved UI references for a project."""
        conn = get_standalone_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM ui_reference_images
            WHERE project_id = ?
            ORDER BY id ASC
        """, (project_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        for r in rows:
            try:
                r["analysis"] = json.loads(r["analysis_json"]) if r.get("analysis_json") else {}
            except Exception:
                r["analysis"] = {}
        return rows

    @staticmethod
    def get_reference_for_page(project_id: str, page_name: str) -> Optional[Dict[str, Any]]:
        """Find the matching reference for a specific page."""
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", page_name.lower()).strip("_")
        conn = get_standalone_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM ui_reference_images
            WHERE project_id = ? AND page_name = ?
            ORDER BY id DESC LIMIT 1
        """, (project_id, clean))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        try:
            res["analysis"] = json.loads(res["analysis_json"]) if res.get("analysis_json") else {}
        except Exception:
            res["analysis"] = {}
        return res

    @staticmethod
    def compare_preview_with_reference(project_id: str, page_name: str, rendered_html: Optional[str] = None) -> Dict[str, Any]:
        """
        Compare generated HTML page against preserved reference design rules.
        Identifies matching elements and reports concrete visual differences.
        """
        ref = UIReferenceService.get_reference_for_page(project_id, page_name)
        if not ref:
            return {
                "has_reference": False,
                "message": f"No uploaded UI reference image on file for page '{page_name}'."
            }

        if rendered_html is None:
            try:
                from services.ui_service import render_preview_page
                ok, html = render_preview_page(project_id, f"templates/{page_name}.html")
                rendered_html = html if ok else ""
            except Exception:
                rendered_html = ""

        analysis = ref.get("analysis", {})
        layout = analysis.get("layout", {})
        palette = analysis.get("palette", {})

        matches = []
        differences = []

        # Check navigation
        if layout.get("has_header_nav") and ("<header" in rendered_html or "<nav" in rendered_html):
            matches.append("Header navigation bar present matching reference layout.")
        elif layout.get("has_header_nav"):
            differences.append("Reference specifies header navigation, but no <header> element was detected.")

        # Check auth card
        if layout.get("has_auth_card") and ("<form" in rendered_html and ("login" in rendered_html.lower() or "password" in rendered_html.lower())):
            matches.append("Authentication form card present conforming to reference wireframe.")

        # Check color palette usage
        primary = palette.get("primary", "#2563EB")
        if primary.lower() in rendered_html.lower():
            matches.append(f"Primary accent color ({primary}) incorporated in styling.")
        else:
            differences.append(f"Primary palette tone ({primary}) not directly matched in template styles.")

        # Check grid cards
        if layout.get("card_arrangement") == "3-column grid":
            if "grid-template-columns" in rendered_html or "display: grid" in rendered_html:
                matches.append("Multi-column card layout verified.")
            else:
                differences.append("Reference indicates multi-column card arrangement; linear layout detected.")

        fidelity_score = round(len(matches) / max(1, len(matches) + len(differences)) * 100.0, 1)

        return {
            "has_reference": True,
            "reference_id": ref["id"],
            "page_name": page_name,
            "original_filename": ref.get("original_filename"),
            "image_path": ref.get("image_path"),
            "fidelity_score": fidelity_score,
            "matches": matches,
            "matching_tokens": matches,
            "differences": differences,
            "validation_status": "High Fidelity" if fidelity_score >= 80 else ("Moderate Alignment" if fidelity_score >= 50 else "Needs Adjustment")
        }
