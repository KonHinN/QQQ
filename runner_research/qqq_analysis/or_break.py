"""
or_break.py — Analysis M: morning OR-break continuation to 11:00 — timing / level / pullback.

User hypothesis: some OR breaks trend until ~11:00 (consistent with the structural clock:
the dominant leg terminates 10:00-11:00). Questions:
  (a) BASE RATES  — how often does the first OR break extend to 11:00? (by OR window, by side)
  (b) ENTRY TOURNAMENT — immediate vs confirmed vs hold vs OR-retest vs VWAP-pullback entries,
      all exiting at 10:59 close, net of 0.4 bps costs. No look-ahead: entries use only past bars.
  (c) PULLBACK GEOMETRY — on days that DID trend (>=1 ATR beyond the OR extreme at 10:59),
      how deep was the deepest pullback after the break (in day-ATR units, relative to the
      break level), did it retest the OR level, and WHEN did the pullback bottom occur?
      -> answers "what level to place the order and when to expect the entry".

Conventions: break = first CLOSE beyond the OR extreme after the OR window; day-ATR = median
1-min ATR(14); direction-signed arithmetic throughout; H1/H2 split reported for every rule.
Outputs -> output/tables/M_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk, N_MIN

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
COST_BPS = 0.4
EXIT_IX = 89                 # 10:59 close — inside the 10:00-11:00 turn window
RETEST_TOL_ATR = 0.10        # "touch" tolerance for level retests
TREND_ATR = 1.0              # trend-to-11 = >=1 day-ATR beyond the OR extreme at exit


def _days(m):
    for date, g in m[m.is_clean].groupby("date"):
        g = g.sort_values("minute_index").reset_index(drop=True)
        if len(g) == N_MIN:
            yield date, g


def _break_event(g, w):
    """First close beyond the OR extreme after the OR window. Returns None if no break by 10:30."""
    orh = g.loc[g.minute_index < w, "high"].max()
    orl = g.loc[g.minute_index < w, "low"].min()
    post = g[(g.minute_index >= w) & (g.minute_index <= 60)]      # break must happen by 10:30
    up = post[post.close > orh]
    dn = post[post.close < orl]
    t_up = up.minute_index.iloc[0] if len(up) else 999
    t_dn = dn.minute_index.iloc[0] if len(dn) else 999
    if t_up == 999 and t_dn == 999:
        return None
    if t_up <= t_dn:
        return dict(side=1, t=int(t_up), level=orh, orh=orh, orl=orl)
    return dict(side=-1, t=int(t_dn), level=orl, orh=orh, orl=orl)


def collect(m, w):
    rows = []
    for date, g in _days(m):
        ev = _break_event(g, w)
        if ev is None:
            continue
        atr = g.atr.median()
        if not np.isfinite(atr) or atr <= 0:
            continue
        s, t0, lvl = ev["side"], ev["t"], ev["level"]
        c = g.close.values; lo = g.low.values; hi = g.high.values; vw = g.vwap_rth.values
        entry_now = c[t0]
        exit_px = c[EXIT_IX]
        ext_atr = (exit_px - lvl) * s / atr                         # extension beyond level at exit
        trended = ext_atr >= TREND_ATR
        # deepest pullback AFTER the break bar, before exit, relative to the break level
        seg_lo = lo[t0 + 1:EXIT_IX + 1]; seg_hi = hi[t0 + 1:EXIT_IX + 1]
        adverse = (lvl - seg_lo) if s == 1 else (seg_hi - lvl)      # + = came back INSIDE the range
        pb_depth_atr = float(adverse.max() / atr) if len(adverse) else np.nan
        pb_when = int(t0 + 1 + adverse.argmax()) if len(adverse) else -1
        retested = pb_depth_atr >= -RETEST_TOL_ATR                  # came back to within tol of level

        # ---- entry rules (past-only information) ----
        entries = {"E1_immediate": (t0, entry_now)}
        if t0 + 1 <= EXIT_IX and (c[t0 + 1] - lvl) * s > 0:
            entries["E2_confirm2"] = (t0 + 1, c[t0 + 1])
        if t0 + 5 <= EXIT_IX and (c[t0 + 5] - lvl) * s > 0:
            entries["E3_hold5"] = (t0 + 5, c[t0 + 5])
        # E4 retest: first bar after break whose extreme comes back to within tol of the level
        for t in range(t0 + 1, EXIT_IX):
            touch = (lo[t] <= lvl + RETEST_TOL_ATR * atr) if s == 1 else (hi[t] >= lvl - RETEST_TOL_ATR * atr)
            if touch:
                entries["E4_or_retest"] = (t, c[t])
                break
        # E5 vwap pullback: first bar after break that touches session VWAP
        for t in range(t0 + 1, EXIT_IX):
            touch = (lo[t] <= vw[t]) if s == 1 else (hi[t] >= vw[t])
            if touch:
                entries["E5_vwap_pullback"] = (t, c[t])
                break

        rec = dict(date=date, or_w=w, side=s, t_break=t0, clock_break=_clk(t0),
                   level=lvl, atr=atr, exit_px=exit_px,
                   ext_atr=round(ext_atr, 3), trended=bool(trended),
                   pb_depth_atr=round(pb_depth_atr, 3), pb_when=pb_when,
                   retested=bool(retested))
        for name, (t, px) in entries.items():
            pnl = ((exit_px - px) * s / px) * 1e4 - COST_BPS
            mae_seg = lo[t:EXIT_IX + 1] if s == 1 else hi[t:EXIT_IX + 1]
            mae = ((px - mae_seg.min()) if s == 1 else (mae_seg.max() - px)) / atr
            rec[f"{name}_t"] = t
            rec[f"{name}_pnl"] = round(pnl, 2)
            rec[f"{name}_mae_atr"] = round(float(mae), 2)
        rows.append(rec)
    return pd.DataFrame(rows)


def _stats(x: pd.Series):
    x = x.dropna()
    n = len(x)
    if n < 8:
        return None
    t = x.mean() / (x.std() / np.sqrt(n)) if x.std() > 0 else np.nan
    half = n // 2
    return dict(n=n, hit_pct=round((x > 0).mean() * 100, 1), mean_bps=round(x.mean(), 2),
                med_bps=round(x.median(), 2), t_stat=round(t, 2),
                mean_H1=round(x.iloc[:half].mean(), 2), mean_H2=round(x.iloc[half:].mean(), 2))


def run(write=True):
    m, d = load()
    frames = {w: collect(m, w) for w in (5, 15, 30)}

    # (a) base rates
    base = []
    for w, df in frames.items():
        n_days = m[m.is_clean].date.nunique()
        for lbl, sub in [("all breaks", df), ("up breaks", df[df.side == 1]), ("down breaks", df[df.side == -1])]:
            base.append(dict(or_window=w, subset=lbl, n_break_days=len(sub),
                             break_rate_pct=round(len(sub) / n_days * 100, 1) if lbl == "all breaks" else np.nan,
                             trend_to_11_pct=round(sub.trended.mean() * 100, 1),
                             ext_med_atr=round(sub.ext_atr.median(), 2),
                             break_med_clock=_clk(int(sub.t_break.median()))))
    base_tbl = pd.DataFrame(base)

    # (b) entry tournament
    rules = ["E1_immediate", "E2_confirm2", "E3_hold5", "E4_or_retest", "E5_vwap_pullback"]
    tour = []
    for w, df in frames.items():
        for r in rules:
            st = _stats(df[f"{r}_pnl"]) if f"{r}_pnl" in df else None
            if st:
                fill = df[f"{r}_pnl"].notna().sum() / len(df) * 100
                mae = df[f"{r}_mae_atr"].median()
                tour.append(dict(or_window=w, entry=r, fill_rate_pct=round(fill, 1),
                                 mae_med_atr=round(mae, 2), **st))
    tour_tbl = pd.DataFrame(tour)

    # (c) pullback geometry on TRENDED days (descriptive, for level/timing placement)
    geo = []
    for w, df in frames.items():
        tr = df[df.trended]
        if len(tr) < 8:
            continue
        geo.append(dict(
            or_window=w, n_trend_days=len(tr),
            retest_or_level_pct=round(tr.retested.mean() * 100, 1),
            pb_depth_med_atr=round(tr.pb_depth_atr.median(), 2),
            pb_depth_q75_atr=round(tr.pb_depth_atr.quantile(.75), 2),
            straight_run_pct=round((tr.pb_depth_atr < -0.25).mean() * 100, 1),
            pb_bottom_med_clock=_clk(int(tr[tr.pb_when >= 0].pb_when.median())),
            pb_bottom_q25=_clk(int(tr[tr.pb_when >= 0].pb_when.quantile(.25))),
            pb_bottom_q75=_clk(int(tr[tr.pb_when >= 0].pb_when.quantile(.75))),
        ))
    geo_tbl = pd.DataFrame(geo)

    res = {"M_base_rates": base_tbl, "M_entry_tournament": tour_tbl,
           "M_pullback_geometry": geo_tbl}
    for w, df in frames.items():
        res[f"M_days_or{w}"] = df
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[or_break] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 240)
    r = run()
    print("\n=== M(a) base rates: does the first break trend to 11:00? ===")
    print(r["M_base_rates"].to_string(index=False))
    print("\n=== M(b) entry tournament (exit 10:59, net 0.4bps) ===")
    print(r["M_entry_tournament"].to_string(index=False))
    print("\n=== M(c) pullback geometry on trended days ===")
    print(r["M_pullback_geometry"].to_string(index=False))
