@echo off
REM ============================================================
REM BnV Halo Scraper - v2.2 (04.07.2026)
REM Izmene u odnosu na v2.1:
REM   1. Brana sada proverava i SVEZINU fajla (mora biti od danas)
REM      - stari podaci vise ne mogu da prodju kao "lazno zeleno"
REM   2. python -u flag: log hronoloski uredan (stdout bez buffera)
REM Napomena: SCRAPER_API_KEY je user env varijabla, ne setuje se ovde.
REM Lokacija: C:\bnv-tracker\bnv-tracker\run_halo_scraper.bat
REM ============================================================

set PYTHONUTF8=1
set GIT_MERGE_AUTOEDIT=no
cd /d C:\bnv-tracker\bnv-tracker

echo [%date% %time%] Pokretanje BnV Halo scrapera... >> logs\halo_scraper.log 2>&1

REM Povuci najnoviju verziju koda pre pokretanja (isto kao NRS bat).
git pull --no-rebase --no-edit -X ours origin main >> logs\halo_scraper.log 2>&1

REM Pokreni Halo scraper (scrape.py radi prodaju i rentu, bez git logike).
"C:\Users\NikolaNedeljkovic\AppData\Local\Python\bin\python.exe" -u scraper\scrape.py >> logs\halo_scraper.log 2>&1
if %errorlevel% neq 0 goto :greska_scrape

REM Brana v2: (a) fajlovi modifikovani DANAS, (b) minimalan broj oglasa.
"C:\Users\NikolaNedeljkovic\AppData\Local\Python\bin\python.exe" -u -c "import json,sys,os,datetime; danas=datetime.date.today(); fp='data/latest_prodaja.json'; fr='data/latest_renta.json'; sp=datetime.date.fromtimestamp(os.path.getmtime(fp)); sr=datetime.date.fromtimestamp(os.path.getmtime(fr)); p=len(json.load(open(fp,encoding='utf-8')).get('listings',[])); r=len(json.load(open(fr,encoding='utf-8')).get('listings',[])); print(f'Provera: prodaja={p} ({sp}), renta={r} ({sr})'); sys.exit(0 if sp==danas and sr==danas and p>=100 and r>=50 else 3)" >> logs\halo_scraper.log 2>&1
if %errorlevel% neq 0 goto :greska_brana

git add data\ >> logs\halo_scraper.log 2>&1
git diff --cached --quiet
if %errorlevel% equ 0 goto :nema_promena

git commit -m "data: halo scrape %date%" >> logs\halo_scraper.log 2>&1
git push origin main >> logs\halo_scraper.log 2>&1
if %errorlevel% neq 0 goto :greska_push

echo [%date% %time%] Pushano na GitHub >> logs\halo_scraper.log
goto :kraj

:greska_scrape
echo [%date% %time%] GRESKA u scrape.py >> logs\halo_scraper.log
exit /b 1

:greska_brana
echo [%date% %time%] STOP: podaci nisu svezi ili premalo oglasa - NE commitujem >> logs\halo_scraper.log
exit /b 1

:greska_push
echo [%date% %time%] GRESKA: push NEUSPESAN - podaci ostaju lokalno >> logs\halo_scraper.log
exit /b 1

:nema_promena
echo [%date% %time%] Nema promena >> logs\halo_scraper.log

:kraj
echo [%date% %time%] Zavrseno >> logs\halo_scraper.log
exit /b 0