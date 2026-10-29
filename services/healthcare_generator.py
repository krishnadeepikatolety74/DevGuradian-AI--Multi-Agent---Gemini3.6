"""
Healthcare Multi-Agent AI Workflow Automation Generator
DevGuardian AI
"""
from typing import Dict, Any

def _generate_healthcare_project(
    project_name: str, description: str, slug: str, assigned_port: int,
    primary_color: str, secondary_color: str, bg_color: str, accent_color: str
) -> Dict[str, str]:
    files = {}

    # config.py
    files["config.py"] = f'''"""Configuration for {project_name}"""
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "healthcare-secret-key-88912")
    PORT = int(os.environ.get("PORT", {assigned_port}))
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "instance", "{slug}.db")
    TRIAGE_ALERT_THRESHOLD = 75
    APPOINTMENT_DURATION_MINS = 30
    DEFAULT_CLINIC_NAME = "{project_name}"
'''

    # database package
    files["database/__init__.py"] = "# Database Package\n"

    # database/db.py
    files["database/db.py"] = ('''"""Database connection and schema setup for __PROJECT_NAME__"""
import sqlite3
import os
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "instance" / "__SLUG__.db"

def get_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'Clinician',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                dob TEXT NOT NULL,
                gender TEXT NOT NULL,
                blood_group TEXT DEFAULT 'O+',
                phone TEXT NOT NULL,
                email TEXT,
                medical_history TEXT,
                allergies TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                doctor_name TEXT NOT NULL,
                department TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT DEFAULT 'Confirmed',
                reason TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS triage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                patient_name TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                vital_signs_json TEXT NOT NULL,
                acuity_level TEXT NOT NULL,
                danger_score REAL NOT NULL,
                recommended_action TEXT NOT NULL,
                status TEXT DEFAULT 'Assessed',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS medical_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                extracted_data_json TEXT NOT NULL,
                status TEXT DEFAULT 'Processed',
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM users")
        if cur.fetchone()["c"] == 0:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES ('doctor', 'doctor123', 'Dr. Evelyn Reed, MD', 'Chief Medical Officer')
            """)

        cur.execute("SELECT COUNT(*) as c FROM patients")
        if cur.fetchone()["c"] == 0:
            sample_patients = [
                ('Alexander Hayes', '1984-06-12', 'Male', 'A+', '+1-555-0192', 'alex.hayes@example.com', 'Hypertension, Mild Asthma', 'Penicillin'),
                ('Sophia Lin', '1992-11-04', 'Female', 'O+', '+1-555-0348', 'sophia.lin@example.com', 'No chronic conditions', 'None'),
                ('Marcus Vance', '1976-03-22', 'Male', 'B-', '+1-555-0781', 'm.vance@example.com', 'Type 2 Diabetes', 'Sulfa drugs')
            ]
            cur.executemany("""
                INSERT INTO patients (full_name, dob, gender, blood_group, phone, email, medical_history, allergies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_patients)

            sample_appts = [
                (1, 'Dr. Evelyn Reed', 'Cardiology', '2026-10-25', '09:30 AM', 'Confirmed', 'Routine quarterly blood pressure and cardiac rhythm follow-up', 'Patient advised to bring BP log'),
                (2, 'Dr. Aris Thorne', 'Neurology', '2026-10-25', '11:00 AM', 'Confirmed', 'Evaluation of recurring tension headaches and migraine aura', 'MRI scan requested'),
                (3, 'Dr. Marcus Webb', 'Endocrinology', '2026-10-26', '02:15 PM', 'Pending', 'Bi-annual HbA1c diabetic monitoring and dosage review', 'Fasting required')
            ]
            cur.executemany("""
                INSERT INTO appointments (patient_id, doctor_name, department, appointment_date, time_slot, status, reason, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_appts)

            sample_triage = [
                (1, 'Alexander Hayes', 'Sudden palpitations and chest tightness after mild exertion', '{"hr": 108, "bp": "148/92", "spo2": 97, "temp": 37.1}', 'Urgent (ESI-2)', 84.5, 'Immediate 12-lead ECG and cardiology stat consultation.', 'In Triage'),
                (2, 'Sophia Lin', 'Seasonal allergy exacerbation and nasal congestion', '{"hr": 74, "bp": "118/76", "spo2": 99, "temp": 36.8}', 'Routine (ESI-4)', 18.0, 'Prescribe second-generation antihistamine and schedule outpatient follow-up.', 'Resolved')
            ]
            cur.executemany("""
                INSERT INTO triage_records (patient_id, patient_name, symptoms, vital_signs_json, acuity_level, danger_score, recommended_action, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_triage)
    conn.close()
''').replace("__PROJECT_NAME__", project_name).replace("__SLUG__", slug)

    # database/models.py
    files["database/models.py"] = '''"""Data Models for Healthcare Records & Appointments"""
from database.db import get_db
import json

class PatientModel:
    @staticmethod
    def get_all():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients ORDER BY id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_by_id(pid: int):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients WHERE id = ?", (pid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(full_name, dob, gender, blood_group, phone, email, medical_history, allergies):
        conn = get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO patients (full_name, dob, gender, blood_group, phone, email, medical_history, allergies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (full_name, dob, gender, blood_group, phone, email, medical_history, allergies))
            new_id = cur.lastrowid
        conn.close()
        return new_id

class AppointmentModel:
    @staticmethod
    def get_all():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, p.full_name as patient_name 
            FROM appointments a 
            LEFT JOIN patients p ON a.patient_id = p.id 
            ORDER BY a.appointment_date ASC, a.time_slot ASC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_recent(limit=5):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, p.full_name as patient_name 
            FROM appointments a 
            LEFT JOIN patients p ON a.patient_id = p.id 
            ORDER BY a.id DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def create(patient_id, doctor_name, department, appointment_date, time_slot, reason, notes=""):
        conn = get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO appointments (patient_id, doctor_name, department, appointment_date, time_slot, reason, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, doctor_name, department, appointment_date, time_slot, reason, notes))
            new_id = cur.lastrowid
        conn.close()
        return new_id

    @staticmethod
    def update_status(aid, status):
        conn = get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, aid))
        conn.close()

class TriageModel:
    @staticmethod
    def get_recent(limit=5):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM triage_records ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def record_triage(patient_id, patient_name, symptoms, vital_signs, acuity_level, danger_score, action):
        conn = get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO triage_records (patient_id, patient_name, symptoms, vital_signs_json, acuity_level, danger_score, recommended_action)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, patient_name, symptoms, json.dumps(vital_signs), acuity_level, danger_score, action))
            new_id = cur.lastrowid
        conn.close()
        return new_id

class DocumentModel:
    @staticmethod
    def get_all():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM medical_documents ORDER BY id DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def record_document(patient_id, doc_type, title, summary, extracted_data):
        conn = get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO medical_documents (patient_id, doc_type, title, summary, extracted_data_json)
                VALUES (?, ?, ?, ?, ?)
            """, (patient_id, doc_type, title, summary, json.dumps(extracted_data)))
            new_id = cur.lastrowid
        conn.close()
        return new_id
'''

    # models/__init__.py
    files["models/__init__.py"] = "# Models Package\n"

    # models/patient.py
    files["models/patient.py"] = '''"""Patient Domain Entity"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class PatientEntity:
    id: Optional[int]
    full_name: str
    dob: str
    gender: str
    blood_group: str
    phone: str
    email: Optional[str]
    medical_history: Optional[str]
    allergies: Optional[str]
'''

    # models/appointment.py
    files["models/appointment.py"] = '''"""Appointment Domain Entity"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class AppointmentEntity:
    id: Optional[int]
    patient_id: int
    doctor_name: str
    department: str
    appointment_date: str
    time_slot: str
    status: str
    reason: str
    notes: Optional[str] = None
'''

    # agents/__init__.py
    files["agents/__init__.py"] = "# Autonomous Agents Package\n"

    # agents/appointment_agent.py
    files["agents/appointment_agent.py"] = '''"""Autonomous Appointment Scheduling & Doctor Matching Agent"""
from typing import Dict, Any, List

class AppointmentAgent:
    SPECIALTY_MAP = {
        "chest": "Cardiology",
        "heart": "Cardiology",
        "palpitation": "Cardiology",
        "headache": "Neurology",
        "dizzy": "Neurology",
        "nerve": "Neurology",
        "bone": "Orthopedics",
        "joint": "Orthopedics",
        "fracture": "Orthopedics",
        "diabetes": "Endocrinology",
        "thyroid": "Endocrinology",
        "child": "Pediatrics",
        "fever": "General Medicine",
        "cough": "General Medicine"
    }

    DEPARTMENT_DOCTORS = {
        "Cardiology": ["Dr. Evelyn Reed, MD", "Dr. David Vance, MD"],
        "Neurology": ["Dr. Aris Thorne, MD", "Dr. Clara Oswald, MD"],
        "Orthopedics": ["Dr. Nathan Drake, MD"],
        "Endocrinology": ["Dr. Marcus Webb, MD"],
        "General Medicine": ["Dr. Sarah Jenkins, MD", "Dr. Robert Song, MD"]
    }

    @classmethod
    def match_specialist(cls, symptoms: str) -> Dict[str, Any]:
        sym_lower = symptoms.lower()
        dept = "General Medicine"
        for kw, target_dept in cls.SPECIALTY_MAP.items():
            if kw in sym_lower:
                dept = target_dept
                break

        doctors = cls.DEPARTMENT_DOCTORS.get(dept, ["Dr. General Physician, MD"])
        return {
            "department": dept,
            "recommended_physician": doctors[0],
            "alternate_physicians": doctors[1:],
            "confidence_score": 0.94
        }

    @classmethod
    def find_available_slots(cls, department: str, date_str: str) -> List[str]:
        standard_slots = ["09:00 AM", "09:30 AM", "10:15 AM", "11:00 AM", "02:00 PM", "03:30 PM", "04:15 PM"]
        return standard_slots
'''

    # agents/document_agent.py
    files["agents/document_agent.py"] = '''"""Autonomous Medical Document & Clinical Intake Agent"""
import re
from typing import Dict, Any, List

class DocumentAgent:
    @staticmethod
    def extract_clinical_entities(notes: str) -> Dict[str, Any]:
        conditions = []
        medications = []
        
        common_conditions = ["hypertension", "diabetes", "asthma", "migraine", "arthritis", "arrhythmia"]
        notes_lower = notes.lower()
        for cond in common_conditions:
            if cond in notes_lower:
                conditions.append(cond.title())

        med_matches = re.findall(r"([A-Za-z]+)\s*(\d+\s*(?:mg|mcg|ml))", notes, re.IGNORECASE)
        for med, dose in med_matches:
            medications.append(f"{med.title()} ({dose})")

        return {
            "extracted_conditions": conditions or ["Non-specific symptoms recorded"],
            "detected_medications": medications or ["No prescription dosages mentioned"],
            "urgency_marker": "Urgent" if any(w in notes_lower for w in ["severe", "acute", "sudden", "critical"]) else "Standard",
            "entity_count": len(conditions) + len(medications)
        }

    @staticmethod
    def synthesize_ehr_summary(patient_name: str, notes: str) -> str:
        entities = DocumentAgent.extract_clinical_entities(notes)
        cond_str = ", ".join(entities["extracted_conditions"])
        med_str = ", ".join(entities["detected_medications"])
        return f"Clinical EHR Brief for {patient_name}: Identified conditions ({cond_str}); Active medications ({med_str}). Priority: {entities['urgency_marker']}."
'''

    # agents/workflow_agent.py
    files["agents/workflow_agent.py"] = '''"""Healthcare Multi-Agent Workflow Automation Orchestrator"""
from agents.appointment_agent import AppointmentAgent
from agents.document_agent import DocumentAgent
from database.models import TriageModel, AppointmentModel, PatientModel
import json

class WorkflowAgent:
    @classmethod
    def process_patient_intake(cls, patient_id: int, symptoms: str, vitals: dict):
        patient = PatientModel.get_by_id(patient_id)
        pname = patient["full_name"] if patient else "Outpatient Guest"

        # 1. Triage Acuity Evaluation
        hr = float(vitals.get("hr", 75))
        spo2 = float(vitals.get("spo2", 98))
        danger_score = 15.0
        if hr > 100 or hr < 55:
            danger_score += 35.0
        if spo2 < 95:
            danger_score += 40.0

        if danger_score >= 70:
            acuity = "Urgent (ESI-2)"
            action = "Immediate physician examination and stat telemetry."
        elif danger_score >= 40:
            acuity = "Priority (ESI-3)"
            action = "Same-day consultation and priority lab workup."
        else:
            acuity = "Routine (ESI-4)"
            action = "Standard outpatient scheduling and routine care."

        triage_id = TriageModel.record_triage(
            patient_id=patient_id,
            patient_name=pname,
            symptoms=symptoms,
            vital_signs=vitals,
            acuity_level=acuity,
            danger_score=danger_score,
            action=action
        )

        # 2. Specialist Selection via AppointmentAgent
        specialist_info = AppointmentAgent.match_specialist(symptoms)

        # 3. Document Extraction via DocumentAgent
        doc_summary = DocumentAgent.synthesize_ehr_summary(pname, symptoms)

        # 4. Automated Booking
        appt_id = AppointmentModel.create(
            patient_id=patient_id,
            doctor_name=specialist_info["recommended_physician"],
            department=specialist_info["department"],
            appointment_date="2026-10-27",
            time_slot="10:00 AM",
            reason=symptoms[:120],
            notes=f"Auto-scheduled by Healthcare Multi-Agent AI. Triage Acuity: {acuity}. {doc_summary}"
        )

        return {
            "workflow_id": f"WF-MED-{triage_id:04d}",
            "patient_name": pname,
            "triage_id": triage_id,
            "acuity_level": acuity,
            "danger_score": danger_score,
            "recommended_department": specialist_info["department"],
            "assigned_doctor": specialist_info["recommended_physician"],
            "appointment_id": appt_id,
            "status": "Orchestrated Successfully"
        }
'''

    # services/__init__.py
    files["services/__init__.py"] = "# Services Package\n"

    # services/appointment_service.py
    files["services/appointment_service.py"] = '''"""Appointment Service Layer"""
from database.models import AppointmentModel, PatientModel

class AppointmentService:
    @staticmethod
    def list_appointments():
        return AppointmentModel.get_all()

    @staticmethod
    def book_new_appointment(patient_id, doctor, department, date, time_slot, reason):
        return AppointmentModel.create(
            patient_id=patient_id,
            doctor_name=doctor,
            department=department,
            appointment_date=date,
            time_slot=time_slot,
            reason=reason,
            notes="Booked via Clinical Portal"
        )
'''

    # services/notification_service.py
    files["services/notification_service.py"] = '''"""Patient & Staff Notification Service"""
class NotificationService:
    @staticmethod
    def send_appointment_reminder(patient_name: str, doctor: str, date_time: str):
        return {
            "delivered": True,
            "channel": "SMS & Email",
            "recipient": patient_name,
            "message": f"Confirmed: Appointment with {doctor} on {date_time}. Please arrive 10m early."
        }

    @staticmethod
    def broadcast_urgent_triage_alert(patient_name: str, acuity: str):
        return {
            "dispatched": True,
            "priority": "HIGH",
            "alert": f"CRITICAL TRIAGE: Patient {patient_name} assessed at {acuity}. Stat response requested."
        }
'''

    # services/triage_service.py
    files["services/triage_service.py"] = '''"""Clinical Triage Service"""
from database.models import TriageModel

class TriageService:
    @staticmethod
    def evaluate(patient_id, patient_name, symptoms, vitals):
        hr = float(vitals.get("hr", 75))
        spo2 = float(vitals.get("spo2", 98))
        danger_score = 10.0
        if hr > 105 or hr < 50:
            danger_score += 40.0
        if spo2 < 94:
            danger_score += 45.0

        acuity = "Urgent (ESI-2)" if danger_score >= 60 else "Routine (ESI-4)"
        action = "Stat clinical observation" if danger_score >= 60 else "Outpatient care"
        tid = TriageModel.record_triage(patient_id, patient_name, symptoms, vitals, acuity, danger_score, action)
        return {
            "triage_id": tid,
            "acuity": acuity,
            "danger_score": danger_score,
            "action": action
        }
'''

    # templates/base.html
    base_tpl = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}__PROJECT_NAME__{% endblock %}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <header class="navbar">
        <a href="{{ url_for('index') }}" class="brand">
            <span style="font-size: 20px;">&#10010;</span>
            <span>__PROJECT_NAME__</span>
            <span class="brand-badge">Healthcare AI</span>
        </a>
        <nav class="nav-links">
            <a href="{{ url_for('index') }}">Home</a>
            <a href="{{ url_for('dashboard') }}">Dashboard</a>
            <a href="{{ url_for('appointments') }}">Appointments</a>
            <a href="{{ url_for('triage') }}">&#9889; AI Triage</a>
            <a href="{{ url_for('records') }}">EHR Records</a>
            {% if session.get('user_id') %}
                <span style="font-size: 12px; color: #34D399; font-weight: 600;">&#9679; {{ session.get('username') }}</span>
                <a href="{{ url_for('logout') }}" class="btn btn-secondary" style="padding: 5px 12px; font-size: 12px;">Sign Out</a>
            {% else %}
                <a href="{{ url_for('login') }}" class="btn btn-secondary" style="padding: 5px 12px; font-size: 12px;">Log In</a>
                <a href="{{ url_for('signup') }}" class="btn btn-primary" style="padding: 5px 12px; font-size: 12px;">Sign Up</a>
            {% endif %}
        </nav>
    </header>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-container">
                {% for category, message in messages %}
                    <div class="flash-msg flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <main class="main-content">
        {% block content %}{% endblock %}
    </main>

    <footer class="footer">
        __PROJECT_NAME__ &bull; Autonomous Healthcare Workflow Platform &bull; Port __ASSIGNED_PORT__
    </footer>
</body>
</html>
"""
    files["templates/base.html"] = base_tpl.replace("__PROJECT_NAME__", project_name).replace("__ASSIGNED_PORT__", str(assigned_port))

    # templates/landing.html & templates/index.html
    landing_tpl = """{% extends "base.html" %}
{% block title %}__PROJECT_NAME__ — Clinical Automation &amp; Multi-Agent AI{% endblock %}
{% block content %}
<div style="background: linear-gradient(135deg, #064E3B 0%, #0F172A 100%); border-radius: 12px; padding: 48px 40px; color: #FFFFFF; margin-bottom: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.15);">
    <div style="max-width: 760px;">
        <span style="background: rgba(16,185,129,0.25); color: #6EE7B7; border: 1px solid rgba(110,231,183,0.3); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase;">Autonomous Clinical Workflow Orchestrator</span>
        <h1 style="font-size: 38px; font-weight: 800; margin: 16px 0 14px 0; line-height: 1.2;">Multi-Agent AI for Hospital Intake, Triage &amp; Automated Scheduling</h1>
        <p style="font-size: 16px; color: #D1D5DB; margin-bottom: 24px; line-height: 1.6;">
            __DESCRIPTION__
        </p>
        <div style="display: flex; gap: 14px; flex-wrap: wrap;">
            <a href="{{ url_for('dashboard') }}" class="btn btn-primary" style="padding: 12px 24px; font-size: 14px;">
                Open Clinical Dashboard &rarr;
            </a>
            <a href="{{ url_for('triage') }}" class="btn btn-secondary" style="padding: 12px 24px; font-size: 14px;">
                &#9889; Run Emergency Triage
            </a>
            <a href="{{ url_for('appointments') }}" class="btn btn-secondary" style="padding: 12px 24px; font-size: 14px;">
                Manage Appointments
            </a>
        </div>
    </div>
</div>

<div class="grid-4" style="margin-bottom: 32px;">
    <div class="stat-card">
        <span class="stat-label">Active Patients</span>
        <h3 class="stat-val">3,420</h3>
        <span style="font-size: 12px; color: var(--success); font-weight: 600;">&#8593; 99.8% EHR Integrity</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Available Doctors</span>
        <h3 class="stat-val">42 Staff</h3>
        <span style="font-size: 12px; color: #64748B;">Across 6 Specializations</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Triage Processing SLA</span>
        <h3 class="stat-val" style="color: var(--primary);">4.2 sec</h3>
        <span style="font-size: 12px; color: var(--success); font-weight: 600;">Instant Acuity Routing</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Autonomous Workflows</span>
        <h3 class="stat-val">100%</h3>
        <span style="font-size: 12px; color: #64748B;">Zero Scheduling Conflicts</span>
    </div>
</div>

<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
    <div class="card">
        <h3 class="card-title">&#128197; Appointment Agent</h3>
        <p class="card-subtitle">Autonomous physician matching and conflict-free calendar booking with automatic slot optimization.</p>
    </div>
    <div class="card">
        <h3 class="card-title">&#128196; Document Agent</h3>
        <p class="card-subtitle">Clinical NLP for parsing medical intake records, lab panels, and generating structured EHR summaries.</p>
    </div>
    <div class="card">
        <h3 class="card-title">&#9878; Workflow Agent</h3>
        <p class="card-subtitle">End-to-end multi-agent orchestration coordinating emergency triage, specialist referrals, and patient alerts.</p>
    </div>
</div>
{% endblock %}
"""
    landing_rendered = landing_tpl.replace("__PROJECT_NAME__", project_name).replace("__DESCRIPTION__", description)
    files["templates/landing.html"] = landing_rendered
    files["templates/index.html"] = landing_rendered

    # templates/login.html
    login_tpl = """{% extends "base.html" %}
{% block title %}Clinician Sign In — __PROJECT_NAME__{% endblock %}
{% block content %}
<div class="auth-card">
    <div style="text-align: center; margin-bottom: 24px;">
        <span style="font-size: 32px;">&#129658;</span>
        <h2 style="font-size: 22px; font-weight: 700; color: #0F172A; margin: 8px 0 4px 0;">Clinician Portal Login</h2>
        <p style="font-size: 13px; color: #64748B;">Access __PROJECT_NAME__ multi-agent clinical workflow platform.</p>
    </div>

    <form method="POST" action="{{ url_for('login') }}">
        <div style="margin-bottom: 16px;">
            <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Staff Username</label>
            <input type="text" name="username" value="doctor" required class="form-input">
        </div>
        <div style="margin-bottom: 20px;">
            <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Password</label>
            <input type="password" name="password" value="doctor123" required class="form-input">
        </div>
        <button type="submit" class="btn btn-primary" style="width: 100%; padding: 11px; font-size: 14px;">
            Sign In to Clinical Console
        </button>
    </form>

    <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border); text-align: center; font-size: 12.5px; color: #64748B;">
        Need staff credentials? <a href="{{ url_for('signup') }}" style="color: var(--primary); font-weight: 600; text-decoration: none;">Register New Staff Account</a>
    </div>
</div>
{% endblock %}
"""
    files["templates/login.html"] = login_tpl.replace("__PROJECT_NAME__", project_name)

    # templates/signup.html
    signup_tpl = """{% extends "base.html" %}
{% block title %}Register Staff Account — __PROJECT_NAME__{% endblock %}
{% block content %}
<div class="auth-card">
    <div style="text-align: center; margin-bottom: 24px;">
        <span style="font-size: 32px;">&#10010;</span>
        <h2 style="font-size: 22px; font-weight: 700; color: #0F172A; margin: 8px 0 4px 0;">New Clinical Staff Registration</h2>
        <p style="font-size: 13px; color: #64748B;">Create an authorized clinician or coordinator account.</p>
    </div>

    <form method="POST" action="{{ url_for('signup') }}">
        <div style="margin-bottom: 16px;">
            <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Full Name with Title</label>
            <input type="text" name="full_name" placeholder="Dr. Jane Watson, MD" required class="form-input">
        </div>
        <div style="margin-bottom: 16px;">
            <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Username</label>
            <input type="text" name="username" placeholder="jwatson" required class="form-input">
        </div>
        <div style="margin-bottom: 20px;">
            <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Password</label>
            <input type="password" name="password" required class="form-input">
        </div>
        <button type="submit" class="btn btn-primary" style="width: 100%; padding: 11px; font-size: 14px;">
            Create Staff Profile
        </button>
    </form>
</div>
{% endblock %}
"""
    files["templates/signup.html"] = signup_tpl.replace("__PROJECT_NAME__", project_name)

    # templates/dashboard.html
    dash_tpl = """{% extends "base.html" %}
{% block title %}Clinical Command Center — __PROJECT_NAME__{% endblock %}
{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px;">
    <div>
        <h2 style="font-size: 24px; font-weight: 800; color: #0F172A; margin-bottom: 4px;">Clinical Command Center</h2>
        <p style="font-size: 14px; color: #64748B;">Real-time automated multi-agent triage, scheduling, and EHR intelligence.</p>
    </div>
    <div style="display: flex; gap: 10px;">
        <a href="{{ url_for('triage') }}" class="btn btn-primary">&#9889; New AI Intake &amp; Triage</a>
        <a href="{{ url_for('appointments') }}" class="btn btn-secondary">&#128197; Book Appointment</a>
    </div>
</div>

<div class="grid-4" style="margin-bottom: 28px;">
    <div class="stat-card">
        <span class="stat-label">Total Appointments</span>
        <h3 class="stat-val">{{ appointments|length }}</h3>
        <span style="font-size: 12px; color: var(--success); font-weight: 600;">Autonomous Queue Active</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Triage Intakes</span>
        <h3 class="stat-val">{{ triages|length }}</h3>
        <span style="font-size: 12px; color: #64748B;">Processed Last 24 Hours</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Registered Patients</span>
        <h3 class="stat-val">{{ patients|length }}</h3>
        <span style="font-size: 12px; color: var(--primary); font-weight: 600;">EHR Verified</span>
    </div>
    <div class="stat-card">
        <span class="stat-label">Agent Swarm Health</span>
        <h3 class="stat-val" style="color: var(--success);">100%</h3>
        <span style="font-size: 12px; color: #64748B;">3 Agents Operational</span>
    </div>
</div>

<div style="display: grid; grid-template-columns: 3fr 2fr; gap: 24px; margin-bottom: 30px;">
    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 class="card-title" style="margin: 0;">Upcoming Clinical Appointments</h3>
            <a href="{{ url_for('appointments') }}" style="font-size: 13px; color: var(--primary); font-weight: 600; text-decoration: none;">View All &rarr;</a>
        </div>
        <table class="table">
            <thead>
                <tr>
                    <th>Patient</th>
                    <th>Physician / Specialty</th>
                    <th>Date &amp; Slot</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for a in appointments[:5] %}
                <tr>
                    <td>
                        <strong style="color: #0F172A;">{{ a.patient_name or 'Outpatient' }}</strong><br>
                        <span style="font-size: 11px; color: #64748B;">Ref #APT-{{ a.id }}</span>
                    </td>
                    <td>
                        <div style="font-weight: 600; color: #0F172A;">{{ a.doctor_name }}</div>
                        <div style="font-size: 11px; color: #64748B;">{{ a.department }}</div>
                    </td>
                    <td>
                        <div style="font-weight: 600;">{{ a.appointment_date }}</div>
                        <div style="font-size: 11px; color: #64748B;">{{ a.time_slot }}</div>
                    </td>
                    <td>
                        <span class="badge badge-success">{{ a.status }}</span>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="4" style="text-align: center; color: #64748B;">No upcoming appointments found.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 class="card-title" style="margin: 0;">Recent Emergency Triage</h3>
            <a href="{{ url_for('triage') }}" style="font-size: 13px; color: var(--primary); font-weight: 600; text-decoration: none;">New &rarr;</a>
        </div>
        <div>
            {% for t in triages[:4] %}
            <div style="padding: 12px; border-radius: 8px; background: #F8FAFC; border: 1px solid var(--border); margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="font-size: 13.5px; color: #0F172A;">{{ t.patient_name }}</strong>
                    {% if 'Urgent' in t.acuity_level %}
                        <span class="badge badge-danger">{{ t.acuity_level }}</span>
                    {% else %}
                        <span class="badge badge-success">{{ t.acuity_level }}</span>
                    {% endif %}
                </div>
                <p style="font-size: 12px; color: #475569; margin-bottom: 6px;">{{ t.symptoms }}<p>
                <div style="font-size: 11px; color: var(--primary); font-weight: 600;">&#10148; Action: {{ t.recommended_action }}</div>
            </div>
            {% else %}
            <p style="font-size: 13px; color: #64748B; text-align: center; padding: 20px 0;">No triage records yet.</p>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
"""
    files["templates/dashboard.html"] = dash_tpl.replace("__PROJECT_NAME__", project_name)

    # templates/appointments.html
    appts_tpl = """{% extends "base.html" %}
{% block title %}Appointment Management — __PROJECT_NAME__{% endblock %}
{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <div>
        <h2 style="font-size: 24px; font-weight: 800; color: #0F172A; margin-bottom: 4px;">Appointment Scheduling &amp; Allocation</h2>
        <p style="font-size: 14px; color: #64748B;">Autonomous appointment booking powered by AppointmentAgent.</p>
    </div>
</div>

<div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
    <div class="card">
        <h3 class="card-title">Schedule Master Roster</h3>
        <table class="table">
            <thead>
                <tr>
                    <th>Patient</th>
                    <th>Doctor</th>
                    <th>Department</th>
                    <th>Date &amp; Slot</th>
                    <th>Reason</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for a in appointments %}
                <tr>
                    <td><strong>{{ a.patient_name or 'Outpatient' }}</strong></td>
                    <td>{{ a.doctor_name }}</td>
                    <td><span class="badge badge-primary">{{ a.department }}</span></td>
                    <td>{{ a.appointment_date }} {{ a.time_slot }}</td>
                    <td style="font-size: 12px; color: #475569;">{{ a.reason }}</td>
                    <td><span class="badge badge-success">{{ a.status }}</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h3 class="card-title">&#128197; Quick Booking</h3>
        <p class="card-subtitle">Automated specialist matching and conflict resolution.</p>
        <form method="POST" action="{{ url_for('appointments') }}">
            <div style="margin-bottom: 12px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Select Patient</label>
                <select name="patient_id" class="form-input">
                    {% for p in patients %}
                        <option value="{{ p.id }}">{{ p.full_name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Department Specialty</label>
                <select name="department" class="form-input">
                    <option value="Cardiology">Cardiology</option>
                    <option value="Neurology">Neurology</option>
                    <option value="Orthopedics">Orthopedics</option>
                    <option value="Endocrinology">Endocrinology</option>
                    <option value="General Medicine">General Medicine</option>
                </select>
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Doctor</label>
                <input type="text" name="doctor_name" value="Dr. Evelyn Reed, MD" class="form-input">
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Date</label>
                <input type="date" name="appointment_date" value="2026-10-27" class="form-input">
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Time Slot</label>
                <select name="time_slot" class="form-input">
                    <option value="09:00 AM">09:00 AM</option>
                    <option value="10:30 AM">10:30 AM</option>
                    <option value="02:00 PM">02:00 PM</option>
                    <option value="03:45 PM">03:45 PM</option>
                </select>
            </div>
            <div style="margin-bottom: 16px;">
                <label style="display: block; font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 4px;">Clinical Reason</label>
                <input type="text" name="reason" placeholder="e.g. Follow-up consultation" class="form-input" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%;">Confirm &amp; Dispatch Alert</button>
        </form>
    </div>
</div>
{% endblock %}
"""
    files["templates/appointments.html"] = appts_tpl.replace("__PROJECT_NAME__", project_name)

    # templates/triage.html
    triage_tpl = """{% extends "base.html" %}
{% block title %}AI Clinical Triage &amp; Intake — __PROJECT_NAME__{% endblock %}
{% block content %}
<div style="margin-bottom: 24px;">
    <h2 style="font-size: 24px; font-weight: 800; color: #0F172A; margin-bottom: 4px;">Autonomous AI Clinical Intake &amp; Triage</h2>
    <p style="font-size: 14px; color: #64748B;">Multi-agent system evaluating symptoms, vital signs, ESI acuity, and auto-dispatching referrals.</p>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
    <div class="card">
        <h3 class="card-title">&#9889; Patient Intake &amp; Vitals Assessment</h3>
        <p class="card-subtitle">Intake data is parsed by DocumentAgent and evaluated by WorkflowAgent.</p>
        <form method="POST" action="{{ url_for('triage') }}">
            <div style="margin-bottom: 14px;">
                <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Patient</label>
                <select name="patient_id" class="form-input">
                    {% for p in patients %}
                        <option value="{{ p.id }}">{{ p.full_name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div style="margin-bottom: 14px;">
                <label style="display: block; font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 6px;">Chief Complaints &amp; Symptoms</label>
                <textarea name="symptoms" rows="3" class="form-input" placeholder="e.g. Patient presents with acute chest pain, shortness of breath, and diaphoresis..." required>Sudden chest tightness, elevated pulse, mild dyspnea after moderate activity</textarea>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 4px;">Heart Rate (bpm)</label>
                    <input type="number" name="hr" value="106" class="form-input" required>
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 4px;">Blood Pressure</label>
                    <input type="text" name="bp" value="142/92" class="form-input" required>
                </div>
                <div>
                    <label style="display: block; font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 4px;">SpO2 (%)</label>
                    <input type="number" name="spo2" value="94" class="form-input" required>
                </div>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px;">Run Multi-Agent Clinical Orchestration</button>
        </form>
    </div>

    <div>
        {% if result %}
        <div class="card" style="border: 2px solid var(--primary); background: #F0FDF4; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                <span class="badge badge-success">&#10003; {{ result.status }}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 700;">{{ result.workflow_id }}</span>
            </div>
            <h3 style="font-size: 18px; font-weight: 700; color: #0F172A; margin-bottom: 8px;">Acuity: {{ result.acuity_level }}</h3>
            <p style="font-size: 13.5px; color: #334155; margin-bottom: 12px;">
                <strong>Assigned Specialty:</strong> {{ result.recommended_department }}<br>
                <strong>Attending Physician:</strong> {{ result.assigned_doctor }}<br>
                <strong>Danger Score:</strong> {{ result.danger_score }} / 100
            </p>
            <div style="background: #FFFFFF; padding: 12px; border-radius: 6px; border: 1px solid #D1D5DB; font-size: 12.5px; color: #475569;">
                &#9989; <strong>Autonomous Action:</strong> Auto-scheduled appointment #{{ result.appointment_id }} and sent stat pager notification to clinical floor.
            </div>
        </div>
        {% endif %}

        <div class="card">
            <h3 class="card-title">Recent Triage Records</h3>
            {% for t in triages %}
            <div style="padding: 10px 0; border-bottom: 1px solid var(--border);">
                <div style="display: flex; justify-content: space-between;">
                    <strong style="font-size: 13px;">{{ t.patient_name }}</strong>
                    <span style="font-size: 11px; font-weight: 700; color: #DC2626;">{{ t.acuity_level }}</span>
                </div>
                <div style="font-size: 12px; color: #64748B;">{{ t.symptoms[:80] }}...</div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
"""
    files["templates/triage.html"] = triage_tpl.replace("__PROJECT_NAME__", project_name)

    # templates/records.html
    records_tpl = """{% extends "base.html" %}
{% block title %}EHR Patient Directory — __PROJECT_NAME__{% endblock %}
{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <div>
        <h2 style="font-size: 24px; font-weight: 800; color: #0F172A; margin-bottom: 4px;">Electronic Health Records (EHR)</h2>
        <p style="font-size: 14px; color: #64748B;">Clinical records, patient profiles, and medical histories.</p>
    </div>
</div>

<div class="card">
    <table class="table">
        <thead>
            <tr>
                <th>ID</th>
                <th>Patient Name</th>
                <th>DOB / Gender</th>
                <th>Blood Group</th>
                <th>Contact</th>
                <th>Chronic Conditions</th>
                <th>Allergies</th>
            </tr>
        </thead>
        <tbody>
            {% for p in patients %}
            <tr>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 12px;">#PT-{{ p.id }}</td>
                <td><strong>{{ p.full_name }}</strong></td>
                <td>{{ p.dob }} ({{ p.gender }})</td>
                <td><span class="badge badge-primary">{{ p.blood_group }}</span></td>
                <td style="font-size: 12px;">{{ p.phone }}<br><span style="color: #64748B;">{{ p.email }}</span></td>
                <td style="font-size: 12px; color: #334155;">{{ p.medical_history or 'None' }}</td>
                <td style="font-size: 12px; color: #DC2626; font-weight: 600;">{{ p.allergies or 'None' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""
    files["templates/records.html"] = records_tpl.replace("__PROJECT_NAME__", project_name)

    # static/css/style.css
    files["static/css/style.css"] = f""":root {{
    --primary: {primary_color};
    --primary-hover: #047857;
    --secondary: {secondary_color};
    --bg: {bg_color};
    --card-bg: #FFFFFF;
    --border: #E2E8F0;
    --text: #0F172A;
    --text-muted: #64748B;
    --success: #10B981;
    --danger: #EF4444;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--bg);
    color: var(--text);
    line-height: 1.5;
}}

.navbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #FFFFFF;
    padding: 14px 32px;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 50;
}}

.brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    color: #0F172A;
    font-weight: 800;
    font-size: 17px;
}}

.brand-badge {{
    background: #ECFDF5;
    color: var(--primary);
    border: 1px solid #A7F3D0;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}

.nav-links {{
    display: flex;
    align-items: center;
    gap: 20px;
}}

.nav-links a {{
    text-decoration: none;
    color: #475569;
    font-size: 13.5px;
    font-weight: 500;
    transition: color 0.15s ease;
}}

.nav-links a:hover {{
    color: var(--primary);
}}

.main-content {{
    max-width: 1200px;
    margin: 32px auto;
    padding: 0 24px;
    min-height: calc(100vh - 160px);
}}

.card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}

.card-title {{
    font-size: 16px;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 6px;
}}

.card-subtitle {{
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 16px;
}}

.grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}}

.stat-card {{
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
}}

.stat-label {{
    font-size: 12.5px;
    color: var(--text-muted);
    font-weight: 500;
    display: block;
    margin-bottom: 4px;
}}

.stat-val {{
    font-size: 26px;
    font-weight: 800;
    color: #0F172A;
    margin-bottom: 4px;
}}

.btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s ease;
}}

.btn-primary {{
    background: var(--primary);
    color: #FFFFFF;
}}

.btn-primary:hover {{
    background: var(--primary-hover);
}}

.btn-secondary {{
    background: #FFFFFF;
    color: #334155;
    border-color: var(--border);
}}

.btn-secondary:hover {{
    background: #F1F5F9;
}}

.form-input {{
    width: 100%;
    padding: 9px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    font-size: 13px;
    color: #0F172A;
    background: #FFFFFF;
    outline: none;
}}

.form-input:focus {{
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.2);
}}

.table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}

.table th {{
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    color: #64748B;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}

.table td {{
    padding: 12px;
    border-bottom: 1px solid var(--border);
}}

.badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11.5px;
    font-weight: 600;
}}

.badge-primary {{
    background: #EFF6FF;
    color: #2563EB;
}}

.badge-success {{
    background: #ECFDF5;
    color: #059669;
}}

.badge-danger {{
    background: #FEF2F2;
    color: #DC2626;
}}

.auth-card {{
    max-width: 420px;
    margin: 40px auto;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}}

.flash-container {{
    max-width: 1200px;
    margin: 16px auto 0 auto;
    padding: 0 24px;
}}

.flash-msg {{
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 13px;
    margin-bottom: 8px;
}}

.flash-success {{
    background: #ECFDF5;
    color: #065F46;
    border: 1px solid #A7F3D0;
}}

.flash-error {{
    background: #FEF2F2;
    color: #991B1B;
    border: 1px solid #FECACA;
}}

.footer {{
    text-align: center;
    padding: 24px;
    font-size: 12px;
    color: #94A3B8;
    border-top: 1px solid var(--border);
    background: #FFFFFF;
}}
"""

    # static/js/main.js
    files["static/js/main.js"] = """// Clinical Client Interactivity
console.log("Healthcare Multi-Agent AI system initialized.");
"""

    # app.py (Mandatory Flask entry point adhering strictly to create_app factory)
    app_py_code = """\"\"\"
__PROJECT_NAME__ — Autonomous Server Entry Point
Healthcare Multi-Agent AI Workflow Automation
Generated by DevGuardian AI
\"\"\"
import os
import sys
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import Config
from database.db import init_db, get_db
from database.models import PatientModel, AppointmentModel, TriageModel, DocumentModel
from agents.appointment_agent import AppointmentAgent
from agents.document_agent import DocumentAgent
from agents.workflow_agent import WorkflowAgent
from services.appointment_service import AppointmentService
from services.notification_service import NotificationService
from services.triage_service import TriageService

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize SQLite tables
    init_db()

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in to access clinical console.", "error")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("base.html", content="<div class='card' style='text-align:center;'><h2>404 - Page Not Found</h2><p>Requested clinical resource could not be found.</p></div>"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("base.html", content="<div class='card' style='text-align:center;'><h2>500 - Server Error</h2><p>An unexpected clinical workflow error occurred.</p></div>"), 500

    @app.route("/")
    def index():
        return render_template("landing.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cur.fetchone()
            conn.close()
            if user and user["password_hash"] == password:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["full_name"] = user["full_name"]
                flash(f"Welcome back, {user['full_name']}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid clinician credentials. Try doctor / doctor123", "error")
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if full_name and username and password:
                conn = get_db()
                try:
                    with conn:
                        conn.execute("INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)",
                                     (username, password, full_name))
                    flash("Staff profile registered successfully. Please log in.", "success")
                    return redirect(url_for("login"))
                except Exception:
                    flash("Username already registered.", "error")
                finally:
                    conn.close()
            else:
                flash("All profile fields are required.", "error")
        return render_template("signup.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Signed out of clinical console.", "success")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    def dashboard():
        patients = PatientModel.get_all()
        appointments = AppointmentModel.get_all()
        triages = TriageModel.get_recent(5)
        return render_template("dashboard.html", patients=patients, appointments=appointments, triages=triages)

    @app.route("/appointments", methods=["GET", "POST"])
    def appointments():
        if request.method == "POST":
            patient_id = int(request.form.get("patient_id", 1))
            doctor = request.form.get("doctor_name", "Dr. Evelyn Reed, MD")
            department = request.form.get("department", "General Medicine")
            date_str = request.form.get("appointment_date", "2026-10-27")
            time_slot = request.form.get("time_slot", "09:00 AM")
            reason = request.form.get("reason", "Consultation")
            AppointmentService.book_new_appointment(patient_id, doctor, department, date_str, time_slot, reason)
            flash("Appointment successfully registered and physician schedule locked.", "success")
            return redirect(url_for("appointments"))
        appts = AppointmentService.list_appointments()
        patients = PatientModel.get_all()
        return render_template("appointments.html", appointments=appts, patients=patients)

    @app.route("/triage", methods=["GET", "POST"])
    def triage():
        result = None
        if request.method == "POST":
            patient_id = int(request.form.get("patient_id", 1))
            symptoms = request.form.get("symptoms", "")
            hr = float(request.form.get("hr", 75))
            bp = request.form.get("bp", "120/80")
            spo2 = float(request.form.get("spo2", 98))
            vitals = {"hr": hr, "bp": bp, "spo2": spo2}
            result = WorkflowAgent.process_patient_intake(patient_id, symptoms, vitals)
            flash(f"Clinical intake processed: {result['acuity_level']}", "success")
        patients = PatientModel.get_all()
        triages = TriageModel.get_recent(10)
        return render_template("triage.html", patients=patients, triages=triages, result=result)

    @app.route("/records")
    def records():
        patients = PatientModel.get_all()
        docs = DocumentModel.get_all()
        return render_template("records.html", patients=patients, docs=docs)

    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "__PROJECT_NAME__",
            "database": "connected",
            "agents_active": 3
        })

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", __ASSIGNED_PORT__))
    app.run(host="127.0.0.1", port=port, debug=False)
"""
    files["app.py"] = app_py_code.replace("__PROJECT_NAME__", project_name).replace("__ASSIGNED_PORT__", str(assigned_port))

    # tests/test_app.py
    test_py_code = """\"\"\"Unit and Integration Tests for __PROJECT_NAME__\"\"\"
import pytest
from app import app
from agents.appointment_agent import AppointmentAgent
from agents.document_agent import DocumentAgent
from agents.workflow_agent import WorkflowAgent
from database.models import PatientModel, AppointmentModel

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_root_and_landing(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"__PROJECT_NAME__" in res.data or b"Healthcare" in res.data

def test_health_check_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert "service" in data

def test_login_page_renders(client):
    res = client.get("/login")
    assert res.status_code == 200
    assert b"Clinician Portal" in res.data or b"Sign In" in res.data

def test_appointment_specialist_agent():
    match = AppointmentAgent.match_specialist("Severe chest tightness and palpitations")
    assert match["department"] == "Cardiology"
    assert "Evelyn Reed" in match["recommended_physician"]

def test_document_entity_agent():
    res = DocumentAgent.extract_clinical_entities("Patient has hypertension and asthma, taking Lisinopril 20mg.")
    assert "Hypertension" in res["extracted_conditions"]
    assert "Asthma" in res["extracted_conditions"]
    assert len(res["detected_medications"]) >= 1

def test_workflow_orchestration_intake():
    res = WorkflowAgent.process_patient_intake(
        patient_id=1,
        symptoms="Irregular pulse and fatigue",
        vitals={"hr": 105, "spo2": 97, "bp": "140/90", "temp": 37.0}
    )
    assert res["status"] == "Orchestrated Successfully"
    assert "Urgent" in res["acuity_level"]
    assert res["recommended_department"] == "Cardiology"
"""
    files["tests/test_app.py"] = test_py_code.replace("__PROJECT_NAME__", project_name)

    # requirements.txt
    files["requirements.txt"] = "Flask>=3.0.0\nWerkzeug>=3.0.0\npytest>=8.0.0\npython-dotenv>=1.0.0\nrequests>=2.31.0\n"

    # README.md
    files["README.md"] = f"""# {project_name}

An autonomous healthcare multi-agent AI system for hospital intake, triage, and automated appointment scheduling.
Generated by DevGuardian AI.

## Project Structure
- `app.py`: Mandatory Flask application entry point with `create_app()` factory.
- `config.py`: Secure application configuration.
- `database/`: SQLite database persistence for patients, appointments, and triage records.
- `models/`: Patient and Appointment domain models.
- `agents/`: Autonomous AI agents:
  - `appointment_agent.py`: Specialist matching & conflict-free scheduling.
  - `document_agent.py`: Clinical NLP and EHR summary extraction.
  - `workflow_agent.py`: Multi-agent patient intake and triage orchestrator.
- `services/`: Business services for appointments, notifications, and emergency triage.
- `templates/`: Clinical portals, triage calculators, and dashboards.
- `static/`: Clinical CSS stylesheets and assets.
- `tests/test_app.py`: Unit and integration test assertions.

## Running the Application
```bash
python app.py
```
Default local URL: `http://127.0.0.1:{assigned_port}`
Clinician Login: `doctor` / `doctor123`
"""

    # .env.example
    files[".env.example"] = f"""# {project_name} Environment Configuration
PORT={assigned_port}
SECRET_KEY=replace-with-a-secure-secret-key
FLASK_ENV=development
DATABASE_URL=sqlite:///instance/{slug}.db
"""

    # .gitignore
    files[".gitignore"] = """__pycache__/
*.pyc
instance/*.db
.env
.pytest_cache/
"""

    return files
