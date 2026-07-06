"""
oos_improve.py — Disciplined improvement pass on the two playbooks.

PROTOCOL (so we don't burn the OOS data):
  DEV  = 2018-2021 (12 symbol-years)  — variants explored here
  VAL  = 2022-2024 ( 9 symbol-years)  — frozen after DEV, each variant scored once
  The 2025-26 in-sample year is NOT used for selection.

P1 OR30 variants (small, pre-registered from HANDOFF §6.3 leads — no wide grid):
  A0 frozen spec (baseline)             A1 longs only (kill the n=11-lineage short book)
  A2 tighter stop @75% OR retrace       A3 OR15 window (same everything else)
P2 noon-check variants:
  B0 frozen spec (baseline)             B1 drop the HOD target (VWAP stop, flat 15:57)
  B2 pure hold 12:00->15:57 (diagnostic: raw drift of fire days, no exit engine)

Scoring: per symbol-year net bps ledgers -> pooled med/mean bps, win%, and per-year
$10k @1% return for the OR30 family. Verdict = does the variant beat A0/B0 on DEV
AND hold sign on VAL?

    python oos_improve.py <data_dir>
Outputs -> tables/IMP_or30.csv, tables/IMP_noon.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
RUNG, CANCEL_T, EXIT_IX = 0.25, 60, 89
DRIVE_Q, MIN_WARM = 2 / 3, 30
CHECK_T, TEN_AM, FLAT_T = 150, 30, 387
DEV_YEARS = {"2018", "2019", "2020", "2021"}


# ---------------------------------------------------------------- OR30 parametric
def or30_trades(m, or_w=30, longs_only=False, stop_retrace=None):
    """system_backtest.build_trades with knobs. stop_retrace=None -> far side of OR;
    else stop at that fraction retracement of the OR (e.g. 0.75)."""
    cands = []
    for date, g in m[m.is_clean].groupby("date"):
        g = g.sort_values("minute_index").reset_index(drop=True)
        if len(g) != ingest.N_MIN:
            continue
        orh = g.loc[g.minute_index < or_w, "high"].max()
        orl = g.loc[g.minute_index < or_w, "low"].min()
        orr = orh - orl
        if orr <= 0:
            continue
        post = g[(g.minute_index >= or_w) & (g.minute_index <= 60)]
        up = post[post.close > orh]; dn = post[post.close < orl]
        t_up = up.minute_index.iloc[0] if len(up) else 999
        t_dn = dn.minute_index.iloc[0] if len(dn) else 999
        if t_up == 999 and t_dn == 999:
            continue
        s = 1 if t_up <= t_dn else -1
        t0 = int(min(t_up, t_dn))
        drive = abs(g.close.iloc[t0] / g.open.iloc[0] - 1)
        cands.append(dict(date=date, g=g, side=s, t0=t0, orh=orh, orl=orl, orr=orr, drive=drive))

    trades, drives_seen = [], []
    for cnd in cands:
        take = True
        if cnd["side"] == -1:
            if longs_only:
                take = False
            elif len(drives_seen) < MIN_WARM:
                take = False
            else:
                take = cnd["drive"] >= np.quantile(drives_seen, DRIVE_Q)
        drives_seen.append(cnd["drive"])
        if not take:
            continue
        g, s, t0 = cnd["g"], cnd["side"], cnd["t0"]
        lvl = cnd["orh"] if s == 1 else cnd["orl"]
        limit = lvl - s * RUNG * cnd["orr"]
        stop = (cnd["orl"] if s == 1 else cnd["orh"]) if stop_retrace is None \
            else lvl - s * stop_retrace * cnd["orr"]
        lo, hi, c = g.low.values, g.high.values, g.close.values
        ft = None
        for t in range(t0 + 1, min(CANCEL_T, EXIT_IX) + 1):
            if (lo[t] <= limit) if s == 1 else (hi[t] >= limit):
                ft = t; break
        if ft is None:
            continue
        exit_px, reason = None, None
        for t in range(ft, EXIT_IX + 1):                     # pessimistic: fill bar can stop us
            if (lo[t] <= stop) if s == 1 else (hi[t] >= stop):
                exit_px, reason = stop, "stop"; break
        if exit_px is None:
            exit_px, reason = c[EXIT_IX], "time"
        trades.append(dict(date=cnd["date"], side=s, entry=limit, stop_dist=abs(limit - stop),
                           raw_ret=(exit_px - limit) * s, reason=reason,
                           net_bps=((exit_px - limit) * s - 2 * TICK) / limit * 1e4))
    return pd.DataFrame(trades)


def or30_year_return(trades, risk_frac=0.01, start_eq=10_000.0, lev_cap=4.0):
    eq = start_eq
    for _, tr in trades.iterrows():
        shares = min(int(eq * risk_frac // tr.stop_dist), int(eq * lev_cap // tr.entry))
        if shares < 1:
            continue
        eq += shares * tr.raw_ret - shares * TICK * 2
    return (eq / start_eq - 1) * 100


# ---------------------------------------------------------------- noon parametric
def noon_trades(minute, use_target=True, use_vwap_stop=True):
    m = minute[minute.is_clean].sort_values(["date", "minute_index"])
    ok = m.groupby("date")["minute_index"].size() == ingest.N_MIN
    m = m[m.date.isin(ok[ok].index)]
    piv_c = m.pivot_table(index="date", columns="minute_index", values="close")
    piv_h = m.pivot_table(index="date", columns="minute_index", values="high")
    piv_v = m.pivot_table(index="date", columns="minute_index", values="vwap_rth")
    piv_lm = m.pivot_table(index="date", columns="minute_index", values="lod_minute_sofar")
    piv_rh = m.pivot_table(index="date", columns="minute_index", values="run_hod")
    fires = (piv_lm[CHECK_T] < TEN_AM) & (piv_c[CHECK_T] > piv_v[CHECK_T])
    rows = []
    for dt in fires[fires].index:
        entry = float(piv_c.loc[dt, CHECK_T])
        target = float(piv_rh.loc[dt, CHECK_T])
        c, h, v = piv_c.loc[dt], piv_h.loc[dt], piv_v.loc[dt]
        exit_px, reason = None, None
        for t in range(CHECK_T + 1, FLAT_T + 1):
            if use_vwap_stop and c[t] < v[t]:
                exit_px, reason = float(v[t]), "stop"; break
            if use_target and h[t] >= target:
                exit_px, reason = target, "target"; break
        if exit_px is None:
            exit_px, reason = float(c[FLAT_T]), "flat"
        rows.append(dict(date=dt, reason=reason,
                         net_bps=((exit_px - TICK) / (entry + TICK) - 1) * 1e4))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- scoring
def score(ledgers: dict[str, pd.DataFrame], year_ret: dict[str, float] | None, variant: str,
          split: str) -> dict:
    bps = pd.concat([l.net_bps for l in ledgers.values() if len(l)])
    out = dict(variant=variant, split=split, n_symbol_years=len(ledgers), n_trades=len(bps),
               med_bps=round(bps.median(), 1), mean_bps=round(bps.mean(), 1),
               win_pct=round((bps > 0).mean() * 100, 1),
               pos_years=int(sum(l.net_bps.sum() > 0 for l in ledgers.values())))
    if year_ret:
        r = pd.Series(year_ret)
        out |= dict(avg_year_ret_pct=round(r.mean(), 1), med_year_ret_pct=round(r.median(), 1),
                    worst_year_pct=round(r.min(), 1), best_year_pct=round(r.max(), 1))
    return out


def run(data_dir: Path):
    files = sorted(data_dir.glob("*.csv"))
    frames = {}
    for p in files:
        label = p.stem.replace("_1min", "")
        frames[label] = load_file(p)
        print(f"[load] {label}")

    OR_VARIANTS = {
        "A0_frozen": dict(),
        "A1_longs_only": dict(longs_only=True),
        "A2_stop75": dict(stop_retrace=0.75),
        "A3_or15": dict(or_w=15),
    }
    NOON_VARIANTS = {
        "B0_frozen": dict(),
        "B1_no_target": dict(use_target=False),
        "B2_pure_hold": dict(use_target=False, use_vwap_stop=False),
    }
    or_rows, noon_rows = [], []
    for split, keep in (("DEV", DEV_YEARS), ("VAL", None)):
        labels = [l for l in frames if (l[-4:] in keep) == True] if keep else \
                 [l for l in frames if l[-4:] not in DEV_YEARS]
        for vname, kw in OR_VARIANTS.items():
            led = {l: or30_trades(frames[l][0], **kw) for l in labels}
            yr = {l: or30_year_return(led[l]) for l in labels if len(led[l])}
            or_rows.append(score(led, yr, vname, split))
        for vname, kw in NOON_VARIANTS.items():
            led = {l: noon_trades(frames[l][0], **kw) for l in labels}
            noon_rows.append(score(led, None, vname, split))
        print(f"[{split}] done ({len(labels)} symbol-years)")

    or_tab, noon_tab = pd.DataFrame(or_rows), pd.DataFrame(noon_rows)
    TBL.mkdir(parents=True, exist_ok=True)
    or_tab.to_csv(TBL / "IMP_or30.csv", index=False)
    noon_tab.to_csv(TBL / "IMP_noon.csv", index=False)
    from tabulate import tabulate as tb
    print("\n=== OR30 variants (DEV=2018-21, VAL=2022-24; pooled QQQ+SPY+IWM) ===")
    print(tb(or_tab, headers="keys", showindex=False))
    print("\n=== Noon-check variants ===")
    print(tb(noon_tab, headers="keys", showindex=False))
    return or_tab, noon_tab


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "../oos_data"))
