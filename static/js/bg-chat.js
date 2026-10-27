/*
 * Chat drawer: request chats ('sr:<id>') and group rooms ('g:<room>').
 *
 * WhatsApp-style: photos (shrunk in the browser before upload), voice notes
 * (MediaRecorder; the server turns them into AAC so iPhones play them),
 * ticks on my own messages (one grey: sent, two grey: seen by some, two blue:
 * seen by everyone in the chat) and Message info (who has seen it and when,
 * who not yet). The @ list is the open chat's members only.
 *
 * Server: /api/chat/sr-list, /api/chat/groups, the two message routes
 * (/api/sales/requests/<id>/comments, /api/chat/groups/<room>/messages),
 * /api/chat/thread/<t>/members, /api/chat/thread/<t>/messages/<id>/info,
 * /api/chat/media/<id>.
 *
 * Needs jQuery and window.BG_CHAT = {meId, meName}.
 */
(function ($) {
    'use strict';
    if (!$ || !document.getElementById('chatDrawer')) { return; }

    var ME = (window.BG_CHAT || {}).meId;
    var ME_NAME = (window.BG_CHAT || {}).meName || '';
    var T = function (s) { return window.bgT ? window.bgT(s) : s; };
    var PHONE = window.matchMedia('(max-width: 767.98px)');
    var COARSE = window.matchMedia('(pointer: coarse)');
    var CAN_RECORD = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia
                        && window.isSecureContext);
    var MAX_VOICE_MS = 5 * 60 * 1000;
    var MENTION_ALL = /(^|\s)@(all|everyone)(?=$|[\s.,!?;:)\]}])/i;
    // The emoji picker: what a team uses at work, grouped as on a phone keyboard.
    var EMOJI = [
        ['fa-smile', 'Smileys', '😀 😃 😄 😁 😆 😅 🤣 😂 🙂 😉 😊 😇 🥰 😍 🤩 😘 😋 😛 😜 🤪 🤗 🤭 🤫 🤔 🤐 🤨 😐 😑 😶 😏 😒 🙄 😬 😌 😔 😪 😴 😷 🤒 🤕 🥵 🥶 😵 🤯 🥳 😎 🤓 🧐 😕 😟 🙁 😮 😯 😲 😳 🥺 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 💀 💩 🤡 👻 👽 🤖'],
        ['fa-hand-paper', 'Gestures', '👍 👎 👌 🤌 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ ✋ 🤚 🖐️ 🖖 👋 🤝 🙏 👏 🙌 👐 🤲 💪 ✍️ 💅 🤳 👀 🧠 🫡 🙋 🙆 🙅 🤷 🤦 💁 🙇'],
        ['fa-heart', 'Hearts', '❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💯 ✨ ⭐ 🌟 🔥 💥 💫 🎉 🎊 🎈 🎁 🏆 🥇 🥈 🥉 🎯'],
        ['fa-briefcase', 'Work', '✅ ☑️ ✔️ ❌ ❎ ⚠️ ❗ ❓ ⏰ ⏳ 📅 📆 🗓️ 📌 📍 📎 🖊️ 📝 📋 📁 📂 📊 📈 📉 💼 💰 💵 💳 🧾 📦 🚚 🚛 🏗️ 🛠️ 🔧 🔨 ⚙️ 🖨️ 💻 🖥️ 📱 ☎️ 📞 📧 📨 💡 🔑 🔒 🏢 🏬 🎪 🎤 🎬 📸 🖼️ 🎨 🧵 ☕ 🍕 🍔 🥤 🍰'],
        ['fa-flag', 'Signs', '🟢 🟡 🔴 🔵 🟣 ⚫ ⚪ 🟥 🟧 🟨 🟩 🟦 ➡️ ⬅️ ⬆️ ⬇️ 🔄 🔁 ➕ ➖ ✖️ ➗ 🆗 🆕 🆙 🔝 🆘 ⛔ 🚫 🇪🇬']
    ].map(function (g) { return { icon: g[0], title: g[1], list: g[2].split(' ') }; });
    // Big ones that send on a tap, as stickers do.
    var BIG_EMOJI = '👍 ❤️ 😂 😮 😢 🙏 👏 🔥 🎉 💯 ✅ 👌 🤝 💪 😎 🥳 🤔 😅 😍 🫡'.split(' ');
    var JUMBO = (function () { try { return new RegExp('^(?:\\p{Extended_Pictographic}(?:\\uFE0F|\\u200D\\p{Extended_Pictographic}|[\\u{1F3FB}-\\u{1F3FF}])*|[\\u{1F1E6}-\\u{1F1FF}]{2}|\\s){1,8}$', 'u'); } catch (e) { return null; } })();
    function jumboCount(text) {
        if (!JUMBO || !text || !JUMBO.test(text)) { return 0; }
        var n = (text.match(/\p{Extended_Pictographic}/gu) || []).length;
        return n >= 1 && n <= 3 ? n : 0;
    }
    var stickers = null;       // the company pack, once loaded
    var AUTHOR_COLOURS = ['#e542a3', '#1f7aec', '#d3396d', '#00a884', '#a62c71', '#c75300', '#7f66ff', '#02a698'];

    var $drawer = $('#chatDrawer'), $overlay = $('#chatDrawerOverlay'), $badge = $('#chatUnreadBadge');
    var chats = [], groups = [], srUnread = 0, groupUnread = 0, srDenied = false;
    var filter = 'all';
    var cur = null;              // {thread, kind, key, members:[], meta}
    var rendered = {};           // message id -> receipt, for the open thread
    var cache = {};              // message id -> message, for quoting
    var lastDay = null, lastAuthor = null;
    var pending = [];            // my messages on their way up
    var replyTo = null;          // {id, user_id, user_name, text, kind} being answered
    var tempSeq = 0;
    var listTimer = null, threadTimer = null, badgeTimer = null;
    var lastToastAt = null, lastGroupUnread = null;

    // ---------------------------------------------------------------- helpers
    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function parseTime(iso) { return iso ? new Date(String(iso).replace(' ', 'T')) : null; }
    function hhmm(iso) {
        var d = parseTime(iso);
        return d && !isNaN(d) ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    }
    function dayKey(d) { return d.getFullYear() + '-' + d.getMonth() + '-' + d.getDate(); }
    function dayLabel(iso) {
        var d = parseTime(iso); if (!d || isNaN(d)) { return ''; }
        var today = new Date(), y = new Date(); y.setDate(today.getDate() - 1);
        if (dayKey(d) === dayKey(today)) { return T('Today'); }
        if (dayKey(d) === dayKey(y)) { return T('Yesterday'); }
        return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
    }
    function listTime(iso) {
        var d = parseTime(iso); if (!d || isNaN(d)) { return ''; }
        var today = new Date(), y = new Date(); y.setDate(today.getDate() - 1);
        if (dayKey(d) === dayKey(today)) { return hhmm(iso); }
        if (dayKey(d) === dayKey(y)) { return T('Yesterday'); }
        return d.toLocaleDateString([], { day: '2-digit', month: '2-digit', year: '2-digit' });
    }
    function initials(name) {
        return (name || '?').split(/\s+/).map(function (p) { return p.charAt(0); }).slice(0, 2).join('').toUpperCase();
    }
    function colourFor(id) { return AUTHOR_COLOURS[Math.abs(Number(id) || 0) % AUTHOR_COLOURS.length]; }
    function mmss(ms) {
        var s = Math.max(0, Math.round((ms || 0) / 1000));
        return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
    }
    function isGroup(t) { return typeof t === 'string' && t.indexOf('g:') === 0; }
    function messagesUrl(t) {
        return isGroup(t) ? '/api/chat/groups/' + t.slice(2) + '/messages'
                          : '/api/sales/requests/' + t.slice(3) + '/comments';
    }
    function visible() { return document.visibilityState !== 'hidden' && $drawer.hasClass('open'); }
    function toast(icon, text) {
        if (window.Swal) { Swal.fire({ toast: true, position: 'top', icon: icon, timer: 3500, showConfirmButton: false, title: text }); }
    }

    function highlight(text, names) {
        // Only a member's exact @name is marked; what follows stays plain.
        if (!text) { return ''; }
        names = (names || []).slice().sort(function (a, b) { return b.length - a.length; });
        var out = '', i = 0;
        while (i < text.length) {
            if (text.charAt(i) === '@') {
                var hit = null;
                for (var k = 0; k < names.length; k++) {
                    var n = names[k];
                    if (text.substr(i + 1, n.length) === n && /^($|[\s.,!?;:)\]}])/.test(text.charAt(i + 1 + n.length))) { hit = n; break; }
                }
                if (hit) { out += '<span class="mention">@' + esc(hit) + '</span>'; i += 1 + hit.length; continue; }
            }
            out += esc(text.charAt(i)); i++;
        }
        return out;
    }

    // ---------------------------------------------------------------- media
    // Shared by the request page's own comment views.
    function mediaHtml(atts, progress) {
        return (atts || []).map(function (a) {
            if (a.kind === 'sticker') {
                return '<div class="bgc-media bgc-sticker-wrap"><img class="bgc-sticker" loading="lazy" alt="' + esc(T('Sticker')) +
                    '" src="' + esc(a.url) + '"></div>';
            }
            if (a.kind === 'image') {
                var ratio = (a.width && a.height) ? ' style="aspect-ratio:' + a.width + '/' + a.height + '"' : '';
                return '<div class="bgc-media"><img class="bgc-img" loading="lazy" alt="' + esc(T('Photo')) + '" src="' +
                    esc(a.url) + '"' + ratio + ' data-full="' + esc(a.url) + '">' +
                    (progress != null ? '<div class="bgc-progress">' + progress + '%</div>' : '') + '</div>';
            }
            return '<div class="bgc-voice" data-src="' + esc(a.url) + '" data-dur="' + (a.duration_ms || 0) + '">' +
                '<button type="button" class="bgc-play" aria-label="' + esc(T('Play')) + '"' + (a.url ? '' : ' disabled') + '>' +
                (progress != null ? '<i class="fas fa-spinner fa-spin"></i>' : '<i class="fas fa-play"></i>') + '</button>' +
                '<div class="bgc-voice-track"><input type="range" min="0" max="1000" value="0" aria-label="' + esc(T('Voice note')) + '">' +
                '<span class="bgc-voice-time">' + mmss(a.duration_ms) + '</span></div>' +
                '<i class="fas fa-microphone bgc-voice-mic"></i></div>';
        }).join('');
    }
    window.bgChatMediaHtml = function (atts) { return mediaHtml(atts); };

    // One player for every voice note on the page: starting one stops another.
    var audio = new Audio(), $playing = null;
    audio.preload = 'metadata';
    function voiceUi($v, playing) {
        $v.find('.bgc-play').html('<i class="fas fa-' + (playing ? 'pause' : 'play') + '"></i>');
    }
    $(document).on('click', '.bgc-voice .bgc-play', function (e) {
        e.stopPropagation();
        var $v = $(this).closest('.bgc-voice'), src = $v.data('src');
        if (!src) { return; }
        if ($playing && $playing[0] === $v[0] && !audio.paused) { audio.pause(); return; }
        if (!$playing || $playing[0] !== $v[0]) {
            if ($playing) { voiceUi($playing, false); }
            $playing = $v;
            audio.src = src;
            var pos = Number($v.find('input').val()) || 0;
            if (pos) { audio.addEventListener('loadedmetadata', function seek() {
                audio.removeEventListener('loadedmetadata', seek);
                if (isFinite(audio.duration)) { audio.currentTime = audio.duration * pos / 1000; }
            }); }
        }
        audio.play().catch(function () { toast('error', T('This voice note could not be played')); });
    });
    audio.addEventListener('play', function () { if ($playing) { voiceUi($playing, true); } });
    audio.addEventListener('pause', function () { if ($playing) { voiceUi($playing, false); } });
    audio.addEventListener('ended', function () {
        if ($playing) { voiceUi($playing, false); $playing.find('input').val(0);
            $playing.find('.bgc-voice-time').text(mmss($playing.data('dur'))); }
    });
    audio.addEventListener('timeupdate', function () {
        if (!$playing) { return; }
        var dur = isFinite(audio.duration) && audio.duration ? audio.duration : (Number($playing.data('dur')) || 0) / 1000;
        if (dur) { $playing.find('input').val(Math.round(1000 * audio.currentTime / dur)); }
        $playing.find('.bgc-voice-time').text(mmss(audio.currentTime * 1000));
    });
    $(document).on('input', '.bgc-voice input[type=range]', function () {
        var $v = $(this).closest('.bgc-voice');
        if ($playing && $playing[0] === $v[0] && isFinite(audio.duration)) {
            audio.currentTime = audio.duration * Number(this.value) / 1000;
        }
    });

    // Full-screen photo.
    $(document).on('click', '.bgc-img', function (e) {
        e.stopPropagation();
        var src = $(this).data('full') || this.src;
        var $lb = $('<div class="bgc-lightbox" role="dialog" aria-modal="true">' +
            '<div class="bgc-lightbox-bar">' +
            '<a class="bgc-icon-btn" href="' + esc(src) + '" download title="' + esc(T('Download')) + '"><i class="fas fa-download"></i></a>' +
            '<button type="button" class="bgc-icon-btn bgc-lb-close" title="' + esc(T('Close')) + '"><i class="fas fa-times"></i></button></div>' +
            '<div class="bgc-lightbox-img"><img alt="" src="' + esc(src) + '"></div></div>');
        $('body').append($lb);
        $lb.on('click', function (ev) { if (!$(ev.target).closest('a').length) { $lb.remove(); } });
    });

    // ---------------------------------------------------------------- badge + list
    function setBadge() {
        var n = srUnread + groupUnread;
        if (n > 0) { $badge.text(n > 99 ? '99+' : n).show(); } else { $badge.hide(); }
    }

    function fetchGroups() {
        return $.ajax({ url: '/api/chat/groups', cache: false, silent: true }).done(function (r) {
            if (!r || !r.success) { return; }
            groups = r.groups || [];
            groupUnread = r.total_unread || 0;
            if (lastGroupUnread !== null && groupUnread > lastGroupUnread && !$drawer.hasClass('open')) {
                var g = groups.filter(function (x) { return x.unread; })[0];
                if (g) { toast('info', g.title + ': ' + (g.last_message_user || '') + ' ' + (g.last_message_text || '').slice(0, 60)); }
            }
            lastGroupUnread = groupUnread;
            setBadge();
            if ($drawer.hasClass('open')) { renderList(); }
        });
    }

    function fetchChats() {
        fetchGroups();
        if (srDenied) { return; }
        $.ajax({ url: '/api/chat/sr-list', cache: false, silent: true }).done(function (r) {
            if (!r || !r.success) { return; }
            chats = r.chats || [];
            srUnread = r.total_unread || 0;
            setBadge();
            var top = chats[0];
            if (top && top.last_message_at) {
                if (lastToastAt && top.last_message_at > lastToastAt && top.last_message_user !== ME_NAME
                    && !(cur && cur.thread === 'sr:' + top.request_id && visible())) {
                    toast('info', 'SR-' + top.request_id + ' · ' + (top.last_message_user || '') + ': ' + (top.last_message_text || '').slice(0, 60));
                }
                lastToastAt = top.last_message_at;
            }
            if ($drawer.hasClass('open')) { renderList(); }
        }).fail(function (xhr) {
            if (xhr && (xhr.status === 401 || xhr.status === 403)) { srDenied = true; renderList(); }
        });
    }

    function renderList() {
        var q = ($('#chatListSearch').val() || '').toLowerCase().trim();
        var sort = $('#chatListSort').val() || 'recent';
        var unreadChats = chats.filter(function (c) { return c.unread_mentions > 0; }).length +
                          groups.filter(function (g) { return g.unread > 0; }).length;
        $('#chatUnreadCnt').text(unreadChats || '');

        var gs = groups.filter(function (g) {
            if (filter === 'requests') { return false; }
            if (filter === 'unread' && !(g.unread > 0)) { return false; }
            return !q || (g.title || '').toLowerCase().indexOf(q) >= 0;
        });
        var rs = srDenied ? [] : chats.filter(function (c) {
            if (filter === 'groups') { return false; }
            if (filter === 'unread' && !(c.unread_mentions > 0)) { return false; }
            if (!q) { return true; }
            return ('sr-' + c.request_id).indexOf(q) >= 0 || String(c.request_id).indexOf(q) >= 0 ||
                (c.title || '').toLowerCase().indexOf(q) >= 0 || (c.client_name || '').toLowerCase().indexOf(q) >= 0 ||
                (c.company_name || '').toLowerCase().indexOf(q) >= 0;
        });
        rs.sort(function (a, b) {
            if (sort === 'id_desc') { return b.request_id - a.request_id; }
            if (sort === 'id_asc') { return a.request_id - b.request_id; }
            if (sort === 'unread') { return (b.unread_mentions || 0) - (a.unread_mentions || 0) ||
                                            String(b.last_message_at || '').localeCompare(String(a.last_message_at || '')); }
            return String(b.last_message_at || b.sr_created_at || '').localeCompare(String(a.last_message_at || a.sr_created_at || ''));
        });

        var html = '';
        if (gs.length) {
            html += '<div class="bgc-heading">' + esc(T('Groups')) + '</div>' + gs.map(function (g) {
                var t = 'g:' + g.room;
                return '<div class="bgc-item' + (g.unread ? ' unread' : '') + (cur && cur.thread === t ? ' active' : '') +
                    '" data-thread="' + t + '" role="button" tabindex="0">' +
                    '<div class="bgc-avatar group"><i class="fas ' + esc(g.icon || 'fa-users') + '"></i></div>' +
                    '<div class="bgc-item-body"><div class="bgc-row"><span class="bgc-name">' + esc(T(g.title)) + '</span>' +
                    '<span class="bgc-time">' + listTime(g.last_message_at) + '</span></div>' +
                    '<div class="bgc-row"><span class="bgc-preview" data-no-i18n>' +
                    (g.last_message_at ? esc((g.last_message_user || '').split(' ')[0]) + ': ' + esc(g.last_message_text || '')
                                       : '<i>' + esc(T('No messages yet')) + '</i>') + '</span>' +
                    (g.unread ? '<span class="bgc-count">' + g.unread + '</span>' : '') + '</div></div></div>';
            }).join('');
        }
        if (!srDenied && filter !== 'groups') {
            html += '<div class="bgc-heading">' + esc(T('Requests')) + '</div>';
            html += rs.length ? rs.slice(0, 300).map(function (c) {
                var t = 'sr:' + c.request_id;
                return '<div class="bgc-item' + (c.unread_mentions ? ' unread' : '') + (cur && cur.thread === t ? ' active' : '') +
                    '" data-thread="' + t + '" role="button" tabindex="0">' +
                    '<div class="bgc-avatar">' + esc(initials(c.client_name || c.title)) + '</div>' +
                    '<div class="bgc-item-body"><div class="bgc-row"><span class="bgc-name"><span class="rid">SR-' + c.request_id +
                    '</span> · ' + esc(c.title || '') + '</span>' +
                    '<span class="bgc-time">' + (c.last_message_at ? listTime(c.last_message_at) : '') + '</span></div>' +
                    '<div class="bgc-sub">' + esc(c.client_name || '-') + (c.company_name ? ' · ' + esc(c.company_name) : '') + '</div>' +
                    '<div class="bgc-row"><span class="bgc-preview" data-no-i18n>' +
                    (c.last_message_at ? esc((c.last_message_user || '').split(' ')[0]) + ': ' + esc(c.last_message_text || '')
                                       : '<i>' + esc(T('No messages yet')) + '</i>') + '</span>' +
                    (c.unread_mentions ? '<span class="bgc-count">@' + c.unread_mentions + '</span>' : '') +
                    '</div></div></div>';
            }).join('') : '<div class="bgc-empty">' + esc(T(filter === 'unread' ? 'No unread chats.' : 'No chats found.')) + '</div>';
        }
        if (!html) { html = '<div class="bgc-empty">' + esc(T('No chats found.')) + '</div>'; }
        $('#chatListItems').html(html);
    }

    // ---------------------------------------------------------------- open / close
    var historyPushed = 0;
    function pushState(kind) {
        try { history.pushState({ bgChat: kind }, ''); historyPushed++; } catch (e) { /* ignore */ }
    }
    function fit() {
        // Keep the composer above the on-screen keyboard (iOS shrinks only the visual viewport).
        var vv = window.visualViewport;
        if (!vv || !$drawer.hasClass('open') || !PHONE.matches) { $drawer.css({ height: '', top: '' }); return; }
        $drawer.css({ height: vv.height + 'px', top: vv.offsetTop + 'px' });
    }
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', fit);
        window.visualViewport.addEventListener('scroll', fit);
    }

    function openDrawer() {
        if ($drawer.hasClass('open')) { return; }
        $drawer.addClass('open').attr('aria-hidden', 'false');
        $overlay.addClass('open');
        $('body').addClass('bgc-lock');
        if (PHONE.matches) { pushState('list'); }
        fit();
        renderList();
        fetchChats();
        clearInterval(listTimer);
        listTimer = setInterval(function () { if (visible()) { fetchChats(); } }, 8000);
    }
    function closeDrawer(fromHistory) {
        if (!$drawer.hasClass('open')) { return; }
        stopRecording(true);
        $drawer.removeClass('open thread-open').attr('aria-hidden', 'true');
        $overlay.removeClass('open');
        $('body').removeClass('bgc-lock');
        clearInterval(listTimer); clearInterval(threadTimer);
        audio.pause();
        cur = null;
        $drawer.css({ height: '', top: '' });
        if (!fromHistory && historyPushed) { var n = historyPushed; historyPushed = 0; skipPop += n; history.go(-n); }
        historyPushed = 0;
    }
    function backToList(fromHistory) {
        stopRecording(true);
        $drawer.removeClass('thread-open');
        clearInterval(threadTimer);
        cur = null;
        renderList();
        if (!fromHistory && historyPushed > 1) { historyPushed--; skipPop++; history.back(); }
    }
    var skipPop = 0;
    window.addEventListener('popstate', function () {
        if (skipPop) { skipPop--; return; }
        if (!$drawer.hasClass('open')) { return; }
        historyPushed = Math.max(0, historyPushed - 1);
        if ($('#chatThreadPane .bgc-sheet').length) { $('#chatThreadPane .bgc-sheet').remove(); pushState('sheet-closed'); return; }
        if ($drawer.hasClass('thread-open') && PHONE.matches) { backToList(true); } else { closeDrawer(true); }
    });

    function openThread(thread) {
        if (!thread) { return; }
        openDrawer();
        stopRecording(true);
        var wasOpen = $drawer.hasClass('thread-open');
        cur = { thread: thread, kind: isGroup(thread) ? 'g' : 'sr', key: thread.split(':')[1], members: [] };
        rendered = {}; cache = {}; lastDay = null; lastAuthor = null; pending = []; replyTo = null;
        $drawer.addClass('thread-open');
        if (PHONE.matches && !wasOpen) { pushState('thread'); }
        renderShell();
        renderList();
        fetchThread(false);
        loadMembers();
        clearInterval(threadTimer);
        threadTimer = setInterval(function () { if (cur && visible()) { fetchThread(true); } }, 4000);
        if (cur.kind === 'sr') {
            var c = chats.filter(function (x) { return 'sr:' + x.request_id === thread; })[0];
            if (c && c.unread_mentions) { srUnread = Math.max(0, srUnread - c.unread_mentions); c.unread_mentions = 0; setBadge(); }
            $.ajax({ url: '/api/chat/sr/' + cur.key + '/mark-read', type: 'POST', silent: true }).always(function () { setTimeout(fetchChats, 300); });
            fetchSrMeta(cur.key);
        } else {
            var g = groups.filter(function (x) { return 'g:' + x.room === thread; })[0];
            if (g && g.unread) { groupUnread = Math.max(0, groupUnread - g.unread); g.unread = 0; setBadge(); }
        }
        if (!COARSE.matches) { setTimeout(function () { $('#chatComposer').trigger('focus'); }, 50); }
    }

    function headerInfo() {
        if (cur.kind === 'g') {
            var g = groups.filter(function (x) { return x.room === cur.key; })[0] || {};
            return { icon: '<i class="fas ' + esc(g.icon || 'fa-users') + '"></i>', title: T('{0} group').replace('{0}', T(g.title || cur.key)),
                     sub: (g.members || cur.members.length || '') + ' ' + T('members'), group: true };
        }
        var c = chats.filter(function (x) { return String(x.request_id) === cur.key; })[0] || {};
        return { icon: esc(initials(c.client_name || c.title || 'SR')), title: 'SR-' + cur.key + (c.title ? ' · ' + c.title : ''),
                 sub: [c.client_name, c.company_name].filter(Boolean).join(' · '), group: false };
    }

    function renderShell() {
        var h = headerInfo();
        $('#chatThreadPane').html(
            '<div class="bgc-thead">' +
              '<button type="button" class="bgc-icon-btn bgc-back" title="' + esc(T('Back')) + '"><i class="fas fa-arrow-left fa-flip-rtl"></i></button>' +
              '<div class="bgc-avatar' + (h.group ? ' group' : '') + '">' + h.icon + '</div>' +
              '<div class="bgc-thead-main" title="' + esc(T('Members')) + '">' +
                '<div class="bgc-thead-title" data-no-i18n>' + esc(h.title) + '</div>' +
                '<div class="bgc-thead-sub" id="chatThreadMeta">' + esc(h.sub) + '</div></div>' +
              (h.group ? '' : '<button type="button" class="bgc-open-btn" id="chatDetailsBtn"><i class="fas fa-external-link-alt"></i> ' + esc(T('Open')) + '</button>') +
              '<button type="button" class="bgc-icon-btn bgc-members-btn" title="' + esc(T('Members')) + '"><i class="fas fa-users"></i></button>' +
              '<button type="button" class="bgc-icon-btn bgc-thread-close" title="' + esc(T('Close')) + '"><i class="fas fa-times"></i></button>' +
            '</div>' +
            '<div class="bgc-msgs" id="chatThreadMessages"><div class="bgc-empty"><i class="fas fa-spinner fa-spin"></i></div></div>' +
            '<button type="button" class="bgc-jump" title="' + esc(T('Latest')) + '"><i class="fas fa-chevron-down"></i></button>' +
            '<div class="bgc-composer" id="chatComposerBar">' +
              '<div class="bgc-suggest" id="chatMentionSuggest"></div>' +
              '<div class="bgc-replybar" id="chatReplyBar"></div>' +
              '<div class="bgc-emoji-panel" id="chatEmojiPanel"></div>' +
              '<div class="bgc-crow">' +
                '<button type="button" class="bgc-icon-btn bgc-emoji-btn" title="' + esc(T('Emoji and stickers')) + '"><i class="far fa-smile"></i></button>' +
                '<button type="button" class="bgc-icon-btn bgc-attach" title="' + esc(T('Photo')) + '"><i class="fas fa-paperclip"></i></button>' +
                (COARSE.matches ? '<button type="button" class="bgc-icon-btn bgc-camera" title="' + esc(T('Camera')) + '"><i class="fas fa-camera"></i></button>' : '') +
                '<div class="bgc-input"><textarea id="chatComposer" rows="1" placeholder="' + esc(T('Type a message')) + '" enterkeyhint="' + (COARSE.matches ? 'enter' : 'send') + '"></textarea></div>' +
                '<button type="button" class="bgc-send" id="chatSendBtn" title="' + esc(T('Send')) + '"></button>' +
              '</div>' +
              '<div class="bgc-rec"><button type="button" class="bgc-icon-btn bgc-trash" title="' + esc(T('Cancel')) + '"><i class="fas fa-trash"></i></button>' +
                '<span class="bgc-rec-dot"></span><span class="bgc-rec-time">0:00</span>' +
                '<span class="bgc-rec-label">' + esc(T('Recording...')) + '</span>' +
                '<button type="button" class="bgc-send bgc-rec-send" title="' + esc(T('Send')) + '"><i class="fas fa-paper-plane"></i></button></div>' +
            '</div>' +
            '<div class="bgc-drop">' + esc(T('Drop photos to send')) + '</div>' +
            '<input type="file" id="chatFileInput" accept="image/*" multiple hidden>' +
            '<input type="file" id="chatCameraInput" accept="image/*" capture="environment" hidden>' +
            '<input type="file" id="chatStickerInput" accept="image/png,image/webp,image/gif,image/jpeg" hidden>');
        updateSendButton();
    }

    function fetchSrMeta(id) {
        $.ajax({ url: '/api/sales/requests/' + id, silent: true }).done(function (r) {
            if (!r || !r.success || !r.request || !cur || cur.key !== String(id)) { return; }
            var sr = r.request, bits = [sr.client_name, sr.company_name, sr.status].filter(Boolean);
            $('#chatThreadMeta').text(bits.join(' · '));
            if (sr.title) { $('.bgc-thead-title').text('SR-' + id + ' · ' + sr.title); }
        });
    }

    function loadMembers() {
        var t = cur.thread;
        $.ajax({ url: '/api/chat/thread/' + encodeURIComponent(t) + '/members', cache: false, silent: true }).done(function (r) {
            if (!r || !r.success || !cur || cur.thread !== t) { return; }
            cur.members = r.members || [];
            if (cur.kind === 'g') { $('#chatThreadMeta').text(cur.members.length + ' ' + T('members')); }
        });
    }

    // ---------------------------------------------------------------- messages
    function fetchThread(silent) {
        var t = cur.thread;
        var params = { seen: visible() ? 1 : 0 };
        if (cur.kind === 'sr') { params.receipts = 1; }
        $.ajax({ url: messagesUrl(t), data: params, cache: false, silent: !!silent }).done(function (r) {
            if (!r || !r.success || !cur || cur.thread !== t) { return; }
            renderMessages((r.comments || []).slice().reverse());
        }).fail(function (xhr) {
            if (!silent && cur && cur.thread === t) {
                $('#chatThreadMessages').html('<div class="bgc-empty">' + esc(T(xhr.status === 403 ? 'You are not in this chat.' : 'Could not load messages.')) + '</div>');
            }
        });
    }

    function ticksHtml(m) {
        if (m.user_id !== ME) { return ''; }
        var st = m.receipt || 'sent';
        if (st === 'sending') { return '<span class="bgc-ticks"><i class="far fa-clock"></i></span>'; }
        if (st === 'failed') { return '<span class="bgc-ticks failed" title="' + esc(T('Not sent. Tap to retry')) + '"><i class="fas fa-exclamation-circle"></i></span>'; }
        var icon = st === 'sent' ? '<i class="fas fa-check"></i>' : '<i class="fas fa-check-double"></i>';
        var title = st === 'seen_all' ? T('Seen by everyone') : st === 'seen_some' ? (m.seen_count + ' / ' + m.member_count + ' ' + T('seen')) : T('Sent');
        return '<span class="bgc-ticks ' + st + '" title="' + esc(title) + '">' + icon + '</span>';
    }

    function bubbleHtml(m, first) {
        var own = m.user_id === ME;
        var names = cur.members.map(function (u) { return u.name; }).concat(['all', 'everyone']);
        var text = (m.attachments && m.attachments.length) ? (m.caption || '') : (m.comment_text || '');
        var isSticker = m.attachments && m.attachments.length && m.attachments[0].kind === 'sticker';
        var big = !(m.attachments && m.attachments.length) && !m.reply ? jumboCount(text) : 0;
        return '<div class="bgc-msg' + (own ? ' own' : '') + (first ? ' first' : '') + (m.temp ? ' pending' : '') +
            (isSticker ? ' sticker' : '') + (big ? ' jumbo jumbo-' + big : '') +
            '" data-id="' + esc(m.id) + '">' +
            '<div class="bgc-bubble">' +
              (m.temp ? '' : '<button type="button" class="bgc-reply-btn" title="' + esc(T('Reply')) + '"><i class="fas fa-reply"></i></button>') +
              (!own && first ? '<div class="bgc-author" style="color:' + colourFor(m.user_id) + '" data-no-i18n>' + esc(m.user_name || '') + '</div>' : '') +
              quoteHtml(m.reply, true) +
              mediaHtml(m.attachments, m.progress) +
              (text ? '<span class="bgc-text" data-no-i18n>' + highlight(text, names) + '</span>' : '') +
              '<span class="bgc-meta">' + hhmm(m.created_at) + ticksHtml(m) + '</span>' +
            '</div></div>';
    }

    // ---------------------------------------------------------------- replies
    function quoteText(q) {
        if (!q) { return ''; }
        if (q.deleted) { return '<i>' + esc(T('This message was deleted')) + '</i>'; }
        var icon = q.kind === 'image' ? '<i class="fas fa-camera"></i> ' : q.kind === 'voice' ? '<i class="fas fa-microphone"></i> '
                 : q.kind === 'sticker' ? '<i class="far fa-sticky-note"></i> ' : '';
        var t = q.text || (q.kind === 'image' ? T('Photo') : q.kind === 'voice' ? T('Voice note') : q.kind === 'sticker' ? T('Sticker') : '');
        return icon + '<span data-no-i18n>' + esc(t) + '</span>';
    }
    function quoteHtml(q, inBubble) {
        if (!q) { return ''; }
        var who = q.user_id === ME ? T('You') : (q.user_name || '');
        return '<div class="bgc-quote"' + (inBubble ? ' data-jump="' + esc(q.id) + '"' : '') +
            ' style="border-inline-start-color:' + colourFor(q.user_id) + '">' +
            '<div class="who" style="color:' + colourFor(q.user_id) + '" data-no-i18n>' + esc(who) + '</div>' +
            '<div class="q">' + quoteText(q) + '</div></div>';
    }
    function messageById(id) {
        var $m = $('#chatThreadMessages .bgc-msg[data-id="' + id + '"]');
        if (!$m.length) { return null; }
        var src = cache[id];
        return src ? { id: src.id, user_id: src.user_id, user_name: src.user_name,
                       text: (src.attachments && src.attachments.length) ? (src.caption || '') : (src.comment_text || ''),
                       kind: src.attachments && src.attachments.length ? src.attachments[0].kind : null } : null;
    }
    function startReply(id) {
        var q = messageById(id);
        if (!q || !cur) { return; }
        replyTo = q;
        $('#chatReplyBar').html(quoteHtml(q, false) +
            '<button type="button" class="bgc-icon-btn bgc-reply-cancel" title="' + esc(T('Cancel')) + '"><i class="fas fa-times"></i></button>').show();
        if (!$('#chatComposerBar').hasClass('recording')) { $('#chatComposer').trigger('focus'); }
    }
    function clearReply() { replyTo = null; $('#chatReplyBar').hide().empty(); }
    function jumpTo(id) {
        var $m = $('#chatThreadMessages .bgc-msg[data-id="' + id + '"]');
        if (!$m.length) { toast('info', T('That message is too far back to show here')); return; }
        $m[0].scrollIntoView({ block: 'center', behavior: 'smooth' });
        $m.removeClass('flash'); void $m[0].offsetWidth; $m.addClass('flash');
    }

    function nearBottom($box) { var el = $box[0]; return el.scrollHeight - el.scrollTop - el.clientHeight < 120; }
    function toBottom() { var el = $('#chatThreadMessages')[0]; if (el) { el.scrollTop = el.scrollHeight; } $('.bgc-jump').removeClass('show').find('.bgc-count').remove(); }

    function renderMessages(list) {
        var $box = $('#chatThreadMessages');
        if (!$box.length) { return; }
        var first = $.isEmptyObject(rendered) && !$box.find('.bgc-msg').length;
        var ids = {};
        list.forEach(function (m) { ids[m.id] = 1; });
        // A message gone (deleted): start again rather than patch around it.
        var gone = Object.keys(rendered).some(function (id) { return !ids[id]; });
        if (gone && !(audio && !audio.paused)) { rendered = {}; lastDay = null; lastAuthor = null; $box.empty(); first = true; }
        if (first) { $box.empty(); }
        var stick = first || nearBottom($box), added = 0, mine = false;
        list.forEach(function (m) {
            cache[m.id] = m;
            if (rendered.hasOwnProperty(m.id)) {
                if (m.user_id === ME && rendered[m.id] !== m.receipt) {
                    $box.find('.bgc-msg[data-id="' + m.id + '"] .bgc-ticks').replaceWith(ticksHtml(m));
                    rendered[m.id] = m.receipt;
                }
                return;
            }
            var d = parseTime(m.created_at), dk = d && !isNaN(d) ? dayKey(d) : '';
            var html = '';
            if (dk !== lastDay) { html += '<div class="bgc-day"><span>' + esc(dayLabel(m.created_at)) + '</span></div>'; lastDay = dk; lastAuthor = null; }
            html += bubbleHtml(m, lastAuthor !== m.user_id);
            lastAuthor = m.user_id;
            var $pend = $box.find('.bgc-msg.pending').first();
            if ($pend.length) { $pend.before(html); } else { $box.append(html); }
            rendered[m.id] = m.receipt;
            added++;
            if (m.user_id === ME) { mine = true; }
        });
        if (!list.length && first) { $box.html('<div class="bgc-empty">' + esc(T('No messages yet. Say hello')) + '</div>'); }
        if (list.length) { $box.children('.bgc-empty').remove(); }
        if (stick || mine) { toBottom(); }
        else if (added) {
            var $j = $('.bgc-jump').addClass('show'), $n = $j.find('.bgc-count');
            var n = (Number($n.text()) || 0) + added;
            if ($n.length) { $n.text(n); } else { $j.append('<span class="bgc-count">' + n + '</span>'); }
        }
    }

    $(document).on('scroll', '#chatThreadMessages', function () { if (nearBottom($(this))) { $('.bgc-jump').removeClass('show').find('.bgc-count').remove(); } });
    document.addEventListener('scroll', function (e) {
        if (e.target && e.target.id === 'chatThreadMessages' && nearBottom($(e.target))) { $('.bgc-jump').removeClass('show').find('.bgc-count').remove(); }
    }, true);
    $(document).on('click', '.bgc-jump', toBottom);

    // ---------------------------------------------------------------- sending
    function mentionIds(text) {
        var out = MENTION_ALL.test(text || '') ? ['all'] : [];
        cur.members.forEach(function (u) {
            if (u.is_me || !u.name) { return; }
            var re = new RegExp('@' + u.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?=$|[\\s.,!?;:)\\]}])');
            if (re.test(text) && out.indexOf(u.id) < 0) { out.push(u.id); }
        });
        return out;
    }

    function addPending(msg) {
        msg.temp = true; msg.id = 'tmp' + (++tempSeq); msg.user_id = ME; msg.user_name = ME_NAME;
        msg.created_at = new Date().toISOString().slice(0, 19).replace('T', ' ');
        msg.receipt = 'sending';
        pending.push(msg);
        var $box = $('#chatThreadMessages');
        $box.children('.bgc-empty').remove();
        $box.append(bubbleHtml(msg, lastAuthor !== ME));
        toBottom();
        return msg;
    }
    function redrawPending(msg) {
        $('#chatThreadMessages .bgc-msg[data-id="' + msg.id + '"]').replaceWith(bubbleHtml(msg, false));
    }
    function dropPending(msg) {
        pending = pending.filter(function (p) { return p !== msg; });
        $('#chatThreadMessages .bgc-msg[data-id="' + msg.id + '"]').remove();
        if (msg.objectUrl) { URL.revokeObjectURL(msg.objectUrl); }
    }

    function post(msg) {
        var t = cur.thread, fd = null, data;
        if (msg.blob) {
            fd = new FormData();
            fd.append('file', msg.blob, msg.filename);
            fd.append('kind', msg.kind);
            fd.append('comment_text', msg.comment_text || '');
            fd.append('mentioned_users', JSON.stringify(msg.mentions || []));
            fd.append('source', 'general');
            if (msg.reply) { fd.append('reply_to', String(msg.reply.id)); }
            if (msg.duration_ms) { fd.append('duration_ms', String(msg.duration_ms)); }
        } else {
            data = JSON.stringify({ comment_text: msg.comment_text, source: 'general', is_note: false,
                                    mentioned_users: msg.mentions || [], reply_to: msg.reply ? msg.reply.id : null,
                                    sticker_id: msg.sticker_id || null });
        }
        msg.receipt = 'sending'; msg.progress = msg.blob ? 0 : null; redrawPending(msg);
        $.ajax({
            url: messagesUrl(t), type: 'POST', silent: true,
            data: fd || data, processData: !fd, contentType: fd ? false : 'application/json',
            xhr: function () {
                var x = $.ajaxSettings.xhr();
                if (fd && x.upload) {
                    x.upload.addEventListener('progress', function (e) {
                        if (e.lengthComputable) { msg.progress = Math.round(100 * e.loaded / e.total);
                            $('#chatThreadMessages .bgc-msg[data-id="' + msg.id + '"] .bgc-progress').text(msg.progress + '%'); }
                    });
                }
                return x;
            }
        }).done(function (r) {
            if (r && r.success) {
                dropPending(msg);
                if (cur && cur.thread === t) { fetchThread(false); }
                fetchChats();
            } else { failed(msg, r && r.error); }
        }).fail(function (xhr) { failed(msg, xhr.responseJSON && xhr.responseJSON.error); });
    }
    function failed(msg, why) {
        msg.receipt = 'failed'; msg.progress = null; redrawPending(msg);
        toast('error', why || T('Not sent. Tap to retry'));
    }
    $(document).on('click', '.bgc-msg.pending .bgc-ticks.failed', function (e) {
        e.stopPropagation();
        var id = $(this).closest('.bgc-msg').data('id');
        var msg = pending.filter(function (p) { return p.id === id; })[0];
        if (msg) { post(msg); }
    });

    function sendText() {
        var $ta = $('#chatComposer'), text = ($ta.val() || '').trim();
        if (!text || !cur) { return; }
        $ta.val('').trigger('input');
        hideSuggest();
        var reply = replyTo; clearReply();
        post(addPending({ comment_text: text, mentions: mentionIds(text), attachments: [], reply: reply }));
    }

    function updateSendButton() {
        var empty = !($('#chatComposer').val() || '').trim();
        var mic = empty && CAN_RECORD;
        $('#chatSendBtn').html('<i class="fas fa-' + (mic ? 'microphone' : 'paper-plane') + '"></i>')
            .attr('title', T(mic ? 'Record a voice note' : 'Send')).toggleClass('is-mic', mic);
    }
    function autosize(ta) { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'; }

    // ---------------------------------------------------------------- photos
    function shrink(file) {
        // Re-encode in the browser: a 4 MB phone photo becomes ~300 KB, and its
        // location data does not travel with it. GIFs are sent as they are.
        return new Promise(function (resolve) {
            if (!/^image\/(jpeg|png|webp|heic|heif)$/i.test(file.type) && file.type) { return resolve({ blob: file }); }
            var url = URL.createObjectURL(file), img = new Image();
            img.onload = function () {
                var max = 1600, w = img.naturalWidth, h = img.naturalHeight, k = Math.min(1, max / Math.max(w, h));
                var c = document.createElement('canvas'); c.width = Math.round(w * k); c.height = Math.round(h * k);
                c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
                URL.revokeObjectURL(url);
                c.toBlob(function (b) {
                    resolve(b && (b.size < file.size || !/^image\/(jpeg|png|webp|gif)$/i.test(file.type))
                        ? { blob: b, width: c.width, height: c.height } : { blob: file, width: w, height: h });
                }, 'image/jpeg', 0.82);
            };
            img.onerror = function () { URL.revokeObjectURL(url); resolve({ blob: file }); };
            img.src = url;
        });
    }

    function previewPhotos(files) {
        files = Array.prototype.filter.call(files || [], function (f) { return /^image\//.test(f.type) || /\.(heic|heif)$/i.test(f.name); }).slice(0, 10);
        if (!files.length || !cur) { return; }
        var urls = files.map(function (f) { return URL.createObjectURL(f); }), at = 0;
        var $s = $('<div class="bgc-sheet bgc-photo-sheet">' +
            '<div class="bgc-sheet-head"><button type="button" class="bgc-icon-btn bgc-sheet-close" title="' + esc(T('Cancel')) + '"><i class="fas fa-times"></i></button>' +
            '<span>' + esc(files.length === 1 ? T('Send photo') : files.length + ' ' + T('photos')) + '</span></div>' +
            '<div class="bgc-preview-wrap"><img alt="" src="' + urls[0] + '"></div>' +
            (files.length > 1 ? '<div class="bgc-preview-thumbs">' + urls.map(function (u, i) { return '<img src="' + u + '" data-i="' + i + '"' + (i ? '' : ' class="on"') + '>'; }).join('') + '</div>' : '') +
            '<div class="bgc-composer"><div class="bgc-crow"><div class="bgc-input"><textarea class="bgc-caption" rows="1" placeholder="' +
            esc(T('Add a caption...')) + '"></textarea></div>' +
            '<button type="button" class="bgc-send bgc-photo-send" title="' + esc(T('Send')) + '"><i class="fas fa-paper-plane"></i></button></div></div></div>');
        $('#chatThreadPane').append($s);
        if (PHONE.matches) { pushState('sheet'); }
        $s.on('click', '.bgc-preview-thumbs img', function () {
            at = Number($(this).data('i'));
            $s.find('.bgc-preview-wrap img').attr('src', urls[at]);
            $s.find('.bgc-preview-thumbs img').removeClass('on'); $(this).addClass('on');
        });
        function close() { urls.forEach(function (u) { URL.revokeObjectURL(u); }); closeSheet($s); }
        $s.on('click', '.bgc-sheet-close', close);
        $s.on('input', '.bgc-caption', function () { autosize(this); });
        $s.on('keydown', '.bgc-caption', function (e) { if (e.key === 'Enter' && !e.shiftKey && !COARSE.matches) { e.preventDefault(); $s.find('.bgc-photo-send').click(); } });
        $s.on('click', '.bgc-photo-send', function () {
            var caption = ($s.find('.bgc-caption').val() || '').trim();
            var reply = replyTo; clearReply();
            close();
            files.forEach(function (f, i) {
                var local = URL.createObjectURL(f);
                var msg = addPending({ kind: 'image', comment_text: i === 0 ? caption : '', caption: i === 0 ? caption : '',
                                       mentions: i === 0 ? mentionIds(caption) : [], objectUrl: local, reply: i === 0 ? reply : null,
                                       attachments: [{ kind: 'image', url: local }] });
                shrink(f).then(function (r) {
                    msg.blob = r.blob; msg.filename = (f.name || 'photo').replace(/\.\w+$/, '') + (r.blob.type === 'image/jpeg' ? '.jpg' : '');
                    post(msg);
                });
            });
        });
        if (!COARSE.matches) { $s.find('.bgc-caption').trigger('focus'); }
    }
    function closeSheet($s) {
        $s.remove();
        if (PHONE.matches && historyPushed > 1) { historyPushed--; skipPop++; history.back(); }
    }

    // ---------------------------------------------------------------- voice notes
    var rec = null;   // {recorder, stream, chunks, started, timer, cancelled}
    function pickMime() {
        var options = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'];
        for (var i = 0; i < options.length; i++) { if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(options[i])) { return options[i]; } }
        return '';
    }
    function startRecording() {
        if (rec || !cur) { return; }
        navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
            var mime = pickMime();
            var recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
            rec = { recorder: recorder, stream: stream, chunks: [], started: Date.now(), thread: cur.thread };
            recorder.ondataavailable = function (e) { if (e.data && e.data.size) { rec && rec.chunks.push(e.data); } };
            recorder.onstop = function () {
                var r = rec; rec = null;
                r.stream.getTracks().forEach(function (t) { t.stop(); });
                clearInterval(r.timer);
                $('#chatComposerBar').removeClass('recording');
                if (r.cancelled || !cur || cur.thread !== r.thread) { return; }
                var ms = Date.now() - r.started;
                if (ms < 800) { toast('info', T('Hold on a little longer to record')); return; }
                var type = (recorder.mimeType || mime || 'audio/webm').split(';')[0];
                var blob = new Blob(r.chunks, { type: type });
                var reply = replyTo; clearReply();
                var msg = addPending({ kind: 'voice', comment_text: '', duration_ms: ms, mentions: [], reply: reply,
                                       attachments: [{ kind: 'voice', url: '', duration_ms: ms }] });
                msg.blob = blob;
                msg.filename = 'voice.' + ({ 'audio/mp4': 'm4a', 'audio/ogg': 'ogg' }[type] || 'webm');
                post(msg);
            };
            recorder.start(250);
            $('#chatComposerBar').addClass('recording');
            rec.timer = setInterval(function () {
                if (!rec) { return; }
                var ms = Date.now() - rec.started;
                $('.bgc-rec-time').text(mmss(ms));
                if (ms >= MAX_VOICE_MS) { stopRecording(false); }
            }, 250);
        }).catch(function () {
            toast('warning', T('Allow the microphone in your browser to record voice notes'));
        });
    }
    function stopRecording(cancel) {
        if (!rec) { return; }
        rec.cancelled = !!cancel;
        try { rec.recorder.stop(); } catch (e) { rec = null; $('#chatComposerBar').removeClass('recording'); }
    }

    // ---------------------------------------------------------------- @ mentions
    var sug = { on: false, start: -1, list: [], idx: 0 };
    function updateSuggest() {
        var ta = document.getElementById('chatComposer'); if (!ta || !cur) { return; }
        var before = ta.value.substring(0, ta.selectionStart), at = before.lastIndexOf('@');
        if (at < 0 || (at > 0 && !/\s/.test(before.charAt(at - 1)))) { return hideSuggest(); }
        var q = before.substring(at + 1);
        if (/\n/.test(q) || q.length > 30) { return hideSuggest(); }
        q = q.toLowerCase();
        sug.list = cur.members.filter(function (u) { return !u.is_me && (u.name || '').toLowerCase().indexOf(q) >= 0; }).slice(0, 8);
        // @all: everyone in this chat, at the top like WhatsApp's "everyone".
        if (cur.members.length > 1 && ('all'.indexOf(q) === 0 || 'everyone'.indexOf(q) === 0)) {
            sug.list.unshift({ id: 'all', name: 'all', everyone: true });
        }
        if (!sug.list.length) { return hideSuggest(); }
        sug.on = true; sug.start = at; sug.idx = 0;
        $('#chatMentionSuggest').html('<div class="hint">' + esc(T('People in this chat')) + '</div>' + sug.list.map(function (u, i) {
            if (u.everyone) {
                var others = cur.members.filter(function (m) { return !m.is_me; }).length;
                return '<div class="item' + (i ? '' : ' active') + '" data-i="' + i + '">' +
                    '<div class="bgc-avatar sm group"><i class="fas fa-users"></i></div>' +
                    '<div><div class="who">@all</div><small>' + esc(T('Everyone in this chat')) + ' (' + others + ')</small></div></div>';
            }
            return '<div class="item' + (i ? '' : ' active') + '" data-i="' + i + '">' +
                '<div class="bgc-avatar sm" style="background:' + colourFor(u.id) + '">' + esc(initials(u.name)) + '</div>' +
                '<div><div class="who" data-no-i18n>' + esc(u.name) + '</div><small>' + esc([u.role_name, u.department_name].filter(Boolean).join(' · ')) + '</small></div></div>';
        }).join('')).show();
    }
    function hideSuggest() { sug.on = false; $('#chatMentionSuggest').hide(); }
    function pickSuggest(i) {
        var u = sug.list[i], ta = document.getElementById('chatComposer'); if (!u || !ta) { return; }
        var v = ta.value, pos = ta.selectionStart;
        ta.value = v.substring(0, sug.start) + '@' + u.name + ' ' + v.substring(pos);
        var np = sug.start + u.name.length + 2;
        ta.setSelectionRange(np, np); ta.focus();
        hideSuggest(); updateSendButton(); autosize(ta);
    }

    // ---------------------------------------------------------------- emoji + stickers
    var pickerTab = 'emoji';
    function recentEmoji() { try { return JSON.parse(localStorage.getItem('bg.chat.recentEmoji') || '[]'); } catch (e) { return []; } }
    function rememberEmoji(e) {
        var list = recentEmoji().filter(function (x) { return x !== e; }); list.unshift(e);
        try { localStorage.setItem('bg.chat.recentEmoji', JSON.stringify(list.slice(0, 24))); } catch (err) { /* ignore */ }
    }
    function renderPicker() {
        var $p = $('#chatEmojiPanel');
        var tabs = '<div class="bgc-ep-tabs">' +
            '<button type="button" class="bgc-ep-tab' + (pickerTab === 'emoji' ? ' on' : '') + '" data-tab="emoji"><i class="far fa-smile"></i> ' + esc(T('Emoji')) + '</button>' +
            '<button type="button" class="bgc-ep-tab' + (pickerTab === 'stickers' ? ' on' : '') + '" data-tab="stickers"><i class="far fa-sticky-note"></i> ' + esc(T('Stickers')) + '</button></div>';
        var body = '';
        if (pickerTab === 'emoji') {
            var recent = recentEmoji();
            var groups = (recent.length ? [{ title: 'Recent', list: recent }] : []).concat(EMOJI);
            body = groups.map(function (g) {
                return '<div class="bgc-ep-title">' + esc(T(g.title)) + '</div><div class="bgc-ep-grid">' +
                    g.list.map(function (e) { return '<button type="button" class="bgc-ep-emoji" data-e="' + esc(e) + '">' + e + '</button>'; }).join('') + '</div>';
            }).join('');
        } else {
            body = '<div class="bgc-ep-title">' + esc(T('Big emoji')) + '</div><div class="bgc-ep-grid big">' +
                BIG_EMOJI.map(function (e) { return '<button type="button" class="bgc-ep-big" data-e="' + esc(e) + '">' + e + '</button>'; }).join('') + '</div>' +
                '<div class="bgc-ep-title">' + esc(T('Company stickers')) + '</div><div class="bgc-ep-stickers">' +
                '<button type="button" class="bgc-ep-add" title="' + esc(T('Add a sticker')) + '"><i class="fas fa-plus"></i><small>' + esc(T('Add')) + '</small></button>' +
                (stickers === null ? '<div class="bgc-empty"><i class="fas fa-spinner fa-spin"></i></div>'
                    : stickers.map(function (st) {
                        return '<button type="button" class="bgc-ep-sticker" data-id="' + st.id + '" data-url="' + esc(st.url) + '"' +
                            (st.mine || canRemoveAny ? ' data-removable="1"' : '') + '><img loading="lazy" alt="" src="' + esc(st.url) + '"></button>';
                    }).join('')) + '</div>' +
                (stickers && !stickers.length ? '<div class="bgc-ep-hint">' + esc(T('No stickers yet. Add one, or hold a photo in a chat and pick "Add to stickers".')) + '</div>' : '');
        }
        $p.html(tabs + '<div class="bgc-ep-body">' + body + '</div>');
    }
    var canRemoveAny = false;
    function loadStickers() {
        $.ajax({ url: '/api/chat/stickers', cache: false, silent: true }).done(function (r) {
            if (!r || !r.success) { return; }
            stickers = r.stickers || []; canRemoveAny = !!r.can_remove_any;
            if (pickerTab === 'stickers' && $('#chatEmojiPanel').hasClass('open')) { renderPicker(); }
        });
    }
    function togglePicker(force) {
        var $p = $('#chatEmojiPanel'), open = force === undefined ? !$p.hasClass('open') : force;
        $p.toggleClass('open', open);
        $('.bgc-emoji-btn').toggleClass('on', open).find('i').attr('class', open ? 'fas fa-keyboard' : 'far fa-smile');
        if (open) { hideSuggest(); renderPicker(); if (stickers === null) { loadStickers(); } }
    }
    function insertAtCursor(text) {
        var ta = document.getElementById('chatComposer'); if (!ta) { return; }
        var a = ta.selectionStart || ta.value.length, b = ta.selectionEnd || a;
        ta.value = ta.value.slice(0, a) + text + ta.value.slice(b);
        ta.setSelectionRange(a + text.length, a + text.length);
        autosize(ta); updateSendButton();
        if (!COARSE.matches) { ta.focus(); }
    }
    function sendSticker(st) {
        var reply = replyTo; clearReply(); togglePicker(false);
        post(addPending({ kind: 'sticker', sticker_id: st.id, comment_text: '', mentions: [], reply: reply,
                          attachments: [{ kind: 'sticker', url: st.url }] }));
    }
    function sendBigEmoji(e) {
        var reply = replyTo; clearReply(); togglePicker(false); rememberEmoji(e);
        post(addPending({ comment_text: e, mentions: [], attachments: [], reply: reply }));
    }
    $(document).on('click', '.bgc-emoji-btn', function () { togglePicker(); });
    $(document).on('click', '.bgc-ep-tab', function () { pickerTab = $(this).data('tab'); renderPicker(); if (pickerTab === 'stickers') { loadStickers(); } });
    $(document).on('click', '.bgc-ep-emoji', function () { var e = String($(this).data('e')); rememberEmoji(e); insertAtCursor(e); });
    $(document).on('click', '.bgc-ep-big', function () { sendBigEmoji(String($(this).data('e'))); });
    $(document).on('click', '.bgc-ep-sticker', function () {
        if ($(this).data('holding')) { return; }
        sendSticker({ id: $(this).data('id'), url: $(this).data('url') });
    });
    $(document).on('click', '.bgc-ep-add', function () { $('#chatStickerInput').val('').click(); });
    $(document).on('contextmenu', '.bgc-ep-sticker[data-removable]', function (e) { e.preventDefault(); removeSticker($(this)); });
    var stPress = null;
    $(document).on('touchstart', '.bgc-ep-sticker[data-removable]', function () {
        var $b = $(this); stPress = setTimeout(function () { $b.data('holding', 1); removeSticker($b); setTimeout(function () { $b.data('holding', 0); }, 600); }, 600);
    });
    $(document).on('touchend touchmove touchcancel', '.bgc-ep-sticker', function () { clearTimeout(stPress); });
    function removeSticker($b) {
        var go = function () {
            $.ajax({ url: '/api/chat/stickers/' + $b.data('id'), type: 'DELETE', silent: true }).done(function () {
                stickers = (stickers || []).filter(function (x) { return x.id !== $b.data('id'); }); renderPicker();
            });
        };
        if (window.Swal) { Swal.fire({ title: T('Remove this sticker from the pack?'), icon: 'question', showCancelButton: true,
                                        confirmButtonText: T('Remove'), cancelButtonText: T('Cancel') }).then(function (r) { if (r.isConfirmed) { go(); } }); }
        else if (confirm(T('Remove this sticker from the pack?'))) { go(); }
    }
    $(document).on('change', '#chatStickerInput', function () {
        var f = this.files && this.files[0]; if (!f) { return; }
        stickerFromFile(f).then(function (blob) {
            var fd = new FormData(); fd.append('file', blob, 'sticker.' + (blob.type === 'image/gif' ? 'gif' : blob.type === 'image/png' ? 'png' : 'webp'));
            $.ajax({ url: '/api/chat/stickers', type: 'POST', data: fd, processData: false, contentType: false, silent: true })
                .done(function (r) { if (r && r.success) { (stickers = stickers || []).unshift(r.sticker); pickerTab = 'stickers'; renderPicker(); toast('success', T('Added to stickers')); } })
                .fail(function (x) { toast('error', (x.responseJSON && x.responseJSON.error) || T('Could not add the sticker')); });
        });
    });
    function stickerFromFile(file) {
        // 512px, transparency kept (WebP, else PNG). GIFs stay as they are so they still move.
        return new Promise(function (resolve) {
            if (file.type === 'image/gif') { return resolve(file); }
            var url = URL.createObjectURL(file), img = new Image();
            img.onload = function () {
                var k = Math.min(1, 512 / Math.max(img.naturalWidth, img.naturalHeight));
                var c = document.createElement('canvas'); c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
                c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
                c.toBlob(function (b) {
                    if (b && b.type === 'image/webp') { return resolve(b); }
                    c.toBlob(function (p) { resolve(p || file); }, 'image/png');
                }, 'image/webp', 0.9);
            };
            img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
            img.src = url;
        });
    }
    // Typing closes the picker on a phone, as the keyboard takes the room.
    $(document).on('focus', '#chatComposer', function () { if (COARSE.matches) { togglePicker(false); } });

    // ---------------------------------------------------------------- info sheets
    function personRow(p, right) {
        return '<div class="bgc-person"><div class="bgc-avatar sm" style="background:' + colourFor(p.id) + '">' + esc(initials(p.name)) + '</div>' +
            '<div class="who"><div data-no-i18n>' + esc(p.name) + (p.is_me ? ' <small>(' + esc(T('You')) + ')</small>' : '') + '</div>' +
            (p.role_name || p.department_name ? '<small>' + esc([p.role_name, p.department_name].filter(Boolean).join(' · ')) + '</small>' : '') +
            '</div>' + (right ? '<span class="when">' + right + '</span>' : '') + '</div>';
    }
    function openSheet(title, body) {
        $('#chatThreadPane .bgc-sheet').remove();
        var $s = $('<div class="bgc-sheet"><div class="bgc-sheet-head"><button type="button" class="bgc-icon-btn bgc-sheet-close" title="' +
            esc(T('Close')) + '"><i class="fas fa-arrow-left fa-flip-rtl"></i></button><span>' + esc(title) + '</span></div>' +
            '<div class="bgc-sheet-body">' + body + '</div></div>');
        $('#chatThreadPane').append($s);
        if (PHONE.matches) { pushState('sheet'); }
        $s.on('click', '.bgc-sheet-close', function () { closeSheet($s); });
        return $s;
    }
    function showInfo(id) {
        if (!cur || String(id).indexOf('tmp') === 0) { return; }
        var $preview = $('#chatThreadMessages .bgc-msg[data-id="' + id + '"]').clone();
        var $s = openSheet(T('Message info'), '<div class="bgc-info-preview"></div><div class="bgc-info-lists"><div class="bgc-empty"><i class="fas fa-spinner fa-spin"></i></div></div>');
        $s.find('.bgc-info-preview').append($preview.css('width', '100%'));
        $.ajax({ url: '/api/chat/thread/' + encodeURIComponent(cur.thread) + '/messages/' + id + '/info', cache: false, silent: true }).done(function (r) {
            if (!r || !r.success) { return; }
            var html = '<div class="bgc-sheet-section"><i class="fas fa-check-double" style="color:var(--bgc-tick-seen)"></i> ' + esc(T('Seen by')) +
                ' (' + r.seen.length + ')</div>' +
                (r.seen.length ? r.seen.map(function (p) { return personRow(p, dayLabel(p.at) + ' ' + hhmm(p.at)); }).join('') : '<div class="bgc-empty">' + esc(T('Nobody yet')) + '</div>') +
                '<div class="bgc-sheet-section"><i class="fas fa-check"></i> ' + esc(T('Not seen yet')) + ' (' + r.not_seen.length + ')</div>' +
                (r.not_seen.length ? r.not_seen.map(function (p) { return personRow(p); }).join('') : '<div class="bgc-empty">' + esc(T('Everyone has seen it')) + '</div>');
            $s.find('.bgc-info-lists').html(html);
        }).fail(function () { $s.find('.bgc-info-lists').html('<div class="bgc-empty">' + esc(T('Could not load message info.')) + '</div>'); });
    }
    function showMembers() {
        if (!cur) { return; }
        var list = cur.members || [];
        openSheet(T('Members') + ' (' + list.length + ')', list.length ? list.map(function (p) { return personRow(p); }).join('') : '<div class="bgc-empty"><i class="fas fa-spinner fa-spin"></i></div>');
    }

    // A message's menu: long press on a phone, right click on a computer.
    function openMenu(id, x, y) {
        closeMenu();
        if (!cur || String(id).indexOf('tmp') === 0) { return; }
        var m = cache[id] || {}, own = m.user_id === ME;
        var text = (m.attachments && m.attachments.length) ? (m.caption || '') : (m.comment_text || '');
        var photo = (m.attachments || []).filter(function (a) { return a.kind === 'image' || a.kind === 'sticker'; })[0];
        var $menu = $('<div class="bgc-menu" role="menu">' +
            '<button type="button" data-act="reply"><i class="fas fa-reply"></i> ' + esc(T('Reply')) + '</button>' +
            (text ? '<button type="button" data-act="copy"><i class="far fa-copy"></i> ' + esc(T('Copy')) + '</button>' : '') +
            (photo ? '<button type="button" data-act="sticker"><i class="far fa-sticky-note"></i> ' + esc(T('Add to stickers')) + '</button>' : '') +
            (own ? '<button type="button" data-act="info"><i class="fas fa-info-circle"></i> ' + esc(T('Message info')) + '</button>' : '') +
            '</div>');
        $('body').append($menu);
        var w = $menu.outerWidth(), h = $menu.outerHeight();
        $menu.css({ left: Math.max(8, Math.min(x, window.innerWidth - w - 8)), top: Math.max(8, Math.min(y, window.innerHeight - h - 8)) });
        $menu.on('click', 'button', function () {
            var act = $(this).data('act');
            closeMenu();
            if (act === 'reply') { startReply(id); }
            if (act === 'info') { showInfo(id); }
            if (act === 'sticker' && photo) {
                $.ajax({ url: '/api/chat/stickers', type: 'POST', contentType: 'application/json', silent: true,
                         data: JSON.stringify({ from_attachment: photo.id }) })
                    .done(function (r) { if (r && r.success) { if (stickers) { stickers.unshift(r.sticker); } toast('success', T('Added to stickers')); } })
                    .fail(function (x) { toast('error', (x.responseJSON && x.responseJSON.error) || T('Could not add the sticker')); });
            }
            if (act === 'copy' && navigator.clipboard) { navigator.clipboard.writeText(text).then(function () { toast('success', T('Copied')); }); }
        });
    }
    function closeMenu() { $('.bgc-menu').remove(); }
    $(document).on('mousedown touchstart', function (e) { if (!$(e.target).closest('.bgc-menu').length) { closeMenu(); } });
    $(document).on('scroll', '#chatThreadMessages', closeMenu);

    // Touch: hold for the menu, or swipe the bubble sideways to reply.
    var press = null;
    var rtl = document.documentElement.getAttribute('dir') === 'rtl';
    $(document).on('touchstart', '#chatThreadMessages .bgc-msg:not(.pending) .bgc-bubble', function (e) {
        var $b = $(this), id = $b.closest('.bgc-msg').data('id'), t = e.originalEvent.touches[0];
        press = { id: id, $b: $b, x: t.clientX, y: t.clientY, dx: 0, swiping: false,
                  timer: setTimeout(function () {
                      if (!press || press.swiping) { return; }
                      if (navigator.vibrate) { navigator.vibrate(15); }
                      openMenu(id, press.x, press.y); press = null;
                  }, 500) };
    });
    $(document).on('touchmove', function (e) {
        if (!press) { return; }
        var t = e.originalEvent.touches[0], dx = t.clientX - press.x, dy = t.clientY - press.y;
        if (!press.swiping && Math.abs(dy) > 12) { clearTimeout(press.timer); press = null; return; }
        if (Math.abs(dx) > 10) { clearTimeout(press.timer); press.swiping = true; }
        if (press.swiping) {
            var pull = rtl ? Math.min(0, Math.max(-80, dx)) : Math.max(0, Math.min(80, dx));
            press.dx = pull;
            press.$b.css('transform', 'translateX(' + pull + 'px)');
        }
    });
    $(document).on('touchend touchcancel', function () {
        if (!press) { return; }
        clearTimeout(press.timer);
        var p = press; press = null;
        if (p.swiping) {
            p.$b.css({ transition: 'transform .15s', transform: '' });
            setTimeout(function () { p.$b.css('transition', ''); }, 160);
            if (Math.abs(p.dx) >= 55) { if (navigator.vibrate) { navigator.vibrate(10); } startReply(p.id); }
        }
    });
    $(document).on('contextmenu', '#chatThreadMessages .bgc-msg:not(.pending) .bgc-bubble', function (e) {
        if (COARSE.matches || (window.getSelection && String(window.getSelection()))) { return; }
        e.preventDefault(); openMenu($(this).closest('.bgc-msg').data('id'), e.clientX, e.clientY);
    });
    $(document).on('click', '.bgc-reply-btn', function (e) { e.stopPropagation(); startReply($(this).closest('.bgc-msg').data('id')); });
    $(document).on('click', '.bgc-reply-cancel', clearReply);
    $(document).on('click', '#chatThreadMessages .bgc-quote[data-jump]', function (e) { e.stopPropagation(); jumpTo($(this).data('jump')); });
    $(document).on('click', '#chatThreadMessages .bgc-msg.own:not(.pending) .bgc-ticks', function (e) {
        e.stopPropagation(); showInfo($(this).closest('.bgc-msg').data('id'));
    });

    // ---------------------------------------------------------------- events
    $(document).on('click', '#chatDrawerToggle', function (e) {
        e.preventDefault();
        if ($drawer.hasClass('open')) { closeDrawer(); } else { openDrawer(); }
    });
    $(document).on('click', '#chatDrawerCloseBtn, #chatDrawerOverlay, .bgc-thread-close', function () { closeDrawer(); });
    $(document).on('click', '.bgc-back', function () { backToList(); });
    $(document).on('keydown', function (e) {
        if (e.key !== 'Escape' || !$drawer.hasClass('open')) { return; }
        if ($('.bgc-lightbox').length) { $('.bgc-lightbox').remove(); return; }
        if ($('#chatThreadPane .bgc-sheet').length) { closeSheet($('#chatThreadPane .bgc-sheet')); return; }
        if ($('.bgc-menu').length) { closeMenu(); return; }
        if ($('#chatEmojiPanel').hasClass('open')) { togglePicker(false); return; }
        if (rec) { stopRecording(true); return; }
        if (sug.on) { hideSuggest(); return; }
        if (replyTo) { clearReply(); return; }
        closeDrawer();
    });
    $(document).on('click keydown', '#chatListItems .bgc-item', function (e) {
        if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') { return; }
        e.preventDefault();
        openThread(String($(this).data('thread')));
    });
    $(document).on('input', '#chatListSearch', renderList);
    $(document).on('change', '#chatListSort', renderList);
    $(document).on('click', '.bgc-chip', function () {
        filter = $(this).data('filter');
        $('.bgc-chip').removeClass('active'); $(this).addClass('active');
        renderList();
    });

    $(document).on('input', '#chatComposer', function () { autosize(this); updateSendButton(); updateSuggest(); });
    $(document).on('click', '#chatComposer', updateSuggest);
    $(document).on('keydown', '#chatComposer', function (e) {
        if (sug.on) {
            var $items = $('#chatMentionSuggest .item');
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                sug.idx = Math.max(0, Math.min($items.length - 1, sug.idx + (e.key === 'ArrowDown' ? 1 : -1)));
                $items.removeClass('active').eq(sug.idx).addClass('active'); return;
            }
            if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pickSuggest(sug.idx); return; }
        }
        // Enter sends on a keyboard; on a phone it is a new line and the button sends.
        if (e.key === 'Enter' && !e.shiftKey && !COARSE.matches) { e.preventDefault(); sendText(); }
    });
    $(document).on('mousedown touchstart', '#chatMentionSuggest .item', function (e) { e.preventDefault(); pickSuggest(Number($(this).data('i'))); });
    $(document).on('click', '#chatSendBtn', function () { if ($(this).hasClass('is-mic')) { startRecording(); } else { sendText(); } });
    $(document).on('click', '.bgc-rec-send', function () { stopRecording(false); });
    $(document).on('click', '.bgc-trash', function () { stopRecording(true); });
    $(document).on('click', '.bgc-attach', function () { $('#chatFileInput').val('').click(); });
    $(document).on('click', '.bgc-camera', function () { $('#chatCameraInput').val('').click(); });
    $(document).on('change', '#chatFileInput, #chatCameraInput', function () { previewPhotos(this.files); });
    $(document).on('click', '#chatDetailsBtn', function () { if (cur && cur.kind === 'sr') { window.open('/sales_request_details/' + cur.key, '_blank'); } });
    $(document).on('click', '.bgc-members-btn, .bgc-thead-main', showMembers);
    $(document).on('paste', '#chatComposer', function (e) {
        var items = (e.originalEvent.clipboardData || {}).files;
        if (items && items.length) { e.preventDefault(); previewPhotos(items); }
    });
    $(document).on('dragover', '#chatThreadPane', function (e) {
        if (!cur) { return; }
        var types = e.originalEvent.dataTransfer && e.originalEvent.dataTransfer.types;
        if (types && Array.prototype.indexOf.call(types, 'Files') >= 0) { e.preventDefault(); $('#chatThreadPane').addClass('dragging'); }
    });
    $(document).on('dragleave drop', '#chatThreadPane', function (e) {
        if (e.type === 'dragleave' && $(e.relatedTarget).closest('#chatThreadPane').length) { return; }
        $('#chatThreadPane').removeClass('dragging');
        if (e.type === 'drop' && cur) { e.preventDefault(); previewPhotos(e.originalEvent.dataTransfer.files); }
    });

    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible' && cur && $drawer.hasClass('open')) { fetchThread(true); }
    });
    PHONE.addEventListener && PHONE.addEventListener('change', fit);

    // Background badge while the drawer is shut.
    function pollBadge() { if (!$drawer.hasClass('open') && document.visibilityState !== 'hidden') { fetchChats(); } }
    $(function () {
        fetchChats();
        badgeTimer = setInterval(pollBadge, 15000);
        // Deep links: a mention notification opens ?chat=g:<room> or ?chat=sr:<id>.
        var wanted = new URLSearchParams(window.location.search).get('chat');
        if (wanted && /^(g:[a-z_]+|sr:\d+)$/.test(wanted)) {
            // Out of the address bar, so a refresh does not reopen it.
            try { var u = new URL(window.location.href); u.searchParams.delete('chat'); history.replaceState(history.state, '', u.toString()); } catch (e) { /* ignore */ }
            setTimeout(function () { openThread(wanted); }, 400);
        }
    });

    // Other pages open a request's chat directly.
    window.openChatDrawerForRequest = function (requestId) { openThread('sr:' + parseInt(requestId, 10)); };
    // A notification about a chat opens that chat where you are ('sr:12' / 'g:sales').
    window.bgOpenChat = function (thread) {
        if (!/^(g:[a-z_]+|sr:\d+)$/.test(thread || '')) { return false; }
        openThread(thread);
        return true;
    };
})(window.jQuery);
