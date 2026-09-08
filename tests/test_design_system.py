from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_design_system_assets_are_wired_into_shared_templates():
    css = ROOT / "static/css/branding-gate-system.css"
    spec = ROOT / "docs/design-system/README.md"
    macros = ROOT / "templates/design_system/macros.html"

    assert css.exists()
    assert spec.exists()
    assert macros.exists()

    for token in (
        "--bg-brand-primary",
        "--bg-status-success",
        ".bg-shell",
        ".bg-data-table",
        ".bg-detail-drawer",
        ".modal-xl .modal-dialog",
    ):
        assert token in css.read_text(encoding="utf-8")

    assert "branding-gate-system.css" in read("templates/main.html")
    assert "branding-gate-system.css" in read("templates/login.html")
    assert "branding-gate-system.css" in read("templates/register.html")
    assert 'class="bg-shell"' in read("templates/main.html")
    assert "page_header" in macros.read_text(encoding="utf-8")


def test_main_design_system_css_loads_after_inline_shell_styles():
    source = read("templates/main.html")
    head = source[: source.index("</head>")]

    assert head.rfind("branding-gate-system.css") > head.rfind("</style>")
    assert head.rfind("branding-gate-system.css") > head.rfind("{% block head %}")


def test_global_tables_inherit_scroll_drag_system():
    css = read("static/css/branding-gate-system.css")
    shell = read("templates/main.html")

    assert ".table-responsive.bg-table-dragging" in css
    assert ".dataTables_wrapper.bg-table-dragging" in css
    assert "table.finance-table" in css
    assert "table.transfers-table" in css
    assert "function getBgTableScrollTarget" in shell
    assert "pointerdown.bgTableDrag" in shell
    assert "setPointerCapture" in shell
    assert "table-responsive, .dataTables_scrollBody, .dataTables_wrapper, table.finance-table" in shell


def test_full_pages_extend_the_shared_shell():
    standalone = {
        "main.html", "login.html", "register.html",
        "comments_widget.html", "party_requests_section.html",
        "team_actions_section.html",
    }
    for template in (ROOT / "templates").glob("*.html"):
        if template.name in standalone:
            continue
        source = template.read_text(encoding="utf-8", errors="ignore")
        assert (
            'extends "main.html"' in source or "extends 'main.html'" in source
        ), f"{template.name} must extend main.html to inherit the design system"


def test_sales_request_table_is_mobile_and_scroll_friendly():
    source = read("templates/sales_request.html")

    assert "sales-request-page" in source
    assert '"scrollX": false' in source
    assert '"autoWidth": false' in source
    assert "attachSalesRequestTopScroller" in source
    assert "enableSalesRequestDragScroll" in source
    assert "pointermove.salesRequestDrag" in source
    assert "setPointerCapture" in source
    assert "e.preventDefault();" in source
    assert "sales-request-table-final-overrides" in source
    assert "sales-request-table-admin" in source
    assert "min-width: 2360px" in source
    assert "col.srq-col-title" in source
    assert "data-label" in source
    assert ".sales-request-mobile-card" in source
    assert "@media (max-width: 768px)" in source


def test_sales_request_party_dropdowns_are_readable_and_accessible():
    source = read("templates/sales_request.html")
    css = read("static/css/branding-gate-system.css")

    assert "sales-party-field" in source
    assert "formatCompanyOption" in source
    assert "formatClientOption" in source
    assert "sales-party-select-dropdown" in source
    assert "'mobile-number': client.mobile_number" in source
    assert "'job-title': client.job_title" in source

    assert ".sales-party-select-dropdown .select2-results__option" in css
    assert "min-height: 52px" in css
    assert ".sales-party-option__primary" in css
    assert ".sales-party-option__meta" in css
    assert ".sales-party-select-dropdown .select2-results__option--highlighted" in css


def test_costed_item_lock_explains_why_the_item_is_protected():
    source = read("templates/sales_request.html")

    assert "Costed by Operations" in source
    assert "Changing it would invalidate the Operations cost and downstream totals" in source


def test_company_filter_only_updates_its_own_client_dropdown():
    source = read("templates/sales_request.html")

    assert "function populateClientDropdowns(companyId = null, selector" in source
    assert "isEditForm ? '#editClientSelect' : '#clientSelect'" in source
    assert "populateClientDropdowns(companyId || null, clientSelector)" in source


def test_sales_request_scrollers_share_the_real_datatable_viewport():
    source = read("templates/sales_request.html")

    assert "function getSalesRequestScrollViewport" in source
    assert "$('#requests-table_wrapper')" in source
    assert "$top.insertBefore($viewport)" in source
    assert "$viewport.scrollLeft(this.scrollLeft)" in source
    assert "enableSalesRequestDragScroll($viewport)" in source
    assert ".sales-request-top-scroll::-webkit-scrollbar-thumb" in source


def test_sales_request_more_menu_uses_an_unclipped_portal():
    source = read("templates/sales_request.html")

    assert "sales-request-action-menu-portal" in source
    assert "function openSalesRequestActionMenu" in source
    assert "$portal.appendTo(document.body)" in source
    assert "positionSalesRequestActionMenu" in source
    assert 'class="btn btn-sm btn-more"' in source
    assert 'btn-more dropdown-toggle" data-toggle="dropdown"' not in source
    assert "inset: auto !important" not in source


def test_authorized_users_get_primary_set_selling_price_action():
    source = read("templates/sales_request.html")

    assert "if (window.CAN_CONTROL_PRICING)" in source
    assert "Set Selling Price" in source
    assert "has-pricing-action" in source


def test_selling_price_modal_uses_compact_summary_and_professional_workflow_states():
    source = read("templates/sales_request.html")
    css = read("static/css/branding-gate-system.css")

    assert 'class="pricing-total-summary"' in source
    assert "pricing-total-summary__metric" in source
    assert "pricing-workflow-alert" in source
    assert "pricing-decision-actions" in source
    assert "#setPriceModal .pricing-total-summary" in css
    assert "#setPriceModal .pricing-workflow-alert" in css
    header_rule = css.split("#setPriceModal .pricing-modal__header {", 1)[1].split("}", 1)[0]
    assert "background: var(--bg-brand-primary) !important;" in header_rule
    assert "color: #fff !important;" in header_rule


def test_repricing_requests_receive_a_simple_row_attention_marker():
    source = read("templates/sales_request.html")
    css = read("static/css/branding-gate-system.css")

    assert "sales-request-row--repricing" in source
    assert "repricing-row-alert" in source
    assert "Re-Pricing Required" in source
    assert ".sales-request-row--repricing" in css
    assert ".repricing-row-alert" in css


def test_client_management_page_uses_operational_design_system():
    source = read("templates/client.html")
    css = read("static/css/branding-gate-system.css")

    assert "client-management-page" in source
    assert "client-summary-band" in source
    assert 'id="clientSearch"' in source
    assert 'id="clientCompanyFilter"' in source
    assert 'id="clientChannelFilter"' in source
    assert "clientDuplicateKey" in source
    assert "potential-duplicate-badge" in source
    assert "client-table-mobile-card" in source
    assert ".client-management-page" in css
    assert ".client-table-mobile-card" in css
    assert "@media (max-width: 768px)" in css
    assert "dropdownParent: $modal" in source
    assert "initCompanySelect($('#parentCompany'), $('#addClientModal'))" in source
    assert "initCompanySelect($('#editParentCompany'), $('#editClientModal'))" in source
    assert "Debug: Reload Companies" not in source


def test_client_table_has_compact_columns_and_icon_actions():
    source = read("templates/client.html")

    for heading in ("Client", "Company", "Contact", "Preferred Channel", "Added", "Actions"):
        assert f"<th>{heading}</th>" in source
    assert "client-action-group" in source
    assert "fa-pen" in source
    assert "fa-trash" in source
    assert '"responsive": true' not in source


def test_client_add_and_edit_forms_share_correct_field_mapping():
    source = read("templates/client.html")

    assert "function clientFieldSelector" in source
    assert "name.charAt(0).toLowerCase() + name.slice(1)" in source
    assert "clientFormPayload('')" in source
    assert "clientFormPayload('edit')" in source
    assert 'type="text" class="form-control" id="editEmailAddress"' in source


def test_global_quick_add_buttons_match_create_and_request_permissions():
    source = read("templates/main.html")

    assert "{% set can_create_clients    = 'client.create'   in _p %}" in source
    assert "{% set can_request_clients   = 'client_request.create'   in _p %}" in source
    assert "{% set can_request_companies = 'company_request.create'  in _p %}" in source
    assert "{% if can_create_clients %}\n      <button class=\"fab-item\" data-toggle=\"modal\" data-target=\"#quickAddClientModal\"" in source
    assert "{% elif can_request_clients %}\n      <button class=\"fab-item\" onclick=\"window.location.href='{{ url_for('client') }}?new_request=1'\"" in source
    assert "{% elif can_request_companies %}\n      <button class=\"fab-item\" onclick=\"window.location.href='{{ url_for('company') }}?new_request=1'\"" in source
    assert "{% if can_create_clients %}\n  <div class=\"modal fade\" id=\"quickAddClientModal\"" in source
    assert "{% if can_create_suppliers %}\n      <button class=\"fab-item\" data-toggle=\"modal\" data-target=\"#quickAddSupplierModal\"" in source
    assert "{% if can_create_suppliers %}\n  <div class=\"modal fade\" id=\"quickAddSupplierModal\"" in source


def test_company_page_uses_request_flow_and_gates_direct_actions():
    source = read("templates/company.html")

    assert "{% set party_kind = 'company' %}" in source
    assert "{% include 'party_requests_section.html' %}" in source
    # The button moved out of the card header and into the page header when the
    # company directory was rebuilt on the client-directory shell. What is being
    # pinned is that it is still gated, not where it sits.
    assert "{% if can_create_company %}\n        <button class=\"btn btn-primary\" data-toggle=\"modal\" data-target=\"#addCompanyModal\">" in source
    assert "const CAN_EDIT_COMPANY = {{ can_edit_company | tojson }};" in source
    assert "const CAN_DELETE_COMPANY = {{ can_delete_company | tojson }};" in source


def test_party_request_component_supports_company_requests():
    source = read("templates/party_requests_section.html")

    assert "party_kind == 'company' and 'company_request.create' in _pp" in source
    assert "company: [" in source
    assert "['company_name', 'Company name', true]" in source
    assert "q.payload.client_name || q.payload.company_name || q.payload.supplier_name" in source
    assert "new URLSearchParams(window.location.search).get('new_request') === '1'" in source


def test_party_request_approvals_have_mobile_cards_with_visible_actions():
    source = read("templates/party_requests_section.html")
    css = read("static/css/branding-gate-system.css")
    shell = read("templates/main.html")

    assert "branding-gate-system.css') }}?v=20260906-person-numbers" in shell
    assert 'class="table-responsive party-request-table-wrap d-none d-md-block"' in source
    assert 'class="party-request-mobile-list d-md-none"' in source
    assert 'id="partyRequestCards"' in source
    assert "function partyActionButtons" in source
    assert "party-request-mobile-card" in source
    assert "party-request-mobile-actions" in source
    assert ".party-request-table-wrap" in css
    assert ".party-request-mobile-list" in css
    assert ".party-request-mobile-actions" in css
    assert "@media (max-width: 768px)" in css


if __name__ == "__main__":
    test_design_system_assets_are_wired_into_shared_templates()
    test_main_design_system_css_loads_after_inline_shell_styles()
    test_global_tables_inherit_scroll_drag_system()
    test_full_pages_extend_the_shared_shell()
    test_sales_request_table_is_mobile_and_scroll_friendly()
    test_sales_request_party_dropdowns_are_readable_and_accessible()
    test_costed_item_lock_explains_why_the_item_is_protected()
    test_company_filter_only_updates_its_own_client_dropdown()
    test_sales_request_scrollers_share_the_real_datatable_viewport()
    test_sales_request_more_menu_uses_an_unclipped_portal()
    test_authorized_users_get_primary_set_selling_price_action()
    test_selling_price_modal_uses_compact_summary_and_professional_workflow_states()
    test_repricing_requests_receive_a_simple_row_attention_marker()
    test_client_management_page_uses_operational_design_system()
    test_client_table_has_compact_columns_and_icon_actions()
    test_client_add_and_edit_forms_share_correct_field_mapping()
    test_global_quick_add_buttons_match_create_and_request_permissions()
    test_company_page_uses_request_flow_and_gates_direct_actions()
    test_party_request_component_supports_company_requests()
    test_party_request_approvals_have_mobile_cards_with_visible_actions()
