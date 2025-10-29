"""
Promotion Gate system (v0.4.0)

Promotion gates validate whether a generation is ready to be promoted to production.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .data import SqliteData
from .generation import Generation
from .evolution import Evolution


class GateResult:
    """Result of a promotion gate check"""

    def __init__(self, passed: bool, message: str, details: Optional[Dict[str, Any]] = None):
        self.passed = passed
        self.message = message
        self.details = details or {}

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"GateResult({status}: {self.message})"


class PromotionGate(ABC):
    """
    Base class for promotion gates.

    A promotion gate validates whether a generation meets specific criteria
    before it can be promoted to production.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def check(self, generation: Generation, data: SqliteData) -> GateResult:
        """
        Check if the generation passes this gate.

        Returns a GateResult indicating pass/fail and a message.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class AllChangesProvenGate(PromotionGate):
    """
    Gate that requires all changes in a generation to have at least one PASS evolution.

    This is the core gate that enforces the "100% PASS" requirement.
    """

    def __init__(self):
        super().__init__("all_changes_proven")

    def check(self, generation: Generation, data: SqliteData) -> GateResult:
        """Check that all changes have at least one PASS evolution"""
        # Get all changes for this generation
        if not generation.changes:
            return GateResult(
                passed=False,
                message="Generation has no changes",
                details={"change_count": 0}
            )

        # Check each change
        unproven_changes = []
        change_status = {}

        for change in generation.changes:
            # Get evolutions for this change
            evolutions = data.query(
                """
                SELECT status FROM evolutions
                WHERE generation_id = ? AND change_id = ?
                """,
                (generation.generation_id, change.change_id)
            )

            # Check if any evolution passed
            passed_evolutions = [e for e in evolutions if e["status"] == "pass"]
            has_pass = len(passed_evolutions) > 0

            change_status[change.change_id] = {
                "title": change.title,
                "type": change.type,
                "evolutions_count": len(evolutions),
                "passed_count": len(passed_evolutions),
                "has_pass": has_pass
            }

            if not has_pass:
                unproven_changes.append(change.change_id)

        if unproven_changes:
            return GateResult(
                passed=False,
                message=f"Changes without PASS evolution: {', '.join(unproven_changes)}",
                details={
                    "unproven_changes": unproven_changes,
                    "change_status": change_status,
                    "total_changes": len(generation.changes),
                    "proven_changes": len(generation.changes) - len(unproven_changes)
                }
            )

        return GateResult(
            passed=True,
            message=f"All {len(generation.changes)} changes have PASS evolutions",
            details={
                "change_status": change_status,
                "total_changes": len(generation.changes)
            }
        )


class MinEvolutionsGate(PromotionGate):
    """
    Gate that requires a minimum number of evolutions per change.

    This can be used to enforce multiple test runs before promotion.
    """

    def __init__(self, min_evolutions: int = 1):
        super().__init__(f"min_{min_evolutions}_evolutions")
        self.min_evolutions = min_evolutions

    def check(self, generation: Generation, data: SqliteData) -> GateResult:
        """Check that each change has at least min_evolutions"""
        if not generation.changes:
            return GateResult(
                passed=False,
                message="Generation has no changes",
                details={"change_count": 0}
            )

        insufficient_changes = []
        change_status = {}

        for change in generation.changes:
            evolutions = data.query(
                """
                SELECT COUNT(*) as count FROM evolutions
                WHERE generation_id = ? AND change_id = ?
                """,
                (generation.generation_id, change.change_id)
            )

            count = evolutions[0]["count"] if evolutions else 0
            change_status[change.change_id] = {
                "title": change.title,
                "evolutions_count": count,
                "meets_minimum": count >= self.min_evolutions
            }

            if count < self.min_evolutions:
                insufficient_changes.append(f"{change.change_id} ({count}/{self.min_evolutions})")

        if insufficient_changes:
            return GateResult(
                passed=False,
                message=f"Changes with insufficient evolutions: {', '.join(insufficient_changes)}",
                details={
                    "insufficient_changes": insufficient_changes,
                    "change_status": change_status,
                    "min_required": self.min_evolutions
                }
            )

        return GateResult(
            passed=True,
            message=f"All changes have at least {self.min_evolutions} evolution(s)",
            details={
                "change_status": change_status,
                "min_required": self.min_evolutions
            }
        )


class NoFailedEvolutionsGate(PromotionGate):
    """
    Gate that fails if any evolution is in 'fail' status.

    This enforces that all test runs must pass before promotion.
    """

    def __init__(self):
        super().__init__("no_failed_evolutions")

    def check(self, generation: Generation, data: SqliteData) -> GateResult:
        """Check that no evolutions are in fail status"""
        failed_evolutions = data.query(
            """
            SELECT e.tag, e.change_id, e.status
            FROM evolutions e
            WHERE e.generation_id = ? AND e.status = 'fail'
            """,
            (generation.generation_id,)
        )

        if failed_evolutions:
            failed_list = [f"{e['tag']} ({e['change_id']})" for e in failed_evolutions]
            return GateResult(
                passed=False,
                message=f"Failed evolutions found: {', '.join(failed_list)}",
                details={
                    "failed_evolutions": failed_evolutions,
                    "count": len(failed_evolutions)
                }
            )

        return GateResult(
            passed=True,
            message="No failed evolutions",
            details={"failed_count": 0}
        )


def get_default_gates() -> List[PromotionGate]:
    """Get the default set of promotion gates"""
    return [
        AllChangesProvenGate(),
        NoFailedEvolutionsGate(),
    ]
