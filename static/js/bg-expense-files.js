/*
 * Receipts on an expense: the paperclip button and the viewer behind it.
 * Shared by My Expenses, the approval screens and the Sales Request page, so
 * a receipt looks the same wherever it is opened.
 *
 *   bgExpenseFilesButton(attachments, title)  -> HTML for a table cell
 *   bgShowExpenseFiles(attachments, title)    -> opens the viewer
 */
(function () {
    'use strict';
    var store = [];

    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function size(bytes) {
        if (!bytes) return '';
        return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB';
    }
    function icon(a) {
        var t = a.type || '';
        if (a.is_image) return 'fa-file-image';
        if (t.indexOf('pdf') >= 0) return 'fa-file-pdf';
        if (t.indexOf('word') >= 0 || t.indexOf('msword') >= 0) return 'fa-file-word';
        if (t.indexOf('sheet') >= 0 || t.indexOf('excel') >= 0) return 'fa-file-excel';
        return 'fa-file';
    }

    window.bgExpenseFileTile = function (a, removable) {
        return '<div class="bg-xf-tile" data-id="' + a.id + '">' +
            (a.is_image
                ? '<a href="' + esc(a.url) + '" target="_blank" rel="noopener"><img src="' + esc(a.url) + '" alt="" loading="lazy"></a>'
                : '<a href="' + esc(a.url) + '" target="_blank" rel="noopener" class="bg-xf-doc"><i class="fas ' + icon(a) + '"></i></a>') +
            '<div class="bg-xf-name" title="' + esc(a.name) + '" data-no-i18n>' + esc(a.name) + '</div>' +
            '<div class="bg-xf-meta">' + esc(size(a.size)) + '</div>' +
            (removable ? '<button type="button" class="bg-xf-remove" data-id="' + a.id + '" title="Remove"><i class="fas fa-times"></i></button>' : '') +
            '</div>';
    };

    window.bgExpenseFilesButton = function (attachments, title) {
        var list = attachments || [];
        if (!list.length) return '<span class="text-muted">-</span>';
        store.push({ list: list, title: title || '' });
        return '<button type="button" class="bg-xf-btn" data-xf="' + (store.length - 1) + '">' +
            '<i class="fas fa-paperclip"></i> ' + list.length + '</button>';
    };

    window.bgShowExpenseFiles = function (attachments, title) {
        Swal.fire({
            title: title || 'Receipts',
            html: '<div class="bg-xf-grid">' + (attachments || []).map(function (a) {
                return window.bgExpenseFileTile(a, false);
            }).join('') + '</div>',
            width: 760, showCloseButton: true, confirmButtonText: 'Close'
        });
    };

    $(document).on('click', '.bg-xf-btn', function (e) {
        e.stopPropagation();
        var entry = store[+$(this).data('xf')];
        if (entry) window.bgShowExpenseFiles(entry.list, entry.title);
    });

    var css = '' +
        '.bg-xf-btn{border:1px solid #c7d2fe;background:#eef2ff;color:#4f46e5;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}' +
        '.bg-xf-btn:hover{background:#4f46e5;color:#fff}' +
        '.bg-xf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;text-align:start}' +
        '.bg-xf-tile{position:relative;border:1px solid #e2e8f0;border-radius:12px;padding:8px;background:#fff}' +
        '.bg-xf-tile img{width:100%;height:96px;object-fit:cover;border-radius:8px;display:block}' +
        '.bg-xf-doc{display:flex;align-items:center;justify-content:center;height:96px;border-radius:8px;background:#f1f5f9;color:#64748b;font-size:36px}' +
        '.bg-xf-doc .fa-file-pdf{color:#dc2626}.bg-xf-doc .fa-file-word{color:#2563eb}.bg-xf-doc .fa-file-excel{color:#16a34a}' +
        '.bg-xf-name{font-size:12px;font-weight:600;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
        '.bg-xf-meta{font-size:11px;color:#94a3b8}' +
        '.bg-xf-remove{position:absolute;top:4px;inset-inline-end:4px;width:24px;height:24px;border-radius:50%;border:none;background:#ef4444;color:#fff;font-size:11px;cursor:pointer}';
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
})();
