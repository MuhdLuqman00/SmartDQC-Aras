"""Deployment branding — the single place that names the owning organisation.

Neutral defaults so the app ships unbranded; override per deployment via env
vars (no code change needed). Used by the report/export layer for cover pages,
footers and column stamps. Domain logic (WHO z-scores, cleaning rules) never
reads these — they are presentation-only.
"""
from __future__ import annotations

import os

# Organisation name shown on report covers/footers. Bilingual (EN / BM) to match
# the app's bilingual UI; set both to your organisation's name per deployment.
ORG_NAME_EN: str = os.environ.get("SMARTDQC_ORG_NAME_EN", "Your Organisation")
ORG_NAME_BM: str = os.environ.get("SMARTDQC_ORG_NAME_BM", "Organisasi Anda")

# Product/app name (rarely changed).
APP_NAME: str = os.environ.get("SMARTDQC_APP_NAME", "SmartDQC")
