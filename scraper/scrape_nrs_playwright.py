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
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Windows konzola/log koristi cp1252 i puca na ćirilici/strelicama/emoji.
# Forsiramo UTF-8 izlaz; errors='replace' garantuje da ispis nikad ne sruši scraper.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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
    "vojvode milenka",
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

        # Cena sa detaljne stranice (mnogi oglasi nemaju cenu na listing pregledu)
        if not data.get("cena"):
            cena_found = None
            # Probaj ciljani element sa cenom
            for sel in ["[class*='price']", "[class*='Price']", "[class*='cena']", "[class*='Cena']"]:
                el = page.locator(sel).first
                if await el.count() > 0:
                    try:
                        txt = (await el.inner_text()).strip()
                        m = re.search(r"€\s*([\d\.\s]+)", txt)
                        if m and not re.search(r"€\s*[\d\.\s]+\s*/?\s*m", txt):
                            cena_found = m.group(1).strip()
                            break
                    except Exception:
                        pass
            # Fallback: ceo body, prvi € iznos koji NIJE €/m²
            if not cena_found:
                try:
                    body = await page.locator("body").inner_text()
                    # Ukloni "€ X/m²" obrasce da ne uhvatimo cenu po kvadratu
                    body_clean = re.sub(r"€\s*[\d\.\s]+\s*/?\s*m²", " ", body)
                    m = re.search(r"€\s*([\d]{1,3}(?:[\.\s]\d{3})*)", body_clean)
                    if m:
                        cena_found = m.group(1).strip()
                except Exception:
                    pass
            if cena_found:
                c = clean_price(cena_found)
                if c and c >= 100:  # ignoriši sitne brojeve
                    data["cena_raw"] = "€ " + cena_found
                    data["cena"] = c

        # Opis oglasa — naziv zgrade je često ovde, ne u naslovu
        opis_parts = []
        meta = page.locator("meta[name='description']").first
        if await meta.count() > 0:
            md = await meta.get_attribute("content")
            if md:
                opis_parts.append(md)
        for sel in ["[class*='description']", "[class*='Description']",
                    "[class*='opis']", ".listing-detail__description", "article"]:
            el = page.locator(sel).first
            if await el.count() > 0:
                try:
                    txt = (await el.inner_text()).strip()
                    if txt and len(txt) > 30:
                        opis_parts.append(txt)
                        break
                except Exception:
                    pass
        if opis_parts:
            data["opis"] = " ".join(opis_parts)[:2000]

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

# Mapiranje ključnih reči (iz naslova ILI opisa) na naziv zgrade
ZGRADA_KEYWORDS = {
    "St. Regis":        ["st. regis", "st regis", "st.regis", "bw kula", "bw kuli", "bw kule"],
    "BW Residences":    ["bw residences", "bw residence"],
    "BW Quartet":       ["bw quartet", "quartet"],
    "BW Aria":          ["bw aria", "aria"],
    "BW Perla":         ["bw perla", "perla"],
    "BW Victoria":      ["bw victoria", "victoria"],
    "BW Simfonija":     ["bw simfonija", "simfonija"],
    "BW Iris":          ["bw iris", "iris"],
    "BW Magnolia":      ["bw magnolia", "magnolia"],
    "BW Aqua":          ["bw aqua", "aqua"],
    "BW Diva":          ["bw diva", "diva"],
    "BW Iskra":         ["bw iskra", "iskra"],
    "BW Lumia":         ["bw lumia", "lumia"],
    "BW Vista":         ["bw vista", "vista"],
    "BW Riviera":       ["bw riviera", "riviera"],
    "BW Metropolitan":  ["bw metropolitan", "metropolitan"],
    "BW King's Park":   ["king's park", "kings park", "king`s park"],
    "BW Queens":        ["bw queens"],
    "BW Eterna":        ["bw eterna", "eterna"],
    "BW Sole":          ["bw sole"],
    "BW Libera":        ["bw libera", "libera"],
    "BW Sensa":         ["bw sensa", "sensa"],
    "BW Parkview":      ["bw parkview", "parkview"],
    "BW Apollo":        ["bw apollo"],
    "BW Terraces":      ["bw terraces", "terraces"],
    "Bristol Residences":["bristol residences", "bristol"],
    "AFI Skyline":      ["afi skyline", "skyline residence"],
}

# Mapiranje naslova na strukturu (Halo format: "1.0", "2.0", ...)
def detect_struktura(naslov: str, sobe: str = None) -> str:
    """Detektuje strukturu iz naslova ili broja soba."""
    if not naslov:
        naslov = ""
    n = naslov.lower()

    # Prvo probaj iz teksta naslova
    if "garsonjer" in n or "studio" in n:
        return "1.0"
    if "jednoiposob" in n:
        return "1.5"
    if "jednosob" in n:
        return "1.0"
    if "dvoiposob" in n:
        return "2.5"
    if "dvosob" in n:
        return "2.0"
    if "troiposob" in n:
        return "3.5"
    if "trosob" in n:
        return "3.0"
    if "cetvorosob" in n or "četvorosob" in n:
        return "4.0"
    if "petosob" in n or "petosoban" in n:
        return "5.0"

    # Fallback: iz broja soba
    if sobe:
        try:
            br = float(str(sobe).replace(",", "."))
            mapa = {1.0:"1.0", 1.5:"1.5", 2.0:"2.0", 2.5:"2.5",
                    3.0:"3.0", 3.5:"3.5", 4.0:"4.0", 5.0:"5.0"}
            if br >= 5:
                return "5.0"
            return mapa.get(br, "nepoznato")
        except (ValueError, TypeError):
            pass

    return "nepoznato"

def detect_zgrada(naslov: str, opis: str = "") -> str:
    """Detektuje naziv zgrade iz naslova ILI opisa oglasa."""
    tekst = ((naslov or "") + " " + (opis or "")).lower()
    if not tekst.strip():
        return "Neidentifikovano"
    for zgrada, keywords in ZGRADA_KEYWORDS.items():
        if any(kw in tekst for kw in keywords):
            return zgrada
    return "Neidentifikovano"

def _norm_sprat(s) -> str:
    """Izvuče samo cifre sprata za poređenje (npr 'sprat 5' -> '5')."""
    if not s:
        return ""
    return re.sub(r"[^\d]", "", str(s))[:3]

def compute_dedup(listings: list[dict]) -> tuple[int, int, list[dict]]:
    """
    Označava duplikate: isti fizički stan koji je više agencija postavilo
    pod različitim ID-evima.

    Pravilo: ista ZGRADA + ista KVADRATURA + ista CENA = isti stan.
      - Cena i kvadratura MORAJU postojati (cena je ključ). Bez njih -> jedinstven.
      - Za poznatu zgradu: ključ = zgrada | m² | cena
      - Za nepoznatu zgradu: dodaje se i sprat (zgrada|m²|cena|sprat) radi sigurnosti,
        da se ne spoje dva različita stana iste površine/cene.

    Vraća: (broj_jedinstvenih, broj_duplikata, lista_duplikata)
    Svakom listingu upisuje 'dedup_key'.
    """
    groups: dict[str, list[dict]] = {}
    for l in listings:
        m2   = l.get("m2") or l.get("kvadratura")
        cena = l.get("cena")
        zgrada = l.get("zgrada") or "Neidentifikovano"
        key = None
        if m2 and cena:
            try:
                m2r = round(float(m2))
                if zgrada == "Neidentifikovano":
                    key = f"NID|{m2r}|{int(cena)}|{_norm_sprat(l.get('sprat'))}"
                else:
                    key = f"{zgrada}|{m2r}|{int(cena)}"
            except (ValueError, TypeError):
                key = None
        if not key:
            key = f"ID|{l.get('id')}"  # ne može se pouzdano dedupovati
        l["dedup_key"] = key
        groups.setdefault(key, []).append(l)

    duplicates = []
    for key, grp in groups.items():
        if key.startswith("ID|"):
            continue
        if len(grp) > 1:
            # prvi (najstariji/prvi viđen) je kanonski; ostali su duplikati
            for dup in grp[1:]:
                duplicates.append({
                    "id":      dup.get("id"),
                    "naslov":  dup.get("naslov"),
                    "agencija": dup.get("agencija"),
                    "dedup_key": key,
                })
    total_unique = len(groups)
    total_dups   = len(listings) - total_unique
    return total_unique, total_dups, duplicates

def build_output(listings: list[dict], path: Path) -> dict:
    """Wrappe listu listinga u format koji Dashboard ocekuje."""
    # Očisti listinge koji matchuju exclusion (za slučaj starih podataka)
    listings = [l for l in listings if not should_exclude(l.get("naslov", ""))]

    # Detektuj zgrade i strukturu pre svega ostalog
    for l in listings:
        if not l.get("zgrada") or l.get("zgrada") == "Neidentifikovano":
            l["zgrada"] = detect_zgrada(l.get("naslov", ""), l.get("opis", ""))
        if not l.get("struktura"):
            l["struktura"] = detect_struktura(l.get("naslov", ""), l.get("sobe"))
        # Dashboard koristi 'm2' polje — mapiraj iz 'kvadratura'
        if not l.get("m2") and l.get("kvadratura"):
            l["m2"] = l["kvadratura"]

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

    # Detekcija duplikata: ista zgrada + kvadratura + cena = isti stan
    total_unique, total_dups, duplicates = compute_dedup(listings)

    return {
        "scraped_at":   datetime.now().isoformat(timespec="seconds"),
        "total_raw":    len(listings),
        "total_unique": total_unique,
        "total_dups":   total_dups,
        "listings":     listings,
        "diff":         diff,
        "duplicates":   duplicates,
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
