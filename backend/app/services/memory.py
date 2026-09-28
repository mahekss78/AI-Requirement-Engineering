"""
app/services/memory.py
=======================
Requirement Memory & Versioning Service for the AREA platform.

Responsibilities (PDS Vol 2 §9.3.1):
1. Computes JSON diffs between requirement versions.
2. Creates deterministic version snapshots (Semantic Versioning MAJOR.MINOR.PATCH).
3. Maintains an immutable version history log in requirement_versions.
4. Executes version rollbacks with full auditability.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Requirement, RequirementVersion

logger = logging.getLogger(__name__)


def compute_json_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute structured diff between two JSON/dict payloads.

    Returns:
        Dict with keys "added", "modified", "removed".
    """
    added = {}
    modified = {}
    removed = {}

    before_keys = set(before.keys()) if isinstance(before, dict) else set()
    after_keys = set(after.keys()) if isinstance(after, dict) else set()

    for k in after_keys - before_keys:
        added[k] = after[k]

    for k in before_keys - after_keys:
        removed[k] = before[k]

    for k in before_keys & after_keys:
        if before[k] != after[k]:
            modified[k] = {"before": before[k], "after": after[k]}

    return {
        "added": added,
        "modified": modified,
        "removed": removed,
    }


def bump_version_string(current_version: str, is_major: bool = False) -> str:
    """
    Bump Semantic Version string MAJOR.MINOR.PATCH.
    is_major=True -> MAJOR + 1, MINOR=0, PATCH=0 (e.g. 0.3.0 -> 1.0.0 when freezing).
    is_major=False -> MINOR + 1 (e.g. 0.1.0 -> 0.2.0).
    """
    parts = (current_version or "0.1.0").split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        major, minor, patch = 0, 1, 0

    if is_major:
        return f"{major + 1}.0.0"
    else:
        return f"{major}.{minor + 1}.0"


class RequirementMemoryService:
    """
    Manages requirement version history, diff calculation, and rollbacks.
    """

    @staticmethod
    def create_version_snapshot(
        db: Session,
        requirement: Requirement,
        change_rationale: str = "Requirement update",
        is_major_bump: bool = False,
    ) -> RequirementVersion:
        """
        Creates an immutable RequirementVersion record and updates requirement.version.
        """
        new_version_str = bump_version_string(requirement.version, is_major=is_major_bump)
        requirement.version = new_version_str

        snapshot = RequirementVersion(
            requirement_id=requirement.id,
            version=new_version_str,
            requirement_data=requirement.requirement_data or {},
            change_rationale=change_rationale,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        db.refresh(requirement)
        logger.info(
            f"Created version snapshot {new_version_str} for requirement {requirement.id}"
        )
        return snapshot

    @staticmethod
    def get_version_history(db: Session, requirement_id: UUID) -> List[RequirementVersion]:
        """
        Fetch version history for a requirement ordered by creation timestamp.
        """
        return (
            db.query(RequirementVersion)
            .filter(RequirementVersion.requirement_id == requirement_id)
            .order_by(RequirementVersion.created_at.asc())
            .all()
        )

    @staticmethod
    def rollback_to_version(
        db: Session,
        requirement: Requirement,
        target_version_str: str,
    ) -> Tuple[Requirement, RequirementVersion]:
        """
        Restores a requirement's requirement_data payload to a target version.

        Bumps minor version with change_rationale explaining the rollback.
        """
        target_snapshot = (
            db.query(RequirementVersion)
            .filter(
                RequirementVersion.requirement_id == requirement.id,
                RequirementVersion.version == target_version_str,
            )
            .first()
        )

        if not target_snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{target_version_str}' not found for this requirement.",
            )

        # Apply target snapshot data
        requirement.requirement_data = target_snapshot.requirement_data

        # Create new version snapshot recording the rollback
        rationale = f"Rollback restored content to version {target_version_str}"
        new_snapshot = RequirementMemoryService.create_version_snapshot(
            db=db,
            requirement=requirement,
            change_rationale=rationale,
            is_major_bump=False,
        )

        return requirement, new_snapshot


memory_service = RequirementMemoryService()
