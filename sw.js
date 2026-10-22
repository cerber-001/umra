/* Гид паломника JURT — офлайн-кэш. Версия меняется автоматически при каждой сборке. */
var CACHE = 'jurt-umra-e8ea3ed54f';
var ASSETS = ['./', 'index.html', 'manifest.webmanifest', 'amiri-400.woff2',
  'exo2-regular.woff2', 'exo2-semibold.woff2', 'exo2-bold.woff2', 'logo-white.svg', 'umra.ics',
  'icon-mark.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll(ASSETS.map(function (u) { return new Request(u, { cache: 'reload' }); }));
  }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('jurt-umra-') === 0 && k !== CACHE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('message', function (e) { if (e.data === 'skip') self.skipWaiting(); });

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  if (req.mode === 'navigate' && !/^\/(program|admin)(\/|$)/.test(new URL(req.url).pathname)) {  // /program/ и /admin/ — отдельные страницы, не приложение
    e.respondWith(caches.match('index.html').then(function (r) { return r || fetch(req); }));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(function (r) { return r || fetch(req); }));
});
