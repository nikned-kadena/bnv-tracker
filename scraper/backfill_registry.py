#!/usr/bin/env python3
"""
backfill_registry.py — rekonstruise registar iz starih snapshot fajlova.

ZASTO
-----
Registar sam po sebi zna samo ono sto vidi od dana kad je ukljucen. Da smo
ga samo upalili, `first_seen` bi svim stanovima bio danasnji datum i DOM
statistika bi bila upotrebljiva tek za nekoliko meseci.

Ali mi VEC imamo istoriju: `data/snapshot_{mode}_YYYY-MM-DD.json` postoji za
svaki dan od pocetka pracenja. Ovaj skript ih prolazi hronoloski i pusta
kroz istu `store.update()` logiku kao da se run desavao tog dana. Rezultat
je registar sa stvarnim datumima objave i skidanja, unazad.

Pokretanje (jednokratno, pre prvog pravog run-a sa store slojem):
    python scraper/backfill_registry.py            # oba moda
    python scraper/backfill_registry.py prodaja    # samo jedan

RUPE U SERIJI
-------------
Gde nedostaju snapshot fajlovi (11-20.08. i 12-15.09.2026 na BnV-u), ne
znamo kog dana je oglas stvarno skinut — znamo samo da ga nije bilo kad se
pracenje nastavilo. Takvi oglasi se obelezavaju sa `deactivation_uncertain`
i njihovo trajanje je precenjeno za duzinu rupe. Skript ispisuje sve rupe
koje nadje da bi se znalo koliko podataka je pogodjeno.
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import store  # noqa: E402


def run(data_dir: Path, mode: str, source: str = "halo") -> dict:
    files = sorted(data_dir.glob(f"snapshot_{mode}_*.json"))
    if not files:
        print(f"[BACKFILL] Nema snapshot fajlova za {mode} — nista za rekonstrukciju.")
        return {}

    reg_path = data_dir / f"registry_{mode}.json"
    if reg_path.exists():
        print(f"[BACKFILL] {reg_path.name} vec postoji. Obrisi ga rucno ako zelis "
              f"da rekonstruises iz nule — necu ga pregaziti.")
        return {}

    print(f"[BACKFILL] {mode}: {len(files)} snapshot fajlova "
          f"({files[0].stem.split('_')[-1]} → {files[-1].stem.split('_')[-1]})")

    gaps, prev_d, n_l = [], None, 0
    for f in files:
        d_str = f.stem.split("_")[-1]
        try:
            d = date.fromisoformat(d_str)
        except ValueError:
            print(f"  ⚠ Preskacem {f.name} — neispravan datum u imenu.")
            continue

        if prev_d and (d - prev_d).days > 1:
            gaps.append({"od": prev_d.isoformat(), "do": d_str, "dana": (d - prev_d).days - 1})
        prev_d = d

        try:
            snap = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ Preskacem {f.name}: {e}")
            continue

        listings = snap.get("listings", [])
        n_l += len(listings)
        store.update(data_dir, mode, listings, source=source,
                     run_date=d_str, verbose=False)

    # obelezi deaktivacije koje su pale odmah posle rupe kao nesigurne
    reg = store.load_registry(data_dir, mode)
    gap_ends = {g["do"] for g in gaps}
    n_unc = 0
    for e in reg["entries"].values():
        if e.get("deactivated_at") in gap_ends:
            e["deactivation_uncertain"] = True
            n_unc += 1
    store.save_registry(data_dir, mode, reg)

    ent = reg["entries"]
    aktivni = sum(1 for e in ent.values() if e.get("is_active"))
    zavrseni = len(ent) - aktivni

    print(f"  → obradjeno {n_l} zapisa iz {len(files)} fajlova")
    print(f"  → registar: {len(ent)} oglasa ({aktivni} aktivnih, {zavrseni} skinutih)")
    if gaps:
        uk = sum(g['dana'] for g in gaps)
        print(f"  ⚠ RUPE U SERIJI: {len(gaps)}, ukupno {uk} dana bez podataka")
        for g in gaps:
            print(f"      {g['od']} → {g['do']}  ({g['dana']} dana)")
        print(f"  ⚠ {n_unc} oglasa ima nesigurno vreme skidanja "
              f"(obelezeni sa deactivation_uncertain) — trajanje im je precenjeno.")
    return {"oglasa": len(ent), "aktivnih": aktivni, "rupe": gaps, "nesigurnih": n_unc}


if __name__ == "__main__":
    dd = Path(__file__).parent.parent / "data"
    modes = [sys.argv[1]] if len(sys.argv) > 1 else ["prodaja", "renta"]
    for m in modes:
        run(dd, m)
        print()
