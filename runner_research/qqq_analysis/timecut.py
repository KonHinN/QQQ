"""
timecut.py — Analysis O: cutting false pullbacks with a TIME filter on the level retest.

User hypothesis: a pullback that returns to the broken OR level LATE is not a pullback —
it is the reversal. Therefore: rest a limit at the level after the break, but CANCEL it if
unfilled by a cutoff time T. Late fills are the ones to refuse.

Three products (OR15 and OR30):
  O(a) P(trend | first-retest time bucket)  — does retest lateness predict failure? (descriptive)
  O(b) last-touch clock                     — on trend days, when does price touch the level for
       the LAST time? => "if it's still at the level after ~T, it's usually not a trend day."
  O(c) cancel-by-T grid (tradable, causal)  — limit at the level (0% rung) and at the 25% rung,
       fill only if touched by T ∈ {09:55,10:00,10:10,10:20,10:30,10:45,none}; exit 10:59,
       net 0.4 bps; H1/H2 per cell.

Outputs -> output/tables/O_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk
from or_break import _days, _break_event, COST_BPS, EXIT_IX, TREND_ATR

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TOL_ATR = 0.10
CUTS = [(25, "09:55"), (30, "10:00"), (40, "10:10"), (50, "10:20"),
        (60, "10:30"), (75, "10:45"), (89, "none")]
RUNGS = [0, 25]          # % retracement of the resting limit


def collect(m, w):
    rows = []
    for date, g in _days(m):
        ev = _break_event(g, w)
        if ev is None:
            continue
        atr = g.atr.median()
        s, t0 = ev["side"], ev["t"]
        orh, orl = ev["orh"], ev["orl"]
        orr = orh - orl
        if orr <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        lvl = orh if s == 1 else orl
        c = g.close.values; lo = g.low.values; hi = g.high.values
        exit_px = c[EXIT_IX]
        trended = ((exit_px - lvl) * s / atr) >= TREND_ATR
        rec = dict(date=date, or_w=w, side=s, t_break=t0, trended=bool(trended))
        # touch times of the level (with tolerance), after the break bar
        tol = TOL_ATR * atr
        touches = [t for t in range(t0 + 1, EXIT_IX + 1)
                   if (lo[t] <= lvl + tol if s == 1 else hi[t] >= lvl - tol)]
        rec["first_retest_t"] = touches[0] if touches else np.nan
        rec["last_touch_t"] = touches[-1] if touches else np.nan
        # fills at each rung (limit price known at t0)
        for r in RUNGS:
            limit = lvl - s * (r / 100) * orr
            ft = None
            for t in range(t0 + 1, EXIT_IX):
                if (lo[t] <= limit) if s == 1 else (hi[t] >= limit):
                    ft = t
                    break
            rec[f"r{r}_fill_t"] = ft if ft is not None else np.nan
            if ft is not None:
                rec[f"r{r}_pnl"] = round(float(((exit_px - limit) * s / limit) * 1e4 - COST_BPS), 2)
        rows.append(rec)
    return pd.DataFrame(rows)


def retest_time_outcome(df, w):
    """O(a): P(trend | first retest time bucket) + fill pnl by bucket (descriptive)."""
    sub = df[df.first_retest_t.notna()].copy()
    edges = [0, 30, 45, 60, 75, 90]
    labs = ["<10:00", "10:00-10:14", "10:15-10:29", "10:30-10:44", "10:45+"]
    sub["bucket"] = pd.cut(sub.first_retest_t, bins=edges, labels=labs, right=False)
    rows = []
    for b, s in sub.groupby("bucket", observed=True):
        if len(s) < 8:
            continue
        pnl = s["r0_pnl"].dropna()
        rows.append(dict(or_window=w, retest_bucket=b, n_days=len(s),
                         p_trend_pct=round(s.trended.mean() * 100, 1),
                         fill_pnl_mean_bps=round(pnl.mean(), 2) if len(pnl) else np.nan))
    never = df[df.first_retest_t.isna()]
    rows.append(dict(or_window=w, retest_bucket="never retests", n_days=len(never),
                     p_trend_pct=round(never.trended.mean() * 100, 1),
                     fill_pnl_mean_bps=np.nan))
    return pd.DataFrame(rows)


def last_touch_table(df, w):
    rows = []
    for lbl, s in [("trended", df[df.trended]), ("failed", df[~df.trended])]:
        x = s.last_touch_t.dropna()
        rows.append(dict(or_window=w, outcome=lbl, n_days=len(x),
                         last_touch_med=_clk(int(x.median())),
                         q75=_clk(int(x.quantile(.75))), q90=_clk(int(x.quantile(.90)))))
    return pd.DataFrame(rows)


def cutoff_grid(df, w):
    rows = []
    for r in RUNGS:
        for T, tlab in CUTS:
            fills = df[(df[f"r{r}_fill_t"].notna()) & (df[f"r{r}_fill_t"] <= T)]
            x = fills[f"r{r}_pnl"].dropna()
            n = len(x)
            if n < 10:
                continue
            half = n // 2
            t_stat = x.mean() / (x.std() / np.sqrt(n)) if x.std() > 0 else np.nan
            rows.append(dict(or_window=w, rung_pct=r, cancel_after=tlab, n_trades=n,
                             hit_pct=round((x > 0).mean() * 100, 1),
                             mean_bps=round(x.mean(), 2), t_stat=round(t_stat, 2),
                             mean_H1=round(x.iloc[:half].mean(), 2),
                             mean_H2=round(x.iloc[half:].mean(), 2),
                             p_trend_given_fill_pct=round(fills.trended.mean() * 100, 1)))
    return pd.DataFrame(rows)


def abort_test(m, w, abort_after=60):
    """O(d): 25%-rung fills; exit early on the first LEVEL touch at/after `abort_after`
    (10:30) vs holding to 10:59. Verdict: aborting sells the pullback low — it hurts."""
    rows = []
    for date, g in _days(m):
        ev = _break_event(g, w)
        if ev is None:
            continue
        atr = g.atr.median()
        s, t0 = ev["side"], ev["t"]
        orh, orl = ev["orh"], ev["orl"]
        orr = orh - orl
        if orr <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        lvl = orh if s == 1 else orl
        c = g.close.values; lo = g.low.values; hi = g.high.values
        limit = lvl - s * 0.25 * orr
        ft = None
        for t in range(t0 + 1, EXIT_IX):
            if (lo[t] <= limit) if s == 1 else (hi[t] >= limit):
                ft = t
                break
        if ft is None:
            continue
        pnl_hold = ((c[EXIT_IX] - limit) * s / limit) * 1e4 - COST_BPS
        tol = TOL_ATR * atr
        pnl_ab = pnl_hold
        for t in range(max(ft + 1, abort_after), EXIT_IX):
            if (lo[t] <= lvl + tol) if s == 1 else (hi[t] >= lvl - tol):
                pnl_ab = ((c[t] - limit) * s / limit) * 1e4 - COST_BPS
                break
        rows.append((pnl_hold, pnl_ab))
    df = pd.DataFrame(rows, columns=["hold_1059", "abort_on_late_touch"])
    out = []
    half = len(df) // 2
    for col in df.columns:
        x = df[col]
        t = x.mean() / (x.std() / np.sqrt(len(x))) if x.std() > 0 else np.nan
        out.append(dict(or_window=w, exit_rule=col, n_trades=len(x),
                        hit_pct=round((x > 0).mean() * 100, 1),
                        mean_bps=round(x.mean(), 2), t_stat=round(t, 2),
                        mean_H1=round(x.iloc[:half].mean(), 2),
                        mean_H2=round(x.iloc[half:].mean(), 2)))
    return pd.DataFrame(out)


def run(write=True):
    m, d = load()
    res = {}
    a, b, cgrid, ab = [], [], [], []
    for w in (15, 30):
        df = collect(m, w)
        res[f"O_days_or{w}"] = df
        a.append(retest_time_outcome(df, w))
        b.append(last_touch_table(df, w))
        cgrid.append(cutoff_grid(df, w))
        ab.append(abort_test(m, w))
    res["O_retest_time_outcome"] = pd.concat(a, ignore_index=True)
    res["O_last_touch"] = pd.concat(b, ignore_index=True)
    res["O_cutoff_grid"] = pd.concat(cgrid, ignore_index=True)
    res["O_abort_test"] = pd.concat(ab, ignore_index=True)
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[timecut] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 240)
    r = run()
    print("\n=== O(a) P(trend | first retest time) ===")
    print(r["O_retest_time_outcome"].to_string(index=False))
    print("\n=== O(b) LAST touch of the level (when does the level go quiet?) ===")
    print(r["O_last_touch"].to_string(index=False))
    print("\n=== O(c) cancel-by-time grid (limit at level / 25% rung, exit 10:59, net) ===")
    print(r["O_cutoff_grid"].to_string(index=False))
