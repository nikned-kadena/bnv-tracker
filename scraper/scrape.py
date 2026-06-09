#!/usr/bin/env python3
"""
BnV Tracker v4.8 — ScraperAPI, prodaja + izdavanje
"""

import json, re, time, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SCRAPER_API_KEY = "4dba199ae91807746affc7e94e446ce0"

URLS = {
    "prodaja": "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd-savski-venac-beograd-na-vodi",
    "renta":   "https://www.halooglasi.com/nekretnine/izdavanje-stanova/beograd-savski-venac-beograd-na-vodi",
}

DATA_DIR  = Path(__file__).parent.parent / "data"
MAX_PAGES = 50
PAGE_DELAY = 3

STRUCTURE_MAP = {
    "0.5":"Garsonjera/Studio","1.0":"Jednosoban","1.5":"Jednoiposoban",
    "2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban",
    "4.0":"Četvorosoban","4.5":"Četvoriposoban","5.0":"Petosoban+",
}

def scraper_get(url, render_js=True):
    params = {
        "api_key": SCRAPER_API_KEY,
        "url":     url,
        "render":  "true" if render_js else "false",
    }
    try:
        r = requests.get("https://api.scraperapi.com", params=params, timeout=60)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  ⚠ ScraperAPI greška za {url}: {e}", file=sys.stderr)
        return None

def parse_price(text, mode="prodaja"):
    if not text: return None
    clean = re.sub(r"[^\d]", "", str(text))
    if not clean: return None
    val = int(clean)
    if mode == "renta":
        if 200 < val < 50_000:   # EUR/mesec: 200-50.000
            return val
    else:
        if 10_000 < val < 30_000_000:  # Prodaja EUR
            return val
    return None

def listing_hash(zgrada, struktura, m2):
    key = f"{zgrada}|{struktura}|{round((m2 or 0)/3)}"
    return hashlib.md5(key.encode()).hexdigest()[:10]

def parse_page(html, page_num, mode="prodaja"):
    if not html:
        return [], 0

    soup  = BeautifulSoup(html, "lxml")
    cards = soup.find_all("div", class_=re.compile(r"\bproduct-item\b"))

    total = 0
    for pattern in [r"(\d[\d\.]*)\s+rezultat", r"(\d+)\s+stan"]:
        m = re.search(pattern, soup.get_text())
        if m:
            total = int(m.group(1).replace(".", ""))
            break

    print(f"  Stranica {page_num}: {len(cards)} oglasa" + (f" (ukupno: {total})" if total else ""))

    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from buildings import canonical_building
        has_bld = True
    except:
        has_bld = False

    listings = []
    for card in cards:
        try:
            data_id = card.get("data-id") or ""
            
            # Prodaja vs renta — različiti URL paterni
            if mode == "prodaja":
                link = card.find("a", href=re.compile("/nekretnine/prodaja-stanova/"))
            else:
                link = card.find("a", href=re.compile("/nekretnine/izdavanje-stanova/"))
            
            if not link:
                link = card.find("a", href=re.compile("/nekretnine/"))
            if not link: continue
            
            href     = link.get("href", "")
            url_full = f"https://www.halooglasi.com{href}" if href.startswith("/") else href
            title    = link.get_text(strip=True)
            if not title:
                h = card.find(["h3","h2"])
                title = h.get_text(strip=True) if h else ""

            price_el = card.find("span", {"data-value": True})
            cena     = parse_price(price_el["data-value"], mode) if price_el else None
            if not cena:
                cf = card.find(class_=re.compile("central-feature"))
                cena = parse_price(cf.get_text(), mode) if cf else None

            # Za rentu, cena_m2 nema smisla
            cena_m2 = None
            if mode == "prodaja":
                m2price_el  = card.find(class_=re.compile("price-by-surface"))
                cena_m2_raw = m2price_el.get_text(strip=True) if m2price_el else ""
                if "€" in cena_m2_raw:
                    cena_m2 = parse_price(re.sub(r"[^\d]","",cena_m2_raw.split("€")[0]))

            m2_val = sobe_val = sprat_val = None
            for attr in card.find_all(class_=re.compile("feature-value|oglasene-osobine|product-feature")):
                txt = attr.get_text(strip=True)
                if "m2" in txt.lower() or "m²" in txt:
                    mm = re.search(r"([\d,\.]+)\s*m", txt, re.I)
                    if mm:
                        try: m2_val = float(mm.group(1).replace(",","."))
                        except: pass
                elif re.search(r"\b(soba|soban|studio|garsonjera)\b", txt, re.I):
                    mm = re.search(r"([\d,\.]+)", txt)
                    if mm:
                        try: sobe_val = float(mm.group(1).replace(",","."))
                        except: pass
                elif "sprat" in txt.lower():
                    sp = re.sub(r"[^\d/IVXLCM]","",txt)
                    if sp: sprat_val = sp[:8]

            if not m2_val:
                mm = re.search(r"([\d,\.]+)\s*m[²2]", title, re.I)
                if mm:
                    try: m2_val = float(mm.group(1).replace(",","."))
                    except: pass

            # Izvuci ulicu iz subtitle-places za adresni lookup
            street_text = ""
            subtitle = card.find(class_=re.compile("subtitle-places"))
            if subtitle:
                street_text = " ".join(li.get_text(strip=True) for li in subtitle.find_all("li"))
            
            # Kratki opis iz kartice ako postoji
            desc_el = card.find(class_=re.compile("product-description|desc|opis"))
            desc_text = desc_el.get_text(strip=True)[:300] if desc_el else ""
            full_context = f"{title} {street_text} {desc_text}" 

            if not sobe_val:
                slug_map = {"garsonjera":0.5,"jednosoban":1.0,"jednoiposoban":1.5,
                           "dvosoban":2.0,"dvoiposoban":2.5,"trosoban":3.0,
                           "troiposoban":3.5,"cetvorosoban":4.0,"petosoban":5.0}
                for slug, val in slug_map.items():
                    if slug in href.lower(): sobe_val = val; break

            zgrada = canonical_building(title, full_context if "full_context" in dir() else "", street_text if "street_text" in dir() else "", sprat_val) if has_bld else "BW (neidentifikovano)"
            if mode == "prodaja" and cena and m2_val and not cena_m2:
                cena_m2 = round(cena / m2_val)

            str_key = str(sobe_val) if sobe_val is not None else None
            listings.append({
                "id":        data_id or href.split("/")[-1].split("?")[0],
                "url":       url_full,
                "naslov":    title[:120],
                "zgrada":    zgrada,
                "struktura": str_key,
                "str_label": STRUCTURE_MAP.get(str_key,"nepoznato") if str_key else "nepoznato",
                "m2":        m2_val,
                "cena":      cena,
                "cena_m2":   cena_m2 if mode == "prodaja" else None,
                "sprat":     sprat_val,
                "mode":      mode,
                "scraped_at":datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"  ⚠ Greška kartice: {e}", file=sys.stderr)

    return listings, total

def scrape_mode(mode):
    """Scrape-uj sve stranice za jedan mode (prodaja ili renta)."""
    base_url = URLS[mode]
    print(f"\n{'='*55}")
    print(f"Scrapujem: {mode.upper()} — {base_url}")
    print(f"{'='*55}")

    all_listings, total_raw = [], 0

    # Stranica 1 — sa JS renderingom
    print("Učitavam stranicu 1...")
    html1 = scraper_get(base_url, render_js=False)
    lp, total_raw = parse_page(html1, 1, mode)
    all_listings.extend(lp)

    if not lp:
        print(f"⚠ Stranica 1 nema oglasa!", file=sys.stderr)
        return [], 0

    n_pages = MAX_PAGES  # Uvek idi do MAX_PAGES, stani kad nema kartica
    print(f"Planiranih stranica: {n_pages}")

    for p in range(2, n_pages + 1):
        time.sleep(PAGE_DELAY)
        print(f"Učitavam stranicu {p}...")
        html = scraper_get(f"{base_url}?page={p}", render_js=False)
        lp, _ = parse_page(html, p, mode)
        if not lp:
            print(f"  → Prazna stranica {p}, zaustavljam.")
            break
        all_listings.extend(lp)

    return all_listings, total_raw

def dedup(listings):
    seen, unique, dups = {}, [], []
    for l in listings:
        h = listing_hash(l["zgrada"], l["struktura"], l["m2"])
        if h not in seen:
            seen[h] = l["id"]; l["dedup_key"] = h; unique.append(l)
        else:
            dups.append({"id":l["id"],"original_id":seen[h]})
    return unique, dups

def build_stats(listings):
    by_str, by_zgrada = {}, {}
    for l in listings:
        s = l.get("struktura") or "nepoznato"
        if s not in by_str:
            by_str[s] = {"label":STRUCTURE_MAP.get(s,s),"count":0,
                         "cene":[],"cene_m2":[],"m2":[],"zgrade":set()}
        by_str[s]["count"] += 1
        if l.get("cena"):    by_str[s]["cene"].append(l["cena"])
        if l.get("cena_m2"): by_str[s]["cene_m2"].append(l["cena_m2"])
        if l.get("m2"):      by_str[s]["m2"].append(l["m2"])
        by_str[s]["zgrade"].add(l.get("zgrada",""))
        z = l.get("zgrada") or "BW (ostalo)"
        if z not in by_zgrada:
            by_zgrada[z] = {"count":0,"strukture":set(),"cene":[],"cena_m2":[]}
        by_zgrada[z]["count"] += 1
        if l.get("struktura"): by_zgrada[z]["strukture"].add(l["struktura"])
        if l.get("cena"):      by_zgrada[z]["cene"].append(l["cena"])
        if l.get("cena_m2"):   by_zgrada[z]["cena_m2"].append(l["cena_m2"])

    def agg(v):
        return {"min":min(v),"max":max(v),"avg":round(sum(v)/len(v))} if v else None

    return {
        "po_strukturi":{s:{"label":v["label"],"count":v["count"],
            "cena":agg(v["cene"]),"cena_m2":agg(v["cene_m2"]),"m2":agg(v["m2"]),
            "zgrade":sorted(v["zgrade"])} for s,v in by_str.items()},
        "po_zgradi":{z:{"count":v["count"],"strukture":sorted(v["strukture"]),
            "cena":agg(v["cene"]),"cena_m2":agg(v["cena_m2"])} for z,v in by_zgrada.items()},
    }

def diff_listings(prev, curr):
    prev_ids = {l["id"] for l in prev}
    curr_ids  = {l["id"] for l in curr}
    curr_map  = {l["id"]:l for l in curr}
    return {
        "new":          [curr_map[i] for i in curr_ids-prev_ids],
        "removed":      [l for l in prev if l["id"] in prev_ids-curr_ids],
        "count_change": len(curr)-len(prev),
    }

def load_latest(mode):
    path = DATA_DIR / f"latest_{mode}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f: return json.load(f)
    # Fallback na stari latest.json za prodaju
    if mode == "prodaja":
        snaps = sorted(DATA_DIR.glob("snapshot_*.json"))
        if snaps:
            with open(snaps[-1], encoding="utf-8") as f: return json.load(f)
    return None

def save_snapshot(mode, all_listings, total_raw):
    unique, dups = dedup(all_listings)
    print(f"\n{mode.upper()} — Unique: {len(unique)}, Duplikati: {len(dups)}")

    stats   = build_stats(unique)
    prev    = load_latest(mode)
    diff    = diff_listings(prev.get("listings",[]) if prev else [], unique)
    m2v     = [l["cena_m2"] for l in unique if l.get("cena_m2")]
    avg_m2  = round(sum(m2v)/len(m2v)) if m2v else None

    snapshot = {
        "mode":         mode,
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
        "total_raw":    len(all_listings),  # Pravi broj scraped oglasa
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

    # Mode-specific latest
    with open(DATA_DIR / f"latest_{mode}.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)

    # Snapshot arhiv
    with open(DATA_DIR / f"snapshot_{mode}_{date_str}.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)

    # Backwards compat za prodaju
    if mode == "prodaja":
        with open(DATA_DIR / "latest.json","w",encoding="utf-8") as f:
            json.dump(snapshot,f,ensure_ascii=False,indent=2)

    # History
    hist_path = DATA_DIR / f"history_{mode}.json"
    # Merge u zajednički history.json za trend grafikon
    shared_hist_path = DATA_DIR / "history.json"

    history = json.load(open(hist_path,encoding="utf-8")) if hist_path.exists() else []
    history.append({
        "date":         date_str,
        "mode":         mode,
        "total_raw":    snapshot["total_raw"],
        "total_unique": len(unique),
        "total_dups":   len(dups),
        "avg_m2":       avg_m2,
        "diff_new":     len(diff["new"]),
        "diff_removed": len(diff["removed"]),
        "by_struktura": {k:v["count"] for k,v in stats["po_strukturi"].items()},
    })
    with open(hist_path,"w",encoding="utf-8") as f:
        json.dump(history,f,ensure_ascii=False,indent=2)

    # Shared history (prodaja only za glavni trend)
    if mode == "prodaja":
        with open(shared_hist_path,"w",encoding="utf-8") as f:
            json.dump(history,f,ensure_ascii=False,indent=2)

    print(f"✓ Sačuvano latest_{mode}.json. Novi: {len(diff['new'])}, Skinuti: {len(diff['removed'])}")
    return snapshot

def main():
    print("="*55)
    print(f"BnV Scraper v4.8 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Prodaja + Izdavanje")
    print("="*55)

    # Scrape prodaja
    listings_p, total_p = scrape_mode("prodaja")
    if listings_p:
        save_snapshot("prodaja", listings_p, total_p)

    # Pauza između dva moda
    print("\nPauza 10s pre izdavanja...")
    time.sleep(10)

    # Scrape renta/izdavanje
    listings_r, total_r = scrape_mode("renta")
    if listings_r:
        save_snapshot("renta", listings_r, total_r)

    print("\n✓ Sve završeno.")

if __name__ == "__main__":
    main()