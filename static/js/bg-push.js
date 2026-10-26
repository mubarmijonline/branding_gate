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

    function enable() {
        return navigator.serviceWorker.register('/firebase-messaging-sw.js').then(function (reg) {
            return app().getToken({ vapidKey: cfg.vapidKey, serviceWorkerRegistration: reg });
        }).then(save).catch(function (e) { console.warn('push:', e && e.message ? e.message : e); });
    }

    // Already allowed: refresh the token quietly on each visit (they rotate).
    if (Notification.permission === 'granted') {
        enable();
        app().onMessage(function (payload) {
            // In the foreground the bell updates itself; a toast is enough.
            var n = payload.notification || payload.data || {};
            if (window.Swal) Swal.fire({ toast: true, position: 'top', timer: 4000, showConfirmButton: false, icon: 'info',
                title: n.title || 'Notification', text: n.body || '' });
            if (typeof fetchNotifications === 'function') fetchNotifications();
        });
        return;
    }
    if (Notification.permission === 'denied') return;

    // Not decided yet: ask on the first tap on the bell or the Alerts tab,
    // never on page load.
    function askOnce() {
        document.removeEventListener('click', onTap, true);
        Notification.requestPermission().then(function (p) { if (p === 'granted') enable(); });
    }
    function onTap(e) {
        if (e.target.closest('#notificationDropdown, [data-bgm-action="notifications"], #bgPushEnable')) askOnce();
    }
    document.addEventListener('click', onTap, true);
    window.bgEnablePush = askOnce;
})();
