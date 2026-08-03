



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
messaging.onBackgroundMessage(payload => {
  console.log('[SW] Background message:', payload);
  const { title = 'Notification', body = '' } = payload.notification || payload.data || {};
  self.registration.showNotification(title, { body });
});