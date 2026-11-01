"""Auto refresh for the published pages (display only; the card's numbers, plays and logs are untouched).

Each page carries its build time in <meta name="otg-built">. While the page is on screen, a small script fetches the
page again every 3 minutes, a few seconds after it opens, and whenever the tab or phone app comes back into view. If
the published copy is newer, the page reloads in place: same scroll position, and on the card the same odds-board tab
and "Plays only" setting (the play sort is already remembered). It never reloads while someone is typing, and if a
reload lands on an older copy (a cache serving behind), it waits 10 minutes before trying that build again.
"""
from __future__ import annotations

import html

import pandas as pd

EVERY_MS = 180_000


def stamp(at: pd.Timestamp | None = None) -> str:
    return (at or pd.Timestamp.now(tz="UTC")).tz_convert("UTC").isoformat(timespec="seconds")


def meta(built: str) -> str:
    return f'<meta name="otg-built" content="{html.escape(built)}">'


# Page hooks (optional): window.otgState() returns what to keep across the reload; window.otgRestore(state) puts it back.
SCRIPT = r"""<script>
(() => {
  const el = document.querySelector('meta[name="otg-built"]');
  if (!el || !window.fetch) return;
  const built = new Date(el.content), path = location.pathname, KEY = "otg-keep:" + path, EVERY = __EVERY__;
  let waitUntil = 0, busy = false;
  // a reload this script started: drop the cache-busting query, put the page back the way it was
  try {
    const k = JSON.parse(sessionStorage.getItem(KEY) || "null");
    sessionStorage.removeItem(KEY);
    if (/[?&]t=\d+/.test(location.search)) history.replaceState(null, "", path + location.hash);
    if (k) {
      if (k.want && built < new Date(k.want)) waitUntil = Date.now() + 600000;   // landed on an older copy: back off
      if (k.state && window.otgRestore) { try { window.otgRestore(k.state); } catch (e) {} }
      let moved = false;
      const mark = () => { moved = true; };
      ["wheel", "touchstart", "keydown"].forEach((ev) => addEventListener(ev, mark, {once: true, passive: true}));
      const put = () => { if (!moved) scrollTo(0, k.y || 0); };
      requestAnimationFrame(put);
      addEventListener("load", put, {once: true});
      setTimeout(put, 800);
    }
  } catch (e) {}
  const typing = () => { const a = document.activeElement;
    return a && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && /^(text|search|number|email|password)$/.test(a.type))); };
  const check = async () => {
    if (busy || document.hidden || Date.now() < waitUntil) return;
    busy = true;
    try {
      const r = await fetch(path + "?fresh=" + Date.now(), {cache: "no-store"});
      const m = r.ok ? (await r.text()).match(/<meta name="otg-built" content="([^"]+)">/) : null;
      if (m && new Date(m[1]) > built && !typing()) {
        let state = null;
        try { state = window.otgState ? window.otgState() : null; } catch (e) {}
        try { sessionStorage.setItem(KEY, JSON.stringify({y: scrollY, want: m[1], state})); } catch (e) {}
        location.replace(path + "?t=" + Date.now() + location.hash);
        return;
      }
    } catch (e) {}
    busy = false;
  };
  setTimeout(check, 3000);
  setInterval(check, EVERY);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
  addEventListener("pageshow", (e) => { if (e.persisted) check(); });
  addEventListener("online", check);
})();
</script>
""".replace("__EVERY__", str(EVERY_MS))
