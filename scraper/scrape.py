#!/usr/bin/env python3
"""
BnV Tracker v2 — requests + BeautifulSoup scraper
Bez Playwright, radi na GitHub Actions bez problema.
"""

import json, re, time, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL  = "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd-savski-venac-beograd-na-vodi"
DATA_DIR  = Path(__file__).parent.parent / "data"
MAX_PAGES = 40
PAGE_SIZE = 20   # oglasa po stranici

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sr-RS,sr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.halooglasi.com/",
}

STRUCTURE_MAP = {
    "0.5":"Garsonjera/Studio","1.0":"Jednosoban","1.5":"Jednoiposoban",
    "2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban",
    "4.0":"Četvorosoban","4.5":"Četvoriposoban","5.0":"Petosoban+",
}

def parse_price(text):
    if not text: return None
    clean = re.sub(r"[^\d]", "", str(text))
    if clean and 5 <= len(clean) <= 10:
        val = int(clean)
        if 30_000 < val < 30_000_000:
            return val
    return None

def parse_m2(text):
    if not text: return None
    m = re.search(r"([\d\.,]+)\s*m", str(text), re.I)
    if m:
        try: return float(m.group(1).replace(",","."))
        except: pass
    return None

def parse_rooms(text):
    if not text: return None
    m = re.search(r"([\d\.,]+)", str(text))
    if m:
        try: return float(m.group(1).replace(",","."))
        except: pass
    return None

def listing_hash(zgrada, struktura, m2):
    key = f"{zgrada}|{struktura}|{round((m2 or 0)/3)}"
    return hashlib.md5(key.encode()).hexdigest()[:10]

def scrape_page(page_num, session):
    url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠ Greška stranica {page_num}: {e}", file=sys.stderr)
        return [], 0

    soup = BeautifulSoup(r.text, "html.parser")

    # Ukupan broj oglasa
    total = 0
    count_el = soup.find(class_=re.compile("total-count|results-count|broj-oglasa"))
    if not count_el:
        count_el = soup.find("span", string=re.compile(r"\d+\s+rezultat"))
    if not count_el:
        # Traži "562 rezultata" pattern
        m = re.search(r"(\d+)\s+rezultat", r.text)
        if m: total = int(m.group(1))
    else:
        m = re.search(r"(\d[\d\.]*)", count_el.get_text())
        if m: total = int(m.group(1).replace(".", ""))

    cards = soup.find_all("div", class_=re.compile(r"\bproduct-item\b"))
    print(f"  Stranica {page_num}: {len(cards)} oglasa")

    listings = []
    for card in cards:
        try:
            # ID
            data_id = card.get("data-id") or card.get("data-ad-id") or ""
            
            # URL i naslov
            link = card.find("a", href=re.compile("/nekretnine/prodaja-stanova/"))
            href = link["href"] if link else ""
            url_full = f"https://www.halooglasi.com{href}" if href.startswith("/") else href
            title = link.get_text(strip=True) if link else ""
            if not title:
                h3 = card.find(["h3","h2"])
                title = h3.get_text(strip=True) if h3 else ""

            # Cena
            price_el = card.find("span", {"data-value": True})
            cena = parse_price(price_el["data-value"]) if price_el else None
            if not cena:
                price_div = card.find(class_=re.compile("central-feature"))
                cena = parse_price(price_div.get_text()) if price_div else None

            # Cena/m2
            m2price_el = card.find(class_=re.compile("price-by-surface"))
            cena_m2_raw = m2price_el.get_text(strip=True) if m2price_el else ""
            cena_m2 = parse_price(re.sub(r"[^\d]","",cena_m2_raw.split("€")[0])) if "€" in cena_m2_raw else None

            # Atributi (m2, sobe, sprat)
            m2_val = sobe_val = sprat_val = None
            attrs = card.find_all(class_=re.compile("feature-value|characteristic|oglasene-osobine|product-feature"))
            for attr in attrs:
                txt = attr.get_text(strip=True)
                if "m2" in txt.lower() or "m²" in txt:
                    m2_val = parse_m2(txt)
                elif re.search(r"\b(soba|soban|studio|garsonjera)\b", txt, re.I):
                    sobe_val = parse_rooms(txt)
                elif "sprat" in txt.lower():
                    sprat_val = re.sub(r"[^\d/IVXLCM]","",txt)[:8] or None

            # Fallback m2 iz naslova
            if not m2_val:
                m = re.search(r"([\d,\.]+)\s*m[²2]", title, re.I)
                if m:
                    try: m2_val = float(m.group(1).replace(",","."))
                    except: pass

            # Fallback sobe iz URL-a
            if not sobe_val:
                slug_map = {"garsonjera":0.5,"jednosoban":1.0,"jednoiposoban":1.5,
                           "dvosoban":2.0,"dvoiposoban":2.5,"trosoban":3.0,
                           "troiposoban":3.5,"cetvorosoban":4.0,"petosoban":5.0}
                for slug, val in slug_map.items():
                    if slug in href.lower():
                        sobe_val = val
                        break

            # Zgrada iz naslova
            from buildings import canonical_building
            zgrada = canonical_building(title, "", url_full, sprat_val)

            # Cena/m2 izračun ako nije parsiran
            if cena and m2_val and not cena_m2:
                cena_m2 = round(cena / m2_val)

            str_key = str(sobe_val) if sobe_val is not None else None

            listings.append({
                "id": data_id or href.split("/")[-1].split("?")[0],
                "url": url_full,
                "naslov": title[:120],
                "zgrada": zgrada,
                "struktura": str_key,
                "str_label": STRUCTURE_MAP.get(str_key, "nepoznato") if str_key else "nepoznato",
                "m2": m2_val,
                "cena": cena,
                "cena_m2": cena_m2,
                "sprat": sprat_val,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"  ⚠ Greška parsiranja kartice: {e}", file=sys.stderr)

    return listings, total

def dedup(listings):
    seen, unique, dups = {}, [], []
    for l in listings:
        h = listing_hash(l["zgrada"], l["struktura"], l["m2"])
        if h not in seen:
            seen[h] = l["id"]
            l["dedup_key"] = h
            unique.append(l)
        else:
            dups.append({"id": l["id"], "original_id": seen[h]})
    return unique, dups

def build_stats(listings):
    by_str, by_zgrada = {}, {}
    for l in listings:
        s = l.get("struktura") or "nepoznato"
        if s not in by_str:
            by_str[s] = {"label": STRUCTURE_MAP.get(s,s), "count":0,
                         "cene":[], "cene_m2":[], "m2":[], "zgrade":set()}
        by_str[s]["count"] += 1
        if l.get("cena"):    by_str[s]["cene"].append(l["cena"])
        if l.get("cena_m2"): by_str[s]["cene_m2"].append(l["cena_m2"])
        if l.get("m2"):      by_str[s]["m2"].append(l["m2"])
        by_str[s]["zgrade"].add(l.get("zgrada",""))

        z = l.get("zgrada") or "BW (ostalo)"
        if z not in by_zgrada:
            by_zgrada[z] = {"count":0,"strukture":set(),"cene":[],"cene_m2":[]}
        by_zgrada[z]["count"] += 1
        if l.get("struktura"): by_zgrada[z]["strukture"].add(l["struktura"])
        if l.get("cena"):      by_zgrada[z]["cene"].append(l["cena"])
        if l.get("cena_m2"):   by_zgrada[z]["cene_m2"].append(l["cena_m2"])

    def agg(vals):
        return {"min":min(vals),"max":max(vals),"avg":round(sum(vals)/len(vals))} if vals else None

    return {
        "po_strukturi": {s: {"label":v["label"],"count":v["count"],
            "cena":agg(v["cene"]),"cena_m2":agg(v["cene_m2"]),"m2":agg(v["m2"]),
            "zgrade":sorted(v["zgrade"])} for s,v in by_str.items()},
        "po_zgradi": {z: {"count":v["count"],"strukture":sorted(v["strukture"]),
            "cena":agg(v["cene"]),"cena_m2":agg(v["cene_m2"])} for z,v in by_zgrada.items()},
    }

def diff_listings(prev_listings, curr_listings):
    prev_ids = {l["id"] for l in prev_listings}
    curr_ids  = {l["id"] for l in curr_listings}
    curr_map  = {l["id"]: l for l in curr_listings}
    return {
        "new":     [curr_map[i] for i in curr_ids - prev_ids],
        "removed": [l for l in prev_listings if l["id"] in prev_ids - curr_ids],
        "count_change": len(curr_listings) - len(prev_listings),
    }

def load_latest():
    snaps = sorted(DATA_DIR.glob("snapshot_*.json"))
    if not snaps: return None
    with open(snaps[-1]) as f: return json.load(f)

def main():
    print("="*55)
    print(f"BnV Scraper v2 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*55)

    session = requests.Session()
    all_listings, total_raw = [], 0

    # Stranica 1
    listings1, total_raw = scrape_page(1, session)
    all_listings.extend(listings1)

    if total_raw > 0:
        n_pages = min((total_raw // PAGE_SIZE) + 2, MAX_PAGES)
    else:
        n_pages = MAX_PAGES
    print(f"Ukupno oglasa: {total_raw}, stranica: {n_pages}")

    for p in range(2, n_pages + 1):
        time.sleep(1.5)
        listings_p, _ = scrape_page(p, session)
        if not listings_p: break
        all_listings.extend(listings_p)

    print(f"\nSirovi listinzi: {len(all_listings)}")
    unique, dups = dedup(all_listings)
    print(f"Unique: {len(unique)}, Duplikati: {len(dups)}")

    stats   = build_stats(unique)
    prev    = load_latest()
    diff    = diff_listings(prev.get("listings",[]) if prev else [], unique)
    avg_m2_vals = [l["cena_m2"] for l in unique if l.get("cena_m2")]
    avg_m2  = round(sum(avg_m2_vals)/len(avg_m2_vals)) if avg_m2_vals else None

    snapshot = {
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
        "total_raw":    total_raw or len(all_listings),
        "total_unique": len(unique),
        "total_dups":   len(dups),
        "avg_m2":       avg_m2,
        "listings":     unique,
        "duplicates":   dups,
        "diff":         diff,
        "stats":        stats,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(DATA_DIR / f"snapshot_{date_str}.json","w",encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(DATA_DIR / "latest.json","w",encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # History
    hist_path = DATA_DIR / "history.json"
    history = json.load(open(hist_path)) if hist_path.exists() else []
    history.append({
        "date":           date_str,
        "total_raw":      snapshot["total_raw"],
        "total_unique":   len(unique),
        "total_dups":     len(dups),
        "avg_m2":         avg_m2,
        "diff_new":       len(diff["new"]),
        "diff_removed":   len(diff["removed"]),
        "by_struktura":   {k:v["count"] for k,v in stats["po_strukturi"].items()},
    })
    with open(hist_path,"w",encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Sačuvano. Novi: {len(diff['new'])}, Skinuti: {len(diff['removed'])}")

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
