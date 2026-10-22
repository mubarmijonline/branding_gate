/*
 * A client invoice (or refund) in a window, on any page: what it is, its lines
 * and totals, the entry it books in the Finance Tree, what was paid against it
 * and its refunds. Print goes through a hidden frame, so no tab opens.
 *
 *   bgShowInvoice(id)
 *   any element with data-invoice-id="ID" opens it on click.
 */
(function () {
    'use strict';
    var ACCOUNTS = {
        '1103': 'العملاء', '4101': 'المبيعات', '4102': 'مردودات ومسموحات المبيعات',
        '2103': 'ضريبة القيمة المضافة للمبيعات', '2104': 'ضريبة الخصم والتحصيل المستحقة', '1107': 'ضريبة الخصم والتحصيل'
    };
    var STATUS = { draft: ['Draft', '#64748b'], submitted: ['With Finance', '#b45309'], returned: ['Returned', '#dc2626'],
                   posted: ['Posted', '#047857'], cancelled: ['Cancelled', '#94a3b8'] };

    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function money(v) { return Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    function modal() {
        var m = $('#bgInvoiceModal');
        if (m.length) return m;
        m = $('<div class="modal fade" id="bgInvoiceModal" tabindex="-1"><div class="modal-dialog modal-xl"><div class="modal-content">' +
              '<div class="modal-header bgiv-head"><h5 class="modal-title" id="bgivTitle"></h5>' +
              '<button type="button" class="close" data-dismiss="modal" style="color:#fff;opacity:.9">&times;</button></div>' +
              '<div class="modal-body" id="bgivBody"></div>' +
              '<div class="modal-footer"><button class="btn btn-light" id="bgivPrint"><i class="fas fa-print mr-1"></i>Print</button>' +
              '<a class="btn btn-light" id="bgivOpen" href="#"><i class="fas fa-external-link-alt mr-1"></i>Invoices &amp; Refunds</a>' +
              '<button class="btn btn-primary" data-dismiss="modal">Close</button></div></div></div></div>').appendTo('body');
        // Above another open window (the ledger, a statement).
        m.on('show.bs.modal', function () {
            m.css('z-index', 1070);
            setTimeout(function () { $('.modal-backdrop').last().css('z-index', 1065); }, 0);
        }).on('hidden.bs.modal', function () { if ($('.modal.show').length) $('body').addClass('modal-open'); });
        return m;
    }

    function entry(inv) {
        var w = inv.withholding_account || '2104', refund = inv.kind === 'refund';
        var rows = refund
            ? [['4102', inv.subtotal, 0], ['2103', inv.vat_total, 0], ['1103', 0, inv.total], [w, 0, inv.profit_tax_total]]
            : [['1103', inv.total, 0], [w, inv.profit_tax_total, 0], ['4101', 0, inv.subtotal], ['2103', 0, inv.vat_total]];
        return rows.filter(function (r) { return r[1] || r[2]; }).map(function (r) {
            return '<tr><td><b>' + r[0] + '</b> <bdi>' + esc(ACCOUNTS[r[0]] || '') + '</bdi></td><td class="bgiv-r">' +
                   (r[1] ? money(r[1]) : '') + '</td><td class="bgiv-r">' + (r[2] ? money(r[2]) : '') + '</td></tr>';
        }).join('');
    }

    function render(inv, lines) {
        var st = STATUS[inv.status] || [inv.status, '#64748b'];
        $('#bgivTitle').html(esc(inv.label || 'Invoice') + ' &middot; SR-' + esc(inv.sales_request_id) +
            ' <span class="bgiv-badge" style="background:' + st[1] + '">' + st[0] + '</span>');
        var html = '<div class="bgiv-meta">' +
            '<div><span>Company</span><b data-no-i18n>' + esc(inv.company_name || '-') + '</b></div>' +
            '<div><span>Client</span><b data-no-i18n>' + esc(inv.client_name || '-') + '</b></div>' +
            '<div><span>Invoice date</span><b>' + esc((inv.invoice_date || '').slice(0, 10)) + '</b></div>' +
            '<div><span>Billing month</span><b>' + esc(inv.billing_month || '-') + '</b></div>' +
            (inv.refund_of_number ? '<div><span>Refund of</span><b>Invoice ' + esc(inv.refund_of_number) + '</b></div>' : '') +
            '<div><span>Prepared by</span><b data-no-i18n>' + esc(inv.created_by_name || '-') + '</b></div>' +
            (inv.posted_by_name ? '<div><span>Posted by</span><b data-no-i18n>' + esc(inv.posted_by_name) + ' &middot; ' + esc((inv.posted_at || '').slice(0, 10)) + '</b></div>' : '') +
            '</div>';
        html += '<table class="bgiv-table"><thead><tr><th>Code</th><th>Item</th><th class="bgiv-r">Qty</th><th class="bgiv-r">Unit price</th>' +
            '<th class="bgiv-r">Cash discount</th><th class="bgiv-r">Sales value</th><th class="bgiv-r">VAT</th><th class="bgiv-r">Total</th></tr></thead><tbody>' +
            lines.map(function (l) {
                return '<tr><td>#' + esc(l.item_code) + '</td><td data-no-i18n>' + esc(l.description || l.name_en || '') + '</td>' +
                    '<td class="bgiv-r">' + l.qty + '</td><td class="bgiv-r">' + money(l.unit_price) + '</td><td class="bgiv-r">' +
                    (l.cash_discount ? money(l.cash_discount) : '-') + '</td><td class="bgiv-r">' + money(l.sales_value) + '</td>' +
                    '<td class="bgiv-r">' + money(l.vat) + '</td><td class="bgiv-r"><b>' + money(l.line_total) + '</b></td></tr>';
            }).join('') + '</tbody></table>';
        html += '<div class="bgiv-split"><div>';
        if (inv.status === 'posted') {
            html += '<h6>Booked in the Finance Tree</h6><table class="bgiv-table"><thead><tr><th>Account</th><th class="bgiv-r">Debit</th>' +
                '<th class="bgiv-r">Credit</th></tr></thead><tbody>' + entry(inv) + '</tbody></table>';
        } else {
            html += '<div class="bgiv-note">Not posted yet: nothing is booked in the Finance Tree until Finance posts it.</div>';
        }
        if ((inv.payments || []).length) {
            html += '<h6>' + (inv.kind === 'refund' ? 'Paid back' : 'Payments received') + '</h6><table class="bgiv-table"><tbody>' +
                inv.payments.map(function (p) {
                    return '<tr><td>' + esc((p.transaction_date || '').slice(0, 10)) + '</td><td>' + esc(p.transaction_code) + '</td><td data-no-i18n>' +
                        esc(p.payment_method_name || '') + '</td><td>' + esc(p.status) + '</td><td class="bgiv-r"><b>' + money(p.amount) + '</b></td></tr>';
                }).join('') + '</tbody></table>';
        }
        if ((inv.refunds || []).length) {
            html += '<h6>Refunds</h6><table class="bgiv-table"><tbody>' + inv.refunds.map(function (r) {
                return '<tr><td><a href="#" data-invoice-id="' + r.id + '">R-' + esc(r.invoice_number || '') + '</a></td><td>' +
                    esc(r.status) + '</td><td class="bgiv-r">' + money(r.total) + '</td></tr>';
            }).join('') + '</tbody></table>';
        }
        html += '</div><div class="bgiv-totals">' +
            '<div><span>Total before tax</span><b>' + money(inv.subtotal) + '</b></div>' +
            '<div><span>VAT ' + Number(inv.vat_rate || 14) + '%</span><b>' + money(inv.vat_total) + '</b></div>' +
            '<div><span>Commercial profits tax ' + Number(inv.profit_tax_rate || 1) + '%</span><b>' + (inv.profit_tax_total ? '−' + money(inv.profit_tax_total) : '0.00') + '</b></div>' +
            '<div class="grand"><span>Total</span><b>EGP ' + money(inv.total) + '</b></div>' +
            (inv.status === 'posted' ? '<div><span>' + (inv.kind === 'refund' ? 'Paid back' : 'Paid') + '</span><b>' + money(inv.paid) + '</b></div>' +
             '<div><span>' + (inv.kind === 'refund' ? 'Still to pay back' : 'Still owed') + '</span><b>' + money(inv.total - (inv.paid || 0)) + '</b></div>' : '') +
            '</div></div>';
        if (inv.notes) html += '<div class="bgiv-note">' + esc(inv.notes) + '</div>';
        $('#bgivBody').html(html);
        $('#bgivOpen').attr('href', '/invoices?open=' + inv.id);
        $('#bgivPrint').off('click').on('click', function () { printInvoice(inv.id); });
    }

    function printInvoice(id) {
        $('#bgivPrintFrame').remove();
        var frame = $('<iframe id="bgivPrintFrame" style="position:fixed;width:0;height:0;border:0;right:0;bottom:0"></iframe>')
            .attr('src', '/invoices/' + id + '/print').appendTo('body');
        frame.on('load', function () { this.contentWindow.focus(); this.contentWindow.print(); });
    }

    window.bgShowInvoice = function (id) {
        var m = modal();
        $('#bgivTitle').text('Invoice');
        $('#bgivBody').html('<div style="padding:40px;text-align:center;color:#64748b">Loading...</div>');
        m.modal('show');
        $.getJSON('/api/invoices/' + id).done(function (r) { render(r.invoice, r.lines || []); })
            .fail(function (x) {
                $('#bgivBody').html('<div style="padding:40px;text-align:center;color:#b91c1c">' +
                    esc((x.responseJSON || {}).error || 'This invoice could not be opened') + '</div>');
            });
    };

    $(document).on('click', '[data-invoice-id]', function (e) {
        e.preventDefault();
        e.stopPropagation();
        window.bgShowInvoice($(this).attr('data-invoice-id'));
    });

    var css = '' +
        '.bgiv-head{background:#1e3a5f;color:#fff}.bgiv-head .modal-title{font-weight:800}' +
        '.bgiv-badge{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;color:#fff;margin-inline-start:8px;vertical-align:middle}' +
        '.bgiv-meta{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-bottom:14px}' +
        '.bgiv-meta div{border:1px solid #e2e8f0;border-radius:10px;padding:8px 12px}' +
        '.bgiv-meta span{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#64748b}' +
        '.bgiv-table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:14px}' +
        '.bgiv-table th{font-size:11px;text-transform:uppercase;color:#64748b;background:#f8fafc;padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:start}' +
        '.bgiv-table td{padding:8px 10px;border-bottom:1px solid #f1f5f9}' +
        '.bgiv-r{text-align:end!important;white-space:nowrap;font-variant-numeric:tabular-nums}' +
        '.bgiv-split{display:grid;grid-template-columns:1fr 340px;gap:20px;align-items:start}' +
        '.bgiv-split h6{font-weight:800;margin:4px 0 8px}' +
        '.bgiv-totals div{display:flex;justify-content:space-between;padding:6px 0;font-size:14px}' +
        '.bgiv-totals .grand{border-top:2px solid #0f172a;margin-top:4px;padding-top:8px;font-size:17px}' +
        '.bgiv-note{background:#f8fafc;border:1px dashed #cbd5e1;border-radius:10px;padding:10px 12px;color:#475569;font-size:13px;margin-bottom:12px}' +
        '@media (max-width:768px){.bgiv-split{grid-template-columns:1fr}}';
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
})();
