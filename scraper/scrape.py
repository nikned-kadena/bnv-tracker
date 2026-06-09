#!/usr/bin/env python3
"""
BnV Tracker v3 — Selenium + Chrome scraper
Pokrece se lokalno sa pravim Chrome browserom.
"""

import json, re, time, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

BASE_URL  = "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd-savski-venac-beograd-na-vodi"
DATA_DIR  = Path(__file__).parent.parent / "data"
MAX_PAGES = 40

STRUCTURE_MAP = {
    "0.5":"Garsonjera/Studio","1.0":"Jednosoban","1.5":"Jednoiposoban",
    "2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban",
    "4.0":"Četvorosoban","4.5":"Četvoriposoban","5.0":"Petosoban+",
}

def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def parse_price(text):
    if not text: return None
    clean = re.sub(r"[^\d]", "", str(text))
    if clean and 5 <= len(clean) <= 10:
        val = int(clean)
        if 30_000 < val < 30_000_000:
            return val
    return None

def listing_hash(zgrada, struktura, m2):
    key = f"{zgrada}|{struktura}|{round((m2 or 0)/3)}"
    return hashlib.md5(key.encode()).hexdigest()[:10]

def scrape_page(driver, page_num):
    url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item, [class*='product-item']"))
        )
    except:
        print(f"  ⚠ Timeout na stranici {page_num}", file=sys.stderr)
        return [], 0

    time.sleep(1.5)
    soup = BeautifulSoup(driver.page_source, "lxml")

    # Ukupan broj
    total = 0
    m = re.search(r"(\d[\d\.]*)\s+rezultat", soup.get_text())
    if m:
        total = int(m.group(1).replace(".", ""))

    cards = soup.find_all("div", class_=re.compile(r"\bproduct-item\b"))
    print(f"  Stranica {page_num}: {len(cards)} oglasa (ukupno: {total})")

    listings = []
    for card in cards:
        try:
            data_id = card.get("data-id") or ""
            link    = card.find("a", href=re.compile("/nekretnine/prodaja-stanova/"))
            if not link: continue
            href     = link.get("href","")
            url_full = f"https://www.halooglasi.com{href}" if href.startswith("/") else href
            title    = link.get_text(strip=True) or card.find(["h3","h2"], text=True) or ""
            if hasattr(title, "get_text"):
                title = title.get_text(strip=True)

            price_el = card.find("span", {"data-value": True})
            cena     = parse_price(price_el["data-value"]) if price_el else None
            if not cena:
                cf = card.find(class_=re.compile("central-feature"))
                cena = parse_price(cf.get_text()) if cf else None

            m2price_el = card.find(class_=re.compile("price-by-surface"))
            cena_m2_raw = m2price_el.get_text(strip=True) if m2price_el else ""
            cena_m2 = None
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
                    sprat_val = re.sub(r"[^\d/IVXLCM]","",txt)[:8] or None

            if not m2_val:
                mm = re.search(r"([\d,\.]+)\s*m[²2]", str(title), re.I)
                if mm:
                    try: m2_val = float(mm.group(1).replace(",","."))
                    except: pass

            if not sobe_val:
                slug_map = {"garsonjera":0.5,"jednosoban":1.0,"jednoiposoban":1.5,
                           "dvosoban":2.0,"dvoiposoban":2.5,"trosoban":3.0,
                           "troiposoban":3.5,"cetvorosoban":4.0,"petosoban":5.0}
                for slug, val in slug_map.items():
                    if slug in href.lower():
                        sobe_val = val; break

            sys.path.insert(0, str(Path(__file__).parent))
            try:
                from buildings import canonical_building
                zgrada = canonical_building(str(title), "", url_full, sprat_val)
            except:
                zgrada = "BW (neidentifikovano)"

            if cena and m2_val and not cena_m2:
                cena_m2 = round(cena / m2_val)

            str_key = str(sobe_val) if sobe_val is not None else None
            listings.append({
                "id":        data_id or href.split("/")[-1].split("?")[0],
                "url":       url_full,
                "naslov":    str(title)[:120],
                "zgrada":    zgrada,
                "struktura": str_key,
                "str_label": STRUCTURE_MAP.get(str_key,"nepoznato") if str_key else "nepoznato",
                "m2":        m2_val,
                "cena":      cena,
                "cena_m2":   cena_m2,
                "sprat":     sprat_val,
                "scraped_at":datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"  ⚠ Greška kartice: {e}", file=sys.stderr)

    return listings, total

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
            by_str[s] = {"label":STRUCTURE_MAP.get(s,s),"count":0,"cene":[],"cene_m2":[],"m2":[],"zgrade":set()}
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

    def agg(vals):
        return {"min":min(vals),"max":max(vals),"avg":round(sum(vals)/len(vals))} if vals else None

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
        "new":     [curr_map[i] for i in curr_ids-prev_ids],
        "removed": [l for l in prev if l["id"] in prev_ids-curr_ids],
        "count_change": len(curr)-len(prev),
    }

def load_latest():
    snaps = sorted(DATA_DIR.glob("snapshot_*.json"))
    if not snaps: return None
    with open(snaps[-1], encoding="utf-8") as f: return json.load(f)

def main():
    print("="*55)
    print(f"BnV Scraper v3 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*55)

    driver = make_driver()
    all_listings, total_raw = [], 0

    try:
        listings1, total_raw = scrape_page(driver, 1)
        all_listings.extend(listings1)

        n_pages = min((total_raw // 20) + 2, MAX_PAGES) if total_raw > 0 else MAX_PAGES
        print(f"Ukupno oglasa: {total_raw}, stranica: {n_pages}")

        for p in range(2, n_pages + 1):
            time.sleep(2)
            lp, _ = scrape_page(driver, p)
            if not lp: break
            all_listings.extend(lp)
    finally:
        driver.quit()

    print(f"\nSirovi listinzi: {len(all_listings)}")
    unique, dups = dedup(all_listings)
    print(f"Unique: {len(unique)}, Duplikati: {len(dups)}")

    stats   = build_stats(unique)
    prev    = load_latest()
    diff    = diff_listings(prev.get("listings",[]) if prev else [], unique)
    m2_vals = [l["cena_m2"] for l in unique if l.get("cena_m2")]
    avg_m2  = round(sum(m2_vals)/len(m2_vals)) if m2_vals else None

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
    with open(DATA_DIR/f"snapshot_{date_str}.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)
    with open(DATA_DIR/"latest.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)

    hist_path = DATA_DIR/"history.json"
    history   = json.load(open(hist_path,encoding="utf-8")) if hist_path.exists() else []
    history.append({
        "date":         date_str,
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

    print(f"\n✓ Sačuvano. Novi: {len(diff['new'])}, Skinuti: {len(diff['removed'])}")

if __name__ == "__main__":
    main()
