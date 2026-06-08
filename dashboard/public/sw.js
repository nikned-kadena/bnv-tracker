const CACHE = "bnv-v1";
const DATA_URLS = [
  "https://raw.githubusercontent.com/USERNAME/bnv-tracker/main/data/latest.json",
  "https://raw.githubusercontent.com/USERNAME/bnv-tracker/main/data/history.json",
];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(["/"])));
  self.skipWaiting();
});
self.addEventListener("fetch", e => {
  const url = e.request.url;
  // Data files: network first, cache fallback
  if (DATA_URLS.some(u => url.includes("latest.json") || url.includes("history.json"))) {
    e.respondWith(
      fetch(e.request)
        .then(r => { const c = r.clone(); caches.open(CACHE).then(cache => cache.put(e.request, c)); return r; })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  // App shell: cache first
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
