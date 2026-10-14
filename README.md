# RM Lab – firmy bez webu v okolí

Interní nástroj pro 2–4 obchodníky. V zadaném okruhu najde firmy z veřejných rejstříků,
odhadne, jestli mají web a jestli reálně fungují, a vede mini CRM, aby nikdo neoslovil
stejnou firmu dvakrát.

## Jak to funguje

1. **Základ: RES (ČSÚ)** – všechny aktivní podnikatelské subjekty (OSVČ, s.r.o., a.s., družstva)
   s oborem, počtem zaměstnanců a kódem adresy. Stahuje se jednou měsíčně jako otevřená data.
2. **Poloha: RÚIAN (ČÚZK)** – souřadnice adresních míst. Díky nim funguje hledání v okruhu.
3. **Ověření na kliknutí** (tlačítko *Ověřit top N* nebo u jednotlivé firmy):
   - **ARES** – plátce DPH (≈ obrat nad zákonný limit), insolvence, likvidace, případně telefon
     a e-mail, pokud je firma sama zveřejnila v registru osob, a datová schránka.
   - **Detekce webu** – z názvu odhadne domény (`truhlarstvidvorak.cz`, `truhlarstvi-dvorak.cz`, …),
     ověří DNS a stránku: pokud na ní je IČO firmy, web je jistě její.
   - **Google Places** – jestli má firma profil na Mapách, jestli je u něj web, telefon, recenze
     a otevírací doba. Ukládá se jen `place_id`, ostatní se tahá živě (podmínky Google).
4. **Skóre**
   - *Bez webu* – pravděpodobnost, že firma nemá web (výchozí odhad podle oboru + signály).
   - *Živost* 0–100 – plátce DPH, recenze, zaměstnanci, stáří firmy; dolů jdou insolvence,
     likvidace, virtuální sídlo (desítky firem na jedné adrese).
   - *Priorita* = bez webu × živost. V detailu firmy je vidět každý důvod a jeho váha.
     Váhy jsou v `app/scoring.py`, výchozí odhady podle oborů v `app/refdata.py` – laďte je podle praxe.
5. **CRM** – rezervace firmy (výchozí 7 dní), zápis oslovení s výsledkem a dalším krokem,
   „Nepřeje si kontakt“ (firma se už nikdy nenabídne), přehled *Moje leady* a *Tým*.

## Tým a přihlášení

První založený uživatel je automaticky **admin**. Admin v záložce **Tým → Uživatelé týmu** přidává
další členy (tlačítko *Vygenerovat* vytvoří heslo), nastavuje nové heslo, uděluje admina a deaktivuje
lidi, kteří odešli. Deaktivovaný se nepřihlásí, jeho rezervované firmy se uvolní ostatním a historie
oslovení zůstane. Každý si může změnit vlastní heslo tlačítkem *Heslo* vpravo nahoře.
Záchrana z příkazové řádky: `python manage.py make-admin <uživatel>` nebo `passwd <uživatel>`.

## Checklisty a ceník

Záložka **Checklist** má dvě části:
- **Prodej – co říct klientovi**: příprava, začátek hovoru, proč web, co slibovat, co neslibovat
  (a co říct místo toho), námitky, cíl hovoru = schůzka s Lukášem, pravidla. Nahoře je ceník.
- **Jak má vypadat správný web**: jednoduchost, SEO formátování, autentické fotky, USP, recenze, kontakt.

Položky si prodejci během hovoru odškrtávají (*Vynulovat* je smaže). Admin text upravuje tlačítkem *Upravit*.

**Ceník** spravuje admin v záložce **Tým → Produkty a ceník**: každý produkt má základní (jednorázovou)
cenu, měsíční poplatek, popis a seznam toho, co je v ceně. Skrytý produkt prodejci nevidí.

## Weby pro klienty

V detailu firmy je tlačítko **Připravit web**. Založí web předvyplněný z registru (název, adresa, IČO)
a z Googlu (telefon, otevírací doba), pokud byla firma ověřená. Záložka **Weby** ukazuje všechny rozpracované.

- **Editor**: prodejce vyplní brief – texty, výhody (USP), nabídku/ceník, fotky, recenze, kontakt, hodiny, SEO.
  Ukládá se automaticky, vpravo je živý náhled (mobil / počítač) a kontrola podle checklistu „Správný web“.
- **Texty**: tlačítko *Navrhnout texty* – s `ANTHROPIC_API_KEY` v `.env` je napíše Claude z poznámek prodejce,
  bez klíče se předvyplní šablona. Co nikdo neví, zůstane jako [doplnit: …] a web nejde schválit, dokud to někdo nedoplní.
- **Fotky** se při nahrání zmenší a změří (rozlišení, jas, ostrost) – slabé fotky dostanou varování.
- **Šablona**: jednostránkový mobilní web pro kadeřnictví, kavárny a restaurace – swipovací karusely, spodní lišta
  Zavolat / Trasa / Hodiny, „Teď otevřeno“ podle hodin, galerie na celou obrazovku, na desktopu mřížka.
  SEO: jeden H1, titulek a popisek, alt u fotek, strukturovaná data schema.org (LocalBusiness), mapa.
- **Schvalování**: prodejce *Odešle ke schválení* (jen když jsou splněná povinná pravidla), admin *Schválí*,
  stáhne web jako ZIP (index.html + fotky + logo + robots.txt) a nahraje na hosting, pak *Označí jako spuštěný*.
- **Náhled pro klienta**: odkaz `/p/<kód>/` funguje bez přihlášení – klientovi ho ale půjde poslat,
  až RM Lab poběží na internetu (viz Provoz pro tým). Do té doby ukazujte náhled na schůzce z notebooku.

## Rychlé vyzkoušení (fiktivní data, bez sítě)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py demo                       # 400 fiktivních firem kolem Čelákovic
python manage.py adduser lukas "Lukáš"      # zeptá se na heslo
uvicorn app.main:app --port 8000
```
Otevřete http://localhost:8000. V demu se ověřování jen simuluje.

> Na macOS doporučuji Python z Homebrew (`brew install python@3.12`) nebo `uv`;
> kód běží i na systémovém 3.9, ale ten už nemá podporu.

## Ostrá data

```bash
python manage.py update        # stáhne RES (~ stovky MB) + RÚIAN a naimportuje (desítky minut)
```
Nebo po krocích: `python manage.py download`, `import-res`, `import-ruian`.
RES se aktualizuje 2× měsíčně, RÚIAN 1× měsíčně – stačí `update` jednou měsíčně z cronu.
Import přepíše tabulku firem, CRM a cache ověření zůstávají.

### Google Places API

1. V Google Cloud Console založte projekt, zapněte **Places API (New)** a vytvořte API klíč.
2. Klíč omezte jen na Places API a nastavte denní kvótu – vyhledávání s webem a telefonem
   patří do dražší cenové kategorie, aktuální ceník a bezplatné limity si ověřte u Google.
3. Do `.env` dejte `GOOGLE_PLACES_API_KEY=...`.

Bez klíče aplikace funguje dál, jen bez signálů z Google.

## Provoz pro tým

Nejjednodušší je malý VPS nebo domácí server s Dockerem:

```bash
cp .env.example .env            # doplňte LF_SECRET_KEY a GOOGLE_PLACES_API_KEY
docker compose up -d --build
docker compose exec app python manage.py adduser petr "Petr"
docker compose exec app python manage.py update
```
Před aplikaci dejte HTTPS (např. Caddy: `leads.vasedomena.cz { reverse_proxy localhost:8000 }`)
a v `docker-compose.yml` pak port vystavte jen na `127.0.0.1`.

## Nastavení (`.env`)

| proměnná | výchozí | význam |
|---|---|---|
| `LF_SECRET_KEY` | vygeneruje se | klíč pro přihlašovací cookie |
| `GOOGLE_PLACES_API_KEY` | – | klíč pro Google Places |
| `LF_CLAIM_DAYS` | 7 | na jak dlouho se firma rezervuje |
| `LF_ENRICH_MAX` | 200 | max. firem na jedno ověření |
| `LF_CACHE_DAYS` | 30 | jak dlouho platí ověření z ARES a domén |
| `LF_MASS_ADDRESS` | 15 | od kolika firem na adrese jde o virtuální sídlo |

## Omezení, o kterých je dobré vědět

- **Obrat** veřejně není. Plátcovství DPH je nejlepší bezplatný ukazatel; skutečné tržby mají
  jen placené databáze (Merk, Cribis, D&B) nebo účetní závěrky na justice.cz (odkaz v detailu).
- **OSVČ** mají v rejstříku jméno, na Googlu často obchodní název – párování pak selže
  a firma zůstane jako „na Mapách nenalezeno“. Odkazy na Firmy.cz a Google v detailu pomůžou.
- **Firmy.cz** se automaticky neprohledávají (bez veřejného API, scraping je proti podmínkám).
- Sídlo ≠ provozovna: řemeslník může mít sídlo doma a dílnu jinde.

## Právní minimum

- U OSVČ jde o osobní údaje (GDPR): mějte sepsaný oprávněný zájem, při prvním kontaktu
  řekněte, odkud údaje máte, a námitku respektujte (výsledek *Nepřeje si kontakt*).
- Obchodní e-maily bez předchozího souhlasu zákon o některých službách informační společnosti
  nedovoluje – hlavním kanálem je telefon. I pro marketingové hovory platí pravidla o souhlasu;
  postup si nechte ověřit právníkem.

## Struktura

```
app/main.py        API, přihlášení, CRM
app/importers.py   import RES a RÚIAN, demo data
app/enrich.py      ověřování na pozadí (ARES, domény, Google)
app/ares.py        klient ARES
app/webcheck.py    odhad a ověření domén
app/places.py      Google Places (New)
app/scoring.py     výpočet skóre
app/refdata.py     obory, právní formy, kategorie zaměstnanců
app/static/        frontend (Leaflet mapa)
app/checklist.py   výchozí checklisty (prodej, správný web)
app/sites.py       weby pro klienty: data, kontrola kvality, šablona, export
app/ai.py          návrhy textů (Claude API nebo šablona)
manage.py          správa: import, uživatelé, demo
tests/             testy bez sítě (python -m pytest -q)
```
