#!/usr/bin/env python3
"""
BnV Tracker v4.19 — SCRAPER_API_KEY iz env varijable (kao NB), guard + exit kodovi
"""

import json, re, time, hashlib, sys, os
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")

URLS = {
    # NAPOMENA (09.07.2026): Sinoc je pokusano dodavanje ?sortiranje=1
    # da bi se hvatali svezi oglasi (npr. propušten oglas 5425646449478).
    # Ali izmena je oborila BnV Halo scraper — verovatno Cloudflare/HTML
    # razlika za sortirane URL-ove. Vraceno na osnovni URL.
    # ALTERNATIVA za buduce: probati sortiranje=novo, sortiranje=6, ili
    # drugi Halo parametri; ili povecati MAX_PAGES sa 50 na 80+.
    "prodaja": "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd-savski-venac-beograd-na-vodi",
    "renta":   "https://www.halooglasi.com/nekretnine/izdavanje-stanova/beograd-savski-venac-beograd-na-vodi",
}

DATA_DIR  = Path(__file__).parent.parent / "data"
MAX_PAGES = 50
PAGE_DELAY = 3

STRUCTURE_MAP = {
    "1.0":"Garsonjera/Studio","1.5":"Jednoiposoban",
    "2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban",
    "4.0":"Četvorosoban","4.5":"Četvoriposoban","5.0":"Petosoban+",
}

def scraper_get(url):
    params = {
        "api_key":      SCRAPER_API_KEY,
        "url":          url,
        "render":       "false",
        "premium":      "true",
        "keep_headers": "true",
    }
    try:
        r = requests.get("https://api.scraperapi.com", params=params, timeout=120)
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
        if 300 < val < 50_000:
            return val
    else:
        if 150_000 < val < 5_000_000:
            return val
    return None

def sanitize_m2(m2, cena=None, mode="prodaja"):
    """Ispravlja decimalni previd u kvadraturi.
    Neki Halo card template-i (npr. Premium/Novogradnja) renderuju decimalni
    deo kvadrature kao poseban element, pa get_text spoji cifre i izgubi zarez
    (npr. "36,68" -> "3.668" ili "3668"). Ovo daje besmislen €/m².
    Rešenje: ako kvadratura daje nerealan €/m² (ili je van opsega 8–600 m²),
    skalira je (×10, ×100, ÷10...) dok ne dobije realnu vrednost.
    BnV stanovi realno: ~8–600 m², prodajni €/m²: ~1.200–25.000.
    """
    if m2 is None:
        return None
    in_range = lambda x: 8 <= x <= 600
    ok_pm2   = lambda x: bool(x) and cena is not None and 1200 <= cena / x <= 25000

    if mode == "prodaja" and cena:
        if in_range(m2) and ok_pm2(m2):
            return m2
        for f in (10, 100, 0.1, 0.01, 1000, 0.001):
            c = m2 * f
            if in_range(c) and ok_pm2(c):
                return round(c, 2)
        return m2

    # renta ili prodaja bez cene: samo opseg realne površine
    if in_range(m2):
        return m2
    for f in (10, 100, 0.1, 0.01):
        c = m2 * f
        if in_range(c):
            return round(c, 2)
    return m2

def listing_hash(zgrada, struktura, m2):
    key = f"{zgrada}|{struktura}|{round((m2 or 0)/3)}"
    return hashlib.md5(key.encode()).hexdigest()[:10]

def extract_agencija(card):
    """Izvuci slug agencije iz href linka oko loga na kartici.
    Npr. /oglasi/EUROPOLISNEKRETNINE -> europolisnekretnine
    """
    # Traži link ka profilu agencije: href="/oglasi/NAZIV"
    for a in card.find_all("a", href=re.compile(r"/oglasi/", re.I)):
        href = a.get("href", "")
        m = re.search(r"/oglasi/([^/?#]+)", href, re.I)
        if m:
            slug = m.group(1).strip()
            if 2 < len(slug) < 80:
                return slug
    return None

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
        from buildings import canonical_building, is_blacklisted
        has_bld = True
    except:
        has_bld = False

    listings = []
    for card in cards:
        try:
            card_classes = card.get("class", [])
            if "banner-list" in card_classes or "banner" in " ".join(card_classes):
                continue

            data_id = card.get("data-id") or ""

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

            cena_m2 = None
            if mode == "prodaja":
                m2price_el  = card.find(class_=re.compile("price-by-surface"))
                cena_m2_raw = m2price_el.get_text(strip=True) if m2price_el else ""
                if "€" in cena_m2_raw:
                    cena_m2 = parse_price(re.sub(r"[^\d]","",cena_m2_raw.split("€")[0]))

            m2_val = sobe_val = sprat_val = None

            features = card.find("ul", class_=re.compile("product-features"))
            if features:
                for li in features.find_all("li"):
                    legend    = li.find("span", class_="legend")
                    value_div = li.find(class_="value-wrapper")
                    if not legend or not value_div: continue
                    field    = legend.get_text(strip=True).lower()
                    full_txt = value_div.get_text(strip=True)
                    leg_txt  = legend.get_text(strip=True)
                    val_txt  = full_txt.replace(leg_txt, "").strip() or full_txt
                    if "broj soba" in field or "sobe" in field:
                        mm = re.search(r"([\d]+[,\.]?[\d]*)", val_txt)
                        if mm:
                            try: sobe_val = float(mm.group(1).replace(",","."))
                            except: pass
                    elif "kvadratura" in field or "površina" in field:
                        mm = re.search(r"([\d]+[,\.]?[\d]*)", val_txt)
                        if mm:
                            try: m2_val = float(mm.group(1).replace(",","."))
                            except: pass
                    elif "spratnost" in field or "sprat" in field:
                        sp = re.sub(r"[^\d/IVXLCM]","",val_txt)
                        if sp: sprat_val = sp[:8]

            if not m2_val:
                mm = re.search(r"([\d,\.]+)\s*m[²2]", title, re.I)
                if mm:
                    try: m2_val = float(mm.group(1).replace(",","."))
                    except: pass

            # Ispravka decimalnog previda u kvadraturi (npr. "36,68" -> 3.668/3668)
            m2_val = sanitize_m2(m2_val, cena, mode)

            street_text = ""
            subtitle = card.find(class_=re.compile("subtitle-places"))
            if subtitle:
                street_text = " ".join(li.get_text(strip=True) for li in subtitle.find_all("li"))

            desc_el      = card.find(class_=re.compile("product-description|desc|opis"))
            desc_text    = desc_el.get_text(strip=True)[:300] if desc_el else ""
            full_context = f"{title} {street_text} {desc_text}"

            if not sobe_val:
                slug_map = {"garsonjera":0.5,"jednosoban":1.0,"jednoiposoban":1.5,
                            "dvosoban":2.0,"dvoiposoban":2.5,"trosoban":3.0,
                            "troiposoban":3.5,"cetvorosoban":4.0,"petosoban":5.0}
                for slug, val in slug_map.items():
                    if slug in href.lower(): sobe_val = val; break

            # Spoji garsonjeru (0.5) u istu kategoriju kao jednosoban (1.0)
            if sobe_val == 0.5:
                sobe_val = 1.0

            # Preskoči oglase koji ne pripadaju BW kompleksu
            if has_bld and is_blacklisted(title, full_context, street_text):
                continue

            zgrada = canonical_building(title, full_context, street_text, sprat_val) if has_bld else "BW (neidentifikovano)"
            # cena_m2 za OBA moda: kod rente je to EUR/m2 mesecno,
            # standardna metrika za poredjenje zgrada (v4.19 fix)
            if cena and m2_val and not cena_m2:
                cena_m2 = round(cena / m2_val)

            # Izvuci agenciju
            agencija = extract_agencija(card)

            str_key = str(sobe_val) if sobe_val is not None else None
            listings.append({
                "id":        data_id or href.split("/")[-1].split("?")[0],
                "url":       url_full,
                "naslov":    title[:120],
                "zgrada":    zgrada,
                "agencija":  agencija,
                "struktura": str_key,
                "str_label": STRUCTURE_MAP.get(str_key,"nepoznato") if str_key else "nepoznato",
                "m2":        m2_val,
                "cena":      cena,
                "cena_m2":   cena_m2,
                "sprat":     sprat_val,
                "mode":      mode,
                "scraped_at":datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"  ⚠ Greška kartice: {e}", file=sys.stderr)

    return listings, total

def scrape_mode(mode):
    base_url = URLS[mode]
    print(f"\n{'='*55}")
    print(f"Scrapujem: {mode.upper()} — {base_url}")
    print(f"{'='*55}")

    all_listings = []

    print("Učitavam stranicu 1...")
    html1 = scraper_get(base_url)
    lp, total_raw = parse_page(html1, 1, mode)
    all_listings.extend(lp)

    if not lp:
        print(f"⚠ Stranica 1 nema oglasa!", file=sys.stderr)
        return [], 0

    print(f"Planiranih stranica: {MAX_PAGES}")

    empty_streak = 0
    for p in range(2, MAX_PAGES + 1):
        time.sleep(PAGE_DELAY)
        print(f"Učitavam stranicu {p}...")
        html = scraper_get(f"{base_url}?page={p}")
        lp, _ = parse_page(html, p, mode)
        if not lp:
            empty_streak += 1
            if empty_streak >= 3:
                print(f"  → {empty_streak} uzastopne prazne stranice, zaustavljam.")
                break
            print(f"  → Prazna str. {p}, pokušavam sledeću ({empty_streak}/3)...")
            continue
        empty_streak = 0
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
    prev_keys = {l.get("dedup_key") or l["id"] for l in prev}
    curr_keys  = {l.get("dedup_key") or l["id"] for l in curr}
    curr_map   = {(l.get("dedup_key") or l["id"]): l for l in curr}
    prev_map   = {(l.get("dedup_key") or l["id"]): l for l in prev}
    return {
        "new":          [curr_map[k] for k in curr_keys - prev_keys],
        "removed":      [prev_map[k] for k in prev_keys - curr_keys],
        "count_change": len(curr) - len(prev),
    }

def load_eod_snapshot(mode, date_str):
    path = DATA_DIR / f"eod_{mode}.json"
    if path.exists():
        data = json.load(open(path, encoding="utf-8"))
        if data.get("date") != date_str:
            return data
    latest_path = DATA_DIR / f"latest_{mode}.json"
    if latest_path.exists():
        data = json.load(open(latest_path, encoding="utf-8"))
        if data.get("scraped_at","")[:10] == date_str:
            yesterday = sorted(DATA_DIR.glob(f"snapshot_{mode}_*.json"))
            yesterday = [f for f in yesterday if f.stem.split("_")[-1] < date_str]
            if yesterday:
                return json.load(open(yesterday[-1], encoding="utf-8"))
        return data
    return None

def save_snapshot(mode, all_listings, total_raw):
    unique, dups = dedup(all_listings)
    print(f"\n{mode.upper()} — Unique: {len(unique)}, Duplikati: {len(dups)}")

    stats    = build_stats(unique)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prev          = load_eod_snapshot(mode, date_str)
    prev_listings = prev.get("listings", []) if prev else []
    diff          = diff_listings(prev_listings, unique)

    m2v    = [l["cena_m2"] for l in unique if l.get("cena_m2")]
    avg_m2 = round(sum(m2v)/len(m2v)) if m2v else None

    snapshot = {
        "mode":         mode,
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
        "date":         date_str,
        "total_raw":    len(all_listings),
        "total_unique": len(unique),
        "total_dups":   len(dups),
        "avg_m2":       avg_m2,
        "listings":     unique,
        "duplicates":   dups,
        "diff":         diff,
        "stats":        stats,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / f"latest_{mode}.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)
    with open(DATA_DIR / f"snapshot_{mode}_{date_str}.json","w",encoding="utf-8") as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2)
    if mode == "prodaja":
        with open(DATA_DIR / "latest.json","w",encoding="utf-8") as f:
            json.dump(snapshot,f,ensure_ascii=False,indent=2)

    eod_path = DATA_DIR / f"eod_{mode}.json"
    if not eod_path.exists() or json.load(open(eod_path,encoding="utf-8")).get("date") != date_str:
        if not eod_path.exists():
            with open(eod_path,"w",encoding="utf-8") as f:
                json.dump(snapshot,f,ensure_ascii=False,indent=2)
    with open(eod_path,"w",encoding="utf-8") as f:
        json.dump({**snapshot, "date": date_str},f,ensure_ascii=False,indent=2)

    hist_path        = DATA_DIR / f"history_{mode}.json"
    shared_hist_path = DATA_DIR / "history.json"

    history = json.load(open(hist_path,encoding="utf-8")) if hist_path.exists() else []

    entry = {
        "date":         date_str,
        "mode":         mode,
        "total_raw":    snapshot["total_raw"],
        "total_unique": len(unique),
        "total_dups":   len(dups),
        "avg_m2":       avg_m2,
        "diff_new":     len(diff["new"]),
        "diff_removed": len(diff["removed"]),
        "by_struktura": {k:v["count"] for k,v in stats["po_strukturi"].items()},
    }

    idx = next((i for i, h in enumerate(history)
                if h.get("date") == date_str and h.get("mode") == mode), None)
    if idx is not None:
        history[idx] = entry
    else:
        history.append(entry)

    with open(hist_path,"w",encoding="utf-8") as f:
        json.dump(history,f,ensure_ascii=False,indent=2)
    if mode == "prodaja":
        with open(shared_hist_path,"w",encoding="utf-8") as f:
            json.dump(history,f,ensure_ascii=False,indent=2)

    print(f"✓ Sačuvano latest_{mode}.json. Novi: {len(diff['new'])}, Skinuti: {len(diff['removed'])}")
    return snapshot

def main():
    print("="*55)
    print(f"BnV Scraper v4.19 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Prodaja + Izdavanje")
    print("="*55)

    # ── Zaštita: ključ mora postojati (env varijabla, kao NB) ──
    # Živi u scraperu (ne u bat-u) da važi za SVAKI način pokretanja.
    if not SCRAPER_API_KEY:
        print("ERROR: SCRAPER_API_KEY nije postavljen (env varijabla).", file=sys.stderr)
        sys.exit(1)

    listings_p, total_p = scrape_mode("prodaja")
    if listings_p:
        save_snapshot("prodaja", listings_p, total_p)

    print("\nPauza 10s pre izdavanja...")
    time.sleep(10)

    listings_r, total_r = scrape_mode("renta")
    if listings_r:
        save_snapshot("renta", listings_r, total_r)

    # ── Exit kod: ako bilo koji mod nije doneo oglase, javi bat-u grešku ──
    if not listings_p or not listings_r:
        print("⚠ Scrape nepotpun (prodaja i/ili renta bez oglasa) — exit 2.", file=sys.stderr)
        sys.exit(2)

    print("\n✓ Sve završeno.")

if __name__ == "__main__":
    main()
