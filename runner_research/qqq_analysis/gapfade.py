"""
gapfade.py — Analysis T: anatomy of the big-gap-down up-leg (deep dive on the S2 finding).

Event (pre-registered from S2 bottom-quintile edge): gap / prior-day-range <= -0.35.
On these days the trailing-P80 up-leg rate was ~36-43% vs ~27% base (both halves same sign).

T1. Timing — when is the bounce low set, when does the leg top out, LOD minute distribution.
T2. Economics — simple TIME-RULE longs on event days, costs = 1 tick/share/side:
      open->10:59, 10:00->10:59, open->close, 10:00->close ; each vs the same rule on
      ALL OTHER days (the matched control — a bounce "edge" must beat the base drift).
T3. System overlap — does the OR30 break->pullback system (R) already capture these days?
      Trade frequency + net bps on event vs non-event days.
T4. Median path from open (event vs rest) for charting.

Honesty: the event was FOUND on this year (S2). Everything here is in-sample anatomy;
the +32% drift year rewards buying weakness mechanically. OOS before any capital.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from runners import build_frame, TAB_DIR, OUT_DIR

TICK = 0.01
EVENT_THR = -0.35          # gap / prior-day range


def _paths(m: pd.DataFrame) -> pd.DataFrame:
    piv = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
           .reindex(columns=np.arange(390)).dropna())
    return piv.div(piv.iloc[:, 0], axis=0).sub(1).mul(100)     # % from open


def _net_bps(entry_px: pd.Series, exit_px: pd.Series) -> pd.Series:
    """Long net return in bps after 1 tick each side."""
    return ((exit_px - TICK) / (entry_px + TICK) - 1) * 1e4


def time_rules(m: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    piv_c = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
             .reindex(columns=np.arange(390)))
    piv_o = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="open")
             .reindex(columns=np.arange(390)))
    d = d.set_index("date")
    rules = {  # (entry px series, exit px series, label)
        "open_to_1059": (piv_o[0], piv_c[89]),
        "1000_to_1059": (piv_c[30], piv_c[89]),
        "open_to_close": (piv_o[0], piv_c[389]),
        "1000_to_close": (piv_c[30], piv_c[389]),
    }
    rows = []
    for lab, (e, x) in rules.items():
        bps = _net_bps(e, x).rename("bps").to_frame().join(d[["event", "half"]], how="inner").dropna()
        for grp, sub in (("event", bps[bps.event]), ("control", bps[~bps.event])):
            h1 = sub[sub.half == "H1"].bps; h2 = sub[sub.half == "H2"].bps
            rows.append(dict(rule=lab, group=grp, n=len(sub),
                             med_bps=round(sub.bps.median(), 1),
                             mean_bps=round(sub.bps.mean(), 1),
                             hit_pct=round((sub.bps > 0).mean() * 100, 1),
                             med_H1=round(h1.median(), 1), med_H2=round(h2.median(), 1),
                             same_sign=bool(np.sign(h1.median()) == np.sign(h2.median()))))
    return pd.DataFrame(rows)


def run():
    m = pd.read_parquet(OUT_DIR / "minute.parquet")
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    d = build_frame(daily, m)
    d["event"] = d.gap_over_prange <= EVENT_THR
    ev = d[d.event]

    # ---------------- T1 timing
    lod_min = daily.set_index("date").loc[ev.date, "lod_minute"]
    t1 = pd.DataFrame([dict(
        n_event=len(ev),
        med_gap_pct=round(ev.gap_pct.median(), 2),
        med_upleg_pct=round(ev.up_leg_pct.median(), 2),
        upleg_P80rate_pct=round(ev.Y_up_trail.mean() * 100, 1),
        base_P80rate_pct=round(d.dropna(subset=["thr_up_run"]).Y_up_trail.mean() * 100, 1),
        med_leg_low_min=int(ev.leg_low_min.median()),
        med_leg_high_min=int(ev.leg_high_min.median()),
        pct_low_before_1000=round((ev.leg_low_min <= 30).mean() * 100, 1),
        pct_low_before_1030=round((ev.leg_low_min <= 60).mean() * 100, 1),
        pct_lod_before_1030=round((lod_min <= 60).mean() * 100, 1),
        pct_close_above_open=round((ev.rth_close > ev.rth_open).mean() * 100, 1),
        pct_gap_filled=round((ev.rth_high >= ev.pdc).mean() * 100, 1))])

    # leg-low minute histogram (event days), 30-min bins
    bins = list(range(0, 391, 30))
    hist = (pd.cut(ev.leg_low_min, bins=bins, right=False).value_counts().sort_index()
            .rename("n").rename_axis("bin").reset_index())
    hist["bin"] = hist["bin"].astype(str)

    # ---------------- T2 time rules
    t2 = time_rules(m, d[["date", "event", "half"]].copy())

    # ---------------- T3 system overlap
    from system_backtest import build_trades
    from analytics import load
    m2, _ = load()
    tr = build_trades(m2)
    tr["net_bps"] = ((tr.exit - TICK * np.where(tr.side == "LONG", 1, -1))
                     / (tr.entry + TICK * np.where(tr.side == "LONG", 1, -1)) - 1) * 1e4
    tr.loc[tr.side == "SHORT", "net_bps"] = ((tr.entry - TICK) / (tr.exit + TICK) - 1)[tr.side == "SHORT"] * 1e4
    tr = tr.merge(d[["date", "event"]], on="date", how="left")
    rows = []
    for grp, sub in (("event", tr[tr.event == True]), ("non_event", tr[tr.event != True])):
        rows.append(dict(group=grp, n_trades=len(sub),
                         n_long=int((sub.side == "LONG").sum()),
                         med_bps=round(sub.net_bps.median(), 1),
                         mean_bps=round(sub.net_bps.mean(), 1),
                         hit_pct=round((sub.net_bps > 0).mean() * 100, 1)))
    n_ev_days = int(d.event.sum())
    rows.append(dict(group=f"event days w/ system trade: {int((tr.event == True).sum())}/{n_ev_days}",
                     n_trades=np.nan, n_long=np.nan, med_bps=np.nan, mean_bps=np.nan, hit_pct=np.nan))
    t3 = pd.DataFrame(rows)

    # ---------------- T4 median paths
    paths = _paths(m)
    ev_dates = set(ev.date)
    med_ev = paths.loc[paths.index.isin(ev_dates)].median()
    med_rest = paths.loc[~paths.index.isin(ev_dates)].median()
    t4 = pd.DataFrame({"minute": np.arange(390), "event_med_pct": med_ev.values,
                       "rest_med_pct": med_rest.values})

    t1.to_csv(TAB_DIR / "T_gapfade_timing.csv", index=False)
    hist.to_csv(TAB_DIR / "T_gapfade_leglow_hist.csv", index=False)
    t2.to_csv(TAB_DIR / "T_gapfade_timerules.csv", index=False)
    t3.to_csv(TAB_DIR / "T_gapfade_system_overlap.csv", index=False)
    t4.to_csv(TAB_DIR / "T_gapfade_paths.csv", index=False)
    return {"T1": t1, "hist": hist, "T2": t2, "T3": t3, "T4": t4}


if __name__ == "__main__":
    r = run()
    from tabulate import tabulate as tb
    print("=== T1 event timing ===");   print(tb(r["T1"].T, headers=["metric", "value"]))
    print("\n=== leg-low minute histogram (30-min bins) ==="); print(tb(r["hist"], headers="keys", showindex=False))
    print("\n=== T2 time rules, net bps (1 tick/side) ==="); print(tb(r["T2"], headers="keys", showindex=False))
    print("\n=== T3 OR30 system overlap ===");  print(tb(r["T3"], headers="keys", showindex=False))
