# 07 - Mobile shell, cards and push

**Goal:** on a phone the system works like an app: one shell (trimmed top bar,
bottom tab bar, "More" sheet), every list page readable as cards with no
sideways scrolling, full-screen forms and modals, big tap targets, installable
to the home screen, with notifications arriving as phone push.

**What it is:**
- `static/css/bg-mobile.css` (phones only, `max-width: 767.98px`, loaded on every
  page before the Arabic overrides) and `static/js/bg-mobile.js`.
- The tab bar and the More sheet are read from the navbar's own gated markup,
  keyed on the menu ids, so nothing is offered that the server hid; the three
  navbar badges are mirrored onto the tabs.
- Every `<table>` becomes one card per row: the script labels each cell from its
  header (`data-label`), picks the title column (first name-like header) and the
  Actions column; the CSS stacks the cells and lays the buttons in a row. A page
  keeps a table with `data-mobile="scroll"`, or names columns with
  `data-mobile-title` / `data-mobile-actions`. client, company and
  sales_request keep their own card views (opted out).
- Headers with controls stack; inline px widths on inputs are overridden;
  BS4 stat cards go two-up and short; modals are full-screen with a sticky
  footer; inputs are 16px (no iOS zoom) and 44px tall.
- PWA: one viewport (zoom allowed, notch-safe), `static/manifest.webmanifest`,
  icons under `static/img/icons/`, theme colour. nginx serves `.webmanifest`
  with its own type (the `/static/` block).
- Push: `static/js/bg-push.js` registers the Firebase service worker, asks
  permission on the first tap on the bell, saves the device token under the
  user (`/api/push/register`). `notify_users` then sends every bell notification
  to the person's devices (`push_to_users`) through the app's own Firebase
  project; a tap on the push opens the notification's link. The leftover
  sender that pointed at another project (`eltime-6571b`) is gone.
  Needs `BG_FCM_VAPID_KEY` in `/development/projects/branding_gate/.env`
  (Firebase console > Cloud Messaging > Web Push certificates); without it,
  phones get the bell only.

**Acceptance:**
- `tests/`: the suite (route coverage counts the two push routes as login-only;
  the register flow stores the token under the user and refuses anonymous).
- Browser at 390px, EN and AR: tab bar with five tabs, More sheet lists every
  menu, no page scrolls sideways (operations, expense approval, sales, finance
  management, clients, invoices, approved items, my expenses, users, costing,
  supplier, finance approvals, notifications), cards show every field and all
  action buttons.
- Phone: "Add to Home Screen" offered; after allowing notifications a bell
  notification also arrives as a push and opens its page.

**Status:** live 2026-10-26. Push waits on the VAPID key.
