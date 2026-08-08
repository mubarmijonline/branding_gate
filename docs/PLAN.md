# Plan — عهدة, on its way up and back down

Everything here is **عهدة**: money the company hands to a person, which that
person spends against real work and eventually accounts for. One idea runs
through it — **money moves one layer at a time, and the layer above you signs
before Finance ever sees it.**

Status: **signed off. Building.**

## The shape of it

**One running عهدة per person.** Not a numbered advance each time: a single
custody balance that approved requests add to and approved expenses draw down.
That is the balance already in `user_finance_balances`, so nothing recorded so
far is lost or re-entered.

```
        request  ──► manager ──► Finance ──►  ┌──────────────┐
                                              │   عهدة       │
        expense  ◄── manager ◄── Finance ◄──  │  (a running  │
        (against a sales request)             │   balance)   │
                                              └──────┬───────┘
                                    return leftover  │
                                    recorded by Finance
                                    back onto a payment method
```

### Decided

1. **A sales request per expense line**, not per sheet.
2. **The manager may edit any money value** — the expense amounts and the
   requested عهدة amount alike. The original is kept either way.
3. **No re-confirmation by the submitter.** A manager's edit goes straight on to
   Finance, as asked.
4. **The CEO's own request** goes straight to Finance.
5. **Leftover عهدة is returned and recorded.**
6. **تسوية عهدة is raised by the person holding it**, not by Finance. Whenever
   someone has a remaining balance they get a *Settle عهدة* action showing what
   they were given, what they have spent against sales requests, and what is
   left. They declare the amount they are handing back; Finance confirms it has
   arrived, chooses the payment method it goes onto, and only then does the
   عهدة fall. A settlement is one more row on `user_balance_transfers` with
   `transfer_type = 'settlement'`, so it queues, notifies and reads exactly like
   a request, in the other direction. No manager step: handing money back is not
   spending it. *(Say so if you want the manager on this one too.)*

---

## 1. Balance request

### The flow you asked for

```
someone asks for balance
      │
      ├─ the line above approves         ← any of them, never the CEO
      │
      ├─ Finance approves (picks the payment method)
      │
      └─ the money lands on their balance
```

### Who skips the manager step

Nine people report directly to the CEO and are therefore their own top layer:

Sales Head · Assistant · Marketing Manager · Finance Manager · Account Director ·
2D Designer Head · 3D Head · Operations Manager · Pricing Manager

Their requests are created already waiting on Finance. Everyone else — team
leaders and members — waits on their own manager first. The rule is read from
`user.manager_id`, not from a list of names, so it survives a transfer or a new
hire with no edit here.

### What changes

**`user_balance_transfers`**

| Column | Why |
|---|---|
| `status` gains `pending_manager`, `pending_finance` | Two queues need two words. `pending` cannot say who is holding it |
| `manager_approved_by`, `manager_approved_at`, `manager_notes` | Same three columns, same names, as `expense_tracking` already uses |

Existing rows: both are `approved`, so the migration maps nothing and nothing
moves. There are no live pending requests to strand.

**Permissions**

- `user_balance.approve_manager` — new. Granted at `team` scope to every role
  that has people under it (heads and team leaders).
- `user_balance.approve` — unchanged, and now means *the Finance step*.

**Who may approve whom.** Holding the permission is not enough: the route checks
that you are somewhere in the line *above* the requester — their manager, their
manager's manager, and so on up to but never including the CEO. Any one of them
can act and all of them are told, so a leader on leave cannot hold up their
member's عهدة while the head is right there. Same rule as targets — reading
follows scope, writing is narrower and is checked in the route.

**Routes**

- `POST /api/finance/balance-requests/<id>/manager-approve` — new
- `POST /api/finance/balance-requests/<id>/manager-reject` — new, reason required
- the existing approve/reject become the Finance step and refuse anything not
  already `pending_finance`

**Queues.** The approvals page gains a "Waiting on me" list for managers. The
existing Balance Requests tab keeps showing Finance its own queue.

---

## 2. Recording an expense

### The flow you asked for

```
someone records an expense, against a sales request that exists
      │
      ├─ their manager approves        ← and may correct any of the amounts first
      │
      ├─ Finance approves
      │
      └─ posted as it is today: one income line in, one expense line out
         per item, against that item's category
```

### What changes

**Every expense line names a sales request.** `expense_tracking_items` gains
`sales_request_id`, required, validated against `sales_request` on the way in —
not free text, not a number nobody checks. Per line rather than per sheet, so one
submission can cover work on two requests. *(Confirm: per line, or one for the
whole sheet?)*

`/my-expenses` already requires a sales request; this brings the reimbursement
sheet in line with it.

**The manager approves, and may edit first.** Today `manager-approve` accepts
anyone holding the permission, for anybody's sheet — it never looks at the
reporting line. It will check it, exactly like the balance step.

Editing amounts is `expense_tracking.edit_amount`, today Finance-only. The
manager gets it at `team` scope while the sheet is still `pending`. The original
figure is already kept in `original_total_amount` / `original_amount`, so what
was claimed and what was approved both stay on the record and the submitter can
see the difference.

**Finance is unchanged.** Once the manager sends it on, everything Finance does
today happens exactly as it does now — the income transaction, the per-item
expense transactions, the category posting, the balance deduction.

**Notifications** at every hop, to the person who has to act next and to the
submitter when the answer comes back. Nothing in either flow is silent.

---

## What I am not deciding for you

1. **SR per line or per sheet?** Plan assumes per line.
2. **May a manager change the *balance* amount** the way they can change an
   expense amount? Plan assumes no — a balance request is approved or refused as
   asked.
3. **After a manager edits an amount, does the submitter re-confirm?** Plan
   assumes no: it goes straight to Finance, as you described.
4. **The CEO's own balance request** — plan assumes it goes straight to Finance.

---

## Order of work

1. Migration: the new columns and statuses. DDL outside any transaction, since
   `ALTER TABLE` commits implicitly in MySQL.
2. `rbac.py`: the new permission and its grants; re-seed.
3. Balance: manager step, the two routes, the skip rule, the queues.
4. Expense: the SR link and its validation, the reporting-line check, the
   manager's edit window.
5. Tests: the skip rule, the reporting-line refusals, an SR that does not exist,
   the money posted at the end.
6. Deploy, then verify each flow in the browser as a member, a manager and
   Finance.
