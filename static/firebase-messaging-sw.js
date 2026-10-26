



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
messaging.onBackgroundMessage(payload => {
  const n = payload.notification || {};
  const link = (payload.data && payload.data.link) || (payload.fcmOptions && payload.fcmOptions.link) || '/notifications';
  self.registration.showNotification(n.title || 'Branding Gate', {
    body: n.body || '', icon: '/static/img/icons/icon-192.png', badge: '/static/img/icons/icon-192.png',
    data: { link: link }, tag: link
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