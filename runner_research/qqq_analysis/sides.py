"""
sides.py — Analysis Q: the OR-break playbook split by side (LONG up-breaks vs SHORT down-breaks).

Computed by conditioning the M/N/P per-day tables on `side` — no new simulation, same rules:
  * geometry symmetry: trend rate, extension, max retracement, health meter per side
  * 25%-rung ladder per side
  * full rule stack (25% rung, cancel 10:30, far-side stop, exit 10:59) per side
  * + the strong-drive filter per side
Everything with H1/H2. Outputs -> output/tables/Q_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
SIDES = [(1, "long_up_break"), (-1, "short_down_break")]


def _hstats(x: pd.Series):
    x = x.dropna()
    n = len(x)
    if n < 10:
        return None
    h = n // 2
    t = x.mean() / (x.std() / np.sqrt(n)) if x.std() > 0 else np.nan
    return dict(n_trades=n, hit_pct=round((x > 0).mean() * 100, 1),
                mean_bps=round(x.mean(), 2), t_stat=round(t, 2),
                mean_H1=round(x.iloc[:h].mean(), 2), mean_H2=round(x.iloc[h:].mean(), 2))


def run(write=True):
    res = {}
    summary, ladder, stack, depth = [], [], [], []
    for w in (15, 30):
        n = pd.read_csv(TBL / f"N_days_or{w}.csv")
        p = pd.read_csv(TBL / f"P_days_or{w}.csv")
        for s, lbl in SIDES:
            ns = n[n.side == s]
            tr = ns[ns.trended]
            summary.append(dict(
                or_window=w, side=lbl, n_break_days=len(ns),
                trend_to_11_pct=round(ns.trended.mean() * 100, 1),
                ext_med_atr=round(ns.ext_atr.median(), 2),
                trendday_max_retrace_med_pct=round(tr.max_ret_pct.median(), 1) if len(tr) > 8 else np.nan,
                full_traverse_pct=round((ns.max_ret_pct >= 100).mean() * 100, 1)))
            # ladder r25 per side
            st = _hstats(ns["r25_pnl"])
            if st:
                ladder.append(dict(or_window=w, side=lbl, rung_pct=25, **st))
            # rule stack with stop, per side (+ strong drive)
            ps = p[p.side == s]
            fills = ps[ps.filled & ps.pnl.notna()]
            st = _hstats(fills.pnl)
            if st:
                stack.append(dict(or_window=w, side=lbl, filter="none",
                                  p_offered_1R_pct=round(fills.offered_R.ge(1).mean() * 100, 1),
                                  p_stop_first_pct=round(fills.stop_first.astype(float).mean() * 100, 1),
                                  **st))
            hi = fills[fills.drive_abs_bps >= fills.drive_abs_bps.quantile(2 / 3)]
            st = _hstats(hi.pnl)
            if st:
                stack.append(dict(or_window=w, side=lbl, filter="strong drive (top tercile)",
                                  p_offered_1R_pct=round(hi.offered_R.ge(1).mean() * 100, 1),
                                  p_stop_first_pct=round(hi.stop_first.astype(float).mean() * 100, 1),
                                  **st))
            # health meter per side (OR15 only has enough n; compute anyway)
            for a, b, blab in [(0, 25, "0-25%"), (25, 50, "25-50%"), (50, 75, "50-75%"),
                               (75, 100, "75-100%"), (100, 1e9, ">100%")]:
                sub = ns[(ns.max_ret_pct >= a) & (ns.max_ret_pct < b)]
                if len(sub) >= 6:
                    depth.append(dict(or_window=w, side=lbl, bucket=blab, n_days=len(sub),
                                      p_trend_pct=round(sub.trended.mean() * 100, 1)))
    res["Q_side_summary"] = pd.DataFrame(summary)
    res["Q_side_ladder_r25"] = pd.DataFrame(ladder)
    res["Q_side_rule_stack"] = pd.DataFrame(stack)
    res["Q_side_health_meter"] = pd.DataFrame(depth)
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[sides] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 240)
    r = run()
    for k, v in r.items():
        print(f"\n=== {k} ===")
        print(v.to_string(index=False))
