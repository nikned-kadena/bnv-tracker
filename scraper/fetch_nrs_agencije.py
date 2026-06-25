"""
fetch_nrs_agencije.py
Fetchuje ID agencija sa nekretnine.rs i snima mapping u data/nrs_agencije_mapping.json
Pokretanje: python scraper/fetch_nrs_agencije.py
Zahteva: pip install playwright && python -m playwright install chromium
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

DATA_DIR    = Path("data")
PRODAJA_JSON = DATA_DIR / "latest_nrs_prodaja.json"
RENTA_JSON   = DATA_DIR / "latest_nrs_renta.json"
OUT_FILE     = DATA_DIR / "nrs_agencije_mapping.json"

BASE_URL = "https://www.nekretnine.rs"
WAIT_MS  = 3000   # ms čekanja na JS render detail stranice

# ── Učitaj sve agencije iz JSON fajlova ───────────────────────────────────────

def load_agencies() -> dict[str, list[str]]:
    """Vraća {naziv_agencije: [oglas_url, ...]} — samo oglasi sa agencijom."""
    agencies: dict[str, list[str]] = {}
    for path in [PRODAJA_JSON, RENTA_JSON]:
        if not path.exists():
            print(f"  ⚠ Fajl ne postoji: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        listings = data.get("listings", []) if isinstance(data, dict) else data
        for l in listings:
            naziv = l.get("agencija", "").strip()
            url   = l.get("url", "")
            # Preskoči prazne i generičke nazive
            if not naziv or re.match(r"^(agencij[ae]|mapa|logo|\d+)$", naziv, re.IGNORECASE):
                continue
            if naziv not in agencies:
                agencies[naziv] = []
            if url and url not in agencies[naziv]:
                agencies[naziv].append(url)
    return agencies

# ── Fetchuj ID agencije sa detail stranice oglasa ─────────────────────────────

async def fetch_agency_id(page, oglas_urls: list[str], naziv: str) -> str | None:
    """Poseti oglas i traži link /agencije-za-nekretnine/ID/"""
    for url in oglas_urls[:3]:   # probaj max 3 oglasa
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(WAIT_MS)

            # Traži link sa numeričkim ID-em
            links = page.locator("a[href*='/agencije-za-nekretnine/']")
            count = await links.count()
            for i in range(count):
                href = await links.nth(i).get_attribute("href") or ""
                m = re.search(r"/agencije-za-nekretnine/(\d+)", href)
                if m:
                    return m.group(1)

        except PlaywrightTimeout:
            print(f"    ⚠ Timeout: {url}")
        except Exception as e:
            print(f"    ⚠ Greška: {e}")

    return None

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    # Učitaj postojeći mapping (da ne fetchujemo ponovo ono što već imamo)
    existing: dict[str, str] = {}
    if OUT_FILE.exists():
        existing = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        print(f"Postojeći mapping: {len(existing)} agencija")

    agencies = load_agencies()
    print(f"Pronađeno {len(agencies)} agencija u JSON fajlovima\n")

    # Filtriraj samo one koje nemamo
    to_fetch = {k: v for k, v in agencies.items() if k not in existing}
    print(f"Treba fetchovati: {len(to_fetch)} novih agencija\n")

    if not to_fetch:
        print("Sve agencije su već u mappingu. Gotovo.")
        return

    mapping = dict(existing)  # kopija

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        total = len(to_fetch)
        for idx, (naziv, urls) in enumerate(to_fetch.items(), 1):
            print(f"[{idx}/{total}] {naziv}")
            ag_id = await fetch_agency_id(page, urls, naziv)
            if ag_id:
                mapping[naziv] = ag_id
                print(f"  ✓ ID: {ag_id} → {BASE_URL}/agencije-za-nekretnine/{ag_id}/")
            else:
                print(f"  ✗ ID nije pronađen")
            await asyncio.sleep(0.5)

        await browser.close()

    # Snimi mapping
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    found = sum(1 for v in mapping.values() if v)
    print(f"\n✅ Snimljeno: {OUT_FILE} ({found}/{len(mapping)} agencija sa ID-em)")

if __name__ == "__main__":
    asyncio.run(main())
