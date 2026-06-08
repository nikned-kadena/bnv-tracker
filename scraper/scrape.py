#!/usr/bin/env python3
"""
BnV Tracker — Halo Oglasi scraper
Pokreće se kao GitHub Actions cron job.
Koristi Playwright (headless Chromium) da zaobiđe JS rendering i bot detekciju.
"""

import asyncio
import json
import os
import re
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ─── CONFIG ─────────────────────────────────────────────────────────────────
BASE_URL   = "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd-savski-venac-beograd-na-vodi"
DATA_DIR   = Path(__file__).parent.parent / "data"
MAX_PAGES  = 40          # sajt ima ~564 oglasa / 15 po stranici ≈ 38 stranica
PAGE_DELAY = 2.5         # sekunde između stranica (da ne triggeruje rate-limit)
TIMEOUT    = 30_000      # ms

STRUCTURE_MAP = {
    "0.5": "Garsonjera/Studio",
    "1.0": "Jednosoban",
    "1.5": "Jednoiposoban",
    "2.0": "Dvosoban",
    "2.5": "Dvoiposoban",
    "3.0": "Trosoban",
    "3.5": "Troiposoban",
    "4.0": "Četvorosoban",
    "4.5": "Četvoriposoban",
    "5.0": "Petosoban+",
}

# Regex za cenu u EUR
PRICE_RE   = re.compile(r"([\d\.,]+)\s*[€eE]")
PRICE_M2_RE = re.compile(r"([\d\.,]+)\s*[€eE]\s*/\s*m")

# BW zgrada canonicalization
BW_NAMES = [
    "Alegra","Aqua","Aria","Aurora","Bella","Diva","Dolce","Eden","Eterna",
    "Iris","Kings Park","Kula","Libera","Lumia","Magnolia","Metropolitan",
    "Nika","Nota","Parkview","Perla","Quartet 1","Quartet 2","Quartet 3",
    "Quartet 4","Rima","Riviera","Sava Riverline","Scala","Sensa","Simfonija 1",
    "Simfonija 2","Simfonija","Sole","St. Regis","Terraces","Thalia",
    "Verde","Victoria","Vista",
]

def canonical_building(text: str) -> str:
    """Izvuci kanonski naziv zgrade iz teksta oglasa."""
    if not text:
        return "BW (nepoznato)"
    t = text.upper()
    for name in BW_NAMES:
        if name.upper() in t:
            return f"BW {name}"
    # fallback: traži BW + reč
    m = re.search(r"\bBW\s+([A-ZŠĐČĆŽ][a-zšđčćžA-Z]+)", text)
    if m:
        return f"BW {m.group(1)}"
    return "BW (ostalo)"

def parse_price(text: str) -> Optional[int]:
    """Parsira cenu iz stringa, vraća EUR int ili None."""
    if not text:
        return None
    # ukloni tačke/zareze kao separatore hiljada
    clean = text.replace(".", "").replace(",", "")
    m = re.search(r"(\d{5,10})", clean)
    if m:
        val = int(m.group(1))
        if 50_000 < val < 20_000_000:
            return val
    return None

def listing_hash(l: dict) -> str:
    """Stabilan hash za dedup — identifikuje istu nekretninu."""
    key = f"{l.get('zgrada','')}|{l.get('struktura','')}|{round(l.get('m2',0)/3)}"
    return hashlib.md5(key.encode()).hexdigest()[:10]

def dedup(listings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Vrati (unique, dups). Čuva prvi pojavljeni oglas po hash ključu."""
    seen = {}
    unique, dups = [], []
    for l in listings:
        h = listing_hash(l)
        if h not in seen:
            seen[h] = l["id"]
            l["dedup_key"] = h
            unique.append(l)
        else:
            dups.append({"id": l["id"], "original_id": seen[h], "dedup_key": h})
    return unique, dups

def diff_listings(prev: list[dict], curr: list[dict]) -> dict:
    """Uporedi prethodni i trenutni snapshot — vrati nove i skinute oglase."""
    prev_ids = {l["id"] for l in prev}
    curr_ids = {l["id"] for l in curr}
    new_ids     = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    curr_map    = {l["id"]: l for l in curr}
    return {
        "new":     [curr_map[i] for i in new_ids if i in curr_map],
        "removed": [l for l in prev if l["id"] in removed_ids],
        "count_change": len(curr) - len(prev),
    }

# ─── SCRAPER ────────────────────────────────────────────────────────────────
async def scrape_page(page, url: str) -> list[dict]:
    """Scrape-uj jednu stranicu i vrati listu listinga."""
    listings = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
        # Čekaj da se učitaju product card-ovi
        await page.wait_for_selector(".product-item, .classified-list-item, [class*='product']", timeout=15_000)
    except PWTimeout:
        print(f"  ⚠ Timeout na {url}", file=sys.stderr)
        return listings

    # Pokušaj nekoliko selektora — sajt može da promeni strukturu
    cards = await page.query_selector_all(".product-item")
    if not cards:
        cards = await page.query_selector_all("[class*='classified-item']")
    if not cards:
        cards = await page.query_selector_all("li[class*='product']")

    print(f"  → {len(cards)} kartica na {url.split('?')[1] if '?' in url else 'str.1'}")

    for card in cards:
        try:
            l = await extract_listing(card, page)
            if l:
                listings.append(l)
        except Exception as e:
            print(f"  ⚠ Greška pri parsiranju kartice: {e}", file=sys.stderr)

    return listings

async def extract_listing(card, page) -> Optional[dict]:
    """Izvuci sve podatke iz jedne product kartice."""
    # ID iz URL-a ili data atributa
    link_el = await card.query_selector("a[href*='/nekretnine/prodaja-stanova/']")
    if not link_el:
        return None
    href = await link_el.get_attribute("href") or ""
    # ID je poslednji segment URL-a
    m = re.search(r"/(\d{10,})(?:\?|$)", href)
    listing_id = m.group(1) if m else href.split("/")[-1].split("?")[0]

    # Naslov
    title_el = await card.query_selector("h3, h2, [class*='title'], [class*='naziv']")
    title = (await title_el.inner_text()).strip() if title_el else ""

    # Cena
    price_el = await card.query_selector("[class*='price'], [class*='cena'], .price")
    price_text = (await price_el.inner_text()).strip() if price_el else ""
    cena = parse_price(price_text)

    # Cena po m2
    price_m2_el = await card.query_selector("[class*='price-m2'], [class*='cena-m2'], .price-m2")
    price_m2_text = (await price_m2_el.inner_text()).strip() if price_m2_el else ""
    cena_m2 = parse_price(price_m2_text)

    # Atributi (m2, sobe, sprat)
    m2_val, sobe_val, sprat_val = None, None, None

    attr_els = await card.query_selector_all("[class*='feature'], [class*='characteristic'], [class*='attr']")
    for el in attr_els:
        txt = (await el.inner_text()).strip()
        if "m2" in txt.lower() or "m²" in txt:
            m = re.search(r"([\d,\.]+)\s*m", txt)
            if m:
                try:
                    m2_val = float(m.group(1).replace(",", "."))
                except:
                    pass
        if "soba" in txt.lower() or "broj soba" in txt.lower():
            m = re.search(r"([\d,\.]+)", txt)
            if m:
                try:
                    sobe_val = float(m.group(1).replace(",", "."))
                except:
                    pass
        if "sprat" in txt.lower():
            m = re.search(r"([IVXLCM]+|\d+)\s*/?\s*([IVXLCM]+|\d+)?", txt)
            if m:
                sprat_val = m.group(0).strip()

    # Fallback: izvuci iz naslova/opisa
    if m2_val is None:
        m = re.search(r"([\d,\.]+)\s*m[²2]", title, re.I)
        if m:
            try:
                m2_val = float(m.group(1).replace(",", "."))
            except:
                pass
    if sobe_val is None:
        m = re.search(r"([\d,\.]+)\s*[Bb]roj\s*soba", title)
        if not m:
            # pokušaj iz URL-a (ima /jednosoban, /dvosoban...)
            slug_map = {"garsonjera": 0.5, "jednosoban": 1.0, "jednoiposoban": 1.5,
                        "dvosoban": 2.0, "dvoiposoban": 2.5, "trosoban": 3.0,
                        "troiposoban": 3.5, "cetvorosoban": 4.0, "petosoban": 5.0}
            for slug, val in slug_map.items():
                if slug in href.lower():
                    sobe_val = val
                    break

    # Oglas data-sobe atribut (halo oglasi ga često ima)
    data_sobe = await card.get_attribute("data-sobe")
    if data_sobe and sobe_val is None:
        try:
            sobe_val = float(data_sobe)
        except:
            pass

    # Oglašivač tip
    agency_el = await card.query_selector("[class*='agency'], [class*='agencija'], [class*='advertiser']")
    oglasivac = "nepoznato"
    if agency_el:
        ag_text = (await agency_el.inner_text()).strip().lower()
        if "vlasnik" in ag_text:
            oglasivac = "vlasnik"
        elif "agencija" in ag_text or "agency" in ag_text:
            oglasivac = "agencija"
        elif "investitor" in ag_text:
            oglasivac = "investitor"

    # Datum objave
    date_el = await card.query_selector("[class*='date'], [class*='datum'], time")
    datum_raw = (await date_el.inner_text()).strip() if date_el else ""

    # Naziv zgrade iz naslova
    zgrada = canonical_building(title)

    # Izračunaj cenu po m2 ako nije parsirana
    if cena and m2_val and not cena_m2:
        cena_m2 = round(cena / m2_val)

    return {
        "id":         listing_id,
        "url":        f"https://www.halooglasi.com{href}" if href.startswith("/") else href,
        "naslov":     title,
        "zgrada":     zgrada,
        "struktura":  str(sobe_val) if sobe_val is not None else None,
        "str_label":  STRUCTURE_MAP.get(str(sobe_val), "nepoznato") if sobe_val is not None else "nepoznato",
        "m2":         m2_val,
        "cena":       cena,
        "cena_m2":    cena_m2,
        "sprat":      sprat_val,
        "oglasivac":  oglasivac,
        "datum_raw":  datum_raw,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

async def get_total_pages(page) -> int:
    """Pokuša da utvrdi ukupan broj stranica iz paginacije."""
    try:
        # Halo oglasi paginacija
        pag = await page.query_selector_all("[class*='pagination'] a, [class*='pager'] a")
        nums = []
        for el in pag:
            t = (await el.inner_text()).strip()
            if t.isdigit():
                nums.append(int(t))
        if nums:
            return min(max(nums), MAX_PAGES)
        # Fallback: ukupan broj oglasa iz naslova/breadcrumb
        count_el = await page.query_selector("[class*='total-count'], [class*='results-count'], [class*='broj-oglasa']")
        if count_el:
            ct = (await count_el.inner_text()).strip()
            m = re.search(r"(\d+)", ct.replace(".", "").replace(",", ""))
            if m:
                total = int(m.group(1))
                return min((total // 15) + 1, MAX_PAGES)
    except Exception as e:
        print(f"  ⚠ Greška pri detekciji broja stranica: {e}", file=sys.stderr)
    return MAX_PAGES

async def scrape_all() -> dict:
    """Glavni scraper — prolazi sve stranice i vraća kompletan snapshot."""
    all_listings = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="sr-RS",
        )
        # Sakrij Playwright fingerprint
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        # Stranica 1
        print(f"Scrapujem stranicu 1...")
        page1_listings = await scrape_page(page, BASE_URL)
        all_listings.extend(page1_listings)

        total_pages = await get_total_pages(page)
        print(f"Ukupno stranica: {total_pages}")

        # Stranice 2..N
        for p in range(2, total_pages + 1):
            url = f"{BASE_URL}?page={p}"
            print(f"Scrapujem stranicu {p}/{total_pages}...")
            await asyncio.sleep(PAGE_DELAY)  # Rate limiting
            listings = await scrape_page(page, url)
            if not listings:
                print(f"  → Prazna stranica {p}, zaustavljam.")
                break
            all_listings.extend(listings)

        await browser.close()

    print(f"\nUkupno sirovanih listinga: {len(all_listings)}")
    unique, dups = dedup(all_listings)
    print(f"Nakon deduplikacije: {len(unique)} unique, {len(dups)} duplikata")

    return {
        "scraped_at":      datetime.now(timezone.utc).isoformat(),
        "total_raw":       len(all_listings),
        "total_unique":    len(unique),
        "total_dups":      len(dups),
        "listings":        unique,
        "duplicates":      dups,
    }

# ─── DIFF & SAVE ────────────────────────────────────────────────────────────
def load_latest_snapshot() -> Optional[dict]:
    """Učitaj poslednji snapshot iz data/ foldera."""
    snapshots = sorted(DATA_DIR.glob("snapshot_*.json"))
    if not snapshots:
        return None
    with open(snapshots[-1]) as f:
        return json.load(f)

def build_stats(snapshot: dict) -> dict:
    """Izgradi agregirane statistike iz snapshot-a."""
    listings = snapshot.get("listings", [])
    by_str, by_zgrada = {}, {}

    for l in listings:
        # Po strukturi
        s = l.get("struktura") or "nepoznato"
        if s not in by_str:
            by_str[s] = {"label": STRUCTURE_MAP.get(s, s), "count": 0,
                         "cene": [], "cene_m2": [], "m2": [], "zgrade": set()}
        by_str[s]["count"] += 1
        if l.get("cena"):
            by_str[s]["cene"].append(l["cena"])
        if l.get("cena_m2"):
            by_str[s]["cene_m2"].append(l["cena_m2"])
        if l.get("m2"):
            by_str[s]["m2"].append(l["m2"])
        by_str[s]["zgrade"].add(l.get("zgrada", ""))

        # Po zgradi
        z = l.get("zgrada") or "BW (ostalo)"
        if z not in by_zgrada:
            by_zgrada[z] = {"count": 0, "strukture": set(), "cene": [], "cene_m2": []}
        by_zgrada[z]["count"] += 1
        if l.get("struktura"):
            by_zgrada[z]["strukture"].add(l["struktura"])
        if l.get("cena"):
            by_zgrada[z]["cene"].append(l["cena"])
        if l.get("cena_m2"):
            by_zgrada[z]["cene_m2"].append(l["cena_m2"])

    # Serijalizuj setove → liste
    def agg(vals):
        return {"min": min(vals), "max": max(vals),
                "avg": round(sum(vals)/len(vals))} if vals else None

    stats_str = {}
    for s, v in by_str.items():
        stats_str[s] = {
            "label": v["label"], "count": v["count"],
            "cena": agg(v["cene"]), "cena_m2": agg(v["cene_m2"]),
            "m2": agg(v["m2"]), "zgrade": sorted(v["zgrade"]),
        }

    stats_zgrada = {}
    for z, v in by_zgrada.items():
        stats_zgrada[z] = {
            "count": v["count"],
            "strukture": sorted(v["strukture"]),
            "cena": agg(v["cene"]), "cena_m2": agg(v["cene_m2"]),
        }

    return {"po_strukturi": stats_str, "po_zgradi": stats_zgrada}

def save_results(snapshot: dict, prev_snapshot: Optional[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Diff
    diff = {}
    if prev_snapshot:
        diff = diff_listings(prev_snapshot.get("listings", []), snapshot["listings"])
        print(f"\nDiff vs prethodni snapshot:")
        print(f"  Novi oglasi:    {len(diff['new'])}")
        print(f"  Skinuti oglasi: {len(diff['removed'])}")
        print(f"  Neto promena:   {diff['count_change']:+d}")

    # Stats
    stats = build_stats(snapshot)

    # Kompletan snapshot fajl
    output = {**snapshot, "diff": diff, "stats": stats}
    snap_path = DATA_DIR / f"snapshot_{date_str}.json"
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSnapshot sačuvan: {snap_path}")

    # latest.json — dashboard uvek čita ovaj fajl
    latest_path = DATA_DIR / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"latest.json ažuriran")

    # history.json — samo agregati po danima (za trend graf)
    history_path = DATA_DIR / "history.json"
    history = []
    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    history.append({
        "date": date_str,
        "total_raw": snapshot["total_raw"],
        "total_unique": snapshot["total_unique"],
        "total_dups": snapshot["total_dups"],
        "diff_new": len(diff.get("new", [])),
        "diff_removed": len(diff.get("removed", [])),
        "by_struktura": {k: v["count"] for k, v in stats["po_strukturi"].items()},
        "avg_m2": round(sum(l["cena_m2"] for l in snapshot["listings"] if l.get("cena_m2")) / max(sum(1 for l in snapshot["listings"] if l.get("cena_m2")),1)),
    })
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"history.json ažuriran ({len(history)} dana)")

    return snap_path

# ─── MAIN ────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print(f"BnV Tracker — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"URL: {BASE_URL}")
    print("=" * 60)

    prev = load_latest_snapshot()
    if prev:
        print(f"Prethodni snapshot: {prev.get('scraped_at', 'nepoznato')} ({prev.get('total_unique', '?')} unique oglasa)\n")
    else:
        print("Nema prethodnog snapshota — ovo je inicijalni run.\n")

    snapshot = await scrape_all()
    save_results(snapshot, prev)

    print("\n✓ Završeno.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

# ─── IMPORT BUILDING DETECTION ───────────────────────────────────────────────
# (inject at runtime so scrape.py can find buildings.py in same dir)
import importlib.util, pathlib
_bmod = importlib.util.spec_from_file_location(
    "buildings", pathlib.Path(__file__).parent / "buildings.py"
)
_bpkg = importlib.util.module_from_spec(_bmod)
_bmod.loader.exec_module(_bpkg)
canonical_building_v2 = _bpkg.canonical_building

# Patch extract_listing to use v2 building detection
_original_extract = extract_listing
async def extract_listing(card, page):
    l = await _original_extract(card, page)
    if l:
        l["zgrada"] = canonical_building_v2(
            l.get("naslov",""),
            "",                      # description loaded separately in full-page scrape
            l.get("url",""),
            l.get("sprat")
        )
    return l
