"""
scrape_nrs_playwright.py — BnV Tracker scraper za nekretnine.rs (lokalni Chromium)
Verzija: 1.0

Alternativa za scrape_nrs.py koja NE koristi ScraperAPI, već lokalni
headless Chromium preko Playwright-a. Prednost: nema potrošnje API kredita,
prava JS paginacija (klik kroz stranice), potpuna kontrola nad render-om.

Scrape-uje listinge sa:
  Prodaja: https://www.nekretnine.rs/prodaja-stanova/beograd/beograd-na-vodi-palata-pravde/
  Renta:   https://www.nekretnine.rs/izdavanje-stanova/beograd/beograd-na-vodi-palata-pravde/

Output (isti format kao scrape_nrs.py — dashboard ostaje kompatibilan):
  data/latest_nrs_prodaja.json
  data/latest_nrs_renta.json
  data/history_nrs.json
  data/eod_nrs_YYYY-MM-DD.json

Pokretanje:
  pip install playwright beautifulsoup4
  python -m playwright install chromium
  python scraper/scrape_nrs_playwright.py

Opcionalno auto git push (default: OFF):
  BNV_GIT_PUSH=1 python scraper/scrape_nrs_playwright.py
  # push ide na trenutni branch; override-uj sa BNV_PUSH_BRANCH=<branch>

Zahteva: playwright, beautifulsoup4 (requests NIJE potreban)
"""

import re
import json
import time
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

# Ponovo koristimo SVE čiste (fetch-nezavisne) helpere iz scrape_nrs.py
# kako bi format izlaza i logika identifikacije zgrada ostali identični.
sys.path.insert(0, str(Path(__file__).parent))
from scrape_nrs import (  # noqa: E402
    identify_building,
    parse_struktura,
    parse_cena,
    parse_m2,
    make_dedup_key,
    parse_listing_page,
    compute_stats,
    compute_diff,
    save_json,
    load_json,
    SITE_BASE,
    BASE_PRODAJA,
    BASE_RENTA,
    BASE_PRODAJA_P1,
    BASE_RENTA_P1,
)

# ── CONFIG ─────────────────────────────────────────────────────────────────
HEADLESS     = os.environ.get("BNV_HEADLESS", "1") != "0"
NAV_TIMEOUT  = 60_000   # ms — timeout za page.goto / waitForSelector
DELAY_PAGE   = 1.0      # sekundi između stranica liste
DELAY_DETAIL = 0.6      # sekundi između detail fetch-eva
MAX_PAGES    = 25       # safety cap
MAX_EMPTY    = 3        # stop posle N uzastopnih praznih stranica

LISTING_SELECTOR = "a[href*='/oglasi/']"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── PLAYWRIGHT RENDER ────────────────────────────────────────────────────────
def render_soup(page, url: str, wait_selector: str | None = LISTING_SELECTOR) -> BeautifulSoup | None:
    """Učitaj URL u već otvorenom Chromium page-u i vrati BeautifulSoup.
    Browser izvršava JS (Next.js render), pa je sadržaj pravi rendered HTML.
    """
    for attempt in range(1, 4):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=NAV_TIMEOUT)
                except Exception:
                    # selektor se nije pojavio — možda prazna stranica; vrati šta imamo
                    pass
            html = page.content()
            if html and len(html) > 500:
                return BeautifulSoup(html, "html.parser")
            print(f"    Prazan sadržaj ({len(html or '')}b) — pokušaj {attempt}/3")
        except Exception as e:
            print(f"    Greška render-a: {e} (pokušaj {attempt}/3)")
        time.sleep(3 * attempt)
    return None


def goto_listing_page(page, base, base_p1, page_num: int) -> BeautifulSoup | None:
    """Otvori stranicu liste. Stranica 1 je base_p1, stranice 2+ koriste ?strana=N.

    "Prava JS paginacija": prvo pokušavamo da kliknemo na link/dugme stranice
    u paginatoru (kao realan korisnik). Ako klik ne uspe (paginator nije nađen),
    fallback je direktna navigacija na ?strana=N URL — browser i tako renderuje JS.
    """
    if page_num == 1:
        return render_soup(page, base_p1)

    # 1) Pokušaj klik kroz paginator (real JS pagination)
    pager_selectors = [
        f"a[aria-label='{page_num}']",
        f"a[data-page='{page_num}']",
        f".pagination a:has-text('{page_num}')",
        f"nav[aria-label*='agin'] a:has-text('{page_num}')",
        f"a[href*='strana={page_num}']",
    ]
    for sel in pager_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.scroll_into_view_if_needed(timeout=5_000)
                loc.click(timeout=10_000)
                page.wait_for_selector(LISTING_SELECTOR, timeout=NAV_TIMEOUT)
                page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT)
                html = page.content()
                if html and len(html) > 500:
                    print(f"    (klik na paginator '{sel}')")
                    return BeautifulSoup(html, "html.parser")
        except Exception:
            continue

    # 2) Fallback: direktna navigacija na ?strana=N
    return render_soup(page, base.format(page_num))


# ── PARSE DETAIL (iz Playwright soup-a) ──────────────────────────────────────
def parse_detail_soup(soup: BeautifulSoup, oglas_id: str, partial: dict, mode: str) -> dict | None:
    """Identično ponašanje kao scrape_nrs.parse_detail, ali radi nad već
    render-ovanim soup-om (bez ScraperAPI fetch-a). Vraća isti shape zapisa.
    """
    url = f"{SITE_BASE}/oglasi/{oglas_id}/"

    # ── Zgrada ──────────────────────────────────────────────────
    zgrada = "BW (neidentifikovano)"
    for meta_name in [("name", "description"), ("property", "og:description")]:
        meta = soup.find("meta", {meta_name[0]: meta_name[1]})
        if meta:
            z = identify_building(meta.get("content", ""))
            if z and z != "BW (neidentifikovano)":
                zgrada = z
                break

    if zgrada == "BW (neidentifikovano)":
        h1 = soup.select_one("h1")
        if h1:
            z = identify_building(h1.get_text())
            if z and z != "BW (neidentifikovano)":
                zgrada = z

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
        if not agencija:
            for img in soup.select("[class*='advertiser'] img, [class*='agency'] img"):
                alt = img.get("alt", "").strip()
                if alt and len(alt) > 2:
                    agencija = alt
                    break

    if agencija:
        words = agencija.split()
        half = len(words) // 2
        if half > 0 and words[:half] == words[half:]:
            agencija = " ".join(words[:half])
        agencija = agencija.strip() or None

    # ── Sprat ─────────────────────────────────────────────────────
    sprat = None
    for dt in soup.select("dt, th, .label, [class*='label']"):
        if "sprat" in dt.get_text(strip=True).lower():
            nxt = dt.find_next_sibling()
            if nxt:
                sprat = nxt.get_text(strip=True)
                break
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
        meta_opt = soup.find("meta", {"name": "nekretnine_rs:options"})
        if meta_opt:
            m2 = parse_m2(meta_opt.get("content", ""))
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
    naslov = partial.get("naslov", "")
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
def scrape_mode(page, mode: str) -> list[dict]:
    base    = BASE_PRODAJA    if mode == "prodaja" else BASE_RENTA
    base_p1 = BASE_PRODAJA_P1 if mode == "prodaja" else BASE_RENTA_P1
    partials = []
    seen_ids = set()
    empty    = 0

    print(f"\n  Faza 1: prikupljanje listinga (JS paginacija)...")
    for page_num in range(1, MAX_PAGES + 1):
        print(f"    [{mode}] Stranica {page_num}")
        soup = goto_listing_page(page, base, base_p1, page_num)

        if not soup:
            empty += 1
            print(f"    Stranica {page_num}: render fail (empty {empty}/{MAX_EMPTY})")
            if empty >= MAX_EMPTY:
                print(f"    Stop — {MAX_EMPTY} uzastopne greske")
                break
            time.sleep(DELAY_PAGE)
            continue

        items = parse_listing_page(soup)
        if not items:
            empty += 1
            print(f"    Stranica {page_num}: 0 listinga (empty {empty}/{MAX_EMPTY})")
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

        print(f"    Stranica {page_num}: {new} novih ({len(partials)} ukupno)")

        # Ako nema novih ID-jeva, paginacija je iscrpljena (ili petlja)
        if new == 0:
            print(f"    Nema novih oglasa — kraj paginacije")
            break

        h1 = soup.select_one("h1")
        if h1:
            cnt_m = re.search(r"(\d+)\s+rezultat", h1.get_text())
            if cnt_m and len(partials) >= int(cnt_m.group(1)):
                print(f"    Dostignut ukupan broj ({cnt_m.group(1)}) — kraj liste")
                break

        time.sleep(DELAY_PAGE)

    print(f"  Faza 1 zavrsena: {len(partials)} oglasa")

    print(f"\n  Faza 2: detail fetch ({len(partials)} oglasa)...")
    listings = []
    for i, partial in enumerate(partials, 1):
        oglas_id = partial["id"]
        if i % 10 == 0 or i == 1:
            print(f"    [{mode}] {i}/{len(partials)}")
        soup = render_soup(page, f"{SITE_BASE}/oglasi/{oglas_id}/", wait_selector="h1")
        if soup:
            detail = parse_detail_soup(soup, oglas_id, partial, mode)
            if detail:
                listings.append(detail)
        time.sleep(DELAY_DETAIL)

    print(f"  Faza 2 zavrsena: {len(listings)} listinga")
    return listings


# ── GIT PUSH ─────────────────────────────────────────────────────────────────
def git_push(data_dir: Path):
    """Commit-uj i push-uj data/ izmene. Aktivira se samo ako BNV_GIT_PUSH=1.
    Push ide na trenutni branch (ili BNV_PUSH_BRANCH ako je postavljen).
    """
    repo_root = data_dir.parent
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def run(*args):
        return subprocess.run(args, cwd=str(repo_root), capture_output=True, text=True)

    branch = os.environ.get("BNV_PUSH_BRANCH")
    if not branch:
        r = run("git", "rev-parse", "--abbrev-ref", "HEAD")
        branch = r.stdout.strip() or "main"

    print(f"\n  Git: commit + push na '{branch}'...")
    run("git", "add", "data/")
    staged = run("git", "diff", "--cached", "--quiet")
    if staged.returncode == 0:
        print("  Git: nema izmena za commit — preskačem push")
        return

    run("git", "commit", "-m", f"data: nrs playwright scrape {today}")

    for attempt, delay in enumerate([0, 2, 4, 8, 16], 1):
        if delay:
            time.sleep(delay)
        push = run("git", "push", "-u", "origin", branch)
        if push.returncode == 0:
            print(f"  Git: push uspešan ({branch})")
            return
        print(f"  Git: push pokušaj {attempt} nije uspeo:\n{push.stderr.strip()}")
    print("  Git: push NIJE uspeo posle 5 pokušaja")


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("GREŠKA: playwright nije instaliran.")
        print("  pip install playwright beautifulsoup4")
        print("  python -m playwright install chromium")
        sys.exit(1)

    data_dir = Path(__file__).parent.parent / "data"
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso  = datetime.now(timezone.utc).isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(user_agent=USER_AGENT, locale="sr-RS")
        page = context.new_page()
        page.set_default_timeout(NAV_TIMEOUT)

        for mode in ["prodaja", "renta"]:
            print(f"\n{'='*60}")
            print(f"  nekretnine.rs (Playwright) — {mode.upper()}")
            print(f"{'='*60}")

            latest_path  = data_dir / f"latest_nrs_{mode}.json"
            history_path = data_dir / "history_nrs.json"
            eod_path     = data_dir / f"eod_nrs_{today}.json"

            prev_listings = load_json(str(latest_path)).get("listings", [])
            listings      = scrape_mode(page, mode)

            if not listings:
                print(f"  Nema listinga za {mode} — preskačem (zadržavam stari fajl)")
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

        browser.close()

    print(f"\n{'='*60}")
    print("  SCRAPE ZAVRŠEN (Playwright)")
    print(f"{'='*60}")

    if os.environ.get("BNV_GIT_PUSH", "0") == "1":
        git_push(data_dir)
    else:
        print("\n  (git push preskočen — postavi BNV_GIT_PUSH=1 da automatski push-uješ)")


if __name__ == "__main__":
    main()
