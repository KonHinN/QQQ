"""
tqqq_backtest.py — $100k backtest of the early-low-hold v2 playbook traded on TQQQ. QQQ 2018-2026.

TQQQ = 3x-daily QQQ. Signal is identical (the QQQ intraday structure; a 3x scale preserves the
low-hold / VWAP conditions). Execution is on TQQQ. Because the playbook is FLAT EVERY NIGHT, the
leveraged-ETF volatility decay (a multi-day-hold effect) does NOT apply — intraday a constant-3x
product delivers r_TQQQ = (1 + r_QQQ)^3 - 1 over the hold (variance drag over a few hours is a few
bps, folded into cost below).

Per trade (v2 entry: VWAP-pullback by 11:30 else 11:00; VWAP-close stop; flat 15:57):
  r_qqq   = exit/entry - 1        (gross, from the QQQ minute path)
  r_tqqq  = (1+r_qqq)^3 - 1       (3x intraday)
  net     = r_tqqq - COST_RT      COST_RT = 8 bps round-trip (TQQQ spread ~2-3 bps/side + slip +
                                  intraday variance-drag cushion; vs ~0.5 bps for QQQ)
$100k, one trade/day (non-overlapping): deploy fraction f of equity as TQQQ notional; equity
compounds. Sweep f = 25 / 50 / 100%. Benchmarks: same playbook on QQQ (v2, f=100%) and
TQQQ buy&hold (synthetic, close-to-close 3x, the decay-exposed comparison).

HONESTY: synthetic TQQQ (no real tick data) — real fills differ by tracking error + spread, which
COST_RT approximates conservatively. 3x = 3x the drawdown; sizing is the whole risk story here.
Output -> tables/TQQQ_stats.csv, TQQQ_trades.csv, output/tqqq_bt_data.json
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

from upgrade_lab import firing_paths, TICK, E, FLAT
from oos_playbooks import load_file


def load_file_daily(f):
    _, daily = load_file(Path(f))
    d = daily[daily.is_clean][["date", "rth_close"]].copy()
    return None, d

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
FILES = [f"../qqq_full/QQQ_1min_{y}.csv" for y in range(2018, 2027)]
START = 100_000.0
COST_RT = 8e-4          # TQQQ round-trip cost (fraction)
QQQ_COST_RT = 5e-5      # QQQ ~1 tick round trip on ~$400
LEV = 3
RISKS = (0.25, 0.50, 1.00)


def v2_trade(day) -> tuple[str, float]:
    """Return (date, gross QQQ return) for the v2-managed trade on a firing day."""
    c, lo, vw = day["c"], day["lo"], day["vw"]
    n = len(c)
    e_ix = 0
    for t in range(0, min(30, n)):            # VWAP pullback entry by 11:30
        if lo[t] <= vw[t]:
            e_ix = t; break
    entry = c[e_ix]
    exit_px = c[n - 1]
    for t in range(e_ix + 1, n):
        if c[t] < vw[t]:
            exit_px = c[t]; break
    return day["date"], day["year"], exit_px / entry - 1


def build():
    days = [d for f in FILES for d in firing_paths(f)]
    rows = []
    for d in days:
        dt, yr, rq = v2_trade(d)
        rt = (1 + rq) ** LEV - 1
        rows.append(dict(date=dt, year=int(yr), r_qqq=rq, r_tqqq=rt,
                         net_tqqq=rt - COST_RT, net_qqq=rq - QQQ_COST_RT))
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def sim(tr, col, frac):
    eq = START; curve = []
    for _, t in tr.iterrows():
        pnl = eq * frac * t[col]
        eq += pnl
        curve.append(dict(date=t.date, equity=eq, r=t[col]))
    return pd.DataFrame(curve)


def stats(curve, label, years):
    eqs = pd.concat([pd.Series([START]), curve.equity])
    dd = (eqs / eqs.cummax() - 1).min() * 100
    tot = curve.equity.iloc[-1] / START - 1
    cagr = ((1 + tot) ** (1 / years) - 1) * 100
    wins = (curve.r > 0).mean() * 100
    return dict(config=label, n=len(curve), end_equity=round(curve.equity.iloc[-1]),
                total_ret_pct=round(tot * 100, 1), cagr_pct=round(cagr, 1),
                max_dd_pct=round(dd, 1), win_pct=round(wins, 1),
                best_day_pct=round(curve.r.max() * 100, 1), worst_day_pct=round(curve.r.min() * 100, 1))


def run():
    tr = build()
    years = (pd.to_datetime(tr.date.iloc[-1]) - pd.to_datetime(tr.date.iloc[0])).days / 365.25
    rowss, curves = [], {}
    for f in RISKS:
        c = sim(tr, "net_tqqq", f)
        rowss.append(stats(c, f"TQQQ deploy {int(f*100)}%", years))
        curves[f"TQQQ {int(f*100)}%"] = c
    cq = sim(tr, "net_qqq", 1.0); rowss.append(stats(cq, "QQQ v2 deploy 100%", years))
    curves["QQQ 100%"] = cq

    # synthetic TQQQ buy&hold: 3x daily-reset compounding of QQQ close-to-close (decay-exposed)
    import ingest
    dailyc = []
    for f in FILES:
        _, daily = load_file_daily(f)
        dailyc.append(daily)
    dc = pd.concat(dailyc).sort_values("date")
    dc["r"] = dc.rth_close.pct_change()
    dc = dc.dropna()
    bh_eq = START; bh = []
    for _, r in dc.iterrows():
        bh_eq *= (1 + LEV * r.r); bh.append((r.date, bh_eq))
    bh = pd.DataFrame(bh, columns=["date", "equity"])
    bh_dd = (bh.equity / bh.equity.cummax() - 1).min() * 100
    rowss.append(dict(config="TQQQ buy&hold (synthetic)", n=len(bh),
                      end_equity=round(bh.equity.iloc[-1]),
                      total_ret_pct=round((bh.equity.iloc[-1] / START - 1) * 100, 1),
                      cagr_pct=round(((bh.equity.iloc[-1] / START) ** (1 / years) - 1) * 100, 1),
                      max_dd_pct=round(bh_dd, 1), win_pct=np.nan,
                      best_day_pct=np.nan, worst_day_pct=np.nan))
    st = pd.DataFrame(rowss)

    # synthetic TQQQ buy&hold (close-to-close 3x with daily reset -> decay exposed)
    st.to_csv(TBL / "TQQQ_stats.csv", index=False)
    tr.to_csv(TBL / "TQQQ_trades.csv", index=False)

    yearly = tr.assign(r=tr.net_tqqq).groupby("year").agg(
        n=("r", "size"), mean_bps=("r", lambda x: round(x.mean() * 1e4, 0)),
        ret_pct=("r", lambda x: round(((1 + x).prod() - 1) * 100, 1))).reset_index()

    # equity path on the daily date axis for the main curve (100% and 50% + QQQ)
    def path(curve):
        m = curve.set_index("date").equity
        return [round(float(m.loc[d])) for d in curve.date]
    main = curves["TQQQ 100%"]
    bh_map = bh.set_index("date").equity
    data = dict(dates=list(main.date), tqqq100=path(curves["TQQQ 100%"]),
                tqqq50=path(curves["TQQQ 50%"]), qqq=path(curves["QQQ 100%"]),
                bh=[round(float(bh_map.loc[d])) if d in bh_map.index else None for d in main.date],
                bh_maxdd=round(bh_dd, 1),
                stats=st.to_dict("records"), yearly=yearly.to_dict("records"),
                start=START)
    (OUT / "tqqq_bt_data.json").write_text(json.dumps(data))
    from tabulate import tabulate as tb
    print(f"=== TQQQ $100k backtest (early-low-hold v2, {len(tr)} trades, {years:.1f}y) ===")
    print(tb(st, headers="keys", showindex=False))
    print("\nper year (100% deploy):")
    print(tb(yearly, headers="keys", showindex=False))
    print(f"\nper-trade net: TQQQ {tr.net_tqqq.mean()*1e4:.0f} bps vs QQQ {tr.net_qqq.mean()*1e4:.1f} bps")
    return st, yearly


if __name__ == "__main__":
    run()
