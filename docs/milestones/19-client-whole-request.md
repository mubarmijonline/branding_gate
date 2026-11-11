# 19. Approve all / Reject all for a request

**Goal.** David (2026-11-11): when the client answers the whole event, Sales
decides it in one step and Operations gets one notification, not one per item.

**Acceptance check.** Approve all / Reject all on each request on Client
Approval with a confirmation; every open item decided in one transaction; one
notification naming the request; per-item actions unchanged; same permission
and scope (`tests/test_client_whole_request.py`).

**Status.** Live 2026-11-11.
