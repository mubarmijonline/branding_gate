/*
 * Phone shell for every page (bg-mobile.css draws it):
 *   - a bottom tab bar: Home, the role's main section, Approvals, Alerts, More
 *   - a "More" sheet listing every navbar menu and its items
 *   - the navbar's own badge numbers mirrored onto the tabs
 *   - every table turned into cards: each cell labelled from its header
 *
 * Nothing here decides who may see what. The tabs and the sheet are read
 * from the navbar markup the server already gated, so a hidden menu stays
 * hidden on the phone too. Desktop (>= 768px) is left alone.
 *
 * A page may steer the cards:
 *   <table data-mobile="scroll">            keep it as a table (sideways scroll)
 *   <table data-mobile-title="2">           which column is the card's title (default: first non-empty text column)
 *   <table data-mobile-actions="last">      which column holds the buttons (default: a header named Actions, else none)
 */
(function () {
    'use strict';
    var PHONE = window.matchMedia('(max-width: 767.98px)');
    if (!PHONE.matches) { PHONE.addEventListener && PHONE.addEventListener('change', function (e) { if (e.matches) location.reload(); }); return; }

    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function text(el) { return (el.textContent || '').replace(/\s+/g, ' ').trim(); }
    function iconOf(el) { var i = el.querySelector('i'); return i ? i.className : 'fas fa-circle'; }
    function samePage(href) {
        if (!href || href === '#') return false;
        var a = document.createElement('a'); a.href = href;
        return a.pathname === location.pathname;
    }

    // ---------- the menus, as the navbar has them ----------
    // Keyed on the toggle's id (operationsDropdown ...), which the translator
    // never touches; the label is whatever language the page is in.
    function readMenus() {
        var out = [];
        document.querySelectorAll('#main_nav_bar #navbarSupportedContent > ul.navbar-nav.mr-auto > li.nav-item').forEach(function (li) {
            if (li.style.display === 'none') return;
            var toggle = li.querySelector(':scope > a.nav-link');
            if (!toggle) return;
            var badge = toggle.querySelector('.badge');
            var key = (toggle.id || '').replace(/Dropdown$/, '') || text(toggle).toLowerCase();
            var menu = { key: key, label: text(toggle).replace(/\s*\d+\s*$/, ''), icon: iconOf(toggle), badge: badge, items: [], href: null };
            var dd = li.querySelector(':scope > .dropdown-menu');
            if (dd) {
                dd.childNodes.forEach(function (n) {
                    if (n.nodeType !== 1) return;
                    if (n.classList.contains('dropdown-item')) {
                        menu.items.push({ label: text(n), icon: iconOf(n), href: n.getAttribute('href'), onclick: n.getAttribute('onclick') });
                    } else if (n.classList.contains('dropdown-header')) {
                        menu.items.push({ header: text(n) });
                    } else if (n.classList.contains('dropdown-divider')) {
                        menu.items.push({ divider: true });
                    }
                });
            } else {
                menu.href = toggle.getAttribute('href');
            }
            out.push(menu);
        });
        return out;
    }

    // ---------- bottom tab bar ----------
    var MAIN_SECTIONS = ['sales', 'operations', 'finance', 'pricing', 'admin'];
    var AR = document.documentElement.lang === 'ar';
    var T = AR ? { home: 'الرئيسية', approvals: 'الموافقات', alerts: 'التنبيهات', more: 'المزيد', menu: 'القائمة', notifications: 'الإشعارات', logout: 'تسجيل الخروج', account: 'الحساب' }
               : { home: 'Home', approvals: 'Approvals', alerts: 'Alerts', more: 'More', menu: 'Menu', notifications: 'Notifications', logout: 'Logout', account: 'Account' };
    function buildTabs(menus) {
        var bar = document.createElement('nav');
        bar.className = 'bgm-tabbar';
        bar.setAttribute('data-no-i18n', '');
        bar.setAttribute('aria-label', 'Main');
        var tabs = [{ label: T.home, icon: 'fas fa-home', href: '/home' }];
        var main = null;
        MAIN_SECTIONS.some(function (name) {
            main = menus.filter(function (m) { return m.key === name; })[0];
            return !!main;
        });
        if (main) {
            // The section's first page, with its badge; the section's name.
            var first = main.items.filter(function (i) { return i.href && i.href !== '#'; })[0];
            tabs.push({ label: main.label, icon: main.icon, href: main.href || (first && first.href) || '/home', badge: main.badge });
        }
        var approvals = menus.filter(function (m) { return m.key === 'approvals'; })[0];
        if (approvals) {
            var firstA = approvals.items.filter(function (i) { return i.href && i.href !== '#'; })[0];
            tabs.push({ label: T.approvals, icon: 'fas fa-clipboard-check', href: firstA ? firstA.href : '/approvals', badge: approvals.badge });
        }
        tabs.push({ label: T.alerts, icon: 'fas fa-bell', action: 'notifications', badge: document.querySelector('#main_nav_bar .notification-badge') });
        tabs.push({ label: T.more, icon: 'fas fa-bars', action: 'more' });

        tabs.forEach(function (t) {
            var el = document.createElement(t.href ? 'a' : 'button');
            el.className = 'bgm-tab' + (t.href && samePage(t.href) ? ' active' : '');
            if (t.href) el.href = t.href; else el.type = 'button';
            if (t.action) el.setAttribute('data-bgm-action', t.action);
            el.innerHTML = '<i class="' + esc(t.icon) + '"></i><span>' + esc(t.label) + '</span>';
            if (t.badge) {
                var b = document.createElement('span');
                b.className = 'bgm-badge';
                el.appendChild(b);
                mirrorBadge(t.badge, b);
            }
            bar.appendChild(el);
        });
        document.body.appendChild(bar);
    }

    // The navbar badge is painted by the page's own pollers; copy its state.
    function mirrorBadge(src, dst) {
        function paint() {
            var hidden = src.classList.contains('d-none') || src.style.display === 'none' || !text(src);
            dst.style.display = hidden ? 'none' : '';
            dst.textContent = text(src);
        }
        paint();
        new MutationObserver(paint).observe(src, { attributes: true, childList: true, characterData: true, subtree: true });
    }

    // ---------- More sheet ----------
    function buildSheet(menus) {
        var overlay = document.createElement('div');
        overlay.className = 'bgm-sheet-overlay';
        var sheet = document.createElement('div');
        sheet.className = 'bgm-sheet';
        sheet.setAttribute('aria-hidden', 'true');
        var body = menus.map(function (m, n) {
            if (!m.items.length) {
                return '<a class="bgm-group bgm-item" href="' + esc(m.href || '#') + '"><i class="' + esc(m.icon) + '"></i>' + esc(m.label) + '</a>';
            }
            var open = m.items.some(function (i) { return i.href && samePage(i.href); });
            return '<div class="bgm-group' + (open ? ' open' : '') + '"><div class="bgm-group-head"><i class="' + esc(m.icon) + '"></i>' + esc(m.label) +
                '<i class="fas fa-chevron-down bgm-chev"></i></div><div class="bgm-group-items">' +
                m.items.map(function (i) {
                    if (i.divider) return '<div class="bgm-divider"></div>';
                    if (i.header) return '<div class="bgm-sheet-header-item">' + esc(i.header) + '</div>';
                    return '<a class="bgm-item" href="' + esc(i.href || '#') + '"' + (i.onclick ? ' onclick="' + esc(i.onclick) + '"' : '') + '>' +
                        '<i class="' + esc(i.icon) + '"></i>' + esc(i.label) + '</a>';
                }).join('') + '</div></div>';
        }).join('');
        var user = document.querySelector('#navbarDropdown > span');
        var lang = document.querySelector('#main_nav_bar .bg-lang-toggle');
        body += '<div class="bgm-group"><div class="bgm-group-head"><i class="fas fa-user-circle"></i>' + esc(user ? text(user) : T.account) +
            '<i class="fas fa-chevron-down bgm-chev"></i></div><div class="bgm-group-items">' +
            (lang ? '<a class="bgm-item" data-no-i18n href="' + esc(lang.getAttribute('href')) + '"><i class="fas fa-language"></i>' + esc(text(lang)) + '</a>' : '') +
            '<a class="bgm-item" href="/notifications"><i class="fas fa-bell"></i>' + T.notifications + '</a>' +
            '<a class="bgm-item" href="/logout"><i class="fas fa-sign-out-alt"></i>' + T.logout + '</a></div></div>';
        sheet.innerHTML = '<div class="bgm-sheet-handle"></div><div class="bgm-sheet-head"><b>' + T.menu + '</b>' +
            '<button type="button" class="bgm-sheet-close" aria-label="Close">&times;</button></div><div class="bgm-sheet-body">' + body + '</div>';
        document.body.appendChild(overlay);
        document.body.appendChild(sheet);

        function toggle(open) {
            overlay.classList.toggle('open', open);
            sheet.classList.toggle('open', open);
            sheet.setAttribute('aria-hidden', open ? 'false' : 'true');
        }
        overlay.addEventListener('click', function () { toggle(false); });
        sheet.querySelector('.bgm-sheet-close').addEventListener('click', function () { toggle(false); });
        sheet.addEventListener('click', function (e) {
            var head = e.target.closest('.bgm-group-head');
            if (head) head.parentNode.classList.toggle('open');
        });
        document.addEventListener('click', function (e) {
            var t = e.target.closest('[data-bgm-action]');
            if (!t) return;
            e.preventDefault();
            var action = t.getAttribute('data-bgm-action');
            if (action === 'more') toggle(!sheet.classList.contains('open'));
            if (action === 'notifications') {
                var bell = document.getElementById('notificationDropdown');
                if (bell) bell.click(); else location.href = '/notifications';
            }
        });
    }

    // ---------- tables -> cards ----------
    function headerCells(table) {
        var rows = table.tHead ? table.tHead.rows : [];
        if (!rows.length) return null;
        var row = rows[rows.length - 1];
        return Array.prototype.map.call(row.cells, text);
    }
    function labelTable(table) {
        if (table.getAttribute('data-mobile') === 'scroll' || table.closest('.swal2-popup, .bgm-skip, .modal')) return;
        var heads = headerCells(table);
        if (!heads || heads.length < 2) return;
        var titleCol = parseInt(table.getAttribute('data-mobile-title'), 10);
        var actionsAttr = table.getAttribute('data-mobile-actions');
        var actionsCol = actionsAttr === 'last' ? heads.length - 1
            : actionsAttr ? parseInt(actionsAttr, 10)
            : heads.map(function (h) { return h.toLowerCase(); }).indexOf('actions');
        if (isNaN(titleCol)) {
            titleCol = -1;
            // The first header that reads like a name; a bare number column (#, serial) is not a title.
            heads.some(function (h, i) {
                if (i === actionsCol) return false;
                if (/^(#|serial|serial ?#|id|code|no\.?|type|request id|sr|\s*)$/i.test(h) || /\bid$/i.test(h)) return false;
                titleCol = i; return true;
            });
        }
        table.classList.add('bgm-cards');
        Array.prototype.forEach.call(table.tBodies, function (tb) {
            Array.prototype.forEach.call(tb.rows, function (tr) {
                if (tr.cells.length === 1 && tr.cells[0].colSpan > 1) { tr.classList.add('bgm-empty'); return; }
                Array.prototype.forEach.call(tr.cells, function (td, i) {
                    var label = heads[i] || '';
                    td.setAttribute('data-label', label);
                    td.classList.toggle('bgm-title', i === titleCol);
                    td.classList.toggle('bgm-actions', i === actionsCol);
                    var t = text(td);
                    td.classList.toggle('bgm-blank', !td.children.length && (t === '' || t === '-'));
                });
            });
        });
    }
    function labelAll(root) {
        (root || document).querySelectorAll('table').forEach(labelTable);
    }

    // ---------- go ----------
    function init() {
        var menus = readMenus();
        buildTabs(menus);
        buildSheet(menus);
        labelAll();
        // Rows drawn later (DataTables, AJAX lists) get labelled as they land.
        var pending = null;
        new MutationObserver(function (muts) {
            if (pending) return;
            pending = setTimeout(function () {
                pending = null;
                muts.forEach(function (m) {
                    if (m.target.closest && m.target.closest('table')) labelTable(m.target.closest('table'));
                });
                labelAll();
            }, 60);
        }).observe(document.body, { childList: true, subtree: true });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

/*
 * A back button for the home-screen app (Ahmed, 2026-10-29). Installed to the
 * home screen the app has no browser bar, so there was no way back on any
 * page. On a phone, in the installed app, every page but Home gets one in the
 * top bar: back one step, or Home when the app was opened straight onto it.
 */
(function () {
    'use strict';
    var installed = window.navigator.standalone === true ||
        (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
    if (!installed || !window.matchMedia('(max-width: 767.98px)').matches) return;
    if (/^\/(home)?\/?$/.test(location.pathname)) return;
    var brand = document.querySelector('#main_nav_bar .navbar-brand');
    if (!brand) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bgm-back';
    btn.setAttribute('aria-label', window.bgT ? window.bgT('Back') : 'Back');
    btn.innerHTML = '<i class="fas fa-arrow-left fa-flip-rtl"></i>';
    btn.addEventListener('click', function () {
        var fromHere = document.referrer && document.referrer.indexOf(location.origin) === 0;
        if (fromHere && history.length > 1) { history.back(); } else { location.href = '/home'; }
    });
    brand.parentNode.insertBefore(btn, brand);
})();
