"""
enrich_zgrade.py
Popunjava nazive zgrada u NRS JSON fajlovima čitajući OPIS oglasa.
Naziv zgrade se nalazi u meta-description tagu (statički HTML) — ne treba Playwright.

Pokretanje:
    pip install requests
    python scraper/enrich_zgrade.py

Obrađuje data/latest_nrs_prodaja.json i data/latest_nrs_renta.json,
fetchuje opis za listinge koji su "Neidentifikovano", detektuje zgradu,
i prepisuje fajlove + osvežava stats.po_zgradi.
"""
import json
import re
import time
from pathlib import Path

import requests

DATA = Path("data")
FILES = ["latest_nrs_prodaja.json", "latest_nrs_renta.json"]

ZGRADA_KEYWORDS = {
    "BW Residences":["bw residences","bw residence"],"BW Quartet":["bw quartet","quartet"],
    "BW Aria":["bw aria","aria"],"BW Perla":["bw perla","perla"],"BW Kula":["bw kula"],
    "BW Victoria":["bw victoria","victoria"],"BW Simfonija":["bw simfonija","simfonija"],
    "BW Iris":["bw iris"],"BW Magnolia":["bw magnolia","magnolia"],
    "BW Aqua":["bw aqua","aqua"],"BW Diva":["bw diva"],"BW Iskra":["bw iskra","iskra"],
    "BW Lumia":["bw lumia","lumia"],"BW Vista":["bw vista"],
    "BW Riviera":["bw riviera","riviera"],"BW Metropolitan":["bw metropolitan","metropolitan"],
    "BW King's Park":["king's park","kings park","king`s park"],"BW Queens":["bw queens"],
    "BW Eterna":["bw eterna","eterna"],"BW Sole":["bw sole"],"BW Libera":["bw libera","libera"],
    "BW Sensa":["bw sensa","sensa"],"BW Parkview":["bw parkview","parkview"],
    "BW Apollo":["bw apollo"],"BW Terraces":["bw terraces","terraces"],
    "Bristol Residences":["bristol residences","bristol"],
    "AFI Skyline":["afi skyline","skyline residence"],
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
}

def detect_zgrada(tekst: str) -> str:
    t = (tekst or "").lower()
    for zgrada, kws in ZGRADA_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return zgrada
    return "Neidentifikovano"

def fetch_opis(url: str) -> str:
    """Vraća meta-description (sadrži naziv zgrade) iz statičkog HTML-a."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        m = re.search(r'<meta name="description" content="([^"]*)"', r.text)
        if m:
            return m.group(1)
    except Exception as e:
        print(f"    ⚠ {e}")
    return ""

def rebuild_stats(listings):
    po = {}
    for l in listings:
        z = l.get("zgrada") or "Neidentifikovano"
        po.setdefault(z, {"count": 0, "cene": [], "cene_m2": []})
        po[z]["count"] += 1
        if l.get("cena"):    po[z]["cene"].append(l["cena"])
        if l.get("cena_m2"): po[z]["cene_m2"].append(l["cena_m2"])
    out = {}
    for z, v in po.items():
        c, m = v["cene"], v["cene_m2"]
        out[z] = {"count": v["count"],
                  "avg_cena": round(sum(c)/len(c)) if c else None,
                  "avg_m2":   round(sum(m)/len(m)) if m else None}
    return out

def process(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    listings = data.get("listings", [])
    todo = [l for l in listings if l.get("zgrada", "Neidentifikovano") == "Neidentifikovano"]
    print(f"\n{path.name}: {len(todo)} oglasa za proveru opisa")

    found = 0
    for i, l in enumerate(todo, 1):
        # prvo probaj iz naslova (možda već ima)
        z = detect_zgrada(l.get("naslov", ""))
        if z == "Neidentifikovano":
            opis = fetch_opis(l["url"])
            if opis:
                l["opis"] = opis
                z = detect_zgrada(opis)
            time.sleep(0.4)  # ljubazno prema serveru
        if z != "Neidentifikovano":
            l["zgrada"] = z
            found += 1
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} ... pronađeno {found}")

    data["stats"] = data.get("stats", {})
    data["stats"]["po_zgradi"] = rebuild_stats(listings)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {path.name}: novih {found} zgrada identifikovano")

if __name__ == "__main__":
    for f in FILES:
        p = DATA / f
        if p.exists():
            process(p)
        else:
            print(f"  ⚠ Nema fajla: {p}")
    print("\nGotovo. Sada: git add data/latest_nrs_*.json && git commit && git push")
