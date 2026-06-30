"""Feature #14 — Entity Resolution.

v1 (back-compat):
  link_records()      — exact 12-digit IC grouping
  persist_linkage()   — writes groups to entity_linkage table

v2 (current):
  link_records_v2()   — probabilistic matching with:
                          IC exact + IC fuzzy (Levenshtein)
                        + name similarity (BIN/BINTI-stripped, token-aware)
                        + DOB tolerance (±N days)
                        + location boost (negeri match)
                        + contradiction scanning (hard/soft/strong severities)
                        + canonical identity + chronological timeline
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
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
        result.append(
            {
                "ic": ic,
                "source_types": list({m["source_type"] for m in members}),
                "sources": members,
                "match_confidence": 1.0,
                "name": next((m["name"] for m in members if m.get("name")), None),
                "dob": next((m["dob"] for m in members if m.get("dob")), None),
            }
        )

    for rec in unmatched:
        result.append(
            {
                "ic": rec.get("ic", ""),
                "source_types": [rec["source_type"]],
                "sources": [rec],
                "match_confidence": 0.0,
                "name": rec.get("name"),
                "dob": rec.get("dob"),
            }
        )

    return result


def persist_linkage(groups: list[dict], db_session) -> int:
    """Write entity linkage groups to the entity_linkage table. Returns row count."""
    from datetime import datetime
    from backend.db.models import EntityLinkage

    rows_written = 0
    for group in groups:
        for src in group["sources"]:
            db_session.add(
                EntityLinkage(
                    ic_no=group["ic"],
                    source_type=src["source_type"],
                    dataset_id=src.get("dataset_id"),
                    name=group["name"],
                    dob=group["dob"],
                    match_confidence=group["match_confidence"],
                    created_at=datetime.utcnow(),
                )
            )
            rows_written += 1

    db_session.commit()
    return rows_written


# ─────────────────────────────────────────────────────────────────────────────
# v2 matching — fuzzy IC + name/dob boost with confidence reasoning
# ─────────────────────────────────────────────────────────────────────────────


def _levenshtein(a: str, b: str) -> int:
    """Iterative Levenshtein distance — used for fuzzy IC matching where
    a single typo / OCR slip changes one digit. Keeps memory O(min(|a|,|b|))."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _deletes_within(term: str, max_deletes: int) -> set[str]:
    """All strings from deleting up to max_deletes chars (term included).
    For a 12-digit IC at max_deletes=1 this is 13 strings."""
    results = {term}
    frontier = {term}
    for _ in range(max(0, max_deletes)):
        nxt = set()
        for w in frontier:
            for i in range(len(w)):
                nxt.add(w[:i] + w[i + 1 :])
        results |= nxt
        frontier = nxt
    return results


def _normalise_name(raw: str) -> str:
    """Uppercase + strip + collapse internal whitespace so 'Ali  Bin Ahmad' and
    'ALI BIN AHMAD ' are equivalent for boost-comparison."""
    return " ".join(str(raw or "").upper().split())


def _normalise_dob(raw: str) -> str:
    """Reduce to YYYY-MM-DD if it looks like an ISO-style date; otherwise
    just strip whitespace. Tolerant on purpose — input is messy."""
    s = str(raw or "").strip()
    # Common formats: '2020-01-15', '15/01/2020', '15-01-2020', '2020/01/15'
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) == 8:
        # Heuristic: leading 4 digits in 1900–2030 → YYYYMMDD, else DDMMYYYY.
        if 1900 <= int(digits[:4]) <= 2030:
            return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
        return f"{digits[4:8]}-{digits[2:4]}-{digits[0:2]}"
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Name similarity — stdlib only. Strips Malay/Indian name particles so
# "Ali bin Ahmad" ↔ "Ali Ahmad" doesn't tank the ratio. Returns max of
# three signals so we catch typos AND token reordering AND partial overlap.
# ─────────────────────────────────────────────────────────────────────────────

_NAME_PARTICLES = {
    "BIN",
    "BINTI",
    "BT",
    "BTE",
    "B",  # Malay
    "A/L",
    "A/P",
    "AL",
    "AP",  # Indian Malaysian
    "S/O",
    "D/O",  # alternative South Asian
}


def _name_tokens(name: str) -> list[str]:
    """Tokenise + uppercase + strip particles + drop pure punctuation."""
    if not name:
        return []
    cleaned = re.sub(r"[.,]", " ", str(name).upper())
    return [t for t in cleaned.split() if t and t not in _NAME_PARTICLES]


def _name_similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity score that's robust to:
      - typos (raw SequenceMatcher ratio on normalised strings)
      - reordered/inserted name particles (sorted-token SequenceMatcher)
      - long-name partial overlap (Jaccard on token sets)
    Takes the maximum of the three. Stdlib only — no rapidfuzz/jellyfish."""
    norm_a = _normalise_name(a)
    norm_b = _normalise_name(b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    # (1) raw normalised-string ratio
    raw_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()

    # (2) sorted-token ratio with particles stripped
    toks_a = _name_tokens(a)
    toks_b = _name_tokens(b)
    sorted_ratio = 0.0
    if toks_a and toks_b:
        sorted_ratio = SequenceMatcher(
            None, " ".join(sorted(toks_a)), " ".join(sorted(toks_b))
        ).ratio()

    # (3) Jaccard on token sets
    jaccard = 0.0
    if toks_a or toks_b:
        set_a, set_b = set(toks_a), set(toks_b)
        if set_a or set_b:
            jaccard = len(set_a & set_b) / len(set_a | set_b)

    return max(raw_ratio, sorted_ratio, jaccard)


# ─────────────────────────────────────────────────────────────────────────────
# DOB parsing + tolerance — single source of truth for both matcher and
# conflict scanner so they never disagree about whether two DOBs are "equal".
# Mirrors the ISO-first, dayfirst-fallback pattern in backend/eda/cleaning.py.
# ─────────────────────────────────────────────────────────────────────────────


def _parse_dob(raw: Any) -> date | None:
    """Best-effort coerce to a date. Accepts ISO (YYYY-MM-DD), dayfirst
    (dd/mm/yyyy), and the same compact digits-only forms _normalise_dob
    already handles. Returns None on failure (never raises)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    # _normalise_dob converts digit-only forms (DDMMYYYY / YYYYMMDD) to
    # ISO; if it succeeds the remaining branch is cheap.
    norm = _normalise_dob(s)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(norm, fmt).date()
        except ValueError:
            continue
    return None


def _dob_equal(a: Any, b: Any, tol_days: int = 1) -> bool:
    """Return True when both DOBs parse and differ by ≤ tol_days. False
    when either is unparseable — callers decide if that's a conflict."""
    pa, pb = _parse_dob(a), _parse_dob(b)
    if pa is None or pb is None:
        return False
    return abs((pa - pb).days) <= tol_days


# ─────────────────────────────────────────────────────────────────────────────
# Canonical identity + timeline + conflict scan — emitted per matched group
# so the UI can render the "unified longitudinal profile" the spec demands.
# ─────────────────────────────────────────────────────────────────────────────

# Preference order when canonical-identity ties on frequency + recency. The
# bundled default reflects the original dataset's sources; override per deployment
# with SMARTDQC_SOURCE_PRIORITY (comma-separated source tags, most-preferred
# first). Unknown sources go last regardless.
_DEFAULT_SOURCE_PRIORITY = ["MyVASS", "wide_multiyear", "Clinic", "clinic", "NCDC", "wide_registry"]
_SOURCE_PRIORITY = (
    [s.strip() for s in os.environ["SMARTDQC_SOURCE_PRIORITY"].split(",") if s.strip()]
    if os.environ.get("SMARTDQC_SOURCE_PRIORITY")
    else list(_DEFAULT_SOURCE_PRIORITY)
)


def _source_priority(src: str | None) -> int:
    """Lower = preferred. Unknown sources go last."""
    if src is None:
        return len(_SOURCE_PRIORITY) + 1
    try:
        return _SOURCE_PRIORITY.index(src)
    except ValueError:
        return len(_SOURCE_PRIORITY)


def _canonicalise_group(
    group: dict,
    dataset_created_at_by_id: dict[str, datetime] | None = None,
) -> dict:
    """Return canonical identity: most-frequent non-null per field; tie
    broken by newest dataset (created_at), then source priority. Returns
    a dict with at minimum {ic, name, dob, gender, state, district}."""
    dataset_created_at_by_id = dataset_created_at_by_id or {}
    sources = group.get("sources", []) or []
    canonical: dict[str, Any] = {}

    def _pick(field: str) -> Any:
        # Tally non-null values along with provenance.
        tally: dict[Any, list[dict]] = defaultdict(list)
        for s in sources:
            v = s.get(field)
            if v is None or v == "":
                continue
            tally[v].append(s)
        if not tally:
            return None

        # Sort: highest count → newest dataset → best source priority.
        def _rank(item):
            value, srcs = item
            count = len(srcs)
            # Filter to actually-present datetimes before taking max.
            datetimes = [
                dataset_created_at_by_id.get(s.get("dataset_id"))
                for s in srcs
                if s.get("dataset_id")
            ]
            datetimes = [d for d in datetimes if isinstance(d, datetime)]
            newest_ts = max((d.timestamp() for d in datetimes), default=0.0)
            best_prio = min(_source_priority(s.get("source_type")) for s in srcs)
            return (-count, -newest_ts, best_prio)

        ranked = sorted(tally.items(), key=_rank)
        return ranked[0][0]

    canonical["ic"] = group.get("ic") or _pick("ic")
    canonical["name"] = _pick("name")
    canonical["dob"] = _pick("dob")
    canonical["gender"] = _pick("gender")
    canonical["state"] = _pick("state")
    canonical["district"] = _pick("district")
    return canonical


def _build_timeline(group: dict) -> list[dict]:
    """Chronological measurements across sources. Skips rows whose
    measure_date can't be parsed. Output entries:
      {date, source_type, weight_kg, height_cm, bmi, waz, haz, baz}
    Date stored as ISO string for JSON-friendliness."""
    out: list[dict] = []
    for s in group.get("sources", []) or []:
        d = _parse_dob(s.get("measure_date"))  # same parser; works for any date
        if d is None:
            continue
        out.append(
            {
                "date": d.isoformat(),
                "source_type": s.get("source_type"),
                "weight_kg": s.get("weight_kg"),
                "height_cm": s.get("height_cm"),
                "bmi": s.get("bmi"),
                "waz": s.get("waz"),
                "haz": s.get("haz"),
                "baz": s.get("baz"),
            }
        )
    out.sort(key=lambda r: r["date"])
    return out


def _scan_conflicts(
    group: dict,
    *,
    name_fuzzy_threshold: float = 0.85,
    dob_tolerance_days: int = 1,
) -> list[dict]:
    """Walk source pairs and emit conflicts. Each conflict:
      {field, severity, values: [{source_type, value}]}
    Severities:
      hard   — exact-equality fields differ (jantina, negeri); DOB
               differs by years; non-empty values disagree.
      soft   — name fuzzy ≥ threshold but not exact; daerah differs
               while negeri agrees.
      strong — name fuzzy < 0.6.
    """
    sources = group.get("sources", []) or []
    if len(sources) < 2:
        return []

    def _values_for(field: str) -> list[dict]:
        """Distinct non-null values across sources with their provenance."""
        seen: dict[Any, dict] = {}
        for s in sources:
            v = s.get(field)
            if v is None or v == "":
                continue
            if v not in seen:
                seen[v] = {"source_type": s.get("source_type"), "value": v}
        return list(seen.values())

    conflicts: list[dict] = []

    # Gender — hard conflict on any disagreement
    g_vals = _values_for("gender")
    if len(g_vals) > 1:
        conflicts.append({"field": "gender", "severity": "hard", "values": g_vals})

    # State (negeri) — hard conflict
    st_vals = _values_for("state")
    if len(st_vals) > 1:
        conflicts.append({"field": "state", "severity": "hard", "values": st_vals})

    # District (daerah) — soft if state agrees, hard otherwise
    d_vals = _values_for("district")
    if len(d_vals) > 1:
        sev = "soft" if len(st_vals) <= 1 else "hard"
        conflicts.append({"field": "district", "severity": sev, "values": d_vals})

    # DOB — hard if any pair differs beyond tolerance OR by years
    dob_vals = _values_for("dob")
    if len(dob_vals) > 1:
        parsed = [(_parse_dob(v["value"]), v) for v in dob_vals]
        parsed = [(p, v) for (p, v) in parsed if p is not None]
        if len(parsed) >= 2:
            years = {p.year for p, _ in parsed}
            severe = len(years) > 1
            ok = all(
                _dob_equal(parsed[0][1]["value"], v["value"], dob_tolerance_days)
                for (_, v) in parsed[1:]
            )
            if not ok or severe:
                conflicts.append(
                    {
                        "field": "dob",
                        "severity": "hard",
                        "values": [v for (_, v) in parsed],
                    }
                )

    # Name — fuzzy comparison decides severity
    name_vals = _values_for("name")
    if len(name_vals) > 1:
        sims: list[float] = []
        first = name_vals[0]["value"]
        for v in name_vals[1:]:
            sims.append(_name_similarity(first, v["value"]))
        worst = min(sims) if sims else 1.0
        # Skip when all pairs are exact equal (they wouldn't be in _values_for).
        if worst < 0.6:
            severity = "strong"
        elif worst < name_fuzzy_threshold:
            severity = "hard"
        else:
            severity = "soft"
        conflicts.append(
            {
                "field": "name",
                "severity": severity,
                "values": name_vals,
            }
        )

    return conflicts


def link_records_v2(
    records: list[dict[str, Any]],
    *,
    fuzzy_ic: bool = True,
    fuzzy_ic_max_distance: int = 1,
    name_dob_boost: bool = True,
    name_fuzzy: bool = True,
    name_fuzzy_threshold: float = 0.85,
    dob_tolerance_days: int = 1,
    location_boost: bool = True,
    min_confidence: float = 0.6,
    dataset_created_at_by_id: dict[str, datetime] | None = None,
) -> list[dict[str, Any]]:
    """Group records across datasets with probabilistic multi-signal matching.

    Pipeline (each pass only sees records still unmatched at that point):
      1. Exact IC                    → confidence 1.00, reason "exact_ic"
      2. Fuzzy IC (Levenshtein ≤N)   → confidence 0.85, reason "fuzzy_ic±N"
      3. Name+DOB exact               → confidence 0.70, reason "name+dob"
      4. Name fuzzy + DOB tolerance   → confidence 0.70, reason "name_fuzzy" /
         (only IC-less records, scoped to     "dob±Nd"
         a year-month DOB bucket for O(N) bound)
      5. Anything still unmatched     → confidence 0.00, reason "unmatched"

    Optional location boost: when a matched group's sources agree on
    `state`, raise the group's confidence by +0.10 (capped at 1.0) and
    append a `same_state` reason chip. Applied only after ≥2 sources are
    in the group, so it can never lift an unmatched single.

    Each returned group additionally carries:
      profile.canonical  — {ic, name, dob, gender, state, district}
                            (most-frequent non-null per field; ties → newest
                             Dataset.created_at → source_type priority)
      profile.timeline   — chronological measurements across all sources
      conflicts          — [{field, severity, values: [...]}]
                            severity ∈ {hard, soft, strong}

    Input records: {ic, source_type, dataset_id, name, dob, [gender, state,
                    district, measure_date, weight_kg, height_cm, bmi, waz,
                    haz, baz — all optional, passed through]}
    """
    groups: list[dict] = []  # list of group dicts
    by_ic: dict[str, dict] = {}  # normalised IC → group
    by_name_dob_exact: dict[tuple[str, str], dict] = {}  # (name, dob)  → group
    # bucketed index for fuzzy-name pass: (dob_year_month) → list[group]
    by_dob_window: dict[tuple[int, int], list[dict]] = defaultdict(list)
    # Parallel set index for O(1) membership check (avoids O(N) list scan)
    _dob_window_ids: dict[tuple[int, int], set[int]] = defaultdict(set)

    def _dob_window_key(rec_dob: Any) -> tuple[int, int] | None:
        d = _parse_dob(rec_dob)
        return (d.year, d.month) if d else None

    def _index_group(g: dict, rec: dict) -> None:
        """Register group in name+dob and dob-window indexes."""
        nd = (_normalise_name(rec.get("name", "")), _normalise_dob(rec.get("dob", "")))
        if nd[0] and nd[1]:
            by_name_dob_exact.setdefault(nd, g)
        win = _dob_window_key(rec.get("dob"))
        if win and id(g) not in _dob_window_ids[win]:
            _dob_window_ids[win].add(id(g))
            by_dob_window[win].append(g)

    def _new_group(
        rec: dict, ic_norm: str, confidence: float, reasons: list[str]
    ) -> dict:
        g = {
            "ic": ic_norm,
            "sources": [rec],
            "confidence": confidence,
            "match_reasons": list(reasons),
            "name": rec.get("name") or None,
            "dob": rec.get("dob") or None,
        }
        groups.append(g)
        _index_group(g, rec)
        return g

    def _attach(
        g: dict,
        rec: dict,
        *,
        drop_confidence_floor: float | None = None,
        boost: float = 0.0,
        add_reason: str | None = None,
    ) -> None:
        g["sources"].append(rec)
        if drop_confidence_floor is not None:
            g["confidence"] = min(g["confidence"], drop_confidence_floor)
        if boost:
            g["confidence"] = min(1.0, g["confidence"] + boost)
        if add_reason and add_reason not in g["match_reasons"]:
            g["match_reasons"].append(add_reason)
        for fld in ("name", "dob"):
            if not g.get(fld) and rec.get(fld):
                g[fld] = rec[fld]
        _index_group(g, rec)

    # ── Pass 1: exact IC ────────────────────────────────────────────────────
    for rec in records:
        ic_norm = _normalise_ic(rec.get("ic", ""))
        if not ic_norm:
            continue
        g = by_ic.get(ic_norm)
        if g is None:
            g = _new_group(rec, ic_norm, confidence=1.0, reasons=["exact_ic"])
            by_ic[ic_norm] = g
        else:
            _attach(g, rec)

    # ── Pass 2: fuzzy IC ────────────────────────────────────────────────────
    # SymSpell symmetric-delete: replace O(G^2) candidate enumeration with
    # O(1) delete-neighborhood lookup, then verify with Levenshtein.
    fuzzy_unmatched: list[dict] = [
        r for r in records if not _normalise_ic(r.get("ic", ""))
    ]
    if fuzzy_ic and len(by_ic) > 1:
        merged_targets: dict[int, dict] = {}  # id(losing_group) → winner
        ic_keys = list(by_ic.keys())
        # Build symmetric-delete index over current IC keys
        delete_index: dict[str, list[str]] = defaultdict(list)
        for key in ic_keys:
            for variant in _deletes_within(key, fuzzy_ic_max_distance):
                delete_index[variant].append(key)
        for key_i in ic_keys:  # preserve original key order
            g_i = by_ic[key_i]
            if id(g_i) in merged_targets:
                continue
            # Candidate partners = ICs sharing any delete-variant with key_i
            cand: set[str] = set()
            for variant in _deletes_within(key_i, fuzzy_ic_max_distance):
                cand.update(delete_index.get(variant, ()))
            cand.discard(key_i)
            for key_j in cand:
                g_j = by_ic[key_j]
                if g_j is g_i or id(g_j) in merged_targets:
                    continue
                d = _levenshtein(key_i, key_j)  # verify — drop false candidates
                if 0 < d <= fuzzy_ic_max_distance:
                    for src in list(g_j["sources"]):
                        _attach(
                            g_i,
                            src,
                            drop_confidence_floor=0.85,
                            add_reason=f"fuzzy_ic±{d}",
                        )
                    merged_targets[id(g_j)] = g_i
        if merged_targets:
            groups[:] = [g for g in groups if id(g) not in merged_targets]
            # Rebuild by_ic so subsequent passes lookup the surviving group.
            survivors = {g["ic"]: g for g in groups if g.get("ic")}
            by_ic.clear()
            by_ic.update(survivors)

    # ── Pass 3: name + DOB exact ────────────────────────────────────────────
    still_unmatched: list[dict] = []
    if name_dob_boost:
        for rec in fuzzy_unmatched:
            name_n = _normalise_name(rec.get("name", ""))
            dob_n = _normalise_dob(rec.get("dob", ""))
            if not name_n or not dob_n:
                still_unmatched.append(rec)
                continue
            g = by_name_dob_exact.get((name_n, dob_n))
            if g is None:
                still_unmatched.append(rec)
            else:
                _attach(g, rec, drop_confidence_floor=0.7, add_reason="name+dob")
    else:
        still_unmatched = fuzzy_unmatched

    # ── Pass 4: fuzzy name + DOB tolerance ─────────────────────────────────
    # Only IC-less records reach here. Scoped to the dob-year-month bucket
    # ± nearby buckets so we never run SequenceMatcher across the whole
    # cross product. Self-bootstrapping: when no candidate matches, the
    # record becomes its own group, making it findable for subsequent
    # records in the same pass.
    truly_unmatched: list[dict] = []
    if name_fuzzy:
        for rec in still_unmatched:
            rec_dob = _parse_dob(rec.get("dob"))
            rec_name = rec.get("name") or ""
            if rec_dob is None or not rec_name:
                truly_unmatched.append(rec)
                continue
            # Consider buckets within ±1 month either side — covers any
            # tolerance ≤ 31 days; for larger windows the gate below
            # rejects out-of-range pairs anyway.
            base = (rec_dob.year, rec_dob.month)
            candidates: list[dict] = []
            for dy, dm in ((0, -1), (0, 0), (0, 1)):
                y, m = base[0] + dy, base[1] + dm
                if m == 0:
                    y, m = y - 1, 12
                elif m == 13:
                    y, m = y + 1, 1
                candidates.extend(by_dob_window.get((y, m), []))
            best_g, best_sim = None, name_fuzzy_threshold
            for g in candidates:
                if not g.get("name"):
                    continue
                gdob = g.get("dob")
                if gdob is None or not _dob_equal(
                    rec.get("dob"), gdob, dob_tolerance_days
                ):
                    continue
                sim = _name_similarity(rec_name, g["name"])
                if sim >= best_sim:
                    best_g, best_sim = g, sim
            if best_g is not None:
                _attach(
                    best_g,
                    rec,
                    drop_confidence_floor=0.7,
                    add_reason=(
                        f"name_fuzzy:{best_sim:.2f}"
                        if dob_tolerance_days == 0
                        else f"name_fuzzy:{best_sim:.2f}+dob±{dob_tolerance_days}d"
                    ),
                )
            else:
                # No candidate yet — create a new group so the NEXT
                # IC-less record with a fuzzy-similar name can find this
                # one. Pass 5 will skip records that already landed here.
                _new_group(
                    rec,
                    _normalise_ic(rec.get("ic", "")),
                    confidence=0.0,
                    reasons=["unmatched"],
                )
    else:
        truly_unmatched = still_unmatched

    # ── Pass 5: orphans become their own single-source groups ──────────────
    # Only records that couldn't even reach Pass 4 (missing name or DOB)
    # arrive here. Pass-4-created groups are already in `groups`.
    for rec in truly_unmatched:
        ic_norm = _normalise_ic(rec.get("ic", ""))
        g = _new_group(rec, ic_norm, confidence=0.0, reasons=["unmatched"])
        if ic_norm and ic_norm not in by_ic:
            by_ic[ic_norm] = g

    # ── Location boost: same `state` across ≥2 sources ─────────────────────
    if location_boost:
        for g in groups:
            srcs = g.get("sources", [])
            if len(srcs) < 2:
                continue
            states = {s.get("state") for s in srcs if s.get("state")}
            if len(states) == 1:
                g["confidence"] = min(1.0, g["confidence"] + 0.10)
                if "same_state" not in g["match_reasons"]:
                    g["match_reasons"].append("same_state")

    # ── Attach unified profile + conflict scan to every group ──────────────
    for g in groups:
        g["profile"] = {
            "canonical": _canonicalise_group(g, dataset_created_at_by_id),
            "timeline": _build_timeline(g),
        }
        g["conflicts"] = _scan_conflicts(
            g,
            name_fuzzy_threshold=name_fuzzy_threshold,
            dob_tolerance_days=dob_tolerance_days,
        )

    # Filter to >= min_confidence at *match-attempt* level (every group with
    # at least one matched pair has confidence ≥ 0.7 in our pipeline; the
    # threshold mostly excludes unmatched singles when set above 0.0).
    if min_confidence > 0.0:
        groups = [g for g in groups if g["confidence"] >= min_confidence]

    return groups
