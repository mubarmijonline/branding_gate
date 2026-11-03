"""
The tests' own database (Ahmed, 2026-11-03).

The suite used to run on the live database and roll back. Rolled-back rows
leave no data, but MySQL never hands back an AUTO_INCREMENT value, so every run
burned a few hundred request numbers (15 requests, numbered 23645 to 46577).
Every test module that touches MySQL or the app imports this first, so the
app reads BG_DB before it opens a connection. tests/run.sh refreshes the copy
from live before each run.
"""

import os

DB = os.environ.setdefault('BG_DB', 'branding_gate_test')
os.environ.setdefault('BG_MONGO_DB', 'branding_gate_test')

if DB == 'branding_gate':
    raise SystemExit('Refusing to run the tests on the live database (BG_DB=branding_gate).')
