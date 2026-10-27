# 10 - Chat like WhatsApp: phone layout, photos, voice notes, seen

**Goal:** the chat works on a phone like WhatsApp and properly on desktop
browsers: one pane at a time on a phone, photos and voice notes, ticks and
"who has seen it", and an @ list of the chat's own members.

**Acceptance:**
- `tests/test_chat_media.py`: request chat members (owner, Operations
  ladder; not a member with no comment permission, not an unrelated seller);
  @ lists limited to members; outsiders get 403 on read, write, list and
  media; ticks go sent -> seen_some when someone opens with `seen=1`; message
  info lists seen / not seen and is the author's only; photo with caption;
  voice note stored as AAC; a non-image refused; group photo and seen.
- Browser, 390px and 1440px, EN and AR: list, open a group, @ shows only its
  members, send text, photo with caption, voice note recorded and played by
  another member, ticks turn to seen after they open it, Message info,
  phone back button closes sheet -> chat -> drawer.

**Status:** live 2026-10-27. Replies (swipe, hover arrow, message menu) live 2026-10-28.

Shipped alongside: storage page (`/admin/storage`), who-assigned-whom on the
operations board, Client Approval without cost for Account Management and
collapsible, item photos kept across request edits.
