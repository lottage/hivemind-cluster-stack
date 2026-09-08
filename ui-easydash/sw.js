// EasyDash Service Worker v1.0
// Enables PWA installation, offline asset caching, and mobile notifications across Tailscale

const CACHE_NAME = 'easydash-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icon.svg',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('[SW] Caching failed during install:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        kYOUR_LONG_LIVED_TOKEN_HERE((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }
  const url = new URL(event.request.url);

  // Never cache API calls or streaming endpoints
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/sse')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => caches.match(event.request))
  );
});

// Handle Background Push Notifications
self.addEventListener('push', (event) => {
  let data = { title: 'EasyDash Homelab Alert', body: 'New notification from cluster', icon: '/icon-192.png' };
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    if (event.data) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body || 'Task completed successfully',
    icon: data.icon || '/icon-192.png',
    badge: '/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Handle Client Messages (e.g. Test Alert or local push dispatches from UI)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'PUSH_NOTIF') {
    const payload = event.data.payload || {};
    const title = payload.title || 'EasyDash Alert';
    const opts = payload.options || {
      body: 'Proxmox dual-GPU cluster & Home Assistant are operational!',
      icon: '/icon-192.png',
      badge: '/icon-192.png'
    };
    event.waitUntil(
      self.registration.showNotification(title, opts)
    );
  }
});

// Click on Notification opens or focuses the EasyDash tab
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
