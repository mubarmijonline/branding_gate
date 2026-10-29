# Branding Gate - functional PRD

What the system does, for whom, and how "done" is checked. Behaviour only:
how it is built lives in `docs/PLAN.md`. The sales request journey (request,
costing, pricing, client approval, negotiation) is described in
`docs/sales-request-journey.md`; sections are added here as features are
specified.

## Design Requests

Asked for by Gamal Gaber (Design), 28 Oct 2026, with the "Design Request
System" map he sent.

### Who uses it

| Role | What they do |
|---|---|
| Account Manager / Sales (requester) | Opens a design request for a client, follows it, and when it is approved sends it to Operation. |
| Design head (2D or 3D) and Design Manager | Sees every incoming request and assigns a designer. |
| Designer (2D or 3D) | Sees the requests assigned to them, uploads the work (PDF, JPG/PNG, or a link) and submits it for approval. |
| Design Manager | Approves the work or sends it back with a note. Approving is a Design decision: it is not done as Account Director. |
| Operations | Sees the requests sent to Operation and opens their files, to execute. |
| Admin | Everything. |

### Screens and flow

1. **Design Requests page** (Sales / Account menus, and the 2D and 3D Design
   portals). A list of requests the person may see, newest first, with
   2D / 3D and status filters. 2D and 3D are one list with a column, not two
   copies.
2. **New design request** (requesters):
   1. Header shared by the whole request: Company, Client, Job code (an
      optional Sales Request of that client the requester can see), Event
      Date, Deadline, and 2D or 3D.
   2. Category tabs: Social Media, Printing & Production, Video, Mockup &
      Reference, Identity, Presentation, Other.
   3. "Add item" on a tab adds an item of that category with its fields.
      Several items, of any categories, in one request.
   4. Every item: Request Title, Deadline (defaults to the request's),
      Attachments (picked as many times as needed, from different folders,
      each removable before submit), Description. In addition:
      - Printing & Production: Size (cm) H x W x L, Quantity and unit (the
        same units as a sales request item), Type of Printing (Vinyl, Banner,
        Laser, Digital, Silkscreen, UV).
      - Video: Size H x W, Duration.
      - Other: every field above.
   5. Submit. Until then nothing is saved.
3. **Request detail**: header, items with their fields and attachments, and
   under each item its state, its work (the round handed in, what is not
   handed in yet, earlier rounds) and the buttons for that item; the history
   (who did what, when) and the request's buttons at the bottom.

### Workflow and rules

Each item (Gamal, 30 Oct 2026):

```
open --designer submits the item--> in review --approve--> approved --send--> sent
  ^                                     |
  +-------- changes requested <---------+
```

The request: waiting for a designer until one is assigned; then waiting for
approval while any item is in review, changes requested while any item is
returned, approved once every item is approved, sent to Operation once every
item is sent; otherwise with the designer. Cancelled by the requester only
before any work was handed in.

- A request needs a client, an event date or deadline is optional, and at
  least one item with a title.
- Only design heads and the Design Manager assign; they may reassign until
  the work is approved.
- Only the assigned designer uploads work, to one item, and submits that
  item, only with new work since its last round (a file or a link). Handed-in
  work cannot be removed; it stays as an earlier round.
- Only the Design Manager approves an item or asks for changes; asking for
  changes needs a note and returns that item to the designer.
- Only the requester (or someone above them in Sales / Account) sends the
  approved items to Operation, as soon as any are approved.
- Operations sees the sent items with their final round only: no drafts,
  earlier rounds, attachments of the brief, or history, and cannot open
  those files by link.
- The requester may cancel until a designer has handed in work.
- Each step notifies the next person: Design on submit, the designer on
  assign and on changes, the Design Manager on submit for review, the
  requester on each approved item, Operations on send.
- A requester sees their own requests (a team leader their team's, a head
  their department's); Design sees all; Operations sees only those sent to it.
- Files: PDF, images, Office and design files (AI, PSD, EPS, ZIP), up to 20 MB
  each; a photo opens in the
  viewer.

### Out of scope (for now)

- A library of client assets (logos) reused across requests: recommended,
  not built. See PLAN.md.
- Separate 3D categories and fields: 3D uses the same seven until Gamal's 3D
  map arrives.
- Assigning different items of one request to different designers.
- Turning a design request into a sales request automatically.

### Done when

- `tests/test_design_requests.py`: the whole flow by the right people, each
  step refused to the wrong ones, category fields kept per category, scope
  (requester sees own, Operations only sent ones), files readable only by
  who may see the request.
- Browser at 390px and 1440px: create a request with a printing item and a
  video item and attachments, assign, upload, approve, send to Operation,
  each as the right user.
