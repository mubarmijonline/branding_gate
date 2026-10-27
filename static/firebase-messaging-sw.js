



importScripts(
  'https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js',
  'https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js'
);

firebase.initializeApp({
  apiKey:           "AIzaSyDzIyVDGUqXre9oJmctzzOX0Zqw2NihW6I",               // same config
  authDomain:       "brandinggate-7c1f6.firebaseapp.com",
  projectId:        "brandinggate-7c1f6",
  messagingSenderId:"938997040582",
  appId:            "1:938997040582:web:a7e4963b85fbafb71b5ec7"
});
const messaging = firebase.messaging();
// Background: show it with the app icon; a tap opens the page the
// notification is about (data.link), focusing the app if it is already open.
// The server sends data only (title, body, link), so this is the one place a
// push becomes a notification: never two copies. Same link, same tag, so a
// busy chat replaces its notification instead of stacking them.
messaging.onBackgroundMessage(payload => {
  const d = payload.data || {}, n = payload.notification || {};
  const link = d.link || '/notifications';
  // The home-screen icon's badge: the unread Important count the server sent.
  if (d.badge !== undefined && self.navigator.setAppBadge) {
    const n = parseInt(d.badge, 10) || 0;
    (n ? self.navigator.setAppBadge(n) : self.navigator.clearAppBadge()).catch(() => {});
  }
  return self.registration.showNotification(d.title || n.title || 'Branding Gate', {
    body: d.body || n.body || '', icon: '/static/img/icons/icon-192.png', badge: '/static/img/icons/icon-192.png',
    data: { link: link }, tag: link, renotify: true
  });
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || '/notifications';
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) { c.navigate(link); return c.focus(); } }
    return clients.openWindow(link);
  }));
});