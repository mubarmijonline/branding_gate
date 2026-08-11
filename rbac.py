"""
Role-based access control policy for Branding Gate.

Pure logic: no Flask, no MySQL, no imports beyond the standard library. The
database wrappers live in branding_gate.py; everything decidable without a
connection is decided here so it can be unit-tested the way
negotiation_workflow.py is.

Three things live in this module:

* PERMISSIONS  - the vocabulary. `resource.action` strings.
* SEED_MATRIX  - which role holds which permission, at which scope.
* the resolver - resolve(), allowed_user_ids(), negotiation_actor().

SEED_MATRIX is the single source of truth for the grants. The rows in
`role_permission` are generated from it, never hand-edited, so a change is a
reviewable diff rather than an UPDATE nobody sees.
"""

SCOPES = ('own', 'team', 'department', 'all')

# Scope ordering, widest last. Used when a role would otherwise hold the same
# permission twice; the wider grant wins.
_SCOPE_RANK = {'own': 0, 'team': 1, 'department': 2, 'all': 3}


class UnknownPermission(KeyError):
    """Raised when code asks about a permission that is not in the vocabulary."""


def widest(*scopes):
    """Return the widest of the given scopes, ignoring None."""
    present = [s for s in scopes if s in _SCOPE_RANK]
    if not present:
        return None
    return max(present, key=lambda s: _SCOPE_RANK[s])


# ---------------------------------------------------------------------------
# Permission vocabulary
# ---------------------------------------------------------------------------

PERMISSIONS = {
    # Sales requests
    'sales_request.view':    'View sales requests',
    'sales_request.create':  'Create a sales request',
    'sales_request.edit':    'Edit a sales request',
    'sales_request.delete':  'Delete a sales request',
    'sales_request.approve': 'Approve urgent requests and change request status',
    'sales_request.comment': 'Comment on a sales request',

    # Item money. Cost is Operations, selling price is Pricing.
    #
    # `sales_item.cost` is what makes cost visible at all -- the columns, the
    # totals, the operations pages -- so it is held right down the Operations
    # ladder. Typing a cost straight onto an item is `sales_item.cost_direct`
    # and is deliberately narrower: costing normally arrives through the
    # assignment workflow below, and the accepted proposal writes the number.
    'sales_item.cost':        'See item cost',
    'sales_item.cost_direct': 'Type a cost straight onto an item, outside the costing workflow',
    'sales_item.price': 'Enter or change item selling price',

    # Costing workflow
    'costing.view':    'View costing assignments and proposals',
    'costing.assign':  'Assign an item for costing to your own team',
    'costing.propose': 'Put up a costing proposal for an item assigned to you',
    'costing.decide':  'Accept or reject a costing proposal you asked for',

    # Client approval
    'client_approval.view':   'View items awaiting client approval',
    'client_approval.submit': 'Submit items for client approval',
    'client_approval.decide': 'Record the client approve, reject or negotiate decision',

    # Negotiation
    'negotiation.view':              'View negotiations',
    'negotiation.decide_sales_head': 'Approve or decline a negotiation as Sales Head',
    'negotiation.decide_pricing':    'Re-price, request re-costing, or decline as Pricing',
    'negotiation.complete_costing':  'Complete negotiation re-costing as Operations',

    # Operations
    'approved_item.view':   'View client-approved items',
    'approved_item.edit':   'Edit approved item components and suppliers',
    # Making an assignment and changing one afterwards are different acts. The
    # first is the daily work of the operations floor; the second rewrites a
    # commitment somebody already made to a supplier, so it stops with the head.
    'approved_item.reassign': 'Change a supplier assignment after it has been made',
    'supplier_report.view': 'View the supplier report',

    # Inventory
    'inventory.view':     'View inventory',
    'inventory.create':   'Create inventory items',
    'inventory.edit':     'Edit inventory items',
    'inventory.delete':   'Delete inventory items',
    'inventory.transact': 'Record inventory transactions and credit items',

    # Finance
    'finance_master.view':  'View payment methods and finance categories',
    'finance_master.edit':  'Manage payment methods and finance categories',
    'finance_txn.view':     'View finance transactions',
    'finance_txn.create':   'Create finance transactions',
    'finance_txn.approve':  'Approve or reject finance transactions',
    'finance_txn.delete':   'Delete finance transactions',
    'finance_report.view':  'View income statement, balance sheet and analytics',
    'user_balance.view':    'View user balances',
    'user_balance.request': 'Request a balance top-up',
    'user_balance.transfer': 'Transfer balance between users',
    # The two signatures on a عهدة request, in the order they are given. The
    # manager's is first and covers their own reports only; Finance's is what
    # actually moves the money.
    'user_balance.approve_manager': "Approve a direct report's balance request",
    'user_balance.approve': 'Approve or reject balance requests',
    'user_balance.settle':  'Hand back what is left of a عهدة',
    'loan.view':            'View loans',
    'loan.create':          'Create loans',

    # Expenses
    'expense.view':   'View personal expenses',
    'expense.create': 'Create personal expenses',
    'expense.edit':   'Edit personal expenses',
    'expense.delete': 'Delete personal expenses',
    'expense.submit': 'Submit personal expenses',
    'expense_tracking.view':            'View expense tracking records',
    'expense_tracking.create':          'Create expense tracking records',
    'expense_tracking.approve_manager': 'Give the manager approval on an expense',
    'expense_tracking.approve_finance': 'Give the finance approval on an expense',
    'expense_tracking.edit_amount':     'Adjust an expense amount',
    'expense_tracking.reject':          'Reject an expense',

    # Master data
    'client.view':   'View clients',
    'client.create': 'Create clients',
    'client.edit':   'Edit clients',
    'client.delete': 'Delete clients',
    'company.view':   'View companies',
    'company.create': 'Create companies',
    'company.edit':   'Edit companies',
    'company.delete': 'Delete companies',
    'supplier.view':   'View suppliers',
    'supplier.create': 'Create suppliers',
    'supplier.edit':   'Edit suppliers',
    'supplier.delete': 'Delete suppliers',
    'entity.view':   'View entities',
    'entity.create': 'Create entities',
    'entity.edit':   'Edit entities',
    'entity.delete': 'Delete entities',
    'catalog.view': 'View the item catalog',
    'catalog.edit': 'Edit the item catalog',

    # Sections. Which top-level area of the app a role belongs in, and so which
    # menu it sees. Kept separate from the data permissions on purpose: an
    # Operations Team Leader has to read a sales request in order to cost its
    # items, but that is not a reason to show them the Sales section. Before
    # this the Sales menu was gated on `sales_request.view`, which the whole
    # Operations ladder holds, so Operations saw Sales.
    'section.sales':      'See the Sales section',
    'section.operations': 'See the Operations section',
    'section.finance':    'See the Finance section',

    # Department portals. One per team whose home-page card had nowhere to go.
    # A portal is a landing page, so it carries no row dimension and no scope;
    # holding it is what puts the card on the home page and opens the page.
    'portal.marketing': 'Open the Marketing portal',
    'portal.account':   'Open the Account Management portal',
    'portal.design_2d': 'Open the 2D Design portal',
    'portal.design_3d': 'Open the 3D Design portal',

    # Targets. Assigning is further narrowed in the route to a direct report:
    # scope says whose numbers you may read, the reporting line says whose you
    # may set.
    'target.view':   'View sales targets',
    'target.assign': 'Set the sales target of a direct report',
    'team.edit':     'Name a team',

    # Administration
    'user.view':   'View users',
    'user.create': 'Create users',
    'user.edit':   'Edit users',
    'user.delete': 'Delete users',
    'department.view': 'View departments',
    'department.edit': 'Create and rename departments',
    'role.view':   'View roles and their permissions',
    'role.assign': 'Assign a role to a user',

    # Dashboards
    'dashboard.sales':      'View the sales dashboard',
    'dashboard.operations': 'View the operations dashboard',
    'dashboard.finance':    'View the finance dashboard',
    'dashboard.supplier':   'View the supplier dashboard',
}

# Permissions with no row dimension. Their scope is stored as 'all' and ignored
# by the scope predicates; listing them here keeps the tests honest about which
# grants are genuinely scope-free.
SCOPELESS_PERMISSIONS = frozenset({
    'finance_master.view', 'finance_master.edit',
    'catalog.view', 'catalog.edit',
    'department.view', 'department.edit',
    'role.view', 'role.assign',
    'supplier_report.view',
    'dashboard.sales', 'dashboard.operations', 'dashboard.finance', 'dashboard.supplier',
    'portal.marketing', 'portal.account', 'portal.design_2d', 'portal.design_3d',
    'section.sales', 'section.operations', 'section.finance',
})


# ---------------------------------------------------------------------------
# Departments and roles
# ---------------------------------------------------------------------------

DEPARTMENTS = {
    'executive':  'Executive',
    'sales':      'Sales',
    'marketing':  'Marketing',
    'finance':    'Finance',
    'account':    'Account Management',
    'design_2d':  '2D Design',
    'design_3d':  '3D Design',
    'operations': 'Operations',
    'pricing':    'Pricing',
}

LEVEL_EXECUTIVE = 0
LEVEL_HEAD = 1
LEVEL_TEAM_LEADER = 2
LEVEL_MEMBER = 3

# role_code -> (display name, department code or None, level)
ROLES = {
    'admin':                  ('Admin / CEO',            'executive',  LEVEL_EXECUTIVE),
    'assistant':              ('Assistant',              'executive',  LEVEL_HEAD),

    'sales_head':             ('Sales Head',             'sales',      LEVEL_HEAD),
    'sales_team_leader':      ('Sales Team Leader',      'sales',      LEVEL_TEAM_LEADER),
    'sales_member':           ('Sales Member',           'sales',      LEVEL_MEMBER),

    'marketing_manager':      ('Marketing Manager',      'marketing',  LEVEL_HEAD),
    'marketing_member':       ('Marketing Member',       'marketing',  LEVEL_MEMBER),

    'finance_manager':        ('Finance Manager',        'finance',    LEVEL_HEAD),
    'finance_member':         ('Finance Member',         'finance',    LEVEL_MEMBER),

    'account_director':       ('Account Director',       'account',    LEVEL_HEAD),
    'account_team_leader':    ('Account Team Leader',    'account',    LEVEL_TEAM_LEADER),
    'account_member':         ('Account Member',         'account',    LEVEL_MEMBER),

    'design_2d_head':         ('2D Designer Head',       'design_2d',  LEVEL_HEAD),
    'design_2d_member':       ('2D Designer',            'design_2d',  LEVEL_MEMBER),

    'design_3d_head':         ('3D Head',                'design_3d',  LEVEL_HEAD),
    # One person wears both hats today. A role of its own rather than widening
    # design_3d_head, which would hand purchasing to the next 3D head by
    # accident, and rather than a per-user override, which this system
    # deliberately does not have.
    'design_3d_purchasing':   ('3D Head & Purchasing',   'design_3d',  LEVEL_HEAD),
    'design_3d_member':       ('3D Designer',            'design_3d',  LEVEL_MEMBER),

    'operations_manager':     ('Operations Manager',     'operations', LEVEL_HEAD),
    'operations_team_leader': ('Operations Team Leader', 'operations', LEVEL_TEAM_LEADER),
    'operations_member':      ('Operations Member',      'operations', LEVEL_MEMBER),

    'pricing_manager':        ('Pricing Manager',        'pricing',    LEVEL_HEAD),
    'pricing_specialist':     ('Pricing Specialist',     'pricing',    LEVEL_MEMBER),
}


# ---------------------------------------------------------------------------
# Grant matrix
# ---------------------------------------------------------------------------

def _expand(scope, *codes):
    """Grant every listed permission at one scope."""
    return {code: scope for code in codes}


def _merge(*grant_dicts):
    """
    Combine grant dictionaries. When the same permission appears twice the
    wider scope wins, so a role never silently loses reach by the order its
    building blocks happen to be listed in.
    """
    merged = {}
    for grants in grant_dicts:
        for code, scope in grants.items():
            merged[code] = widest(merged.get(code), scope)
    return merged


# Personal expenses are always own-scope: nobody files another person's claim.
_OWN_EXPENSES = _expand(
    'own',
    'expense.view', 'expense.create', 'expense.edit', 'expense.delete', 'expense.submit',
)


def _sales_line(scope, approve=False, decide_client=False, decide_negotiation=False):
    """
    The Sales / Account ladder. Head, team leader and member differ only by
    scope and by which decisions they may take, so express that once.
    """
    grants = {
        'sales_request.view': scope,
        'sales_request.create': 'own',
        'sales_request.edit': scope,
        'sales_request.comment': scope,
        'client_approval.view': scope,
        'client_approval.submit': scope,
        'negotiation.view': scope,
        'client.view': 'all',
        'company.view': 'all',
        'catalog.view': 'all',
        'dashboard.sales': 'all',
    }
    if approve:
        grants['sales_request.approve'] = scope
    if decide_client:
        grants['client_approval.decide'] = scope
    if decide_negotiation:
        grants['negotiation.decide_sales_head'] = scope
    return grants


def _manager_expense_approval(scope):
    """Every head, manager and team leader signs off expenses within their scope."""
    return {
        'expense_tracking.view': scope,
        'expense_tracking.create': 'own',
        'expense_tracking.approve_manager': scope,
    }


SEED_MATRIX = {
    # Admin is filled in below from the full vocabulary so a new permission is
    # reachable by construction rather than by remembering to add it here.
    'admin': {},

    # Supports the CEO. Explicitly NOT a shadow admin: no approvals, no
    # deletes, no finance transactions.
    'assistant': _merge(
        _OWN_EXPENSES,
        {
            'client.view': 'all',
            'company.view': 'all',
            'user.view': 'all',
            'sales_request.view': 'all',
            'catalog.view': 'all',
            'dashboard.sales': 'all',
            'dashboard.finance': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),

    # --- Sales -------------------------------------------------------------
    'sales_head': _merge(
        _sales_line('department', approve=True, decide_client=True, decide_negotiation=True),
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'client.create': 'department', 'client.edit': 'department',
            # Reads the whole department's numbers, sets its team leaders'.
            'target.view': 'department', 'target.assign': 'department',
            'team.edit': 'department',
        },
    ),
    'sales_team_leader': _merge(
        _sales_line('team'),
        _OWN_EXPENSES,
        _manager_expense_approval('team'),
        {
            'client.create': 'own', 'client.edit': 'team',
            'target.view': 'team', 'target.assign': 'team',
        },
    ),
    'sales_member': _merge(
        _sales_line('own'),
        _OWN_EXPENSES,
        {
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
            'client.create': 'own',
            'target.view': 'own',
        },
    ),

    # --- Account management (client relationship line) ----------------------
    'account_director': _merge(
        _sales_line('department', decide_client=True),
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {'client.create': 'department', 'client.edit': 'department'},
    ),
    'account_team_leader': _merge(
        _sales_line('team'),
        _OWN_EXPENSES,
        _manager_expense_approval('team'),
        {'client.create': 'own', 'client.edit': 'team'},
    ),
    'account_member': _merge(
        _sales_line('own'),
        _OWN_EXPENSES,
        {'expense_tracking.view': 'own', 'expense_tracking.create': 'own', 'client.create': 'own'},
    ),

    # --- Pricing, a separate function under the CEO -------------------------
    'pricing_manager': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'sales_item.price': 'all',
            'sales_request.view': 'all',
            'client_approval.view': 'all',
            'negotiation.view': 'all',
            'negotiation.decide_pricing': 'all',
            'catalog.view': 'all',
            'catalog.edit': 'all',
            'client.view': 'all',
            'dashboard.sales': 'all',
        },
    ),
    # Prepares quotations and updates price data. The decision on a negotiation
    # belongs to the manager.
    'pricing_specialist': _merge(
        _OWN_EXPENSES,
        {
            'sales_item.price': 'all',
            'sales_request.view': 'all',
            'client_approval.view': 'all',
            'negotiation.view': 'all',
            'catalog.view': 'all',
            'client.view': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),

    # --- Operations ---------------------------------------------------------
    'operations_manager': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'approved_item.reassign': 'all',
            'sales_request.view': 'all',
            # Operations raises and maintains its own requests through
            # /operation_request, so it needs create and edit, not just view.
            'sales_request.create': 'all',
            'sales_request.edit': 'all',
            'sales_request.comment': 'all',
            'sales_item.cost': 'all',
            # The Head can still type a cost. Nobody below can: costing arrives
            # by assignment, and an accepted proposal writes the number.
            'sales_item.cost_direct': 'all',
            'costing.view': 'all',
            'costing.assign': 'all',
            'costing.decide': 'all',
            'negotiation.view': 'all',
            'negotiation.complete_costing': 'all',
            'approved_item.view': 'all',
            'approved_item.edit': 'all',
            'catalog.edit': 'all',
            'supplier_report.view': 'all',
            'supplier.view': 'all',
            'supplier.create': 'all',
            'supplier.edit': 'all',
            'inventory.view': 'all',
            'inventory.create': 'all',
            'inventory.edit': 'all',
            'inventory.delete': 'all',
            'inventory.transact': 'all',
            'entity.view': 'all',
            'client.view': 'all',
            'company.view': 'all',
            'catalog.view': 'all',
            'dashboard.operations': 'all',
            'dashboard.supplier': 'all',
        },
    ),
    'operations_team_leader': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('team'),
        {
            # Reads and comments on requests because costing needs the item;
            # raising and editing one is the Operations Manager's job, not
            # theirs, and the Sales section is not theirs to see at all.
            'sales_request.view': 'all',
            'sales_request.comment': 'all',
            'sales_item.cost': 'all',
            # A leader may type a cost straight in when an item does not need
            # proposals, and otherwise assigns it to their own people.
            'sales_item.cost_direct': 'all',
            'costing.view': 'team',
            'costing.assign': 'team',
            'costing.decide': 'team',
            'costing.propose': 'own',
            'negotiation.view': 'all',
            'negotiation.complete_costing': 'all',
            'approved_item.view': 'all',
            'approved_item.edit': 'all',
            'supplier_report.view': 'all',
            'supplier.view': 'all',
            'inventory.view': 'all',
            'inventory.create': 'all',
            'inventory.edit': 'all',
            'inventory.transact': 'all',
            'entity.view': 'all',
            'client.view': 'all',
            'catalog.view': 'all',
            'dashboard.operations': 'all',
        },
    ),
    'operations_member': _merge(
        _OWN_EXPENSES,
        {
            'sales_request.view': 'all',
            'sales_item.cost': 'all',
            # Costs what they are asked to cost, and nothing else.
            'costing.view': 'own',
            'costing.propose': 'own',
            'approved_item.view': 'all',
            'supplier.view': 'all',
            'inventory.view': 'all',
            'catalog.view': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),

    # --- Finance ------------------------------------------------------------
    'finance_manager': _merge(
        _OWN_EXPENSES,
        {
            'finance_master.view': 'all',
            'finance_master.edit': 'all',
            'finance_txn.view': 'all',
            'finance_txn.create': 'all',
            'finance_txn.approve': 'all',
            'finance_txn.delete': 'all',
            'finance_report.view': 'all',
            'user_balance.view': 'all',
            'user_balance.request': 'own',
            'user_balance.transfer': 'all',
            'user_balance.approve': 'all',
            'loan.view': 'all',
            'loan.create': 'all',
            'expense_tracking.view': 'all',
            'expense_tracking.create': 'own',
            'expense_tracking.approve_manager': 'department',
            'expense_tracking.approve_finance': 'all',
            'expense_tracking.edit_amount': 'all',
            'expense_tracking.reject': 'all',
            'sales_request.view': 'all',
            'client.view': 'all',
            'company.view': 'all',
            'supplier.view': 'all',
            'dashboard.finance': 'all',
        },
    ),
    # Records and reports. Approves nothing.
    'finance_member': _merge(
        _OWN_EXPENSES,
        {
            'finance_master.view': 'all',
            'finance_txn.view': 'all',
            'finance_txn.create': 'all',
            'finance_report.view': 'all',
            'user_balance.view': 'all',
            'user_balance.request': 'own',
            'loan.view': 'all',
            'expense_tracking.view': 'all',
            'expense_tracking.create': 'own',
            'sales_request.view': 'all',
            'client.view': 'all',
            'supplier.view': 'all',
            'dashboard.finance': 'all',
        },
    ),

    # --- Marketing ----------------------------------------------------------
    'marketing_manager': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'sales_request.view': 'department',
            'client.view': 'all',
            'company.view': 'all',
            'catalog.view': 'all',
            'dashboard.sales': 'all',
        },
    ),
    'marketing_member': _merge(
        _OWN_EXPENSES,
        {
            'client.view': 'all',
            'catalog.view': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),

    # --- Design -------------------------------------------------------------
    'design_2d_head': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'sales_request.view': 'all',
            'approved_item.view': 'all',
            'catalog.view': 'all',
            'catalog.edit': 'all',
            'client.view': 'all',
        },
    ),
    'design_2d_member': _merge(
        _OWN_EXPENSES,
        {
            'sales_request.view': 'all',
            'approved_item.view': 'all',
            'catalog.view': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),
    'design_3d_head': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'sales_request.view': 'all',
            'approved_item.view': 'all',
            'catalog.view': 'all',
            'catalog.edit': 'all',
            'client.view': 'all',
        },
    ),
    # 3D Head, plus what purchasing needs until purchasing is a thing of its own:
    # the suppliers bought from and the stock bought into.
    'design_3d_purchasing': _merge(
        _OWN_EXPENSES,
        _manager_expense_approval('department'),
        {
            'sales_request.view': 'all',
            'approved_item.view': 'all',
            'catalog.view': 'all',
            'catalog.edit': 'all',
            'client.view': 'all',
            'supplier.view': 'all',
            'supplier.create': 'all',
            'supplier.edit': 'all',
            'inventory.view': 'all',
            'inventory.create': 'all',
            'inventory.edit': 'all',
            'inventory.transact': 'all',
        },
    ),
    'design_3d_member': _merge(
        _OWN_EXPENSES,
        {
            'sales_request.view': 'all',
            'approved_item.view': 'all',
            'catalog.view': 'all',
            'expense_tracking.view': 'own',
            'expense_tracking.create': 'own',
        },
    ),
}

# A portal belongs to a department, not to a job title, so grant it by
# department rather than role by role: a role added to Marketing later gets the
# card by being in Marketing, not by someone remembering to edit a list.
#
# This is what the home page cards are gated on. They used to borrow whatever
# permission looked close -- Account Management on `client.edit`, which its own
# members do not hold, and both design teams on `catalog.edit`, which only their
# heads hold -- so the people the card was for could not see it.
_DEPARTMENT_PORTALS = {
    'marketing': 'portal.marketing',
    'account':   'portal.account',
    'design_2d': 'portal.design_2d',
    'design_3d': 'portal.design_3d',
}

for _role_code, (_role_name, _dept_code, _level) in ROLES.items():
    _portal = _DEPARTMENT_PORTALS.get(_dept_code)
    if _portal and _role_code in SEED_MATRIX:
        SEED_MATRIX[_role_code] = _merge(SEED_MATRIX[_role_code], {_portal: 'all'})

# A section belongs to a department, so it is granted by department too. The
# two exceptions are deliberate and named rather than left implicit: Account
# Management works inside the Sales section on the same requests, and Pricing
# lives inside the Operations menu.
_DEPARTMENT_SECTIONS = {
    'sales':      ('section.sales',),
    'account':    ('section.sales',),
    'operations': ('section.operations',),
    'pricing':    ('section.operations',),
    'finance':    ('section.finance',),
    'executive':  ('section.sales', 'section.operations', 'section.finance'),
}

for _role_code, (_role_name, _dept_code, _level) in ROLES.items():
    for _section in _DEPARTMENT_SECTIONS.get(_dept_code, ()):
        if _role_code in SEED_MATRIX:
            SEED_MATRIX[_role_code] = _merge(SEED_MATRIX[_role_code], {_section: 'all'})

# Anybody with people under them signs their عهدة requests and may correct the
# money on their expense sheets. Granted by level rather than by naming the
# roles, so a new team leader is covered by being one. Scope is 'team' -- self
# plus direct reports -- and the route narrows that further to the requester's
# own manager, because holding a permission is not the same as being the person
# somebody actually reports to.
#
# The Assistant is the named exception: a head by level, with nobody reporting
# to them and deliberately no approvals of any kind. tests/test_rbac.py holds
# that line.
_NO_REPORTS = {'assistant'}

for _role_code, (_role_name, _dept_code, _level) in ROLES.items():
    if (_level in (LEVEL_HEAD, LEVEL_TEAM_LEADER)
            and _role_code not in _NO_REPORTS
            and _role_code in SEED_MATRIX):
        SEED_MATRIX[_role_code] = _merge(SEED_MATRIX[_role_code], {
            'user_balance.approve_manager': 'team',
            'user_balance.view': 'team',
            'expense_tracking.edit_amount': 'team',
        })

# Self-service: what every employee needs regardless of job. The navbar balance
# widget and the item-catalog lookup in main.html are rendered for everyone, so
# gating them behind a departmental permission would break the shell itself.
_SELF_SERVICE = _merge(
    _OWN_EXPENSES,
    {
        'user_balance.view': 'own',
        'user_balance.request': 'own',
        # Everybody who can hold a عهدة can hand back what is left of it.
        'user_balance.settle': 'own',
        'catalog.view': 'all',
        'expense_tracking.view': 'own',
        'expense_tracking.create': 'own',
    },
)

SELF_SERVICE_PERMISSIONS = frozenset(_SELF_SERVICE)

# Pricing is a responsibility, not necessarily a job. Any account can be
# flagged as pricing, and the flag grants these on top of whatever the role
# already gives -- so either the Pricing roles or the flag is enough.
#
# Scope is 'all' throughout on purpose: someone who prices has to reach every
# request, not only the ones their own role would show them. The grant is
# merged with widest(), so the flag can widen a role but never narrow it.
PRICING_FLAG_PERMISSIONS = {
    'sales_item.price': 'all',
    'negotiation.view': 'all',
    'negotiation.decide_pricing': 'all',
    'sales_request.view': 'all',
    'client_approval.view': 'all',
    'catalog.view': 'all',
}


def apply_pricing_flag(perms):
    """Return the permission set a pricing-flagged account holds."""
    return _merge(perms or {}, PRICING_FLAG_PERMISSIONS)

for _role_code in list(SEED_MATRIX):
    if _role_code == 'admin':
        continue
    # _merge keeps the wider scope, so a role that already sees expense tracking
    # at department scope is not narrowed to own by this baseline.
    SEED_MATRIX[_role_code] = _merge(_SELF_SERVICE, SEED_MATRIX[_role_code])

# Admin holds everything, generated rather than listed, so a permission added
# to PERMISSIONS is never accidentally unreachable.
SEED_MATRIX['admin'] = {code: 'all' for code in PERMISSIONS}


# ---------------------------------------------------------------------------
# Negotiation actors
#
# negotiation_workflow.transition() speaks three actor strings. Map role codes
# onto them here rather than hardcoding role names in the route handlers, so
# that module stays untouched.
# ---------------------------------------------------------------------------

_NEGOTIATION_ACTORS = {
    'admin': 'sales_head',          # admin retains the global bypass
    'sales_head': 'sales_head',
    'pricing_manager': 'pricing',
    'pricing_specialist': 'pricing',
    'operations_manager': 'operation',
    'operations_team_leader': 'operation',
    'operations_member': 'operation',
}


def negotiation_actor(role_code):
    """Return the negotiation_workflow actor string for a role, or None."""
    return _NEGOTIATION_ACTORS.get(role_code)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def resolve(perms, code):
    """
    Return the scope a permission is held at, or None when it is not held.

    `perms` is the {permission_code: scope} mapping carried in the session.
    Deny by default: an unknown or absent code returns None.
    """
    if code not in PERMISSIONS:
        raise UnknownPermission(code)
    scope = perms.get(code) if perms else None
    return scope if scope in SCOPES else None


def sections(perms):
    """
    Which sections a permission set earns: one navbar menu and one home card
    each, both read from here.

    The two lists used to be gated separately and had drifted apart -- a 2D
    designer was offered Sales and Operations cards for menus they could not
    see, an Assistant an Admin card, a Sales Head an Admin menu. A section is
    either on or off for a role; what sits inside it is still gated item by
    item.
    """
    held = perms or {}
    out = []
    # Client is edited from the Sales menu, so client.edit alone is not what
    # makes somebody an administrator.
    if any(c in held for c in ('user.create', 'company.edit', 'entity.edit', 'supplier.edit')):
        out.append('admin')
    if 'section.sales' in held and 'sales_request.view' in held:
        out.append('sales')
    if 'section.operations' in held and 'approved_item.view' in held:
        out.append('operations')
    # Pricing is its own section rather than a link inside Operations: the
    # pricing roles hold section.operations only in order to reach it, and
    # nothing else on that menu is theirs.
    if 'sales_item.price' in held:
        out.append('pricing')
    if 'section.finance' in held and 'finance_txn.view' in held:
        out.append('finance')
    for code, key in (('portal.marketing', 'marketing'), ('portal.account', 'account'),
                      ('portal.design_2d', 'design_2d'), ('portal.design_3d', 'design_3d')):
        if code in held:
            out.append(key)
    return out


def allowed_user_ids(scope, me, direct_report_ids=(), department_member_ids=()):
    """
    Translate a scope into the set of owner ids a caller may see.

    Returns None for 'all', meaning unrestricted, so callers can skip building
    a predicate entirely. Otherwise returns a sorted list that always includes
    the caller.
    """
    if scope == 'all':
        return None
    if scope == 'own':
        return [me]
    if scope == 'team':
        return sorted({me, *direct_report_ids})
    if scope == 'department':
        return sorted({me, *department_member_ids})
    # Unknown or absent scope grants nothing, not everything.
    return []


# ---------------------------------------------------------------------------
# Seed generation
# ---------------------------------------------------------------------------

def seed_rows():
    """
    Flatten SEED_MATRIX into (role_code, permission_code, scope) tuples for the
    role_permission table. Raises on any permission code not in the vocabulary,
    so a typo fails at seed time rather than silently granting nothing.
    """
    rows = []
    for role_code, grants in SEED_MATRIX.items():
        if role_code not in ROLES:
            raise KeyError('SEED_MATRIX names an unknown role: %s' % role_code)
        for code, scope in grants.items():
            if code not in PERMISSIONS:
                raise UnknownPermission('%s grants unknown permission %s' % (role_code, code))
            if scope not in SCOPES:
                raise ValueError('%s grants %s at invalid scope %r' % (role_code, code, scope))
            rows.append((role_code, code, scope))
    return rows
