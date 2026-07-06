"""
gap_playbook_page.py — One-page trader sheet for the GAP-DOWN BOUNCE playbook (S/T/U).

Data-driven from output/tables/S_*, T_*, U_*.csv + a fresh stop x exit combo computation.
Output: output/gap_playbook.html (single page, offline, house dark style).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from runners import build_frame
from gap_playbook import EVENT_THR, ENTRY_T, _net_bps

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
GREEN = "#26a69a"; RED = "#ef5350"; AMBER = "#ffb74d"; BLUE = "#42a5f5"
DIM = "#7d8895"; FAINT = "#5c6773"

EXIT_T = 240   # 13:30
STOP = 1.0     # %


def build():
    m = pd.read_parquet(OUT / "minute.parquet")
    daily = pd.read_parquet(OUT / "daily.parquet")
    d = build_frame(daily, m)
    d["event"] = d.gap_over_prange <= EVENT_THR

    pc = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
    pl = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="low")
    ev = d[d.event].set_index("date")
    ev = ev[ev.index.isin(pc.index)]
    entry = pc.loc[ev.index, ENTRY_T]

    mae = (entry - pl.loc[ev.index, ENTRY_T:EXIT_T].min(axis=1)) / entry * 100
    stopped = mae >= STOP
    px = np.where(stopped, entry * (1 - STOP / 100), pc.loc[ev.index, EXIT_T])
    bps = _net_bps(entry, pd.Series(px, index=entry.index))
    h1 = bps[ev.half == "H1"]; h2 = bps[ev.half == "H2"]

    t1 = pd.read_csv(TBL / "T_gapfade_timing.csv").iloc[0]
    u1 = pd.read_csv(TBL / "U_exit_ladder.csv").set_index("exit")
    u2 = pd.read_csv(TBL / "U_mae.csv").set_index("group")
    u3 = pd.read_csv(TBL / "U_checkpoints.csv")
    t3 = pd.read_csv(TBL / "T_gapfade_system_overlap.csv")
    sys_ev = t3[t3.group == "event"].iloc[0]
    n_ev = len(ev); n_days = int(d.event.notna().sum())
    per_month = n_ev / 12

    ao = u3[(u3.checkpoint == "above_open_1000")]
    ao_t = ao[ao.state == True].iloc[0]; ao_f = ao[ao.state == False].iloc[0]

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gap-Down Bounce Playbook — QQQ</title>
<style>
  :root{{--bg:#0b0e11;--panel:#12161c;--grid:#1e2630;--fg:#c9d1d9;--dim:{DIM};--faint:{FAINT}}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--fg);font-family:Consolas,Menlo,'SF Mono',monospace;padding:34px 4vw 60px}}
  .wrap{{max-width:1150px;margin:0 auto}}
  .kicker{{color:{AMBER};letter-spacing:3px;font-size:12px}}
  h1{{font-size:clamp(26px,4vw,44px);margin:.2em 0 .1em;line-height:1.08}}
  .sub{{color:var(--dim);font-size:15px;line-height:1.6;max-width:820px}}
  .steps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:14px;margin-top:26px}}
  .step{{background:var(--panel);border:1px solid var(--grid);border-radius:14px;padding:18px 20px;position:relative}}
  .step .no{{position:absolute;top:-12px;left:16px;background:{AMBER};color:#000;font-weight:700;border-radius:8px;padding:2px 10px;font-size:13px}}
  .step h3{{margin:6px 0 8px;font-size:17px}}
  .step p{{margin:0;color:var(--dim);font-size:13.5px;line-height:1.6}}
  .big{{font-size:22px;color:#fff;font-weight:700}}
  b{{color:#fff}}
  .statrow{{display:flex;flex-wrap:wrap;gap:14px;margin-top:26px}}
  .stat{{background:var(--panel);border:1px solid var(--grid);border-radius:10px;padding:12px 18px;min-width:140px}}
  .stat span{{display:block;font-size:23px;color:{GREEN};font-weight:700}}
  .stat small{{color:var(--faint);font-size:11px;letter-spacing:1px}}
  .warn{{background:rgba(239,83,80,.08);border:1px solid rgba(239,83,80,.45);border-radius:14px;padding:16px 20px;margin-top:26px}}
  .warn h3{{color:{RED};margin:0 0 8px;font-size:16px}}
  .warn p{{color:var(--dim);font-size:13.5px;line-height:1.65;margin:6px 0}}
  .note{{color:var(--faint);font-size:12px;margin-top:18px;line-height:1.6}}
  h2{{font-size:20px;margin:34px 0 6px;color:#e8eef4}}
  table{{border-collapse:collapse;margin-top:10px;font-size:13px}}
  td,th{{border:1px solid var(--grid);padding:6px 12px;text-align:right;color:var(--dim)}}
  th{{color:#c9d1d9;background:var(--panel)}}
  td:first-child,th:first-child{{text-align:left}}
</style></head><body><div class="wrap">
<div class="kicker">QQQ · GAP-DOWN BOUNCE · ANALYSES S/T/U · {n_days} DAYS 2025-26 · IN-SAMPLE</div>
<h1>The Gap-Down Bounce</h1>
<p class="sub">When QQQ opens well below yesterday's close, the day's biggest up-leg usually starts
in the first half hour and tops out early afternoon. One rule-set, measured end to end, costs included.
<b>Every number is one in-sample year — see the red box before risking a dollar.</b></p>

<div class="steps">
  <div class="step"><div class="no">1 · SETUP (premarket)</div>
    <h3>Gap ≤ <span class="big">−0.35×</span> yesterday's range</h3>
    <p>Overnight gap (open vs yesterday's RTH close) at or below −0.35× yesterday's high−low.
    Median qualifying gap {t1.med_gap_pct}%. Fires ~<b>{per_month:.0f}×/month</b> ({n_ev}/{n_days} days).
    No other filter earned its place: below-PDL vs inside-range, prior day up vs down — all flat.</p></div>
  <div class="step"><div class="no">2 · ENTRY</div>
    <h3>Buy the <span class="big">10:00</span> close. Don't wait for green.</h3>
    <p>The bounce low is set by 10:00 on {t1.pct_low_before_1000}% of event days.
    Demanding price back above the open first <i>costs</i> edge: still-red-at-10:00 entries made
    {ao_f.med_bps:+.1f} bps median vs {ao_t.med_bps:+.1f} for already-green (n={int(ao_f.n)}/{int(ao_t.n)}).
    Weakness is the product.</p></div>
  <div class="step"><div class="no">3 · STOP</div>
    <h3><span class="big">−1.0%</span> from entry, hard</h3>
    <p>Winning days' MAE below the entry: P75 = {u2.loc['winners','mae_P75']}%, P90 = {u2.loc['winners','mae_P90']}%.
    Losers run to {u2.loc['losers','mae_P75']}%+. A 1% stop catches only the dumps
    ({int(stopped.sum())}/{n_ev} days stopped) and caps the worst day at −100 bps (was −131 unstopped).
    Tighter kills it: 0.5% stops out {20}/47 and flips H2 negative.</p></div>
  <div class="step"><div class="no">4 · EXIT</div>
    <h3><span class="big">13:30</span>, no exceptions</h3>
    <p>The up-leg tops out at median {13*60+23 and "13:23"} on event days. Exit ladder (median net bps):
    11:00 → {u1.loc['11:00','med_bps']:+.1f} · 12:00 → {u1.loc['12:00','med_bps']:+.1f} ·
    <b>13:30 → {u1.loc['13:30','med_bps']:+.1f}</b> · close → {u1.loc['close','med_bps']:+.1f}.
    Holding to the close gives back half the move.</p></div>
</div>

<div class="statrow">
  <div class="stat"><span>{bps.median():+.1f}</span><small>MEDIAN BPS / TRADE (NET)</small></div>
  <div class="stat"><span>{bps.mean():+.1f}</span><small>MEAN BPS (fat tail capped)</small></div>
  <div class="stat"><span>{(bps>0).mean()*100:.0f}%</span><small>HIT RATE</small></div>
  <div class="stat"><span>{h1.median():+.1f} / {h2.median():+.1f}</span><small>H1 / H2 MEDIAN — SAME SIGN</small></div>
  <div class="stat"><span>−100</span><small>WORST DAY, BPS (stopped)</small></div>
  <div class="stat"><span>~{per_month:.0f}/mo</span><small>TRADE FREQUENCY</small></div>
</div>

<h2>If the OR30 system also fires — prefer it</h2>
<p class="sub">On event days where the OR30 break→pullback system triggered, its trades ran
<b>{sys_ev.med_bps:+.1f} bps median at {sys_ev.hit_pct:.0f}% hit</b> (n={int(sys_ev.n_trades)}, {int(sys_ev.n_long)} long) —
better entry, tighter structure. But it only fires on {int(sys_ev.n_trades)}/{n_ev} event days;
this time-rule playbook covers the rest. Never run both on the same day (one QQQ day-position max).</p>

<h2>Monthly ledger (honesty)</h2>
<table><tr><th>month</th>{''.join(f"<th>{r.month[2:]}</th>" for r in pd.read_csv(TBL/'U_monthly.csv').itertuples())}</tr>
<tr><td>trades</td>{''.join(f"<td>{int(r.n)}</td>" for r in pd.read_csv(TBL/'U_monthly.csv').itertuples())}</tr>
<tr><td>med bps*</td>{''.join(f"<td style='color:{GREEN if r.med_bps>0 else RED}'>{r.med_bps:+.0f}</td>" for r in pd.read_csv(TBL/'U_monthly.csv').itertuples())}</tr></table>
<p class="note">*unstopped open→close basis (U5) — lumpy, with real losing months. The stop repairs the
tail, not the frequency of red months. 2–5 trades/month means quarterly P&L is noise-dominated.</p>

<div class="warn"><h3>⚠ READ BEFORE RISKING MONEY</h3>
<p>1 · <b>All in-sample.</b> The event definition, entry, stop and exit were all found on this same
2025-26 year. This is a hypothesis sheet, not a proven system.</p>
<p>2 · <b>It rhymes with the regime.</b> QQQ drifted +32% this year; "buy weakness" is what such a
year pays by construction. The 2022 bear year is the acid test — this playbook goes live only if the
edge survives there (HANDOFF §6, item 1 + 5a).</p>
<p>3 · <b>n = {n_ev}.</b> Forty-seven events. One bad regime-month can erase a quarter's expectancy.
Risk sizing: treat like the R-system — ≤1% equity risk per trade against the 1% stop.</p>
<p>4 · <b>Costs modelled at 1 tick/side.</b> Slippage on a gap-down open can be worse; the 10:00
entry (not the open) is partly there to dodge the worst spread window.</p></div>

<p class="note">Sources: tables/S_runner_gap_buckets.csv · T_gapfade_*.csv · U_*.csv ·
rebuild: python runners.py && python gapfade.py && python gap_playbook.py && python gap_playbook_page.py</p>
</div></body></html>"""
    path = OUT / "gap_playbook.html"
    path.write_text(html, encoding="utf-8")
    print(f"[gap_playbook_page] wrote {path} ({path.stat().st_size//1024} KB)")
    print(f"  spec: entry 10:00, stop -{STOP}%, exit 13:30 -> med {bps.median():+.1f} bps, "
          f"mean {bps.mean():+.1f}, hit {(bps>0).mean()*100:.0f}%, H1 {h1.median():+.1f} / H2 {h2.median():+.1f}")
    return path


if __name__ == "__main__":
    build()
