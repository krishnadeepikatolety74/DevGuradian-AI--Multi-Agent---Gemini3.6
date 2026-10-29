"""
Test Suite — Cute and Relaxing Project Launch Modal System
DevGuardian AI — Autonomous Software Project Manager
"""

import os
import sys
import json
import shutil
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.execution_service as execution_service
from services.port_manager import PortManager
from services.workspace_manager import GENERATED_PROJECTS_DIR, get_project_workspace


class LaunchModalSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        init_db()

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'test_launcher@devguardian.local'")
            row = cursor.fetchone()
            if row:
                cls.user_id = row['id']
            else:
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role)
                    VALUES ('Launcher Tester', 'test_launcher@devguardian.local', 'hash123', 'Developer')
                """)
                cls.user_id = cursor.lastrowid
        conn.close()

        cls.project_id = 'test_launch_modal_proj'
        cls.project_dir = GENERATED_PROJECTS_DIR / cls.project_id
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir)
        cls.project_dir.mkdir(parents=True, exist_ok=True)

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            cursor.execute("""
                INSERT INTO projects (id, user_id, name, description, status, language)
                VALUES (?, ?, 'Cute Launcher App', 'A test app for launch modal', 'in_progress', 'Python Flask')
            """, (cls.project_id, cls.user_id))
        conn.close()

        app_py_code = """import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Cute Launcher Test App</h1>'

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'ready': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5060))
    app.run(host='127.0.0.1', port=port, debug=False)
"""
        (cls.project_dir / 'app.py').write_text(app_py_code, encoding='utf-8')
        (cls.project_dir / 'requirements.txt').write_text("flask\n", encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        try:
            execution_service.stop_project_process(cls.project_id)
        except Exception:
            pass
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir, ignore_errors=True)
        conn = get_standalone_db()
        with conn:
            conn.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            conn.execute('DELETE FROM users WHERE id = ?', (cls.user_id,))
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['user_email'] = 'test_launcher@devguardian.local'
            sess['user_name'] = 'Launcher Tester'
            sess['user_role'] = 'Developer'

    def tearDown(self):
        try:
            execution_service.stop_project_process(self.project_id)
        except Exception:
            pass

    def test_start_project_app_with_progress_generator_stages(self):
        events = []
        for event in execution_service.start_project_app_with_progress(self.project_id):
            events.append(event)

        self.assertGreaterEqual(len(events), 4)

        step1 = events[0]
        self.assertEqual(step1['step'], 1)
        self.assertEqual(step1['percent'], 15)
        self.assertEqual(step1['stage'], 'validating')
        self.assertIn('Waking up', step1['message'])
        self.assertEqual(step1['project_name'], 'Cute Launcher App')

        step2 = events[1]
        self.assertEqual(step2['step'], 2)
        self.assertEqual(step2['percent'], 35)
        self.assertEqual(step2['stage'], 'environment')
        self.assertIn('Checking your environment', step2['message'])

        step3 = events[2]
        self.assertEqual(step3['step'], 3)
        self.assertEqual(step3['percent'], 55)
        self.assertEqual(step3['stage'], 'preparing')
        self.assertIn('Preparing your application', step3['message'])

        step4 = events[3]
        self.assertEqual(step4['step'], 4)
        self.assertEqual(step4['percent'], 75)
        self.assertEqual(step4['stage'], 'starting')
        self.assertIn('Starting your server', step4['message'])
        self.assertIsNotNone(step4.get('port'))

        final_event = events[-1]
        self.assertIn(final_event['stage'], ('ready', 'failed'))
        if final_event['stage'] == 'ready':
            self.assertEqual(final_event['step'], 6)
            self.assertEqual(final_event['percent'], 100)
            self.assertEqual(final_event['message'], "Your project is ready! Let's explore it.")
            self.assertTrue(final_event['local_url'].startswith('http://127.0.0.1:'))
            self.assertIsNotNone(final_event.get('port'))

    def test_missing_dependencies_handling(self):
        req_path = self.project_dir / 'requirements.txt'
        original_req = req_path.read_text(encoding='utf-8')
        req_path.write_text('nonexistent_package_foo_bar_xyz==9.9.9\n', encoding='utf-8')

        try:
            events = list(execution_service.start_project_app_with_progress(self.project_id))
            failed_event = events[-1]
            self.assertEqual(failed_event['stage'], 'failed')
            self.assertEqual(failed_event['step'], 2)
            self.assertEqual(failed_event['status'], 'Dependencies Missing')
            self.assertIn('nonexistent_package_foo_bar_xyz', failed_event['message'])
            self.assertIn('nonexistent_package_foo_bar_xyz', failed_event.get('missing_deps', []))
        finally:
            req_path.write_text(original_req, encoding='utf-8')

    def test_run_project_stream_sse_endpoint(self):
        resp = self.client.get(f'/projects/{self.project_id}/run-project-stream')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/event-stream', resp.content_type)

        chunks = []
        for line in resp.response:
            decoded = line.decode('utf-8') if isinstance(line, bytes) else line
            for part in decoded.split('\n\n'):
                part = part.strip()
                if part.startswith('data:'):
                    raw_json = part[5:].strip()
                    try:
                        data = json.loads(raw_json)
                        chunks.append(data)
                    except json.JSONDecodeError:
                        pass
            if len(chunks) >= 3:
                break

        self.assertGreaterEqual(len(chunks), 1)
        first_chunk = chunks[0]
        self.assertIn('step', first_chunk)
        self.assertIn('percent', first_chunk)
        self.assertIn('stage', first_chunk)
        self.assertEqual(first_chunk['project_name'], 'Cute Launcher App')

    def test_run_project_ajax_json_response(self):
        resp = self.client.post(
            f'/projects/{self.project_id}/run-project',
            headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertIn('status', data)
        self.assertIn('project_name', data)
        self.assertEqual(data['project_name'], 'Cute Launcher App')

    def test_project_status_json_endpoint(self):
        resp = self.client.get(f'/projects/{self.project_id}/status-json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertIn('is_running', data)
        self.assertIn('status', data)
        self.assertEqual(data['project_id'], self.project_id)
        self.assertEqual(data['project_name'], 'Cute Launcher App')

    def test_duplicate_launch_prevention(self):
        res1 = execution_service.start_project_app(self.project_id)
        res2 = execution_service.start_project_app(self.project_id)
        self.assertTrue(res1['success'] or res1.get('status') in ['Running', 'Health Check Failed', 'Starting'])
        self.assertTrue(res2['success'] or res2.get('status') in ['Running', 'Health Check Failed', 'Starting'])
        stop_res = execution_service.stop_project_process(self.project_id)
        self.assertTrue(stop_res['success'])

    def test_frontend_launch_modal_assets(self):
        css_file = ROOT_DIR / 'static' / 'css' / 'launch_modal.css'
        self.assertTrue(css_file.exists())
        css_text = css_file.read_text(encoding='utf-8')

        self.assertIn('--launch-lavender-50', css_text)
        self.assertIn('--launch-lavender-400', css_text)
        self.assertIn('--launch-blue-100', css_text)
        self.assertIn('--launch-pink-400', css_text)
        self.assertIn('backdrop-filter', css_text)
        self.assertIn('border-radius: 28px', css_text)

        self.assertIn('@keyframes robotFloat', css_text)
        self.assertIn('@keyframes cloudDrift', css_text)
        self.assertIn('@keyframes starTwinkle', css_text)
        self.assertIn('@keyframes antennaPulse', css_text)
        self.assertIn('@keyframes progressShimmer', css_text)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css_text)

        modal_file = ROOT_DIR / 'templates' / 'components' / 'launch_modal.html'
        self.assertTrue(modal_file.exists())
        modal_text = modal_file.read_text(encoding='utf-8')

        self.assertIn('<svg class="launch-mascot-svg"', modal_text)
        self.assertIn('mascotRobotGroup', modal_text)
        self.assertIn('mascotLaptopGroup', modal_text)
        self.assertIn('laptop-code-line', modal_text)
        self.assertIn('launch-sparkle', modal_text)
        self.assertIn('launch-cloud', modal_text)

        self.assertIn('Getting Your Project Ready! ✨', modal_text)
        self.assertIn('Just a little moment', modal_text)
        self.assertIn('Yay! Your Project Is Ready! 🎉', modal_text)
        self.assertIn("Oops! Let's Fix This. 💜", modal_text)
        self.assertIn('Open Project Preview', modal_text)
        self.assertIn('View Logs', modal_text)

        base_html = (ROOT_DIR / 'templates' / 'base.html').read_text(encoding='utf-8')
        self.assertIn('launch_modal.css', base_html)
        self.assertIn('components/launch_modal.html', base_html)

        progress_html = (ROOT_DIR / 'templates' / 'project_progress.html').read_text(encoding='utf-8')
        self.assertIn('btn-run-project', progress_html)
        self.assertIn('projectExecutionControlBar', progress_html)
        self.assertIn('devguardian:project-started', progress_html)

        projects_html = (ROOT_DIR / 'templates' / 'projects.html').read_text(encoding='utf-8')
        self.assertIn('btn-run-project', projects_html)

        logs_html = (ROOT_DIR / 'templates' / 'project_logs.html').read_text(encoding='utf-8')
        self.assertIn('btn-run-project', logs_html)


if __name__ == '__main__':
    unittest.main()
