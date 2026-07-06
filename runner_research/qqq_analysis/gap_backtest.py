"""
gap_backtest.py — Analysis W: $100k equity-curve backtest of the gap-down bounce playbook.

RULES (from U/V, all causal at trade time):
  Setup   : gap <= -0.35 x prior-day range (open vs prior RTH close)
  PM check: (variant B) RTH open >= 0.3% above the premarket low (04:00-09:29)
  Entry   : BUY the 10:00 close (+1 tick cost)
  Stop    : entry - 1.0%; intrabar touch -> stopped (pessimistic), exit at stop
  Exit    : 13:30 close (-1 tick), or the stop, whichever first
RISK:
  fixed-fractional: risk r% of CURRENT equity per trade; shares = risk$ / (1% x entry)
  (=> notional ~ r/1% x equity; capped at 4x equity intraday margin); whole shares
  sweep r = 0.5 / 1.0 / 2.0 %; SUGGESTED = 1.0%
Benchmark: QQQ buy & hold (RTH close to close) on the same $100k.

HONESTY: rules selected on this same year across three refinement rounds. This shows the
risk/behaviour profile only. n(B)=19 — a single year cannot prove this. OOS is the gate.
Outputs -> tables/W_gap_backtest_stats.csv, W_gap_trades.csv, output/gap_equity_curve.html
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from runners import build_frame, TAB_DIR, OUT_DIR
from premarket import premarket_daily

START_EQ = 100_000.0
TICK = 0.01
EVENT_THR = -0.35
ENTRY_T, EXIT_T = 30, 240
STOP_PCT = 1.0
LEV_CAP = 4.0
RISKS = (0.5, 1.0, 2.0)
GREEN = "#26a69a"; AMBER = "#ffb74d"; DIM = "#7d8895"; RED = "#ef5350"


# ---------------------------------------------------------------- trades
def build_trade_list(with_pm_check: bool) -> pd.DataFrame:
    m = pd.read_parquet(OUT_DIR / "minute.parquet")
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    d = build_frame(daily, m)
    d["event"] = d.gap_over_prange <= EVENT_THR
    pmd = premarket_daily()
    d = d.merge(pmd, on="date", how="left")
    d["pm_ok"] = (d.rth_open / d.pm_low - 1) * 100 >= 0.30
    sel = d[d.event & (d.pm_ok if with_pm_check else True)].copy()

    pc = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
    pl = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="low")
    rows = []
    for dte in sel.date:
        if dte not in pc.index:
            continue
        entry = float(pc.loc[dte, ENTRY_T])
        stop_px = entry * (1 - STOP_PCT / 100)
        lows = pl.loc[dte, ENTRY_T:EXIT_T]
        hit = lows[lows <= stop_px]
        if len(hit):
            exit_px, reason = stop_px, "stop"
        else:
            exit_px, reason = float(pc.loc[dte, EXIT_T]), "time"
        rows.append(dict(date=dte, entry=entry, exit=exit_px, reason=reason,
                         net_bps=((exit_px - TICK) / (entry + TICK) - 1) * 1e4))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- simulate
def simulate(trades: pd.DataFrame, risk_pct: float) -> pd.DataFrame:
    eq = START_EQ
    led = []
    for _, t in trades.sort_values("date").iterrows():
        risk_dollar = eq * risk_pct / 100
        stop_dist = t.entry * STOP_PCT / 100
        shares = int(min(risk_dollar / stop_dist, eq * LEV_CAP / t.entry))
        if shares < 1:
            continue
        pnl = shares * ((t.exit - t.entry) - 2 * TICK)
        eq += pnl
        led.append(dict(date=t.date, shares=shares, entry=t.entry, exit=t.exit,
                        reason=t.reason, pnl=round(pnl, 2), equity=round(eq, 2),
                        ret_R=round(pnl / risk_dollar, 2)))
    return pd.DataFrame(led)


def stats(led: pd.DataFrame, label: str) -> dict:
    eqs = pd.concat([pd.Series([START_EQ]), led.equity])
    peak = eqs.cummax()
    dd = (eqs / peak - 1).min() * 100
    ret = (led.equity.iloc[-1] / START_EQ - 1) * 100
    return dict(config=label, n_trades=len(led),
                win_pct=round((led.pnl > 0).mean() * 100, 1),
                avg_R=round(led.ret_R.mean(), 2),
                stop_out_pct=round((led.reason == "stop").mean() * 100, 1),
                total_ret_pct=round(ret, 2), max_dd_pct=round(dd, 2),
                end_equity=round(led.equity.iloc[-1], 0),
                best_trade=round(led.pnl.max(), 0), worst_trade=round(led.pnl.min(), 0))


# ---------------------------------------------------------------- chart
def equity_chart(curves: dict, bh: pd.Series) -> str:
    W, H, padl, padr, padt, padb = 1100, 480, 74, 24, 30, 44
    all_dates = sorted(bh.index)
    n = len(all_dates)
    vals = [v for led in curves.values() for v in led.equity] + list(bh.values) + [START_EQ]
    vmin, vmax = min(vals) * 0.995, max(vals) * 1.005
    X = lambda i: padl + i / (n - 1) * (W - padl - padr)
    Y = lambda v: H - padb - (v - vmin) / (vmax - vmin) * (H - padt - padb)
    didx = {d: i for i, d in enumerate(all_dates)}
    o = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    for v in np.linspace(vmin, vmax, 6):
        o.append(f'<line x1="{padl}" y1="{Y(v):.0f}" x2="{W-padr}" y2="{Y(v):.0f}" stroke="#1e2630"/>')
        o.append(f'<text x="{padl-8}" y="{Y(v)+4:.0f}" font-size="12" fill="#5c6773" text-anchor="end">${v/1000:.0f}k</text>')
    for i in range(0, n, max(1, n // 10)):
        o.append(f'<text x="{X(i):.0f}" y="{H-14}" font-size="11" fill="#5c6773" text-anchor="middle">{all_dates[i][2:7]}</text>')
    pts = " ".join(f"{X(didx[d]):.1f},{Y(v):.1f}" for d, v in bh.items())
    o.append(f'<polyline points="{pts}" fill="none" stroke="{DIM}" stroke-width="1.6" opacity="0.8"/>')
    colors = {"all events @1%": AMBER, "PM-checked @1%": GREEN}
    for lab, led in curves.items():
        xs = [0.0] + [float(didx[d]) for d in led.date]
        ys = [START_EQ] + list(led.equity)
        # step-forward between trades
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{colors[lab]}" stroke-width="2.6"/>')
    ly = padt + 8
    for lab, col in list(colors.items()) + [("QQQ buy && hold (RTH)", DIM)]:
        o.append(f'<rect x="{padl+14}" y="{ly-9}" width="18" height="5" fill="{col}"/>')
        o.append(f'<text x="{padl+40}" y="{ly-3}" font-size="13" fill="{col}">{lab}</text>')
        ly += 22
    o.append("</svg>")
    return "".join(o)


def run():
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    dd = daily[daily.is_clean].sort_values("date")
    bh = (START_EQ * dd.set_index("date").rth_close / dd.rth_close.iloc[0])

    all_stats, curves = [], {}
    trades_out = []
    for with_pm, vlab in ((False, "all events"), (True, "PM-checked")):
        trades = build_trade_list(with_pm)
        for r in RISKS:
            led = simulate(trades, r)
            lab = f"{vlab} @{r:g}%"
            all_stats.append(stats(led, lab))
            if r == 1.0:
                curves[lab] = led
                led2 = led.copy(); led2["variant"] = vlab
                trades_out.append(led2)
    bh_ret = (bh.iloc[-1] / START_EQ - 1) * 100
    bh_dd = ((bh / bh.cummax()) - 1).min() * 100
    all_stats.append(dict(config="QQQ buy & hold (RTH)", n_trades=1, win_pct=np.nan,
                          avg_R=np.nan, stop_out_pct=np.nan,
                          total_ret_pct=round(bh_ret, 2), max_dd_pct=round(bh_dd, 2),
                          end_equity=round(bh.iloc[-1], 0), best_trade=np.nan, worst_trade=np.nan))
    st = pd.DataFrame(all_stats)
    tr = pd.concat(trades_out, ignore_index=True)
    st.to_csv(TAB_DIR / "W_gap_backtest_stats.csv", index=False)
    tr.to_csv(TAB_DIR / "W_gap_trades.csv", index=False)

    chart = equity_chart(curves, bh)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Gap-Down Bounce — $100k Backtest</title>
<style>body{{margin:0;background:#0b0e11;color:#c9d1d9;font-family:Consolas,Menlo,monospace;padding:28px 4vw}}
.wrap{{max-width:1150px;margin:0 auto}} h1{{font-size:26px;margin:0 0 4px}}
.kicker{{color:{AMBER};letter-spacing:3px;font-size:11px}}
.panel{{background:#12161c;border:1px solid #1e2630;border-radius:14px;padding:12px 16px;margin-top:14px}}
table{{border-collapse:collapse;margin-top:14px;font-size:13px;width:100%}}
td,th{{border:1px solid #1e2630;padding:6px 10px;text-align:right;color:#7d8895}}
th{{color:#c9d1d9;background:#12161c}} td:first-child{{text-align:left;color:#c9d1d9}}
.warn{{margin-top:14px;border:1px solid rgba(239,83,80,.5);background:rgba(239,83,80,.08);border-radius:10px;padding:10px 16px;color:#7d8895;font-size:12.5px}}
.warn b{{color:{RED}}}</style></head><body><div class="wrap">
<div class="kicker">QQQ · GAP-DOWN BOUNCE · $100,000 · 2025-06-30 → 2026-06-30 · IN-SAMPLE</div>
<h1>Playbook backtest — suggested risk 1% / trade</h1>
<div class="panel">{chart}</div>
<table><tr>{''.join(f'<th>{c}</th>' for c in st.columns)}</tr>
{''.join('<tr>' + ''.join(f'<td>{v if pd.notna(v) else "—"}</td>' for v in row) + '</tr>' for row in st.itertuples(index=False))}</table>
<div class="warn"><b>⚠ In-sample, one drift year, three refinement rounds; PM-checked n≈19.</b>
This chart shows the shape of the risk, not expected returns. OOS (2022–24) before capital.</div>
</div></body></html>"""
    (OUT_DIR / "gap_equity_curve.html").write_text(html, encoding="utf-8")
    print(f"[gap_backtest] wrote gap_equity_curve.html")
    return st


if __name__ == "__main__":
    st = run()
    from tabulate import tabulate as tb
    print(tb(st, headers="keys", showindex=False))
