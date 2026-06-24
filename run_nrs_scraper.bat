@echo off
cd /d C:\bnv-tracker\bnv-tracker
"C:\Users\NikolaNedeljkovic\AppData\Local\Python\bin\python.exe" scraper\scrape_nrs_playwright.py >> logs\nrs_scraper.log 2>&1