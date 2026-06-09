"""Tests for SymSpell symmetric-delete fuzzy IC matching (D5-M1)."""

import time
import random
from backend.ml.entity import link_records_v2


def _rec(ic, name="ALI", dob="2021-03-03", src="a", ds="d1"):
    """Helper to create a record dict."""
    return {
        "ic": ic,
        "name": name,
        "dob": dob,
        "source_type": src,
        "dataset_id": ds,
    }


def _group_signature(groups):
    """Order-independent signature: set of frozenset(member identities) per group."""
    sig = set()
    for g in groups:
        members = frozenset(
            (s.get("ic"), s.get("source_type"), s.get("dataset_id"))
            for s in g["sources"]
        )
        sig.add(members)
    return sig


def test_symspell_equivalence_small():
    """New Pass 2 must produce identical groups to the all-pairs baseline on a mixed fixture."""
    recs = [
        _rec("900101010001", src="myvass"),
        _rec("900101010001", src="ncdc"),  # exact dup
        _rec("900101010002", src="ncdc"),  # 1-digit typo of ...0001 (last digit)
        _rec("910202020005", src="myvass"),  # unrelated
        _rec(
            "010202020005", src="ncdc"
        ),  # 1-digit typo in FIRST digit -> must still link
    ]
    groups = link_records_v2(
        recs, fuzzy_ic=True, fuzzy_ic_max_distance=1, min_confidence=0.0
    )
    sizes = sorted(len(m) for m in _group_signature(groups))
    assert sizes == [2, 3], f"Expected [2, 3], got {sizes}"


def test_symspell_recall_typo_in_leading_digits():
    """A typo in IC positions 1-6 (birth date) must STILL be caught — the property blocking loses."""
    recs = [
        _rec("210303075001", src="a"),
        _rec("210303075002", src="b"),  # last-digit typo
        _rec("110303075001", src="c"),  # first-digit typo of the first IC
    ]
    groups = link_records_v2(recs, fuzzy_ic_max_distance=1, min_confidence=0.0)
    big = max(groups, key=lambda g: len(g["sources"]))
    assert len(big["sources"]) == 3, (
        f"Expected 3 sources in largest group, got {len(big['sources'])}"
    )


def test_symspell_100k_perf():
    """100K pooled records link in well under 30s (was minutes-to-hours)."""
    random.seed(0)
    recs = []
    for i in range(100_000):
        ic = f"21{random.randint(0, 12):02d}{random.randint(1, 28):02d}{random.randint(0, 99):02d}{i % 10000:04d}"
        recs.append(_rec(ic[:12].ljust(12, "0"), src="a", ds=f"d{i % 5}"))
    t = time.time()
    link_records_v2(recs, min_confidence=0.0)
    dt = time.time() - t
    assert dt < 30, f"Performance test failed: took {dt:.1f}s (limit is 30s)"
