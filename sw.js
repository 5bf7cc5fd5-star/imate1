const CACHE = "ownclub-v3-fullscreen";
const ASSETS = ["/", "/manifest.json", "/static/fullscreen.css"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws")) return;
  e.respondWith((async () => {
    const res = await fetch(e.request).catch(() => caches.match(e.request));
    if (!res) return res;
    const type = res.headers.get("content-type") || "";
    if (type.includes("text/html")) {
      let html = await res.text();
      if (!html.includes("fullscreen.css")) {
        html = html.replace("</head>", '<link rel="stylesheet" href="/static/fullscreen.css"></head>');
      }
      return new Response(html, { status: res.status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
    }
    return res;
  })());
});
