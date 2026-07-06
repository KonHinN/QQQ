"""
tradable.py — Analysis P: defining (and predicting) a "worth trading" OR-break day.

Two layers:
  P(a) DEFINITION — what magnitude makes the day worth it?
       D1: extension beyond the OR level at 10:59 >= k x day-ATR (sweep k) — descriptive scale.
       D2: R-multiple, trade-frame definition (recommended): entry at the 25% retracement rung,
           hard stop at the far side of the OR (risk = 0.75 x OR range). The day is TRADABLE if
           the trade offered >= 1R of favorable excursion before the stop was hit (and before
           10:59). This prices the day in the trade's own risk unit, not an abstract one.
  P(b) PREDICTION — features KNOWN AT BREAK TIME (strictly causal):
       or_range_atr_pre (OR width / ATR computed up to the break bar), drive strength,
       |gap|, first-15-min volume vs its own 10-day history, prior-day range, break time.
       Tercile -> P(tradable) with H1/H2 consistency.
  P(c) MONEY TEST — champion entry (25% rung, cancel unfilled 10:30, exit 10:59) with vs
       without the best causal filter.

Outputs -> output/tables/P_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk
from or_break import _days, _break_event, COST_BPS, EXIT_IX

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
RUNG = 0.25
CANCEL_T = 60                       # 10:30


def collect(m, d, w=15):
    daily = d[d.is_clean].sort_values("date").reset_index(drop=True)
    daily["prev_range"] = daily.day_range.shift(1)
    # first-15-min volume vs own trailing 10-day median (causal)
    v15 = (m[m.is_clean & (m.minute_index < 15)].groupby("date")["volume"].sum()
           .reindex(daily.date).reset_index(drop=True))
    v15_med = v15.shift(1).rolling(10, min_periods=5).median()
    aux = daily.set_index("date")
    aux["v15_ratio"] = (v15 / v15_med).values

    rows = []
    for date, g in _days(m):
        ev = _break_event(g, w)
        if ev is None or date not in aux.index:
            continue
        s, t0 = ev["side"], ev["t"]
        orh, orl = ev["orh"], ev["orl"]
        orr = orh - orl
        atr_day = g.atr.median()
        atr_pre = g.loc[g.minute_index <= t0, "atr"].median()       # causal at break time
        if orr <= 0 or not np.isfinite(atr_day) or atr_day <= 0 or not np.isfinite(atr_pre) or atr_pre <= 0:
            continue
        lvl = orh if s == 1 else orl
        c = g.close.values; lo = g.low.values; hi = g.high.values
        exit_px = c[EXIT_IX]
        ext_atr = (exit_px - lvl) * s / atr_day

        # D2 trade frame: entry 25% rung, stop far side, risk = 0.75*orr
        limit = lvl - s * RUNG * orr
        stop = orl if s == 1 else orh
        risk = 0.75 * orr
        ft = None
        for t in range(t0 + 1, EXIT_IX):
            if (lo[t] <= limit) if s == 1 else (hi[t] >= limit):
                ft = t
                break
        offered_R = np.nan; stop_first = np.nan; pnl = np.nan
        if ft is not None and ft <= CANCEL_T:
            mfe = 0.0; stop_first = False
            for t in range(ft, EXIT_IX + 1):
                if (lo[t] <= stop) if s == 1 else (hi[t] >= stop):
                    stop_first = True
                    break
                fav = (hi[t] - limit) if s == 1 else (limit - lo[t])
                mfe = max(mfe, fav)
            offered_R = mfe / risk
            if stop_first:
                pnl = ((stop - limit) * s / limit) * 1e4 - COST_BPS
            else:
                pnl = ((exit_px - limit) * s / limit) * 1e4 - COST_BPS

        rows.append(dict(
            date=date, side=s, t_break=t0, ext_atr=round(ext_atr, 3),
            or_range_atr_pre=round(orr / atr_pre, 2),
            drive_abs_bps=round(abs(c[t0] / g.open.iloc[0] - 1) * 1e4, 1),
            gap_abs_pct=round(abs(aux.loc[date, "gap_pct"]), 3),
            v15_ratio=round(float(aux.loc[date, "v15_ratio"]), 2),
            prev_range=round(float(aux.loc[date, "prev_range"]), 2),
            break_t=t0,
            filled=ft is not None and ft <= CANCEL_T,
            offered_R=round(float(offered_R), 2) if np.isfinite(offered_R) else np.nan,
            stop_first=stop_first, pnl=round(float(pnl), 2) if np.isfinite(pnl) else np.nan,
            tradable=bool(np.isfinite(offered_R) and offered_R >= 1.0),
        ))
    df = pd.DataFrame(rows)
    half = len(df) // 2
    df["half"] = ["H1"] * half + ["H2"] * (len(df) - half)
    return df


def definition_tables(df, w):
    d1 = []
    for k in (0.5, 1.0, 1.5, 2.0, 3.0):
        d1.append(dict(or_window=w, definition=f"ext >= {k} x dayATR at 10:59",
                       pct_of_break_days=round((df.ext_atr >= k).mean() * 100, 1)))
    fills = df[df.filled]
    d2 = pd.DataFrame([dict(
        or_window=w, n_fills=len(fills),
        p_offered_1R_pct=round((fills.offered_R >= 1).mean() * 100, 1),
        p_offered_2R_pct=round((fills.offered_R >= 2).mean() * 100, 1),
        p_stop_first_pct=round(fills.stop_first.astype(float).mean() * 100, 1),
        offered_R_med=round(fills.offered_R.median(), 2),
        risk_in_dayATR_med=round((0.75 * fills.or_range_atr_pre).median(), 2),
    )])
    return pd.DataFrame(d1), d2


def predictor_table(df, w):
    feats = ["or_range_atr_pre", "drive_abs_bps", "gap_abs_pct", "v15_ratio",
             "prev_range", "break_t"]
    fills = df[df.filled & df.offered_R.notna()].copy()
    rows = []
    for f in feats:
        x = fills[f].dropna()
        if len(x) < 30:
            continue
        q = x.quantile([1 / 3, 2 / 3]).values
        for lbl, mask in [("low", fills[f] <= q[0]), ("mid", (fills[f] > q[0]) & (fills[f] < q[1])),
                          ("high", fills[f] >= q[1])]:
            s = fills[mask]
            if len(s) < 10:
                continue
            h1 = s[s.half == "H1"]; h2 = s[s.half == "H2"]
            rows.append(dict(or_window=w, feature=f, tercile=lbl, n=len(s),
                             p_tradable_pct=round(s.tradable.mean() * 100, 1),
                             pnl_mean_bps=round(s.pnl.mean(), 2),
                             p_tradable_H1=round(h1.tradable.mean() * 100, 1) if len(h1) >= 5 else np.nan,
                             p_tradable_H2=round(h2.tradable.mean() * 100, 1) if len(h2) >= 5 else np.nan))
    return pd.DataFrame(rows)


def money_test(df, w):
    fills = df[df.filled & df.pnl.notna()].copy()
    out = []

    def stat(sub, lbl):
        x = sub.pnl.dropna()
        if len(x) < 10:
            return None
        half = len(x) // 2
        t = x.mean() / (x.std() / np.sqrt(len(x))) if x.std() > 0 else np.nan
        return dict(or_window=w, filter=lbl, n_trades=len(x),
                    hit_pct=round((x > 0).mean() * 100, 1),
                    mean_bps=round(x.mean(), 2), t_stat=round(t, 2),
                    mean_H1=round(x.iloc[:half].mean(), 2), mean_H2=round(x.iloc[half:].mean(), 2))
    out.append(stat(fills, "none (all fills, stop at far side)"))
    for f, direction in [("or_range_atr_pre", "low"), ("drive_abs_bps", "high"),
                         ("v15_ratio", "high"), ("prev_range", "high")]:
        x = fills[f].dropna()
        q = x.quantile(1 / 3 if direction == "low" else 2 / 3)
        sub = fills[fills[f] <= q] if direction == "low" else fills[fills[f] >= q]
        r = stat(sub, f"{f} {direction} tercile")
        if r:
            out.append(r)
    return pd.DataFrame([r for r in out if r])


def run(write=True):
    m, d = load()
    res = {}
    d1s, d2s, preds, moneys = [], [], [], []
    for w in (15, 30):
        df = collect(m, d, w)
        res[f"P_days_or{w}"] = df
        d1, d2 = definition_tables(df, w)
        d1s.append(d1); d2s.append(d2)
        preds.append(predictor_table(df, w))
        moneys.append(money_test(df, w))
    res["P_definition_sweep"] = pd.concat(d1s, ignore_index=True)
    res["P_trade_frame"] = pd.concat(d2s, ignore_index=True)
    res["P_predictors"] = pd.concat(preds, ignore_index=True)
    res["P_money_test"] = pd.concat(moneys, ignore_index=True)
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[tradable] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 240)
    r = run()
    print("\n=== P(a) D1 sweep: extension thresholds ===")
    print(r["P_definition_sweep"].to_string(index=False))
    print("\n=== P(a) D2 trade frame (entry 25% rung, stop far side) ===")
    print(r["P_trade_frame"].to_string(index=False))
    print("\n=== P(b) causal predictors of a tradable (>=1R) day ===")
    print(r["P_predictors"].to_string(index=False))
    print("\n=== P(c) money test: champion entry with stop, filtered ===")
    print(r["P_money_test"].to_string(index=False))
