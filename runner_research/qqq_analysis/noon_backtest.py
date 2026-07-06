"""
noon_backtest.py — $100k equity-curve backtest of the noon-check B1 playbook on QQQ, 2018-2026.

RULES (B1, frozen after the DEV/VAL improvement pass — see OOS_PLAYBOOK_REPORT.md):
  Fire  : at 12:00 ET — LOD set before 10:00 AND still the LOD AND close > session VWAP
  Entry : BUY 12:00 close (+1 tick)
  Stop  : first 1-min CLOSE below session VWAP -> exit AT THAT CLOSE (pessimistic — not at the
          VWAP level itself, so fast drops fill worse than the trigger)
  Exit  : 15:57 close (-1 tick) if never stopped
RISK  :
  fixed-fractional r% of current equity; stop distance at entry = entry - VWAP(12:00);
  shares = risk$/dist capped at 4x equity intraday margin (the cap binds when entry is barely
  above VWAP); whole shares. Sweep r = 0.5 / 1.0 / 2.0.
  NOTE: risk-based sizing off the VWAP distance is a sizing DESIGN CHOICE layered on the
  validated signal — the signal was validated per-trade in bps, unsized.
DATA  : QQQ 2018-2024 (oos_data/) chained with QQQ_1min_1y_TH.csv (2025-06-30..2026-06-30).
        There is a data gap 2025-01..2025-06 (flat equity there). Benchmark: buy&hold RTH.

Outputs -> tables/NB_stats.csv, NB_trades.csv, NB_yearly.csv, output/noon_b1_data.json
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

from oos_playbooks import load_file

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
CHECK_T, FLAT_T = 150, 387
START_EQ = 100_000.0
LEV_CAP = 4.0
RISKS = (0.5, 1.0, 2.0)

FILES = [Path(f"../oos_data/QQQ_1min_{y}.csv") for y in range(2018, 2025)] + \
        [Path("../QQQ_1min_1y_TH.csv")]


def year_trades(csv_path: Path) -> tuple[pd.DataFrame, pd.Series]:
    minute, daily = load_file(csv_path)
    m = minute[minute.is_clean].sort_values(["date", "minute_index"])
    ok = m.groupby("date")["minute_index"].size() == 390
    m = m[m.date.isin(ok[ok].index)]
    pc = m.pivot_table(index="date", columns="minute_index", values="close")
    pv = m.pivot_table(index="date", columns="minute_index", values="vwap_rth")
    plm = m.pivot_table(index="date", columns="minute_index", values="lod_minute_sofar")
    fires = (plm[CHECK_T] < 30) & (pc[CHECK_T] > pv[CHECK_T])
    rows = []
    for dt in fires[fires].index:
        c, v = pc.loc[dt], pv.loc[dt]
        entry = float(c[CHECK_T]); vw0 = float(v[CHECK_T])
        exit_px, reason, exit_t = None, "flat", FLAT_T
        for t in range(CHECK_T + 1, FLAT_T + 1):
            if c[t] < v[t]:
                exit_px, reason, exit_t = float(c[t]), "stop", t
                break
        if exit_px is None:
            exit_px = float(c[FLAT_T])
        rows.append(dict(date=dt, entry=entry, stop_dist=max(entry - vw0, TICK),
                         exit=exit_px, reason=reason, exit_t=exit_t))
    closes = m.groupby("date")["close"].last()
    return pd.DataFrame(rows), closes


def simulate(trades: pd.DataFrame, risk_pct: float) -> pd.DataFrame:
    eq, led = START_EQ, []
    for _, t in trades.sort_values("date").iterrows():
        shares = int(min(eq * risk_pct / 100 / t.stop_dist, eq * LEV_CAP / t.entry))
        if shares < 1:
            continue
        pnl = shares * ((t.exit - t.entry) - 2 * TICK)
        eq += pnl
        led.append(dict(date=t.date, shares=shares, entry=t.entry, exit=t.exit,
                        reason=t.reason, notional=round(shares * t.entry, 0),
                        lev=round(shares * t.entry / (eq - pnl), 2),
                        pnl=round(pnl, 2), equity=round(eq, 2),
                        ret_R=round(pnl / ((eq - pnl) * risk_pct / 100), 2)))
    return pd.DataFrame(led)


def stats(led: pd.DataFrame, label: str, years: float) -> dict:
    eqs = pd.concat([pd.Series([START_EQ]), led.equity])
    dd = (eqs / eqs.cummax() - 1).min() * 100
    total = led.equity.iloc[-1] / START_EQ - 1
    cagr = ((1 + total) ** (1 / years) - 1) * 100
    yearly = led.assign(y=led.date.str[:4]).groupby("y").pnl.sum()
    return dict(config=label, n_trades=len(led), win_pct=round((led.pnl > 0).mean() * 100, 1),
                stop_pct=round((led.reason == "stop").mean() * 100, 1),
                avg_R=round(led.ret_R.mean(), 2), avg_lev=round(led.lev.mean(), 2),
                total_ret_pct=round(total * 100, 1), cagr_pct=round(cagr, 2),
                max_dd_pct=round(dd, 2), end_equity=round(led.equity.iloc[-1], 0),
                worst_trade=round(led.pnl.min(), 0), best_trade=round(led.pnl.max(), 0),
                neg_years=int((yearly < 0).sum()), n_years=len(yearly))


def run():
    all_tr, all_closes = [], []
    for p in FILES:
        tr, closes = year_trades(p)
        all_tr.append(tr); all_closes.append(closes)
        print(f"[{p.stem}] {len(tr)} trades")
    trades = pd.concat(all_tr, ignore_index=True).sort_values("date")
    closes = pd.concat(all_closes).sort_index()
    closes = closes[~closes.index.duplicated()]
    years = (pd.to_datetime(closes.index[-1]) - pd.to_datetime(closes.index[0])).days / 365.25

    bh = START_EQ * closes / closes.iloc[0]
    st_rows, curves = [], {}
    for r in RISKS:
        led = simulate(trades, r)
        st_rows.append(stats(led, f"B1 @{r:g}% risk", years))
        if r == 1.0:
            led.to_csv(TBL / "NB_trades.csv", index=False)
            curves["1%"] = led
    st_rows.append(dict(config="QQQ buy & hold (RTH)", n_trades=1, win_pct=np.nan,
                        stop_pct=np.nan, avg_R=np.nan, avg_lev=1.0,
                        total_ret_pct=round((bh.iloc[-1] / START_EQ - 1) * 100, 1),
                        cagr_pct=round(((bh.iloc[-1] / START_EQ) ** (1 / years) - 1) * 100, 2),
                        max_dd_pct=round((bh / bh.cummax() - 1).min() * 100, 2),
                        end_equity=round(bh.iloc[-1], 0),
                        worst_trade=np.nan, best_trade=np.nan, neg_years=np.nan, n_years=np.nan))
    st = pd.DataFrame(st_rows)
    st.to_csv(TBL / "NB_stats.csv", index=False)

    led = curves["1%"]
    yearly = led.assign(y=led.date.str[:4]).groupby("y").agg(
        n=("pnl", "size"), pnl=("pnl", "sum"),
        win_pct=("pnl", lambda x: round((x > 0).mean() * 100, 1))).round(0).reset_index()
    yearly.to_csv(TBL / "NB_yearly.csv", index=False)

    # data for the chart page: equity stepped onto the daily date axis
    eq_by_date = led.set_index("date").equity
    eq_path, cur = [], START_EQ
    for dt in closes.index:
        if dt in eq_by_date.index:
            cur = float(eq_by_date.loc[dt])
        eq_path.append(round(cur, 0))
    (OUT / "noon_b1_data.json").write_text(json.dumps(dict(
        dates=list(closes.index), system=eq_path,
        bh=[round(x, 0) for x in bh.tolist()],
        stats=st.to_dict("records"), yearly=yearly.to_dict("records"))))
    return st, yearly, led


if __name__ == "__main__":
    st, yearly, led = run()
    from tabulate import tabulate as tb
    print("\n=== $100k noon-check B1 backtest — QQQ 2018-01 .. 2026-06 ===")
    print(tb(st, headers="keys", showindex=False))
    print("\n=== yearly ledger @1% ===")
    print(tb(yearly, headers="keys", showindex=False))
