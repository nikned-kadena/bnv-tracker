"""
buildings.py — Kanonički nazivi zgrada za BnV Tracker
"""
import re

ALL_BUILDINGS = [
    # Quartet
    "BW Quartet 1", "BW Quartet 2", "BW Quartet 3", "BW Quartet 4",
    # Simfonija
    "BW Simfonija 1", "BW Simfonija 2",
    # Ostale zgrade
    "BW Iris", "BW Aurora", "BW Riviera",
    "BW Riva",
    "BW Residences",
    "BW St. Regis",
    "BW Sole", "BW Lido",
    "BW Elegance",
    "BW Sky",
    "BW King's Park",
    "BW Queen's Park",
    "BW Bristol",
    "BW Rima",
    "BW Victoria",
    "BW Perla",
    "BW Terraces",
    "BW Vista",
    "BW Libera",
    "BW Thalia",
    "BW Aria",
    "BW Aqua",
    "BW Verde",
    "BW Bonaca",
    "BW Eden",
    "BW Metropolitan",
    "BW Terra",
    "BW Scala",
    "BW Eterna",
    "BW Sensa",
    "BW Dolce",
    "BW Oda",
    "BW Sena",
    "BW Magnolia",
    "BW Topaz",
    "BW Lumia",
    "BW Garden Plaza",
    "BW Bella",
    "BW Vizia",
    "BW Hudson",
    "BW Maestra",
    "BW Nika",
    "BW Parkview",
    "BW Lena",
    "BW Emerald",
    "BW Arcadia",
    "BW Nota",
    "BW Diva",
    "BW Iskra",
    "BW Nova",
    "BW Alegra",
    "BW Sava",
]

ALIASES = {
    # Quartet
    r"quartet\s*1|kvartet\s*1":              "BW Quartet 1",
    r"quartet\s*2|kvartet\s*2":              "BW Quartet 2",
    r"quartet\s*3|kvartet\s*3":              "BW Quartet 3",
    r"quartet\s*4|kvartet\s*4":              "BW Quartet 4",
    r"quartet|kvartet":                      "BW Quartet ?",
    # Simfonija
    r"simf[oi]nija?\s*1|simfonia\s*1":       "BW Simfonija 1",
    r"simf[oi]nija?\s*2|simfonia\s*2":       "BW Simfonija 2",
    r"simf[oi]nija?|simfonia":                "BW Simfonija 1",
    # Iris
    r"\biris\b":                              "BW Iris",
    # Aurora
    r"\baurora\b":                            "BW Aurora",
    # Aqua — MORA biti pre "kul[aiue]" aliasa (opisi Aqua stanova cesto
    # sadrze rec "kula" jer je Aqua toranj kao St. Regis, sto je do sada
    # obaralo Aqua oglase na St. Regis (bug otkriven 08.07.2026)
    r"\baqua\b":                              "BW Aqua",
    # Riviera
    r"\briviera\b":                           "BW Riviera",
    # Riva — \b granice sprečavaju koliziju sa "riviera" (nema granice posle "riva" u "riviera")
    r"\briva\b":                              "BW Riva",
    # BW Residences — SAMO ako je eksplicitno "BW" ispred
    r"bw\s+residenc[eyi]":                   "BW Residences",
    # Bristol Residence — mora biti pre King's/Queen's Park da ne bi "The Bristol" završio u parku
    r"bristol\s+residenc|the\s+bristol":     "BW Bristol",
    # King's Park — sa i bez apostrofa, i samo King
    r"kings?\s*['\u2019]?\s*park|\bking\b": "BW King's Park",
    # Queen's Park — sa i bez apostrofa
    r"queens?\s*['\u2019]?\s*park":          "BW Queen's Park",
    # St. Regis / Kula — sve varijante → BW St. Regis
    r"st[\.\s]*regis|stregis":               "BW St. Regis",
    r"kula\s*beograd|belgrade\s*tower":      "BW St. Regis",
    # STARO (do 09.07.2026): r"kul[aiue]" je vodio na "BW St. Regis"
    # Uklonjeno jer:
    #   1) "kula" u srpskom je previše česta reč (svaka BW zgrada je "kula")
    #   2) BW ima više tornjeva sada (Aqua, Riva, Verde, St. Regis)
    #   3) St. Regis je premijum segment - pogresna atribucija podiže
    #      prosek €/m² na dashboardu i kvari cenu tržišne slike
    # Sada: samo eksplicitni "Belgrade Tower" ili "Kula Beograd" (marketinški
    # nazivi St. Regis-a) vode na St. Regis. Sve ostalo → neidentifikovano.
    r"\bverde\b":                             "BW Verde",
    # Bonaca — nova zgrada, dodata 09.07.2026
    r"\bbonaca\b":                            "BW Bonaca",
    # Sole
    r"\bsole\b":                              "BW Sole",
    # Lido
    r"\blido\b":                              "BW Lido",
    # Elegance
    r"\belegance\b":                          "BW Elegance",
    # Perla
    r"\bperla\b":                             "BW Perla",
    # Victoria
    r"\bvictoria\b":                         "BW Victoria",
    # Rima
    r"\brima\b":                              "BW Rima",
    # Terraces
    r"\bterraces\b":                        "BW Terraces",
    # Vista
    r"\bvista\b":                           "BW Vista",
    # Libera
    r"\blibera\b":                          "BW Libera",
    # Thalia
    r"\bthalia\b":                          "BW Thalia",
    # Aria
    r"\baria\b":                            "BW Aria",
    # Eden
    r"\beden\b":                            "BW Eden",
    # Metropolitan
    r"\bmetropolitan\b|metropoliten":       "BW Metropolitan",
    # Terra / Tera — sinonimi
    r"\bterr?a\b":                          "BW Terra",
    # Scala
    r"\bscala\b":                           "BW Scala",
    # Eterna
    r"\beterna\b":                          "BW Eterna",
    # Sensa
    r"\bsensa\b":                           "BW Sensa",
    # Dolce
    r"\bdolce\b":                           "BW Dolce",
    # Oda
    r"\boda\b":                             "BW Oda",
    # Sena
    r"\bsena\b":                            "BW Sena",
    # Magnolia
    r"\bmagnolia\b":                        "BW Magnolia",
    # Topaz
    r"\btopaz\b":                           "BW Topaz",
    # Lumia
    r"\blumia\b":                           "BW Lumia",
    # Garden Plaza
    r"garden\s*plaza":                       "BW Garden Plaza",
    # Bella
    r"\bbella\b":                           "BW Bella",
    # Vizia
    r"\bvizia\b":                           "BW Vizia",
    # Hudson
    r"\bhudson\b":                          "BW Hudson",
    # Maestra
    r"\bmaestra\b":                         "BW Maestra",
    # Nika
    r"\bnika\b":                            "BW Nika",
    # Parkview
    r"parkview":                              "BW Parkview",
    # Lena
    r"\blena\b":                            "BW Lena",
    # Emerald
    r"\bemerald\b":                         "BW Emerald",
    # Arcadia / Arkadia — sinonimi
    r"arc?adia|ark?adia":                     "BW Arcadia",
    # Nota
    r"\bnota\b":                            "BW Nota",
    # Diva
    r"\bdiva\b":                            "BW Diva",
    # Iskra
    r"\biskra\b":                           "BW Iskra",
    # Nova
    r"\bnova\b":                            "BW Nova",
    # Alegra
    r"\balegra\b":                          "BW Alegra",
    # Sava
    r"\bsava\b":                             "BW Sava",
    # Sky
    r"\bsky\b":                               "BW Sky",
}

# Oglasi koji izgledaju kao BW ali nisu — preskočiti identifikaciju
NOT_BW = [
    r"park\s*bristol",           # Park Bristol — zgrada preko puta
    r"karađorđeva|karadjordjeva", # Karađorđeva ulica — nije BW
    r"višegradska|visegradska",   # Višegradska — nije BW
    r"risanska",                  # Risanska ulica — nije BW
    r"gavrila\s*principa",       # Gavrila Principa — nije BW
    r"durmitorska",               # Durmitorska — nije BW
    r"mihaila\s*bogićevića|mihaila\s*bogicevica",  # Mihaila Bogićevića — nije BW
    r"vojvode\s*milenka",        # Vojvode Milenka — nije BW
]

ADDRESS_MAP = {
    ("savska", "1"):             "BW St. Regis",
    ("savska", "3"):             "BW St. Regis",
    ("hercegovačka", "15a"):     "BW Simfonija 1",
    ("hercegovačka", "15b"):     "BW Simfonija 2",
    ("hercegovina",  "15a"):     "BW Simfonija 1",
    ("luke celovića", "1"):      "BW Sole",
    ("luke celovica", "1"):      "BW Sole",
    ("bulevar vudroa vilsona", "1"): "BW Iris",
}

# STREET_FALLBACK — samo indikator "ovo je BW ali ne znamo tacno koja zgrada".
# Ranije je mapirao ulica -> zgrada, ali kako BW gradi vise kula u istim
# ulicama (Savska: St. Regis + Aqua + Riva; Hercegovacka: Simfonija 1+2;
# Luke Celovica: Sole + druge), ime ulice bez kucnog broja je nepouzdano.
# ADDRESS_MAP (iznad) hvata konkretne kucne brojeve pouzdano.
# (Bug otkriven 08.07.2026 - Savska stanovi bez broja obarali su na St. Regis)
STREET_FALLBACK = {
    "savska":        "BW (neidentifikovano)",
    "hercegovačka":  "BW (neidentifikovano)",
    "luke celovića": "BW (neidentifikovano)",
}

def simfonija_by_floors(floor_info):
    if not floor_info: return "BW Simfonija 1"
    m = re.search(r"(\d+)\s*/\s*(\d+)", str(floor_info))
    if m:
        total = int(m.group(2))
        return "BW Simfonija 2" if total >= 25 else "BW Simfonija 1"
    return "BW Simfonija 1"

def quartet_by_floors(floor_info):
    if not floor_info: return "BW Quartet 1"
    m = re.search(r"(\d+)\s*/\s*(\d+)", str(floor_info))
    if m:
        total = int(m.group(2))
        if total <= 10:   return "BW Quartet 1"
        elif total <= 15: return "BW Quartet 2"
        elif total <= 20: return "BW Quartet 3"
        else:             return "BW Quartet 4"
    return "BW Quartet 1"


def is_blacklisted(title: str, description: str = "", address: str = "") -> bool:
    """Vraća True ako oglas ne pripada BW kompleksu i treba ga potpuno ignorisati."""
    full_text = f"{title} {description} {address}".lower()
    for pattern in NOT_BW:
        if re.search(pattern, full_text, re.I):
            return True
    return False

def _find_by_direct_name(text: str) -> str:
    """Pretraži tekst za direktna imena zgrada iz ALL_BUILDINGS."""
    for building in sorted(ALL_BUILDINGS, key=len, reverse=True):
        pattern = re.escape(building.lower()).replace(r"'", "['\u2019]?")
        if re.search(r"\b" + pattern + r"\b", text):
            return building
    return None


def _find_by_alias(text: str, floor_info=None) -> str:
    """Pretraži tekst po ALIASES dictu."""
    for pattern, canonical in ALIASES.items():
        if re.search(pattern, text, re.I):
            if "simfonija" in canonical.lower() and "simfonija 1" not in text and "simfonija 2" not in text:
                return simfonija_by_floors(floor_info)
            if canonical == "BW Quartet ?":
                return quartet_by_floors(floor_info)
            return canonical
    return None


def canonical_building(title: str, description: str = "", address: str = "", floor_info=None) -> str:
    title_lower = title.lower().replace("'", "'")
    full_text = f"{title} {description} {address}".lower()
    full_text = full_text.replace("'", "'")

    # 0. Blacklista — oglasi koji nisu BW (proveravamo u kombinovanom tekstu)
    for pattern in NOT_BW:
        if re.search(pattern, full_text, re.I):
            return "BW (neidentifikovano)"

    # ── PRIORITET NASLOVA ────────────────────────────────────────────
    # Naslov je najpouzdaniji signal — ako u naslovu pogađamo zgradu,
    # opis se ignoriše. Rešava klasu bug-ova gde opis pomene drugu zgradu
    # (npr. "u blizini St. Regis kompleksa") i vuče oglas u pogrešnu zgradu.
    # (Sistemska popravka 09.07.2026 — Bonaca, Verde slučajevi.)
    title_direct = _find_by_direct_name(title_lower)
    if title_direct:
        return title_direct
    title_alias = _find_by_alias(title_lower, floor_info)
    if title_alias:
        return title_alias

    # ── Ako naslov nije bio jasan, pretraži pun tekst (naslov+opis+adresa) ──
    direct = _find_by_direct_name(full_text)
    if direct:
        return direct
    alias = _find_by_alias(full_text, floor_info)
    if alias:
        return alias

    # 3. Adresni lookup sa kućnim brojem
    addr_lower = (address + " " + title + " " + description).lower()
    for (street, num), building in ADDRESS_MAP.items():
        if street in addr_lower and re.search(r"\b" + re.escape(num) + r"\b", addr_lower, re.I):
            return building

    # 4. Samo "Simfonija" bez broja
    if "simfonija" in full_text:
        return simfonija_by_floors(floor_info)

    # 5. Quartet bez broja
    if "quartet" in full_text or "kvartet" in full_text:
        return quartet_by_floors(floor_info)

    # 6. Ulica bez kućnog broja
    for street, fallback in STREET_FALLBACK.items():
        if street in addr_lower or street in full_text:
            return fallback

    # 7. Generički BnV
    if "beograd na vodi" in full_text or "beograd-na-vodi" in address.lower():
        return "BW (neidentifikovano)"

    return "BW (neidentifikovano)"


if __name__ == "__main__":
    tests = [
        # Bristol
        ("The Bristol Residence, bez provizije ID#4340", "", "Hercegovačka", "5/6"),
        ("Bristol Residence, 2.0 lux",                  "", "",              "3/6"),
        # BW Residences
        ("BW Residences, 4.0",                          "", "", "5/10"),
        ("Prelep stan BW Residency, odmah useljiv",     "", "", "7"),
        # King's Park
        ("Kings Park Residence, 2.0 Lux",               "", "", "3/8"),
        ("BW King's Park, trosoban",                     "", "", "6/15"),
        ("BW Kings park, kompletno namešten",            "", "", "8/15"),
        # Queen's Park
        ("Beograd na vodi, Bw Queens Park Residences",  "", "", "4/8"),
        ("BW Queen's Park, neuseljavan",                 "", "", "7/8"),
        # Park Bristol — ne sme biti identifikovan
        ("Park Bristol 41m2 - Karađorđeva",              "", "", "4/7"),
        # Riva vs Riviera — ne smeju se mešati
        ("BW RIVA - Dvosoban stan l 55.05m2",            "", "", "5/10"),
        ("Bw riva, novogradnja, direktna prodaja",       "", "", "3/8"),
        ("BW Riviera, dvosoban lux",                     "", "", "6/12"),
        # Ostale
        ("BW St. Regis, 3.0, lux",                      "", "", "25/30"),
        ("Luksuzno opremljen stan u BW Kuli",            "", "", "29"),
        ("BW Quartet 3, trosoban",                       "", "", "3/9"),
        ("Višegradska, 4.0 stan",                        "", "", "2/7"),
    ]
    print(f"{'Ulaz':52} Rezultat")
    print("-"*82)
    for title, desc, addr, fl in tests:
        result = canonical_building(title, desc, addr, fl)
        is_bad = any(x in title.lower() for x in ["park bristol", "višegradska"])
        if is_bad:
            status = "✓" if "neidentifikovano" in result else "✗ PROBLEM"
        else:
            status = "✓" if "neidentifikovano" not in result else "✗"
        print(f"{status} {title[:51]:52} → {result}")
