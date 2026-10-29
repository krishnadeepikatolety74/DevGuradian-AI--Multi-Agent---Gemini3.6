"""
Test Suite — Cute & Relaxing Run All Agents Modal & Progress Tracking System
DevGuardian AI — Autonomous Software Project Manager
"""

import os
import sys
import json
import shutil
import unittest
import time
from unittest.mock import patch
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
from services.agent_metrics_service import AgentMetricsService
from services.workflow_tracker import (
    start_workflow_in_background,
    get_workflow_status_payload,
    is_workflow_running,
    retry_failed_agents_in_background
)
from services.workspace_manager import GENERATED_PROJECTS_DIR


class AgentsModalSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        init_db()

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'agents_modal_tester@devguardian.local'")
            row = cursor.fetchone()
            if row:
                cls.user_id = row['id']
            else:
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role)
                    VALUES ('Agents Tester', 'agents_modal_tester@devguardian.local', 'hash123', 'Developer')
                """)
                cls.user_id = cursor.lastrowid

            # Create another user to test unauthorized access
            cursor.execute("SELECT id FROM users WHERE email = 'unauthorized_tester@devguardian.local'")
            row2 = cursor.fetchone()
            if row2:
                cls.other_user_id = row2['id']
            else:
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role)
                    VALUES ('Other Tester', 'unauthorized_tester@devguardian.local', 'hash123', 'Developer')
                """)
                cls.other_user_id = cursor.lastrowid
        conn.close()

        cls.project_id = 'test_agents_modal_proj'
        cls.project_dir = GENERATED_PROJECTS_DIR / cls.project_id
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir, ignore_errors=True)
        cls.project_dir.mkdir(parents=True, exist_ok=True)

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            cursor.execute('DELETE FROM agent_executions WHERE project_id = ?', (cls.project_id,))
            cursor.execute("""
                INSERT INTO projects (id, user_id, name, description, status, language)
                VALUES (?, ?, 'TaskFlow AI', 'An autonomous project for agent modal testing', 'in_progress', 'Python Flask')
            """, (cls.project_id, cls.user_id))
        conn.close()

        # Initialize agent executions for the project
        AgentMetricsService.sync_or_heal_project_agent_executions(cls.project_id)

    @classmethod
    def tearDownClass(cls):
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir, ignore_errors=True)
        conn = get_standalone_db()
        with conn:
            conn.execute('DELETE FROM agent_executions WHERE project_id = ?', (cls.project_id,))
            conn.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            conn.execute('DELETE FROM users WHERE id IN (?, ?)', (cls.user_id, cls.other_user_id))
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['user_email'] = 'agents_modal_tester@devguardian.local'
            sess['user_name'] = 'Agents Tester'

    def test_css_design_tokens_and_aesthetic(self):
        """Verifies pastel palette, robot mascot styles, shimmer, and reduced motion in agents_modal.css."""
        css_path = ROOT_DIR / 'static' / 'css' / 'agents_modal.css'
        self.assertTrue(css_path.exists(), "agents_modal.css must exist in static/css")
        content = css_path.read_text(encoding='utf-8')

        # Check pastel tokens
        self.assertIn('--agents-lavender-100', content)
        self.assertIn('--agents-blue-100', content)
        self.assertIn('--agents-pink-100', content)

        # Check modal, mascot animations & keyframes
        self.assertIn('.agents-modal-backdrop', content)
        self.assertIn('.agents-progress-bar', content)
        self.assertIn('@keyframes agentsFloat', content)
        self.assertIn('@keyframes agentsShimmer', content)
        self.assertIn('@keyframes agentsDotBounce', content)

        # Check accessibility / reduced motion
        self.assertIn('@media (prefers-reduced-motion: reduce)', content)

    def test_html_modal_component_structure(self):
        """Verifies modal template structure, friendly headings, mascot SVG, and action buttons."""
        tmpl_path = ROOT_DIR / 'templates' / 'components' / 'agents_modal.html'
        self.assertTrue(tmpl_path.exists(), "agents_modal.html must exist in templates/components")
        content = tmpl_path.read_text(encoding='utf-8')

        # Headings and subtitles
        self.assertIn("Your AI Team Is Getting to Work! ✨", content)
        self.assertIn("Your agents are collaborating to build something amazing.", content)
        self.assertIn("Your AI Team Has Finished! 🎉", content)
        self.assertIn("A Little Hiccup! Let's Fix It. 💜", content)

        # Mascot SVG with laptop and sparkles
        self.assertIn('id="agentsRobotMascotSvg"', content)
        self.assertIn('id="agentsRobotGroup"', content)
        self.assertIn('id="agentsLaptopGroup"', content)

        # Working action buttons
        self.assertIn('View Agent Reports', content)
        self.assertIn('View Project Files', content)
        self.assertIn('Run Project', content)
        self.assertIn('View Logs', content)
        self.assertIn('Retry Failed Agents', content)

    def test_base_template_integration(self):
        """Verifies that base.html includes agents_modal.css and agents_modal.html."""
        base_path = ROOT_DIR / 'templates' / 'base.html'
        content = base_path.read_text(encoding='utf-8')

        self.assertIn('agents_modal.css', content)
        self.assertIn('components/agents_modal.html', content)

    def test_workflow_tracker_status_payload(self):
        """Verifies accurate status payload computation for all configured agents."""
        payload = get_workflow_status_payload(self.project_id)

        self.assertEqual(payload['project_id'], self.project_id)
        self.assertEqual(payload['project_name'], 'TaskFlow AI')
        self.assertEqual(payload['total_count'], 8)
        self.assertIn('progress_pct', payload)
        self.assertIn('live_message', payload)
        self.assertIn('agents', payload)

        agents = payload['agents']
        self.assertEqual(len(agents), 8)

        # Expected agents in order
        expected_agents = [
            "Requirement Analysis Agent",
            "Architecture Agent",
            "Coding Agent",
            "Code Review Agent",
            "Deployment Agent",
            "Testing Agent",
            "Security Agent",
            "Project Manager / Orchestrator"
        ]
        agent_names = [a['agent_name'] for a in agents]
        for expected in expected_agents:
            self.assertIn(expected, agent_names)

        # Check properties of each agent
        for a in agents:
            self.assertIn(a['status'], ['waiting', 'in_progress', 'completed', 'failed', 'skipped'])
            self.assertIn('assigned_task', a)
            self.assertIn('actual_work', a)
            self.assertIn('files_count', a)
            self.assertIn('validation_results', a)

    def test_run_all_agents_ajax_start_and_duplicate_prevention(self):
        """Verifies clicking Run All Agents via AJAX starts background execution and prevents duplicates."""
        with patch('services.workflow_service.run_full_workflow', side_effect=lambda pid, api_key=None: time.sleep(1.0)):
            # 1. Start execution via AJAX
            res = self.client.post(
                f"/projects/{self.project_id}/run",
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn(data.get("status"), ["started", "already_running"])
            self.assertEqual(data.get("project_name"), "TaskFlow AI")
            self.assertEqual(data.get("total_agents"), 8)

            # 2. Repeated click immediately should return already_running, avoiding duplicate job
            res_dup = self.client.post(
                f"/projects/{self.project_id}/run",
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            self.assertEqual(res_dup.status_code, 200)
            data_dup = res_dup.get_json()
            self.assertEqual(data_dup.get("status"), "already_running")
            self.assertTrue(data_dup.get("is_running"))

    def test_workflow_status_rest_endpoint(self):
        """Verifies GET /api/projects/<project_id>/workflow-status returns real-time progress."""
        res = self.client.get(f"/api/projects/{self.project_id}/workflow-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertEqual(data["project_id"], self.project_id)
        self.assertEqual(data["project_name"], "TaskFlow AI")
        self.assertIsInstance(data["progress_pct"], int)
        self.assertIsInstance(data["completed_count"], int)
        self.assertEqual(data["total_count"], 8)
        self.assertIn("live_message", data)
        self.assertIn("agents", data)
        self.assertIn("success_summary", data)

    def test_workflow_stream_sse_endpoint(self):
        """Verifies GET /projects/<project_id>/workflow-stream delivers SSE stream."""
        res = self.client.get(f"/projects/{self.project_id}/workflow-stream")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.content_type)

        # Read the first event chunk
        iterator = res.iter_encoded()
        first_chunk = next(iterator).decode('utf-8')
        self.assertIn("data: ", first_chunk)

        # Extract and validate json
        json_str = first_chunk.replace("data: ", "").strip()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["project_id"], self.project_id)
        self.assertEqual(parsed["total_count"], 8)

    def test_workflow_retry_endpoint(self):
        """Verifies POST /projects/<project_id>/workflow-retry resets failed agents safely."""
        with patch('services.workflow_service.run_full_workflow', return_value=None):
            # Mark an agent as failed in the database
            conn = get_standalone_db()
            with conn:
                conn.execute("""
                    UPDATE agent_executions
                    SET status = 'failed', error_message = 'Simulated syntax exception during testing'
                    WHERE project_id = ? AND agent_key = 'coding'
                """, (self.project_id,))
            conn.close()

            # Trigger retry
            res = self.client.post(
                f"/projects/{self.project_id}/workflow-retry",
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertIn(data.get("status"), ["retrying", "already_running"])

            # Check DB status: coding should now be 'pending', 'running', or 'completed'
            conn = get_standalone_db()
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM agent_executions WHERE project_id = ? AND agent_key = 'coding'", (self.project_id,))
                row = cursor.fetchone()
                self.assertIn(row['status'], ['pending', 'running', 'completed'])
            conn.close()

    def test_authorization_protection(self):
        """Verifies unauthorized users cannot access status or execute workflows."""
        # 1. Unauthenticated client
        unauth_client = app.test_client()
        res_unauth = unauth_client.get(f"/api/projects/{self.project_id}/workflow-status")
        self.assertEqual(res_unauth.status_code, 401)
        self.assertTrue(res_unauth.is_json)

        # 2. Authenticated as different user
        other_client = app.test_client()
        with other_client.session_transaction() as sess:
            sess['user_id'] = self.other_user_id
            sess['user_email'] = 'unauthorized_tester@devguardian.local'
            sess['user_role'] = 'Developer'

        res_other = other_client.get(f"/api/projects/{self.project_id}/workflow-status")
        self.assertEqual(res_other.status_code, 403)

        res_other_run = other_client.post(
            f"/projects/{self.project_id}/run",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(res_other_run.status_code, 403)

    def test_independence_of_run_project_and_run_all_agents(self):
        """Verifies Run All Agents and Run Project remain completely independent."""
        # Run All Agents endpoint triggers workflow tracker
        res_agents = self.client.get(f"/api/projects/{self.project_id}/workflow-status")
        self.assertEqual(res_agents.status_code, 200)
        self.assertIn("agents", res_agents.get_json())

        # Run Project launch status endpoint queries runtime process
        res_runtime = self.client.get(f"/projects/{self.project_id}/launch-status")
        self.assertEqual(res_runtime.status_code, 200)
        runtime_data = res_runtime.get_json()
        self.assertIn("ready", runtime_data)
        self.assertIn("state", runtime_data)
        self.assertIn("local_url", runtime_data)

    def test_state_persistence_across_page_refresh(self):
        """Verifies agent state is stored in the database and recovered accurately after refresh."""
        conn = get_standalone_db()
        with conn:
            # Set requirement and architecture to completed
            conn.execute("""
                UPDATE agent_executions
                SET status = 'completed', files_created = 3, files_modified = 1
                WHERE project_id = ? AND agent_key IN ('requirement', 'architecture')
            """, (self.project_id,))
        conn.close()

        # Query status API as if refreshing the page
        res = self.client.get(f"/api/projects/{self.project_id}/workflow-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertGreaterEqual(data["completed_count"], 2)
        self.assertGreaterEqual(data["progress_pct"], 25)

        # Check stage 1 agent details
        stage1 = next(a for a in data["agents"] if a["agent_key"] == "requirement")
        self.assertEqual(stage1["status"], "completed")


if __name__ == '__main__':
    unittest.main()
