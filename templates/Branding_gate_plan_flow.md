BRANDING GATE PROJECT FULL BRIEF

1. PROJECT OVERVIEW

Branding Gate is an internal business workflow system built as a monolithic Flask application with a MySQL database. The system manages the full operational cycle for branding, events, production, printing, giveaways, purchases, transfers, digital marketing, expenses, approvals, inventory, suppliers, clients, and companies.

The main application file is branding_gate.py. Most backend routes, APIs, authentication checks, database queries, approval logic, pricing logic, inventory logic, and document handling live inside this file.

Frontend pages are Jinja HTML templates inside the templates folder. The frontend uses Bootstrap, jQuery, DataTables, Select2, SweetAlert2, inline JavaScript, Firebase comments/notifications, and server-rendered HTML.

The system is role-based. Different users see different pages and actions depending on roles such as admin, sales, company_management, operations, finance, inventory, and approval-related roles.

Main project areas:
- Authentication and user roles
- Home/dashboard
- Sales request management
- Dynamic template forms
- Item management inside requests
- Costing and pricing
- Client approval
- Sales head approval
- Operations requests
- Inventory management
- Companies and clients
- Suppliers
- Finance and expenses
- Comments and notifications
- Proposal/change-log workflows

2. TECHNICAL STACK

Backend:
- Python Flask
- MySQL
- Session-based authentication
- Role-based decorators
- JSON fields for dynamic request/template/item data
- File uploads under uploads folder
- Firebase integration for comments/notifications

Frontend:
- Jinja templates
- Bootstrap 4
- jQuery
- DataTables
- Select2
- SweetAlert2
- Font Awesome icons
- Inline JavaScript in many pages

Important deployment/testing:
- Jinja templates are validated before deployment.
- Python syntax is checked with ast.parse.
- App runs through systemd/gunicorn.
- Main service is branding_gate.service.

3. AUTHENTICATION AND AUTHORIZATION FLOW

Users log in through the login page. After login, user data and roles are stored in Flask session.

Common checks:
- If user_id is missing from session, user is redirected to login or receives 401 JSON.
- Page and API access are protected using role_required decorators.
- Some pages allow multiple roles, for example admin and company_management.

Logic:
- Login validates user credentials.
- Session stores user id, username, name, and roles.
- Navigation/menu visibility depends on role.
- APIs return unauthorized errors if session is missing.
- Admin users generally see more cost, inventory, management, and delete/edit actions.

4. MAIN HOME / DASHBOARD FLOW

The home/main page acts as the landing area after login. It routes users toward their modules:
- Sales section
- Operations section
- Finance section
- Admin/management section
- Inventory
- Approvals
- Notifications

Logic:
- Display depends on user role.
- Dashboard cards/buttons point to pages the user can access.
- Some role sections are hidden for unauthorized users.

5. SALES REQUEST PAGE

Main page: sales_request.html
Backend: sales request APIs in branding_gate.py

This is the central module of the system.

Purpose:
Sales users create requests for client work. A request can include multiple request types, dynamic template fields, items/services, dates, company/client data, comments, images, costs, selling prices, and approval states.

Main flow:
1. Sales user opens Sales Request page.
2. Page loads DataTable of requests from /api/sales/requests.
3. Page loads companies, clients, templates, item catalog, and saved item templates.
4. User clicks Add Request.
5. User selects company/client, title, priority, start date, end date, and request types.
6. Based on request types, template sections load automatically.
7. User fills template fields.
8. User adds items under each template/request type.
9. User saves request.
10. Request appears in table.
11. Operations/admin may add cost.
12. Sales/pricing adds selling price.
13. Client approval flow begins.
14. Items may later become inventory items.

Sales Request table columns:
- Request ID
- Title
- Request Type
- Client
- Company
- Priority
- Status
- Start Date
- End Date
- Items Count
- Costed Items, admin only
- Total Cost, admin only
- Total Sell
- Client Approval Stage
- Sales Added By
- Actions

Admin detection:
- The frontend detects admin layout by table header column count.
- 16 columns means admin view.
- 14 columns means non-admin view.
- DataTable column count must match HTML headers exactly.

Main actions:
- Edit request
- View details
- Comments
- Set Prices
- Generate Proposal
- View Change Log
- Delete request, when allowed

6. SALES REQUEST TEMPLATE SYSTEM

Templates are dynamic forms attached to request types.

User does not manually pick templates. Instead, user selects request types, and the system automatically loads the correct template form.

Template mapping:
- T1: Event, Booth, Activation, Media
- T2: Production, Printing, Giveaways, Purchases, Material delivery, Receiving material
- T3: Digital marketing
- T4: Transfers
- T5: Others

T1 fields:
- Event Name
- Contact Number
- Location
- Event Duration
- Setup Date
- Event Date
- Dismantle Date
- Hotel Name
- Hall Name
- General Notes

T2 fields:
- Contact Number
- Required Delivery Date
- Delivery Location
- General Notes

T3 fields:
- Brand Name
- Contact Number
- Campaign Start Date
- Campaign End Date
- General Notes

T4 fields:
- Contact Number
- Pickup Date
- Delivery Date
- Transfer Type
- General Notes

T5 fields:
- Service Name
- Start Date
- End Date
- Contact Number
- Location
- General Notes

Multiple template instance logic:
If a user selects multiple request types, the system creates a separate template instance for each request type.

Example:
Selected request types:
- Event
- Booth
- Production

Generated instances:
- T1 instance for Event
- T1 instance for Booth
- T2 instance for Production

This allows each request type to have its own fields and item list, even when two request types use the same base template.

Template instance ID format:
- template_id + request_type
Example:
- 1_Event
- 1_Booth
- 2_Production

Template loading flow:
1. User checks/unchecks request type.
2. System detects if user is in Add modal or Edit modal.
3. System reads selected request types from the correct modal.
4. System maps request types to templates.
5. System creates required template instances.
6. System adds new instances without rebuilding existing ones.
7. Removed request types remove their related instance.
8. Already filled forms are preserved when possible.

7. TEMPLATE FIELD LOGIC

Auto-population:
Some template fields auto-fill from the main request fields.

Auto-filled values include:
- Selected client name
- Selected company name
- Request start date
- Request end date
- Calculated duration

Duration logic:
- Duration = end date - start date + 1 day
- Same-day event = 1 day
- Duration fields are updated when start/end dates change.
- The code retries if fields are not yet rendered because templates are dynamic.
- The code also restores duration if another script clears it accidentally.

Date validation:
Template date fields can be restricted to the main request date range.
For example:
- Event Date must be inside request start/end date.
- Delivery Date must be inside request start/end date.
- Campaign dates must be inside request start/end date.

Manual edit protection:
If a user manually changes an auto-filled field, the system marks it as manually edited and does not overwrite it later.

Location companion logic:
Any location field automatically receives:
- Governorate dropdown
- Google Maps Link field

Detected location fields:
- location
- delivery_location
- pickup_location
- event_location
- any field ending in _location

The extra fields are saved into template JSON with names like:
- location_governorate
- location_google_maps_link
- delivery_location_governorate
- delivery_location_google_maps_link

8. SALES REQUEST ITEMS LOGIC

Items represent products, services, rented items, production items, printed items, giveaways, transfers, or other request deliverables.

Items can include:
- Item name
- Quantity
- Unit
- Width
- Height
- Depth
- Dimension calculation formula
- Sell/rent type
- Rental days
- Include quantity in calculation
- Include days in calculation
- Image
- Comment
- Catalog item reference

Item UI:
- Items are added under each request type/template instance.
- Item rows are compact and collapsible.
- Header summary updates live from item name, quantity, and unit.
- User can expand/collapse item details.
- Items can be removed.

Units:
- Unit
- Meters

Dimension logic:
- User enters dimensions in centimeters.
- System saves/calculates dimensions in meters.
- Submission divides width/height/depth by 100.
- Edit mode converts stored meter values back to centimeters for display using a heuristic.

Example:
User enters:
- Width = 250 cm
Saved/calculated:
- Width = 2.5 m

Dimension formula examples:
- W
- W*H
- W*H*D

Dimension multiplier:
- If formula is W*H, multiplier = width * height.
- If formula is W*H*D, multiplier = width * height * depth.
- This multiplier affects pricing totals.

9. ITEM CATALOG AND SAVED ITEM TEMPLATES

The item entry form supports reusable item data from two sources.

Inventory item catalog:
- Loaded from /api/item-catalog.
- Used in item searchable dropdown.
- Selecting an item can fill name, unit, description, dimensions, formula, image, and catalog reference.
- Dropdown display shows rich info such as dimensions, unit, usage count, image indicator, and formula indicator.

Saved item templates:
- Stored in browser localStorage.
- Used as a legacy quick-fill system.
- Can save and reuse item details.

10. SALES REQUEST SAVE LOGIC

When saving, the frontend collects:
- Main request fields
- Selected company/client
- Title
- Priority
- Dates
- Selected request types
- Template instance fields
- Flattened template fields for backward compatibility
- Items under each request type
- Item images
- Dimension and calculation data

Important helper logic:
- collectTemplateData
- collectTemplateFieldsForSubmission
- flattenInstanceFields
- getSelectedRequestTypes

Backend saves:
- Sales request record
- Request data JSON
- Template data JSON
- Sales request items
- Item attributes JSON
- Uploaded images/documents if present

11. EDIT SALES REQUEST FLOW

Edit flow:
1. User clicks Edit.
2. Existing request data is loaded.
3. Main fields are populated.
4. Selected request types are restored.
5. Template instances are rebuilt.
6. Saved template data is populated back into fields.
7. Location companion fields are restored.
8. Items are loaded back into their sections.
9. Stored dimensions are shown in user-friendly units.
10. User updates and saves.

Important edit detail:
Older items may have dimensions stored differently. The code uses a heuristic:
- Small values may be treated as meters and converted to centimeters.
- Larger legacy values may be treated as already centimeters.

12. PRICING MODE

The same sales_request.html page is reused for the pricing portal.

Pricing mode is controlled by:
window.PRICING_MODE = true/false

In pricing mode:
- Edit button is hidden.
- Pricing dashboard filters are active.
- User focuses on setting selling prices, repricing, and pending approvals.

Pricing dashboard filters:
- All
- Needs Pricing
- Needs Repricing
- Pending

DataTables custom filtering reads approval_stats:
- not_priced
- repricing
- pending

13. SET SELLING PRICE FLOW

User clicks Set Prices.

Flow:
1. Modal opens.
2. Request items are loaded.
3. Items are displayed even if no cost price exists.
4. User enters sell price per item.
5. System calculates total sell.
6. System calculates Gross % and Net %.
7. User saves prices.
8. Backend updates sell_per_item and total_sell.
9. Price history/change log may be created.
10. Request status/approval stats update.

Important change:
Selling price can now be added even if cost price is missing. Cost is no longer required before pricing.

Pricing formula:
total_sell = sell_per_item * effective_quantity * effective_days * dimension_multiplier

Where:
- effective_quantity = item quantity if quantity is included, otherwise 1
- effective_days = rental days if rent and days are included, otherwise 1
- dimension_multiplier = result of W/H/D formula
- sell items usually use days = 1

Pricing UI:
- Total Cost card
- Total Sell card
- Gross % badge
- Net % badge
- Per-item summaries
- Negotiation/repricing indicators

Gross and Net:
- Markup label was renamed to Gross %.
- Gross % and Net % display under Total Cost / Total Sell containers.

14. COSTING LOGIC

Costing is separate from pricing.

Cost fields:
- cost_per_item
- total_cost

Costing can be added by admin/operations/costing roles.

Request table shows:
- Costed items count
- Total cost, admin only
- Not costed badge in approval summary

Costing affects:
- Profit calculations
- Gross %
- Net %
- Costed item statistics
- Proposal readiness
- Inventory/profit expectations

But costing does not block selling price entry anymore.

15. CLIENT APPROVAL FLOW

After pricing, items can move to client approval.

Possible states:
- Not costed
- Not priced
- Pending approval
- Negotiating
- Repricing
- Approved
- Rejected

Request table summarizes item statuses with badges:
- Not Costed
- No Price
- Re-Pricing
- Pending
- Negotiating
- Approved
- Rejected
- All Approved

Flow:
1. Sales/pricing sets selling price.
2. Items are sent for client approval.
3. Client reviews proposal/items.
4. Client approves, rejects, or negotiates.
5. If negotiation happens, item moves to negotiation/repricing.
6. Sales updates price if needed.
7. Approved items become ready for next workflow step.

16. CLIENT APPROVAL PAGE

Main page: client_approval.html

Purpose:
Allows client-facing or internal approval handling for sales request items.

Logic:
- Shows items awaiting approval.
- Displays item details, price, quantity, and approval status.
- Allows approval/rejection/negotiation depending on role and workflow.
- Stores approval decisions and updates item status.
- Negotiation can create repricing requirement.
- Approved items can later be used for inventory creation.

17. SALES HEAD APPROVAL PAGE

Main page: sales_head_approval.html

Purpose:
Handles sales management approval before/after pricing or before client approval depending on configured workflow.

Logic:
- Sales head reviews requests or items.
- Can approve or reject.
- Approval status updates request/item workflow.
- Ensures sales management validation before next stage.

18. APPROVALS PAGE

Main page: approvals.html

Purpose:
General approval dashboard.

Logic:
- Shows pending approvals according to user role.
- Can display requests/items needing action.
- Routes user to relevant approval operation.
- Supports approval tracking and status display.

19. APPROVED ITEMS PAGE

Main page: approved_items.html

Purpose:
Shows approved items that are ready for downstream processing such as inventory or operations.

Logic:
- Lists items approved by client/internal workflow.
- Allows admin/operations to continue fulfillment.
- May connect with inventory creation from sales item.

20. OPERATION REQUEST PAGE

Main page: operation_request.html

Purpose:
Operations team handles production/execution work after or during sales request flow.

Logic:
- Operations can see requests/items requiring action.
- Costing may be added from operations side.
- Operation status can be updated.
- Production/delivery/transfer tasks can be tracked.
- Comments and status logs support collaboration.

21. OPERATION MAIN PAGE / OPERATIONS SECTION

Pages:
- operation_mainpage.html
- operations_section.html

Purpose:
Operations dashboard and navigation.

Logic:
- Shows operation-related modules and pending tasks.
- Role-based access.
- Guides operations users to requests, approvals, or work queues.

22. INVENTORY MANAGEMENT PAGE

Main page: inventory_management.html

Purpose:
Manages inventory items, stock, simple/composite items, credit/consignment, and transactions.

Main inventory concepts:
- Simple items
- Composite items
- Stock quantity
- Inventory transactions
- Credit/consignment items
- Inventory item creation from sales items

Important logic:
- inventory_items.item_type must be simple or composite.
- If unsure, force simple.
- Inventory triggers manage transaction history and stock balance.
- Code should not manually insert into inventory_transactions when triggers already handle it.

Create inventory from sales item flow:
1. Sales item is approved.
2. Admin opens create-from-sales action.
3. Backend reads sales item attributes JSON.
4. Width/height/depth/specifications are extracted.
5. Inventory code is generated.
6. Inventory item is inserted.
7. item_type is set to simple unless composite explicitly applies.
8. DB trigger creates transaction and updates stock.

Credit/consignment flow:
- Insert into inventory_credit_items.
- Triggers create transactions and update inventory stock.
- Avoid manual transaction insert to prevent trigger conflicts.

23. INVENTORY SELECTION PAGE

Main page: inventory_selection.html

Purpose:
Supports selecting inventory items for use in other workflows.

Logic:
- User searches/selects existing inventory.
- Selected inventory item data can be applied to request/item forms.
- Helps avoid duplicate item entry.

24. ITEM MANAGEMENT PAGE

Main page: item_management.html

Purpose:
Manages item catalog/master items used by sales requests and inventory.

Logic:
- Add/edit/delete catalog items.
- Store item name, description, dimensions, unit, image, and formula.
- Catalog items appear in sales request item dropdowns.
- Usage count and metadata help users pick correct items.

25. COMPANY MANAGEMENT PAGE

Main page: company.html
Route: /company

Purpose:
Manage parent companies.

Fields:
- Company Name
- Industry / Sector
- Address
- Tax Number
- VAT Number
- Phone Number
- Email Address
- Website / Social Media
- Primary Contact Person
- Additional Notes
- Documents
- Attachment Links

Flow:
1. Admin/company_management user opens company page.
2. DataTable loads companies from /api/companies.
3. User can add company.
4. User can edit company.
5. User can view documents.
6. User can delete company if allowed.

Document logic:
- If Tax Number or VAT Number is provided, supporting documentation is required.
- Supporting documentation can now be an uploaded file or an attachment link.
- Files are saved under uploads/companies/company_id.
- Links are stored in company_documents with document_type = link.
- Link rows open in new browser tab.
- Uploaded files download normally.

Modal logic:
- Add/Edit company modals use static backdrop.
- This prevents modal from closing unexpectedly while selecting/uploading files.

26. CLIENT MANAGEMENT PAGE

Main page: client.html

Purpose:
Manage clients/contacts, often linked to parent companies.

Logic:
- Add/edit/delete clients.
- Link client to parent company.
- Client dropdowns in sales request page are populated from client API.
- When company is selected, client list can be filtered by parent company.
- Client selection can auto-populate template fields.

27. SUPPLIER PAGE

Main page: supplier.html

Purpose:
Manage suppliers.

Logic:
- Add/edit/delete supplier records.
- Supplier data may be used by purchases, costing, inventory, or operations.
- Schema note: supplier table uses primary_phone, not contact_mobile.
- Queries should alias primary_phone as contact_mobile when needed.

28. SUPPLIER REPORT PAGE

Main page: supplier_report.html

Purpose:
Supplier reporting and review.

Logic:
- Shows supplier-related data in report/table format.
- Used for management review or operational reporting.

29. FINANCE MANAGEMENT PAGE

Main page: finance_management.html

Purpose:
Finance dashboard/management page.

Logic:
- Gives finance users access to expense tracking, approvals, and finance workflows.
- Role-based display.
- Connects to expense and approval pages.

30. EXPENSE TRACKING PAGE

Main page: expense_tracking.html

Purpose:
Create and track expenses.

Logic:
- User enters expense details.
- Expense may include category, amount, date, description, attachments, and status.
- Expense enters approval workflow.
- Finance/admin can review depending on role.

31. MY EXPENSES PAGE

Main page: my_expenses.html

Purpose:
User-specific expense list.

Logic:
- Shows expenses submitted by current user.
- User can track status.
- May allow editing pending expenses depending on workflow.

32. EXPENSE APPROVAL PAGES

Pages:
- expense_tracking_approval.html
- finance_expense_approval.html
- finance_approvals.html

Purpose:
Approve or reject expenses.

Logic:
- Approver views pending expenses.
- Approver approves/rejects.
- Status updates.
- Finance gets visibility over approved/rejected/pending expenses.
- May support comments/logs.

33. FINANCE SECTION PAGE

Main page: finance_section.html

Purpose:
Finance navigation section.

Logic:
- Shows finance-related actions based on role.
- Links to finance management, approvals, expense tracking, and reports.

34. ADMIN / MANAGEMENT PAGES

Pages:
- admin_section.html
- management_admin.html
- users.html
- entity_management.html

Purpose:
System administration.

Admin section:
- Entry point for admin tools.

Users page:
- Manage users.
- Assign roles.
- Activate/deactivate users.
- Control access.

Entity management:
- Manage shared entities used in the system.
- Could include company/client/supplier-like supporting data depending on implementation.

Management admin:
- Higher-level administrative controls and management dashboard.

35. NOTIFICATIONS PAGE

Main page: notifications.html

Purpose:
Show user notifications.

Logic:
- Notifications may come from comments, mentions, approvals, workflow status changes, or Firebase.
- User sees recent notifications.
- Notifications can support read/unread behavior.

36. COMMENTS SYSTEM

Template: comments_widget.html
Used across pages such as sales requests.

Purpose:
Allow collaboration on requests/items/workflows.

Logic:
- Comments attached to source records.
- Source can be general, costing, operations, approval, etc.
- Mentions are supported.
- Comment badge count appears in tables.
- Firebase integration supports live or near-live updates.
- Comments help different departments communicate in the same request context.

37. WORKFLOW TIMELINE

Template: workflow_timeline.html

Purpose:
Show chronological workflow events.

Logic:
- Displays request/item progress over time.
- Can include creation, edits, costing, pricing, approvals, comments, status changes, and logs.
- Helps users understand where the request is in the process.

38. PROPOSAL GENERATION FLOW

Proposal generation is available from Sales Request actions.

Flow:
1. User clicks Generate Proposal.
2. System checks request data and items.
3. Proposal uses client/company/request/item/pricing data.
4. If data is incomplete, user may receive warning.
5. Generated proposal can be downloaded/viewed.

Important:
- Proposal generation depends heavily on item pricing and request details.
- Costed count and total item count are passed in the action menu.

39. CHANGE LOG FLOW

Many workflows create logs.

Change log captures:
- Request edits
- Price changes
- Approval changes
- Status changes
- Possibly comments or operations changes

Purpose:
- Audit trail
- Accountability
- Review history

40. CLIENT / COMPANY / SALES REQUEST RELATIONSHIP

Company:
- Parent company / business entity.

Client:
- Individual/contact/customer linked to company.

Sales Request:
- Work request for a client/company.

Flow:
1. Company is created.
2. Client is created and linked to company.
3. Sales request selects company/client.
4. Template fields can auto-populate company/client data.
5. Pricing/proposals use company/client data.

41. REQUEST STATUS AND APPROVAL STATUS

The system uses multiple status layers:

Request-level status:
- General request progress.

Item-level approval_status:
- Tracks approval/client workflow per item.

Approval statistics:
- not_costed
- not_priced
- pending
- negotiation
- repricing
- approved
- rejected

These stats are summarized in Sales Request table.

42. ROLE-BASED VISIBILITY

Examples:
- Admin sees cost columns.
- Sales can create requests and set prices.
- Company management can manage companies.
- Operations can handle operation requests/costing.
- Finance can handle expenses and finance approvals.
- Admin can manage users and system data.

UI and backend both enforce permissions.

43. DATA STORAGE PATTERNS

Important storage patterns:
- Standard fields stored in normal MySQL columns.
- Dynamic template fields stored as JSON.
- Item custom attributes stored as JSON.
- Dimensions can be stored in item attributes.
- Uploaded files stored on disk, paths stored in database.
- Links stored in document_path when document_type = link.

44. DATABASE TRIGGER RULES

Inventory triggers are important.

Avoid:
- Manual insert into inventory_transactions when trigger already creates transaction.

Use:
- Insert into correct inventory source table.
- Let trigger update transaction and stock.

This prevents duplicate transactions, balance conflicts, and trigger loops.

45. SELECT2 MODAL LOGIC

Select2 dropdowns inside Bootstrap modals need dropdownParent.

The helper safeInitializeSelect2:
- Destroys old Select2 safely if already initialized.
- Applies default options.
- Detects closest modal.
- Sets dropdownParent to that modal.
- Initializes Select2.

This prevents corrupted dropdown/search behavior inside modals.

46. FILE UPLOAD LOGIC

Used in:
- Company documents
- Sales request/item images
- Possibly expenses and other modules

General logic:
- Validate file size.
- Store file under uploads folder.
- Save file path and metadata in database.
- Show download/view actions later.

Company-specific:
- Max file size is 20MB.
- Tax/VAT requires file or link.
- Edit modal can add more documents.
- Delete document is blocked if it would leave tax/VAT company without support document.

47. IMPORTANT CURRENT CUSTOMIZATIONS / RECENT CHANGES

Recent completed changes:
- Pricing portal uses sales_request.html with pricing_mode enabled.
- Pricing dashboard cards filter DataTable.
- Markup label renamed to Gross %.
- Gross and Net badges moved under Total Cost and Total Sell cards.
- Location fields automatically add Governorate and Google Maps Link.
- Select2 inside modals fixed by dropdownParent auto-detection.
- Item add UI improved with compact/collapsible rows.
- Dimensions entered in CM, saved/calculated as meters.
- Selling price can be added even if cost price is missing.
- Company documents now support attachment links, not only file upload.
- Company file picker/modal issue fixed by static modals.

48. END-TO-END SALES REQUEST BUSINESS FLOW

Full business flow:
1. Admin creates companies and clients.
2. Sales creates a Sales Request.
3. Sales selects one or more request types.
4. System auto-loads templates.
5. Sales fills dynamic template data.
6. Sales adds items under each request type.
7. Sales saves request.
8. Operations/admin adds costing when ready.
9. Pricing/sales sets selling price, even if cost is missing.
10. Proposal can be generated.
11. Client approval starts.
12. Client approves, rejects, or negotiates.
13. Negotiation triggers repricing if needed.
14. Approved items become ready for operations/inventory.
15. Inventory items can be created from approved sales items.
16. Finance/expense workflows may run in parallel for costs and approvals.
17. Comments, notifications, and change logs track collaboration and history.

49. HIGH-LEVEL PAGE MAP

login.html:
- Login/authentication.

main.html:
- Base layout and shared UI shell.

home.html:
- Home/dashboard after login.

sales_section.html:
- Sales navigation.

sales_mainpage.html:
- Sales dashboard/menu.

sales_request.html:
- Main sales request, templates, items, pricing, comments, approvals summary.

client_approval.html:
- Client approval workflow.

sales_head_approval.html:
- Sales management approval.

approvals.html:
- General approval dashboard.

approved_items.html:
- Approved items ready for next stage.

operation_mainpage.html:
- Operations dashboard.

operations_section.html:
- Operations navigation.

operation_request.html:
- Operations request handling and costing/execution workflows.

inventory_management.html:
- Inventory items, stock, transactions, simple/composite items.

inventory_selection.html:
- Select inventory/catalog items.

item_management.html:
- Item catalog/master items.

company.html:
- Parent company management and company documents/links.

client.html:
- Client/contact management.

supplier.html:
- Supplier management.

supplier_report.html:
- Supplier reporting.

finance_section.html:
- Finance navigation.

finance_management.html:
- Finance dashboard.

expense_tracking.html:
- Submit/track expenses.

my_expenses.html:
- User’s own expenses.

expense_tracking_approval.html:
- Expense approval workflow.

finance_expense_approval.html:
- Finance expense approval.

finance_approvals.html:
- Finance approvals dashboard.

admin_section.html:
- Admin navigation.

management_admin.html:
- Management/admin dashboard.

users.html:
- User and role management.

entity_management.html:
- Shared entity management.

notifications.html:
- User notifications.

comments_widget.html:
- Reusable comments component.

workflow_timeline.html:
- Timeline/history component.

50. SYSTEM SUMMARY

Branding Gate is an ERP-style workflow system for branding and production operations. Sales Requests are the core object. Templates describe the type of work. Items describe what will be delivered. Costing and pricing define financials. Client approval decides acceptance. Operations and inventory handle fulfillment. Finance handles expenses and approvals. Companies, clients, suppliers, comments, notifications, and logs support the full workflow.

The most important logic to understand is:
- Request types automatically create template instances.
- Each request type can have its own fields and items.
- Dynamic data is saved in JSON.
- Items carry dimensions, quantities, images, and formulas.
- Costing and pricing are separate.
- Pricing can happen before costing.
- Approval is tracked per item and summarized per request.
- Inventory creation from sales items must respect database triggers.
- Role permissions control what each user can see and do.