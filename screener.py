"""
fetchers/screener.py — Scrapes Screener.in for fundamental data.
No API key needed. Uses consolidated page, falls back to standalone.
"""

import time
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 404:
            url2 = url.replace("/consolidated/", "/")
            r = requests.get(url2, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  [!] HTTP {r.status_code} for {url}")
            return None
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"  [!] Fetch error: {e}")
        return None


def _num(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[,%₹\s]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def _table(soup: BeautifulSoup, section_id: str) -> dict:
    section = soup.find("section", {"id": section_id})
    if not section:
        return {}
    table = section.find("table")
    if not table:
        return {}
    result = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        values = [_num(c.get_text(strip=True)) for c in cells[1:]]
        result[label] = values
    return result


def _top_ratios(soup: BeautifulSoup) -> dict:
    out = {}
    for li in soup.select("#top-ratios li"):
        name_el = li.find("span", class_="name")
        val_el = li.find("span", class_="value")
        if name_el and val_el:
            out[name_el.get_text(strip=True)] = _num(val_el.get_text(strip=True))
    return out


def _last(lst: list) -> float | None:
    clean = [v for v in lst if v is not None]
    return clean[-1] if clean else None


def _increasing(values: list, min_pts: int = 3) -> bool | None:
    clean = [v for v in values if v is not None]
    if len(clean) < min_pts:
        return None
    return clean[-1] > clean[0]


def _avg_growth(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    g = []
    for i in range(1, len(clean)):
        if clean[i - 1] and clean[i - 1] != 0:
            g.append((clean[i] - clean[i - 1]) / abs(clean[i - 1]) * 100)
    return round(sum(g) / len(g), 2) if g else None


def fetch(symbol: str, delay: float = 2.0) -> dict:
    symbol = symbol.upper().strip()
    print(f"  Fetching {symbol} from Screener.in...")
    time.sleep(delay)

    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    soup = _get(url)
    if soup is None:
        return {"error": f"Could not fetch {symbol}"}

    h1 = soup.find("h1")
    if h1 and "not found" in h1.get_text().lower():
        return {"error": f"Symbol '{symbol}' not found on Screener.in"}

    pl       = _table(soup, "profit-loss")
    bs       = _table(soup, "balance-sheet")
    cf       = _table(soup, "cash-flow")
    ratios   = _table(soup, "ratios")
    top      = _top_ratios(soup)

    name = h1.get_text(strip=True) if h1 else symbol
    sector_el = soup.select_one(".company-links a")
    sector = sector_el.get_text(strip=True) if sector_el else ""

    sales      = pl.get("Sales", pl.get("Revenue", []))
    op         = pl.get("Operating Profit", [])
    net_profit = pl.get("Net Profit", [])
    eps        = pl.get("EPS in Rs", ratios.get("EPS in Rs", []))
    opm        = pl.get("OPM %", ratios.get("OPM %", []))
    npm        = pl.get("NPM %", [])
    reserves   = bs.get("Reserves", [])
    debt       = bs.get("Borrowings", bs.get("Total Debt", []))
    fixed_a    = bs.get("Fixed Assets", bs.get("Net Block", []))
    cash_bs    = bs.get("Cash Equivalents", bs.get("Cash & Bank", []))
    payables   = bs.get("Trade Payables", [])
    receivables= bs.get("Trade Receivables", [])
    inventory  = bs.get("Inventories", [])
    cfo        = cf.get("Cash from Operating Activity", cf.get("Operating Activity", []))
    cfi        = cf.get("Cash from Investing Activity", cf.get("Investing Activity", []))
    cff        = cf.get("Cash from Financing Activity", cf.get("Financing Activity", []))
    roe_s      = ratios.get("Return on Equity %", ratios.get("ROE %", []))
    roce_s     = ratios.get("ROCE %", [])

    tp  = _last(payables) or 0
    tr  = _last(receivables) or 0
    inv = _last(inventory) or 0
    nwc = (tr + inv) - tp

    d2e = top.get("Debt / Equity")
    if d2e is None:
        d_v = _last(debt); e_v = _last(bs.get("Equity Capital", []))
        d2e = round(d_v / e_v, 2) if d_v and e_v and e_v != 0 else None

    return {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "url": url,
        "top_ratios": top,
        "series": {
            "sales": sales, "operating_profit": op, "net_profit": net_profit,
            "eps": eps, "opm_pct": opm, "npm_pct": npm,
            "reserves": reserves, "debt": debt, "fixed_assets": fixed_a,
            "cash_bs": cash_bs, "cfo": cfo, "cfi": cfi, "cff": cff,
            "roe": roe_s, "roce": roce_s,
        },
        "derived": {
            "sales_avg_growth": _avg_growth(sales),
            "eps_increasing": _increasing(eps),
            "reserves_increasing": _increasing(reserves),
            "cash_increasing": _increasing(cash_bs),
            "fixed_assets_increasing": _increasing(fixed_a),
            "cfo_positive": (_last(cfo) or 0) > 0,
            "cfo_increasing": _increasing(cfo),
            "cfi_negative": (_last(cfi) or 0) < 0,
            "nwc": round(nwc, 2),
            "nwc_negative": nwc < 0,
            "debt_to_equity": d2e,
            "roe": _last(roe_s),
            "roce": _last(roce_s),
            "opm": _last(opm),
            "npm": _last(npm),
            "last_cfo": _last(cfo),
            "last_cfi": _last(cfi),
            "last_cff": _last(cff),
        },
    }
