"""
system_backtest.py — Analysis R: equity-curve backtest of the OR-break playbook, $10,000 start.

SYSTEM (one trade/day max, day-trades only, from the M/N/O/P/Q research):
  Setup   : first CLOSE beyond the OR30 extreme by 10:30.
  LONG    : any up-break.  SHORT: down-break ONLY if |opening drive| >= trailing 66.7th
            percentile of prior break-days' |drive| (CAUSAL gate — expanding window, min 30
            prior break days; no shorts until warmed up).
  Entry   : limit at 25% retracement of the OR (price frozen at break time); cancel if
            unfilled by 10:30.
  Stop    : far side of the OR (risk/share = 0.75 x OR range). Same-bar ambiguity resolved
            PESSIMISTICALLY (if the fill bar also touches the stop, we are stopped).
  Exit    : 10:59 close, or the stop, whichever comes first.

RISK ("best idea" defaults):
  * fixed-fractional: risk 1.0% of CURRENT equity per trade (position sized by stop distance)
  * leverage cap 4x equity (US intraday margin); whole shares; skip if <1 share
  * costs: 1 tick ($0.01)/share each side (slippage+spread) — no commission (US retail)
  * sensitivity sweep: 0.5% / 1% / 2% risk

HONESTY: rules were SELECTED on this same year (in-sample). This backtest shows behaviour and
risk profile, not expected future returns. Phase-2 OOS remains the gate before capital.
Outputs -> output/tables/R_*.csv + output/equity_curve.html
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk
from or_break import _days, _break_event, EXIT_IX

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
START_EQ = 10_000.0
TICK = 0.01
LEV_CAP = 4.0
RUNG = 0.25
CANCEL_T = 60
DRIVE_Q = 2 / 3
MIN_WARM = 30


def build_trades(m):
    """Chronological candidate list with causal short gate."""
    cands = []
    for date, g in _days(m):
        ev = _break_event(g, 30)
        if ev is None:
            continue
        s, t0 = ev["side"], ev["t"]
        orh, orl = ev["orh"], ev["orl"]
        orr = orh - orl
        if orr <= 0:
            continue
        drive = abs(g.close.iloc[t0] / g.open.iloc[0] - 1)
        cands.append(dict(date=date, g=g, side=s, t0=t0, orh=orh, orl=orl, orr=orr, drive=drive))

    trades = []
    drives_seen = []
    for cnd in cands:
        take = True
        if cnd["side"] == -1:
            if len(drives_seen) < MIN_WARM:
                take = False
            else:
                thr = np.quantile(drives_seen, DRIVE_Q)
                take = cnd["drive"] >= thr
        drives_seen.append(cnd["drive"])
        if not take:
            continue
        g, s, t0 = cnd["g"], cnd["side"], cnd["t0"]
        lvl = cnd["orh"] if s == 1 else cnd["orl"]
        stop = cnd["orl"] if s == 1 else cnd["orh"]
        limit = lvl - s * RUNG * cnd["orr"]
        lo = g.low.values; hi = g.high.values; c = g.close.values
        ft = None
        for t in range(t0 + 1, min(CANCEL_T, EXIT_IX) + 1):
            if (lo[t] <= limit) if s == 1 else (hi[t] >= limit):
                ft = t
                break
        if ft is None:
            continue
        exit_px, exit_t, reason = None, None, None
        for t in range(ft, EXIT_IX + 1):                       # pessimistic: fill bar can stop us
            if (lo[t] <= stop) if s == 1 else (hi[t] >= stop):
                exit_px, exit_t, reason = stop, t, "stop"
                break
        if exit_px is None:
            exit_px, exit_t, reason = c[EXIT_IX], EXIT_IX, "time"
        trades.append(dict(date=cnd["date"], side="LONG" if s == 1 else "SHORT",
                           entry=limit, stop=stop, exit=exit_px, exit_reason=reason,
                           entry_t=_clk(ft), exit_t=_clk(exit_t),
                           stop_dist=abs(limit - stop),
                           raw_ret=(exit_px - limit) * s))
    return pd.DataFrame(trades)


def simulate(trades, risk_frac):
    eq = START_EQ
    rows = []
    for _, tr in trades.iterrows():
        risk_dollars = eq * risk_frac
        shares = int(risk_dollars // tr.stop_dist)
        max_shares = int((eq * LEV_CAP) // tr.entry)
        shares = min(shares, max_shares)
        if shares < 1:
            continue
        cost = shares * TICK * 2
        pnl = shares * tr.raw_ret - cost
        r_mult = tr.raw_ret / tr.stop_dist
        eq += pnl
        rows.append(dict(date=tr.date, side=tr.side, shares=shares,
                         notional=round(shares * tr.entry, 0),
                         leverage=round(shares * tr.entry / (eq - pnl), 2),
                         pnl=round(pnl, 2), r_multiple=round(r_mult, 3),
                         exit_reason=tr.exit_reason, equity=round(eq, 2)))
    return pd.DataFrame(rows)


def stats(led, label, n_days=247):
    if not len(led):
        return None
    eqs = pd.concat([pd.Series([START_EQ]), led.equity])
    rets = eqs.pct_change().dropna()
    peak = eqs.cummax()
    dd = (eqs / peak - 1).min()
    total = led.equity.iloc[-1] / START_EQ - 1
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else np.nan
    half = len(led) // 2
    return dict(config=label, n_trades=len(led),
                n_long=int((led.side == "LONG").sum()), n_short=int((led.side == "SHORT").sum()),
                final_equity=round(led.equity.iloc[-1], 0),
                total_return_pct=round(total * 100, 1),
                max_drawdown_pct=round(dd * 100, 1),
                sharpe=round(sharpe, 2),
                win_rate_pct=round((led.pnl > 0).mean() * 100, 1),
                avg_R=round(led.r_multiple.mean(), 3),
                stop_out_pct=round((led.exit_reason == "stop").mean() * 100, 1),
                avg_leverage=round(led.leverage.mean(), 2),
                pnl_H1=round(led.pnl.iloc[:half].sum(), 0),
                pnl_H2=round(led.pnl.iloc[half:].sum(), 0))


def equity_chart(led, d):
    """Small self-contained HTML with the equity curve vs buy&hold, SVG line chart."""
    dd = d[d.is_clean].sort_values("date").reset_index(drop=True)
    bh = START_EQ * (1 + (dd.rth_close / dd.rth_close.iloc[0] - 1))
    eq_by_date = led.set_index("date").equity
    eq_path = []
    cur = START_EQ
    for dt in dd.date:
        if dt in eq_by_date.index:
            cur = float(eq_by_date.loc[dt])
        eq_path.append(cur)
    W, H, padl, padb = 1000, 420, 70, 40
    all_v = eq_path + bh.tolist()
    vmin, vmax = min(all_v) * 0.99, max(all_v) * 1.01
    def xy(i, v):
        x = padl + i / (len(eq_path) - 1) * (W - padl - 20)
        y = (H - padb) - (v - vmin) / (vmax - vmin) * (H - padb - 20)
        return f"{x:.1f},{y:.1f}"
    p_sys = " ".join(xy(i, v) for i, v in enumerate(eq_path))
    p_bh = " ".join(xy(i, float(v)) for i, v in enumerate(bh))
    gl = "".join(f'<line x1="{padl}" y1="{(H-padb)-(v-vmin)/(vmax-vmin)*(H-padb-20):.0f}" x2="{W-20}" y2="{(H-padb)-(v-vmin)/(vmax-vmin)*(H-padb-20):.0f}" stroke="#1e2630"/>'
                 f'<text x="8" y="{(H-padb)-(v-vmin)/(vmax-vmin)*(H-padb-20)+4:.0f}" font-size="12" fill="#5c6773">${v/1000:.1f}k</text>'
                 for v in np.linspace(vmin, vmax, 6))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>OR playbook — equity curve</title>
<style>body{{background:#0b0e11;color:#c9d1d9;font-family:Consolas,monospace;padding:30px}}</style></head><body>
<h2 style="font-weight:600">OR-break playbook — $10,000 · 1% risk · 4x cap · one year (in-sample)</h2>
<svg viewBox="0 0 {W} {H}" style="max-width:1100px;width:100%">
{gl}
<polyline points="{p_bh}" fill="none" stroke="#5c6773" stroke-width="2" stroke-dasharray="6,4"/>
<polyline points="{p_sys}" fill="none" stroke="#26a69a" stroke-width="3"/>
<text x="{padl}" y="16" font-size="14" fill="#26a69a">system (day-trades only)</text>
<text x="{padl+260}" y="16" font-size="14" fill="#5c6773">QQQ buy &amp; hold (dashed)</text>
<text x="{padl}" y="{H-8}" font-size="12" fill="#5c6773">Jun 2025</text>
<text x="{W-120}" y="{H-8}" font-size="12" fill="#5c6773">Jun 2026</text>
</svg>
<p style="color:#7d8895;font-size:13px">Rules selected in-sample; indicative of behaviour, not future returns. Costs 1 tick/side. Shorts causally gated by trailing drive percentile.</p>
</body></html>"""
    (OUT / "equity_curve.html").write_text(html, encoding="utf-8")


def run(write=True):
    m, d = load()
    trades = build_trades(m)
    res = {"R_trade_candidates": trades.drop(columns=[]).copy()}
    all_stats = []
    for rf, lbl in [(0.005, "0.5% risk"), (0.01, "1% risk (recommended)"), (0.02, "2% risk")]:
        led = simulate(trades, rf)
        if rf == 0.01:
            res["R_ledger"] = led
            equity_chart(led, d)
        st = stats(led, lbl)
        if st:
            all_stats.append(st)
    # benchmark
    dd = d[d.is_clean].sort_values("date")
    bh_ret = dd.rth_close.iloc[-1] / dd.rth_close.iloc[0] - 1
    all_stats.append(dict(config="QQQ buy & hold (RTH only)", n_trades=1, n_long=1, n_short=0,
                          final_equity=round(START_EQ * (1 + bh_ret), 0),
                          total_return_pct=round(bh_ret * 100, 1),
                          max_drawdown_pct=round(((dd.rth_close / dd.rth_close.cummax()) - 1).min() * 100, 1),
                          sharpe=np.nan, win_rate_pct=np.nan, avg_R=np.nan,
                          stop_out_pct=np.nan, avg_leverage=1.0, pnl_H1=np.nan, pnl_H2=np.nan))
    res["R_system_stats"] = pd.DataFrame(all_stats)
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[system] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    r = run()
    print("\n=== R system stats ($10,000 start) ===")
    print(r["R_system_stats"].to_string(index=False))
    led = r["R_ledger"]
    print("\nledger tail:")
    print(led.tail(5).to_string(index=False))
    print("\nby side:")
    print(led.groupby("side").agg(n=("pnl", "size"), pnl_sum=("pnl", "sum"),
                                  win=("pnl", lambda x: round((x > 0).mean() * 100, 1))).to_string())
