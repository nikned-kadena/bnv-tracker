@echo off
cd /d C:\bnv-tracker\bnv-tracker

REM Povuci najnoviju verziju koda pre pokretanja.
REM Radni direktorijum je cist na pocetku, pa je merge bezbedan (bez stash/rebase).
git pull --no-rebase --no-edit -X ours origin main >> logs\nrs_scraper.log 2>&1

REM Pokreni scraper (sam radi add/commit/pull/push na kraju)
"C:\Users\NikolaNedeljkovic\AppData\Local\Python\bin\python.exe" scraper\scrape_nrs_playwright.py >> logs\nrs_scraper.log 2>&1
