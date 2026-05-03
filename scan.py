#!/usr/bin/env python3
"""
scan.py — Entry point for GitHub Actions.

Reads watchlist.json, fetches Screener.in data for each stock,
scores all 13 criteria, writes results to:
  - results/{SYMBOL}.json   (individual stock detail)
  - results/summary.json    (all stocks ranked by score)
  - docs/data.json          (same as summary, served by GitHub Pages)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.screener import fetch
from analyzer.scorer import score

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
DOCS_DIR = ROOT / "docs"
WATCHLIST_FILE = ROOT / "watchlist.json"

RESULTS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)


def load_watchlist() -> tuple[list[str], dict]:
    with open(WATCHLIST_FILE) as f:
        data = json.load(f)
    symbols = data.get("watchlist", [])
    overrides = data.get("settings", {}).get("industry_override", {})
    return symbols, overrides


def run():
    symbols, overrides = load_watchlist()
    print(f"\n=== Stock Scan — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"Scanning {len(symbols)} stocks: {', '.join(symbols)}\n")

    summary = []
    errors = []

    for symbol in symbols:
        print(f"[{symbol}]")
        try:
            raw = fetch(symbol, delay=3.0)
            if "error" in raw:
                print(f"  ERROR: {raw['error']}")
                errors.append({"symbol": symbol, "error": raw["error"]})
                continue

            sector_override = overrides.get(symbol, "")
            result = score(raw, sector_override)
            result["scanned_at"] = datetime.now(timezone.utc).isoformat()

            # Write individual file
            out_path = RESULTS_DIR / f"{symbol}.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2, default=str)

            summary.append({
                "symbol": result["symbol"],
                "name": result["name"],
                "sector": result["sector"],
                "score_pct": result["score_pct"],
                "passes": result["passes"],
                "fails": result["fails"],
                "neutrals": result["neutrals"],
                "verdict": result["verdict"],
                "verdict_color": result["verdict_color"],
                "screener_url": result["screener_url"],
                "top_ratios": result.get("top_ratios", {}),
                "scanned_at": result["scanned_at"],
            })

            print(f"  Score: {result['score_pct']}% | {result['verdict']}")
            print(f"  Pass: {result['passes']} | Fail: {result['fails']} | Neutral: {result['neutrals']}\n")

        except Exception as e:
            print(f"  EXCEPTION: {e}")
            errors.append({"symbol": symbol, "error": str(e)})

    # Sort by score descending
    summary.sort(key=lambda x: x["score_pct"], reverse=True)

    scan_meta = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total": len(symbols),
        "success": len(summary),
        "errors": len(errors),
        "error_details": errors,
    }

    # Write summary.json
    summary_payload = {"meta": scan_meta, "stocks": summary}
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump(summary_payload, f, indent=2, default=str)

    # Write docs/data.json (served by GitHub Pages)
    with open(DOCS_DIR / "data.json", "w") as f:
        json.dump(summary_payload, f, indent=2, default=str)

    # Write docs/results/ individual files for detail view
    results_docs_dir = DOCS_DIR / "results"
    results_docs_dir.mkdir(exist_ok=True)
    for symbol in symbols:
        src = RESULTS_DIR / f"{symbol}.json"
        if src.exists():
            import shutil
            shutil.copy(src, results_docs_dir / f"{symbol}.json")

    print(f"=== Done — {len(summary)}/{len(symbols)} stocks scanned ===")
    if errors:
        print(f"Errors: {[e['symbol'] for e in errors]}")


if __name__ == "__main__":
    run()
