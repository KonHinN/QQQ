"""
tqqq_real_backtest.py — $100k early-low-hold backtest on REAL TQQQ data (replaces synthetic 3x).

Signal (unchanged, causal, validated): read on QQQ — at 11:00: LOD before 10:00 & holds,
close>VWAP, session low > premarket low; skip big-body-yesterday & FOMC. ENTRY = MARKET at
11:00 (the look-ahead pullback entry stays retracted). STOP trigger = QQQ 1-min close < QQQ
session VWAP. FLAT 15:57. Execution = REAL TQQQ prices at the same minutes, 1 tick/side.

Also computes, per trade, the synthetic 3x return ((1+r_qqq)^3-1) to VALIDATE the earlier
synthetic assumption: mean gap, correlation, tracking error. Splits (detected empirically:
2018-05-24 3:1, 2021-01-21 2:1, 2022-01-13 2:1, 2025-11-20 2:1) are overnight events — they
do not touch intraday trades; the buy&hold benchmark uses split-adjusted closes.

Outputs -> tables/TQR_stats.csv / TQR_trades.csv / TQR_yearly.csv, output/tqr_data.json
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from upgrade_lab import firing_paths

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
E_ABS, FLAT_ABS = 90, 387
START = 100_000.0
DEPLOYS = (0.25, 0.50, 1.00)
QQQ_FILES = [f"../qqq_full/QQQ_1min_{y}.csv" for y in range(2018, 2027)]
TQ_FILES = [f"../tqqq_full/TQQQ_1min_{y}.csv" for y in range(2018, 2027)]
SPLITS = {"2018-05-24": 3.0, "2021-01-21": 2.0, "2022-01-13": 2.0, "2025-11-20": 2.0}


def load_tqqq():
    """date x minute_index close pivot (RTH, ffilled within day) + daily open/close."""
    pivs, dailies = [], []
    for f in TQ_FILES:
        raw = ingest.load_raw(Path(f))
        rth = ingest.filter_rth(raw)
        piv = (rth.pivot_table(index="date", columns="minute_index", values="close")
               .reindex(columns=np.arange(390)).ffill(axis=1))
        pivs.append(piv)
        dailies.append(pd.DataFrame(dict(cl=piv[389], op=rth.groupby("date").open.first())))
    return pd.concat(pivs), pd.concat(dailies).sort_index()


def run():
    tq, tqd = load_tqqq()
    rows = []
    for f in QQQ_FILES:
        for d in firing_paths(f):                      # FINAL playbook firing days (causal)
            dt = d["date"]
            if dt not in tq.index:
                continue
            cq, vq = d["c"], d["vw"]                   # QQQ path from 11:00, seg index 0..297
            tqrow = tq.loc[dt]
            if not np.isfinite(tqrow[E_ABS]):
                continue
            entry_t = float(tqrow[E_ABS])
            exit_seg = len(cq) - 1                     # default: flat at 15:57
            for t in range(1, len(cq)):
                if cq[t] < vq[t]:
                    exit_seg = t; break
            exit_t = float(tqrow[E_ABS + exit_seg])
            r_real = (exit_t - TICK) / (entry_t + TICK) - 1
            r_qqq = cq[exit_seg] / cq[0] - 1
            rows.append(dict(date=dt, year=int(d["year"]), r_real=r_real,
                             r_syn=(1 + r_qqq) ** 3 - 1 - 8e-4, r_qqq=r_qqq,
                             stopped=exit_seg < len(cq) - 1))
    tr = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # ---- synthetic validation
    diff_bps = (tr.r_real - tr.r_syn) * 1e4
    val = dict(n=len(tr), corr=round(float(np.corrcoef(tr.r_real, tr.r_syn)[0, 1]), 4),
               mean_gap_bps=round(diff_bps.mean(), 1), med_gap_bps=round(diff_bps.median(), 1),
               te_bps=round(diff_bps.std(), 1))

    # ---- $100k sim, deploy sweep
    years = (pd.to_datetime(tr.date.iloc[-1]) - pd.to_datetime(tr.date.iloc[0])).days / 365.25
    def sim(frac):
        eq = START; path = []
        for _, t in tr.iterrows():
            eq += eq * frac * t.r_real
            path.append(dict(date=t.date, equity=eq, r=t.r_real))
        return pd.DataFrame(path)
    def stats(c, label):
        eqs = pd.concat([pd.Series([START]), c.equity])
        dd = (eqs / eqs.cummax() - 1).min() * 100
        tot = c.equity.iloc[-1] / START - 1
        wins = c[c.r > 0].r; losses = c[c.r <= 0].r
        pf = wins.sum() / abs(losses.sum()) if len(losses) else np.inf
        sharpe = c.r.mean() / c.r.std() * np.sqrt(len(c) / years)
        streak = mx = 0
        for r in c.r: streak = streak + 1 if r <= 0 else 0; mx = max(mx, streak)
        return dict(config=label, n=len(c), end_equity=round(c.equity.iloc[-1]),
                    total_ret_pct=round(tot * 100, 1),
                    cagr_pct=round(((1 + tot) ** (1 / years) - 1) * 100, 1),
                    max_dd_pct=round(dd, 1), win_pct=round((c.r > 0).mean() * 100, 1),
                    profit_factor=round(pf, 2),
                    avg_win_pct=round(wins.mean() * 100, 2), avg_loss_pct=round(losses.mean() * 100, 2),
                    expectancy_bps=round(c.r.mean() * 1e4, 0), sharpe=round(sharpe, 2),
                    best_pct=round(c.r.max() * 100, 1), worst_pct=round(c.r.min() * 100, 1),
                    max_consec_loss=mx)
    st_rows, curves = [], {}
    for fr in DEPLOYS:
        c = sim(fr); st_rows.append(stats(c, f"deploy {int(fr*100)}%")); curves[fr] = c

    # ---- split-adjusted buy&hold benchmark
    adj = tqd.copy(); factor = 1.0; adjs = []
    for dt in adj.index:
        if dt in SPLITS: factor *= SPLITS[dt]
        adjs.append(factor)
    adj["cl_adj"] = adj.cl * pd.Series(adjs, index=adj.index)
    bh = START * adj.cl_adj / adj.cl_adj.iloc[0]
    bh_dd = (bh / bh.cummax() - 1).min() * 100
    st_rows.append(dict(config="TQQQ buy&hold (real, split-adj)", n=len(bh),
                        end_equity=round(bh.iloc[-1]),
                        total_ret_pct=round((bh.iloc[-1] / START - 1) * 100, 1),
                        cagr_pct=round(((bh.iloc[-1] / START) ** (1 / years) - 1) * 100, 1),
                        max_dd_pct=round(bh_dd, 1), win_pct=np.nan, profit_factor=np.nan,
                        avg_win_pct=np.nan, avg_loss_pct=np.nan, expectancy_bps=np.nan,
                        sharpe=np.nan, best_pct=np.nan, worst_pct=np.nan, max_consec_loss=np.nan))
    st = pd.DataFrame(st_rows)

    yearly = tr.groupby("year").agg(
        n=("r_real", "size"),
        ret_pct=("r_real", lambda x: round(((1 + x).prod() - 1) * 100, 1)),
        mean_bps=("r_real", lambda x: round(x.mean() * 1e4, 0)),
        win_pct=("r_real", lambda x: round((x > 0).mean() * 100, 0))).reset_index()

    TBL.mkdir(parents=True, exist_ok=True)
    st.to_csv(TBL / "TQR_stats.csv", index=False); tr.to_csv(TBL / "TQR_trades.csv", index=False)
    yearly.to_csv(TBL / "TQR_yearly.csv", index=False)
    main = curves[1.00]
    bh_map = bh
    (OUT / "tqr_data.json").write_text(json.dumps(dict(
        dates=list(main.date), full=[round(v) for v in main.equity],
        half=[round(v) for v in curves[0.50].equity], qtr=[round(v) for v in curves[0.25].equity],
        bh=[round(float(bh_map.loc[d])) if d in bh_map.index else None for d in main.date],
        stats=st.replace({np.nan: None}).to_dict("records"), yearly=yearly.to_dict("records"),
        val=val, rdist=[round(v * 1e4) for v in tr.r_real])))
    from tabulate import tabulate as tb
    print(f"=== synthetic-vs-real validation === {val}")
    print(tb(st, headers="keys", showindex=False))
    print(tb(yearly, headers="keys", showindex=False))
    return st, yearly, val


if __name__ == "__main__":
    run()
