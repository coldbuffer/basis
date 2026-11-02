"""Ledger conflict detection (SHACL on mapped assertions)."""

from basis.services.knowledge.conflict.policy import CONFLICT_SCHEMA_VERSION
from basis.services.knowledge.conflict.scan import run_shacl_conflict_scan
from basis.services.knowledge.conflict.shacl_scan import (
    SHACL_VIOLATION_KIND,
    SHACL_VIOLATION_SUBJECT_TYPE,
)

__all__ = [
    "CONFLICT_SCHEMA_VERSION",
    "SHACL_VIOLATION_KIND",
    "SHACL_VIOLATION_SUBJECT_TYPE",
    "run_shacl_conflict_scan",
]
