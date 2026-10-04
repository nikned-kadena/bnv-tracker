#!/usr/bin/env python3
"""
zgrada_iz_opisa.py — prepoznavanje BW zgrade iz teksta agenta
=============================================================

ZASTO POSTOJI
-------------
4zida u JSON-LD `description` ne daje tekst agenta nego automatski
generisan rezime bez naziva zgrade:

    "Trosoban stan u zgradi za izdavanje, Namesteno, Beograd na vodi,
     140 m2, na 2. spratu, ima lift..."

Zato je 84% BnV oglasa sa 4zida padalo u "BW (neidentifikovano)".
Pravi tekst agenta postoji na strani i skoro uvek pocinje nazivom:

    "St. Regis Residences, Kula Beograd - 25. sprat | 76 m2"
    "Ekskluzivan stan u premium zgradi BW Residences..."

sources.py ga sada izvlaci (vidi `opis_agenta`), a ovaj modul ga cita.

ZASTO NE PROSTA PRETRAGA IMENA
------------------------------
Provereno na 79 stvarnih BnV oglasa za izdavanje sa 4zida (30.09.2026).
Naivna pretraga imena po opisu daje cetiri klase gresaka:

1. OBICNE RECI koje su i imena zgrada.
   "...exudes elegance and attention to detail..."  -> BW Elegance
   "...views of the banks of the River Sava..."     -> BW Sava
   Zato se ime bez kvalifikatora (bw / zgrada / kula / kompleks /
   rezidencija / u okviru...) NE prihvata, sem ako je samo po sebi
   nedvosmisleno ("St. Regis", "Kula Beograd", "King's Park"...).

2. SADRZAJI HOTELA, ne adresa stana.
   "...pristup luksuznim hotelskim sadrzajima: St. Regis bar, spa centar"
   "...Mogucnost koriscenja svih usluga St. Regis hotela"
   Ovo su oglasi iz DRUGIH zgrada koje se hvale blizinom. Zato rec
   hotel/bar/spa/restoran odmah POSLE imena obara pogodak.

3. POTPIS AGENCIJE na kraju teksta.
   "...0660 429 011 / 770 6977  Hercegovacka 15/303, BW Simfonija 2,
    III sprat  Agencijska provizija..."
   To je adresa KANCELARIJE, a stan je u BW Thalia (pomenuta na 118.
   znaku). Zato se tekst reze na prvom telefonu/potpisu, a pozicija u
   tekstu ulazi u ocenu — ono sto je u naslovu tesko da je greska.

4. BLIZINA druge zgrade.
   "...pogled na BW Aria...", "...500m od Kule Beograd..."
   Cue ispred imena (blizu, pored, nasuprot, pogled na, udaljen...)
   obara pogodak.

Kad dve zgrade prodju sa istom ocenom, funkcija vraca None — bolje
neidentifikovano nego pogresna zgrada. Ista logika kojom je u
buildings.py 09.07.2026 izbacen alias r"kul[aiue]": pogresna atribucija
u premium segment kvari prosek EUR/m2 na celom dashboardu.

buildings.py se NE DIRA — ovaj modul samo cita njegove liste, pa
Halo putanja (tunirana kroz sest verzija) ostaje netaknuta.
"""

import re

from buildings import (
    ALIASES,
    ALL_BUILDINGS,
    NOT_BW,
    quartet_by_floors,
    simfonija_by_floors,
)

# ── sinonimi koje buildings.py ne pokriva ───────────────────────────────
# Provereno u stvarnim opisima: agenti pisu "Kule Beograd", "Kuli Saint
# Regis", "Kuli St. Regis Belgrade", "BW Kula (St. Regis)". Postojeci
# alias r"kula\s*beograd" hvata samo nominativ, pa "Kule/Kuli Beograd"
# (18 pojava na 79 oglasa) nije prolazio.
DOPUNSKI = {
    # "Kula A" (Kuli A, Kule A, Kulu A) = BW Residences (osnivac, 04.10.2026).
    # PRE "bw kula" da "BW Kula A" ne padne u St. Regis.
    r"\bkul[aeiou]\s+a\b": "BW Residences",
    r"kul[aeiou]\s*\(?\s*(?:st[\.\s]*regis|saint\s*regis)": "BW St. Regis",
    r"st[\.\s]*regis\s*(?:residences?|belgrade|tower|kul[aeiou])": "BW St. Regis",
    r"saint\s*regis": "BW St. Regis",
    r"kul[aeiou]\s*beograd": "BW St. Regis",
    r"belgrade\s*tower": "BW St. Regis",
    # Srpska transkripcija i tipografske greske iz stvarnih oglasa:
    # "U prestiznoj novoj zgradi Talija izdaje se..." (BW Thalia)
    # "u zgradi BW Metrpolitan" (nedostaje 'o')
    r"\btalija\b": "BW Thalia",
    r"metr\w{0,2}polit[ae]n": "BW Metropolitan",
    # "BW Kula / BW Kuli / BW Kule" je marketinsko ime St. Regis-a.
    # Slab signal (vidi SLABI): svaki eksplicitan naziv ga nadjacava,
    # jer BW danas ima vise tornjeva (Aqua, Riva, Verde). Goli "kula"
    # bez "BW" se NE koristi — taj alias je izbacen 09.07.2026 jer je
    # obarao pola kompleksa u premium segment.
    r"\bbw\s*kul[aeiou]\b": "BW St. Regis",
}

# Sabloni cija ocena je ogranicena na 1 — prolaze samo ako nista bolje
# nije nadjeno u istom oglasu.
SLABI = {r"\bbw\s*kul[aeiou]\b"}

# ── imena koja ne traze kvalifikator ────────────────────────────────────
# Viseclana ili strana imena koja se u srpskom tekstu ne pojavljuju kao
# obicne reci. Sve ostalo (Sava, Nova, Elegance, Vista, Aria, Terra...)
# mora imati "bw", "zgrada", "kula", "kompleks", "rezidencija" ili
# "u okviru" u 40 znakova ispred sebe.
NEDVOSMISLENI = [
    r"kul[aeiou]\s+a\b",
    r"st[\.\s]*regis", r"stregis", r"saint\s*regis",
    r"kul[aeiou]\s*beograd", r"belgrade\s*tower",
    r"kings?\s*['’]?\s*park", r"queens?\s*['’]?\s*park",
    r"garden\s*plaza", r"quartet", r"kvartet", r"simf[oi]nija",
    r"parkview", r"metropolitan", r"metropoliten",
    r"bristol\s*residenc", r"the\s*bristol", r"bw\s*residenc",
    r"terraces", r"magnolia", r"riviera", r"arc?adia", r"ark?adia",
]

KVALIFIKATOR = re.compile(
    r"(?:\bbw\b|zgrad\w*|kul[aeiou]\w*|kompleks\w*|lamel\w*|rezidencij\w*"
    r"|residences?|objekt\w*|naselj\w*|u\s+okviru|u\s+sklopu|u\s+sastavu"
    r"|projek\w*|\btower\b)",
    re.I,
)

# Cue ISPRED imena: oglas se hvali blizinom druge zgrade.
NEG_PRE = re.compile(
    r"(?:blizin\w*|\bblizu\b|\bpored\b|nasuprot|preko\s+puta"
    r"|pogled\w*\s+(?:na|ka)\b|vidik\w*|orijentisan\w*\s+ka|udaljen\w*"
    r"|\bminut\w*\s+od\b|koraka\s+od|nadomak|nedaleko|u\s+okru[zž]enju"
    r"|okolin\w*|susedn\w*|kom[sš]ij\w*|\bpoput\b|za\s+razliku\s+od)",
    re.I,
)

LANDMARK_PRE = re.compile(
    r"(?:nalaz\w*\s+se|pru[zž]\w*\s+se|sa\s+terase|sa\s+balkon|iz\s+stana|prozor\w*|koraka|minut\w*"
    r"|promenad\w*|galerij\w*|okru[zž]enj\w*|blizin\w*|pogled\w*)", re.I)

# Cue POSLE imena: rec je o sadrzajima hotela, ne o adresi stana.
NEG_POST = re.compile(
    r"(?:hotel\w*|\bbar\b|\bspa\b|restoran\w*|\blounge\b|kafe\w*|brend\w*)",
    re.I,
)

# ── rezanje potpisa agencije ────────────────────────────────────────────
POTPIS = re.compile(
    r"(?:reg\.?\s*broj\s*posrednik|registarski\s*broj|agencijska\s*provizij"
    r"|posredni[cč]k\w*\s*provizij|\bpib\b|mati[cč]ni\s*broj"
    r"|licenc\w*\s*broj|broj\s*posrednika)",
    re.I,
)
TELEFON = re.compile(
    r"(?:\+\s*381|\b06\d)[\s/.\-]?\d{2,3}[\s/.\-]?\d{3}[\s/.\-]?\d{2,4}"
)

MIN_REZ = 150   # ne reze pre ovog znaka — potpis nikad nije na pocetku


def bez_potpisa(tekst: str) -> str:
    """Odbaci kontakt-blok na kraju oglasa (adresa kancelarije, telefoni)."""
    rez = len(tekst)
    for rx in (POTPIS, TELEFON):
        m = rx.search(tekst)
        if m and MIN_REZ <= m.start() < rez:
            rez = m.start()
    return tekst[:rez]


# ── pogoci ──────────────────────────────────────────────────────────────

def _sabloni():
    """(regex, kanonsko_ime) od najspecificnijeg ka najopstijem.

    Redosled je bitan: prvi sablon koji pokrije neki deo teksta pobedjuje,
    isto kao u buildings.py._find_by_alias. Bez toga bi "Simfonija 2"
    dalo i Simfoniju 2 (tacan alias) i Simfoniju 1 (goli alias) na istoj
    poziciji, pa bi ih tumacili kao dve zgrade u istom oglasu.
    """
    out = []
    for ime in sorted(ALL_BUILDINGS, key=len, reverse=True):
        p = re.escape(ime.lower()).replace(r"'", "['’]?")
        out.append((re.compile(r"\b" + p + r"\b", re.I), ime, False))
    for p, kanon in DOPUNSKI.items():
        out.append((re.compile(p, re.I), kanon, p in SLABI))
    for p, kanon in ALIASES.items():
        out.append((re.compile(p, re.I), kanon, p in SLABI))
    return out


SABLONI = _sabloni()
_NEDVO = [re.compile(p, re.I) for p in NEDVOSMISLENI]


def _nedvosmislen(deo: str) -> bool:
    return any(rx.search(deo) for rx in _NEDVO)


def zgrada_iz_opisa(opis: str, sprat=None, detaljno: bool = False):
    """Naziv BW zgrade iz teksta agenta, ili None ako nije sigurno.

    `sprat` se koristi samo za Simfoniju/Quartet bez broja.
    `detaljno=True` vraca (zgrada, [obrazlozenje]) za dijagnostiku.
    """
    obrazlozenje = []
    if not opis or len(opis) < 20:
        return (None, obrazlozenje) if detaljno else None

    tekst = bez_potpisa(opis)
    s = tekst.lower().replace("’", "'")

    # Oglas uopste nije BW (Park Bristol, Karadjordjeva, Visegradska...)
    for p in NOT_BW:
        if re.search(p, s, re.I):
            obrazlozenje.append(f"crna lista: {p}")
            return (None, obrazlozenje) if detaljno else None

    pokriveno = set()
    kandidati = {}

    for rx, kanon, slab in SABLONI:
        for m in rx.finditer(s):
            span = range(m.start(), m.end())
            if any(i in pokriveno for i in span):
                continue        # specificniji sablon je ovo vec uzeo
            pokriveno.update(span)

            deo = m.group(0)
            pre = s[max(0, m.start() - 40):m.start()]
            post = s[m.end():m.end() + 25]

            # Cue blizine vazi samo ako je NEPOSREDNO ispred imena.
            # Sire prozor obara i tacne pogotke: u "pogledom na BW Aria,
            # u zgradi BW Perla" bi cue od "pogledom" oborio i Perlu.
            if NEG_PRE.search(pre[-25:]):
                obrazlozenje.append(f"'{deo}'@{m.start()} odbijen (blizina)")
                continue
            if NEG_POST.search(post):
                obrazlozenje.append(f"'{deo}'@{m.start()} odbijen (hotel/sadrzaj)")
                continue

            kvalif = bool(KVALIFIKATOR.search(pre[-40:])) or deo.startswith("bw")

            # "Kula Beograd" je i LANDMARK (vidi se sa pola komplexa): u
            # nabrajanju okoline ("nalaze se Sava promenada, Galerija, Kula
            # Beograd", "pogled na park, TC Galeriju, Kulu Beograd") nije adresa
            # stana. Bez kvalifikatora prolazi samo na pocetku oglasa i bez
            # cue-a okoline u prethodnih 120 znakova (04.10.2026: 207k za 35 m2
            # i 346k za 79 m2 su vodjeni kao St. Regis zbog ovoga).
            if (not kvalif and re.search(r"kul[aeiou]\s*beograd|belgrade\s*tower", deo)
                    and (m.start() >= 150 or LANDMARK_PRE.search(s[max(0, m.start() - 120):m.start()]))):
                obrazlozenje.append(f"'{deo}'@{m.start()} odbijen (landmark u okruzenju)")
                continue
            if not (kvalif or _nedvosmislen(deo)):
                obrazlozenje.append(f"'{deo}'@{m.start()} odbijen (bez kvalifikatora)")
                continue

            if slab:
                ocena = 1
            else:
                ocena = 3 if kvalif else 0
                if m.start() < 150:
                    ocena += 2
                elif m.start() < 600:
                    ocena += 1

            ime = kanon
            if ime == "BW Quartet ?":
                ime = quartet_by_floors(sprat)
            elif "simfonija" in ime.lower() and not re.search(
                    r"simf[oi]nija?\s*[12]\b", s):
                ime = simfonija_by_floors(sprat)

            if ocena > kandidati.get(ime, -1):
                kandidati[ime] = ocena
            obrazlozenje.append(f"'{deo}'@{m.start()} -> {ime} (ocena {ocena})")

    if not kandidati:
        return (None, obrazlozenje) if detaljno else None

    rang = sorted(kandidati.items(), key=lambda x: -x[1])
    if len(rang) > 1 and rang[0][1] == rang[1][1]:
        obrazlozenje.append(f"nerazluceno: {rang[0][0]} i {rang[1][0]} "
                            f"imaju istu ocenu {rang[0][1]}")
        return (None, obrazlozenje) if detaljno else None

    return (rang[0][0], obrazlozenje) if detaljno else rang[0][0]


# ── samotest ────────────────────────────────────────────────────────────
# Svi ulazi su skraceni odlomci STVARNIH opisa sa 4zida (30.09.2026).

TESTOVI = [
    ("Ekskluzivan stan u premium zgradi BW Residences u okviru projekta "
     "Beograd na vodi. Na raspolaganju su dve spavace sobe...",
     "BW Residences"),

    ("St. Regis Residences, Kula Beograd - 25. sprat | 76 m2 | Garazno mesto. "
     "Izdaje se jedan od najluksuznijih jednosobnih stanova u Beogradu...",
     "BW St. Regis"),

    ("Luksuzan dvosoban stan u kuli Saint Regis. Stanarima su na raspolaganju "
     "svi sadrzaji objekta.",
     "BW St. Regis"),

    ("Izdaje se trosoban stan za izdavanje u prestiznom kompleksu BW Thalia, "
     "u okviru naselja Beograd na vodi. 0660 429 011 / 770 6977 "
     "Hercegovacka 15/303, BW Simfonija 2, III sprat Agencijska provizija",
     "BW Thalia"),          # potpis agencije ne sme da pobedi

    ("Stan na 14. spratu u Belgrade Waterfront, exudes elegance and attention "
     "to detail, with continuous views of the banks of the River Sava.",
     None),                 # 'elegance' i 'Sava' su obicne reci

    ("Stan sa pristupom premium sadrzajima i uslugama povezanim sa "
     "St. Regis hotelom 5*, ukljucujuci spa i bazen.",
     None),                 # sadrzaj hotela, ne adresa stana

    ("Izdaje se trosoban stan u zgradi BW Quartet 4, povrsine 98.63 m2.",
     "BW Quartet 4"),

    ("Prostran stan u kompleksu Beograd na vodi, zgrada Metropolitan, "
     "na 12. spratu.",
     "BW Metropolitan"),

    ("Luksuzan stan u BW Perla, u Beogradu na vodi. BW Perla predstavlja "
     "savremeni standard stanovanja.",
     "BW Perla"),

    ("Cetvorosoban luksuzan stan za izdavanje, BW Libera, 3.000 eura, 111 m2. "
     "Namesten stan sa tri spavace sobe u zgradi BW Libera.",
     "BW Libera"),

    ("Stan u luksuznoj zgradi u okviru Beograda na vodi - BW Vista. "
     "Iz stana se pruza prelep pogled na reku.",
     "BW Vista"),

    ("Stan u zgradi Verde, unutar projekta Beograd na vodi. Izuzetna zgrada "
     "u ponudi - Verde - zgrada koja posedjuje sve sadrzaje.",
     "BW Verde"),

    ("Izdaje se stan sa pogledom na BW Aria, u zgradi BW Perla.",
     "BW Perla"),          # 'pogled na BW Aria' se ne racuna

    ("Stan u neposrednoj blizini kompleksa BW Aria, na 5. spratu.",
     None),                # samo blizina, adresa stana nije data

    ("Stan u kuli St. Regis, na 24. spratu. Stanarima su dostupni svi "
     "sadrzaji St. Regis hotela, bar i spa centar.",
     "BW St. Regis"),      # prvi pogodak je adresa, drugi je sadrzaj

    ("Prostran cetvorosoban stan sa pogledom na reku i park. Stan je "
     "polunamesten, sa kompletnom kuhinjom i svim potrebnim uredjajima.",
     None),                # nijedna zgrada nije pomenuta

    ("Park Bristol 41m2 - Karadjordjeva, izdaje se dvosoban stan.",
     None),                # crna lista

    ("Izdaje se ekskluzivan, kompletno opremljen stan u BW Kuli, jednom od "
     "najprestiznijih stambenih objekata u regionu.",
     "BW St. Regis"),      # 'BW Kula' je marketinsko ime St. Regis-a

    ("Stan u BW Kuli, u zgradi BW Aqua, na 18. spratu.",
     "BW Aqua"),           # eksplicitan naziv nadjacava slab signal

    ("U ponudi je luksuzan trosoban stan u zgradi BW Metrpolitan, "
     "na ulasku u kompleks.",
     "BW Metropolitan"),   # tipografska greska agenta

    ("Talija, Beograd na vodi | Elegantan stan 57 m2 sa garaznim mestom. "
     "U prestiznoj novoj zgradi Talija izdaje se stan.",
     "BW Thalia"),         # srpska transkripcija
]


if __name__ == "__main__":
    palo = 0
    print(f"{'ocekivano':22} {'dobijeno':22} ulaz")
    print("-" * 100)
    for opis, ocekivano in TESTOVI:
        dobijeno, zasto = zgrada_iz_opisa(opis, sprat="12/25", detaljno=True)
        ok = dobijeno == ocekivano
        palo += 0 if ok else 1
        znak = "OK " if ok else "PAO"
        print(f"{znak} {str(ocekivano):22} {str(dobijeno):22} {opis[:52]}...")
        if not ok:
            for r in zasto:
                print(f"      {r}")
    print("-" * 100)
    print(f"{len(TESTOVI) - palo}/{len(TESTOVI)} prolazi"
          + ("" if not palo else f"  ({palo} PALO)"))
