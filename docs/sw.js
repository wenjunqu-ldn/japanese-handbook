/* Service worker for the daily exercise app.
 *
 * Two caching strategies, because the two kinds of file behave differently:
 *
 *   app shell (html/js/css/icons)  cache-first, refreshed in the background
 *   exercise data (data/*.json)    network-first, falling back to cache
 *
 * Data must be network-first or a cached copy of index.json would hide the day
 * the workflow just generated. The shell can be cache-first because it changes
 * rarely and a version bump replaces it wholesale.
 */

const VERSION = "v1";
const SHELL_CACHE = `jp-shell-${VERSION}`;
const DATA_CACHE = `jp-data-${VERSION}`;

const SHELL_ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./style.css",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // Individual failures must not abort the install, or one missing file
      // leaves the app permanently uninstallable offline.
      .then((cache) => Promise.allSettled(SHELL_ASSETS.map((a) => cache.add(a))))
      .then(warmLatestData)
      .then(() => self.skipWaiting())
  );
});

/* On the first visit the worker is not yet controlling the page, so that day's
 * exercises never pass through fetch and would not be cached. Installing then
 * immediately going offline is an ordinary thing to do on a phone, so the
 * newest day is fetched here explicitly. */
async function warmLatestData() {
  try {
    const cache = await caches.open(DATA_CACHE);
    const indexUrl = "./data/index.json";
    const indexRes = await fetch(indexUrl, { cache: "no-store" });
    if (!indexRes.ok) return;
    await cache.put(indexUrl, indexRes.clone());

    const index = await indexRes.json();
    if (!index.latest) return;
    const dayUrl = `./data/exercises/${index.latest}.json`;
    const dayRes = await fetch(dayUrl, { cache: "no-store" });
    if (dayRes.ok) await cache.put(dayUrl, dayRes);
  } catch (err) {
    /* warming is best effort; the app still works online */
  }
}

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n !== SHELL_CACHE && n !== DATA_CACHE)
            .map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.includes("/data/")) {
    event.respondWith(networkFirst(request));
  } else {
    event.respondWith(cacheFirst(request));
  }
});

async function networkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    // Offline with nothing cached for this exact URL. The app asks for a
    // specific date, so report it cleanly rather than throwing.
    return new Response(JSON.stringify({ offline: true }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) {
    // Refresh in the background so the next launch has the newer file.
    fetch(request)
      .then((response) => {
        if (response && response.ok) cache.put(request, response.clone());
      })
      .catch(() => {});
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const fallback = await cache.match("./index.html");
    if (fallback && request.mode === "navigate") return fallback;
    throw err;
  }
}
