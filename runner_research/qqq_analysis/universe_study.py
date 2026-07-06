"""
universe_study.py — Cross-sectional runner-precursor framework (the S battery, per US stock).

MISSION: what features known BEFORE today's open (t-1..t-3 candles, overnight gap, premarket)
predict that t0 develops a big intraday up-leg ("runner")? Tested per symbol, then aggregated
across the universe with sign tests — a claim is only real if it holds across MANY symbols,
not just in one ticker's history.

USAGE
    python universe_study.py <data_dir> [out_label]
    data_dir contains one CSV per symbol named  SYMBOL[_anything].csv  in the Phase-1 format:
    timestamp_et (day-first %d/%m/%Y %H:%M), open, high, low, close, volume[, trade_count],
    extended hours included, UNADJUSTED prices (dividend adjustment fabricates gaps!).

PER SYMBOL
    - day hygiene: RTH days with >= MIN_BARS of 390 minutes kept; grid reindexed, gaps
      forward-filled from prior close with volume 0 (documented choice — revisit for thin names)
    - liquidity gate: median daily dollar volume >= MIN_DOLLAR_VOL (runners in illiquid names
      are spread artifacts)
    - the S battery (runners.py): binary precursors x targets, causal trailing thresholds
    - gap ladder Q1/Q5 + premarket features if premarket bars exist

AGGREGATION (the cross-sectional null)
    For each feature: median lift across symbols, % of symbols with positive lift, two-sided
    sign-test p, and the same for the VOL CONTROL target (Y_wide). A directional claim must
    beat its own vol-control row — otherwise it is volatility clustering wearing a costume.

Outputs: tables/UNIV_<label>_per_symbol.csv, tables/UNIV_<label>_summary.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import binomtest

import ingest
from runners import build_frame, BINARY_FEATS
from premarket import premarket_daily

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
MIN_BARS = 350                 # of 390 RTH minutes; below -> day excluded
MIN_DOLLAR_VOL = 50e6          # median daily $ volume gate
MIN_CLEAN_DAYS = 120           # below -> symbol skipped entirely
EVENT_THR = -0.35


# ---------------------------------------------------------------- per-symbol ingest
def load_symbol(csv_path: Path):
    """Phase-1 ingest with a bar-count tolerance suitable for single stocks."""
    raw = ingest.load_raw(csv_path)
    rth = ingest.filter_rth(raw)
    counts = rth.groupby("date").size()
    dates = sorted(counts.index)
    bad = set(counts[counts < MIN_BARS].index) | {dates[0], dates[-1]}
    flags = pd.DataFrame({"date": dates})
    flags["is_clean"] = ~flags.date.isin(bad)
    flags["day_flag"] = np.where(flags.is_clean, "full", "excluded_auto")

    # reindex each clean day to the full 390-minute grid (ffill close, volume 0)
    full = []
    for dte, g in rth.groupby("date", sort=True):
        g = g.set_index("minute_index").reindex(np.arange(ingest.N_MIN))
        g["close"] = g["close"].ffill()
        for c in ("open", "high", "low"):
            g[c] = g[c].fillna(g["close"])
        g["volume"] = g["volume"].fillna(0)
        g["date"] = dte
        full.append(g.reset_index())
    rth = pd.concat(full, ignore_index=True).dropna(subset=["close"])
    rth = rth.merge(flags, on="date", how="left")
    daily = ingest.derive_daily(rth).merge(flags, on="date", how="left")
    return raw, rth, daily


# ---------------------------------------------------------------- per-symbol battery
def study_symbol(csv_path: Path) -> list[dict] | None:
    sym = csv_path.stem.split("_")[0].upper()
    try:
        raw, rth, daily = load_symbol(csv_path)
    except Exception as e:
        print(f"[universe] {sym}: LOAD FAILED ({e})")
        return None
    dv = (daily[daily.is_clean].rth_close * 0).add(
        rth[rth.is_clean].groupby("date").apply(
            lambda g: (g.close * g.volume).sum(), include_groups=False), fill_value=0)
    if daily.is_clean.sum() < MIN_CLEAN_DAYS or dv.median() < MIN_DOLLAR_VOL:
        print(f"[universe] {sym}: skipped (clean_days={int(daily.is_clean.sum())}, "
              f"med_$vol={dv.median()/1e6:.0f}M)")
        return None

    d = build_frame(daily, rth)
    d["event"] = d.gap_over_prange <= EVENT_THR
    pmd = premarket_daily(raw)
    d = d.merge(pmd, on="date", how="left")
    d["pm_ok"] = (d.rth_open / d.pm_low - 1) * 100 >= 0.30

    sub = d.dropna(subset=["thr_up_run"])
    rows = []
    for target in ("Y_up_trail", "Y_wide"):        # direction + its vol control, always paired
        base = sub[target].astype(bool).mean() * 100
        for feat in BINARY_FEATS:
            f = sub[feat].astype("boolean").fillna(False)
            n_f = int(f.sum())
            rate = sub.loc[f, target].astype(bool).mean() * 100 if n_f >= 8 else np.nan
            rows.append(dict(symbol=sym, feature=feat, target=target, n_f=n_f,
                             n_days=len(sub), base_pct=round(base, 1),
                             rate_pct=round(rate, 1) if n_f >= 8 else np.nan,
                             diff_pp=round(rate - base, 1) if n_f >= 8 else np.nan))
        # gap ladder extremes as pseudo-features
        s = sub.dropna(subset=["gap_over_prange"]).copy()
        s["q"] = pd.qcut(s.gap_over_prange, 5, labels=False, duplicates="drop")
        for qi, nm in ((0, "gap_dn_Q1"), (int(s.q.max()), "gap_up_Q5")):
            g = s[s.q == qi]
            rate = g[target].astype(bool).mean() * 100
            rows.append(dict(symbol=sym, feature=nm, target=target, n_f=len(g),
                             n_days=len(sub), base_pct=round(base, 1),
                             rate_pct=round(rate, 1), diff_pp=round(rate - base, 1)))
        # premarket-bounced (event days only, playbook-relevant)
        evd = sub[sub.event]
        if len(evd) >= 15:
            for nm, mask in (("pm_bounced|event", evd.pm_ok.fillna(False)),):
                g = evd[mask]
                if len(g) >= 8:
                    rate = g[target].astype(bool).mean() * 100
                    eb = evd[target].astype(bool).mean() * 100
                    rows.append(dict(symbol=sym, feature=nm, target=target, n_f=len(g),
                                     n_days=len(evd), base_pct=round(eb, 1),
                                     rate_pct=round(rate, 1), diff_pp=round(rate - eb, 1)))
    print(f"[universe] {sym}: ok ({int(daily.is_clean.sum())} clean days, "
          f"med_$vol={dv.median()/1e6:.0f}M)")
    return rows


# ---------------------------------------------------------------- aggregation
def aggregate(per: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (feat, target), g in per.dropna(subset=["diff_pp"]).groupby(["feature", "target"]):
        pos = int((g.diff_pp > 0).sum()); n = len(g)
        p = binomtest(pos, n, 0.5).pvalue if n >= 5 else np.nan
        rows.append(dict(feature=feat, target=target, n_symbols=n,
                         median_diff_pp=round(g.diff_pp.median(), 1),
                         pct_positive=round(pos / n * 100, 1),
                         sign_test_p=round(p, 4) if n >= 5 else np.nan,
                         median_n_f=int(g.n_f.median())))
    out = pd.DataFrame(rows).sort_values(["target", "median_diff_pp"],
                                         ascending=[True, False])
    return out


def run(data_dir: Path, label: str = "universe"):
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        print(f"no CSVs in {data_dir}"); return
    all_rows = []
    for p in csvs:
        r = study_symbol(p)
        if r:
            all_rows += r
    per = pd.DataFrame(all_rows)
    summ = aggregate(per)
    TBL.mkdir(parents=True, exist_ok=True)
    per.to_csv(TBL / f"UNIV_{label}_per_symbol.csv", index=False)
    summ.to_csv(TBL / f"UNIV_{label}_summary.csv", index=False)
    from tabulate import tabulate as tb
    print(f"\n=== universe summary ({per.symbol.nunique()} symbols) ===")
    print(tb(summ, headers="keys", showindex=False))
    print("\nREAD THE PAIRS: a feature is DIRECTIONAL only if its Y_up_trail row beats "
          "its own Y_wide row.\nOtherwise it forecasts volatility, not direction.")
    return per, summ


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    run(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "universe")
