# Sales Request Flowchart and Section Controls

## Sales Request Flow

1. Sales selects the company and client.
2. Sales creates the request, completes the templates, and adds request items.
3. Requests starting within five days go to Admin for urgent approval.
4. Operations adds item costing.
5. Sales adds selling prices.
6. Sales generates the proposal and submits costed and priced items for client approval.
7. The client approves, rejects, or negotiates each item. Sales records the decision.
8. Negotiations go to the Sales Head. A Sales Head approval always sends the item to Re-Pricing.
9. Re-Pricing may enter a new selling price, request re-costing first, or decline the negotiation.
10. When re-costing is requested, Operations updates the cost and returns the item to Re-Pricing.
11. Revised items return to client review.
12. Approved items become ready for operational handoff.

## Sales Request Section Controls

| Sales Request section | View | Create | Edit or act | Approve or decide | Restrictions |
|---|---|---|---|---|---|
| Request List and Details | Sales, Admin | - | Sales, Admin | - | Uses the Sales Request permission |
| New Sales Request | Sales, Admin | Sales, Admin | Sales, Admin | Admin for urgent dates | Normal requests do not require approval |
| Request Templates and Items | Sales, Admin | Sales, Admin | Sales, Admin | - | Costed items cannot be removed or materially changed |
| Urgent Request Approval | Admin | Sales submits | Admin | Admin | Required when a non-admin request starts within five days |
| Costing | Operations, Admin | - | Operations, Admin | Operations owns cost | Separate from selling-price entry |
| Selling Price and Re-pricing | Sales, Pricing/Operations, Admin | - | Sales, Pricing/Operations, Admin | Pricing owns negotiation pricing | Re-pricing returns the item to client review |
| Proposal Generation | Sales, Admin | - | Sales, Admin | Sales confirms | Uses eligible costed and priced items |
| Client Approval Submission | Sales, Admin | - | Sales, Admin | Sales submits | Requires both cost and selling price |
| Client Approve, Reject and Negotiate | Sales, Admin | - | Sales records decision | Client decision | No external Client login |
| Sales Head Negotiation Review | Sales Head, Admin | - | Sales Head, Admin | Sales Head | May decline or approve; approval always sends to Re-Pricing |
| Pricing Negotiation Decision | Pricing/Operations, Admin | - | Pricing/Operations, Admin | Pricing | Chooses Re-Price Now, Re-Cost First, or Decline |
| Negotiation Re-Costing | Operations, Admin | - | Operations, Admin | Operations owns cost | Available only after Pricing requests re-costing; returns to Pricing |
| Comments and Mentions | Sales, Admin | Sales, Admin | Author or Admin | - | Attached to the Sales Request |
| Change Log and Workflow Timeline | Sales, Admin | System generated | - | - | Records all major workflow changes |
| Request Status Control | Sales, Admin | - | Admin | Admin | Manual status changes are Admin controlled |
| Approved-item Operational Handoff | Operations, Admin | - | Operations, Admin | Client approval required | Only approved items move to Operations |
