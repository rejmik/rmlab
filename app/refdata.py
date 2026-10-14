"""Číselníky a heuristiky: CZ-NACE oddíly, právní formy, kategorie zaměstnanců."""

# CZ-NACE (rev. 2) oddíly: (název, apriorní pravděpodobnost "nemá web")
# Pravděpodobnosti jsou odhad – nastavte podle zkušenosti z oslovování.
NACE_DIVISIONS = {
    "01": ("Zemědělství", 0.75), "02": ("Lesnictví a těžba dřeva", 0.75), "03": ("Rybolov a akvakultura", 0.7),
    "05": ("Těžba uhlí", 0.4), "06": ("Těžba ropy a plynu", 0.4), "07": ("Těžba rud", 0.4),
    "08": ("Ostatní těžba", 0.55), "09": ("Podpůrné činnosti při těžbě", 0.5),
    "10": ("Výroba potravin", 0.6), "11": ("Výroba nápojů", 0.45), "12": ("Výroba tabákových výrobků", 0.4),
    "13": ("Výroba textilií", 0.55), "14": ("Výroba oděvů", 0.6), "15": ("Výroba usní a obuvi", 0.55),
    "16": ("Zpracování dřeva", 0.7), "17": ("Výroba papíru", 0.45), "18": ("Tisk a rozmnožování nahraných nosičů", 0.5),
    "19": ("Výroba koksu a rafinovaných ropných produktů", 0.35), "20": ("Výroba chemických látek", 0.4),
    "21": ("Výroba léčiv", 0.3), "22": ("Výroba pryžových a plastových výrobků", 0.5),
    "23": ("Výroba ostatních nekovových minerálních výrobků", 0.6), "24": ("Výroba základních kovů", 0.45),
    "25": ("Výroba kovových konstrukcí a kovodělných výrobků", 0.7), "26": ("Výroba počítačů a elektroniky", 0.4),
    "27": ("Výroba elektrických zařízení", 0.5), "28": ("Výroba strojů a zařízení", 0.5),
    "29": ("Výroba motorových vozidel", 0.45), "30": ("Výroba ostatních dopravních prostředků", 0.45),
    "31": ("Výroba nábytku", 0.65), "32": ("Ostatní zpracovatelský průmysl", 0.6),
    "33": ("Opravy a instalace strojů a zařízení", 0.75), "35": ("Výroba a rozvod energie", 0.45),
    "36": ("Úprava a rozvod vody", 0.5), "37": ("Činnosti související s odpadními vodami", 0.6),
    "38": ("Činnosti související s odpady", 0.6), "39": ("Sanace a jiné činnosti s odpady", 0.6),
    "41": ("Výstavba budov", 0.7), "42": ("Inženýrské stavitelství", 0.65),
    "43": ("Specializované stavební činnosti", 0.8), "45": ("Obchod a opravy motorových vozidel", 0.7),
    "46": ("Velkoobchod", 0.5), "47": ("Maloobchod", 0.6), "49": ("Pozemní a potrubní doprava", 0.75),
    "50": ("Vodní doprava", 0.5), "51": ("Letecká doprava", 0.4), "52": ("Skladování a vedlejší činnosti v dopravě", 0.6),
    "53": ("Poštovní a kurýrní činnosti", 0.65), "55": ("Ubytování", 0.35), "56": ("Stravování a pohostinství", 0.6),
    "58": ("Vydavatelské činnosti", 0.3), "59": ("Film, video, hudba", 0.4), "60": ("Tvorba programů a vysílání", 0.35),
    "61": ("Telekomunikační činnosti", 0.35), "62": ("Činnosti v oblasti IT", 0.3), "63": ("Informační činnosti", 0.3),
    "64": ("Finanční služby", 0.45), "65": ("Pojištění", 0.4), "66": ("Ostatní finanční činnosti", 0.55),
    "68": ("Činnosti v oblasti nemovitostí", 0.65), "69": ("Právní a účetnické činnosti", 0.5),
    "70": ("Vedení podniků, poradenství v oblasti řízení", 0.55), "71": ("Architektonické a inženýrské činnosti", 0.45),
    "72": ("Výzkum a vývoj", 0.35), "73": ("Reklama a průzkum trhu", 0.35), "74": ("Ostatní profesní a technické činnosti", 0.6),
    "75": ("Veterinární činnosti", 0.5), "77": ("Činnosti v oblasti pronájmu a operativního leasingu", 0.6),
    "78": ("Činnosti související se zaměstnáním", 0.45), "79": ("Cestovní agentury a kanceláře", 0.35),
    "80": ("Bezpečnostní a pátrací činnosti", 0.6), "81": ("Činnosti související se stavbami a úpravou krajiny", 0.8),
    "82": ("Administrativní a podpůrné činnosti", 0.6), "84": ("Veřejná správa a obrana", 0.2),
    "85": ("Vzdělávání", 0.55), "86": ("Zdravotní péče", 0.5), "87": ("Pobytové služby sociální péče", 0.4),
    "88": ("Ambulantní sociální péče", 0.45), "90": ("Tvůrčí, umělecké a zábavní činnosti", 0.55),
    "91": ("Knihovny, archivy, muzea", 0.3), "92": ("Hazardní hry", 0.4), "93": ("Sportovní, zábavní a rekreační činnosti", 0.6),
    "94": ("Činnosti organizací sdružujících osoby", 0.6), "95": ("Opravy počítačů a výrobků pro osobní potřebu", 0.75),
    "96": ("Ostatní osobní služby (kadeřnictví, kosmetika…)", 0.75), "97": ("Domácnosti jako zaměstnavatelé", 0.8),
    "99": ("Exteritoriální organizace", 0.3),
}
DEFAULT_PRIOR = 0.55

# Předvolba „řemesla a lokální služby“ – typičtí zákazníci na jednoduchý web
PRESET_LOCAL_SERVICES = [
    "10", "16", "23", "25", "31", "33", "41", "42", "43", "45", "47", "49",
    "56", "68", "77", "81", "85", "86", "93", "95", "96",
]

# Statistické právní formy (číselník ČSÚ 56) – skupiny pro filtr
FORM_GROUPS = {
    "fo": {"label": "Fyzické osoby (OSVČ)", "codes": ["100", "101", "102", "103", "104", "105", "106", "107", "108", "109", "110"]},
    "spol": {"label": "Obchodní společnosti (s.r.o., a.s., …)", "codes": ["111", "112", "113", "114", "115", "116", "121"]},
    "druzstvo": {"label": "Družstva", "codes": ["205"]},
}
ALL_BUSINESS_FORMS = {c for g in FORM_GROUPS.values() for c in g["codes"]}
FO_FORMS = set(FORM_GROUPS["fo"]["codes"])

FORM_LABELS = {
    "101": "FO podnikající dle živnostenského zákona",
    "102": "FO podnikající dle živ. zákona, zapsaná v OR",
    "105": "FO podnikající dle jiných zákonů",
    "106": "FO podnikající dle jiných zákonů, zapsaná v OR",
    "107": "Zemědělský podnikatel",
    "108": "Zemědělský podnikatel, zapsaný v OR",
    "111": "Veřejná obchodní společnost",
    "112": "Společnost s ručením omezeným",
    "113": "Komanditní společnost",
    "121": "Akciová společnost",
    "205": "Družstvo",
}

# Kategorie počtu zaměstnanců (číselník ČSÚ 579)
KATPO_LABELS = {
    "000": "neuvedeno", "110": "bez zaměstnanců", "120": "1–5", "130": "6–9",
    "210": "10–19", "220": "20–24", "230": "25–49", "240": "50–99",
    "310": "100–199", "320": "200–249",
}


def katpo_label(code):
    if not code:
        return "neuvedeno"
    if code in KATPO_LABELS:
        return KATPO_LABELS[code]
    try:
        return "250+" if int(code) >= 330 else "neuvedeno"
    except ValueError:
        return "neuvedeno"


def katpo_rank(code) -> int:
    """0 = neuvedeno, 1 = bez zaměstnanců, 2 = 1–5, 3 = 6–9, 4 = 10–49, 5 = 50+."""
    try:
        c = int(code or 0)
    except ValueError:
        return 0
    if c == 0:
        return 0
    if c <= 110:
        return 1
    if c <= 120:
        return 2
    if c <= 130:
        return 3
    if c <= 230:
        return 4
    return 5


def nace_division(nace) -> str:
    return (nace or "")[:2]


def nace_label(nace) -> str:
    d = nace_division(nace)
    return NACE_DIVISIONS.get(d, ("Neuvedeno", DEFAULT_PRIOR))[0]
