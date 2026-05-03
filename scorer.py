"""
analyzer/scorer.py — Auto-scores 13 fundamental criteria.
"""

from __future__ import annotations

SECTOR_BENCHMARKS = {
    "default":     {"opm": 15.0, "npm": 8.0,  "sales_growth": 10.0},
    "IT":          {"opm": 22.0, "npm": 18.0, "sales_growth": 12.0},
    "Banking":     {"opm": 35.0, "npm": 20.0, "sales_growth": 12.0},
    "NBFC":        {"opm": 30.0, "npm": 15.0, "sales_growth": 14.0},
    "Pharma":      {"opm": 20.0, "npm": 12.0, "sales_growth": 10.0},
    "FMCG":        {"opm": 18.0, "npm": 12.0, "sales_growth": 8.0},
    "Auto":        {"opm": 12.0, "npm": 6.0,  "sales_growth": 10.0},
    "Metal":       {"opm": 14.0, "npm": 7.0,  "sales_growth": 8.0},
    "Cement":      {"opm": 18.0, "npm": 8.0,  "sales_growth": 9.0},
    "Chemical":    {"opm": 18.0, "npm": 10.0, "sales_growth": 11.0},
    "Consumer":    {"opm": 16.0, "npm": 10.0, "sales_growth": 10.0},
    "Power":       {"opm": 25.0, "npm": 10.0, "sales_growth": 10.0},
    "Infra":       {"opm": 12.0, "npm": 5.0,  "sales_growth": 12.0},
    "Real Estate": {"opm": 25.0, "npm": 12.0, "sales_growth": 15.0},
    "Telecom":     {"opm": 30.0, "npm": 8.0,  "sales_growth": 8.0},
}


def _bench(sector: str, override: str = "") -> dict:
    src = override or sector or ""
    for k in SECTOR_BENCHMARKS:
        if k.lower() in src.lower():
            return SECTOR_BENCHMARKS[k]
    return SECTOR_BENCHMARKS["default"]


def _f(v, suf="", dec=1) -> str:
    return f"{round(v, dec)}{suf}" if v is not None else "N/A"


def _trend(lst: list, n: int = 3) -> str:
    clean = [v for v in lst if v is not None]
    return " → ".join(_f(x) for x in clean[-n:]) + f" (last {min(n,len(clean))}Y)" if clean else "no data"


def score(data: dict, sector_override: str = "") -> dict:
    if "error" in data:
        return {"error": data["error"], "symbol": data.get("symbol", "")}

    d = data["derived"]
    s = data["series"]
    bench = _bench(data.get("sector", ""), sector_override)

    def crit(id_, label, result, score_val, detail, weight=1.0):
        return {"id": id_, "label": label, "result": result,
                "score": score_val, "detail": detail, "weight": weight}

    criteria = []

    # C1 — Sales growth
    sg = d["sales_avg_growth"]
    ib = bench["sales_growth"]
    if sg is None:
        c = crit("c1","Sales growth ≥ industry","neutral",0.5,f"Insufficient data. Benchmark: {ib}%")
    elif sg >= ib:
        c = crit("c1","Sales growth ≥ industry","pass",1.0,f"Avg growth {_f(sg,'%')} vs benchmark {ib}%")
    else:
        c = crit("c1","Sales growth ≥ industry","fail",0.0,f"Avg growth {_f(sg,'%')} below benchmark {ib}%")
    criteria.append(c)

    # C2 — OPM
    opm = d["opm"]; iopm = bench["opm"]
    if opm is None:
        c = crit("c2","OPM > industry","neutral",0.5,"OPM data unavailable")
    elif opm > iopm:
        c = crit("c2","OPM > industry","pass",1.0,f"OPM {_f(opm,'%')} vs benchmark {iopm}%")
    else:
        c = crit("c2","OPM > industry","fail",0.0,f"OPM {_f(opm,'%')} below benchmark {iopm}%")
    criteria.append(c)

    # C3 — EPS increasing (weight 1.5)
    ei = d["eps_increasing"]
    if ei is None:
        c = crit("c3","EPS consistently increasing","neutral",0.5,f"Trend: {_trend(s['eps'])}",1.5)
    elif ei:
        c = crit("c3","EPS consistently increasing","pass",1.0,f"EPS: {_trend(s['eps'])}",1.5)
    else:
        c = crit("c3","EPS consistently increasing","fail",0.0,f"EPS not rising: {_trend(s['eps'])}",1.5)
    criteria.append(c)

    # C4 — NPM
    npm = d["npm"]; inpm = bench["npm"]
    if npm is None:
        c = crit("c4","Net margin ≥ industry","neutral",0.5,"NPM data unavailable")
    elif npm >= inpm:
        c = crit("c4","Net margin ≥ industry","pass",1.0,f"NPM {_f(npm,'%')} vs benchmark {inpm}%")
    else:
        c = crit("c4","Net margin ≥ industry","fail",0.0,f"NPM {_f(npm,'%')} below benchmark {inpm}%")
    criteria.append(c)

    # C5 — Reserves increasing
    ri = d["reserves_increasing"]
    if ri is None:
        c = crit("c5","Reserves increasing","neutral",0.5,"Insufficient reserves data")
    elif ri:
        c = crit("c5","Reserves increasing","pass",1.0,f"Reserves: {_trend(s['reserves'])} Cr")
    else:
        c = crit("c5","Reserves increasing","fail",0.0,f"Reserves declining: {_trend(s['reserves'])} Cr")
    criteria.append(c)

    # C6 — Low debt (weight 1.5)
    d2e = d["debt_to_equity"]
    if d2e is None:
        c = crit("c6","Low / no debt","neutral",0.5,"D/E ratio unavailable",1.5)
    elif d2e <= 0.3:
        c = crit("c6","Low / no debt","pass",1.0,f"D/E = {_f(d2e)} — very low leverage",1.5)
    elif d2e <= 0.8:
        c = crit("c6","Low / no debt","neutral",0.5,f"D/E = {_f(d2e)} — moderate debt",1.5)
    else:
        c = crit("c6","Low / no debt","fail",0.0,f"D/E = {_f(d2e)} — high leverage",1.5)
    criteria.append(c)

    # C7 — Cash increasing
    ci_ = d["cash_increasing"]
    if ci_ is None:
        c = crit("c7","Cash on BS increasing","neutral",0.5,"Insufficient cash data")
    elif ci_:
        c = crit("c7","Cash on BS increasing","pass",1.0,f"Cash: {_trend(s['cash_bs'])} Cr")
    else:
        c = crit("c7","Cash on BS increasing","fail",0.0,f"Cash declining: {_trend(s['cash_bs'])} Cr")
    criteria.append(c)

    # C8 — Fixed assets increasing
    fai = d["fixed_assets_increasing"]
    if fai is None:
        c = crit("c8","Fixed assets increasing","neutral",0.5,"Insufficient data",0.8)
    elif fai:
        c = crit("c8","Fixed assets increasing","pass",1.0,f"Fixed assets: {_trend(s['fixed_assets'])} Cr",0.8)
    else:
        c = crit("c8","Fixed assets increasing","fail",0.0,f"Fixed assets: {_trend(s['fixed_assets'])} Cr",0.8)
    criteria.append(c)

    # C9 — Negative NWC (bonus weight)
    nwc = d["nwc"]; nwc_neg = d["nwc_negative"]
    if nwc_neg:
        c = crit("c9","Negative NWC (bargaining power)","pass",1.5,f"NWC = {_f(nwc)} Cr — strong supplier terms",1.0)
    else:
        c = crit("c9","Negative NWC (bargaining power)","neutral",0.5,f"NWC = {_f(nwc)} Cr — positive",1.0)
    criteria.append(c)

    # C10 — CFO positive & increasing (weight 2.0)
    cfo_pos = d["cfo_positive"]; cfo_inc = d["cfo_increasing"]; cfo_v = d["last_cfo"]
    if cfo_pos and cfo_inc:
        c = crit("c10","CFO positive & increasing","pass",1.0,f"CFO {_f(cfo_v)} Cr — {_trend(s['cfo'])} Cr",2.0)
    elif cfo_pos:
        c = crit("c10","CFO positive & increasing","neutral",0.5,f"CFO positive ({_f(cfo_v)} Cr) but not growing consistently",2.0)
    else:
        c = crit("c10","CFO positive & increasing","fail",0.0,f"CFO {_f(cfo_v)} Cr — negative operating cash flow",2.0)
    criteria.append(c)

    # C11 — CFI negative
    cfi_v = d["last_cfi"]
    if d["cfi_negative"]:
        c = crit("c11","CFI negative (investing)","pass",1.0,f"CFI = {_f(cfi_v)} Cr — actively investing in growth")
    else:
        c = crit("c11","CFI negative (investing)","neutral",0.5,f"CFI = {_f(cfi_v)} Cr — positive (possible asset sales)")
    criteria.append(c)

    # C12 — CFF
    cff_v = d["last_cff"]
    if cff_v is None:
        c = crit("c12","CFF: debt repayment or growth","neutral",0.5,"CFF data unavailable")
    elif cff_v < 0:
        c = crit("c12","CFF: debt repayment or growth","pass",1.0,f"CFF = {_f(cff_v)} Cr — net debt repayment")
    else:
        c = crit("c12","CFF: debt repayment or growth","neutral",0.5,f"CFF = {_f(cff_v)} Cr — raising capital (check if for growth)")
    criteria.append(c)

    # C13 — ROE > ROCE (weight 1.5)
    roe = d["roe"]; roce = d["roce"]
    if roe is None or roce is None:
        c = crit("c13","ROE > ROCE","neutral",0.5,f"ROE={_f(roe,'%')} ROCE={_f(roce,'%')}",1.5)
    elif roe > roce:
        c = crit("c13","ROE > ROCE","pass",1.0,f"ROE {_f(roe,'%')} > ROCE {_f(roce,'%')} — leverage working for shareholders",1.5)
    else:
        c = crit("c13","ROE > ROCE","fail",0.0,f"ROE {_f(roe,'%')} ≤ ROCE {_f(roce,'%')} — leverage not adding value",1.5)
    criteria.append(c)

    # Weighted score
    tw = sum(c["weight"] for c in criteria)
    ws = sum(c["score"] * c["weight"] for c in criteria)
    pct = round((ws / tw) * 100, 1)
    passes   = sum(1 for c in criteria if c["result"] == "pass")
    fails    = sum(1 for c in criteria if c["result"] == "fail")
    neutrals = sum(1 for c in criteria if c["result"] == "neutral")

    if pct >= 78:   verdict, vc = "Strong buy candidate", "green"
    elif pct >= 58: verdict, vc = "Moderate — dig deeper", "amber"
    elif pct >= 40: verdict, vc = "Weak fundamentals", "red"
    else:           verdict, vc = "Avoid", "red"

    return {
        "symbol": data["symbol"],
        "name": data["name"],
        "sector": data.get("sector", ""),
        "screener_url": data["url"],
        "score_pct": pct,
        "passes": passes, "fails": fails, "neutrals": neutrals,
        "verdict": verdict, "verdict_color": vc,
        "criteria": criteria,
        "top_ratios": data.get("top_ratios", {}),
        "benchmark": bench,
    }
