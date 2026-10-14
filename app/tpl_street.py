"""Šablony 6 (Urban – žlutočerná, černobílé fotky, ručně psané písmo) a 7 (Štětec – barevné přechody, natržené okraje)."""
import re

from .sites import _count, _cz, _fmt, _stars, e, rich
from .templates_more import (COMMON_CSS, _brand, _fit, _head, _hours_rows, _lightbox, _offer_tabs, _open_time, _root,
                             _script, default_stats)


PHONE_SVG = ('<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><path d="M6.6 10.8a15.2 15.2 0 0 0 6.6 6.6l2.2-2.2'
             'c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1'
             ' 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1z"/></svg>')


def _svg_url(svg):
    from urllib.parse import quote
    return "url(\"data:image/svg+xml," + quote(svg) + "\")"


NOISE_DARK = _svg_url("<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'>"
                      "<feTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/>"
                      "<feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .11 0'/></filter>"
                      "<rect width='100%' height='100%' filter='url(#n)'/></svg>")


def _rng(seed):
    v = seed or 1
    while True:
        v = (v * 9301 + 49297) % 233280
        yield v / 233280


def _torn_clip(seed, amp=2.6, top=True, bottom=True, n=22):
    """clip-path s natrženým horním/dolním okrajem (procenta)."""
    r = _rng(seed)
    pts = []
    for i in range(n + 1):
        x = 100 * i / n
        pts.append((x, next(r) * amp if top else 0))
    for i in range(n, -1, -1):
        x = 100 * i / n
        pts.append((x, 100 - next(r) * amp if bottom else 100))
    return "polygon(" + ",".join(f"{x:.1f}% {y:.1f}%" for x, y in pts) + ")"


def _edge(fill, seed=1, flip=False):
    """Natržený okraj štětce mezi sekcemi (SVG přes celou šířku)."""
    r = _rng(seed)
    W, H = 1440, 90
    d = [f"M0 {H}", "L0 52"]
    x = 0
    base = 46
    while x < W:
        step = 18 + next(r) * 60
        x = min(W, x + step)
        base = max(30, min(62, base + (next(r) - .5) * 14))     # pomalé vlnění tahu štětce
        y = base + (next(r) - .5) * 7                           # drobné zoubky
        if next(r) > .9:                                        # občasný výběžek
            d.append(f"L{x - step * .55:.0f} {y - 10 - next(r) * 12:.0f}")
        d.append(f"L{x:.0f} {y:.0f}")
    d.append(f"L{W} {H}Z")
    flecks = "".join(f'<rect x="{next(r) * W:.0f}" y="{8 + next(r) * 26:.0f}" width="{3 + next(r) * 9:.0f}" height="{2 + next(r) * 4:.0f}" rx="2"/>'
                     for _ in range(9))
    tr = ' transform="scale(1,-1) translate(0,-90)"' if flip else ""
    return (f'<div class="edge{" flip" if flip else ""}" aria-hidden="true"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none">'
            f'<g fill="{fill}"{tr}><path d="{" ".join(d)}"/>{flecks}</g></svg></div>')


def _split_hi(text):
    """„Burgery **na rohu**“ → („Burgery“, „na rohu“)."""
    m = re.search(r"\*\*(.+?)\*\*", text or "")
    if not m:
        return (text or "").strip(), ""
    return re.sub(r"\s+", " ", (text[:m.start()] + text[m.end():])).strip(), m.group(1).strip()


def _nav(x):
    nav = [("o-nas", "O nás")]
    if x["offer"]:
        nav.append(("nabidka", x["t"]["offer_nav"]))
    if x["gallery"]:
        nav.append(("fotky", "Fotky"))
    if x["reviews"] or x["ratings"]:
        nav.append(("recenze", "Recenze"))
    nav.append(("kontakt", "Kontakt"))
    return nav


def _socials_html(x, cls="socs"):
    return "" if not x["socials"] else f'<div class="{cls}">' + "".join(
        f'<a href="{e(u)}" target="_blank" rel="noopener">{e(l)}</a>' for l, u in x["socials"]) + "</div>"


def _person(c, cls="person"):
    if not (c.get("person") or c.get("photo")):
        return ""
    return (f'<div class="{cls}">' + (f'<img src="img/{e(c["photo"])}" alt="{e(c.get("photo_alt"))}" loading="lazy">' if c.get("photo") else "")
            + f'<div><b>{e(c.get("person"))}</b><span>{e(c.get("role"))}</span></div></div>')


def _foot_line(d, x):
    co = d.get("company") or {}
    return (f'{e(co.get("legal_name") or x["name"])}{(" · IČO " + e(co.get("ico"))) if co.get("ico") else ""}'
            f'{(" · " + e(co.get("address"))) if co.get("address") else ""}')


# =====================================================================================  6 · URBAN

URBAN_CSS = """
body { margin:0; background:#fff; color:var(--k); font:16px/1.6 var(--body); -webkit-font-smoothing:antialiased; overflow-x:clip; }
a { text-decoration:none; }
.up { font-family:var(--display); font-weight:var(--dw); text-transform:uppercase; line-height:.9; letter-spacing:-.02em; }
.scr { font-family:var(--script); font-weight:400; text-transform:none; letter-spacing:0; line-height:.8; color:var(--y);
  text-shadow:2px 2px 0 var(--k), 0 4px 18px rgba(0,0,0,.25); }
.lbl { font:700 11px var(--body); letter-spacing:.16em; text-transform:uppercase; }
.yel { background:var(--noise), var(--y); }
.bw { filter:grayscale(1) contrast(1.15); }
.bx { display:inline-flex; align-items:center; gap:8px; min-height:44px; padding:0 18px; border:1.5px solid var(--k); font:700 12px var(--body);
  letter-spacing:.12em; text-transform:uppercase; color:var(--k); background:transparent; transition:background .2s, color .2s; }
.bx:hover, .bx.fill { background:var(--k); color:var(--y); }
.bx.fill:hover { background:var(--y); color:var(--k); }
.top { position:sticky; top:0; z-index:30; display:flex; align-items:center; gap:18px; padding:12px 18px; background:rgba(255,255,255,.94);
  backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); border-bottom:1px solid #eee; }
.logo { padding:6px 9px 5px; font-size:17px; max-width:11ch; }
.top nav { display:none; gap:26px; margin-left:auto; }
.top nav a:hover { text-decoration:underline; text-decoration-thickness:3px; text-decoration-color:var(--y); text-underline-offset:5px; }
.top .bx { margin-left:auto; min-height:38px; padding:0 14px; }
.hero { position:relative; padding:26px 0 56px; }
.hero-y { position:absolute; top:0; right:0; width:70%; height:68%; }
.hero-ph { position:relative; margin:0 0 0 18px; width:80%; aspect-ratio:4/5; overflow:hidden; background:#ddd; }
.hero-ph img, .hero-ph .hv { width:100%; height:100%; object-fit:cover; }
.hero h1 { position:relative; z-index:2; margin:-46px 18px 0; font-size:clamp(30px, var(--fm, 14.5vw), 168px); line-height:1.02; }
.hero h1 .scr { position:absolute; left:4%; bottom:calc(100% - 10px); font-size:clamp(70px, 21vw, 210px); transform:rotate(-8deg); white-space:nowrap; }
.hero-meta { margin:22px 18px 0; display:grid; gap:18px; max-width:520px; }
.hero-meta p { margin:0; font-size:17px; }
.live { display:inline-flex; align-items:center; gap:8px; }
.live i { background:#999 !important; }
.live.open i { background:var(--k) !important; box-shadow:0 0 0 4px var(--y); }
.hero .btns { display:flex; flex-wrap:wrap; gap:10px; }
.rate-line { display:flex; flex-wrap:wrap; gap:6px 16px; align-items:center; }
.rate-line a, .rate-line span.r { display:inline-flex; align-items:center; gap:7px; font-weight:700; }
.statement { padding:70px 18px 40px; max-width:1240px; margin:0 auto; position:relative; }
.statement h2 { font-size:clamp(30px, 6.6vw, 74px); margin:14px 0 26px; max-width:20ch; }
.statement h2 .y { background:linear-gradient(transparent 58%, var(--y) 58% 92%, transparent 92%); }
.statement .arrow { font:400 54px/1 var(--body); }
.statement .txt { max-width:58ch; font-size:16px; color:#333; }
.statement .txt p { margin:0 0 1em; }
.statement .txt h3 { font:var(--dw) 20px var(--display); text-transform:uppercase; margin:1.2em 0 .3em; }
.why { padding:30px 0 70px; position:relative; }
.why h2 { font-size:clamp(64px, 18vw, 200px); margin:0 18px -.12em; position:relative; z-index:0; color:var(--y);
  -webkit-text-stroke:2px var(--k); paint-order:stroke fill; }
.cards { position:relative; z-index:1; display:flex; gap:16px; overflow-x:auto; padding:0 18px 10px; scroll-snap-type:x mandatory; scrollbar-width:none; }
.cards::-webkit-scrollbar { display:none; }
.cards.dragging { cursor:grabbing; scroll-snap-type:none; }
.card { flex:none; width:min(76vw, 360px); scroll-snap-align:start; }
.card .ph { position:relative; aspect-ratio:4/5; overflow:hidden; background:var(--y); }
.card .ph img { width:100%; height:100%; object-fit:cover; pointer-events:none; user-select:none; }
.card .scr { position:absolute; left:10px; bottom:14px; font-size:clamp(46px, 11vw, 64px); transform:rotate(-6deg); max-width:94%; }
.card .ph.noimg .scr { color:var(--k); text-shadow:none; }
.card p { margin:14px 2px 0; font-size:15px; }
.menu-sec { position:relative; padding:70px 18px; }
.menu-in { max-width:1000px; margin:0 auto; }
.menu-sec h2 { font-size:clamp(72px, 20vw, 210px); margin:0 0 6px; }
.menu-sec .note { margin:0 0 28px; }
.tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px; }
.tabs button { min-height:40px; padding:0 16px; border:1.5px solid var(--k); background:transparent; font:700 12px var(--body); letter-spacing:.12em; text-transform:uppercase; cursor:pointer; color:var(--k); }
.tabs button.on { background:var(--k); color:var(--y); }
.mi { display:flex; justify-content:space-between; align-items:baseline; gap:16px; padding:16px 0; border-bottom:2px solid var(--k); }
.mi > span:first-child { font:var(--dw) 19px/1.15 var(--display); text-transform:uppercase; }
.mi small { display:block; font:500 14px var(--body); text-transform:none; margin-top:4px; }
.mi .pr { font:var(--dw) 19px var(--display); white-space:nowrap; }
.gal { position:relative; padding:80px 0 60px; overflow:hidden; }
.gal .ghost { position:absolute; top:30px; left:10px; font-size:clamp(110px, 30vw, 360px); color:transparent; -webkit-text-stroke:2px var(--k); opacity:.9; white-space:nowrap; pointer-events:none; }
.strip { position:relative; display:flex; gap:18px; overflow-x:auto; align-items:center; padding:40px 18px 20px; scroll-snap-type:x mandatory; scrollbar-width:none; cursor:grab; }
.strip::-webkit-scrollbar { display:none; }
.strip.dragging { cursor:grabbing; scroll-snap-type:none; }
.shot { flex:none; width:min(72vw, 340px); padding:0; border:0; background:none; cursor:zoom-in; scroll-snap-align:center; }
.shot:nth-child(3n+2) { width:min(62vw, 280px); margin-top:60px; }
.shot:nth-child(3n) { width:min(80vw, 380px); }
.shot img { width:100%; aspect-ratio:4/5; object-fit:cover; filter:grayscale(1) contrast(1.15); transition:filter .5s; pointer-events:none; }
.shot.sq img { aspect-ratio:1/1; }
.shot:hover img { filter:none; }
.shot span { display:block; text-align:left; margin-top:8px; }
.revs { padding:70px 18px 80px; max-width:1240px; margin:0 auto; display:grid; gap:40px; }
.big { font-size:clamp(110px, 30vw, 220px); line-height:.8; display:inline-block; background:linear-gradient(transparent 62%, var(--y) 62%); }
.revs .src { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:12px; font-weight:700; }
.revs .blogo { height:16px; }
.qs { display:grid; gap:34px; }
.q { margin:0; position:relative; padding-left:54px; }
.q::before { content:"„"; position:absolute; left:0; top:-26px; font:400 110px/1 var(--script); color:var(--y); text-shadow:2px 2px 0 var(--k); }
.q p { margin:0 0 10px; font:600 clamp(19px, 2.4vw, 24px)/1.35 var(--body); }
.contact { position:relative; padding:80px 18px 70px; overflow:hidden; }
.contact-in { max-width:1240px; margin:0 auto; position:relative; }
.contact h2 { position:relative; font-size:clamp(70px, 19vw, 220px); color:#fff; margin:0 0 30px; }
.contact h2 .scr { position:absolute; left:28%; top:58%; font-size:.62em; color:var(--k); text-shadow:none; transform:rotate(-7deg); white-space:nowrap; }
.cgrid { display:grid; gap:36px; }
.tel { display:block; font-size:clamp(34px, 9vw, 60px); margin:8px 0 10px; }
.cgrid a:hover { text-decoration:underline; }
.hours th, .hours td { padding:8px 0; border-bottom:1.5px solid var(--k); }
.hours tr.now th, .hours tr.now td { font-weight:800; }
.person { display:flex; align-items:center; gap:14px; margin-bottom:16px; }
.person img { width:76px; height:76px; object-fit:cover; filter:grayscale(1) contrast(1.15); }
.person b { display:block; font:var(--dw) 18px var(--display); text-transform:uppercase; }
.socs { display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }
.socs a { min-height:38px; padding:0 14px; display:inline-flex; align-items:center; border:1.5px solid currentColor; font:700 12px var(--body); letter-spacing:.12em; text-transform:uppercase; }
.map { height:340px; filter:grayscale(1) contrast(1.1); }
.foot { background:var(--k); color:#bbb; padding:40px 18px; display:grid; gap:20px; font-size:13px; }
.foot .logo { display:inline-block; color:var(--k); font-size:26px; }
.foot .socs a { color:#fff; }
@media (min-width: 900px) {
  .top { padding:14px 48px; } .top nav { display:flex; } .top .bx { margin-left:20px; }
  .hero { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr auto; padding:40px 48px 90px; min-height:min(92vh, 980px); }
  .hero-y { width:44%; height:100%; }
  .hero-ph { grid-column:2; grid-row:1 / span 2; margin:0 0 0 -8%; width:100%; max-width:640px; justify-self:end; align-self:center; }
  .hero h1 { grid-column:1 / span 2; grid-row:1; margin:0; align-self:end; max-width:60vw; font-size:clamp(44px, var(--fd, 11.5vw), 210px); }
  .hero h1 .scr { left:18%; }
  .hero-meta { grid-column:1; grid-row:2; margin:30px 0 0; position:relative; z-index:2; }
  .hero-meta p, .hero .rate-line { font-size:16px; }
  .statement { padding:130px 48px 60px; display:grid; grid-template-columns:120px 1fr; column-gap:40px; }
  .statement .lbl { grid-column:1 / span 2; }
  .statement .txt { grid-column:2; columns:2; column-gap:48px; max-width:none; }
  .why { padding:60px 0 120px; } .why h2 { margin:0 48px -.14em; font-size:clamp(90px, 11vw, 180px); }
  .cards { padding:0 48px 10px; } .card { width:calc((min(100vw, 1440px) - 96px - 32px) / 3); }
  .card:nth-child(2) { margin-top:70px; } .card:nth-child(3) { margin-top:20px; }
  .menu-sec { padding:120px 48px; }
  .menu-in > div[data-tabs] > div[data-pane]:not([hidden]) { display:grid; grid-template-columns:1fr 1fr; column-gap:60px; }
  .strip { padding:40px 48px 20px; }
  .revs { grid-template-columns:auto 1fr; gap:80px; padding:120px 48px; align-items:start; }
  .contact { padding:120px 48px 100px; }
  .cgrid { grid-template-columns:1.2fr 1fr; gap:80px; }
  .map { height:460px; }
  .foot { padding:46px 48px; grid-template-columns:auto 1fr auto; align-items:center; }
}
"""


def render_urban(d, x, banner):
    c = x["c"]
    hero = x["hero"]
    main, hi = _split_hi(hero.get("title") or x["name"])
    th = d.get("theme") or {}
    yel = th["accent"] if re.fullmatch(r"#[0-9a-fA-F]{6}", th.get("accent") or "") else "#FFE500"
    media = x["video_tag"] or (f'<img class="bw" src="{e(x["hero_img"])}" alt="{e(hero.get("alt") or x["name"])}" fetchpriority="high">'
                               if x["hero_img"] else "")
    nav = _nav(x)
    rates = ""
    for r in x["ratings"]:
        inner = f'{_stars(r["value"], 13)} {_cz(r["value"])} {_brand(r, 14)}' + (f' · {e(_count(r["count"]))}' if r["count"] else "")
        rates += (f'<a href="{e(r["url"])}" target="_blank" rel="noopener">{inner}</a>' if r["url"] else f'<span class="r">{inner}</span>')

    hero_html = (
        f'<section class="hero" id="top"><div class="hero-y yel"></div>'
        f'<figure class="hero-ph" style="clip-path:{_torn_clip(7, 2.2)}; margin-top:0">{media}</figure>'
        f'<h1 class="up" style="{_fit(main, 14.5, 11.5, .8, 88, 56)}">{e(main)}' + (f' <span class="scr">{e(hi)}</span>' if hi else "") + "</h1>"
        '<div class="hero-meta"><span class="lbl live"><i></i><span class="lt">Otevírací doba</span></span>'
        + (f'<div class="rate-line">{rates}</div>' if rates else "")
        + '<div class="btns">' + (f'<a class="bx fill" href="tel:{x["tel"]}">Zavolat ↗</a>' if x["tel"] else "")
        + '<a class="bx" href="#kontakt">Kde nás najdete</a></div></div></section>')

    stmt = hero.get("subtitle") or ""
    words = stmt.split()
    if len(words) > 3:   # zvýrazní žlutou linkou prostřední část věty
        a, b = len(words) // 3, 2 * len(words) // 3
        stmt_html = e(" ".join(words[:a])) + ' <span class="y">' + e(" ".join(words[a:b])) + "</span> " + e(" ".join(words[b:]))
    else:
        stmt_html = e(stmt)
    statement = ""
    if stmt or (d.get("about") or "").strip():
        statement = (f'<section class="statement" id="o-nas"><span class="lbl">— {e((d.get("extra") or {}).get("intro_title") or "O nás")}</span>'
                     f'<span class="arrow" aria-hidden="true">↘</span><div>'
                     + (f'<h2 class="up">{stmt_html}</h2>' if stmt else "")
                     + f'<div class="txt">{rich(d.get("about"))}</div></div></section>')
    else:
        statement = '<span id="o-nas"></span>'

    gal = x["gallery"]
    n = len(gal)
    why = ""
    if x["usps"]:
        cards = ""
        for i, u in enumerate(x["usps"]):
            g = gal[(i + 1) % n] if n else None
            img = f'<img class="bw" src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy" draggable="false">' if g else ""
            cards += (f'<article class="card"><div class="ph{"" if g else " noimg yel"}" style="clip-path:{_torn_clip(20 + i, 1.8)}">{img}'
                      f'<span class="scr">{e(u["title"])}</span></div>' + (f'<p>{e(u.get("text"))}</p>' if u.get("text") else "") + "</article>")
        why = f'<section class="why"><h2 class="up" aria-label="Proč k nám">Proč k nám</h2><div class="cards drag-x">{cards}</div></section>'

    menu = ""
    if x["offer"]:
        menu = (f'<section class="menu-sec yel" id="nabidka"><div class="menu-in"><h2 class="up">{e(x["t"]["offer_nav"])}</h2>'
                + f'<p class="lbl note">{e(d.get("offer_title") or "")}{(" · " + e(d.get("booking_note"))) if d.get("booking_note") else ""}</p>'
                + _offer_tabs(x, "mi") + "</div></section>")

    gallery = "" if not gal else (
        '<section class="gal" id="fotky"><div class="ghost up" aria-hidden="true">Fotky</div><div class="strip drag-x">'
        + "".join(f'<button class="shot {_fmt(d, g["file"])}" data-lb="{i}" aria-label="Zvětšit: {e(g.get("alt"))}" style="clip-path:{_torn_clip(40 + i, 1.6)}">'
                  f'<img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy" draggable="false"></button>'
                  for i, g in enumerate(gal)) + "</div></section>")
    video = (f'<section style="padding:0 18px 60px;max-width:1240px;margin:0 auto"><div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{x["yt"]}" '
             f'title="Video – {e(x["name"])}" loading="lazy" allowfullscreen></iframe></div></section>') if x["yt"] else ""

    revs = ""
    if x["reviews"] or x["ratings"]:
        left = ""
        if x["ratings"]:
            r0 = x["ratings"][0]
            left = (f'<div><span class="lbl">— Hodnocení</span><br><span class="big up">{_cz(r0["value"])}</span>'
                    f'<div class="src">{_stars(r0["value"], 18)} {_brand(r0, 16)}' + (f' · {e(_count(r0["count"]))}' if r0["count"] else "") + "</div>"
                    + (f'<p><a class="bx" href="{e(r0["url"])}" target="_blank" rel="noopener" style="margin-top:16px">Všechny recenze ↗</a></p>' if r0["url"] else "")
                    + "</div>")
        qs = "".join(f'<blockquote class="q"><p>{e(r["text"])}</p><span class="lbl">{e(r.get("author"))}'
                     + (f' · {e(r.get("source"))}' if r.get("source") else "") + "</span></blockquote>" for r in x["reviews"])
        revs = f'<section class="revs" id="recenze">{left}<div class="qs">{qs}</div></section>'

    contact = (f'<section class="contact yel" id="kontakt"><div class="contact-in"><h2 class="up">Kontakt <span class="scr">zastavte se</span></h2>'
               f'<div class="cgrid"><div>{_person(c)}'
               + (f'<a class="tel up" href="tel:{x["tel"]}">{e(c.get("phone"))}</a>' if x["tel"] else "")
               + (f'<p><a href="mailto:{e(c["email"])}"><b>{e(c["email"])}</b></a></p>' if c.get("email") else "")
               + f'<p>{e(c.get("address"))}</p><a class="bx" href="{e(x["maps"])}" target="_blank" rel="noopener">Navigovat ↗</a>{_socials_html(x)}</div>'
               + f'<div><span class="lbl">— Otevírací doba</span><table class="hours" style="margin-top:12px">{_hours_rows(x)}</table>'
               + (f'<p>{e(d.get("hours_note"))}</p>' if d.get("hours_note") else "") + "</div></div></div></section>")

    root = _root(x, f"--y:{yel}; --k:#0d0d0d; --script:'Mr Dafoe', cursive; --noise:{NOISE_DARK};")
    return (_head(d, x, (("Mr Dafoe", ["400"]),)) + "<style>" + root + COMMON_CSS + URBAN_CSS + "</style></head>\n"
            f'<body class="t-urban">{banner}<header class="top"><a class="logo up yel" href="#top">{e(x["logo_text"])}</a>'
            '<nav aria-label="Menu">' + "".join(f'<a class="lbl" href="#{a}">{e(l)}</a>' for a, l in nav) + "</nav>"
            + (f'<a class="bx" href="tel:{x["tel"]}">Zavolat ↗</a>' if x["tel"] else "") + "</header>"
            + hero_html + statement + why + menu + gallery + video + revs + contact + x["map_html"]
            + f'<footer class="foot"><span class="logo up yel">{e(x["logo_text"])}</span><span>{_foot_line(d, x)}</span>{_socials_html(x)}</footer>'
            + _lightbox(gal) + _script(x) + "</body></html>")


# =====================================================================================  7 · ŠTĚTEC

BRUSH_CSS = """
body { margin:0; background:var(--gray); color:#1a1a1a; font:17px/1.6 var(--body); -webkit-font-smoothing:antialiased; overflow-x:clip; }
a { text-decoration:none; }
h1, h2, h3, .num { font-family:var(--display); font-weight:var(--dw); letter-spacing:-.01em; }
.pillb { display:inline-flex; align-items:center; justify-content:center; gap:10px; min-height:50px; padding:0 30px; border-radius:999px; font:700 16px var(--body);
  background:var(--yel); color:#fff; box-shadow:0 10px 26px color-mix(in srgb, var(--yel) 45%, transparent); transition:transform .2s; }
.pillb:hover { transform:translateY(-2px); }
.pillb.out { background:transparent; box-shadow:inset 0 0 0 2px #fff; }
.pillb.dark { background:#111; box-shadow:none; }
.edge { position:absolute; left:0; right:0; top:-60px; height:62px; pointer-events:none; z-index:2; }
.edge svg { display:block; width:100%; height:100%; }
.edge.flip { top:-1px; }
.top { position:sticky; top:0; z-index:30; display:flex; align-items:center; gap:24px; padding:14px 18px; background:#090909; color:#fff; }
.logo { line-height:1; }
.logo b { display:block; font:var(--dw) 25px/1 var(--display); }
.logo small { display:block; font-size:10px; letter-spacing:.55em; text-transform:lowercase; opacity:.8; margin-top:4px; }
.top nav { display:none; gap:20px; margin-left:auto; font-weight:700; font-size:15px; }
.top nav a:hover { color:var(--yel); }
.top .tel { margin-left:auto; display:inline-flex; align-items:center; gap:10px; min-height:44px; padding:0 18px 0 6px; border-radius:999px;
  background:var(--yel); color:#111; font-weight:700; font-size:16px; white-space:nowrap; box-shadow:0 6px 20px color-mix(in srgb, var(--yel) 40%, transparent); transition:transform .2s; }
.top .tel:hover { transform:translateY(-1px); background:#fff; }
.top .tel .ti { width:34px; height:34px; border-radius:50%; background:#111; color:var(--yel); display:grid; place-items:center; }
.top .tel .ti svg { width:18px; height:18px; }
@media (max-width: 420px) { .top .tel { font-size:15px; padding-right:14px; } }
.hero { position:relative; min-height:88svh; overflow:hidden; color:#fff; display:flex; align-items:flex-end; background:var(--grad); }
.hero .duo { position:absolute; inset:0; }
.hero .duo img, .hero .duo .hv { width:100%; height:100%; object-fit:cover; filter:grayscale(1) contrast(1.15) brightness(1.08); mix-blend-mode:multiply; }
.hero::before { content:""; position:absolute; inset:0; background:linear-gradient(90deg, color-mix(in srgb, var(--red) 75%, transparent), transparent 70%); z-index:1; }
.hero-in { position:relative; z-index:3; padding:0 18px 110px; max-width:1240px; width:100%; margin:0 auto; }
.live { display:inline-flex; align-items:center; gap:8px; font-weight:700; font-size:14px; background:rgba(0,0,0,.22); padding:6px 14px; border-radius:999px; margin-bottom:18px; }
.live.open i { background:#7CFF9B; }
.hero h1 { font-size:clamp(34px, var(--fm, 13vw), 140px); line-height:1; margin:0 0 24px; max-width:16ch; text-wrap:balance; }
.hero p { font-size:clamp(18px, 2.2vw, 21px); margin:0 0 34px; max-width:36ch; }
.btns { display:flex; flex-wrap:wrap; gap:16px; }
.sec { position:relative; }
.stats { background:var(--gray); padding:80px 18px 110px; }
.stats-in { max-width:1200px; margin:0 auto; display:grid; grid-template-columns:1fr 1fr; gap:46px 20px; text-align:center; }
.num { font-size:clamp(46px, 9vw, 64px); line-height:1; }
.stats h3 { font-size:22px; margin:12px 0 6px; }
.stats p { margin:0; font-size:14px; }
.about { background:var(--yel); padding:70px 0 0; }
.about-in { max-width:1300px; margin:0 auto; display:grid; }
.about-ph { position:relative; background:var(--yel); min-height:380px; overflow:hidden; order:2; }
.about-ph img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center top; filter:grayscale(1) contrast(1.1); mix-blend-mode:multiply; }
.about-tx { padding:20px 18px 60px; }
.about h2 { font-size:clamp(40px, 7vw, 64px); line-height:1.05; margin:0 0 22px; }
.rule { display:flex; align-items:center; gap:16px; margin:0 0 26px; }
.rule i { width:7px; height:7px; border-radius:50%; background:var(--red); }
.rule span { width:76px; height:1.5px; background:rgba(0,0,0,.3); }
.about-tx p { margin:0 0 1em; }
.about-tx p:first-child { font-size:19px; }
.socs { display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }
.socs a { min-height:40px; padding:0 18px; border-radius:999px; background:#fff; display:inline-flex; align-items:center; font-weight:700; font-size:14px; }
.socs a:hover { background:#111; color:#fff; }
.usps { background:#fff; padding:90px 18px 100px; }
.usps-in { max-width:1200px; margin:0 auto; display:grid; gap:36px; }
.usp { display:grid; grid-template-columns:56px 1fr; gap:6px 18px; }
.usp .dot { grid-row:span 2; width:56px; height:56px; border-radius:50%; background:var(--grad); color:#fff; display:grid; place-items:center; font:var(--dw) 24px var(--display); }
.usp h3 { font-size:24px; margin:4px 0 0; }
.usp p { margin:0; color:#555; }
.menu { background:#fff; padding:0 18px 110px; }
.menu-in { max-width:900px; margin:0 auto; }
.ctr { text-align:center; }
.h2c { font-size:clamp(40px, 7vw, 60px); line-height:1.05; margin:0 0 12px; }
.sub { color:#666; margin:0 0 30px; }
.tabs { display:flex; justify-content:center; flex-wrap:wrap; gap:8px; margin-bottom:26px; }
.tabs button { min-height:42px; padding:0 20px; border-radius:999px; border:2px solid #e3e3e3; background:#fff; font:700 15px var(--body); cursor:pointer; }
.tabs button.on { background:var(--red); border-color:var(--red); color:#fff; }
.mi { display:flex; align-items:baseline; gap:12px; padding:16px 0; border-bottom:1px solid #ececec; }
.mi > span:first-child { font:var(--dw) 22px/1.2 var(--display); }
.mi small { display:block; font:400 14px var(--body); color:#777; }
.mi .pr { margin-left:auto; font-weight:700; color:var(--red); white-space:nowrap; }
.gal { background:#0d0d0d; color:#fff; padding:90px 0 110px; }
.gal .h2c { padding:0 18px; }
.gal .sub { color:#aaa; padding:0 18px; }
.track { display:flex; gap:16px; overflow-x:auto; padding:10px 18px 10px; scroll-snap-type:x mandatory; scrollbar-width:none; cursor:grab; }
.track::-webkit-scrollbar { display:none; }
.track.dragging { cursor:grabbing; scroll-snap-type:none; }
.track button { flex:none; width:min(74vw, 360px); padding:0; border:0; background:none; cursor:zoom-in; scroll-snap-align:center; overflow:hidden; }
.track img { width:100%; aspect-ratio:4/5; object-fit:cover; transition:transform .6s; pointer-events:none; }
.track button.sq img { aspect-ratio:1/1; }
.track button:hover img { transform:scale(1.04); }
.revs { background:var(--grad); color:#fff; padding:100px 18px 120px; text-align:center; }
.revs .num { font-size:clamp(70px, 14vw, 120px); }
.revs .src { display:flex; justify-content:center; flex-wrap:wrap; align-items:center; gap:8px; font-weight:700; margin:8px 0 40px; }
.revs .blogo { height:16px; background:#fff; padding:3px 6px; border-radius:4px; box-sizing:content-box; }
.revs .stars .s-bg { opacity:.35; }
.qs { display:flex; gap:20px; overflow-x:auto; scroll-snap-type:x mandatory; scrollbar-width:none; max-width:1100px; margin:0 auto; padding-bottom:6px; }
.qs::-webkit-scrollbar { display:none; }
.q { flex:none; width:100%; scroll-snap-align:center; margin:0; }
.q p { font:var(--dw) clamp(26px, 4vw, 40px)/1.2 var(--display); margin:0 auto 18px; max-width:28ch; }
.q span { font-weight:700; opacity:.9; }
.contact { background:var(--gray); padding:100px 18px 90px; }
.contact-in { max-width:1200px; margin:0 auto; display:grid; gap:44px; }
.contact h2 { font-size:clamp(40px, 7vw, 60px); line-height:1.05; margin:0 0 20px; }
.big { display:block; font:var(--dw) clamp(30px, 6vw, 44px)/1.15 var(--display); margin:6px 0; overflow-wrap:anywhere; }
.big:hover { color:var(--red); }
.person { display:flex; align-items:center; gap:16px; margin-bottom:20px; }
.person img { width:72px; height:72px; border-radius:50%; object-fit:cover; }
.person b { display:block; font:var(--dw) 22px var(--display); }
.person span { color:#666; font-size:15px; }
.card { background:#fff; border-radius:20px; padding:24px 26px; box-shadow:0 16px 40px rgba(0,0,0,.06); }
.hours th, .hours td { padding:9px 0; border-bottom:1px solid #eee; }
.hours tr.now th, .hours tr.now td { color:var(--red); }
.map { height:360px; filter:grayscale(.2); }
.foot { background:#090909; color:#999; padding:40px 18px; font-size:14px; display:grid; gap:18px; }
.foot .logo { color:#fff; }
.foot .socs a { background:#1c1c1c; color:#fff; }
@media (min-width: 900px) {
  .top { padding:18px max(48px, calc((100vw - 1240px) / 2)); } .top nav { display:flex; } .top .tel { margin-left:28px; font-size:18px; min-height:50px; }
  .hero .duo { left:42%; }
  .hero .duo img, .hero .duo .hv { -webkit-mask-image:linear-gradient(90deg, transparent, #000 30%); mask-image:linear-gradient(90deg, transparent, #000 30%); }
  .hero::before { display:none; }
  .hero-in { padding:0 48px 160px; }
  .hero h1 { font-size:clamp(48px, var(--fd, 9vw), 140px); }
  .edge { top:-88px; height:90px; }
  .edge.flip { top:-1px; }
  .stats { padding:110px 48px 150px; } .stats-in { grid-template-columns:repeat(4, 1fr); }
  .about { padding-top:80px; }
  .about-in { grid-template-columns:1fr 1fr; align-items:end; }
  .about-ph { order:0; min-height:620px; }
  .about-tx { padding:40px 48px 120px 60px; align-self:center; }
  .usps { padding:130px 48px; } .usps-in { grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:48px; }
  .menu { padding:0 48px 140px; }
  .gal { padding:130px 0 150px; } .track { padding:10px max(48px, calc((100vw - 1240px) / 2)); }
  .revs { padding:140px 48px 160px; }
  .contact { padding:140px 48px 110px; } .contact-in { grid-template-columns:1.1fr 1fr; gap:80px; align-items:start; }
  .map { height:460px; }
  .foot { padding:44px max(48px, calc((100vw - 1240px) / 2)); grid-template-columns:auto 1fr auto; align-items:center; }
}
"""


def render_brush(d, x, banner):
    c = x["c"]
    hero = x["hero"]
    th = d.get("theme") or {}
    red = th["accent"] if re.fullmatch(r"#[0-9a-fA-F]{6}", th.get("accent") or "") else "#E5161B"
    gal = x["gallery"]
    nav = _nav(x)
    media = x["video_tag"] or (f'<img src="{e(x["hero_img"])}" alt="{e(hero.get("alt") or x["name"])}" fetchpriority="high">'
                               if x["hero_img"] else "")
    kind_lbl = x["t"]["label"].split("/")[0].strip().lower()
    h1 = re.sub(r"[*][*](.+?)[*][*]", r"\1", hero.get("title") or "")

    hero_html = (f'<section class="hero" id="top"><div class="duo">{media}</div><div class="hero-in">'
                 '<span class="live"><i></i><span class="lt">Otevírací doba</span></span>'
                 f'<h1 style="{_fit(h1 or x["name"], 13, 9, .5, 88, 55)}">{e(h1 or x["name"])}</h1>'
                 + (f'<p>{e(hero.get("subtitle"))}</p>' if hero.get("subtitle") else "")
                 + '<div class="btns">' + (f'<a class="pillb" href="tel:{x["tel"]}">Zavolat</a>' if x["tel"] else "")
                 + '<a class="pillb out" href="#kontakt">▸ Kde nás najdete</a></div></div></section>')

    stats = [s for s in d.get("stats") or [] if (s.get("value") or "").strip()] or default_stats(d, x)
    stats_html = ""
    if stats:
        stats_html = (f'<section class="sec stats">{_edge("var(--gray)", 3)}<div class="stats-in">' + "".join(
            f'<div><div class="num">{e(s["value"])}</div><h3>{e(s.get("label"))}</h3>'
            + (f'<p>{e(s.get("note"))}</p>' if s.get("note") else "") + "</div>" for s in stats[:4]) + "</div></section>")

    ph = c.get("photo") or (gal[0]["file"] if gal else "")
    ph_alt = c.get("photo_alt") if c.get("photo") else (gal[0].get("alt") if gal else "")
    intro_t = ((d.get("extra") or {}).get("intro_title") or "").strip() or "O nás"
    about = (f'<section class="sec about" id="o-nas">{_edge("var(--yel)", 11)}<div class="about-in">'
             + (f'<div class="about-ph"><img src="img/{e(ph)}" alt="{e(ph_alt)}" loading="lazy"></div>' if ph else "")
             + f'<div class="about-tx"><h2>{e(intro_t)}</h2><div class="rule"><i></i><span></span></div>{rich(d.get("about"))}{_socials_html(x)}</div>'
             + "</div></section>")

    usps = "" if not x["usps"] else (
        f'<section class="sec usps">{_edge("#fff", 17)}<div class="usps-in">' + "".join(
            f'<div class="usp"><span class="dot">{i + 1}</span><h3>{e(u["title"])}</h3><p>{e(u.get("text"))}</p></div>'
            for i, u in enumerate(x["usps"])) + "</div></section>")

    menu = ""
    if x["offer"]:
        menu = (f'<section class="sec menu" id="nabidka"' + ("" if usps else ' style="padding-top:100px"') + ">"
                + ("" if usps else _edge("#fff", 17))
                + f'<div class="menu-in"><h2 class="h2c ctr">{e(d.get("offer_title") or x["t"]["offer_title"])}</h2>'
                + (f'<p class="sub ctr">{e(d.get("booking_note"))}</p>' if d.get("booking_note") else "")
                + _offer_tabs(x, "mi") + "</div></section>")

    gallery = "" if not gal else (
        f'<section class="sec gal" id="fotky">{_edge("#0d0d0d", 23)}<h2 class="h2c ctr">Fotky</h2><p class="sub ctr">Posuňte do strany, klepnutím zvětšíte.</p>'
        '<div class="track drag-x">' + "".join(
            f'<button class="{_fmt(d, g["file"])}" data-lb="{i}" aria-label="Zvětšit: {e(g.get("alt"))}"><img src="img/{e(g["file"])}" alt="{e(g.get("alt"))}" loading="lazy" draggable="false"></button>'
            for i, g in enumerate(gal)) + "</div></section>")
    video = (f'<section class="sec" style="background:#0d0d0d;padding:0 18px 110px"><div class="video" style="max-width:1100px;margin:0 auto">'
             f'<iframe src="https://www.youtube-nocookie.com/embed/{x["yt"]}" title="Video – {e(x["name"])}" loading="lazy" allowfullscreen></iframe></div></section>') if x["yt"] else ""

    revs = ""
    if x["reviews"] or x["ratings"]:
        top = ""
        if x["ratings"]:
            r0 = x["ratings"][0]
            top = (f'<div class="num">{_cz(r0["value"])}</div><div class="src">{_stars(r0["value"], 20)} {_brand(r0, 16)}'
                   + (f' · {e(_count(r0["count"]))}' if r0["count"] else "") + "</div>")
        qs = "".join(f'<blockquote class="q"><p>„{e(r["text"])}“</p><span>{e(r.get("author"))}</span></blockquote>' for r in x["reviews"])
        prev = "#0d0d0d" if (gal or x["yt"]) else ("#fff" if (x["offer"] or x["usps"]) else "var(--yel)")
        revs = (f'<section class="sec revs" id="recenze">{_edge(prev, 29, flip=True)}{top}'
                + (f'<div class="qs drag-x" id="qs">{qs}</div>' if qs else "")
                + (('<div class="dots" data-dots="qs" style="display:flex;gap:8px;justify-content:center;margin-top:26px">'
                    + "".join('<button aria-label="Recenze" style="width:9px;height:9px;border-radius:50%;border:0;background:#fff;opacity:.5;padding:0;cursor:pointer"></button>'
                              for _ in x["reviews"]) + "</div><style>.dots button.on{opacity:1!important}</style>") if len(x["reviews"]) > 1 else "")
                + "</section>")

    contact = (f'<section class="sec contact" id="kontakt">{_edge("var(--gray)", 31)}<div class="contact-in"><div><h2>Zastavte se</h2>{_person(c)}'
               + (f'<a class="big" href="tel:{x["tel"]}">{e(c.get("phone"))}</a>' if x["tel"] else "")
               + (f'<a class="big" style="font-size:24px" href="mailto:{e(c["email"])}">{e(c["email"])}</a>' if c.get("email") else "")
               + f'<p>{e(c.get("address"))}</p><div class="btns"><a class="pillb" style="background:var(--red);box-shadow:none" href="{e(x["maps"])}" target="_blank" rel="noopener">Navigovat</a></div></div>'
               + f'<div class="card"><h3 style="margin:0 0 10px;font-size:24px">Otevírací doba</h3><table class="hours">{_hours_rows(x)}</table>'
               + (f'<p style="margin:12px 0 0;color:#666">{e(d.get("hours_note"))}</p>' if d.get("hours_note") else "") + "</div></div></section>")

    logo = f'<b>{e(x["logo_text"])}</b><small>{e(kind_lbl)}</small>'
    root = _root(x, f"--red:{red}; --yel:#F5C428; --gray:#F6F6F6; "
                    f"--grad:linear-gradient(115deg, {red} 0%, color-mix(in srgb, {red} 45%, #FF8A1F) 55%, #FFB321 100%);")
    return (_head(d, x) + "<style>" + root + COMMON_CSS + BRUSH_CSS + "</style></head>\n"
            f'<body class="t-brush">{banner}<header class="top"><a class="logo" href="#top">{logo}</a>'
            '<nav aria-label="Menu">' + "".join(f'<a href="#{a}">{e(l)}</a>' for a, l in nav) + "</nav>"
            + (f'<a class="tel" href="tel:{x["tel"]}"><span class="ti" aria-hidden="true">{PHONE_SVG}</span>{e(c.get("phone"))}</a>' if x["tel"] else "") + "</header>"
            + hero_html + stats_html + about + usps + menu + gallery + video + revs + contact
            + (f'<div class="sec">{x["map_html"]}</div>' if x["map_html"] else "")
            + f'<footer class="foot"><span class="logo">{logo}</span><span>{_foot_line(d, x)}</span>{_socials_html(x)}</footer>'
            + _lightbox(gal) + _script(x) + "</body></html>")
