/* Гид паломника JURT — офлайн-кэш. Версия меняется автоматически при каждой сборке. */
var CACHE = 'jurt-umra-da5d5ce263';
var ASSETS = ['./', 'index.html', 'manifest.webmanifest', 'amiri-400.woff2',
  'exo2-regular.woff2', 'exo2-semibold.woff2', 'exo2-bold.woff2', 'logo-white.svg', 'umra.ics',
  'icon-mark.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png',
  'haram3d/', 'haram3d/bg.webp', 'haram3d/haram.glb', 'haram3d/haram_city.glb', 'haram3d/vendor/draco/draco_decoder.wasm', 'haram3d/vendor/draco/draco_wasm_wrapper.js', 'haram3d/vendor/three/addons/loaders/DRACOLoader.js', 'haram3d/haram_meta.json', 'haram3d/walk_route.json', 'haram3d/index.html', 'haram3d/poster.webp', 'haram3d/vendor/three/addons/controls/OrbitControls.js', 'haram3d/vendor/three/addons/environments/RoomEnvironment.js', 'haram3d/vendor/three/addons/loaders/GLTFLoader.js', 'haram3d/vendor/three/addons/utils/BufferGeometryUtils.js', 'haram3d/vendor/three/three.module.min.js'];  // 3D-сцена Харама — тоже офлайн

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
  if (req.mode === 'navigate' && !/^\/(program|admin|haram3d)(\/|$)/.test(new URL(req.url).pathname)) {  // /program/, /admin/, /haram3d/ — отдельные страницы, не приложение
    e.respondWith(caches.match('index.html').then(function (r) { return r || fetch(req); }));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(function (r) { return r || fetch(req); }));
});
