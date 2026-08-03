# Sales Request Journey PDF Redesign

## Purpose

Replace the current compact PDF with a client-readable document focused only on the Sales Request process and the roles controlling each section.

## Document Format

- Two A3 landscape pages.
- Page 1 is dedicated to the Sales Request journey.
- Page 2 contains the section-by-section role-control matrix.
- Branding Gate logo and restrained system colors are retained.
- No general system journey, finance workflow, inventory details, or technical permission-gap notes are included unless they directly affect the Sales Request flow.

## Page 1: Sales Request Flowchart

The journey is presented as one large flowchart using horizontal role lanes instead of narrow vertical stage panels. Every activity sits inside the lane of the role responsible for performing it.

Role lanes:

1. Sales
2. Admin
3. Operations
4. Sales Head
5. Client Decision

Flow stages:

1. Sales selects the company and client.
2. Sales creates the request, selects request types, completes templates, and adds items.
3. If the request starts within five days, Admin approves or rejects the urgent request.
4. Operations adds item costs.
5. Sales adds selling prices.
6. Sales generates the proposal and submits fully costed and priced items for client approval.
7. The client approves, rejects, or negotiates each item. Sales records the decision in the system.
8. A negotiation goes to the Sales Head, who declines it or routes it to Operations for re-costing or Sales for re-pricing.
9. Revised items return to client review.
10. Approved items leave the Sales Request approval journey and become ready for operational handoff.

Arrow rules:

- Main progression runs from left to right.
- Arrows use orthogonal horizontal and vertical segments.
- Arrows never pass through activity boxes or labels.
- Return paths use reserved channels above or below the lanes.
- Decision branches are labeled at the branch point.
- Approve, reject, negotiate, re-cost, and re-price paths remain visually distinct.

## Page 2: Section Role Controls

The matrix contains only Sales Request sections and actions.

Columns:

- Sales Request section
- View
- Create
- Edit
- Approve or decide
- Notes and restrictions

Sections:

- Request list and details
- New Sales Request
- Request templates and items
- Urgent request approval
- Costing
- Selling price and re-pricing
- Proposal generation
- Client approval submission
- Client approve, reject, and negotiate
- Sales Head negotiation review
- Comments and mentions
- Change log and workflow timeline
- Request status control
- Approved-item operational handoff

Role treatment:

- Admin is shown as an override where the current role decorator grants it access.
- Client is shown as a business decision-maker, with a note that Sales currently records the decision.
- Pricing-only access is not presented as save authority because the current save-price endpoint requires Sales.
- Operations owns costing and receives approved items.
- Sales Head controls negotiation approval and routing.

## Acceptance Criteria

- The PDF contains exactly two A3 landscape pages.
- Page 1 uses most of the available page width and height.
- All text is readable at fit-to-page size.
- No arrow intersects an activity box or another arrow label.
- Every process box clearly identifies its controlling role through its lane.
- Page 2 lists the controlling roles for every Sales Request section.
- The generated PDF opens successfully and all pages render as nonblank images.
