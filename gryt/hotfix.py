"""
Hot-fix Generation Workflow (v1.0.0)

Provides fast-track workflow for emergency fixes with minimal gates.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .generation import Generation, GenerationChange
from .evolution import Evolution
from .data import SqliteData
from .gates import PromotionGate, GateResult


class HotfixGate(PromotionGate):
    """Minimal gate for hot-fix promotions

    Only requires:
    - At least one passing evolution
    - No pending evolutions
    """

    def __init__(self):
        super().__init__("hotfix_gate")

    def check(self, generation: Generation, data: SqliteData) -> GateResult:
        """Check hot-fix promotion criteria"""
        if not generation.changes:
            return GateResult(
                passed=False,
                message="No changes defined",
                details={}
            )

        # Check each change has at least one passing evolution
        for change in generation.changes:
            evolutions = data.query("""
                SELECT status FROM evolutions
                WHERE generation_id = ? AND change_id = ?
            """, (generation.generation_id, change.change_id))

            if not evolutions:
                return GateResult(
                    passed=False,
                    message=f"Change {change.change_id} has no evolutions",
                    details={"change_id": change.change_id}
                )

            has_pass = any(e["status"] == "pass" for e in evolutions)
            has_pending = any(e["status"] in ("pending", "running") for e in evolutions)

            if not has_pass:
                return GateResult(
                    passed=False,
                    message=f"Change {change.change_id} has no passing evolution",
                    details={"change_id": change.change_id}
                )

            if has_pending:
                return GateResult(
                    passed=False,
                    message=f"Change {change.change_id} has pending evolutions",
                    details={"change_id": change.change_id}
                )

        return GateResult(
            passed=True,
            message="Hot-fix ready for promotion",
            details={}
        )


class HotfixWorkflow:
    """Manages hot-fix generation workflow"""

    def __init__(self, data: SqliteData):
        self.data = data

    def create_hotfix_generation(
        self,
        base_version: str,
        issue_id: str,
        title: str,
        description: Optional[str] = None
    ) -> Generation:
        """Create a hot-fix generation

        Args:
            base_version: Base version to fix (e.g., "v1.2.0")
            issue_id: Issue/bug ID (e.g., "BUG-123")
            title: Fix title
            description: Optional description

        Returns:
            Created Generation with hot-fix version
        """
        # Calculate hot-fix version
        hotfix_version = self._calculate_hotfix_version(base_version)

        # Create generation with fix change
        change = GenerationChange(
            change_id=issue_id,
            change_type="fix",
            title=title,
            description=description or f"Hot-fix for {base_version}"
        )

        generation = Generation(
            version=hotfix_version,
            description=f"Hot-fix for {base_version}: {title}",
            changes=[change]
        )

        generation.save_to_db(self.data, emit_event=True)

        return generation

    def _calculate_hotfix_version(self, base_version: str) -> str:
        """Calculate next hot-fix version

        Examples:
        - v1.2.0 → v1.2.1
        - v1.2.3 → v1.2.4
        """
        # Remove 'v' prefix if present
        version = base_version.lstrip("v")

        # Split into parts
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {base_version}")

        major, minor, patch = parts

        # Find highest existing patch version
        existing = self.data.query("""
            SELECT version FROM generations
            WHERE version LIKE ?
            ORDER BY version DESC
            LIMIT 1
        """, (f"v{major}.{minor}.%",))

        if existing:
            latest = existing[0]["version"].lstrip("v")
            latest_parts = latest.split(".")
            latest_patch = int(latest_parts[2])
            new_patch = latest_patch + 1
        else:
            new_patch = int(patch) + 1

        return f"v{major}.{minor}.{new_patch}"

    def fast_track_evolution(
        self,
        generation: Generation,
        change_id: str,
        auto_tag: bool = True,
        repo_path: Optional[Path] = None
    ) -> Evolution:
        """Fast-track an evolution for hot-fix

        Args:
            generation: Hot-fix generation
            change_id: Change ID to evolve
            auto_tag: Create git tag
            repo_path: Git repository path

        Returns:
            Created Evolution
        """
        # Start evolution immediately
        evolution = Evolution.start_evolution(
            data=self.data,
            version=generation.version,
            change_id=change_id,
            auto_tag=auto_tag,
            repo_path=repo_path or Path.cwd()
        )

        return evolution

    def promote_hotfix(
        self,
        generation: Generation,
        auto_tag: bool = True,
        repo_path: Optional[Path] = None
    ) -> dict:
        """Promote hot-fix generation with minimal gates

        Args:
            generation: Hot-fix generation to promote
            auto_tag: Create git tag
            repo_path: Git repository path

        Returns:
            Promotion result
        """
        # Use hot-fix gate (minimal validation)
        gates = [HotfixGate()]

        result = generation.promote(
            self.data,
            gates=gates,
            auto_tag=auto_tag,
            repo_path=repo_path
        )

        if result["success"]:
            # Log hot-fix promotion for audit trail
            self._log_hotfix_promotion(generation)

        return result

    def _log_hotfix_promotion(self, generation: Generation) -> None:
        """Log hot-fix promotion for audit purposes"""
        from .audit import AuditTrail

        audit = AuditTrail(self.data)
        audit.log_event(
            event_type="hotfix.promoted",
            resource_type="generation",
            resource_id=generation.generation_id,
            action="promote",
            status="success",
            details={
                "version": generation.version,
                "is_hotfix": True,
                "promoted_at": datetime.now().isoformat()
            }
        )

    def list_hotfixes(self) -> List[Generation]:
        """List all hot-fix generations"""
        rows = self.data.query("""
            SELECT * FROM generations
            WHERE version LIKE '%.%._%'
            AND version NOT LIKE '%rc%'
            ORDER BY created_at DESC
        """)

        generations = []
        for row in rows:
            gen = Generation.from_db(self.data, row["generation_id"])
            if gen:
                generations.append(gen)

        return generations

    def get_hotfix_statistics(self) -> dict:
        """Get hot-fix statistics"""
        hotfixes = self.list_hotfixes()

        stats = {
            "total_hotfixes": len(hotfixes),
            "promoted_hotfixes": sum(1 for g in hotfixes if g.status == "promoted"),
            "pending_hotfixes": sum(1 for g in hotfixes if g.status == "draft"),
            "average_time_to_promote": None,  # TODO: Calculate
        }

        return stats


def create_hotfix(
    db_path: Path,
    base_version: str,
    issue_id: str,
    title: str,
    description: Optional[str] = None
) -> Generation:
    """Create a hot-fix generation

    Args:
        db_path: Path to gryt database
        base_version: Base version to fix
        issue_id: Issue/bug ID
        title: Fix title
        description: Optional description

    Returns:
        Created Generation
    """
    data = SqliteData(db_path=str(db_path))
    try:
        workflow = HotfixWorkflow(data)
        return workflow.create_hotfix_generation(base_version, issue_id, title, description)
    finally:
        data.close()
