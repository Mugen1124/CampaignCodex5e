// The DM site online: the built DM pages (./site), plus a private line to the players' site's worker (the
// BRAIN service binding, its Inside entrance), which keeps everything live - the Party page's cards, current HP,
// the treasury, the tracker, item claims. Only the DM can open this site (Cloudflare Access), so everything that
// goes down that line is the DM.
//
//   /api/...           -> the players' worker, as the DM: the live Party page, History and Undo, the treasury,
//                         sharing the initiative tracker - online, without CampaignCodex5e running at home
//   /as/<who>/...      -> "View as…": the players' site exactly as one player sees it (<who> is their card's id,
//                         or "players" for any player), with a banner. Changes made there are made as that player,
//                         and their card's history says it was the DM. A player's private notes stay closed.
//
// The players never see any of this: it's not on their site, and their worker only takes "view as" from here.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (path.startsWith("/api/")) return toBrain(request, env, path, "dm");
    const m = path.match(/^\/as\/([a-z0-9-]+)(\/.*)?$/);
    if (m) {
      const who = m[1], rest = m[2] || "/";
      if (!m[2]) return Response.redirect(new URL(`/as/${who}/`, url).toString(), 302);
      if (!env.BRAIN) return Response.redirect(new URL("/", url).toString(), 302);   // no players' site
      const res = await toBrain(request, env, rest, who);
      const to = res.headers.get("Location");
      if (to && res.status >= 300 && res.status < 400) {   // e.g. /party -> /party/: stay inside "View as"
        const target = new URL(to, "https://players" + rest);
        return Response.redirect(new URL(`/as/${who}${target.pathname}${target.search}`, url).toString(), res.status === 301 ? 301 : 302);
      }
      if (res.status === 404 && !rest.startsWith("/api/") && request.method === "GET") {
        // A DM-only page (View as… opens the page you're on): their home page instead.
        return Response.redirect(new URL(`/as/${who}/`, url).toString(), 302);
      }
      const type = res.headers.get("Content-Type") || "";
      return type.includes("text/html") ? viewAs(res, who, rest) : res;
    }
    return env.ASSETS.fetch(request);
  },
};

function toBrain(request, env, path, as) {
  if (!env.BRAIN) return new Response(JSON.stringify({ error: "This campaign has no players' site." }),
    { status: 404, headers: { "Content-Type": "application/json" } });
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  headers.set("X-Codex-As", as);
  headers.delete("If-None-Match");   // pages seen "as" someone are rebuilt every time (see viewAs)
  headers.delete("If-Modified-Since");
  return env.BRAIN.fetch(new Request("https://players" + path + url.search, {
    method: request.method, headers, body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
  }));
}

// A players' page, seen as one player: its live features talk to /as/<who>/api/... (so the players' worker
// answers as that player), and a banner says whose eyes these are.
function viewAs(res, who, rest) {
  const base = `/as/${who}`;
  const label = who === "players" ? "a player" : who.replace(/^pc-/, "").replace(/-/g, " ");
  const shim = `<script>(function(){var B=${JSON.stringify(base)};var F=window.fetch;window.fetch=function(u,o){` +
    `if(typeof u==="string"&&u.indexOf("/api/")===0)u=B+u;return F.call(this,u,o);};var W=window.WebSocket;` +
    `function S(u,p){u=String(u).replace(/^(wss?:\\/\\/[^\\/]+)\\/api\\//,"$1"+B+"/api/");return p===undefined?new W(u):new W(u,p);}` +
    `S.prototype=W.prototype;S.CONNECTING=0;S.OPEN=1;S.CLOSING=2;S.CLOSED=3;window.WebSocket=S;window.CODEX_VIEW_AS=${JSON.stringify(who)};` +
    // The banner gets the character's own name once the page is up.
    `document.addEventListener("DOMContentLoaded",function(){window.fetch("/api/me").then(function(r){return r.json();})` +
    `.then(function(m){var e=document.querySelector("[data-viewas-name]");if(e&&m&&m.character)e.textContent=m.character;})` +
    `.catch(function(){});});})();</script>`;
  const banner = `<div class="codex-viewas" style="position:sticky;top:0;z-index:1000;background:#7a3e00;color:#fff;` +
    `font:600 14px/1.4 system-ui,sans-serif;padding:7px 14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">` +
    `<span>Viewing the players' site as <span data-viewas-name>${escapeHtml(label)}</span> — anything you change is saved as them.</span>` +
    `<a href="${escapeHtml(rest)}" style="color:#fff;text-decoration:underline;margin-left:auto">Back to the DM site</a></div>`;
  const page = new Response(res.body, res);
  page.headers.set("Cache-Control", "no-store");   // never a stale banner or shim after an update
  page.headers.delete("ETag");
  return new HTMLRewriter()
    .on("head", { element(e) { e.prepend(shim, { html: true }); } })
    .on("body", { element(e) { e.prepend(banner, { html: true }); } })
    .transform(page);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
