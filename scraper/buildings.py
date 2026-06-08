"""
BW Building Detection Engine
Kanonizacija naziva zgrada iz slobodnog teksta oglasa.

Logika prioriteta (od specifičnog ka opštem):
1. Eksplicitno ime zgrade u tekstu (BW Iris, BW Victoria...)
2. Aliasi i varijante (Kula = St. Regis, Simfonija bez broja, itd.)
3. Adresni lookup za višeznačne ulice (Hercegovačka, Bulevar Vudroa Vilsona...)
4. Spratnost kao disambiguator (Simfonija 1 = 15 spratova, Simfonija 2 = 14)
5. Fallback na "BW (nepoznato)"
"""

import re

# Kanonski nazivi svih BW zgrada (abecedni)
ALL_BUILDINGS = [
    "BW Alegra", "BW Aqua", "BW Arcadia", "BW Aria", "BW Aurora",
    "BW Bella", "BW Bonaca", "BW Diva", "BW Dolce", "BW Eden",
    "BW Emerald", "BW Eterna", "BW Garden Palace", "BW Garden Plaza",
    "BW Hudson", "BW Iris", "BW Iskra", "BW King's Park", "BW Libera",
    "BW Lumia", "BW Maestra", "BW Magnolia", "BW Metropolitan",
    "BW Nika", "BW Neon", "BW Nota", "BW Nova", "BW Oda",
    "BW Parkview", "BW Perla", "BW Prima", "BW Queen's Park",
    "BW Rima", "BW Riviera", "BW Scala", "BW Sava Riverline",
    "BW Sena", "BW Sensa", "BW Simfonija 1", "BW Simfonija 2",
    "BW Sole", "BW St. Regis", "BW Terraces", "BW Thalia",
    "BW Topaz", "BW Vapa", "BW Verde", "BW Victoria", "BW Vizia",
    "BW Vista", "Bristol Residences",
    # Quartet 1-4 posebno
    "BW Quartet 1", "BW Quartet 2", "BW Quartet 3", "BW Quartet 4",
]

# Aliasi → kanonski naziv
ALIASES = {
    # St. Regis / Kula
    r"st[\.\s]*regis": "BW St. Regis",
    r"kula\s+beograd": "BW St. Regis",
    r"\bkula\b": "BW St. Regis",
    r"bw\s+kula": "BW St. Regis",
    r"residences\s+at\s+st": "BW St. Regis",
    r"the\s+residences": "BW St. Regis",

    # Quartet varijante
    r"quartet\s*4|quartet\s*iv|kvartet\s*4": "BW Quartet 4",
    r"quartet\s*3|quartet\s*iii|kvartet\s*3": "BW Quartet 3",
    r"quartet\s*2|quartet\s*ii|kvartet\s*2": "BW Quartet 2",
    r"quartet\s*1|quartet\s*i\b|kvartet\s*1": "BW Quartet 1",
    # Samo "Quartet" bez broja — ostaje ambigvitet, rešava se spratom
    r"\bquartet\b|\bkvartet\b": "BW Quartet ?",

    # Simfonija
    r"simfonija\s*1|simfonija\s*i\b": "BW Simfonija 1",
    r"simfonija\s*2|simfonija\s*ii\b": "BW Simfonija 2",

    # King's Park varijante
    r"king[\'\s]*s?\s*park": "BW King's Park",
    r"kings\s*park": "BW King's Park",

    # Queen's Park
    r"queen[\'\s]*s?\s*park": "BW Queen's Park",

    # Sava Riverline
    r"sava\s*riverline": "BW Sava Riverline",
    r"riverline": "BW Sava Riverline",

    # Česta skraćivanja
    r"\beden\b": "BW Eden",
    r"\biris\b": "BW Iris",
    r"\bvictoria\b": "BW Victoria",
    r"\briviera\b": "BW Riviera",
    r"\bperla\b": "BW Perla",
    r"\blumia\b": "BW Lumia",
    r"\bvista\b": "BW Vista",
    r"\bscala\b": "BW Scala",
    r"\bsole\b": "BW Sole",
    r"\blibera\b": "BW Libera",
    r"\bnika\b": "BW Nika",
    r"\bthalia\b": "BW Thalia",
    r"\bargona\b|\balegra\b": "BW Alegra",
    r"\baurora\b": "BW Aurora",
    r"\bmagnolia\b": "BW Magnolia",
    r"\bmetropolitan\b": "BW Metropolitan",
    r"\bparkview\b|park\s*view": "BW Parkview",
    r"\bterraces\b|\bterrase\b": "BW Terraces",
    r"\beterna\b": "BW Eterna",
    r"\bsensa\b": "BW Sensa",
    r"\baria\b": "BW Aria",
    r"\bdolce\b": "BW Dolce",
    r"\bbella\b": "BW Bella",
    r"\bdiva\b": "BW Diva",
    r"\bnota\b": "BW Nota",
    r"\brima\b": "BW Rima",
    r"\bverde\b": "BW Verde",
    r"\baqua\b": "BW Aqua",
    r"\bmaestra\b": "BW Maestra",
    r"\bbonaca\b": "BW Bonaca",
    r"\bvizia\b": "BW Vizia",
    r"\bnova\b": "BW Nova",
    r"\biskra\b": "BW Iskra",
    r"\bhudson\b": "BW Hudson",
    r"\berald\b|\bemerald\b": "BW Emerald",
    r"\bneon\b": "BW Neon",
    r"\bsena\b": "BW Sena",
    r"\bvapa\b": "BW Vapa",
    r"\boda\b": "BW Oda",
    r"\bprima\b": "BW Prima",
    r"\btopaz\b": "BW Topaz",
    r"\bbristol\b": "Bristol Residences",
}

# Adresni lookup: ulica + broj → zgrada
# Za Hercegovačku posebno razrađeno
ADDRESS_MAP = {
    # Hercegovačka (po brojevima)
    ("hercegovačka", "15a"): "BW Simfonija 1",
    ("hercegovačka", "15b"): "BW Simfonija 2",
    ("hercegovačka", "13"): "BW Magnolia",
    ("hercegovačka", "11"): "BW Metropolitan",
    ("hercegovačka", "9"):  "BW Terraces",
    ("hercegovačka", "7"):  "BW Riviera",
    # Bulevar Vudroa Vilsona
    ("vudroa vilsona", "1"): "BW Iris",       # Apollo kompleks
    ("vudroa vilsona", "3"): "BW Nika",
    ("vudroa vilsona", "5"): "BW Thalia",
    ("vudroa vilsona", "7"): "BW Eden",
    # Luke Ćelovića Trebinjca
    ("luke ćelovića", "1"):  "BW Sole",
    ("luke ćelovića", "3"):  "BW Scala",
    ("luke ćelovića", "5"):  "BW Libera",
    ("luke ćelovića", "7"):  "BW Sensa",
    # Kraljice Drage Obrenović
    ("kraljice drage", "1"): "BW Alegra",
    ("kraljice drage", "3"): "BW Sava Riverline",
    # Nikolaja Kravcova
    ("kravcova", "1"):       "BW Nota",
    ("kravcova", "3"):       "BW Rima",
    # Savska
    ("savska", "1"):         "BW St. Regis",
}

# Spratnost kao disambiguator za Simfoniju (bez broja u tekstu)
# Simfonija 1: 15 spratova; Simfonija 2: 14 spratova
def simfonija_by_floors(floor_str: str | None, total_floors: str | None) -> str:
    for s in [floor_str, total_floors]:
        if s:
            m = re.search(r"(\d+)", str(s))
            if m:
                n = int(m.group(1))
                if n <= 15:
                    return "BW Simfonija 1"
                else:
                    return "BW Simfonija 2"
    return "BW Simfonija"

# Quartet bez broja → disambiguuj po broju spratova
# Quartet 1: 12sp, Quartet 2: 14sp, Quartet 3: 22sp, Quartet 4: 16sp
def quartet_by_floors(floor_str: str | None) -> str:
    if not floor_str:
        return "BW Quartet ?"
    m = re.search(r"(\d+)", str(floor_str))
    if m:
        n = int(m.group(1))
        if n <= 13:  return "BW Quartet 1"
        if n <= 15:  return "BW Quartet 2"
        if n <= 17:  return "BW Quartet 4"
        return "BW Quartet 3"
    return "BW Quartet ?"


def canonical_building(title: str, description: str = "",
                       address: str = "", floor_info: str = None) -> str:
    """
    Glavna funkcija — vraća kanonski naziv zgrade.

    Args:
        title:       Naslov oglasa
        description: Pun opis oglasa
        address:     Adresa (ulica + broj) ako je dostupna
        floor_info:  String poput "5/22" ili "22 sprat" za disambiguaciju

    Returns:
        Kanonski naziv zgrade, npr. "BW Simfonija 1"
    """
    text = f"{title} {description}".lower()

    # 1. Direktno BW + ime (specifično, bez greške)
    for building in sorted(ALL_BUILDINGS, key=len, reverse=True):
        pattern = building.lower().replace("'", "['\u2019]?").replace(".", r"\.")
        if re.search(r"\b" + re.escape(building.lower()) + r"\b", text) or \
           re.search(pattern, text):
            return building

    # 2. Aliasi (regexp)
    for pattern, canonical in ALIASES.items():
        if re.search(pattern, text, re.I):
            if canonical == "BW Simfonija ?" or "simfonija" in canonical.lower():
                # Provjeri koji broj
                if "simfonija 1" not in text and "simfonija 2" not in text:
                    return simfonija_by_floors(floor_info, floor_info)
            if canonical == "BW Quartet ?":
                return quartet_by_floors(floor_info)
            return canonical

    # 3. Adresni lookup
    addr_lower = address.lower()
    for (street, num), building in ADDRESS_MAP.items():
        if street in addr_lower and (num in addr_lower or not num):
            return building

    # 4. Samo "Simfonija" u adresi/tekstu bez broja
    if "simfonija" in text:
        return simfonija_by_floors(floor_info, floor_info)

    # 5. "Quartet" bez broja
    if "quartet" in text or "kvartet" in text:
        return quartet_by_floors(floor_info)

    return "BW (neidentifikovano)"


# ── Testovi ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("BW QUARTET 3 – Trosoban Salonski stan", "", "", "5/22"),
        ("Ultra luksuzan penthaus u srcu Beograda na vodi", "Kula Beograd, 37 sprat", "", "37"),
        ("Stan u Beogradu na vodi", "Zgrada St. Regis, pogled na reku", "Savska 1", "25"),
        ("Prodaje se studio u Simfoniji", "Hercegovacka 15A, 14 sprat", "Hercegovačka 15a", "14/15"),
        ("Prodajem stan u BW", "BW Simfonija 2, II sprat", "", "2/14"),
        ("Trosoban stan 78m2", "BW Iris, 9. sprat, pogled na reku", "Bulevar Vudroa Vilsona 1", "9/18"),
        ("Kings Park Residence, 2BR", "", "Kraljice Natalije", None),
        ("Riverline stan na prodaju", "", "", None),
        ("Beograd na vodi, Hercegovina ulica", "lepo uređen", "Hercegovačka 9", "5/17"),
        ("Stan u kompleksu BnV", "zgrada Metro polis, novi stan", "", None),
    ]
    print(f"{'Ulaz':<45} {'Rezultat'}")
    print("-"*75)
    for title, desc, addr, fl in tests:
        result = canonical_building(title, desc, addr, fl)
        print(f"{title[:44]:<45} → {result}")
