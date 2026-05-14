"""Feature #14 — Entity Resolution (MVP: exact IC match).

link_records()    — groups records by normalised 12-digit IC
persist_linkage() — writes groups to entity_linkage table
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def _normalise_ic(raw: str) -> str:
    """Strip dashes/spaces; return 12-digit string or '' if invalid."""
    cleaned = re.sub(r"[\s\-]", "", str(raw or ""))
    if re.fullmatch(r"\d{12}", cleaned):
        return cleaned
    return ""


def _ic_match_confidence(ic_a: str, ic_b: str) -> float:
    if ic_a and ic_b and ic_a == ic_b:
        return 1.0
    return 0.0


def link_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group records by normalised IC. Return unified child profiles.

    Each record: {ic, source_type, dataset_id, name, dob}
    Each group:  {ic, source_types, sources, match_confidence, name, dob}
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    unmatched: list[dict] = []

    for rec in records:
        norm = _normalise_ic(rec.get("ic", ""))
        if norm:
            groups[norm].append(rec)
        else:
            unmatched.append(rec)

    result = []
    for ic, members in groups.items():
        result.append({
            "ic":               ic,
            "source_types":     list({m["source_type"] for m in members}),
            "sources":          members,
            "match_confidence": 1.0,
            "name":             next((m["name"] for m in members if m.get("name")), None),
            "dob":              next((m["dob"] for m in members if m.get("dob")), None),
        })

    for rec in unmatched:
        result.append({
            "ic":               rec.get("ic", ""),
            "source_types":     [rec["source_type"]],
            "sources":          [rec],
            "match_confidence": 0.0,
            "name":             rec.get("name"),
            "dob":              rec.get("dob"),
        })

    return result


def persist_linkage(groups: list[dict], db_session) -> int:
    """Write entity linkage groups to the entity_linkage table. Returns row count."""
    from datetime import datetime
    from backend.db.models import EntityLinkage

    rows_written = 0
    for group in groups:
        for src in group["sources"]:
            db_session.add(EntityLinkage(
                ic_no=group["ic"],
                source_type=src["source_type"],
                dataset_id=src.get("dataset_id"),
                name=group["name"],
                dob=group["dob"],
                match_confidence=group["match_confidence"],
                created_at=datetime.utcnow(),
            ))
            rows_written += 1

    db_session.commit()
    return rows_written
