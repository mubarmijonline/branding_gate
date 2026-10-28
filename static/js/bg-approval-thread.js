/*
 * Discussing a pending approval (Beshoy, 2026-10-28). The approver asks the
 * requester or their manager ("why is this urgent request so late?") before
 * approving; the requester and the manager answer from the notification link
 * or from the strip on the Sales Request page. One window for all of them.
 *
 *   bgApprovalThread.open(approvalId)   -> opens the discussion
 *
 * Opens by itself on any page with ?approval=N (the requester's link). The
 * thread is refreshed every 15 s while open; no sockets.
 * ponytail: polling, websockets if anybody ever needs it live.
 */
(function () {
    'use strict';
    var T = function (x) { return window.bgT ? window.bgT(x) : x; };
    var current = null, timer = null, people = null, tagged = {};
    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function modal() {
        var $m = $('#bgApprovalThread');
        if ($m.length) return $m;
        $m = $('<div class="modal fade" id="bgApprovalThread" tabindex="-1" role="dialog" aria-hidden="true">' +
            '<div class="modal-dialog modal-lg modal-dialog-scrollable" role="document"><div class="modal-content">' +
            '<div class="modal-header"><div><h5 class="modal-title mb-0"><i class="fas fa-comments mr-2"></i>' + T('Discuss before approving') + '</h5>' +
            '<div class="small text-muted bgat-sub"></div></div>' +
            '<button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button></div>' +
            '<div class="modal-body bgat-body"></div>' +
            '<div class="modal-footer d-block bgat-foot"></div></div></div></div>');
        $('body').append($m);
        $m.on('hidden.bs.modal', function () { clearInterval(timer); current = null; });
        return $m;
    }

    function render(r) {
        var $m = modal();
        $m.find('.bgat-sub').html(esc(r.title) + (r.start_date ? ' · ' + T('Start Date') + ' ' + esc(r.start_date) : '') +
            (r.reason ? ' · <span class="text-danger">' + esc(r.reason) + '</span>' : ''));
        var who = [r.requester_name && T('Requested By') + ': ' + esc(r.requester_name),
                   r.manager_name && T('Manager') + ': ' + esc(r.manager_name)].filter(Boolean).join(' · ');
        var list = r.messages.length ? r.messages.map(function (m) {
            return '<div class="bgat-msg' + (m.mine ? ' mine' : '') + '">' +
                '<div class="bgat-meta"><b>' + esc(m.name) + '</b> <span class="bgat-side">' + esc(T(m.side === 'approver' ? 'Approver' : m.side === 'manager' ? 'Manager' : 'Requester')) + '</span> · ' + esc(m.at) + '</div>' +
                '<div class="bgat-text" data-no-i18n>' + esc(m.body).replace(/@([^\s@]+(?: [^\s@]+)?)/g, '<span class="bgat-at">@$1</span>') + '</div></div>';
        }).join('') : '<div class="text-muted text-center py-3">' + T('No messages yet. Ask your question below.') + '</div>';
        var $body = $m.find('.bgat-body');
        var atBottom = $body[0].scrollHeight - $body.scrollTop() - $body.innerHeight() < 40;
        $body.html((who ? '<div class="small text-muted mb-2">' + who + '</div>' : '') + list);
        if (atBottom || !$body.data('seen')) { $body.scrollTop($body[0].scrollHeight); $body.data('seen', 1); }

        var $foot = $m.find('.bgat-foot');
        if (!r.open) {
            $foot.html('<div class="text-muted small"><i class="fas fa-lock mr-1"></i>' +
                T('This request was {0}; the discussion is closed.').replace('{0}', T(r.status)) +
                (r.sales_request_id ? ' <a href="/sales_request?request=' + r.sales_request_id + '">' + T('Open the request') + '</a>' : '') + '</div>');
            return;
        }
        if ($foot.find('textarea').length) return;  // keep what is being typed
        var quick = r.is_approver ? '<button type="button" class="btn btn-sm btn-outline-warning mb-2 bgat-quick">' +
            T('Why is this request late?') + '</button>' : '';
        $foot.html(quick + '<div class="position-relative"><textarea class="form-control bgat-input" rows="2" maxlength="4000" placeholder="' +
            T('Write a message, @ to tag someone') + '"></textarea><div class="bgat-suggest list-group"></div></div>' +
            '<div class="d-flex mt-2"><button type="button" class="btn btn-secondary mr-auto" data-dismiss="modal">' + T('Close') + '</button>' +
            '<button type="button" class="btn btn-primary bgat-send"><i class="fas fa-paper-plane mr-1"></i>' + T('Send') + '</button></div>');
    }

    function load() {
        if (!current) return;
        $.ajax({ url: '/api/approvals/' + current + '/thread', cache: false, silent: true }).done(render)
            .fail(function (xhr) {
                clearInterval(timer);
                modal().find('.bgat-body').html('<div class="alert alert-warning mb-0">' +
                    esc((xhr.responseJSON || {}).error || T('Could not open the discussion')) + '</div>');
                modal().find('.bgat-foot').html('<button type="button" class="btn btn-secondary" data-dismiss="modal">' + T('Close') + '</button>');
            });
    }

    window.bgApprovalThread = {
        open: function (id) {
            current = Number(id);
            tagged = {};
            var $m = modal();
            $m.find('.bgat-body').html('<div class="text-center py-4 text-muted"><i class="fas fa-spinner fa-spin"></i></div>').data('seen', 0);
            $m.find('.bgat-foot').empty();
            $m.modal('show');
            load();
            clearInterval(timer);
            timer = setInterval(load, 15000);
        }
    };

    $(document).on('click', '.bgat-quick', function () {
        var ask = (window.bgLang === 'ar') ? 'ليه الطلب ده متأخر؟' : 'Why is this request late?';
        $('.bgat-input').val(ask).trigger('focus');
    });
    $(document).on('click', '.bgat-send', function () {
        var $b = $(this), text = $('.bgat-input').val().trim();
        if (!text) return;
        var ids = Object.keys(tagged).filter(function (name) { return text.indexOf('@' + name) >= 0; })
            .map(function (name) { return tagged[name]; });
        $b.prop('disabled', true);
        $.ajax({ url: '/api/approvals/' + current + '/thread', method: 'POST', contentType: 'application/json',
                 data: JSON.stringify({ comment_text: text, mentioned_users: ids }) })
            .done(function () {
                $('.bgat-input').val(''); tagged = {};
                modal().find('.bgat-body').data('seen', 0);
                load();
                $(document).trigger('bg:approval-thread', [current]);
            })
            .fail(function (xhr) { Swal.fire('', (xhr.responseJSON || {}).error || T('Could not send'), 'error'); })
            .always(function () { $b.prop('disabled', false); });
    });

    // @ to tag: the same directory the request comments use.
    $(document).on('input', '.bgat-input', function () {
        var $s = $('.bgat-suggest'), before = this.value.slice(0, this.selectionStart);
        var m = /(^|\s)@([^\s@]*)$/.exec(before);
        if (!m) { $s.empty(); return; }
        var q = m[2].toLowerCase();
        var show = function () {
            $s.html(people.filter(function (p) { return !q || p.name.toLowerCase().indexOf(q) >= 0; }).slice(0, 6).map(function (p) {
                return '<button type="button" class="list-group-item list-group-item-action py-1 bgat-pick" data-id="' + p.id + '" data-name="' + esc(p.name) + '">' +
                    esc(p.name) + ' <small class="text-muted">' + esc(p.role || p.department || '') + '</small></button>';
            }).join(''));
        };
        if (people) { show(); return; }
        $.getJSON('/api/mention-users').done(function (r) {
            people = (r.users || []).map(function (u) { return { id: u.id, name: u.name, role: u.role_name || u.role, department: u.department_name || u.department }; });
            show();
        });
    });
    $(document).on('click', '.bgat-pick', function () {
        var $i = $('.bgat-input'), el = $i[0], name = String($(this).data('name'));
        var before = el.value.slice(0, el.selectionStart).replace(/@([^\s@]*)$/, '@' + name + ' ');
        el.value = before + el.value.slice(el.selectionStart);
        tagged[name] = Number($(this).data('id'));
        $('.bgat-suggest').empty();
        $i.trigger('focus');
    });

    // The requester's side: their requests waiting for approval, on the Sales
    // Request page, each with its discussion.
    function strip() {
        if (location.pathname !== '/sales_request') return;
        $.ajax({ url: '/api/approvals/my-requests', cache: false, silent: true }).done(function (r) {
            var waiting = (r.approvals || []).filter(function (a) { return a.status === 'pending'; });
            $('#bgatStrip').remove();
            if (!waiting.length) return;
            var html = '<div id="bgatStrip" class="alert alert-warning d-flex flex-column mb-3" style="gap:.4rem">' +
                '<b><i class="fas fa-hourglass-half mr-1"></i>' + T('Waiting for approval') + '</b>' +
                waiting.map(function (a) {
                    var d = a.request_data || {};
                    return '<div class="d-flex align-items-center flex-wrap" style="gap:.5rem"><span>' + esc(d.title || '') +
                        ' <small class="text-muted">' + esc(a.approval_reason || '') + '</small></span>' +
                        '<button type="button" class="btn btn-sm ' + (a.thread_waiting ? 'btn-danger' : 'btn-outline-dark') + ' ml-auto bgat-open" data-id="' + a.id + '">' +
                        '<i class="fas fa-comments mr-1"></i>' + T('Discuss') + (a.thread_count ? ' (' + a.thread_count + ')' : '') + '</button></div>';
                }).join('') + '</div>';
            $('.container-fluid').first().prepend(html);
        });
    }
    $(document).on('click', '.bgat-open', function () { window.bgApprovalThread.open($(this).data('id')); });
    $(document).on('bg:approval-thread', strip);

    $(function () {
        strip();
        var id = Number(new URLSearchParams(location.search).get('approval'));
        if (id) window.bgApprovalThread.open(id);
    });
})();
