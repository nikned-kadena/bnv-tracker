"""
scrape_nrs_playwright.py  v3
Lokalni Playwright scraper za nekretnine.rs — Belgrade Waterfront (prodaja + renta)
Pokretanje: python scrape_nrs_playwright.py
Zahteva: pip install playwright && python -m playwright install chromium
"""

import asyncio
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── Konfiguracija ──────────────────────────────────────────────────────────────

BASE_URL = "https://www.nekretnine.rs"

TARGETS = {
    "prodaja": {
        "url": f"{BASE_URL}/prodaja-stanova/beograd/beograd-na-vodi-palata-pravde/",
        "out": Path("data/latest_nrs_prodaja.json"),
    },
    "renta": {
        "url": f"{BASE_URL}/izdavanje-stanova/beograd/beograd-na-vodi-palata-pravde/",
        "out": Path("data/latest_nrs_renta.json"),
    },
}

# Oglasi koji sadrže ove ključne reči u naslovu se isključuju
EXCLUSION_KEYWORDS = [
    "kneza milosa",
    "kneza miloša",
    "ulica kneza",
    "sarajevska",
    "durmitorska",
    "risanska",
    "višegradska",
    "visegradska",
    "miloša poćerca",
    "milosa pocerca",
    "vojvode milanka",
    "bulevar kralja aleksandra",
    "hajduk-veljkov venac",
    "hajduk veljkov venac",
]

MAX_PAGES   = 20
PAGE_WAIT   = 3000
DETAIL_WAIT = 2000
HEADLESS    = True
GIT_PUSH    = True

# ── Helpers ────────────────────────────────────────────────────────────────────

def clean_price(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None

def slug_to_id(url: str) -> str:
    parts = url.rstrip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return part
    return parts[-1]

def should_exclude(naslov: str) -> bool:
    """Vraća True ako oglas treba isključiti na osnovu naslova."""
    naslov_l = naslov.lower()
    return any(kw in naslov_l for kw in EXCLUSION_KEYWORDS)

# ── Detail fetch ───────────────────────────────────────────────────────────────

async def fetch_detail(page, url: str) -> dict:
    data = {}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(DETAIL_WAIT)

        # Agencija URL — /agencije-za-nekretnine/ID/ (mora imati numericki ID)
        import re as _re
        # Trazimo sve linkove ka agencijama, ali samo one sa ID-em (broj na kraju)
        ag_links = page.locator("a[href*='/agencije-za-nekretnine/']")
        ag_count = await ag_links.count()
        for ag_idx in range(ag_count):
            ag_link = ag_links.nth(ag_idx)
            href = await ag_link.get_attribute("href") or ""
            # Mora imati numericki ID: /agencije-za-nekretnine/717/
            if not _re.search(r"/agencije-za-nekretnine/\d+", href):
                continue
            full_href = href if href.startswith("http") else BASE_URL + href
            data["agencija_url"] = full_href
            # Naziv iz img alt
            ag_img = ag_link.locator("img").first
            if await ag_img.count() > 0:
                alt = (await ag_img.get_attribute("alt") or "").strip()
                # Filtriraj genericke i netacne nazive
                INVALID = r"^(Foto\s*\d*|Foto\d+|mapa|logo|agencija|nekretnine\.rs|\d+)$"
                if alt and not _re.match(INVALID, alt, _re.IGNORECASE) and len(alt) > 4:
                    data["agencija"] = alt
            # Naziv iz teksta linka ako img nije dao rezultat
            if not data.get("agencija"):
                txt = (await ag_link.inner_text()).strip()
                INVALID_TXT = r"^(Agencija|Agencije|nekretnine\.rs)$"
                if txt and not _re.match(INVALID_TXT, txt, _re.IGNORECASE) and len(txt) > 4:
                    data["agencija"] = txt
            break  # Uzmi prvi validan link

        # Fallback selektori za agenciju
        if not data.get("agencija"):
            for sel in [
                ".agency-name",
                ".advertiser__name",
                "[class*='agency'] [class*='name']",
                "[class*='Agency'] [class*='name']",
                ".broker-name",
            ]:
                el = page.locator(sel).first
                if await el.count() > 0:
                    txt = (await el.inner_text()).strip()
                    INVALID_TXT = r"^(Agencija|Agencije|nekretnine\.rs)$"
                    if txt and not _re.match(INVALID_TXT, txt, _re.IGNORECASE) and len(txt) > 4:
                        data["agencija"] = txt
                        break

        # Kvadratura iz naslova H1
        title_el = page.locator("h1").first
        if await title_el.count() > 0:
            title_txt = await title_el.inner_text()
            m = re.search(r"([\d,\.]+)\s*m²", title_txt)
            if m:
                data["kvadratura"] = float(m.group(1).replace(",", "."))

        # Karakteristike
        rows = page.locator("table tr, .listing-features li, [class*='feature'] [class*='item']")
        count = await rows.count()
        for i in range(min(count, 30)):
            try:
                txt = (await rows.nth(i).inner_text()).lower()
                if ("sob" in txt or "room" in txt) and not data.get("sobe"):
                    m = re.search(r"([\d,]+)", txt.split(":")[-1])
                    if m:
                        data["sobe"] = m.group(1)
                if "sprat" in txt and not data.get("sprat"):
                    val = txt.split(":")[-1].strip()
                    data["sprat"] = val[:20]
            except Exception:
                pass

    except PlaywrightTimeout:
        print(f"      ⚠ Timeout: {url}")
    except Exception as e:
        print(f"      ⚠ Greška: {e}")

    return data

# ── List page scrape ───────────────────────────────────────────────────────────

async def scrape_listing_page(page, url: str, tip: str) -> list[dict]:
    listings = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(PAGE_WAIT)
    except PlaywrightTimeout:
        print(f"    ⚠ Timeout: {url}")
        return listings

    links = page.locator("a[href*='/oglasi/']")
    count = await links.count()
    print(f"    → Pronađeno {count} oglasnih linkova")

    seen_ids = set()

    for i in range(count):
        el = links.nth(i)
        try:
            href = await el.get_attribute("href") or ""
        except Exception:
            continue

        if not href or "/oglasi/" not in href:
            continue

        full_url = href if href.startswith("http") else BASE_URL + href
        oglas_id = slug_to_id(full_url)

        if oglas_id in seen_ids:
            continue
        seen_ids.add(oglas_id)

        item: dict = {
            "tip":        tip,
            "izvor":      "nekretnine.rs",
            "id":         oglas_id,
            "url":        full_url,
            "scraped_at": datetime.now().isoformat(timespec="seconds"),
        }

        # Naslov
        title = await el.get_attribute("title") or ""
        if not title:
            try:
                title = (await el.inner_text()).strip()
            except Exception:
                pass
        if title:
            item["naslov"] = title.strip()

        # Exclusion filter
        if item.get("naslov") and should_exclude(item["naslov"]):
            print(f"      ✗ Isključen: {item['naslov'][:60]}")
            continue

        # Cena i kvadratura iz parent kontejnera
        try:
            parent = el
            for _ in range(5):
                tag = await parent.evaluate("el => el.tagName.toLowerCase()")
                if tag in ("li", "article", "div"):
                    break
                parent = page.locator(f"xpath=//a[@href='{href}']/..").first

            parent_txt = await parent.inner_text()

            price_m = re.search(r"€\s*([\d\.\s]+)", parent_txt)
            if price_m:
                item["cena_raw"] = "€ " + price_m.group(1).strip()
                item["cena"] = clean_price(price_m.group(1))

            area_m = re.search(r"([\d,\.]+)\s*m²", parent_txt)
            if area_m:
                item["kvadratura"] = float(area_m.group(1).replace(",", "."))

            if item.get("cena") and item.get("kvadratura") and item["kvadratura"] > 0:
                item["cena_m2"] = round(item["cena"] / item["kvadratura"])

            # Agencija iz img alt — filtriraj genericke nazive
            import re as _re
            INVALID_ALT = r"^(Foto ?\d*|mapa|logo|agencija|agencije|nekretnine.rs|\d+)$"
            agency_img = page.locator(
                f"xpath=//a[@href='{href}']/ancestor::li//img[@alt and string-length(@alt) > 4]"
            ).first
            if await agency_img.count() > 0:
                alt = (await agency_img.get_attribute("alt") or "").strip()
                if alt and not _re.match(INVALID_ALT, alt, _re.IGNORECASE):
                    item["agencija"] = alt

        except Exception:
            pass

        listings.append(item)

    return listings

# ── Pagination ─────────────────────────────────────────────────────────────────

async def get_next_page_url(page, current_url: str, page_num: int) -> str | None:
    next_el = page.locator("a[rel='next']").first
    if await next_el.count() > 0:
        href = await next_el.get_attribute("href")
        if href:
            return href if href.startswith("http") else BASE_URL + href

    next_num = page_num + 1
    for sel in [
        f"a[href*='strana={next_num}']",
        f".pagination a:has-text('{next_num}')",
        f"[class*='pagination'] a:has-text('{next_num}')",
        f"[class*='Pagination'] a:has-text('{next_num}')",
    ]:
        el = page.locator(sel).first
        if await el.count() > 0:
            href = await el.get_attribute("href")
            if href:
                return href if href.startswith("http") else BASE_URL + href

    base = current_url.split("?")[0]
    return f"{base}?strana={next_num}"

# ── Main scrape loop ───────────────────────────────────────────────────────────

async def scrape_mode(browser, tip: str, config: dict) -> list[dict]:
    print(f"\nnekretnine.rs — {tip.upper()}")
    print("=" * 60)

    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="sr-RS",
    )
    page  = await context.new_page()
    dpage = await context.new_page()

    all_listings: list[dict] = []
    all_ids:      set[str]   = set()
    url      = config["url"]
    page_num = 1

    while url and page_num <= MAX_PAGES:
        print(f"\n  Stranica {page_num}: {url}")
        batch = await scrape_listing_page(page, url, tip)

        new_batch = [x for x in batch if x["id"] not in all_ids]
        if not new_batch:
            print("  → Nema novih oglasa, zaustavljam.")
            break

        for idx, item in enumerate(new_batch, 1):
            print(f"    [{idx}/{len(new_batch)}] {item.get('naslov', item['id'])[:60]}")
            detail = await fetch_detail(dpage, item["url"])
            item.update({k: v for k, v in detail.items() if k not in item})

        for item in new_batch:
            all_ids.add(item["id"])
        all_listings.extend(new_batch)

        print(f"  ✓ Ukupno do sada: {len(all_listings)}")

        next_url = await get_next_page_url(page, url, page_num)
        url      = next_url
        page_num += 1
        await asyncio.sleep(1.5)

    await context.close()
    print(f"\n  Ukupno {tip}: {len(all_listings)} oglasa")
    return all_listings

# ── Zapis + Git push ───────────────────────────────────────────────────────────

def build_output(listings: list[dict], path: Path) -> dict:
    """Wrappe listu listinga u format koji Dashboard ocekuje."""
    prev_listings = []
    if path.exists():
        try:
            prev_raw = json.loads(path.read_text(encoding="utf-8"))
            prev_listings = prev_raw.get("listings", []) if isinstance(prev_raw, dict) else prev_raw
        except Exception:
            pass

    prev_ids = {l["id"] for l in prev_listings if l.get("id")}
    curr_ids = {l["id"] for l in listings if l.get("id")}
    new_ids     = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids

    diff = {
        "new":     [l for l in listings      if l.get("id") in new_ids],
        "removed": [l for l in prev_listings if l.get("id") in removed_ids],
    }

    po_zgradi = {}
    for l in listings:
        zgrada = l.get("zgrada") or "Neidentifikovano"
        if zgrada not in po_zgradi:
            po_zgradi[zgrada] = {"count": 0, "cene": [], "cene_m2": []}
        po_zgradi[zgrada]["count"] += 1
        if l.get("cena"):    po_zgradi[zgrada]["cene"].append(l["cena"])
        if l.get("cena_m2"): po_zgradi[zgrada]["cene_m2"].append(l["cena_m2"])

    return {
        "scraped_at":   datetime.now().isoformat(timespec="seconds"),
        "total_raw":    len(listings),
        "total_unique": len(listings),
        "total_dups":   0,
        "listings":     listings,
        "diff":         diff,
        "duplicates":   [],
        "stats": {
            "po_zgradi": {
                k: {
                    "count":    v["count"],
                    "avg_cena": round(sum(v["cene"]) / len(v["cene"])) if v["cene"] else None,
                    "avg_m2":   round(sum(v["cene_m2"]) / len(v["cene_m2"])) if v["cene_m2"] else None,
                }
                for k, v in po_zgradi.items()
            }
        },
    }

def save_json(data: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = build_output(data, path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    n, r = len(output["diff"]["new"]), len(output["diff"]["removed"])
    print(f"  💾 Snimljeno: {path} ({len(data)} stavki, +{n} novih, -{r} skinutih)")

def git_push(changed_files: list[Path]) -> None:
    if not changed_files:
        return
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"NRS scrape {ts}: {', '.join(p.name for p in changed_files)}"
    for attempt in range(1, 4):
        try:
            # Stash bilo kakvih uncommitted promena
            subprocess.run(["git", "stash", "-u"], capture_output=True)
            # Povuci remote promene
            subprocess.run(["git", "pull", "--rebase", "-X", "ours", "origin", "main"], check=True)
            # Vrati stash
            subprocess.run(["git", "stash", "pop"], capture_output=True)
            # Dodaj i commituj
            subprocess.run(["git", "add"] + [str(p) for p in changed_files], check=True)
            result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
            if result.returncode == 0:
                print(f"\n✅ Nema promena za commit (vec pushano)")
                return
            subprocess.run(["git", "commit", "-m", msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print(f"\n✅ Git push uspešan (pokušaj {attempt}): {msg}")
            return
        except subprocess.CalledProcessError as e:
            print(f"\n⚠ Git push pokušaj {attempt}/3 neuspešan: {e}")
            if attempt < 3:
                import time; time.sleep(5)
    print("\n❌ Git push neuspešan posle 3 pokušaja — pushajte ručno.")

# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=HEADLESS)
        print(f"Browser pokrenut (headless={HEADLESS})")

        changed: list[Path] = []

        for tip, cfg in TARGETS.items():
            listings = await scrape_mode(browser, tip, cfg)
            if listings:
                save_json(listings, cfg["out"])
                changed.append(cfg["out"])

        await browser.close()

    if GIT_PUSH and changed:
        print("\nPokretam git push...")
        git_push(changed)

    print("\nGotovo.")

if __name__ == "__main__":
    asyncio.run(main())
