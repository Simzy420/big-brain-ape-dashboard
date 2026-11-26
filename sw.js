/* Sims Construction push notifications. v61 */
self.addEventListener('install', function () {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (err) {
    data = { title: 'Sims Construction', body: event.data ? event.data.text() : 'Work order reminder' };
  }
  var title = data.title || 'Sims Construction';
  var options = {
    body: data.body || 'Work order reminder',
    icon: 'icons/icon-192.png',
    badge: 'icons/icon-192.png',
    vibrate: [200, 100, 200, 100, 200],
    silent: false,
    tag: data.tag || 'wo-push',
    renotify: true,
    data: { url: data.url || 'corrigo-app.html' }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var target = (event.notification.data && event.notification.data.url) || 'corrigo-app.html';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      var client = list[i];
      if (client.url.indexOf('corrigo-app.html') !== -1 && client.navigate) {
        return client.navigate(target).then(function (next) {
          return (next || client).focus();
        });
      }
    }
    if (self.clients.openWindow) return self.clients.openWindow(target);
  }));
});
