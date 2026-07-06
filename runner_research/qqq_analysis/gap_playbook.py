"""
gap_playbook.py — Analysis U: playbook parameters for the gap-down bounce (event days from T).

Everything here parameterizes a LONG entered at the 10:00 close on event days
(gap <= -0.35 x prior-day range) — T2's only both-halves-healthy rule. Costs 1 tick/side.

U1. Exit ladder     — same entry, exits 11:00 / 12:00 / 13:30 / close (which exit earns?)
U2. MAE / stop      — adverse excursion below the 10:00 entry, winners vs losers -> stop depth
U3. Checkpoints     — causal state at entry time: above/below open at 10:00, already bounced
                      vs still falling -> conditional hit rates (early recognition of dump days)
U4. Subtypes        — gap below PDL vs inside prior range; prior day up vs down; event & up3
U5. Monthly ledger  — median bps by month (regime honesty)

All in-sample (event definition FOUND on this year). n=47 events; subtype cells are tiny —
report n with every number and treat cells < 15 as anecdotes.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

from runners import build_frame, TAB_DIR, OUT_DIR

TICK = 0.01
EVENT_THR = -0.35
ENTRY_T = 30                      # 10:00 close
EXITS = {"11:00": 90, "12:00": 150, "13:30": 240, "close": 389}


def _net_bps(e, x):
    return ((x - TICK) / (e + TICK) - 1) * 1e4


def run():
    m = pd.read_parquet(OUT_DIR / "minute.parquet")
    daily = pd.read_parquet(OUT_DIR / "daily.parquet")
    d = build_frame(daily, m)
    d["event"] = d.gap_over_prange <= EVENT_THR

    piv_c = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
             .reindex(columns=np.arange(390)))
    piv_l = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="low")
             .reindex(columns=np.arange(390)))
    piv_o = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="open")
             .reindex(columns=np.arange(390)))

    ev = d[d.event].set_index("date")
    ev = ev[ev.index.isin(piv_c.index)]
    entry = piv_c.loc[ev.index, ENTRY_T]
    op = piv_o.loc[ev.index, 0]

    # ---------------- U1 exit ladder
    rows = []
    for lab, t in EXITS.items():
        bps = _net_bps(entry, piv_c.loc[ev.index, t])
        h1 = bps[ev.half == "H1"]; h2 = bps[ev.half == "H2"]
        rows.append(dict(exit=lab, n=len(bps), med_bps=round(bps.median(), 1),
                         mean_bps=round(bps.mean(), 1),
                         hit_pct=round((bps > 0).mean() * 100, 1),
                         med_H1=round(h1.median(), 1), med_H2=round(h2.median(), 1),
                         same_sign=bool(np.sign(h1.median()) == np.sign(h2.median()))))
    u1 = pd.DataFrame(rows)

    # ---------------- U2 MAE below entry (10:00 -> close)
    lows_after = piv_l.loc[ev.index, ENTRY_T:389].min(axis=1)
    mae_pct = (entry - lows_after) / entry * 100
    pnl = _net_bps(entry, piv_c.loc[ev.index, 389])
    win = pnl > 0
    u2 = pd.DataFrame([dict(
        group="winners", n=int(win.sum()),
        mae_P50=round(mae_pct[win].median(), 2), mae_P75=round(mae_pct[win].quantile(.75), 2),
        mae_P90=round(mae_pct[win].quantile(.90), 2)),
        dict(group="losers", n=int((~win).sum()),
        mae_P50=round(mae_pct[~win].median(), 2), mae_P75=round(mae_pct[~win].quantile(.75), 2),
        mae_P90=round(mae_pct[~win].quantile(.90), 2))])
    # stop sweep: stop at -x% from entry (intrabar touch -> stopped, pessimistic)
    srow = []
    for stp in (0.3, 0.5, 0.75, 1.0, 1.5, np.inf):
        stopped = mae_pct >= stp if np.isfinite(stp) else pd.Series(False, index=mae_pct.index)
        px_exit = np.where(stopped, entry * (1 - (stp if np.isfinite(stp) else 0) / 100),
                           piv_c.loc[ev.index, 389])
        bps = _net_bps(entry, pd.Series(px_exit, index=entry.index))
        srow.append(dict(stop_pct=("none" if not np.isfinite(stp) else stp),
                         n_stopped=int(stopped.sum()), med_bps=round(bps.median(), 1),
                         mean_bps=round(bps.mean(), 1), hit_pct=round((bps > 0).mean() * 100, 1),
                         worst_bps=round(bps.min(), 0)))
    u2s = pd.DataFrame(srow)

    # ---------------- U3 causal checkpoints at/around entry
    chk = pd.DataFrame(index=ev.index)
    chk["above_open_1000"] = entry > op                       # bounced already
    chk["off_low_1000"] = (entry / piv_l.loc[ev.index, :ENTRY_T].min(axis=1) - 1) * 100 >= 0.30
    chk["red_first15"] = piv_c.loc[ev.index, 15] < op
    rows = []
    base_med = pnl.median(); base_hit = (pnl > 0).mean() * 100
    for c in chk.columns:
        for v in (True, False):
            sel = chk[c] == v
            if sel.sum() < 5:
                continue
            b = pnl[sel]
            rows.append(dict(checkpoint=c, state=v, n=int(sel.sum()),
                             med_bps=round(b.median(), 1), hit_pct=round((b > 0).mean() * 100, 1),
                             base_med=round(base_med, 1), base_hit=round(base_hit, 1)))
    u3 = pd.DataFrame(rows)

    # ---------------- U4 subtypes
    sub = pd.DataFrame(index=ev.index)
    sub["below_pdl"] = ev.rth_open < ev.pdl
    sub["prior_day_up"] = ev.ret_cc.shift(0).notna() & False  # placeholder replaced below
    prior_up = d.set_index("date").ret_cc.shift(1).reindex(ev.index) > 0
    sub["prior_day_up"] = prior_up
    sub["after_up3"] = d.set_index("date").up3.reindex(ev.index).astype("boolean").fillna(False)
    rows = []
    for c in sub.columns:
        for v in (True, False):
            sel = sub[c] == v
            if sel.sum() < 5:
                continue
            b = pnl[sel]
            rows.append(dict(split=c, state=v, n=int(sel.sum()),
                             med_bps=round(b.median(), 1), hit_pct=round((b > 0).mean() * 100, 1)))
    u4 = pd.DataFrame(rows)

    # ---------------- U5 monthly
    mon = pnl.groupby(pd.to_datetime(pnl.index).strftime("%Y-%m")).agg(["count", "median"])
    mon.columns = ["n", "med_bps"]
    u5 = mon.round(1).reset_index(names="month") if hasattr(mon.reset_index(), "columns") else mon
    u5 = mon.round(1).rename_axis("month").reset_index()

    u1.to_csv(TAB_DIR / "U_exit_ladder.csv", index=False)
    u2.to_csv(TAB_DIR / "U_mae.csv", index=False)
    u2s.to_csv(TAB_DIR / "U_stop_sweep.csv", index=False)
    u3.to_csv(TAB_DIR / "U_checkpoints.csv", index=False)
    u4.to_csv(TAB_DIR / "U_subtypes.csv", index=False)
    u5.to_csv(TAB_DIR / "U_monthly.csv", index=False)
    return {"U1": u1, "U2": u2, "U2s": u2s, "U3": u3, "U4": u4, "U5": u5}


if __name__ == "__main__":
    r = run()
    from tabulate import tabulate as tb
    for k in ("U1", "U2", "U2s", "U3", "U4", "U5"):
        print(f"\n=== {k} ===")
        print(tb(r[k], headers="keys", showindex=False))
