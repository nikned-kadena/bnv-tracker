@echo off
cd /d C:\bnv-tracker\bnv-tracker

REM Povuci najnoviju verziju koda i podataka pre pokretanja
git stash -u >> logs\nrs_scraper.log 2>&1
git pull --rebase origin main >> logs\nrs_scraper.log 2>&1
git stash pop >> logs\nrs_scraper.log 2>&1

REM Pokreni scraper (sam radi git push na kraju)
"C:\Users\NikolaNedeljkovic\AppData\Local\Python\bin\python.exe" scraper\scrape_nrs_playwright.py >> logs\nrs_scraper.log 2>&1
