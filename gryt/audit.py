"""
Audit Trail System (v1.0.0)

Provides comprehensive audit logging and export for secure evolvability.
Implements NIST 800-161 requirements for change tracking and accountability.
"""
from __future__ import annotations

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from .data import SqliteData


@dataclass
class AuditEvent:
    """Represents a single audit event"""
    event_id: str
    timestamp: str
    event_type: str  # generation.created, evolution.completed, gate.failed, etc.
    actor: str  # user or system
    resource_type: str  # generation, evolution, pipeline, etc.
    resource_id: str
    action: str  # create, update, promote, fail, etc.
    status: str  # success, failure
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class AuditTrail:
    """Manages audit trail export and querying"""

    def __init__(self, data: SqliteData):
        self.data = data
        self._ensure_audit_table()

    def _ensure_audit_table(self) -> None:
        """Create audit_events table if it doesn't exist"""
        self.data.query("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                details_json TEXT
            )
        """)

    def log_event(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        action: str,
        status: str = "success",
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log an audit event"""
        import uuid

        event_id = f"audit-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now().isoformat()

        self.data.insert("audit_events", {
            "event_id": event_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "actor": actor,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "status": status,
            "details_json": json.dumps(details or {})
        })

        return event_id

    def export_full_audit_trail(self, output_path: Path, format: str = "json") -> None:
        """Export complete audit trail to file

        Args:
            output_path: Path to output file
            format: Output format (json, csv, html)
        """
        # Gather all audit data
        audit_data = self._gather_audit_data()

        if format == "json":
            self._export_json(audit_data, output_path)
        elif format == "csv":
            self._export_csv(audit_data, output_path)
        elif format == "html":
            self._export_html(audit_data, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _gather_audit_data(self) -> Dict[str, Any]:
        """Gather all audit trail data from database"""
        data = {
            "exported_at": datetime.now().isoformat(),
            "generations": [],
            "evolutions": [],
            "pipeline_runs": [],
            "audit_events": [],
            "statistics": {}
        }

        # Generations
        gen_rows = self.data.query("""
            SELECT g.*,
                   COUNT(DISTINCT e.evolution_id) as evolution_count,
                   SUM(CASE WHEN e.status = 'pass' THEN 1 ELSE 0 END) as passed_count,
                   SUM(CASE WHEN e.status = 'fail' THEN 1 ELSE 0 END) as failed_count
            FROM generations g
            LEFT JOIN evolutions e ON g.generation_id = e.generation_id
            GROUP BY g.generation_id
            ORDER BY g.created_at DESC
        """)
        data["generations"] = [dict(row) for row in gen_rows]

        # Evolutions with change details
        evo_rows = self.data.query("""
            SELECT e.*, gc.type as change_type, gc.title as change_title
            FROM evolutions e
            LEFT JOIN generation_changes gc ON e.change_id = gc.change_id
            ORDER BY e.started_at DESC
        """)
        data["evolutions"] = [dict(row) for row in evo_rows]

        # Pipeline runs
        pipeline_rows = self.data.query("""
            SELECT * FROM pipelines
            ORDER BY start_timestamp DESC
            LIMIT 1000
        """)
        data["pipeline_runs"] = [dict(row) for row in pipeline_rows]

        # Audit events
        audit_rows = self.data.query("""
            SELECT * FROM audit_events
            ORDER BY timestamp DESC
        """)
        data["audit_events"] = [dict(row) for row in audit_rows]

        # Statistics
        stats = self._calculate_statistics()
        data["statistics"] = stats

        return data

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate audit trail statistics"""
        stats = {}

        # Generation stats
        gen_stats = self.data.query("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'promoted' THEN 1 ELSE 0 END) as promoted,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft
            FROM generations
        """)
        stats["generations"] = dict(gen_stats[0]) if gen_stats else {}

        # Evolution stats
        evo_stats = self.data.query("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM evolutions
        """)
        stats["evolutions"] = dict(evo_stats[0]) if evo_stats else {}

        # Calculate pass rate
        if stats["evolutions"].get("total", 0) > 0:
            passed = stats["evolutions"].get("passed", 0)
            total = stats["evolutions"]["total"]
            stats["evolutions"]["pass_rate"] = round((passed / total) * 100, 2)

        return stats

    def _export_json(self, data: Dict[str, Any], output_path: Path) -> None:
        """Export audit data as JSON"""
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _export_csv(self, data: Dict[str, Any], output_path: Path) -> None:
        """Export audit events as CSV"""
        with open(output_path, "w", newline="") as f:
            if not data["audit_events"]:
                return

            fieldnames = data["audit_events"][0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data["audit_events"])

    def _export_html(self, data: Dict[str, Any], output_path: Path) -> None:
        """Export audit trail as HTML report"""
        html = self._generate_html_report(data)
        with open(output_path, "w") as f:
            f.write(html)

    def _generate_html_report(self, data: Dict[str, Any]) -> str:
        """Generate HTML audit report"""
        stats = data["statistics"]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Gryt-CI Audit Trail Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #ecf0f1; padding: 15px; border-radius: 5px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .stat-label {{ color: #7f8c8d; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #34495e; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f8f9fa; }}
        .status-pass {{ color: #27ae60; font-weight: bold; }}
        .status-fail {{ color: #e74c3c; font-weight: bold; }}
        .status-pending {{ color: #f39c12; }}
        .meta {{ color: #7f8c8d; font-size: 0.85em; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Gryt-CI Audit Trail Report</h1>
        <div class="meta">
            Generated: {data['exported_at']}<br>
            Report Type: Full Audit Trail Export
        </div>

        <h2>Summary Statistics</h2>
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{stats.get('generations', {}).get('total', 0)}</div>
                <div class="stat-label">Total Generations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('generations', {}).get('promoted', 0)}</div>
                <div class="stat-label">Promoted Generations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('evolutions', {}).get('total', 0)}</div>
                <div class="stat-label">Total Evolutions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('evolutions', {}).get('pass_rate', 0)}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
        </div>

        <h2>Generations</h2>
        <table>
            <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Evolutions</th>
                <th>Pass/Fail</th>
                <th>Created</th>
                <th>Promoted</th>
            </tr>
"""

        for gen in data["generations"]:
            promoted = gen.get("promoted_at", "") or "—"
            html += f"""
            <tr>
                <td>{gen.get('version', '')}</td>
                <td class="status-{gen.get('status', '')}">{gen.get('status', '')}</td>
                <td>{gen.get('evolution_count', 0)}</td>
                <td>{gen.get('passed_count', 0)} / {gen.get('failed_count', 0)}</td>
                <td>{gen.get('created_at', '')}</td>
                <td>{promoted}</td>
            </tr>
"""

        html += """
        </table>

        <h2>Recent Evolutions</h2>
        <table>
            <tr>
                <th>Tag</th>
                <th>Change Type</th>
                <th>Change Title</th>
                <th>Status</th>
                <th>Started</th>
            </tr>
"""

        for evo in data["evolutions"][:50]:  # Limit to 50 most recent
            html += f"""
            <tr>
                <td>{evo.get('tag', '')}</td>
                <td>{evo.get('change_type', '')}</td>
                <td>{evo.get('change_title', '')}</td>
                <td class="status-{evo.get('status', '')}">{evo.get('status', '')}</td>
                <td>{evo.get('started_at', '')}</td>
            </tr>
"""

        html += """
        </table>

        <div class="meta">
            This report provides a complete audit trail of all gryt-ci activities.<br>
            For compliance purposes, this data demonstrates secure evolvability per NIST 800-161.
        </div>
    </div>
</body>
</html>
"""
        return html


def export_audit_trail(
    db_path: Path,
    output_path: Path,
    format: str = "json"
) -> None:
    """Export audit trail to file

    Args:
        db_path: Path to gryt database
        output_path: Path to output file
        format: Output format (json, csv, html)
    """
    data = SqliteData(db_path=str(db_path))
    try:
        audit = AuditTrail(data)
        audit.export_full_audit_trail(output_path, format)
    finally:
        data.close()
