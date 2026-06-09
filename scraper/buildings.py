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
    "BW Residences",
    "BW St. Regis", "BW Kula",
    "BW Sole", "BW Lido",
    "BW Elegance",
    "BW Sky",
    "Kula Beograd",
]

ALIASES = {
    # Quartet
    r"quartet\s*1|kvartet\s*1":            "BW Quartet 1",
    r"quartet\s*2|kvartet\s*2":            "BW Quartet 2",
    r"quartet\s*3|kvartet\s*3":            "BW Quartet 3",
    r"quartet\s*4|kvartet\s*4":            "BW Quartet 4",
    r"quartet|kvartet":                    "BW Quartet ?",
    # Simfonija
    r"simfonija\s*1":                       "BW Simfonija 1",
    r"simfonija\s*2":                       "BW Simfonija 2",
    r"simfonija":                           "BW Simfonija 1",
    # Iris
    r"\biris\b":                            "BW Iris",
    # Aurora
    r"\baurora\b":                          "BW Aurora",
    # Riviera
    r"\briviera\b":                         "BW Riviera",
    # Residences — više varijanti pisanja
    r"\bresidences?\b|residenc[ei]":        "BW Residences",
    # St. Regis / Savska
    r"st[\.\s]*regis|stregis":             "BW St. Regis",
    # Kula Beograd
    r"kula beograd|belgrade tower":         "Kula Beograd",
    # Sole
    r"\bsole\b":                            "BW Sole",
    # Lido
    r"\blido\b":                            "BW Lido",
    # Elegance
    r"\belegance\b":                        "BW Elegance",
    # Sky
    r"\bsky\b":                             "BW Sky",
}

# Oglasi koji izgledaju kao BW ali nisu — preskočiti identifikaciju
NOT_BW = [
    r"park\s*bristol",
    r"karađorđeva|karadjordjeva",
    r"višegradska|visegradska",
]

ADDRESS_MAP = {
    ("savska", "1"):      "BW St. Regis",
    ("savska", "3"):      "BW St. Regis",
    ("hercegovačka", "15a"): "BW Simfonija 1",
    ("hercegovačka", "15b"): "BW Simfonija 2",
    ("hercegovina",  "15a"): "BW Simfonija 1",
    ("luke celovića", "1"):  "BW Sole",
    ("luke celovica", "1"):  "BW Sole",
    ("bulevar vudroa vilsona", "1"): "BW Iris",
}

STREET_FALLBACK = {
    "savska":          "BW St. Regis",
    "hercegovačka":    "BW (Hercegovačka)",
    "luke celovića":   "BW Sole",
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

def canonical_building(title: str, description: str = "", address: str = "", floor_info=None) -> str:
    full_text = f"{title} {description} {address}".lower()
    full_text = full_text.replace("'", "'")

    # 0. Blacklista — oglasi koji nisu BW bez obzira na ostale signale
    for pattern in NOT_BW:
        if re.search(pattern, full_text, re.I):
            return "BW (neidentifikovano)"

    # 1. Direktno ime zgrade (sortirano od najdužeg)
    for building in sorted(ALL_BUILDINGS, key=len, reverse=True):
        pattern = re.escape(building.lower()).replace(r"'", "['\u2019]?")
        if re.search(r"\b" + pattern + r"\b", full_text):
            return building

    # 2. Aliasi
    for pattern, canonical in ALIASES.items():
        if re.search(pattern, full_text, re.I):
            if "simfonija" in canonical.lower() and "simfonija 1" not in full_text and "simfonija 2" not in full_text:
                return simfonija_by_floors(floor_info)
            if canonical == "BW Quartet ?":
                return quartet_by_floors(floor_info)
            return canonical

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

    # 6. Ulica bez kućnog broja → generički naziv
    for street, fallback in STREET_FALLBACK.items():
        if street in addr_lower or street in full_text:
            return fallback

    # 7. Ako je URL ili naslov "beograd-na-vodi" ali nema zgrade
    if "beograd na vodi" in full_text or "beograd-na-vodi" in address.lower():
        return "BW (neidentifikovano)"

    return "BW (neidentifikovano)"


if __name__ == "__main__":
    tests = [
        ("BW QUARTET 3 – Trosoban", "", "", "5/22"),
        ("Kula Beograd, 37 sprat", "", "Savska 1", "37"),
        ("Stan u Simfoniji", "Hercegovacka 15A", "Hercegovačka 15a", "14/15"),
        ("Luksuzan stan BW Riviera prvi red do reke", "BW Riviera - prvi red", "", None),
        ("BW Iris, odlična pozicija ID#1195", "", "", "14/18"),
        ("BW Residences, 4.0, odmah useljiv", "", "", "5/10"),
        ("Exclusive apartment in BW Residences /45m2 terrace", "", "", "14"),
        # Blacklista testovi
        ("Park Bristol 41m2 - Karađorđeva ulica ID248", "", "", "4/7"),
        ("Park Bristol Residences, dvosoban", "", "Karađorđeva", "3/8"),
        ("Višegradska, 4.0 stan, namešten, odmah useljiv ID#", "", "", "2/7"),
    ]
    print(f"{'Ulaz':55} Rezultat")
    print("-"*85)
    for title, desc, addr, fl in tests:
        result = canonical_building(title, desc, addr, fl)
        # Park Bristol i Višegradska treba da budu neidentifikovano
        if "bristol" in title.lower() or "višegradska" in title.lower() or "visegradska" in title.lower():
            status = "✓" if "neidentifikovano" in result else "✗ PROBLEM"
        else:
            status = "✓" if "neidentifikovano" not in result else "✗"
        print(f"{status} {title[:54]:55} → {result}")
