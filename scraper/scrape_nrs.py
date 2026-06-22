"""
scrape_nrs.py — BnV Tracker scraper za nekretnine.rs
Verzija: 1.0

Scrape-uje listinge sa:
  Prodaja: https://www.nekretnine.rs/prodaja-stanova/beograd/beograd-na-vodi-palata-pravde/
  Renta:   https://www.nekretnine.rs/izdavanje-stanova/beograd/beograd-na-vodi-palata-pravde/

Output:
  data/latest_nrs_prodaja.json
  data/latest_nrs_renta.json
  data/history_nrs.json
  data/eod_nrs_YYYY-MM-DD.json

Pokretanje: python scraper/scrape_nrs.py
Zahteva: SCRAPERAPI_KEY env varijablu
"""

import re
import json
import time
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── CONFIG ─────────────────────────────────────────────────────────────────
API_KEY     = os.environ.get("SCRAPERAPI_KEY", "4dba199ae91807746affc7e94e446ce0")
SCRAPER_URL = "http://api.scraperapi.com"

BASE_PRODAJA = "https://www.nekretnine.rs/prodaja-stanova/beograd/beograd-na-vodi-palata-pravde/lista/stranica/{}/"
BASE_RENTA   = "https://www.nekretnine.rs/izdavanje-stanova/beograd/beograd-na-vodi-palata-pravde/lista/stranica/{}/"
SITE_BASE    = "https://www.nekretnine.rs"

DELAY_PAGE   = 3.0    # sekundi između stranica
DELAY_DETAIL = 1.5    # sekundi za individual oglas fetch
MAX_PAGES    = 25     # safety cap
MAX_EMPTY    = 3      # stop posle N uzastopnih praznih stranica

# ── STRUKTURA MAPPING ───────────────────────────────────────────────────────
STR_MAP = {
    "garsonjera":    "1.0",
    "studio":        "1.0",
    "jednosoban":    "1.0",
    "jednosobni":    "1.0",
    "jednoiposoban": "1.5",
    "jednoiposobni": "1.5",
    "dvosoban":      "2.0",
    "dvosobni":      "2.0",
    "dvoiposoban":   "2.5",
    "dvoiposobni":   "2.5",
    "trosoban":      "3.0",
    "trosobni":      "3.0",
    "troiposoban":   "3.5",
    "troiposobni":   "3.5",
    "četvorosoban":  "4.0",
    "četvorosobni":  "4.0",
    "cetvorosoban":  "4.0",
    "cetvorosobni":  "4.0",
    "petosoban":     "5.0",
    "petosobni":     "5.0",
    "višesoban":     "5.0",
}

STR_LABEL = {
    "1.0": "Garsonjera/Studio",
    "1.5": "Jednoiposoban",
    "2.0": "Dvosoban",
    "2.5": "Dvoiposoban",
    "3.0": "Trosoban",
    "3.5": "Troiposoban",
    "4.0": "Četvorosoban",
    "5.0": "Petosoban+",
}

# ── BUILDINGS ───────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from buildings import ALIASES, NOT_BW, is_blacklisted
    _ALIAS_COMPILED = [(re.compile(p, re.I), v) for p, v in ALIASES.items()]
    print("buildings.py učitan.")
except ImportError:
    print("UPOZORENJE: buildings.py nije nađen — koristim fallback aliase.")
    _ALIAS_COMPILED = [
        (re.compile(r"quartet\s*1|kvartet\s*1", re.I), "BW Quartet 1"),
        (re.compile(r"quartet\s*2|kvartet\s*2", re.I), "BW Quartet 2"),
        (re.compile(r"quartet\s*3|kvartet\s*3", re.I), "BW Quartet 3"),
        (re.compile(r"quartet\s*4|kvartet\s*4", re.I), "BW Quartet 4"),
        (re.compile(r"quartet|kvartet",          re.I), "BW Quartet ?"),
        (re.compile(r"simf[oi]nija?\s*1",        re.I), "BW Simfonija 1"),
        (re.compile(r"simf[oi]nija?\s*2",        re.I), "BW Simfonija 2"),
        (re.compile(r"simf[oi]nija?|simfonia",   re.I), "BW Simfonija 1"),
        (re.compile(r"\biris\b",                 re.I), "BW Iris"),
        (re.compile(r"\baurora\b",               re.I), "BW Aurora"),
        (re.compile(r"\briviera\b",              re.I), "BW Riviera"),
        (re.compile(r"bw\s+residenc[eyi]",       re.I), "BW Residences"),
        (re.compile(r"st[\.\s]*regis|stregis",   re.I), "BW St. Regis"),
        (re.compile(r"kul[aiue]",                re.I), "BW St. Regis"),
        (re.compile(r"\bverde\b",                re.I), "BW St. Regis"),
        (re.compile(r"\bsole\b",                 re.I), "BW Sole"),
        (re.compile(r"\bperla\b",                re.I), "BW Perla"),
        (re.compile(r"kings?\s*['\u2019]?\s*park|\bking\b", re.I), "BW King's Park"),
        (re.compile(r"queens?\s*['\u2019]?\s*park",         re.I), "BW Queen's Park"),
        (re.compile(r"\bterraces\b",             re.I), "BW Terraces"),
        (re.compile(r"\bvista\b",                re.I), "BW Vista"),
        (re.compile(r"\blibera\b",               re.I), "BW Libera"),
        (re.compile(r"\bthalia\b",               re.I), "BW Thalia"),
        (re.compile(r"\baria\b",                 re.I), "BW Aria"),
        (re.compile(r"\beden\b",                 re.I), "BW Eden"),
        (re.compile(r"\bmetropolitan\b|metropoliten", re.I), "BW Metropolitan"),
        (re.compile(r"\bterr?a\b",               re.I), "BW Terra"),
        (re.compile(r"\bscala\b",                re.I), "BW Scala"),
        (re.compile(r"\beterna\b",               re.I), "BW Eterna"),
        (re.compile(r"\bsensa\b",                re.I), "BW Sensa"),
        (re.compile(r"\bmagnolia\b",             re.I), "BW Magnolia"),
        (re.compile(r"\blumia\b",                re.I), "BW Lumia"),
        (re.compile(r"parkview",                 re.I), "BW Parkview"),
        (re.compile(r"arc?adia|ark?adia",        re.I), "BW Arcadia"),
        (re.compile(r"\bnova\b",                 re.I), "BW Nova"),
        (re.compile(r"\bsava\b",                 re.I), "BW Sava"),
        (re.compile(r"\belegance\b",             re.I), "BW Elegance"),
        (re.compile(r"\bvictoria\b",             re.I), "BW Victoria"),
    ]
    NOT_BW_PAT = [re.compile(p, re.I) for p in [
        r"park\s*bristol", r"karađorđeva|karadjordjeva",
        r"višegradska|visegradska", r"risanska",
    ]]
    def is_blacklisted(text):
        t = (text or "").lower()
        return any(p.search(t) for p in NOT_BW_PAT)

def identify_building(text: str) -> str | None:
    if not text:
        return "BW (neidentifikovano)"
    if is_blacklisted(text):
        return None
    for pattern, name in _ALIAS_COMPILED:
        if pattern.search(text):
            return name
    return "BW (neidentifikovano)"

# ── SCRAPERAPI FETCH ────────────────────────────────────────────────────────
def fetch(url: str, session: requests.Session, render: bool = False) -> BeautifulSoup | None:
    """Fetch URL kroz ScraperAPI."""
    params = {
        "api_key": API_KEY,
        "url":     url,
        "render":  "true" if render else "false",
    }
    for attempt in range(1, 4):
        try:
            r = session.get(SCRAPER_URL, params=params, timeout=60)
            if r.status_code == 200 and len(r.text) > 500:
                return BeautifulSoup(r.text, "html.parser")
            print(f"    Fetch {url} → {r.status_code} (pokušaj {attempt})")
        except Exception as e:
            print(f"    Fetch greška {url}: {e} (pokušaj {attempt})")
        time.sleep(2 * attempt)
    return None

# ── PARSE HELPERS ───────────────────────────────────────────────────────────
def parse_struktura(text: str) -> tuple[str | None, str | None]:
    t = text.lower()
    for key, val in STR_MAP.items():
        if key in t:
            return val, STR_LABEL.get(val)
    return None, None

def parse_cena(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text.replace(".", "").replace(",", ""))
    try:
        val = float(cleaned)
        return val if 100 < val < 100_000_000 else None
    except (ValueError, TypeError):
        return None

def parse_m2(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+[\.,]?\d*)\s*m", text, re.I)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None

def make_dedup_key(oglas_id: str) -> str:
    return hashlib.md5(oglas_id.encode()).hexdigest()[:10]

# ── PARSE LISTING PAGE ──────────────────────────────────────────────────────
def parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    """
    Izvuci osnovne podatke o oglasima sa liste.
    nekretnine.rs HTML struktura (statički rendered):
      - Svaki oglas: <article class="property-article ...">
      - Link: <a href="/oglasi/ID/">
      - Naslov: <h2> ili <h3> unutar article
      - Cena: element sa klasom koja sadrži 'price'
      - Agencija: <img alt="IME AGENCIJE"> unutar .advertiser ili .agency
      - M2 info: u feature listama
    """
    results = []

    # Primarni selector
    articles = soup.select("article")
    if not articles:
        # Fallback — traži sve unique linkove ka /oglasi/
        seen = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = re.match(r"(/oglasi/(\d+)/?)", href)
            if m and m.group(2) not in seen:
                seen.add(m.group(2))
                results.append({"id": m.group(2), "_partial": True})
        return results

    for art in articles:
        try:
            # Link i ID
            a_tag = art.select_one("a[href*='/oglasi/']")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            m = re.match(r".*?/oglasi/(\d+)/?", href)
            if not m:
                continue
            oglas_id = m.group(1)

            # Naslov
            h = art.select_one("h2, h3, h4")
            naslov = h.get_text(strip=True) if h else a_tag.get("title", "")[:200]

            # Cena
            cena_el = art.select_one("[class*='price'], .price, .cena")
            cena = parse_cena(cena_el.get_text(strip=True)) if cena_el else None

            # Agencija — img alt
            agencija = None
            for img in art.select("img"):
                alt = img.get("alt", "").strip()
                # Agencija ima puno ime sve caps ili mixed
                if alt and len(alt) > 3 and alt.lower() not in ("foto", "slika", "image", "logo", ""):
                    agencija = alt
                    break

            # M2
            m2 = parse_m2(naslov)
            if not m2:
                for el in art.select("li, span, div"):
                    t = el.get_text(strip=True)
                    if "m²" in t or ("m2" in t.lower() and re.search(r"\d", t)):
                        m2 = parse_m2(t)
                        if m2:
                            break

            results.append({
                "id":       oglas_id,
                "naslov":   naslov,
                "cena":     cena,
                "agencija": agencija,
                "m2":       m2,
            })
        except Exception as e:
            print(f"    Greška parsiranja article: {e}")
            continue

    return results

# ── PARSE DETAIL PAGE ───────────────────────────────────────────────────────
def parse_detail(oglas_id: str, partial: dict, mode: str, session: requests.Session) -> dict | None:
    """
    Dohvati detaljnu stranicu oglasa i izvuci:
    - Zgrada (iz meta-description/og:description/H1/opis)
    - Agencija (ako nije nađena na listi)
    - Sprat, m2, cena (ako nisu nađeni na listi)
    """
    url = f"{SITE_BASE}/oglasi/{oglas_id}/"
    soup = fetch(url, session, render=False)
    if not soup:
        return None

    # ── Zgrada ──────────────────────────────────────────────────
    zgrada = "BW (neidentifikovano)"

    # 1. meta-description — najpouzdaniji (Kadena uvek piše zgrada ovde)
    for meta_name in [("name", "description"), ("property", "og:description")]:
        meta = soup.find("meta", {meta_name[0]: meta_name[1]})
        if meta:
            content = meta.get("content", "")
            z = identify_building(content)
            if z and z != "BW (neidentifikovano)":
                zgrada = z
                break

    # 2. H1 naslov
    if zgrada == "BW (neidentifikovano)":
        h1 = soup.select_one("h1")
        if h1:
            z = identify_building(h1.get_text())
            if z and z != "BW (neidentifikovano)":
                zgrada = z

    # 3. Opis tekst
    if zgrada == "BW (neidentifikovano)":
        opis = soup.select_one(
            ".description, [class*='description'], .property-description, "
            "[class*='opis'], .offer-description"
        )
        if opis:
            z = identify_building(opis.get_text()[:800])
            if z:
                zgrada = z

    if not zgrada:
        return None  # blacklisted

    # ── Agencija ─────────────────────────────────────────────────
    agencija = partial.get("agencija")
    if not agencija:
        # Traži u sekciji oglašivača
        for sel in [
            ".agency-name", "[class*='agency'] h2", "[class*='agency'] h3",
            "[class*='advertiser'] strong", ".advertiser-name",
            "a[href*='/agencije-za-nekretnine/']",
        ]:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(strip=True)
                if t and len(t) > 2:
                    agencija = t
                    break
        # Fallback — img alt u advertiser sekciji
        if not agencija:
            for img in soup.select("[class*='advertiser'] img, [class*='agency'] img"):
                alt = img.get("alt", "").strip()
                if alt and len(alt) > 2:
                    agencija = alt
                    break

    # Normalizuj agenciju — ukloni duplirane reči (nekretnine.rs ponekad duplikuje)
    if agencija:
        words = agencija.split()
        half = len(words) // 2
        if half > 0 and words[:half] == words[half:]:
            agencija = " ".join(words[:half])
        agencija = agencija.strip() or None

    # ── Sprat ─────────────────────────────────────────────────────
    sprat = None
    sprat_patterns = [
        ("dt", "sprat"),
        ("th", "sprat"),
        ("[class*='floor']", None),
        ("[class*='sprat']", None),
    ]
    for dt in soup.select("dt, th, .label, [class*='label']"):
        if "sprat" in dt.get_text(strip=True).lower():
            nxt = dt.find_next_sibling()
            if nxt:
                sprat = nxt.get_text(strip=True)
                break
    # Alternativno iz "Karakteristike" sekcije
    if not sprat:
        for el in soup.select("li, div"):
            t = el.get_text(strip=True)
            if re.match(r"^sprat:?\s*\w+", t, re.I):
                sprat = re.sub(r"^sprat:?\s*", "", t, flags=re.I).strip()
                break

    # ── M2 i Cena ─────────────────────────────────────────────────
    m2   = partial.get("m2")
    cena = partial.get("cena")

    if not m2:
        # Iz meta options
        meta_opt = soup.find("meta", {"name": "nekretnine_rs:options"})
        if meta_opt:
            m2 = parse_m2(meta_opt.get("content", ""))
        # Iz karakteristika
        if not m2:
            for el in soup.select("li, div, span"):
                t = el.get_text(strip=True)
                if "m²" in t and re.search(r"\d+", t):
                    val = parse_m2(t)
                    if val and 10 < val < 5000:
                        m2 = val
                        break

    if not cena:
        for sel in [".price", "[class*='price']", ".cena", "[class*='cena']"]:
            el = soup.select_one(sel)
            if el:
                cena = parse_cena(el.get_text(strip=True))
                if cena:
                    break

    # ── Struktura ─────────────────────────────────────────────────
    naslov   = partial.get("naslov", "")
    str_val, str_lbl = parse_struktura(naslov)

    # ── Cena po m2 ────────────────────────────────────────────────
    cena_m2 = None
    if cena and m2 and m2 > 0 and mode == "prodaja":
        cena_m2 = round(cena / m2)

    return {
        "id":         oglas_id,
        "url":        url,
        "naslov":     naslov,
        "zgrada":     zgrada,
        "agencija":   agencija,
        "struktura":  str_val,
        "str_label":  str_lbl,
        "m2":         m2,
        "cena":       cena,
        "cena_m2":    cena_m2,
        "sprat":      sprat,
        "mode":       mode,
        "source":     "nekretnine.rs",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "dedup_key":  make_dedup_key(oglas_id),
    }

# ── SCRAPE MODE ──────────────────────────────────────────────────────────────
def scrape_mode(mode: str, session: requests.Session) -> list[dict]:
    base     = BASE_PRODAJA if mode == "prodaja" else BASE_RENTA
    partials = []
    seen_ids = set()
    empty    = 0

    # ── Faza 1: Prikupi sve ID-ove i parcijalne podatke sa lista ──
    print(f"\n  Faza 1: prikupljanje listinga sa lista...")
    for page in range(1, MAX_PAGES + 1):
        url = base.format(page)
        print(f"    [{mode}] Stranica {page}")
        soup = fetch(url, session)

        if not soup:
            empty += 1
            if empty >= MAX_EMPTY:
                print(f"    Stop — {MAX_EMPTY} uzastopne greške")
                break
            time.sleep(DELAY_PAGE)
            continue

        items = parse_listing_page(soup)
        if not items:
            empty += 1
            print(f"    Stranica {page}: 0 listinga (empty {empty}/{MAX_EMPTY})")
            if empty >= MAX_EMPTY:
                break
            time.sleep(DELAY_PAGE)
            continue

        empty = 0
        new = 0
        for item in items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                partials.append(item)
                new += 1

        print(f"    Stranica {page}: {new} novih ({len(partials)} ukupno)")

        # Provera ukupnog broja iz H1
        h1 = soup.select_one("h1")
        if h1:
            cnt_m = re.search(r"(\d+)\s+rezultat", h1.get_text())
            if cnt_m and len(partials) >= int(cnt_m.group(1)):
                print(f"    Dostignut ukupan broj ({cnt_m.group(1)}) — kraj liste")
                break

        time.sleep(DELAY_PAGE)

    print(f"  Faza 1 završena: {len(partials)} oglasa")

    # ── Faza 2: Detail fetch za svaki oglas ───────────────────────
    print(f"\n  Faza 2: detail fetch ({len(partials)} oglasa)...")
    listings = []
    for i, partial in enumerate(partials, 1):
        oglas_id = partial["id"]
        if i % 10 == 0 or i == 1:
            print(f"    [{mode}] {i}/{len(partials)}")
        detail = parse_detail(oglas_id, partial, mode, session)
        if detail:
            listings.append(detail)
        time.sleep(DELAY_DETAIL)

    print(f"  Faza 2 završena: {len(listings)} listinga")
    return listings

# ── STATS ───────────────────────────────────────────────────────────────────
def compute_stats(listings: list[dict]) -> dict:
    po_str = {}
    po_zgr = {}
    for l in listings:
        s  = l.get("struktura") or "?"
        z  = l.get("zgrada")   or "BW (neidentifikovano)"
        c  = l.get("cena")
        m  = l.get("cena_m2")
        sq = l.get("m2")

        if s not in po_str:
            po_str[s] = {"label": l.get("str_label", s), "count": 0,
                          "cene": [], "cene_m2": [], "m2s": [], "zgrade": set()}
        po_str[s]["count"] += 1
        if c:  po_str[s]["cene"].append(c)
        if m:  po_str[s]["cene_m2"].append(m)
        if sq: po_str[s]["m2s"].append(sq)
        po_str[s]["zgrade"].add(z)

        if z not in po_zgr:
            po_zgr[z] = {"count": 0, "strukture": set(), "cene": []}
        po_zgr[z]["count"] += 1
        if s != "?": po_zgr[z]["strukture"].add(s)
        if c: po_zgr[z]["cene"].append(c)

    def agg(v):
        return {"min": min(v), "max": max(v), "avg": round(sum(v)/len(v))} if v else None

    return {
        "po_strukturi": {
            s: {**v, "cena": agg(v["cene"]), "cena_m2": agg(v["cene_m2"]),
                "m2": agg(v["m2s"]), "zgrade": sorted(v["zgrade"])}
            for s, v in po_str.items()
        },
        "po_zgradi": {
            z: {"count": v["count"], "strukture": sorted(v["strukture"]), "cena": agg(v["cene"])}
            for z, v in po_zgr.items()
        },
    }

# ── DIFF ─────────────────────────────────────────────────────────────────────
def compute_diff(new_l: list[dict], old_l: list[dict]) -> dict:
    new_ids = {l["id"] for l in new_l}
    old_ids = {l["id"] for l in old_l}
    nm = {l["id"]: l for l in new_l}
    om = {l["id"]: l for l in old_l}
    return {
        "new":          [nm[i] for i in new_ids - old_ids],
        "removed":      [om[i] for i in old_ids - new_ids],
        "count_change": len(new_ids) - len(old_ids),
    }

# ── IO ───────────────────────────────────────────────────────────────────────
def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → {path}")

def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"API_KEY aktivan: {API_KEY[:8]}...")

    data_dir = Path(__file__).parent.parent / "data"
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso  = datetime.now(timezone.utc).isoformat()
    session  = requests.Session()

    for mode in ["prodaja", "renta"]:
        print(f"\n{'='*60}")
        print(f"  nekretnine.rs — {mode.upper()}")
        print(f"{'='*60}")

        latest_path  = data_dir / f"latest_nrs_{mode}.json"
        history_path = data_dir / "history_nrs.json"
        eod_path     = data_dir / f"eod_nrs_{today}.json"

        prev_listings = load_json(str(latest_path)).get("listings", [])
        listings      = scrape_mode(mode, session)

        if not listings:
            print(f"  Nema listinga za {mode} — preskačem")
            continue

        m2_prices = [l["cena_m2"] for l in listings if l.get("cena_m2")]
        avg_m2    = round(sum(m2_prices) / len(m2_prices)) if m2_prices else None
        diff      = compute_diff(listings, prev_listings)
        stats     = compute_stats(listings)

        payload = {
            "source":       "nekretnine.rs",
            "mode":         mode,
            "scraped_at":   now_iso,
            "date":         today,
            "total_raw":    len(listings),
            "total_unique": len(listings),
            "total_dups":   0,
            "avg_m2":       avg_m2,
            "listings":     listings,
            "diff":         diff,
            "stats":        stats,
        }

        save_json(str(latest_path), payload)

        eod = load_json(str(eod_path), {})
        eod[mode] = payload
        save_json(str(eod_path), eod)

        history = load_json(str(history_path), [])
        entry   = {
            "date":         today,
            "mode":         mode,
            "source":       "nekretnine.rs",
            "count":        len(listings),
            "total_raw":    len(listings),
            "total_unique": len(listings),
            "total_dups":   0,
            "avg_m2":       avg_m2,
            "diff_new":     len(diff["new"]),
            "diff_removed": len(diff["removed"]),
        }
        existing = next((e for e in history if e["date"] == today and e["mode"] == mode), None)
        if existing:
            history[history.index(existing)] = entry
        else:
            history.append(entry)
        save_json(str(history_path), history)

        print(f"\n  [{mode}] DONE — {len(listings)} listinga, avg €/m²: {avg_m2}")
        print(f"  Novi: {len(diff['new'])}, Skinuti: {len(diff['removed'])}")

    print(f"\n{'='*60}")
    print("  SCRAPE ZAVRŠEN")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
