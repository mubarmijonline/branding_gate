# 03 - Arabic interface

**Goal:** every page usable in Arabic, right to left, one click from English;
English stays the default.

**Acceptance:**
- `tests/test_i18n.py`: default English loads nothing extra; `/lang/ar` sets the
  cookie and returns to the same page, never off-site; every dictionary entry
  keeps its `{0}` holes and is Arabic; translator matching rules in node.
- Browser in Arabic (home, approved items, finance management, client approval,
  client accounts, 390px home): `dir=rtl`, no page errors, no sideways scroll;
  leftover English is data (names, items, amounts).

**Status:** done 2026-10-16.
