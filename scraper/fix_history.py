#!/usr/bin/env python3
"""
fix_history.py — Čisti history fajlove, ostavlja samo poslednji entry po danu
Pokrenuti jednom: python scraper/fix_history.py
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def fix_history(path):
    if not path.exists():
        print(f"  ⚠ Ne postoji: {path}")
        return

    history = json.load(open(path, encoding="utf-8"))
    print(f"  Pre:  {len(history)} entryja u {path.name}")

    # Za svaki datum+mode, zadrži samo poslednji entry
    seen = {}
    for entry in history:
        key = (entry.get("date"), entry.get("mode"))
        seen[key] = entry  # overwrite → ostaje poslednji

    cleaned = list(seen.values())
    # Sortiraj po datumu
    cleaned.sort(key=lambda x: (x.get("date",""), x.get("mode","")))

    print(f"  Posle: {len(cleaned)} entryja")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Sačuvano")

print("Čišćenje history fajlova...")
fix_history(DATA_DIR / "history.json")
fix_history(DATA_DIR / "history_prodaja.json")
fix_history(DATA_DIR / "history_renta.json")
print("Gotovo.")
