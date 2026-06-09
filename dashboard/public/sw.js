const CACHE = "bnv-v1";
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(["/"])));
  self.skipWaiting();
});
self.addEventListener("fetch", e => {
  const url = e.request.url;
  if (url.includes("latest.json") || url.includes("history.json")) {
    e.respondWith(
      fetch(e.request)
        .then(r => { const c = r.clone(); caches.open(CACHE).then(cache => cache.put(e.request, c)); return r; })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
