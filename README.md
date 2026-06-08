# BnV Tracker 🏢

Automatski dnevni scraper za praćenje prodaje stanova na Beogradu na vodi (Halo Oglasi).

**Šta radi:**
- Svaki dan u 09:00h (Beograd vreme) scrape-uje sve stranice oglasa
- Prati nove i skinute oglase (diff)
- Grupiše po zgradama i tipu stana
- Beleži cene min/max/prosek i €/m²
- Čuva sve podatke u JSON fajlovima unutar ovog repoa

---

## Setup (5 koraka, ~10 minuta)

### Korak 1 — Fork ili kreiraj GitHub repo

```bash
# Opcija A: fork ovog repoa na GitHubu (klikni Fork)

# Opcija B: novi repo
git init bnv-tracker
cd bnv-tracker
# prekopiri sve fajlove ovde
git add .
git commit -m "init"
git remote add origin https://github.com/TvojUsername/bnv-tracker.git
git push -u origin main
```

### Korak 2 — Podesi GitHub Actions permisije

1. Idi na `Settings → Actions → General`
2. Pod **Workflow permissions** izaberi **Read and write permissions**
3. Klikni **Save**

(Ovo je neophodno da bi bot mogao da commituje `data/` fajlove.)

### Korak 3 — Proveri da je workflow aktivan

1. Idi na `Actions` tab
2. Trebalo bi da vidiš `BnV Daily Scraper`
3. Klikni **Run workflow** → **Run workflow** za ručni test

Workflow će se izvršiti, scrape-ovati sajt i commitovati rezultate u `data/`.

### Korak 4 — Dashboard setup

Dashboard čita `data/latest.json` direktno sa GitHub raw CDN.

**Opcija A: Embed u Claude artifact** (najbrže)
- Otvori `dashboard/src/Dashboard.jsx`
- Zameni `USERNAME/bnv-tracker` sa tvojim repo imenom
- Napravi novi artifact u Claude i nalepite kod

**Opcija B: GitHub Pages** (trajna web stranica, besplatno)
```bash
# U repo folderu
npm create vite@latest . -- --template react
# Zameni src/App.jsx sa dashboard/src/Dashboard.jsx
npm install
npm run build

# U GitHub: Settings → Pages → Source: GitHub Actions
# ili dodaj .github/workflows/deploy.yml (vidi ispod)
```

**Opcija C: Vercel/Netlify** (automatski deploy na svaki commit)
- Connectuj repo na vercel.com
- Build command: `npm run build`
- Output dir: `dist`

### Korak 5 — Zameni USERNAME u kodu

U `dashboard/src/Dashboard.jsx`, linija 9:
```js
// PROMENI OVO:
const REPO_RAW = "https://raw.githubusercontent.com/USERNAME/bnv-tracker/main/data";

// U OVO (tvoj GitHub username i repo ime):
const REPO_RAW = "https://raw.githubusercontent.com/MojUsername/bnv-tracker/main/data";
```

---

## Struktura projekta

```
bnv-tracker/
├── .github/
│   └── workflows/
│       └── daily_scrape.yml   # GitHub Actions cron job
├── scraper/
│   ├── scrape.py              # Playwright scraper + diff engine
│   └── requirements.txt
├── dashboard/
│   └── src/
│       └── Dashboard.jsx      # React dashboard
├── data/
│   ├── latest.json            # Uvek poslednji snapshot (dashboard čita ovo)
│   ├── history.json           # Agregirani trend po danima
│   └── snapshot_YYYY-MM-DD.json  # Dnevni arhivi
└── README.md
```

---

## Kako radi scraper

1. **Playwright headless Chromium** — pokreće pravi browser, izvršava JavaScript, zaobilazi bot detekciju
2. **Paginacija** — prolazi sve stranice (~38 stranica × 15 oglasa = ~564 oglasa)
3. **Deduplikacija** — isti stan oglašen od više agencija → jedan unique listing
4. **Diff engine** — poredi sa prethodnim danom, detektuje nove i skinute oglase
5. **Statistike** — agregira po strukturi i zgradi (min/max/avg cena, €/m²)
6. **Commit** — bot automatski commituje JSON fajlove

---

## Podaci koji se prate

Po svakom oglasu:
- ID, URL, naslov
- Zgrada (kanonski naziv: BW Iris, BW Victoria...)
- Struktura (0.5=garsonjera, 1.0=jednosoban... 5.0=petosoban+)
- Kvadratura (m²)
- Cena (EUR)
- Cena po m² (EUR/m²)
- Sprat
- Tip oglašivača (vlasnik/agencija/investitor)
- Datum scrape-a

Po danu u history.json:
- Ukupno raw oglasa (broj koji vidiš na sajtu)
- Unique nekretnine (posle deduplikacije)
- Duplikati (koliko agencija oglašava iste stanove)
- Novi oglasi vs prethodni dan
- Skinuti oglasi vs prethodni dan
- Breakdown po tipu stana

---

## Troškovi

**Sve besplatno:**
- GitHub Actions: 2000 min/mesec besplatno (svaki run ≈ 5-8 min)
- GitHub storage: neograničeno za tekstualne fajlove
- GitHub Pages: besplatno za javne repoe

---

## Troubleshooting

**"Site blocked the request"**
→ Halo Oglasi povremeno menja bot-detection. Otvori `scraper/scrape.py` i podesi `PAGE_DELAY` na veću vrednost (npr. 4.0).

**"No product cards found"**
→ Sajt je promenio CSS klase. Otvori `extract_listing()` i dodaj novi selektor u listu.

**Workflow ne commitu-je**
→ Proveri `Settings → Actions → General → Workflow permissions → Read and write`.

**Manje od 15 oglasa po stranici**
→ Normalno za poslednju stranicu. Scraper detektuje praznu stranicu i staje.
