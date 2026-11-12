// Arvio XMLTV gzip cache-control proxy for Cloudflare Workers.
// Deploy and configure Arvio to use https://YOUR-WORKER-DOMAIN/epg.xml.gz
const ORIGIN = "https://raw.githubusercontent.com/lynseynunez/Arvio-Playlist/main/epg.xml.gz";
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== "/epg.xml.gz") return new Response("Not found", { status: 404 });
    if (!["GET", "HEAD"].includes(request.method)) return new Response("Method not allowed", { status: 405 });
    const version = Math.floor(Date.now() / 3600000);
    const upstream = await fetch(ORIGIN + "?v=" + version, {
      cf: { cacheTtl: 0, cacheEverything: false },
    });
    if (!upstream.ok) return new Response("EPG upstream unavailable", {
      status: 502, headers: { "Cache-Control": "no-store" },
    });
    const headers = new Headers({
      "Content-Type": "application/gzip",
      "Content-Disposition": 'inline; filename="epg.xml.gz"',
      "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      "Pragma": "no-cache",
      "Expires": "0",
      "Access-Control-Allow-Origin": "*",
    });
    // Stream gzip bytes without re-encoding or changing playlist streams.
    return new Response(request.method === "HEAD" ? null : upstream.body, {
      status: 200, headers,
    });
  },
};
