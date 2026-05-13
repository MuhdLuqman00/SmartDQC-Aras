#!/usr/bin/env python3
"""
Seed zscore_archive with synthetic historical data for testing #11 and #16 gap work.
12 months x 100 children x 5 districts = 6,000 rows.

Usage (from project root, with DB running):
    DATABASE_URL=postgresql://smartdqc:smartdqc@localhost:5432/smartdqc \
        python scripts/seed_zscore_archive.py
"""
import os
import random
from datetime import datetime

import sqlalchemy as sa

DATABASE_URL = os.environ["DATABASE_URL"]
engine = sa.create_engine(DATABASE_URL)

DISTRICTS = [
    ("Petaling",    "Selangor"),
    ("Klang",       "Selangor"),
    ("Gombak",      "Selangor"),
    ("Hulu Langat", "Selangor"),
    ("Sepang",      "Selangor"),
]
N_CHILDREN_PER_DISTRICT = 100
N_MONTHS = 12

random.seed(42)

rows = []
for district, state in DISTRICTS:
    for child_idx in range(N_CHILDREN_PER_DISTRICT):
        ic = f"IC{district[:3].upper()}{child_idx:05d}"
        for month in range(N_MONTHS):
            period = f"2025-{month + 1:02d}"
            waz = round(-1.8 + 0.05 * month + random.gauss(0, 0.25), 4)
            haz = round(-1.5 + 0.03 * month + random.gauss(0, 0.20), 4)
            baz = round(-0.5 + random.gauss(0, 0.15), 4)
            rows.append({
                "ic_no":      ic,
                "period":     period,
                "district":   district,
                "state":      state,
                "waz":        waz,
                "haz":        haz,
                "baz":        baz,
                "age_months": 6 + (child_idx % 54),
                "created_at": datetime.utcnow(),
            })

with engine.begin() as conn:
    conn.execute(sa.text("DELETE FROM zscore_archive"))
    conn.execute(
        sa.text(
            "INSERT INTO zscore_archive "
            "(ic_no, period, district, state, waz, haz, baz, age_months, created_at) "
            "VALUES (:ic_no, :period, :district, :state, :waz, :haz, :baz, :age_months, :created_at)"
        ),
        rows,
    )
print(f"Seeded {len(rows)} rows into zscore_archive.")
