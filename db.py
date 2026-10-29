import sqlite3
import os
from pathlib import Path
from flask import g

DB_PATH = Path(__file__).resolve().parent / "instance" / "devguardian.db"

def get_db():
    """Get or create SQLite connection for the current Flask request context."""
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(
            str(DB_PATH),
            timeout=20.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        g.db.row_factory = sqlite3.Row
        # Enable foreign key constraint enforcement in SQLite
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 20000")
    return g.db

def close_db(e=None):
    """Close SQLite connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()

def get_standalone_db(timeout: float = 20.0):
    """Get SQLite connection outside Flask request context (e.g. CLI or background tasks)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=timeout,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 20000")
    return conn

def init_db():
    """Create all tables and seed default agents if they do not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()

        # 1. Users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'Developer',
                gemini_api_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 1b. OAuth Provider Associations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_user_id TEXT NOT NULL,
                provider_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(provider, provider_user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider_uid ON oauth_accounts(provider, provider_user_id)")

        # 2. Projects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                app_type TEXT DEFAULT 'Web App',
                language TEXT DEFAULT 'Python Flask',
                tech_preferences TEXT,
                current_stage TEXT DEFAULT 'requirements',
                status TEXT DEFAULT 'in_progress',
                generation_mode TEXT DEFAULT 'both',
                workspace_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id)")

        # 3. Agents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT NOT NULL,
                stage_order INTEGER NOT NULL
            )
        """)

        # 4. Agent Executions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                input_data TEXT,
                output_data TEXT,
                step_logs TEXT,
                error_message TEXT,
                execution_time_ms INTEGER DEFAULT 0,
                task_assigned TEXT,
                work_performed TEXT,
                files_created TEXT,
                files_modified TEXT,
                output_produced TEXT,
                validation_performed TEXT,
                result_status TEXT DEFAULT 'pending',
                accuracy_score REAL,
                accuracy_status TEXT DEFAULT 'Not yet verified',
                task_completion_score REAL,
                validation_pass_rate REAL,
                test_pass_rate REAL,
                requirements_coverage REAL,
                overall_quality_score REAL,
                errors_or_limitations TEXT,
                evidence_json TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_exec_proj ON agent_executions(project_id)")

        # 4b. Project Generation Runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_generation_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                trigger_type TEXT DEFAULT 'manual',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gen_runs_proj ON project_generation_runs(project_id)")

        # 5. Project Files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                file_content TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_files_proj ON project_files(project_id)")

        # 6. Test Results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                total_tests INTEGER DEFAULT 0,
                passed_tests INTEGER DEFAULT 0,
                failed_tests INTEGER DEFAULT 0,
                skipped_tests INTEGER DEFAULT 0,
                test_log TEXT,
                test_details_json TEXT,
                execution_time_ms INTEGER DEFAULT 0,
                overall_result TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)

        # 7. Security Findings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                rule_id TEXT,
                file_path TEXT,
                line_number INTEGER,
                explanation TEXT NOT NULL,
                recommended_fix TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)

        # 8. Code Reviews
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                overall_score INTEGER DEFAULT 8,
                status TEXT DEFAULT 'approved',
                architecture_notes TEXT,
                maintainability_notes TEXT,
                security_notes TEXT,
                recommendations_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)

        # 9. Deployment Records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                dockerfile_content TEXT,
                startup_command TEXT,
                env_vars_json TEXT,
                instructions TEXT,
                readiness_status TEXT DEFAULT 'ready',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)

        # 10. Project Reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                report_title TEXT NOT NULL,
                summary TEXT,
                final_output TEXT,
                pdf_path TEXT,
                structured_data TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)

        # 11. Requirement Traceability
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                req_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT DEFAULT 'Medium',
                acceptance_criteria TEXT,
                related_files TEXT,
                related_tests TEXT,
                verification_method TEXT,
                status TEXT DEFAULT 'Not Verified',
                evidence TEXT,
                failure_details TEXT,
                remaining_work TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_reqs_proj ON project_requirements(project_id)")

        # 12. Project Processes (Execution Service)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                process_type TEXT NOT NULL,
                command TEXT NOT NULL,
                pid INTEGER,
                status TEXT NOT NULL DEFAULT 'running',
                exit_code INTEGER,
                stdout_log TEXT,
                stderr_log TEXT,
                local_url TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stopped_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_proc_proj ON project_processes(project_id)")

        # 13. Project Corrections (Auto-Fix & Retesting)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                component TEXT NOT NULL,
                error_message TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                fix_applied TEXT NOT NULL,
                backup_path TEXT,
                retest_passed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_corr_proj ON project_corrections(project_id)")

        # 14. UI / UX Design Recommendations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ui_recommendations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                explanation TEXT NOT NULL,
                evidence TEXT NOT NULL,
                affected_file TEXT NOT NULL,
                suggested_improvement TEXT NOT NULL,
                expected_benefit TEXT NOT NULL,
                proposed_diff TEXT,
                status TEXT DEFAULT 'pending',
                source TEXT DEFAULT 'rule_based',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                applied_at TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ui_rec_proj ON ui_recommendations(project_id)")

        # 15. AI Chat Messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                image_path TEXT,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_user ON chat_messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_msg_proj ON chat_messages(project_id)")

        # 16. Project Architecture Diagrams
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_architecture (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                diagram_type TEXT NOT NULL DEFAULT 'system',
                diagram_source TEXT,
                png_path TEXT,
                svg_path TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE(project_id, diagram_type)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_arch_proj ON project_architecture(project_id)")

        # 17. Project Documentation (Strict Master Reference DOCX + PDF)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_documentation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                docx_path TEXT NOT NULL,
                pdf_path TEXT,
                template_used TEXT DEFAULT 'CaptionAI_Documentation.docx',
                sections_json TEXT,
                validation_status TEXT DEFAULT 'valid',
                validation_details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE(project_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_doc_proj ON project_documentation(project_id)")

        # 18. Project Activity History / Audit Logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj_act_proj ON project_activity_logs(project_id)")

        # 19. Documentation Assistant Conversations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documentation_conversations (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                last_docx_path TEXT,
                last_pdf_path TEXT,
                last_validation_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_conv_user ON documentation_conversations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_conv_proj ON documentation_conversations(project_id)")

        # 20. Documentation Assistant Chat Messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documentation_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                attachment_path TEXT,
                attachment_name TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES documentation_conversations (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_msg_conv ON documentation_chat_messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_msg_user_proj ON documentation_chat_messages(user_id, project_id)")

        # 21. UI Reference Images (Design Replication Engine)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ui_reference_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                page_name TEXT NOT NULL,
                image_path TEXT NOT NULL,
                original_filename TEXT,
                analysis_json TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ui_ref_proj ON ui_reference_images(project_id)")

        # 22. Agent Timeline Events (Granular Observability)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_timeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT,
                file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_timeline_proj ON agent_timeline_events(project_id)")

        # Safe Schema Migrations for existing tables
        cursor.execute("PRAGMA table_info(projects)")
        existing_proj_cols = {col["name"] for col in cursor.fetchall()}
        if "selected_ide" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN selected_ide TEXT DEFAULT 'vscode'")
        if "ide_custom_path" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN ide_custom_path TEXT")
        if "ui_requirements" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN ui_requirements TEXT")
        if "validation_results" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN validation_results TEXT")
        if "workspace_path" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN workspace_path TEXT")
        if "assigned_port" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN assigned_port INTEGER")
        if "entry_point" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN entry_point TEXT")
        if "generation_mode" not in existing_proj_cols:
            cursor.execute("ALTER TABLE projects ADD COLUMN generation_mode TEXT DEFAULT 'both'")

        cursor.execute("PRAGMA table_info(agent_executions)")
        existing_exec_cols = {col["name"] for col in cursor.fetchall()}
        exec_cols_to_add = [
            ("task_assigned", "TEXT"),
            ("work_performed", "TEXT"),
            ("files_created", "TEXT"),
            ("files_modified", "TEXT"),
            ("output_produced", "TEXT"),
            ("validation_performed", "TEXT"),
            ("result_status", "TEXT DEFAULT 'pending'"),
            ("accuracy_score", "REAL"),
            ("accuracy_status", "TEXT DEFAULT 'Not yet verified'"),
            ("task_completion_score", "REAL"),
            ("validation_pass_rate", "REAL"),
            ("test_pass_rate", "REAL"),
            ("requirements_coverage", "REAL"),
            ("overall_quality_score", "REAL"),
            ("errors_or_limitations", "TEXT"),
            ("evidence_json", "TEXT"),
            ("generation_run_id", "TEXT")
        ]
        for col_name, col_type in exec_cols_to_add:
            if col_name not in existing_exec_cols:
                cursor.execute(f"ALTER TABLE agent_executions ADD COLUMN {col_name} {col_type}")

        cursor.execute("PRAGMA table_info(project_processes)")
        existing_proc_cols = {col["name"] for col in cursor.fetchall()}
        if "port" not in existing_proc_cols:
            cursor.execute("ALTER TABLE project_processes ADD COLUMN port INTEGER")

        cursor.execute("PRAGMA table_info(project_reports)")
        existing_report_cols = {col["name"] for col in cursor.fetchall()}
        if "structured_data" not in existing_report_cols:
            cursor.execute("ALTER TABLE project_reports ADD COLUMN structured_data TEXT")

        # Seed & ensure all 12 Autonomous Agents exist in agents table
        all_12_agents = [
            ("requirement", "Requirement Analysis Agent", "Understands user prompt, extracts functional & non-functional requirements, produces structured specifications.", "file-text", 1),
            ("architecture", "Architecture Agent", "Designs clean system architecture, selects tech stack, component relations, and directory plan.", "git-branch", 2),
            ("ui_ux", "UI/UX Agent", "Analyzes design references, extracts layout tokens & palettes, plans responsive pages and components.", "layout", 3),
            ("project_structure", "Project Structure Agent", "Generates real directory trees, imports, dependencies, and verifies stack integrity.", "folder", 4),
            ("coding", "Coding Agent", "Generates production-grade application source code, services, models, and templates.", "code", 5),
            ("integration", "Integration Agent", "Connects modules, services, internal/external APIs, and validates environment configurations.", "link", 6),
            ("testing", "Testing Agent", "Executes unit and integration test suites, validates routes, and detects missing dependencies.", "flask", 7),
            ("debugging", "Debugging Agent", "Analyzes error logs, diagnoses root causes, proposes and applies surgical fixes.", "tool", 8),
            ("security", "Security Agent", "Scans code for vulnerabilities, exposed secrets, injection risks, and safe file operations.", "shield", 9),
            ("documentation", "Documentation Agent", "Generates master reference documentation, architecture diagrams, and user manuals.", "book-open", 10),
            ("preview_validation", "Preview & Visual Validation Agent", "Starts project on isolated runtime port, tests UI routes, and compares against references.", "eye", 11),
            ("project_manager", "Project Manager / Orchestrator Agent", "Coordinates all agents, tracks dependencies, computes evidence-based metrics, and compiles delivery reports.", "bar-chart", 12),
        ]
        for key, name, description, icon, order in all_12_agents:
            cursor.execute("""
                INSERT INTO agents (key, name, description, icon, stage_order)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    icon = excluded.icon,
                    stage_order = excluded.stage_order
            """, (key, name, description, icon, order))

        # Clean up any orphaned executions from unexpected restarts
        cursor.execute("""
            UPDATE agent_executions 
            SET status = 'failed', error_message = 'Interrupted by server restart'
            WHERE status = 'running'
        """)

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
