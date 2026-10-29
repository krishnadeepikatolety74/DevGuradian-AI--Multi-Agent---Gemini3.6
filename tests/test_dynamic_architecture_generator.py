"""
DevGuardian AI — Dynamic Architecture Generator Acceptance Test Suite
Validates project-specific architecture extraction across 5 distinct domains:
1. HireSmart AI (Multi-Agent Recruitment)
2. CultureLens (Cultural Travel & Tourism Guide)
3. Smart Crosswalk Safety System (Computer Vision & Video Stream)
4. Simple CRUD Application (Task / Inventory Tracker - No AI)
5. RAG / Document Intelligence Application (Vector Index & LLM)
Also tests source modification invalidation, multi-user isolation, and export downloads.
"""

import os
import shutil
import json
from pathlib import Path
import unittest

from app import app
from db import get_standalone_db
import services.project_service as project_service
import services.architecture_generator as architecture_generator
from services.workspace_manager import GENERATED_PROJECTS_DIR, sanitize_folder_name, get_project_workspace

class TestDynamicArchitectureGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

        # Create isolated test users
        conn = get_standalone_db()
        with conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO users (id, email, password_hash, full_name) VALUES (9901, 'user_a_arch@test.com', 'hash', 'User Arch A')")
            cur.execute("INSERT OR IGNORE INTO users (id, email, password_hash, full_name) VALUES (9902, 'user_b_arch@test.com', 'hash', 'User Arch B')")
        conn.close()

        cls.user_a_id = 9901
        cls.user_b_id = 9902
        cls.created_project_dirs = []

    @classmethod
    def tearDownClass(cls):
        for pdir in cls.created_project_dirs:
            if os.path.exists(pdir):
                try:
                    shutil.rmtree(pdir)
                except Exception:
                    pass

    def _login_as(self, user_id=9901):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = "User Arch A" if user_id == 9901 else "User Arch B"
            sess["user_role"] = "Developer"
            sess["csrf_token"] = "test_token"

    def _create_real_project(self, name, description, app_type="Web App", user_id=9901, files=None):
        """Create project record in DB and populate actual source files on disk."""
        proj_id = project_service.create_project(
            user_id=user_id,
            name=name,
            description=description,
            app_type=app_type,
            language="Python Flask"
        )
        ws_dir = get_project_workspace(proj_id)
        ws_dir.mkdir(parents=True, exist_ok=True)
        self.created_project_dirs.append(str(ws_dir))

        if files:
            for rel_path, content in files.items():
                target_file = ws_dir / rel_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding="utf-8")

        return proj_id, ws_dir

    # =========================================================================
    # TEST 1: HireSmart AI (Multi-Agent Recruitment Platform)
    # =========================================================================
    def test_01_hiresmart_ai_architecture(self):
        """Test that HireSmart AI reflects actual recruitment agents and SQLite storage."""
        hiresmart_files = {
            "app.py": """
from flask import Flask, request, jsonify, render_template
import models
import services

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_resume():
    return jsonify({"status": "received"})

@app.route("/evaluate", methods=["POST"])
def evaluate():
    return jsonify({"status": "evaluated"})
""",
            "models.py": """
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))

class AnalysisResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skills = db.Column(db.Text)
""",
            "services.py": """
import google.generativeai as genai

class ResumeAnalysisAgent:
    def parse_skills(self, text):
        return ["Python", "Flask"]

class CandidateScoringAgent:
    def score_match(self, resume, job):
        return 92
"""
        }

        proj_id, ws_dir = self._create_real_project(
            "HireSmart AI Test",
            "Autonomous AI resume parsing and recruitment platform",
            app_type="Web App",
            files=hiresmart_files
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])

        comp_names = [c["name"] for c in arch["components"]]
        all_text = " ".join(comp_names)

        # Must contain its real agents and components
        self.assertTrue(any("ResumeAnalysisAgent" in c for c in comp_names))
        self.assertTrue(any("CandidateScoringAgent" in c for c in comp_names))
        self.assertTrue(any("Google Gemini API" in c for c in comp_names))
        self.assertTrue(any("SQLite" in c for c in comp_names))

    # =========================================================================
    # TEST 2: CultureLens (Cultural Travel & Destination Intelligence)
    # =========================================================================
    def test_02_culturelens_architecture(self):
        """Test that CultureLens reflects cultural travel agents and no recruitment boxes."""
        culture_files = {
            "app.py": """
from flask import Flask, render_template, request, jsonify
import services

app = Flask(__name__)

@app.route("/destinations")
def destinations():
    return render_template("destinations.html")

@app.route("/itinerary/generate", methods=["POST"])
def generate_itinerary():
    return jsonify({"itinerary": []})
""",
            "models.py": """
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Destination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(100))
    country = db.Column(db.String(100))

class CulturalHeritageSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(120))
""",
            "services.py": """
import google.generativeai as genai

class CulturalItineraryAgent:
    def build_schedule(self, city, days):
        return "Day 1: Historic District"

class DestinationCuratorService:
    def get_highlights(self, city):
        return ["Museum", "Old Town"]
"""
        }

        proj_id, ws_dir = self._create_real_project(
            "CultureLens",
            "AI cultural travel curator and personalized heritage itinerary planner",
            app_type="Web App",
            files=culture_files
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])

        comp_names = [c["name"] for c in arch["components"]]
        all_text = " ".join(comp_names)

        # Must reflect CultureLens components
        self.assertTrue(any("CulturalItineraryAgent" in c for c in comp_names))
        self.assertTrue(any("DestinationCuratorService" in c for c in comp_names))

        # Must NEVER contain HireSmart AI recruitment components!
        self.assertNotIn("Resume", all_text)
        self.assertNotIn("Candidate Scoring", all_text)
        self.assertNotIn("Interview Question", all_text)
        self.assertNotIn("Hiring Decision", all_text)

    # =========================================================================
    # TEST 3: Smart Crosswalk Safety System (Computer Vision)
    # =========================================================================
    def test_03_smart_crosswalk_safety_system_architecture(self):
        """Test that Smart Crosswalk reflects video stream input and CV detection engine."""
        crosswalk_files = {
            "app.py": """
from flask import Flask, render_template, Response, jsonify
import cv2
import services

app = Flask(__name__)

@app.route("/stream/video_feed")
def video_feed():
    return Response(b"feed", mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/incidents")
def incidents():
    return jsonify([])
""",
            "services.py": """
import cv2

class YOLOPedestrianDetector:
    def detect_crossings(self, frame):
        return []

class CrosswalkSafetyEngine:
    def evaluate_risk(self, pedestrians, vehicles):
        return "ALERT_HIGH"
""",
            "models.py": """
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class TrafficIncident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    alert_level = db.Column(db.String(20))
""",
            "templates/dashboard.html": """
<!DOCTYPE html><html><body><video id="crosswalkFeed"></video><canvas id="detectionOverlay"></canvas></body></html>
"""
        }

        proj_id, ws_dir = self._create_real_project(
            "Smart Crosswalk Safety System",
            "Real-time computer vision pedestrian monitoring and optical crosswalk collision prevention",
            app_type="Computer Vision App",
            files=crosswalk_files
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])

        self.assertIn("Computer Vision", arch["pattern"])
        comp_names = [c["name"] for c in arch["components"]]
        all_text = " ".join(comp_names)

        # Video stream input & CV model verification
        self.assertTrue(any("Video Feed Stream" in c or "Camera" in c for c in comp_names))
        self.assertTrue(any("Computer Vision" in c or "YOLO" in c for c in comp_names))

        # Must NEVER contain recruitment boxes
        self.assertNotIn("Resume", all_text)
        self.assertNotIn("Candidate", all_text)
        self.assertNotIn("Interview", all_text)

    # =========================================================================
    # TEST 4: Simple CRUD Application (No AI, Pure Web + DB)
    # =========================================================================
    def test_04_simple_crud_application_architecture(self):
        """Test that a simple CRUD app has NO AI models, NO agents, and NO recruitment labels."""
        crud_files = {
            "app.py": """
from flask import Flask, request, render_template, redirect, url_for
from models import db, Task
from services import TaskService

app = Flask(__name__)

@app.route("/tasks")
def list_tasks():
    return render_template("tasks.html")

@app.route("/tasks/create", methods=["POST"])
def create_task():
    return redirect(url_for("list_tasks"))
""",
            "models.py": """
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    is_completed = db.Column(db.Boolean, default=False)
""",
            "services.py": """
class TaskService:
    def complete_task(self, task_id):
        return True
"""
        }

        proj_id, ws_dir = self._create_real_project(
            "Simple Task Manager CRUD",
            "A clean task and inventory management application with SQLite database persistence",
            app_type="Web App",
            files=crud_files
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])

        comp_names = [c["name"] for c in arch["components"]]
        all_text = " ".join(comp_names)

        # Must contain TaskService, Flask, SQLite
        self.assertTrue(any("TaskService" in c for c in comp_names))
        self.assertTrue(any("SQLite" in c for c in comp_names))

        # Must NOT contain AI agents or recruitment boxes
        self.assertNotIn("Resume", all_text)
        self.assertNotIn("Autonomous AI Engines", all_text)
        self.assertNotIn("Candidate Scoring", all_text)
        self.assertNotIn("Interview", all_text)
        self.assertNotIn("Hiring", all_text)

    # =========================================================================
    # TEST 5: RAG / Document Intelligence Application
    # =========================================================================
    def test_05_rag_document_intelligence_architecture(self):
        """Test that RAG system reflects chunking, vector index, and Gemini API."""
        rag_files = {
            "app.py": """
from flask import Flask, request, jsonify
import chromadb
import google.generativeai as genai
import services

app = Flask(__name__)

@app.route("/upload_doc", methods=["POST"])
def upload_doc():
    return jsonify({"status": "indexed"})

@app.route("/ask", methods=["POST"])
def ask():
    return jsonify({"answer": "Synthesized insight"})
""",
            "services.py": """
import chromadb
import google.generativeai as genai

class DocumentChunkerService:
    def chunk(self, doc_text):
        return ["chunk 1", "chunk 2"]

class VectorSearchRetriever:
    def query_similar(self, query):
        return ["context 1"]
"""
        }

        proj_id, ws_dir = self._create_real_project(
            "LegalDoc Intelligence RAG",
            "Retrieval-Augmented Generation system for legal contracts and document search",
            app_type="Web App",
            files=rag_files
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])

        self.assertIn("RAG", arch["pattern"])
        comp_names = [c["name"] for c in arch["components"]]
        all_text = " ".join(comp_names)

        # Must contain RAG vector components and services
        self.assertTrue(any("DocumentChunkerService" in c or "Vector" in c or "RAG" in c for c in comp_names))
        self.assertTrue(any("Google Gemini API" in c for c in comp_names))

        # Must NOT contain recruitment boxes
        self.assertNotIn("Resume", all_text)
        self.assertNotIn("Candidate Scoring", all_text)

    # =========================================================================
    # TEST 6: Source Modification Cache Invalidation
    # =========================================================================
    def test_06_source_modification_triggers_regeneration(self):
        """Modifying source code changes source_hash and triggers fresh regeneration."""
        initial_files = {
            "app.py": "@app.route('/')\ndef home(): return 'ok'",
            "services.py": "class PaymentService:\n    pass"
        }
        proj_id, ws_dir = self._create_real_project(
            "FinTech MicroPay",
            "Financial payments gateway",
            files=initial_files
        )

        # 1. First generation
        arch1 = architecture_generator.get_project_architecture_data(proj_id)
        hash1 = arch1["source_hash"]
        self.assertTrue(any("PaymentService" in c["name"] for c in arch1["components"]))

        # 2. Modify source code (add new service class)
        services_file = ws_dir / "services.py"
        services_file.write_text("class PaymentService:\n    pass\n\nclass FraudShieldAgent:\n    pass\n", encoding="utf-8")

        # 3. Retrieve architecture (should auto-detect modification and regenerate)
        arch2 = architecture_generator.get_project_architecture_data(proj_id)
        hash2 = arch2["source_hash"]

        self.assertNotEqual(hash1, hash2, "Source hash must change when source file is modified")
        comp_names2 = [c["name"] for c in arch2["components"]]
        self.assertTrue(any("FraudShieldAgent" in c for c in comp_names2), "New component must appear in fresh architecture")

    # =========================================================================
    # TEST 7: Downloads & Exports (PNG, SVG, JSON)
    # =========================================================================
    def test_07_export_endpoints(self):
        """Verify PNG, SVG, and JSON downloads return status 200 with proper headers."""
        self._login_as(self.user_a_id)
        proj_id, ws_dir = self._create_real_project(
            "Export Test App",
            "Testing artifact exports",
            files={"app.py": "@app.route('/')\ndef test(): pass"}
        )

        # 1. Generate via POST
        resp = self.client.post(f"/architecture/{proj_id}/generate", data={
            "csrf_token": "test_token",
            "diagram_type": "system"
        }, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertIn(resp.status_code, [200, 302])

        # 2. Download PNG
        png_resp = self.client.get(f"/architecture/{proj_id}/export/png")
        self.assertEqual(png_resp.status_code, 200)
        self.assertEqual(png_resp.content_type, "image/png")
        self.assertGreater(len(png_resp.data), 1000)

        # 3. Download SVG
        svg_resp = self.client.get(f"/architecture/{proj_id}/export/svg")
        self.assertEqual(svg_resp.status_code, 200)
        self.assertEqual(svg_resp.content_type, "image/svg+xml; charset=utf-8")
        self.assertIn(b"<svg", svg_resp.data)

        # 4. Download JSON
        json_resp = self.client.get(f"/architecture/{proj_id}/export/json")
        self.assertEqual(json_resp.status_code, 200)
        self.assertEqual(json_resp.content_type, "application/json")
        parsed_json = json.loads(json_resp.data.decode("utf-8"))
        self.assertIn("components", parsed_json)

    # =========================================================================
    # TEST 8: Multi-User Isolation
    # =========================================================================
    def test_08_multi_user_isolation(self):
        """Ensure User B cannot access User A's project architecture files."""
        # Create project under User A
        proj_id, ws_dir = self._create_real_project(
            "User A Private System",
            "Proprietary confidential system",
            user_id=self.user_a_id,
            files={"app.py": "# private"}
        )

        # Login as User B
        self._login_as(self.user_b_id)

        # User B attempts to access User A's export
        resp = self.client.get(f"/architecture/{proj_id}/export/png")
        self.assertEqual(resp.status_code, 404, "User B should be denied access to User A's architecture")

    # =========================================================================
    # TEST 9: Insufficient Information Graceful Handling
    # =========================================================================
    def test_09_minimal_project_warning(self):
        """Minimal projects must be marked proposed with clear warning instead of fabricating fake agents."""
        proj_id, ws_dir = self._create_real_project(
            "Empty Shell Project",
            "Minimal specification without code yet",
            files={}
        )

        arch = architecture_generator.generate_project_architecture(proj_id, diagram_type="system")
        self.assertTrue(arch["success"])
        self.assertEqual(arch["architecture_status"], "proposed")
        self.assertTrue(arch["is_minimal"])

if __name__ == "__main__":
    unittest.main()
