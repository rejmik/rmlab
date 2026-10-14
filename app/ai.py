"""Návrhy textů webu: přes Claude API (když je v .env ANTHROPIC_API_KEY), jinak šablonové texty."""
import json
import os
import re

import httpx

from .sites import TYPES

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("LF_AI_MODEL", "claude-sonnet-5-5")


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _obec(d):
    m = re.search(r"\d{3}\s?\d{2}\s+(.+)$", d["contact"].get("address") or "")
    return m.group(1).split(",")[0].strip() if m else ""


PROMPT = """Jsi copywriter malé webové agentury RM Lab. Píšeš česky texty pro jednostránkový web místní provozovny.
Pravidla:
- Používej JEN fakta z podkladů. Co nevíš (roky praxe, počet zaměstnanců, ceny, speciality), si NEVYMÝŠLEJ –
  napiš místo toho [doplnit: co chybí].
- Píš přirozeně, srozumitelně, bez frází typu „jsme tu pro vás“ a bez superlativů. Vykej návštěvníkovi.
- SEO: v hlavním nadpisu, SEO titulku a popisku uveď typ provozovny a obec.

Vrať POUZE JSON tohoto tvaru:
{{"hero_title": "hlavní nadpis H1, 10–60 znaků",
 "hero_subtitle": "jedna věta pod nadpisem, do 110 znaků",
 "about": "text o firmě, 400–900 znaků, 2–3 odstavce oddělené prázdným řádkem; můžeš použít **tučně** a odrážky začínající '- '",
 "usps": [{{"title": "krátký benefit do 50 znaků", "text": "jedna věta"}}],
 "seo_title": "30–60 znaků, obsahuje obec",
 "seo_description": "120–155 znaků, obsahuje obec a výzvu k akci"}}
usps: 3–5 položek, jen z podkladů; když jich je v podkladech málo, doplň [doplnit: …].

Podklady:
{facts}"""


def _facts(d):
    t = TYPES[d["type"]]
    facts = {
        "typ provozovny": t["label"],
        "název": d["name"],
        "obec": _obec(d),
        "adresa": d["contact"]["address"],
        "otevírací doba": {h["day"]: h["value"] for h in d["hours"] if h["value"]},
        "nabídka": [f'{o.get("name")} {o.get("price") or ""}'.strip() for o in d["offer"] if o.get("name")][:30],
        "výhody zadané prodejcem": [u.get("title") for u in d["usps"] if u.get("title")],
        "poznámky prodejce o firmě": d.get("notes") or "",
        "kontaktní osoba": d["contact"]["person"],
    }
    return json.dumps(facts, ensure_ascii=False, indent=1)


async def suggest_claude(d: dict) -> dict:
    body = {"model": MODEL, "max_tokens": 2000,
            "messages": [{"role": "user", "content": PROMPT.format(facts=_facts(d))}]}
    headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(API_URL, json=body, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"Claude API {r.status_code}: {r.text[:300]}")
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("AI nevrátila platný JSON")
    return json.loads(m.group(0))


def suggest_template(d: dict) -> dict:
    t, name, obec = TYPES[d["type"]], d["name"] or "[doplnit: název]", _obec(d) or "[doplnit: obec]"
    label = {"kadernictvi": "Kadeřnictví", "kavarna": "Kavárna", "restaurace": "Restaurace"}[d["type"]]
    short = name if label.lower() in name.lower() else f"{label} {name}"
    about = {
        "kadernictvi": f"{short} najdete v obci {obec}. [doplnit: komu se věnujete – dámy, páni, děti – a čím jste známí].\n\n"
                       "Nabízíme **[doplnit: hlavní služby]**. Ceny najdete v ceníku níže, objednat se můžete telefonicky.\n\n"
                       "[doplnit: něco osobního – kdo v salonu pracuje, jak dlouho, na co jste hrdí]",
        "kavarna": f"{short} najdete v obci {obec}. [doplnit: jaká je u vás atmosféra a pro koho je kavárna ideální].\n\n"
                   "Připravujeme **[doplnit: kávu odkud, dezerty, snídaně…]**. Celou nabídku najdete níže.\n\n"
                   "[doplnit: něco osobního – příběh kavárny, majitel, zahrádka, akce]",
        "restaurace": f"{short} najdete v obci {obec}. [doplnit: jakou kuchyni vaříte a čím jste známí].\n\n"
                      "Nabízíme **[doplnit: polední menu, speciality, salonek…]**. Aktuální menu najdete níže.\n\n"
                      "[doplnit: něco osobního – kuchař, suroviny, historie podniku]",
    }[d["type"]]
    return {
        "hero_title": f"{short}, {obec}"[:70],
        "hero_subtitle": "[doplnit: jedna věta, čím jste jiní než ostatní]",
        "about": about,
        "usps": [{"title": f"[doplnit: výhoda – např. {ex}]", "text": ""} for ex in t["usp_examples"]],
        "seo_title": f"{short} – {obec}"[:60],
        "seo_description": f"{short} v obci {obec}. Otevírací doba, {t['offer_nav'].lower()}, fotky a kontakt. "
                           f"{t['booking']}.",
    }


async def suggest(d: dict) -> dict:
    if enabled():
        return {**await suggest_claude(d), "source": "ai"}
    return {**suggest_template(d), "source": "template"}
