"""Rychlé testy bez sítě: python -m pytest -q"""
import asyncio

import httpx

from app import places, webcheck
from app.scoring import score


def run(coro):
    return asyncio.run(coro)


def test_candidate_domains():
    assert webcheck.candidate_domains("Seznam.cz, a.s.")[0] == "seznam.cz"
    d = webcheck.candidate_domains("TRUHLÁŘSTVÍ DVOŘÁK spol. s r.o.")
    assert "truhlarstvidvorak.cz" in d and "truhlarstvi-dvorak.cz" in d
    d = webcheck.candidate_domains("Jan Novák - Instalatérství")
    assert "instalaterstvi-novak.cz" in d


def test_webcheck_finds_ico(monkeypatch):
    async def fake_resolves(domain):
        return domain == "truhlarstvidvorak.cz"
    monkeypatch.setattr(webcheck, "_resolves", fake_resolves)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"},
                              html="<html><body>Truhlářství Dvořák, IČO: 123 45 678</body></html>")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await webcheck.check(c, "12345678", "Truhlářství Dvořák s.r.o.")
    res = run(go())
    assert res["match"] == "ico" and "truhlarstvidvorak.cz" in res["url"]


def test_webcheck_parked(monkeypatch):
    async def fake_resolves(domain):
        return True
    monkeypatch.setattr(webcheck, "_resolves", fake_resolves)

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, html="<h1>Doména je na prodej</h1>")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await webcheck.check(c, "12345678", "Kadeřnictví Fiala")
    assert run(go())["match"] == "parked"


def test_places_match(monkeypatch):
    monkeypatch.setattr(places, "GOOGLE_API_KEY", "x")

    def handler(request):
        assert request.headers["X-Goog-Api-Key"] == "x"
        return httpx.Response(200, json={"places": [
            {"id": "A", "displayName": {"text": "Úplně jiná firma"}, "location": {"latitude": 50.16, "longitude": 14.75}},
            {"id": "B", "displayName": {"text": "Kadeřnictví Fiala"}, "location": {"latitude": 50.1601, "longitude": 14.7502},
             "nationalPhoneNumber": "777 111 222", "userRatingCount": 12, "businessStatus": "OPERATIONAL"},
        ]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await places.find_match(c, "Kadeřnictví Fiala", "Čelákovice", 50.16, 14.75)
    data, conf = run(go())
    assert data["place_id"] == "B" and data["phone"] == "777 111 222" and conf >= 0.9
    assert places.cached("B")["website"] is None


def test_scoring_directions():
    firm = {"ico": "1", "forma": "101", "katpo": "120", "nace": "43210", "datum_vzniku": "2015-01-01", "addr_count": 1}
    base = score(firm)
    no_site = score(firm, ares={"found": True, "dph": True}, web={"match": "none"}, google={"website": None, "status": "OPERATIONAL", "reviews": 20})
    has_site = score(firm, web={"match": "ico", "url": "https://x.cz"})
    shell = score({**firm, "addr_count": 300}, ares={"found": True, "dph": False, "insolvence": True})
    assert no_site["p_noweb"] > base["p_noweb"] > has_site["p_noweb"]
    assert no_site["vitality"] > base["vitality"] > shell["vitality"]
    assert has_site["p_noweb"] < 0.2


def test_site_checks_and_render():
    from app import sites
    firm = {"ico": "12345678", "nazev": "Kadeřnictví Fiala s.r.o.", "nace": "96020",
            "adresa": "Husova 1, 250 88 Čelákovice", "lat": 50.16, "lon": 14.75}
    d = sites.prefill(firm, {"phone": "777 123 456"}, None)
    assert d["type"] == "kadernictvi" and d["contact"]["phone"] == "777 123 456"
    sm = sites.summary(sites.checks(d))
    assert not sm["ready"] and sm["errors"] > 5
    d["about"] = "Text [doplnit: něco]"
    left = [c for c in sites.checks(d) if c["group"] == "Dokončení"][0]
    assert not left["ok"]
    html = sites.render(d)
    assert "<h1>" in html and "application/ld+json" in html and "HairSalon" in html
    assert "<script>alert" not in sites.render({**d, "name": "<script>alert(1)</script>"})


def test_templates_and_brand(tmp_path, monkeypatch):
    from app import sites
    monkeypatch.setattr(sites, "BRAND_DIR", tmp_path)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    assert sites.save_brand("google", svg, "image/svg+xml") == "brand-google.svg"
    assert sites.brand_files() == {"google": "brand-google.svg"}
    d = sites.empty_data("restaurace")
    d["ratings"]["google"].update(value="4,8", count="přes 100 recenzí")
    h1 = sites.render(d)
    d["theme"]["template"] = "2"
    h2 = sites.render(d)
    assert "t-straight" in h1 and "t-round" not in h1
    assert 'class="t-round"' in h2 and "brand-google.svg" in h2 and "přes 100 recenzí" in h2


def test_templates_3_4_5():
    from app import sites
    d = sites.empty_data("kavarna")
    d.update(name="Kavárna <b>X</b>")
    d["hero"]["title"] = "Káva **pomalu**"
    d["gallery"] = [{"file": f"{i:010x}.jpg", "alt": "fotka"} for i in range(4)]
    d["usps"] = [{"title": "Zahrádka", "text": "30 míst"}]
    d["ratings"]["google"].update(value="4,9", count="120")
    d["hours"][0]["value"] = "7:00–18:00"
    for tpl, cls in (("3", "t-vizitka"), ("4", "t-pop"), ("5", "t-luxus"), ("6", "t-urban"), ("7", "t-brush")):
        d["theme"]["template"] = tpl
        h = sites.render(d)
        assert f'class="{cls}"' in h and "<b>X</b>" not in h and "HairSalon" not in h
        assert "**" not in h.split("<body")[1]
        sites.checks(d)
    d["theme"]["template"] = "4"
    assert '<span class="hl">pomalu</span>' in sites.render(d)
    d["theme"]["template"] = "5"
    h = sites.render(d)
    assert "4,9 ★" in h and "7:00" in h and 'data-par' in h
