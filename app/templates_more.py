"""Šablony 3–5: Vizitka, Pop, Luxus.

Sdílejí data i pomocné funkce se šablonami 1–2 (app/sites.py), liší se jen vykreslením.
CSS je v obyčejných řetězcích (bez f-stringu), proměnné se předávají přes :root.
"""
import html
import re

from . import sites
from .sites import (TYPES, WEIGHTS, _count, _cz, _font_links, _font_ok, _fmt, _hours_ld, _rating, _stars, _yt,
                    brand_files, e, icon_svg, js, rich, RATING_LABEL)

# výchozí písma jednotlivých šablon (uživatel je může přepsat v editoru)
TPL_FONTS = {
    "3": None,  # vizitka – písma podle typu provozovny
    "4": {"display": "Bricolage Grotesque", "display_w": "800", "body": "Figtree"},
    "5": {"display": "Figtree", "display_w": "700", "body": "Figtree"},
    "6": {"display": "Archivo Black", "display_w": "400", "body": "Figtree"},
    "7": {"display": "Crimson Pro", "display_w": "600", "body": "PT Sans"},
}


def _hi(text):
    """**slovo** v nadpisu → zvýrazněný štítek (šablona Pop)."""
    s = e(text)
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="hl">\1</span>', s)


def _fit(text, m_max, d_max, ratio, m_w=88, d_w=58, m_lines=4, d_lines=3):
    """Velikost nadpisu podle délky textu: nejdelší slovo se musí vejít na řádek a celý nadpis do pár řádků.
    Vrací CSS proměnné --fm (mobil) a --fd (desktop) ve vw."""
    t = re.sub(r"[*][*]", "", text or "").strip() or "x"
    longest = max(len(w) for w in t.split())
    n = len(t)
    fm = min(m_max, m_w / (longest * ratio), m_w * m_lines / (n * ratio * 1.08))
    fd = min(d_max, d_w / (longest * ratio), d_w * d_lines / (n * ratio * 1.08))
    return f"--fm:{fm:.2f}vw;--fd:{fd:.2f}vw"


def _wh(d, name):
    """width/height z naměřených rozměrů – prohlížeč zná poměr stran dřív, než se fotka stáhne (masonry neposkakuje)."""
    q = (d.get("images") or {}).get(name) or {}
    return f' width="{int(q["w"])}" height="{int(q["h"])}"' if q.get("w") and q.get("h") else ""


def _rows(d, name):
    """Mozaika pracuje se 4 formáty: 4:5 a 1:1, každý v základní (velké) a poloviční velikosti.
    Poloviční dlaždice = 1 sloupec a 5 (4:5) nebo 4 (1:1) řádky po čtvrtině šířky sloupce; velká má vše dvojnásobné."""
    return 4 if _fmt(d, name) == "sq" else 5


def _plain(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")


def _open_time(hours):
    """Nejdřívější čas otevření v týdnu, např. „7:00“."""
    best = None
    for h in hours or []:
        m = re.search(r"(\d{1,2})[:.](\d{2})\s*[–-]", h.get("value") or "")
        if m:
            t = int(m.group(1)) * 60 + int(m.group(2))
            if best is None or t < best:
                best = t
    return None if best is None else f"{best // 60}:{best % 60:02d}"


def _ctx(d, tpl):
    """Vše, co šablony potřebují, spočítané jednou."""
    kind = d["type"] if d.get("type") in TYPES else "kadernictvi"
    t = TYPES[kind]
    theme = dict(t["theme"])
    th = d.get("theme") or {}
    if re.fullmatch(r"#[0-9a-fA-F]{6}", th.get("accent") or ""):
        theme["accent"] = th["accent"]
    f = dict(TPL_FONTS.get(tpl) or t["fonts"])
    if _font_ok(th.get("font_display")):
        f["display"] = th["font_display"].strip()
        f["display_w"] = th.get("font_display_w") if str(th.get("font_display_w") or "") in WEIGHTS else "400"
    elif str(th.get("font_display_w") or "") in WEIGHTS:
        f["display_w"] = th["font_display_w"]
    if _font_ok(th.get("font_body")):
        f["body"] = th["font_body"].strip()
    dw = f["display_w"].split(";")[-1]

    c = d.get("contact") or {}
    name = d.get("name") or (d.get("logo") or {}).get("text") or ""
    tel = re.sub(r"[^\d+]", "", c.get("phone") or "")
    maps = (f"https://www.google.com/maps/search/?api=1&query={c['lat']},{c['lon']}" if c.get("lat")
            else f"https://www.google.com/maps/search/?api=1&query={html.escape(c.get('address') or name)}")
    hero = d.get("hero") or {}
    hero_img = f"img/{hero['image']}" if hero.get("image") else ""
    gallery = [g for g in d.get("gallery") or [] if g.get("file")]
    usps = [u for u in d.get("usps") or [] if (u.get("title") or "").strip()]
    offer = [o for o in d.get("offer") or [] if (o.get("name") or "").strip()]
    reviews = [r for r in d.get("reviews") or [] if (r.get("text") or "").strip() and r.get("consent")]
    groups = []
    for o in offer:
        g = (o.get("group") or "").strip()
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append(o)

    brands = brand_files()
    ratings = []
    for key in ("google", "facebook"):
        r = (d.get("ratings") or {}).get(key) or {}
        rv = _rating(r)
        if rv:
            url = r.get("url") if (r.get("url") or "").startswith("http") else (d.get("reviews_link") if key == "google" else "")
            ratings.append({"key": key, "label": RATING_LABEL[key], "value": rv[0], "count": rv[1], "url": url or "",
                            "logo": brands.get(key)})
    socials = [(lbl, (d.get("social") or {}).get(k)) for k, lbl in
               (("facebook", "Facebook"), ("instagram", "Instagram"), ("tiktok", "TikTok"))]
    socials = [(lbl, u) for lbl, u in socials if (u or "").startswith("http")]

    ld = {"@context": "https://schema.org", "@type": t["schema"], "name": name,
          "address": c.get("address"), "telephone": c.get("phone") or None, "email": c.get("email") or None,
          "image": hero_img or None, "url": f"https://{d['domain']}/" if d.get("domain") else None,
          "openingHours": _hours_ld(d.get("hours") or []) or None}
    if c.get("lat"):
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": c["lat"], "longitude": c["lon"]}
    ld = {k: v for k, v in ld.items() if v}

    map_html = ""
    if c.get("lat"):
        lat, lon = float(c["lat"]), float(c["lon"])
        bbox = f"{lon - 0.006},{lat - 0.0035},{lon + 0.006},{lat + 0.0035}"
        map_html = (f'<iframe class="map" title="Mapa – {e(name)}" loading="lazy" '
                    f'src="https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={lat},{lon}"></iframe>')

    hero_video = hero.get("video") or ""
    video_tag = ""
    if re.fullmatch(r"[0-9a-f]{10}\.(mp4|webm)", hero_video):
        vtype = "video/mp4" if hero_video.endswith("mp4") else "video/webm"
        video_tag = (f'<video class="hv" id="hero-video" autoplay muted loop playsinline preload="metadata"'
                     + (f' poster="{e(hero_img)}"' if hero_img else "") + f' aria-label="{e(hero.get("alt") or name)}">'
                     f'<source src="img/{hero_video}" type="{vtype}"></video>')

    return dict(t=t, kind=kind, theme=theme, f=f, dw=dw, c=c, name=name, tel=tel, maps=maps, hero=hero,
                hero_img=hero_img, gallery=gallery, usps=usps, offer=offer, groups=groups, reviews=reviews,
                ratings=ratings, socials=socials, ld=ld, map_html=map_html, video_tag=video_tag,
                icon=(d.get("logo") or {}).get("icon") or t["icon"],
                logo_text=(d.get("logo") or {}).get("text") or name,
                hours=d.get("hours") or [], yt=_yt(d.get("video")))


def _brand(r, h=16, cls="blogo"):
    return f'<img class="{cls}" src="img/{r["logo"]}" alt="{e(r["label"])}" height="{h}">' if r["logo"] else e(r["label"])


def _head(d, x, extra_fonts=()):
    seo = d.get("seo") or {}
    f = x["f"]
    links = _font_links(f["display"], sorted({"400", x["dw"]})) + _font_links(f["body"], ["400", "500", "600", "700"])
    for fam, ws in extra_fonts:
        links += _font_links(fam, ws)
    return f'''<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(seo.get("title") or x["name"])}</title>
<meta name="description" content="{e(seo.get("description"))}">
<meta property="og:title" content="{e(seo.get("title") or x["name"])}">
<meta property="og:description" content="{e(seo.get("description"))}">
{f'<meta property="og:image" content="{e(x["hero_img"])}">' if x["hero_img"] else ""}
{f'<link rel="canonical" href="https://{e(d["domain"])}/">' if d.get("domain") else ""}
<link rel="icon" href="logo-icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{links}<script type="application/ld+json">{js(x["ld"])}</script>
'''


def _root(x, extra=""):
    th, f = x["theme"], x["f"]
    return (f':root {{ --bg:{th["bg"]}; --surface:{th["surface"]}; --ink:{th["ink"]}; --muted:{th["muted"]}; '
            f'--accent:{th["accent"]}; --accent2:{th["accent2"]}; --display:"{f["display"]}", system-ui, sans-serif; '
            f'--body:"{f["body"]}", system-ui, sans-serif; --dw:{x["dw"]}; {extra} }}')


def _hours_rows(x, short=False):
    return "".join(f'<tr data-d="{i}"><th>{e(h.get("day"))}</th><td>{e(h.get("value") or "–")}</td></tr>'
                   for i, h in enumerate(x["hours"]))


def _lightbox(gallery):
    if not gallery:
        return ""
    return ('<dialog class="lightbox" aria-label="Galerie"><div class="lb-track">' + "".join(
        f'<figure><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy"><figcaption>{e(g.get("alt"))}</figcaption></figure>'
        for g in gallery) + '</div><button class="lb-close" aria-label="Zavřít">×</button></dialog>')


COMMON_CSS = """
* { box-sizing:border-box; }
html { scroll-behavior:smooth; scroll-padding-top:70px; }
img { display:block; max-width:100%; }
a { color:inherit; }
:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.preview-bar { position:relative; z-index:60; background:#000; color:#fff; font:13px var(--body); text-align:center; padding:6px 10px; }
.stars { position:relative; display:inline-block; width:var(--w); height:var(--h); flex:none; vertical-align:middle; }
.stars svg { display:block; }
.stars .s-bg { fill:currentColor; opacity:.25; }
.stars .s-fg { position:absolute; inset:0 auto 0 0; overflow:hidden; }
.stars .s-fg svg { fill:#f5b301; }
.blogo { display:inline-block; width:auto; vertical-align:middle; }
.lightbox { border:none; padding:0; width:100vw; height:100dvh; max-width:none; max-height:none; background:#000; }
.lightbox::backdrop { background:#000; }
.lb-track { display:flex; height:100%; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; }
.lb-track::-webkit-scrollbar { display:none; }
.lb-track figure { flex:none; width:100vw; height:100%; margin:0; scroll-snap-align:center; display:flex; flex-direction:column; justify-content:center; }
.lb-track img { max-height:86dvh; margin:0 auto; object-fit:contain; }
.lb-track figcaption { color:#bbb; text-align:center; padding:12px 20px; font-size:14px; }
.lb-close { position:fixed; top:14px; right:14px; width:48px; height:48px; border:1px solid rgba(255,255,255,.4); border-radius:50%; background:rgba(0,0,0,.4); color:#fff; font-size:26px; cursor:pointer; }
.map { display:block; width:100%; border:0; }
.video { aspect-ratio:16/9; background:#000; }
.video iframe { width:100%; height:100%; border:0; }
.hours { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
.hours th, .hours td { text-align:left; padding:7px 0; font-weight:400; }
.hours td { text-align:right; }
.hours tr.now th, .hours tr.now td { font-weight:700; }
.live i { display:inline-block; width:8px; height:8px; border-radius:50%; background:#bbb; flex:none; }
.live.open i { background:#2fbf71; }
"""

COMMON_JS = r"""
(function () {
  var H = __HOURS__;
  var i = (new Date().getDay() + 6) % 7, v = H[i] || "";
  document.querySelectorAll('.hours tr[data-d="' + i + '"]').forEach(function (r) { r.className = "now"; });
  var txt = "", open = false;
  if (/zavřeno/i.test(v)) txt = "Dnes zavřeno";
  else if (v) {
    var m = v.match(/(\d{1,2})[:.](\d{2})\s*[–-]\s*(\d{1,2})[:.](\d{2})/), now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
    open = !!(m && mins >= (+m[1]) * 60 + (+m[2]) && mins < (+m[3]) * 60 + (+m[4]));
    txt = open ? "Teď otevřeno do " + m[3] + ":" + m[4] : "Dnes " + v;
  }
  document.querySelectorAll(".live").forEach(function (el) {
    if (!txt) { el.style.display = "none"; return; }
    el.classList.toggle("open", open); var s = el.querySelector(".lt"); if (s) s.textContent = txt;
  });
  document.querySelectorAll("[data-today]").forEach(function (el) { el.textContent = v || "–"; });

  var hv = document.getElementById("hero-video");
  if (hv && window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) { hv.removeAttribute("autoplay"); hv.pause(); }

  // galerie na celou obrazovku
  var lb = document.querySelector(".lightbox");
  if (lb) {
    var track = lb.querySelector(".lb-track");
    document.querySelectorAll("[data-lb]").forEach(function (b) {
      b.addEventListener("click", function (ev) { if (b.dataset.moved) return; ev.preventDefault(); lb.showModal(); track.scrollLeft = track.clientWidth * (+b.dataset.lb); });
    });
    lb.querySelector(".lb-close").addEventListener("click", function () { lb.close(); });
  }

  // vodorovné pásy: táhnutí myší na desktopu
  document.querySelectorAll(".drag-x").forEach(function (el) {
    var down = false, sx = 0, sl = 0, moved = false;
    el.addEventListener("pointerdown", function (ev) { if (ev.pointerType !== "mouse") return; down = true; moved = false; sx = ev.clientX; sl = el.scrollLeft; });
    window.addEventListener("pointermove", function (ev) { if (!down) return; var dx = ev.clientX - sx; if (Math.abs(dx) > 5) { moved = true; el.classList.add("dragging"); } el.scrollLeft = sl - dx; });
    window.addEventListener("pointerup", function () { if (!down) return; down = false; el.classList.remove("dragging"); });
    el.addEventListener("click", function (ev) { if (moved) { ev.preventDefault(); ev.stopPropagation(); moved = false; } }, true);
  });

  // tečky pod karuselem
  document.querySelectorAll("[data-dots]").forEach(function (dots) {
    var el = document.getElementById(dots.dataset.dots); if (!el) return;
    var items = [].slice.call(el.children), ds = [].slice.call(dots.children);
    ds.forEach(function (d, k) { d.addEventListener("click", function () {
      var it = items[k]; el.scrollTo({ left: it.offsetLeft - (el.clientWidth - it.clientWidth) / 2, behavior: "smooth" }); }); });
    function upd() {
      var c = el.scrollLeft + el.clientWidth / 2, best = 0, bd = 1e9;
      items.forEach(function (it, k) { var m = Math.abs(it.offsetLeft + it.clientWidth / 2 - c); if (m < bd) { bd = m; best = k; } });
      ds.forEach(function (d, k) { d.classList.toggle("on", k === best); });
    }
    el.addEventListener("scroll", upd, { passive: true }); upd();
  });

  // záložky nabídky
  document.querySelectorAll("[data-tabs]").forEach(function (box) {
    var btns = box.querySelectorAll("[data-tab]"), panes = box.querySelectorAll("[data-pane]");
    btns.forEach(function (b) { b.addEventListener("click", function () {
      btns.forEach(function (x) { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); });
      panes.forEach(function (p) { p.hidden = p.dataset.pane !== b.dataset.tab; });
    }); });
  });

  // paralaxa
  if (!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    var els = [].slice.call(document.querySelectorAll("[data-par]")), tick = false;
    var run = function () {
      var vh = innerHeight;
      els.forEach(function (el) {
        var r = el.parentElement.getBoundingClientRect();
        if (r.bottom < 0 || r.top > vh) return;
        var k = +el.dataset.par, off = (r.top + r.height / 2 - vh / 2) * -k;
        el.style.transform = "translate3d(0," + off.toFixed(1) + "px,0)";
      });
      tick = false;
    };
    if (els.length) { addEventListener("scroll", function () { if (!tick) { tick = true; requestAnimationFrame(run); } }, { passive: true }); addEventListener("resize", run); run(); }
  }
})();
"""


def _script(x):
    return "<script>" + COMMON_JS.replace("__HOURS__", js([h.get("value") or "" for h in x["hours"]])) + "</script>"


def _offer_tabs(x, cls_item="mi"):
    """Nabídka se záložkami podle skupin (bez JS se ukáže první skupina)."""
    if not x["offer"]:
        return ""
    groups = x["groups"]
    tabs = ""
    if len(groups) > 1:
        tabs = '<div class="tabs" role="tablist">' + "".join(
            f'<button type="button" role="tab" data-tab="{i}" class="{"on" if i == 0 else ""}" aria-selected="{"true" if i == 0 else "false"}">{e(g or "Ostatní")}</button>'
            for i, (g, _) in enumerate(groups)) + "</div>"
    panes = ""
    for i, (g, items) in enumerate(groups):
        rows = "".join(
            f'<div class="{cls_item}"><span>{e(o["name"])}' + (f'<small>{e(o.get("desc"))}</small>' if o.get("desc") else "")
            + f'</span><span class="pr">{e(o.get("price"))}</span></div>' for o in items)
        panes += f'<div data-pane="{i}"{"" if i == 0 or len(groups) == 1 else " hidden"}>{rows}</div>'
    return f'<div data-tabs>{tabs}{panes}</div>'


# =====================================================================================  3 · VIZITKA

VIZITKA_CSS = """
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 var(--body); -webkit-font-smoothing:antialiased; }
.split { min-height:100vh; }
.photo { position:relative; height:46vh; min-height:300px; background:linear-gradient(135deg, var(--accent), var(--accent2)); overflow:hidden; }
.photo img, .photo .hv { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
.photo::after { content:""; position:absolute; inset:0; background:linear-gradient(180deg, transparent 50%, var(--bg)); }
.card { position:relative; max-width:560px; margin:-74px auto 0; padding:0 20px 40px; }
.badge { width:76px; height:76px; border-radius:50%; background:var(--accent); color:#fff; display:grid; place-items:center; box-shadow:0 0 0 6px var(--bg); }
h1 { font:var(--dw) clamp(38px, 9vw, 52px)/1.02 var(--display); letter-spacing:-.02em; margin:18px 0 8px; text-wrap:balance; }
.sub { color:var(--muted); margin:0 0 16px; font-size:17px; }
.meta { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:22px; }
.pill { display:inline-flex; align-items:center; gap:8px; padding:7px 13px; border-radius:999px; background:var(--surface); font-size:14px; font-weight:600; text-decoration:none; }
.pill .lt { white-space:nowrap; }
.actions { display:grid; gap:10px; margin-bottom:26px; }
.act { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 20px; border-radius:16px; background:var(--surface); text-decoration:none; font-weight:700; font-size:17px; transition:transform .15s; }
.act:active { transform:scale(.98); }
.act.main { background:var(--accent); color:#fff; }
.act small { font-weight:500; opacity:.75; font-size:14px; text-align:right; overflow-wrap:anywhere; }
.box { background:var(--surface); border-radius:18px; padding:20px; margin-bottom:10px; }
.box h2 { font:700 12px var(--body); letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:0 0 12px; }
.usp { display:flex; gap:12px; padding:7px 0; }
.usp b { color:var(--accent); flex:none; }
.usp span { font-weight:600; } .usp small { display:block; color:var(--muted); font-weight:400; font-size:14px; }
.about p, .about li { margin:0 0 .8em; }
.about ul { padding-left:20px; margin:0 0 .8em; }
.about h3 { font-size:17px; margin:1em 0 .3em; }
details { border-top:1px solid color-mix(in srgb, var(--ink) 10%, transparent); }
details:first-of-type { border-top:none; }
summary { cursor:pointer; padding:12px 0; font-weight:700; list-style:none; display:flex; justify-content:space-between; }
summary::-webkit-details-marker { display:none; }
summary::after { content:"+"; color:var(--accent); font-size:22px; line-height:1; }
details[open] summary::after { content:"–"; }
.row { display:flex; justify-content:space-between; gap:14px; padding:6px 0 10px; }
.row small { display:block; color:var(--muted); font-size:13px; }
.row .pr { font-weight:700; color:var(--accent); white-space:nowrap; }
.hours th, .hours td { border-bottom:1px solid color-mix(in srgb, var(--ink) 8%, transparent); }
.hours tr.now th, .hours tr.now td { color:var(--accent); }
.thumbs { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; }
.thumbs button { padding:0; border:0; border-radius:12px; overflow:hidden; aspect-ratio:4/5; cursor:zoom-in; background:var(--bg); }
.thumbs img { width:100%; height:100%; object-fit:cover; }
.q { font:var(--dw) 22px/1.3 var(--display); margin:0 0 8px; }
.q + small { color:var(--muted); }
.rate { display:flex; align-items:center; gap:10px; flex-wrap:wrap; font-weight:700; margin-bottom:14px; text-decoration:none; }
.rate span { color:var(--muted); font-weight:500; }
.map { height:200px; border-radius:18px; margin-bottom:10px; filter:grayscale(.3); }
.person { display:flex; gap:14px; align-items:center; }
.person img { width:56px; height:56px; border-radius:50%; object-fit:cover; }
.person span { display:block; color:var(--muted); font-size:14px; }
.socs { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:18px; }
.socs a { padding:9px 16px; border-radius:999px; border:1px solid color-mix(in srgb, var(--ink) 20%, transparent); text-decoration:none; font-weight:600; font-size:14px; }
.foot { text-align:center; color:var(--muted); font-size:13px; margin-top:22px; }
@media (min-width: 900px) {
  .split { display:grid; grid-template-columns:1fr 1fr; }
  .photo { position:sticky; top:0; height:100vh; }
  .photo::after { background:linear-gradient(90deg, transparent 75%, rgba(0,0,0,.12)); }
  .card { margin:0; padding:72px 64px; max-width:640px; }
}
"""


def render_vizitka(d, x, banner):
    c = x["c"]
    photo = x["video_tag"] or (f'<img src="{e(x["hero_img"])}" alt="{e(x["hero"].get("alt") or x["name"])}" fetchpriority="high">'
                               if x["hero_img"] else "")
    meta = '<span class="pill live"><i></i><span class="lt">Otevírací doba</span></span>'
    for r in x["ratings"]:
        inner = f'{_stars(r["value"], 13)} {_cz(r["value"])} {_brand(r, 14)}' + (f' · {e(_count(r["count"]))}' if r["count"] else "")
        meta += (f'<a class="pill" href="{e(r["url"])}" target="_blank" rel="noopener">{inner}</a>' if r["url"]
                 else f'<span class="pill">{inner}</span>')
    acts = ""
    if x["tel"]:
        acts += f'<a class="act main" href="tel:{x["tel"]}">Zavolat <small>{e(c.get("phone"))}</small></a>'
    acts += f'<a class="act" href="{e(x["maps"])}" target="_blank" rel="noopener">Navigovat <small>{e(c.get("address"))}</small></a>'
    if c.get("email"):
        acts += f'<a class="act" href="mailto:{e(c["email"])}">Napsat e-mail <small>{e(c["email"])}</small></a>'

    usps = "" if not x["usps"] else '<div class="box"><h2>Proč k nám</h2>' + "".join(
        f'<div class="usp"><b>—</b><span>{e(u["title"])}' + (f'<small>{e(u.get("text"))}</small>' if u.get("text") else "")
        + "</span></div>" for u in x["usps"]) + "</div>"
    about = f'<div class="box about"><h2>O nás</h2>{rich(d.get("about"))}</div>' if (d.get("about") or "").strip() else ""

    offer = ""
    if x["offer"]:
        offer = f'<div class="box"><h2>{e(d.get("offer_title") or x["t"]["offer_title"])}</h2>' + "".join(
            f'<details{" open" if i == 0 else ""}><summary>{e(g or "Nabídka")}</summary>' + "".join(
                f'<div class="row"><span>{e(o["name"])}' + (f'<small>{e(o.get("desc"))}</small>' if o.get("desc") else "")
                + f'</span><span class="pr">{e(o.get("price"))}</span></div>' for o in items) + "</details>"
            for i, (g, items) in enumerate(x["groups"])) + "</div>"

    thumbs = "" if not x["gallery"] else '<div class="box"><h2>Fotky</h2><div class="thumbs">' + "".join(
        f'<button data-lb="{i}" aria-label="Zvětšit: {e(g.get("alt"))}"><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy"></button>'
        for i, g in enumerate(x["gallery"][:6])) + "</div></div>"

    rev = ""
    if x["reviews"] or x["ratings"]:
        rr = x["ratings"][0] if x["ratings"] else None
        rate = ""
        if rr:
            inner = f'{_stars(rr["value"], 16)} {_cz(rr["value"])} {_brand(rr, 15)}' + (f'<span>· {e(_count(rr["count"]))}</span>' if rr["count"] else "")
            rate = (f'<a class="rate" href="{e(rr["url"])}" target="_blank" rel="noopener">{inner}</a>' if rr["url"]
                    else f'<div class="rate">{inner}</div>')
        q = ""
        if x["reviews"]:
            r0 = x["reviews"][0]
            q = f'<p class="q">„{e(r0["text"])}“</p><small>{e(r0.get("author"))}{(" · " + e(r0.get("source"))) if r0.get("source") else ""}</small>'
        rev = f'<div class="box"><h2>Hodnocení</h2>{rate}{q}</div>'

    hours = (f'<div class="box"><h2>Otevírací doba</h2><table class="hours">{_hours_rows(x)}</table>'
             + (f'<p class="foot" style="text-align:left;margin-top:10px">{e(d.get("hours_note"))}</p>' if d.get("hours_note") else "")
             + "</div>")
    person = ""
    if c.get("person") or c.get("photo"):
        person = ('<div class="box person">' + (f'<img src="img/{e(c["photo"])}" alt="{e(c.get("photo_alt"))}" loading="lazy">' if c.get("photo") else "")
                  + f'<div><b>{e(c.get("person"))}</b><span>{e(c.get("role"))}</span></div></div>')
    socs = "" if not x["socials"] else '<div class="socs">' + "".join(
        f'<a href="{e(u)}" target="_blank" rel="noopener">{e(l)}</a>' for l, u in x["socials"]) + "</div>"
    video = (f'<div class="box"><div class="video" style="border-radius:12px;overflow:hidden"><iframe src="https://www.youtube-nocookie.com/embed/{x["yt"]}" '
             f'title="Video – {e(x["name"])}" loading="lazy" allowfullscreen></iframe></div></div>') if x["yt"] else ""
    co = d.get("company") or {}

    return (_head(d, x) + "<style>" + _root(x) + COMMON_CSS + VIZITKA_CSS + "</style></head>\n"
            f'<body class="t-vizitka">{banner}<div class="split"><div class="photo">{photo}</div><main class="card">'
            f'<div class="badge">{icon_svg(x["icon"], 32)}</div>'
            f'<h1>{e(_plain(x["hero"].get("title")) or x["name"])}</h1>'
            + (f'<p class="sub">{e(x["hero"].get("subtitle"))}</p>' if x["hero"].get("subtitle") else "")
            + f'<div class="meta">{meta}</div><div class="actions">{acts}</div>'
            + usps + offer + hours + about + thumbs + video + rev
            + (f'<div>{x["map_html"]}</div>' if x["map_html"] else "") + person + socs
            + f'<p class="foot">{e(co.get("legal_name") or x["name"])}{(" · IČO " + e(co.get("ico"))) if co.get("ico") else ""}</p>'
            + "</main></div>" + _lightbox(x["gallery"][:6]) + _script(x) + "</body></html>")


# =====================================================================================  4 · POP

POP_CSS = """
body { margin:0; background:var(--pbg); color:var(--pink-ink); font:16px/1.5 var(--body); overflow-x:clip; -webkit-font-smoothing:antialiased; color:#111; }
.d { font-family:var(--display); font-weight:var(--dw); letter-spacing:-.03em; line-height:.92; }
.b { border:3px solid #111; box-shadow:6px 6px 0 #111; }
.top { position:sticky; top:0; z-index:20; display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 18px; background:var(--pbg); border-bottom:3px solid #111; }
.logo { font:var(--dw) 21px/1 var(--display); background:var(--pop); padding:8px 12px; border:3px solid #111; transform:rotate(-2deg); text-decoration:none; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:62vw; }
.top nav { display:none; gap:6px; }
.top nav a { font-weight:800; text-decoration:none; padding:8px 12px; border:3px solid transparent; }
.top nav a:hover { border-color:#111; background:#fff; }
.call { padding:10px 16px; font-weight:800; text-decoration:none; background:#fff; white-space:nowrap; }
.hero { padding:22px 18px 34px; }
.hero h1 { font-size:clamp(34px, var(--fm, 16vw), 168px); margin:6px 0 18px; }
.hl { display:inline-block; background:var(--accent); color:#fff; padding:0 .12em; transform:rotate(-1.5deg); }
.hero p { font-size:19px; font-weight:600; max-width:32ch; }
.btns { display:flex; gap:12px; margin-top:22px; flex-wrap:wrap; }
.btn { padding:15px 22px; font-weight:800; font-size:17px; text-decoration:none; background:var(--pop); display:inline-block; transition:transform .12s, box-shadow .12s; }
.btn:hover { transform:translate(-2px,-2px); box-shadow:8px 8px 0 #111; }
.btn:active { transform:translate(4px,4px); box-shadow:2px 2px 0 #111; }
.btn.alt { background:#fff; }
.hero-img { position:relative; height:360px; margin-top:34px; background:var(--accent); }
.hero-img img, .hero-img .hv { width:100%; height:100%; object-fit:cover; }
.sticker { position:absolute; right:-8px; top:-30px; width:124px; height:124px; border-radius:50%; background:var(--pink); display:grid; place-items:center; text-align:center; font:var(--dw) 16px/1.05 var(--display); transform:rotate(12deg); padding:10px; }
.sticker i { display:none; }
.rst { position:absolute; left:-8px; bottom:-22px; background:#fff; padding:8px 12px; font-weight:800; display:flex; align-items:center; gap:8px; transform:rotate(-3deg); text-decoration:none; }
.marquee { background:#111; color:var(--pop); overflow:hidden; white-space:nowrap; padding:14px 0; font:var(--dw) 26px var(--display); transform:rotate(-2deg); margin:34px -10px; }
.marquee span { display:inline-block; padding-right:0; animation:m 26s linear infinite; }
@keyframes m { to { transform:translateX(-50%); } }
.sec { padding:44px 18px; }
h2 { font-size:clamp(48px, 13vw, 110px); margin:0 0 22px; }
.card { background:#fff; padding:22px; font-size:17px; }
.card p:last-child { margin-bottom:0; }
.card h3 { font:var(--dw) 26px var(--display); margin:.6em 0 .2em; }
.tabs { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:18px; }
.tabs button { font:800 16px var(--body); padding:9px 16px; border:3px solid #111; background:#fff; cursor:pointer; }
.tabs button.on { background:#111; color:var(--pop); }
.tag { background:#fff; padding:16px 18px; display:flex; justify-content:space-between; align-items:center; gap:14px; font-weight:700; font-size:18px; margin-bottom:14px; border:3px solid #111; box-shadow:6px 6px 0 #111; }
.tag small { display:block; font-weight:500; font-size:14px; opacity:.7; }
.tag .pr { background:var(--pop); border:3px solid #111; padding:4px 10px; font-weight:800; transform:rotate(3deg); white-space:nowrap; }
.tag:nth-child(3n+2) .pr { background:var(--pink); transform:rotate(-3deg); }
.tag:nth-child(3n) .pr { background:var(--accent2); }
.polas { display:flex; gap:22px; overflow-x:auto; padding:14px 18px 34px; scrollbar-width:none; scroll-snap-type:x mandatory; cursor:grab; }
.polas::-webkit-scrollbar { display:none; }
.polas.dragging { cursor:grabbing; scroll-snap-type:none; }
.pola { flex:none; width:240px; background:#fff; padding:10px 10px 14px; transform:rotate(-3deg); cursor:zoom-in; scroll-snap-align:center; font:700 14px var(--body); text-align:left; }
.pola:nth-child(even) { transform:rotate(2.5deg); }
.pola img { width:100%; aspect-ratio:4/5; object-fit:cover; border:3px solid #111; margin-bottom:8px; user-select:none; pointer-events:none; }
.pola.sq img { aspect-ratio:1/1; }
.chat { display:grid; gap:16px; }
.bub { background:#fff; padding:14px 18px; border-radius:22px 22px 22px 4px; max-width:88%; font-weight:600; font-size:17px; margin:0; }
.bub:nth-child(even) { justify-self:end; background:var(--pop); border-radius:22px 22px 4px 22px; }
.bub small { display:block; font-weight:800; margin-top:6px; }
.rate { display:inline-flex; flex-wrap:wrap; gap:10px; align-items:center; background:var(--accent); color:#fff; padding:10px 16px; font-weight:800; font-size:20px; margin:0 12px 14px 0; text-decoration:none; }
.rate .blogo { background:#fff; padding:3px 6px; box-sizing:content-box; }
.rate span { font-size:15px; opacity:.9; }
.hours { background:#fff; padding:6px 18px; font-weight:700; font-size:18px; display:block; }
.hours tbody { display:block; }
.hours tr { display:flex; justify-content:space-between; padding:8px 0; border-bottom:3px dashed #ddd; }
.hours tr:last-child { border-bottom:none; }
.hours tr.now { color:var(--accent); }
.hours th { font-weight:700; }
.contact a.big { display:block; font:var(--dw) clamp(30px, 8vw, 44px)/1.05 var(--display); text-decoration:none; margin-bottom:10px; overflow-wrap:anywhere; }
.person { display:flex; align-items:center; gap:14px; margin-bottom:16px; }
.person img { width:72px; height:72px; object-fit:cover; border:3px solid #111; border-radius:50%; }
.mapbox { margin:0 18px; height:300px; overflow:hidden; }
.mapbox .map { height:100%; }
.socs { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }
.socs a { padding:9px 14px; font-weight:800; text-decoration:none; background:var(--pop); color:#111; border:3px solid var(--pop); }
.foot { background:#111; color:#fff; padding:44px 18px 34px; margin-top:44px; }
.foot .d { font-size:clamp(44px, 12vw, 96px); color:var(--pop); margin-bottom:16px; }
.foot p { opacity:.8; }
@media (min-width: 900px) {
  .top { padding:16px 48px; } .top nav { display:flex; margin-left:auto; } .logo { max-width:none; }
  .hero { padding:30px 48px 50px; display:grid; grid-template-columns:1.2fr 1fr; gap:48px; align-items:end; }
  .hero h1 { font-size:clamp(44px, var(--fd, 7.4vw), 150px); }
  .hero-img { height:560px; margin-top:0; }
  .sec { padding:80px 48px; } .polas { padding:14px 48px 40px; } .pola { width:310px; }
  .two { display:grid; grid-template-columns:1fr 1fr; gap:56px; align-items:start; }
  .tags-wrap > div[data-pane] { display:grid; grid-template-columns:1fr 1fr; column-gap:22px; }
  .tags-wrap > div[data-pane][hidden] { display:none; }
  .mapbox { margin:0 48px; height:420px; }
  .foot { padding:70px 48px 50px; }
}
@media (prefers-reduced-motion: reduce) { .marquee span { animation:none; } }
"""


def render_pop(d, x, banner):
    c = x["c"]
    title = x["hero"].get("title") or x["name"]
    media = x["video_tag"] or (f'<img src="{e(x["hero_img"])}" alt="{e(x["hero"].get("alt") or x["name"])}" fetchpriority="high">'
                               if x["hero_img"] else "")
    rst = ""
    if x["ratings"]:
        r = x["ratings"][0]
        inner = f'★ {_cz(r["value"])} {_brand(r, 15)}'
        rst = (f'<a class="rst b" href="{e(r["url"])}" target="_blank" rel="noopener">{inner}</a>' if r["url"]
               else f'<span class="rst b">{inner}</span>')
    nav = [("o-nas", "O nás")]
    if x["offer"]:
        nav.append(("nabidka", x["t"]["offer_nav"]))
    if x["gallery"]:
        nav.append(("fotky", "Fotky"))
    nav.append(("kontakt", "Kontakt"))

    marquee = ""
    if x["usps"]:
        one = "".join(f"★ {e(u['title'])} " for u in x["usps"])
        marquee = f'<div class="marquee" aria-label="Proč k nám"><span>{one * 4}</span></div>'

    about = f'<section class="sec" id="o-nas"><h2 class="d">O nás</h2><div class="card b">{rich(d.get("about"))}</div></section>' \
        if (d.get("about") or "").strip() else '<span id="o-nas"></span>'

    offer = ""
    if x["offer"]:
        offer = (f'<section class="sec" id="nabidka"><h2 class="d">{e(d.get("offer_title") or x["t"]["offer_title"])}</h2>'
                 + (f'<p style="font-weight:700;margin:-8px 0 20px">{e(d.get("booking_note"))}</p>' if d.get("booking_note") else "")
                 + '<div class="tags-wrap">' + _offer_tabs(x, "tag") + "</div></section>")
        offer = offer.replace('<div data-tabs><div class="tabs"', '<div data-tabs class="tags-wrap"><div class="tabs"')

    gal = "" if not x["gallery"] else (
        '<section id="fotky"><div class="sec" style="padding-bottom:0"><h2 class="d">Fotky</h2></div><div class="polas drag-x">'
        + "".join(f'<button class="pola b {_fmt(d, g["file"])}" data-lb="{i}"><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy" draggable="false">{e(g.get("alt"))}</button>'
                  for i, g in enumerate(x["gallery"])) + "</div></section>")
    video = (f'<section class="sec"><div class="video b"><iframe src="https://www.youtube-nocookie.com/embed/{x["yt"]}" '
             f'title="Video – {e(x["name"])}" loading="lazy" allowfullscreen></iframe></div></section>') if x["yt"] else ""

    rev = ""
    if x["reviews"] or x["ratings"]:
        rates = "".join(
            (f'<a class="rate b" href="{e(r["url"])}" target="_blank" rel="noopener">' if r["url"] else '<div class="rate b">')
            + f'★ {_cz(r["value"])} {_brand(r, 16)}' + (f'<span>{e(_count(r["count"]))}</span>' if r["count"] else "")
            + ("</a>" if r["url"] else "</div>") for r in x["ratings"])
        bubs = "".join(f'<blockquote class="bub b">{e(r["text"])}<small>{e(r.get("author"))}</small></blockquote>' for r in x["reviews"])
        rev = f'<section class="sec two"><div><h2 class="d">Říkaj o nás</h2>{rates}</div><div class="chat">{bubs}</div></section>'

    person = ""
    if c.get("person") or c.get("photo"):
        person = ('<div class="person">' + (f'<img src="img/{e(c["photo"])}" alt="{e(c.get("photo_alt"))}" loading="lazy">' if c.get("photo") else "")
                  + f'<div><b>{e(c.get("person"))}</b><br>{e(c.get("role"))}</div></div>')
    socs = "" if not x["socials"] else '<div class="socs">' + "".join(
        f'<a href="{e(u)}" target="_blank" rel="noopener">{e(l)}</a>' for l, u in x["socials"]) + "</div>"
    contact = (f'<section class="sec two" id="kontakt"><div class="contact"><h2 class="d">Kdy a kde?</h2>{person}'
               + (f'<a class="big" href="tel:{x["tel"]}">{e(c.get("phone"))}</a>' if x["tel"] else "")
               + (f'<a class="big" href="mailto:{e(c["email"])}" style="font-size:24px">{e(c["email"])}</a>' if c.get("email") else "")
               + f'<p style="font-weight:700;font-size:18px">{e(c.get("address"))}<br><a href="{e(x["maps"])}" target="_blank" rel="noopener">Navigovat →</a></p>{socs}</div>'
               + f'<div><table class="hours b">{_hours_rows(x)}</table>'
               + (f'<p style="font-weight:700">{e(d.get("hours_note"))}</p>' if d.get("hours_note") else "") + "</div></section>")
    mapbox = f'<div class="mapbox b">{x["map_html"]}</div>' if x["map_html"] else ""
    co = d.get("company") or {}

    root = _root(x, "--pbg:#FFF8E7; --pop:#FFE14D; --pink:#FF7AB6; --pink-ink:#111;")
    return (_head(d, x) + "<style>" + root + COMMON_CSS + POP_CSS + "</style></head>\n"
            f'<body class="t-pop">{banner}<header class="top"><a class="logo" href="#">{e(x["logo_text"])}</a>'
            '<nav aria-label="Menu">' + "".join(f'<a href="#{a}">{e(l)}</a>' for a, l in nav) + "</nav>"
            + (f'<a class="call b" href="tel:{x["tel"]}">Zavolat</a>' if x["tel"] else "") + "</header>"
            f'<section class="hero"><div><h1 class="d" style="{_fit(title, 16, 7.4, .6, 88, 50)}">{_hi(title)}</h1>'
            + (f'<p>{e(x["hero"].get("subtitle"))}</p>' if x["hero"].get("subtitle") else "")
            + '<div class="btns">' + (f'<a class="btn b" href="tel:{x["tel"]}">Zavolat</a>' if x["tel"] else "")
            + '<a class="btn alt b" href="#kontakt">Kde jsme?</a></div></div>'
            f'<div class="hero-img b">{media}<div class="sticker b live"><i></i><span class="lt">Mrkni na otevírací dobu</span></div>{rst}</div></section>'
            + marquee + about + offer + gal + video + rev + contact + mapbox
            + f'<footer class="foot"><div class="d">{e(x["logo_text"])}</div>'
            + f'<p>{e(co.get("legal_name") or x["name"])}{(" · IČO " + e(co.get("ico"))) if co.get("ico") else ""}<br>{e(co.get("address"))}</p>{socs}</footer>'
            + _lightbox(x["gallery"]) + _script(x) + "</body></html>")


# =====================================================================================  5 · LUXUS

LUX_CSS = """
body { margin:0; background:#fff; color:var(--lx); font:400 17px/1.5 var(--body); -webkit-font-smoothing:antialiased; overflow-x:clip; }
a { text-decoration:none; }
h1, h2, .tile b { font-family:var(--display); font-weight:var(--dw); }
.pill { display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:44px; padding:0 22px; border-radius:999px; background:#fff; color:var(--lx); font-weight:600; font-size:16px; white-space:nowrap; border:0; cursor:pointer; transition:transform .2s, background .2s; }
.pill:hover { transform:scale(1.03); }
.pill.dark { background:var(--lx); color:#fff; }
.pill.acc { background:var(--accent); color:#fff; }
.pill.glass { background:rgba(255,255,255,.22); color:#fff; backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); }
.lnav { position:sticky; top:0; z-index:20; height:52px; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:0 20px;
  background:rgba(255,255,255,.8); backdrop-filter:saturate(1.8) blur(20px); -webkit-backdrop-filter:saturate(1.8) blur(20px); font-size:13px; border-bottom:1px solid rgba(0,0,0,.06); }
.lnav b { font-size:15px; font-weight:600; letter-spacing:-.01em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lnav .links { display:none; gap:34px; color:#424245; }
.lnav .links a:hover { color:var(--lx); }
.lnav .pill { min-height:30px; padding:0 14px; font-size:13px; }
.hero { position:relative; height:92svh; min-height:560px; max-height:1100px; overflow:hidden; background:linear-gradient(160deg, var(--accent), #111); color:#fff; }
.hero .bg { position:absolute; inset:-12% 0; will-change:transform; }
.hero .bg img, .hero .bg .hv { width:100%; height:100%; object-fit:cover; }
.hero::after { content:""; position:absolute; inset:0; background:linear-gradient(180deg, rgba(0,0,0,.06) 35%, rgba(0,0,0,.6)); }
.hero-in { position:absolute; left:0; right:0; bottom:9vh; z-index:2; text-align:center; padding:0 20px; }
.hero .live { display:inline-flex; align-items:center; gap:8px; font-weight:600; font-size:14px; opacity:.92; }
.hero h1 { font-size:clamp(34px, var(--fm, 13vw), 128px); line-height:1.02; letter-spacing:-.045em; margin:10px auto 14px; max-width:16ch; text-wrap:balance; }
.hero p { font-size:clamp(19px, 2.4vw, 24px); margin:0 auto 26px; max-width:30ch; opacity:.92; }
.btns { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
.intro { text-align:center; padding:96px 20px 64px; max-width:900px; margin:0 auto; }
.intro h2 { font-size:clamp(34px, 6.5vw, 64px); line-height:1.05; letter-spacing:-.035em; margin:0 0 20px; white-space:pre-line; text-wrap:balance; }
.intro .txt { color:var(--muted2); font-size:clamp(18px, 2vw, 21px); max-width:48ch; margin:0 auto; }
.intro .txt ul { text-align:left; display:inline-block; }
.intro .txt h3 { color:var(--lx); font-size:21px; }
.peek { display:flex; gap:14px; overflow-x:auto; scroll-snap-type:x mandatory; padding:0 7vw 8px; scrollbar-width:none; cursor:grab; }
.peek::-webkit-scrollbar { display:none; }
.peek.dragging { cursor:grabbing; scroll-snap-type:none; }
.slide { position:relative; flex:none; width:86vw; height:min(66vh, 620px); border-radius:22px; overflow:hidden; scroll-snap-align:center; color:#fff; background:var(--soft); }
.slide img { width:100%; height:100%; object-fit:cover; transition:transform .8s cubic-bezier(.2,.7,.2,1); user-select:none; pointer-events:none; }
.slide:hover img { transform:scale(1.03); }
.slide::after { content:""; position:absolute; inset:0; background:linear-gradient(180deg, transparent 50%, rgba(0,0,0,.62)); }
.slide .cap { position:absolute; left:22px; right:22px; bottom:22px; z-index:2; display:flex; align-items:center; gap:10px 16px; flex-wrap:wrap; }
.slide .cap span:not(.pill) { font-size:18px; font-weight:600; line-height:1.35; }
.slide.txt { background:var(--soft); color:var(--lx); display:flex; align-items:flex-end; }
.slide.txt::after { display:none; }
.dots { display:flex; gap:8px; justify-content:center; padding:20px 0 0; }
.dots button { width:8px; height:8px; padding:0; border:0; border-radius:4px; background:#d2d2d7; cursor:pointer; transition:width .3s, background .3s; }
.dots button.on { background:var(--lx); width:22px; }
.tiles { display:grid; gap:12px; padding:96px 12px 0; max-width:1440px; margin:0 auto; }
.tile { position:relative; min-height:520px; border-radius:22px; overflow:hidden; color:#fff; display:flex; flex-direction:column; align-items:center; text-align:center; padding:48px 24px 32px; background:linear-gradient(160deg, var(--accent), #111); }
.tile .ph { position:absolute; inset:-10% 0; will-change:transform; }
.tile .ph img { width:100%; height:100%; object-fit:cover; }
.tile::after { content:""; position:absolute; inset:0; background:linear-gradient(180deg, rgba(0,0,0,.4), transparent 45%, rgba(0,0,0,.4)); }
.tile > :not(.ph) { position:relative; z-index:2; }
.tile b { font-size:clamp(72px, 15vw, 140px); line-height:.9; letter-spacing:-.05em; }
.tile b .blogo { height:.42em; background:#fff; padding:.08em .14em; border-radius:.1em; box-sizing:content-box; vertical-align:.18em; }
.tile span.l { font-size:21px; font-weight:600; margin-top:12px; max-width:22ch; }
.tile .pill { margin-top:auto; }
.tile.light { background:var(--soft); color:var(--lx); }
.tile.light::after { display:none; }
.menu { max-width:820px; margin:0 auto; padding:110px 20px 80px; }
.h2c { text-align:center; font-size:clamp(34px, 6vw, 56px); letter-spacing:-.035em; line-height:1.05; margin:0 0 10px; }
.subc { text-align:center; color:var(--muted2); margin:0 0 36px; }
.tabs { display:flex; gap:6px; justify-content:center; flex-wrap:wrap; margin-bottom:24px; }
.tabs button { padding:8px 18px; border-radius:999px; font:600 15px var(--body); color:var(--muted2); background:none; border:0; cursor:pointer; }
.tabs button.on { background:var(--lx); color:#fff; }
.mi { display:flex; justify-content:space-between; align-items:baseline; gap:20px; padding:22px 0; border-bottom:1px solid #d2d2d7; font-size:19px; font-weight:600; }
.mi small { display:block; color:var(--muted2); font-size:15px; font-weight:400; }
.mi .pr { font-weight:400; white-space:nowrap; }
.gal { padding:40px 12px 120px; max-width:1440px; margin:0 auto; }
.mosaic { --u:40px; --g:12px; display:grid; grid-template-columns:repeat(2, 1fr); grid-auto-rows:var(--u); grid-auto-flow:dense; gap:var(--g); }
.mosaic button { position:relative; margin:0; padding:0; border:0; border-radius:18px; overflow:hidden; cursor:zoom-in; background:var(--soft);
  grid-row:span var(--r, 5); will-change:transform; }
.mosaic button.big { grid-column:span 2; grid-row:span calc(var(--r, 5) * 2); }
.mosaic img { width:100%; height:100%; object-fit:cover; transition:transform .8s cubic-bezier(.2,.7,.2,1); }
.mosaic button:hover img { transform:scale(1.03); }
.mosaic button::after { content:""; position:absolute; inset:auto 0 0 0; height:40%; background:linear-gradient(transparent, rgba(0,0,0,.35)); opacity:0; transition:opacity .4s; }
.mosaic span { position:absolute; left:16px; bottom:14px; z-index:1; color:#fff; font-size:14px; font-weight:600; text-shadow:0 1px 8px rgba(0,0,0,.5); text-align:left; opacity:0; transition:opacity .4s; }
.mosaic button.big::after, .mosaic button.big span, .mosaic button:hover::after, .mosaic button:hover span { opacity:1; }
@media (hover: none) { .mosaic span, .mosaic button::after { opacity:1; } }
.quote { background:var(--soft); text-align:center; padding:110px 20px; }
.quote .rv { display:none; }
.quote .rv.on { display:block; animation:fade .6s ease both; }
@keyframes fade { from { opacity:0; transform:translateY(10px); } }
.quote p { font-family:var(--display); font-weight:var(--dw); font-size:clamp(30px, 5vw, 52px); line-height:1.1; letter-spacing:-.03em; max-width:22ch; margin:18px auto 16px; }
.quote small, .quote .src { color:var(--muted2); font-size:16px; }
.quote .src { display:inline-flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:center; margin-top:22px; }
.video-sec { max-width:1180px; margin:0 auto; padding:0 12px 110px; }
.video-sec .video { border-radius:22px; overflow:hidden; }
.info { display:grid; gap:44px; max-width:1100px; margin:0 auto; padding:100px 20px; }
.info h3 { font-weight:600; font-size:21px; margin:0 0 12px; letter-spacing:-.01em; }
.info p { color:var(--muted2); margin:0 0 6px; }
.info a:hover { color:var(--accent); }
.info .hours th { color:var(--muted2); }
.info .hours tr.now th, .info .hours tr.now td { color:var(--lx); }
.person { display:flex; align-items:center; gap:14px; margin-bottom:14px; }
.person img { width:56px; height:56px; border-radius:50%; object-fit:cover; }
.map { height:340px; filter:grayscale(1) contrast(1.05); }
.foot { padding:22px 20px; font-size:12px; color:var(--muted2); background:var(--soft); display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; }
.foot .s a { margin-left:16px; }
@media (min-width: 900px) {
  .lnav { padding:0 max(20px, calc((100vw - 1000px) / 2)); } .lnav .links { display:flex; }
  .hero h1 { font-size:clamp(48px, var(--fd, 9vw), 128px); max-width:none; }
  .peek { padding:0 max(7vw, calc((100vw - 1180px) / 2)); } .slide { width:min(86vw, 1180px); height:640px; }
  .slide .cap { left:40px; bottom:36px; } .slide .cap span:not(.pill) { font-size:22px; }
  .tiles { grid-template-columns:1fr 1fr; padding:120px 12px 0; } .tile { min-height:640px; padding-top:64px; }
  .tile.wide { grid-column:span 2; min-height:540px; }
  .mosaic { grid-template-columns:repeat(4, 1fr); --g:16px; }
  .info { grid-template-columns:repeat(3, 1fr); }
  .map { height:440px; }
}
@media (prefers-reduced-motion: reduce) { .hero .bg, .tile .ph { transform:none !important; } }
"""


def default_stats(d, x):
    """Když prodejce čísla nevyplní, nabídneme hodnocení a čas otevření."""
    out = []
    if x["ratings"]:
        r = x["ratings"][0]
        out.append({"value": f"{_cz(r['value'])} ★", "label": f"{r['label']}" + (f" · {_count(r['count'])}" if r["count"] else ""),
                    "_link": r["url"], "_btn": "Přečíst recenze"})
    t = _open_time(x["hours"])
    if t:
        out.append({"value": t, "label": "otevíráme", "_link": "#kontakt", "_btn": "Otevírací doba"})
    return out


def render_luxus(d, x, banner):
    c = x["c"]
    gal = x["gallery"]
    hero = x["hero"]
    bg = x["video_tag"] or (f'<img src="{e(x["hero_img"])}" alt="{e(hero.get("alt") or x["name"])}" fetchpriority="high">'
                            if x["hero_img"] else "")
    extra = d.get("extra") or {}

    nav = [("o-nas", "O nás")]
    if x["offer"]:
        nav.append(("nabidka", x["t"]["offer_nav"]))
    if gal:
        nav.append(("fotky", "Fotky"))
    nav.append(("kontakt", "Kontakt"))

    intro_t = (extra.get("intro_title") or "").strip()
    intro = (f'<section class="intro" id="o-nas"><h2>{e(intro_t or "O nás")}</h2><div class="txt">{rich(d.get("about"))}</div></section>'
             if (d.get("about") or "").strip() or intro_t else '<span id="o-nas"></span>')

    # karusel: výhody + fotky (výhoda = štítek, popis = text)
    slides = []
    n = len(gal)
    if x["usps"]:
        for i, u in enumerate(x["usps"]):
            g = gal[(i + 1) % n] if n else None
            slides.append((g, u["title"], u.get("text") or (g.get("alt") if g else "")))
    else:
        for g in gal[1:5] or gal[:4]:
            slides.append((g, "", g.get("alt")))
    peek = ""
    if slides:
        items = ""
        for g, pill, txt in slides:
            img = f'<img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy" draggable="false">' if g else ""
            cap = (f'<span class="pill">{e(pill)}</span>' if pill else "") + (f'<span>{e(txt)}</span>' if txt else "")
            items += f'<div class="slide{"" if g else " txt"}">{img}<div class="cap">{cap}</div></div>'
        on_ = ' class="on"'
        dots = "".join(f'<button aria-label="Snímek {i + 1}"{on_ if i == 0 else ""}></button>' for i in range(len(slides))) \
            if len(slides) > 1 else ""
        peek = f'<div class="peek drag-x" id="peek">{items}</div>' + (f'<div class="dots" data-dots="peek">{dots}</div>' if dots else "")

    # dlaždice s velkými čísly
    stats = [s for s in d.get("stats") or [] if (s.get("value") or "").strip()]
    auto = not stats
    if auto:
        stats = default_stats(d, x)
    tiles = ""
    if stats:
        k = len(stats)
        for i, s in enumerate(stats[:4]):
            wide = (k % 2 == 1 and i == min(k, 4) - 1)
            g = gal[(i + 2) % n] if n and not wide else None
            link, btn = s.get("_link"), s.get("_btn")
            if not link and wide and x["tel"]:
                link, btn = f"tel:{x['tel']}", "Zavolat"
            pill_cls = "dark" if not g else ("" if i % 2 == 0 else "glass")
            ext = ' target="_blank" rel="noopener"' if (link or "").startswith("http") else ""
            pill = f'<a class="pill {pill_cls}" href="{e(link)}"{ext}>{e(btn)}</a>' \
                if link and btn else ""
            ph = f'<div class="ph" data-par="0.1"><img src="img/{e(g["file"])}" alt="" loading="lazy"></div>' if g else ""
            cls = "tile" + ("" if g else " light") + (" wide" if wide else "")
            tiles += f'<div class="{cls}">{ph}<b>{e(s["value"])}</b><span class="l">{e(s.get("label"))}</span>{pill}</div>'
        tiles = f'<section class="tiles" aria-label="V číslech">{tiles}</section>'

    menu = ""
    if x["offer"]:
        menu = (f'<section class="menu" id="nabidka"><h2 class="h2c">{e(d.get("offer_title") or x["t"]["offer_title"])}</h2>'
                + (f'<p class="subc">{e(d.get("booking_note"))}</p>' if d.get("booking_note") else '<div style="height:26px"></div>')
                + _offer_tabs(x, "mi") + "</section>")

    mosaic = "" if not gal else (
        '<section class="gal" id="fotky"><h2 class="h2c">Atmosféra</h2><p class="subc">Klepnutím fotku zvětšíte.</p><div class="mosaic">'
        + "".join(f'<button class="{"big" if i == 0 else ""}" style="--r:{_rows(d, g["file"])}" data-lb="{i}" aria-label="Zvětšit: {e(g.get("alt"))}"><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}"{_wh(d, g["file"])} loading="lazy"><span>{e(g.get("alt"))}</span></button>'
                  for i, g in enumerate(gal[:12])) + "</div></section>")
    video = (f'<section class="video-sec"><div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{x["yt"]}" '
             f'title="Video – {e(x["name"])}" loading="lazy" allowfullscreen></iframe></div></section>') if x["yt"] else ""

    quote = ""
    if x["reviews"] or x["ratings"]:
        r0 = x["ratings"][0] if x["ratings"] else None
        src = ""
        if r0:
            src = (f'<a class="src" href="{e(r0["url"])}" target="_blank" rel="noopener">' if r0["url"] else '<div class="src">') \
                + f'{_stars(r0["value"], 18)} {_cz(r0["value"])} {_brand(r0, 16)}' + (f' · {e(_count(r0["count"]))}' if r0["count"] else "") \
                + ("</a>" if r0["url"] else "</div>")
        rvs = "".join(f'<div class="rv{" on" if i == 0 else ""}"><p>„{e(r["text"])}“</p><small>{e(r.get("author"))}'
                      + (f' · {e(r.get("source"))}' if r.get("source") else "") + "</small></div>" for i, r in enumerate(x["reviews"][:6]))
        quote = f'<section class="quote" id="recenze">{rvs}{src}</section>'

    person = ""
    if c.get("person") or c.get("photo"):
        person = ('<div class="person">' + (f'<img src="img/{e(c["photo"])}" alt="{e(c.get("photo_alt"))}" loading="lazy">' if c.get("photo") else "")
                  + f'<div><b>{e(c.get("person"))}</b><p style="margin:0">{e(c.get("role"))}</p></div></div>')
    soc = " · ".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{e(l)}</a>' for l, u in x["socials"])
    info = (f'<section class="info" id="kontakt"><div><h3>Návštěva</h3><p>{e(c.get("address"))}</p>'
            f'<p><a href="{e(x["maps"])}" target="_blank" rel="noopener" style="color:var(--accent);font-weight:600">Naplánovat trasu ›</a></p></div>'
            f'<div><h3>Otevřeno</h3><table class="hours">{_hours_rows(x)}</table>'
            + (f'<p style="margin-top:10px">{e(d.get("hours_note"))}</p>' if d.get("hours_note") else "") + "</div>"
            + f'<div><h3>Kontakt</h3>{person}'
            + (f'<p><a href="tel:{x["tel"]}">{e(c.get("phone"))}</a></p>' if x["tel"] else "")
            + (f'<p><a href="mailto:{e(c["email"])}">{e(c["email"])}</a></p>' if c.get("email") else "")
            + (f"<p>{soc}</p>" if soc else "") + "</div></section>")
    co = d.get("company") or {}

    masonry_js = "" if not gal else """<script>(function(){var m=document.querySelector('.mosaic');if(!m)return;
var items=[].slice.call(m.children),reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function unit(){var cs=getComputedStyle(m),cols=cs.gridTemplateColumns.split(' ').length,g=parseFloat(cs.columnGap)||12;
var w=(m.clientWidth-g*(cols-1))/cols;m.style.setProperty('--u',((w-3*g)/4)+'px');}
unit();addEventListener('resize',unit);
function setBig(el){if(el.classList.contains('big'))return;var first=items.map(function(i){return i.getBoundingClientRect();});
items.forEach(function(i){i.classList.toggle('big',i===el);});if(reduce)return;
items.forEach(function(i,k){var a=first[k],b=i.getBoundingClientRect();if(!b.width)return;
var dx=a.left-b.left,dy=a.top-b.top,sx=a.width/b.width,sy=a.height/b.height;if(Math.abs(dx)<1&&Math.abs(dy)<1&&Math.abs(sx-1)<.01&&Math.abs(sy-1)<.01)return;
i.style.transformOrigin='0 0';i.style.transition='none';i.style.transform='translate('+dx+'px,'+dy+'px) scale('+sx+','+sy+')';
i.getBoundingClientRect();i.style.transition='transform .55s cubic-bezier(.2,.7,.2,1)';i.style.transform='';});}
if(matchMedia('(hover: hover)').matches){var t,pend=null,busy=0;
/* zvětšíme fotku, nad kterou je kurzor ~140 ms; během přeskládání (600 ms) nic neměníme
   a potom jen při skutečném pohybu myši – jinak by se pod stojícím kurzorem fotky přepínaly samy */
var lx=-1e4,ly=-1e4;
function want(i,ev){if(i.classList.contains('big')||Date.now()<busy||pend===i)return;
if(Math.abs(ev.clientX-lx)+Math.abs(ev.clientY-ly)<60)return;clearTimeout(t);pend=i;
t=setTimeout(function(){pend=null;if(Date.now()<busy)return;lx=ev.clientX;ly=ev.clientY;setBig(i);busy=Date.now()+600;},140);}
items.forEach(function(i){i.addEventListener('mousemove',function(ev){want(i,ev);});
i.addEventListener('mouseleave',function(){if(pend===i){clearTimeout(t);pend=null;}});});}})();</script>"""
    rotate = "" if len(x["reviews"]) < 2 else """<script>(function(){var r=document.querySelectorAll('.quote .rv'),i=0;
if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;setInterval(function(){r[i].classList.remove('on');i=(i+1)%r.length;r[i].classList.add('on');},6000);})();</script>"""

    root = _root(x, "--lx:#1d1d1f; --muted2:#6e6e73; --soft:#f5f5f7;")
    return (_head(d, x) + "<style>" + root + COMMON_CSS + LUX_CSS + "</style></head>\n"
            f'<body class="t-luxus">{banner}<nav class="lnav" aria-label="Menu"><b>{e(x["logo_text"])}</b>'
            '<div class="links">' + "".join(f'<a href="#{a}">{e(l)}</a>' for a, l in nav) + "</div>"
            + (f'<a class="pill dark" href="tel:{x["tel"]}">Zavolat</a>' if x["tel"] else '<a class="pill dark" href="#kontakt">Kontakt</a>')
            + "</nav>"
            f'<header class="hero" id="top"><div class="bg" data-par="0.25">{bg}</div><div class="hero-in">'
            '<span class="live"><i></i><span class="lt"></span></span>'
            f'<h1 style="{_fit(_plain(hero.get("title")) or x["name"], 13, 9, .56, 88, 80, 3, 2)}">{e(_plain(hero.get("title")) or x["name"])}</h1>'
            + (f'<p>{e(hero.get("subtitle"))}</p>' if hero.get("subtitle") else "")
            + '<div class="btns">' + (f'<a class="pill" href="tel:{x["tel"]}">Zavolat</a>' if x["tel"] else "")
            + '<a class="pill glass" href="#kontakt">Jak k nám</a></div></div></header>'
            + intro + peek + tiles + menu + mosaic + video + quote + info + x["map_html"]
            + f'<footer class="foot"><span>{e(co.get("legal_name") or x["name"])}{(" · IČO " + e(co.get("ico"))) if co.get("ico") else ""}'
            + f'{(" · " + e(co.get("address"))) if co.get("address") else ""}</span><span>{e(x["name"])}</span></footer>'
            + _lightbox(gal[:12]) + _script(x) + rotate + masonry_js + "</body></html>")


RENDERERS = {"3": render_vizitka, "4": render_pop, "5": render_luxus}


def render(tpl, d, preview_banner=""):
    x = _ctx(d, tpl)
    if tpl in ("6", "7"):
        from . import tpl_street
        return {"6": tpl_street.render_urban, "7": tpl_street.render_brush}[tpl](d, x, preview_banner)
    return RENDERERS[tpl](d, x, preview_banner)
