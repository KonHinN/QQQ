"""
oos_validate.py — Out-of-sample verdict harness for the pre-registered claims (HANDOFF §6.5-6.6).

    python oos_validate.py <csv_path> <label>
    e.g. python oos_validate.py ..\\QQQ_1min_2022_2024.csv QQQ_2022_24

Input CSV must match the Phase-1 format: columns timestamp_et (day-first %d/%m/%Y %H:%M),
open, high, low, close, volume, trade_count; extended hours included (premarket needed for V).

The harness NEVER re-tunes anything. Frozen spec under test:
  C1  gap ladder      runner rate falls from big-gap-down to big-gap-up quintile
  C2  up3 contraction 3 up closes -> runner rate collapses vs base
  C3  thrust->pause   big up t-2 + small t-1 -> trend-day lift
  C4  playbook        gap<=-0.35x prior range: buy 10:00, stop -1%, sell 13:30, 1 tick/side
  C5  PM check        playbook | open >=0.3% above PM low  vs  open on the PM low
Verdicts: CONFIRMED (effect present, same sign both halves, meaningful size) /
          WEAKENED (right sign, small or one-half) / REFUTED (absent or flipped).

Day hygiene is auto-detected: RTH bar count != 390 -> excluded from aggregates (reported).
Outputs: output/OOS_<label>_verdicts.md + tables/OOS_<label>_details.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from runners import build_frame
from premarket import premarket_daily

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TICK = 0.01
EVENT_THR = -0.35
ENTRY_T, EXIT_T, STOP_PCT = 30, 240, 1.0


# ---------------------------------------------------------------- ingest (auto-hygiene)
def load_oos(csv_path: Path):
    raw = ingest.load_raw(csv_path)
    rth = ingest.filter_rth(raw)
    counts = rth.groupby("date").size()
    bad = set(counts[counts != ingest.N_MIN].index)
    dates = sorted(counts.index)
    bad |= {dates[0], dates[-1]}                      # boundary days: prior/next session unknown
    flags = pd.DataFrame({"date": dates})
    flags["day_flag"] = np.where(flags.date.isin(bad), "excluded_auto", "full")
    flags["is_clean"] = ~flags.date.isin(bad)
    rth = rth.merge(flags, on="date", how="left")
    daily = ingest.derive_daily(rth).merge(flags, on="date", how="left")
    print(f"[oos] {csv_path.name}: {len(dates)} days, excluded {len(bad)} "
          f"(bar-count!={ingest.N_MIN} or boundary): {sorted(bad)[:8]}{'...' if len(bad) > 8 else ''}")
    return raw, rth, daily


def playbook_trades(m, d):
    pc = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
    pl = m[m.is_clean].pivot_table(index="date", columns="minute_index", values="low")
    ev = d[d.event].set_index("date")
    ev = ev[ev.index.isin(pc.index)]
    entry = pc.loc[ev.index, ENTRY_T]
    stop_px = entry * (1 - STOP_PCT / 100)
    stopped = pl.loc[ev.index, ENTRY_T:EXIT_T].min(axis=1) <= stop_px
    px = np.where(stopped, stop_px, pc.loc[ev.index, EXIT_T])
    bps = ((pd.Series(px, index=entry.index) - TICK) / (entry + TICK) - 1) * 1e4
    return ev, bps


def _verdict(ok_strong: bool, ok_weak: bool) -> str:
    return "CONFIRMED" if ok_strong else ("WEAKENED" if ok_weak else "REFUTED")


# ---------------------------------------------------------------- checks
def run(csv_path: Path, label: str):
    raw, rth, daily = load_oos(csv_path)
    d = build_frame(daily, rth)
    d["event"] = d.gap_over_prange <= EVENT_THR
    pmd = premarket_daily(raw)
    d = d.merge(pmd, on="date", how="left")
    d["pm_ok"] = (d.rth_open / d.pm_low - 1) * 100 >= 0.30

    rows, lines = [], [f"# OOS verdicts — {label}", ""]
    sub = d.dropna(subset=["thr_up_run"])
    base = sub.Y_up_trail.mean() * 100

    def halves(mask_col_frame, target="Y_up_trail"):
        out = []
        for h in ("H1", "H2"):
            s = mask_col_frame[mask_col_frame.half == h]
            out.append(s[target].astype(bool).mean() * 100 if len(s) >= 5 else np.nan)
        return out

    # C1 gap ladder
    s = sub.dropna(subset=["gap_over_prange"]).copy()
    s["q"] = pd.qcut(s.gap_over_prange, 5, labels=False, duplicates="drop")
    q1, q5 = s[s.q == 0], s[s.q == s.q.max()]
    r1, r5 = q1.Y_up_trail.mean() * 100, q5.Y_up_trail.mean() * 100
    h1 = [x - s[s.half == h].Y_up_trail.mean() * 100
          for h, x in zip(("H1", "H2"), [q1[q1.half == h].Y_up_trail.mean() * 100 for h in ("H1", "H2")])]
    strong = (r1 - base >= 5) and (r5 <= base) and all(np.nan_to_num(x) > 0 for x in h1)
    weak = (r1 > base) and (r5 < r1)
    v = _verdict(strong, weak)
    rows.append(dict(claim="C1_gap_ladder", verdict=v, detail=f"Q1 {r1:.1f}% / base {base:.1f}% / Q5 {r5:.1f}% (n={len(q1)}/{len(q5)})"))

    # C2 up3
    f = sub[sub.up3.astype("boolean").fillna(False)]
    r = f.Y_up_trail.mean() * 100 if len(f) >= 10 else np.nan
    strong = len(f) >= 10 and (r <= base - 10)
    weak = len(f) >= 10 and (r < base)
    rows.append(dict(claim="C2_up3_contraction", verdict=_verdict(strong, weak),
                     detail=f"up3 {r:.1f}% vs base {base:.1f}% (n={len(f)})"))

    # C3 thrust->pause (trend-day target)
    f = sub[sub.thrust_pause.astype("boolean").fillna(False)]
    bt = sub.Y_trend_up.mean() * 100
    r = f.Y_trend_up.mean() * 100 if len(f) >= 8 else np.nan
    strong = len(f) >= 8 and r >= bt * 1.5
    weak = len(f) >= 8 and r > bt
    rows.append(dict(claim="C3_thrust_pause", verdict=_verdict(strong, weak),
                     detail=f"trend-up {r if len(f)>=8 else float('nan'):.1f}% vs base {bt:.1f}% (n={len(f)})"))

    # C4 playbook (all events)
    ev, bps = playbook_trades(rth, d)
    hh = [bps[ev.half == h].median() for h in ("H1", "H2")]
    strong = bps.median() >= 10 and all(np.nan_to_num(x) > 0 for x in hh)
    weak = bps.median() > 0
    rows.append(dict(claim="C4_playbook_all", verdict=_verdict(strong, weak),
                     detail=f"med {bps.median():+.1f} bps, hit {(bps>0).mean()*100:.0f}%, H1/H2 {hh[0]:+.1f}/{hh[1]:+.1f} (n={len(bps)})"))

    # C5 PM check
    pm_ok = ev.pm_ok.fillna(False)
    b_ok, b_no = bps[pm_ok], bps[~pm_ok]
    if len(b_ok) >= 5 and len(b_no) >= 5:
        diff = b_ok.median() - b_no.median()
        strong = diff >= 15 and b_ok.median() >= 10
        weak = diff > 0
        det = f"bounced {b_ok.median():+.1f} (n={len(b_ok)}) vs not {b_no.median():+.1f} (n={len(b_no)})"
    else:
        strong = weak = False
        det = f"insufficient n ({len(b_ok)}/{len(b_no)})"
    rows.append(dict(claim="C5_pm_check", verdict=_verdict(strong, weak), detail=det))

    tab = pd.DataFrame(rows)
    lines += [f"Days: {int(d.date.nunique())} | clean {int(daily.is_clean.sum())} | "
              f"events {int(d.event.sum())} | base runner rate {base:.1f}%", ""]
    lines += [f"- **{r.claim}** -- **{r.verdict}** | {r.detail}" for r in tab.itertuples()]
    lines += ["", "_Frozen spec (no re-tuning). Methodology per HANDOFF §6. "
              "Verdict thresholds pre-set in oos_validate.py._"]
    TBL.mkdir(parents=True, exist_ok=True)
    tab.to_csv(TBL / f"OOS_{label}_details.csv", index=False)
    (OUT / f"OOS_{label}_verdicts.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return tab


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    run(Path(sys.argv[1]), sys.argv[2])
