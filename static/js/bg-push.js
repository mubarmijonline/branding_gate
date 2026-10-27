/*
 * Phone/browser push through Firebase Cloud Messaging.
 *
 * Loaded only when the server has a VAPID key (window.BG_PUSH.vapidKey). On a
 * page view it registers the service worker, asks for permission once (the
 * first time, from a user tap so browsers allow it), gets this device's token
 * and saves it under the signed-in user (/api/push/register). The server then
 * sends every bell notification to that device too.
 *
 * Firebase's web config lives in firebase-messaging-sw.js; it is repeated here
 * because a page cannot read the worker's file.
 */
(function () {
    'use strict';
    var cfg = window.BG_PUSH || {};
    var T = function (x) { return window.bgT ? window.bgT(x) : x; };
    var IOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var STANDALONE = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
    // An iPhone in a Safari tab has no web push at all: only the Home Screen
    // app does. Say so once after signing in, instead of asking for nothing.
    if (cfg.vapidKey && IOS && !STANDALONE && !('Notification' in window)) {
        if (cfg.afterLogin && window.Swal) {
            setTimeout(function () {
                Swal.fire({ icon: 'info', title: T('Get notifications on your iPhone'),
                    html: T('Tap the Share button, then "Add to Home Screen". Open Branding Gate from that icon and allow notifications.'),
                    confirmButtonText: T('OK') });
            }, 1200);
        }
        return;
    }
    if (!cfg.vapidKey || !('serviceWorker' in navigator) || !('Notification' in window)) return;
    if (!window.firebase || !firebase.messaging) return;

    var FIREBASE = {
        apiKey: 'AIzaSyDzIyVDGUqXre9oJmctzzOX0Zqw2NihW6I',
        authDomain: 'brandinggate-7c1f6.firebaseapp.com',
        projectId: 'brandinggate-7c1f6',
        messagingSenderId: '938997040582',
        appId: '1:938997040582:web:a7e4963b85fbafb71b5ec7'
    };
    var KEY = 'bg.push.token';

    function app() {
        if (!firebase.apps.length) firebase.initializeApp(FIREBASE);
        return firebase.messaging();
    }

    function save(token) {
        if (!token || localStorage.getItem(KEY) === token) return;
        fetch('/api/push/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: token }) })
            .then(function (r) { if (r.ok) try { localStorage.setItem(KEY, token); } catch (e) {} });
    }

    // Firebase's getToken waits forever on a worker that is still installing
    // (the very first visit), with no error -- so wait for it to be active.
    function activated(reg) {
        if (reg.active) return Promise.resolve(reg);
        var sw = reg.installing || reg.waiting;
        if (!sw) return navigator.serviceWorker.ready;
        return new Promise(function (resolve) {
            sw.addEventListener('statechange', function () { if (sw.state === 'activated') resolve(reg); });
        });
    }

    function enable() {
        return navigator.serviceWorker.register('/firebase-messaging-sw.js').then(activated).then(function (reg) {
            return app().getToken({ vapidKey: cfg.vapidKey, serviceWorkerRegistration: reg });
        }).then(save).catch(function (e) { console.warn('push:', e && e.message ? e.message : e); });
    }

    function foreground() {
        app().onMessage(function (payload) {
            // In the foreground the bell updates itself; a toast is enough.
            var n = payload.notification || payload.data || {};
            if (window.Swal) Swal.fire({ toast: true, position: 'top', timer: 4000, showConfirmButton: false, icon: 'info',
                title: n.title || 'Notification', text: n.body || '' });
            // Repaint the bell (and its chime) now rather than at the next poll.
            if (typeof refreshNotifications === 'function') refreshNotifications();
        });
    }

    // Already allowed: refresh the token quietly on each visit (they rotate).
    if (Notification.permission === 'granted') {
        enable();
        foreground();
        return;
    }
    if (Notification.permission === 'denied') return;

    // Not decided yet: ask on the first tap on the bell or the Alerts tab,
    // never on page load.
    function askOnce() {
        document.removeEventListener('click', onTap, true);
        Notification.requestPermission().then(function (p) {
            if (p === 'granted') {
                enable(); foreground();
                if (window.Swal) Swal.fire({ toast: true, position: 'top', timer: 3000, showConfirmButton: false, icon: 'success',
                                             title: T('Notifications are on for this device') });
            }
        });
    }
    function onTap(e) {
        if (e.target.closest('#notificationDropdown, [data-bgm-action="notifications"], #bgPushEnable')) askOnce();
    }
    document.addEventListener('click', onTap, true);
    window.bgEnablePush = askOnce;

    // Asked straight after signing in, and again every 3 days after "Not now"
    // until the person decides. A card, not the browser prompt itself:
    // browsers (iPhones above all) only show that from a tap.
    var SNOOZE = 'bg.push.snoozeUntil';
    var snoozed = false;
    try { snoozed = Number(localStorage.getItem(SNOOZE) || 0) > Date.now(); } catch (e) { /* ignore */ }
    if ((cfg.afterLogin || !snoozed) && window.Swal) {
        setTimeout(function () {
            if (Notification.permission !== 'default' || (Swal.isVisible && Swal.isVisible())) return;
            Swal.fire({
                icon: 'question', iconHtml: '<i class="fas fa-bell"></i>',
                title: T('Turn on notifications'),
                html: T('Approvals, @mentions and important updates will reach this device, even when Branding Gate is closed.'),
                showCancelButton: true, confirmButtonText: T('Allow'), cancelButtonText: T('Not now'),
                confirmButtonColor: '#224abe', reverseButtons: true
            }).then(function (r) {
                if (r.isConfirmed) { askOnce(); return; }
                try { localStorage.setItem(SNOOZE, String(Date.now() + 3 * 86400000)); } catch (e) { /* ignore */ }
            });
        }, 1500);
    }
})();
