"""Výchozí checklisty. Admin je v aplikaci může upravit (uloží se do databáze).

Formát textu pro editor:
  ## Název sekce
  - položka
    > tip nebo příklad věty k předchozí položce
Text v [hranatých závorkách] se zvýrazní jako „doplnit“.
"""

KINDS = {
    "sales": "Prodej – co klientovi říct",
    "web": "Jak má vypadat správný web",
}

SALES_TEXT = """\
## 1. Než zavoláš
- Otevři si detail firmy v RM Lab a přečti si ho
  > Obor, kolik mají recenzí na Googlu, jak dlouho fungují.
- Ověř, že opravdu nemají web
  > Zadej do Googlu název firmy + obec. Když web mají, zapiš poznámku a jdi na další.
- Zarezervuj si firmu (tlačítko „Rezervovat pro mě“)
  > Aby stejnou firmu nevolal i kolega.
- Najdi si jednu konkrétní věc, kterou o firmě víš
  > „Viděl jsem, že máte na Googlu 40 recenzí a skoro všechny pětihvězdičkové.“
- Měj po ruce ceník (nahoře), ukázky hotových webů a Lukášův kalendář na schůzky

## 2. Začátek hovoru (prvních 20 vteřin)
- Pozdrav, řekni své jméno a že voláš za RM Lab
  > „Dobrý den, tady (tvoje jméno) z RM Lab. Děláme moderní weby pro místní firmy.“
- Řekni, kde jsi na ně získal kontakt
  > „Vaše číslo jsem našel na Google Mapách / ve veřejném rejstříku firem.“
- Zeptej se, jestli se teď hodí mluvit 2 minuty
  > Když ne: „Kdy vám můžu zavolat?“ – a zapiš si to jako další krok.
- Ujisti se, že mluvíš s majitelem nebo s tím, kdo o tom rozhoduje

## 3. Proč web – vysvětli jednoduše
- Zákazníci hledají na Googlu, Seznamu a v Mapách
  > „Když někdo napíše ‚kadeřnictví Čelákovice‘, firmy s webem vypadají důvěryhodněji a lidi jim volají dřív.“
- Web pracuje i když oni ne – 24 hodin denně
  > Služby, ceník, fotky hotové práce, kontakt, otevírací doba.
- Ušetří telefonáty s pořád stejnými dotazy
  > „Kolik stojí…? Jezdíte i do…? Máte otevřeno v sobotu?“
- Facebook ani Google profil nestačí
  > Nepatří jim, mají omezené možnosti a ne každý zákazník má Facebook. Web je jejich vlastní.
- Firma působí profesionálněji – zákazníci si ji před objednávkou „prověřují“

## 4. Co nabízíme – tohle můžeš slíbit
- Moderní design – a ukázku webu uvidí dopředu
  > Web vypadá současně a funguje na mobilu, tabletu i počítači. Než se klient rozhodne, připravíme mu ukázku, jak by jeho web mohl vypadat.
- Jednoduché logo jako součást designu
  > Když firma logo nemá, navrhneme jednoduché, které ladí s webem.
- Web vytvořený s pomocí AI
  > Díky tomu je hotový rychle a za rozumnou cenu. Vzhled i texty pak s klientem doladíme.
- Jednoduchý redakční systém na úpravu textů
  > Texty si klient upraví sám. Nebo se o to postaráme my – podle toho, co mu víc vyhovuje.
- Web připravený pro vyhledávače (SEO friendly)
  > Správné nadpisy, popisky a rychlé načítání, aby ho Google a Seznam dobře četly.
- Rozumné termíny
  > Konkrétní termín řekne Lukáš na schůzce – sám žádné datum neslibuj.
- Zalistování do vyhledávačů Google a Seznam
- Zápis do Google Moje firma (včetně Map) a na Firmy.cz
- Cena = základní cena + měsíční poplatek (viz ceník nahoře)
  > Řekni orientační cenu z ceníku. Konečnou nabídku a případné slevy řeší vždy Lukáš.

## 5. Co NESLIBUJ – a co říct místo toho
- Rezervační systém
  > „Umíme ho vyřešit na míru nebo doporučit hotovou aplikaci. Probere to s vámi Lukáš.“
- První místo na Googlu nebo Seznamu
  > To nikdo poctivě slíbit nemůže. „Web připravíme tak, aby ho vyhledávače dobře našly.“
- Nestandardní řešení (e-shop, napojení na jiný systém, speciální funkce…)
  > „Tohle vždycky probereme společně a vymyslíme, co je pro vás nejlepší.“
- Pravidelné SEO (dlouhodobá práce na pozicích ve vyhledávání)
  > „To pro vás můžou zajistit naši partneři.“
- Profily na sociálních sítích
  > „Nejsou součástí webu, ale můžeme vám je zařídit.“
- Reklamu (Google, Seznam, Facebook…)
  > „Tu pro vás můžou zajistit naši partneři.“

## 6. Když zákazník váhá – časté námitky
- „Nepotřebuju to, práce mám dost.“
  > „Web nemusí přinést víc práce, ale lepší zakázky a méně zbytečných telefonátů. Zákazníci vás najdou, i až budete chtít přibrat.“
- „Mám Facebook / Google profil.“
  > „To je skvělý začátek. Web ho doplní – Google profil pak může odkazovat na váš web, a to pomáhá i v Mapách.“
- „Je to drahé.“
  > Srovnej s cenou jedné průměrné zakázky v jejich oboru. Slevy nedávej – to řeší Lukáš na schůzce.
- „Nemám na to čas.“
  > „Většinu uděláme my. Od vás potřebujeme hlavně krátkou schůzku a pár fotek.“
- „Pošlete mi to e-mailem.“
  > „Rád. Na jaký e-mail?“ – zapiš e-mail i to, že o nabídku sám požádal.
- „Už mi to dělá známý / synovec.“
  > Poděkuj, nabídni, že kdyby to nevyšlo, rádi pomůžeme. Zapiš poznámku.

## 7. Konec hovoru – cílem je schůzka s Lukášem
- Navrhni schůzku – první schůzku s klientem vede vždy Lukáš
  > „Navrhuji krátkou schůzku s kolegou Lukášem. Ukáže vám, jak by mohl vypadat váš web, a připraví nabídku na míru. Hodí se vám spíš úterý, nebo čtvrtek?“
- Zapiš výsledek „Domluvena schůzka“ s datem a dej vědět Lukášovi
- Ověř kontakt na rozhodující osobu
  > Jméno, mobil, e-mail (e-mail jen s jeho souhlasem, že mu můžeme poslat nabídku).
- Poděkuj – i když řeknou ne
- Hned po hovoru všechno zapiš do RM Lab
  > Výsledek, poznámka, další krok. Co není zapsané, jako by se nestalo.

## 8. Pravidla – vždycky platí
- Smlouvu, konečnou cenu, slevy a peníze řeší vždy Lukáš
  > Ty domlouváš zájem a schůzku. Nic nepodepisuj, neber zálohy ani hotovost.
- Na první schůzku jde vždy Lukáš
  > Můžeš jít s ním, nikdy ne sám. Vždycky dej vědět, kam jdeš.
- Buď pravdivý – kdo jsi, za koho voláš a odkud máš kontakt
- Když řeknou „už mi nevolejte“, zapiš výsledek „Nepřejí si kontakt“
  > Firma se pak už nikomu nenabídne. Tohle je povinnost, ne zdvořilost.
- Neposílej reklamní e-maily nikomu, kdo o ně sám nepožádal
- Volej ve všední dny zhruba mezi 9 a 18 hodinou
- Když nevíš, neodpovídej od boku
  > „Tohle vám rád ověřím a ozvu se.“ – a zeptej se Lukáše.
"""

WEB_TEXT = """\
## 1. Jednoduchost
- Na první pohled je jasné, co firma dělá, kde a jak ji kontaktovat
  > Návštěvník to musí pochopit do 5 vteřin – i na mobilu.
- Málo stránek, jasné menu, žádné zbytečnosti
- Výrazné tlačítko „Zavolat“ nebo „Napsat“
  > Na mobilu ideálně stále na očích.

## 2. Dost informací – a správně naformátovaných pro SEO
- Služby a ceník (nebo aspoň „ceny od“)
- Jeden hlavní nadpis na stránce (H1) – co a kde
  > Např. „Kadeřnictví v Čelákovicích – stříháme i bez objednání“.
- Podnadpisy (H2, H3), které člení text do bloků
- Formátované texty – krátké odstavce, tučně to důležité, odrážky
- Odkazy – mezi stránkami a odkazové odrážky, které posunou na část stránky
  > Např. obsah nahoře: Služby · Ceník · Recenze · Kontakt.
- SEO titulek a popisek u každé stránky
  > Titulek zhruba do 60 znaků, popisek zhruba do 155 znaků. Obsahují službu a obec.
- Alternativní popisky (alt) ke všem obrázkům
  > Krátce, co je na fotce: „Kadeřnice stříhá pánský účes“.

## 3. Autentické fotky a video
- Vlastní fotky – provozovna, tým, hotová práce
  > Fotky z fotobank jen výjimečně. Zákazník chce vidět skutečnou firmu.
- Krátké video – prohlídka provozovny nebo ukázka práce
  > Natoč mobilem na šířku, 20–40 vteřin, nahraj na YouTube (klidně jako „neveřejné“) a vlož odkaz.
- Jak fotit mobilem, aby fotky byly dobré
  > Fot přes den u okna nebo venku, ne s bleskem. Drž telefon rovně a otři čočku.
  > Hlavní fotku fot na šířku, ostatní klidně na výšku. Ukaž detail práce, interiér, tým při práci.
  > Udělej víc záběrů a vyber nejlepší. RM Lab tě upozorní, když je fotka tmavá, rozmazaná nebo malá.

## 4. Čím se firma liší od konkurence (USP)
- Sepsat 3–5 benefitů, kterými se firma odlišuje
  > Např. stříhání bez objednání, 4 kadeřnice najednou, čekací doba max. 30 minut.
- Benefity dát hned na úvodní stránku, výrazně

## 5. Recenze zákazníků
- Skutečné recenze – ideálně s fotkou nebo jménem
  > Jen se souhlasem zákazníka. Hodí se i odkaz na recenze na Googlu.

## 6. Kontakt a otevírací doba
- Telefon, e-mail, adresa a mapa
- Fotka majitele nebo kontaktní osoby
  > Lidé raději volají někomu, koho „znají“ z fotky.
- Otevírací / úřední doba – aktuální, včetně svátků a dovolených
- IČO a fakturační údaje v patičce webu
"""

DEFAULTS = {"sales": SALES_TEXT, "web": WEB_TEXT}
DEFAULT_TEXT = SALES_TEXT  # zpětná kompatibilita


def parse(text: str):
    """Text → [{title, items: [{text, tip}]}]."""
    sections, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("## "):
            cur = {"title": s[3:].strip(), "items": []}
            sections.append(cur)
        elif s.startswith("- "):
            if cur is None:
                cur = {"title": "Obecné", "items": []}
                sections.append(cur)
            cur["items"].append({"text": s[2:].strip(), "tip": ""})
        elif cur and cur["items"]:  # „> tip“ nebo pokračování tipu
            tip = s[1:].strip() if s.startswith(">") else s
            item = cur["items"][-1]
            item["tip"] = (item["tip"] + "\n" + tip).strip() if item["tip"] else tip
    return sections
