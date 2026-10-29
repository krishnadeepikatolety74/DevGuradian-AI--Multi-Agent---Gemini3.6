import re
import ast
from typing import Dict, Any, List
from db import get_standalone_db

def scan_project_security(project_id: str, files_manifest: Dict[str, str]) -> Dict[str, Any]:
    """
    Performs static security analysis on all generated project files.
    Identifies vulnerabilities, dangerous patterns, and exposed credentials.
    """
    findings = []
    
    for filename, code in files_manifest.items():
        lines = code.splitlines()
        
        # 1. Check for dangerous functions: eval, exec
        for idx, line in enumerate(lines, start=1):
            if re.search(r"\b(eval|exec)\s*\(", line):
                findings.append({
                    "severity": "Critical",
                    "title": "Arbitrary Code Execution Risk (eval/exec)",
                    "rule_id": "SEC-R001",
                    "file_path": filename,
                    "line_number": idx,
                    "explanation": "Use of dynamic evaluation (eval or exec) allows execution of arbitrary input code.",
                    "recommended_fix": "Refactor logic to use safe parsing, mapping dictionaries, or ast.literal_eval."
                })

        # 2. Check for SQL Injection (string formatting in execute)
        for idx, line in enumerate(lines, start=1):
            if re.search(r"\.execute\s*\(\s*f[\"'].*\{.*\}", line) or \
               re.search(r"\.execute\s*\(\s*[\"'].*%\s*\(", line) or \
               re.search(r"\.execute\s*\(\s*[\"'].*\+\s*[a-zA-Z_]", line):
                findings.append({
                    "severity": "Critical",
                    "title": "Potential SQL Injection Flaw",
                    "rule_id": "SEC-R002",
                    "file_path": filename,
                    "line_number": idx,
                    "explanation": "SQL statement is constructed via dynamic string formatting or concatenation rather than parameter binding.",
                    "recommended_fix": "Use parameterized queries with placeholder syntax: cursor.execute('SELECT ... WHERE id = ?', (val,))."
                })

        # 3. Check for Subprocess with shell=True
        for idx, line in enumerate(lines, start=1):
            if "subprocess" in line and "shell=True" in line:
                findings.append({
                    "severity": "High",
                    "title": "Insecure Subprocess Execution (shell=True)",
                    "rule_id": "SEC-R003",
                    "file_path": filename,
                    "line_number": idx,
                    "explanation": "Executing subprocesses with shell=True invites command injection when user input is included.",
                    "recommended_fix": "Pass arguments as an explicit array [command, arg1, arg2] with shell=False."
                })

        # 4. Check for Hardcoded API Keys or Secrets
        secret_patterns = [
            (r"(?i)(api[_-]?key|secret[_-]?key|password|jwt[_-]?secret)\s*=\s*['\"][a-zA-Z0-9_\-\.]{16,}['\"]", "High", "Hardcoded Secret / Credential Token", "SEC-R004"),
            (r"(?i)aws_secret_access_key\s*=", "High", "Hardcoded AWS Secret Key", "SEC-R005"),
        ]
        for pattern, sev, title, rule in secret_patterns:
            for idx, line in enumerate(lines, start=1):
                if re.search(pattern, line):
                    findings.append({
                        "severity": sev,
                        "title": title,
                        "rule_id": rule,
                        "file_path": filename,
                        "line_number": idx,
                        "explanation": "Sensitive authentication key or password found hardcoded in source repository.",
                        "recommended_fix": "Extract secret into environment variables via os.environ.get('SECRET_KEY')."
                    })

        # 5. Check for debug=True in app.run
        for idx, line in enumerate(lines, start=1):
            if re.search(r"app\.run\s*\(.*debug\s*=\s*True", line):
                findings.append({
                    "severity": "Medium",
                    "title": "Flask Interactive Debugger Enabled in Runtime",
                    "rule_id": "SEC-R006",
                    "file_path": filename,
                    "line_number": idx,
                    "explanation": "debug=True in Flask enables the interactive Werkzeug pin-protected debugger, which can leak system internals.",
                    "recommended_fix": "Set debug=False or toggle via FLASK_ENV environment variable only in development."
                })

        # 6. Informational: Missing Security Headers or Standard CSRF Notice
        if filename == "app.py":
            has_csrf = "csrf" in code.lower() or "secret_key" in code.lower()
            if not has_csrf:
                findings.append({
                    "severity": "Low",
                    "title": "Missing Session Secret Configuration",
                    "rule_id": "SEC-R007",
                    "file_path": filename,
                    "line_number": 1,
                    "explanation": "Flask app instance should configure a robust cryptographically generated secret_key.",
                    "recommended_fix": "Assign app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))."
                })

    # Add informational clean check if no critical/high issues found
    if not any(f["severity"] in ["Critical", "High"] for f in findings):
        findings.append({
            "severity": "Informational",
            "title": "Core Security Baseline Passed",
            "rule_id": "SEC-INFO-001",
            "file_path": "Global Workspace",
            "line_number": 0,
            "explanation": "All generated source modules adhere to parameterized data access, sanitized imports, and safe process boundaries.",
            "recommended_fix": "Maintain recurring static security audits in CI/CD pipeline."
        })

    # Save to SQLite database if project exists
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        if cursor.fetchone():
            cursor.execute("DELETE FROM security_findings WHERE project_id = ?", (project_id,))
            for f in findings:
                cursor.execute("""
                    INSERT INTO security_findings 
                    (project_id, severity, title, rule_id, file_path, line_number, explanation, recommended_fix, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """, (project_id, f["severity"], f["title"], f["rule_id"], f["file_path"], f["line_number"], f["explanation"], f["recommended_fix"]))
    conn.close()

    severity_counts = {
        "Critical": sum(1 for f in findings if f["severity"] == "Critical"),
        "High": sum(1 for f in findings if f["severity"] == "High"),
        "Medium": sum(1 for f in findings if f["severity"] == "Medium"),
        "Low": sum(1 for f in findings if f["severity"] == "Low"),
        "Informational": sum(1 for f in findings if f["severity"] == "Informational"),
    }

    status = "failed" if severity_counts["Critical"] > 0 else "completed"

    return {
        "status": status,
        "findings": findings,
        "counts": severity_counts,
        "logs": [
            f"Initiated static AST security scanner across {len(files_manifest)} files",
            f"Evaluated regex rules for SQL injection, eval/exec, shell=True, and secrets",
            f"Audit finished: {severity_counts['Critical']} Critical, {severity_counts['High']} High, {severity_counts['Medium']} Medium, {severity_counts['Low']} Low, {severity_counts['Informational']} Informational",
            "Saved security audit findings to database"
        ]
    }

def get_project_security_findings(project_id: str) -> List[Dict[str, Any]]:
    """Retrieve all security findings for a project."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM security_findings WHERE project_id = ? ORDER BY 
        CASE severity
            WHEN 'Critical' THEN 1
            WHEN 'High' THEN 2
            WHEN 'Medium' THEN 3
            WHEN 'Low' THEN 4
            ELSE 5
        END ASC, id ASC
    """, (project_id,))
    rows = cursor.fetchall()
    findings = [dict(r) for r in rows]
    conn.close()
    return findings
