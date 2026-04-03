// CardioLog Service Worker v1.0
const CACHE_NAME = 'cardiolog-v1';
const OFFLINE_URLS = ['/', '/index.html'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(OFFLINE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // CDN resources: network first, cache fallback
  if (e.request.url.includes('googleapis') || e.request.url.includes('unpkg') ||
      e.request.url.includes('jsdelivr') || e.request.url.includes('cdnjs')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }
  // App shell: cache first
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      if (wins.length > 0) {
        wins[0].focus();
        wins[0].postMessage({ type: 'NOTIFICATION_CLICK', data: e.notification.data });
      } else {
        clients.openWindow('/');
      }
    })
  );
});

// Handle scheduled notification triggers from the app
self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'SCHEDULE_NOTIFICATION') {
    const { title, body, tag, delay, data } = e.data;
    setTimeout(() => {
      self.registration.showNotification(title, {
        body,
        tag,
        icon: '/icon-192.png',
        badge: '/badge-72.png',
        data: data || {},
        vibrate: [200, 100, 200],
        requireInteraction: false,
      });
    }, delay);
  }
});
