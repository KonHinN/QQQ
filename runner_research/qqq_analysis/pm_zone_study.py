"""
pm_zone_study.py — Premarket-zone hypotheses, QQQ 2018-2026 (canonical qqq_full/).

H1  "price always tests or breaks the PM zone in the morning hour"
    -> touch/break rates of PM high/low in 09:30-10:30, PLUS the distance-matched control:
       a touch-probability-vs-distance curve built from arbitrary grid levels; if the PM edge's
       touch rate sits ON the curve, the edge is not special — distance explains everything
       (the Phase-1 PDH/PDL race-test discipline).
H2  "gap + PM extension predicts the morning": gap-up that extended up in PM -> morning pullback;
    gap-down that extended down -> morning rebound.
    -> 2x2 cells (gap sign x open position in PM range) vs open->10:29 return, 9 yearly samples.
H3  "tight PM zone -> false breakout in the morning hour"
    -> PM range vs trailing 60d quantiles (causal); false breakout = 1-min close beyond a PM edge
       in 09:30-10:30 that is back inside the zone (close) by 11:30. Tight vs mid vs wide.

All features causal at 09:30. Days need >=60 PM bars and 390 RTH bars; boundary days dropped.
Outputs -> tables/PMZ_*.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file
from premarket import premarket_daily

TBL = Path(__file__).resolve().parent / "output" / "tables"
FILES = [Path(f"../qqq_full/QQQ_1min_{y}.csv") for y in range(2018, 2027)]
MORN_END = 60          # exclusive: minutes 0..59 = 09:30-10:29
RECLAIM_T = 120        # back inside by minute 119 (11:29) => false breakout
GAP_THR = 0.15         # % — a "real" gap
EXT_HI, EXT_LO = 0.7, 0.3


def build_frame() -> pd.DataFrame:
    rows = []
    for f in FILES:
        raw = ingest.load_raw(f)
        minute, daily = load_file(f)
        m = minute[minute.is_clean]
        ok = m.groupby("date")["minute_index"].size() == 390
        m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
        ph = m.pivot_table(index="date", columns="minute_index", values="high")
        pl = m.pivot_table(index="date", columns="minute_index", values="low")
        pc = m.pivot_table(index="date", columns="minute_index", values="close")
        d = daily[daily.is_clean].set_index("date")
        pmd = premarket_daily(raw).set_index("date")
        for dt in ph.index:
            if dt not in pmd.index or pmd.loc[dt, "pm_bars"] < 60 or dt not in d.index:
                continue
            pm_h, pm_l = float(pmd.loc[dt, "pm_high"]), float(pmd.loc[dt, "pm_low"])
            o = float(d.loc[dt, "rth_open"]); pdc = d.loc[dt, "pdc"]
            if not np.isfinite(pdc) or pm_h <= pm_l:
                continue
            hi_m = ph.loc[dt, :MORN_END - 1]; lo_m = pl.loc[dt, :MORN_END - 1]
            cl_m = pc.loc[dt, :MORN_END - 1]
            rows.append(dict(
                date=dt, year=dt[:4], open=o,
                gap_pct=(o / pdc - 1) * 100,
                pm_range_pct=(pm_h - pm_l) / pdc * 100,
                pos=(o - pm_l) / (pm_h - pm_l),
                dist_hi=(pm_h / o - 1) * 100, dist_lo=(o / pm_l - 1) * 100,
                touch_hi=bool(hi_m.max() >= pm_h), touch_lo=bool(lo_m.min() <= pm_l),
                brk_hi=bool((cl_m > pm_h).any()), brk_lo=bool((cl_m < pm_l).any()),
                morn_ret=(float(pc.loc[dt, MORN_END - 1]) / o - 1) * 1e4,
                # for H3: reclaim after first-hour close-beyond
                back_in_hi=bool((cl_m > pm_h).any() and
                                (pc.loc[dt, int(cl_m[cl_m > pm_h].index[0]):RECLAIM_T - 1] <= pm_h).any()),
                back_in_lo=bool((cl_m < pm_l).any() and
                                (pc.loc[dt, int(cl_m[cl_m < pm_l].index[0]):RECLAIM_T - 1] >= pm_l).any()),
                # touch-vs-distance control samples (grid of synthetic levels, same day)
                max_up=(hi_m.max() / o - 1) * 100, max_dn=(1 - lo_m.min() / o) * 100))
        print(f"[{f.stem}] frame ok")
    df = pd.DataFrame(rows)
    # causal trailing PM-range quantiles
    q20 = df.pm_range_pct.rolling(60, min_periods=30).quantile(0.2).shift(1)
    q80 = df.pm_range_pct.rolling(60, min_periods=30).quantile(0.8).shift(1)
    df["pm_tight"] = df.pm_range_pct <= q20
    df["pm_wide"] = df.pm_range_pct >= q80
    return df


def h1(df: pd.DataFrame):
    inside = df[(df.pos >= 0) & (df.pos <= 1)]
    res = dict(
        n_days=len(df), open_inside_zone_pct=round(len(inside) / len(df) * 100, 1),
        touch_either_pct=round(((inside.touch_hi) | (inside.touch_lo)).mean() * 100, 1),
        touch_both_pct=round(((inside.touch_hi) & (inside.touch_lo)).mean() * 100, 1),
        break_either_pct=round(((inside.brk_hi) | (inside.brk_lo)).mean() * 100, 1))
    # distance-matched control: P(morning max_up >= d) as a function of d, from ALL days
    grid = np.arange(0.02, 1.51, 0.02)
    curve_up = {round(g, 2): (df.max_up >= g).mean() for g in grid}
    curve_dn = {round(g, 2): (df.max_dn >= g).mean() for g in grid}
    def expected(dist, curve):
        g = np.clip(np.round(dist / 0.02) * 0.02, 0.02, 1.5)
        return np.array([curve[round(x, 2)] for x in g])
    up = inside[inside.dist_hi > 0]; dn = inside[inside.dist_lo > 0]
    res["touch_hi_actual_pct"] = round(up.touch_hi.mean() * 100, 1)
    res["touch_hi_expected_pct"] = round(expected(up.dist_hi.values, curve_up).mean() * 100, 1)
    res["touch_lo_actual_pct"] = round(dn.touch_lo.mean() * 100, 1)
    res["touch_lo_expected_pct"] = round(expected(dn.dist_lo.values, curve_dn).mean() * 100, 1)
    return pd.DataFrame([res])


def h2(df: pd.DataFrame):
    cells = {
        "gapUP_extUP  (fade?)": (df.gap_pct >= GAP_THR) & (df.pos >= EXT_HI),
        "gapUP_extDN": (df.gap_pct >= GAP_THR) & (df.pos <= EXT_LO),
        "gapDN_extDN (rebound?)": (df.gap_pct <= -GAP_THR) & (df.pos <= EXT_LO),
        "gapDN_extUP": (df.gap_pct <= -GAP_THR) & (df.pos >= EXT_HI),
        "ALL_DAYS": pd.Series(True, index=df.index)}
    rows = []
    for lab, mask in cells.items():
        s = df[mask]
        yrs = []
        for y in sorted(df.year.unique()):
            sy = df[df.year == y]; syc = sy[mask.reindex(sy.index).fillna(False)]
            if len(syc) >= 8:
                yrs.append(syc.morn_ret.median() < sy.morn_ret.median()
                           if "UP_extUP" in lab else syc.morn_ret.median() > sy.morn_ret.median())
        rows.append(dict(cell=lab, n=len(s), med_morn_bps=round(s.morn_ret.median(), 1),
                         mean_morn_bps=round(s.morn_ret.mean(), 1),
                         pct_neg=round((s.morn_ret < 0).mean() * 100, 1),
                         yrs_hypothesis_dir=f"{sum(yrs)}/{len(yrs)}" if yrs else "-"))
    return pd.DataFrame(rows)


def h3(df: pd.DataFrame):
    inside = df[(df.pos >= 0) & (df.pos <= 1) & df.pm_tight.notna()]
    rows = []
    for lab, mask in (("tight(Q1)", inside.pm_tight), ("mid", ~(inside.pm_tight | inside.pm_wide)),
                      ("wide(Q5)", inside.pm_wide)):
        s = inside[mask.fillna(False)]
        broke = s[(s.brk_hi) | (s.brk_lo)]
        false_rt = ((broke.brk_hi & broke.back_in_hi) | (broke.brk_lo & broke.back_in_lo)).mean() * 100
        yrs = []
        for y in sorted(inside.year.unique()):
            sy = inside[inside.year == y]
            syb = sy[mask.reindex(sy.index).fillna(False) & ((sy.brk_hi) | (sy.brk_lo))]
            ally = sy[(sy.brk_hi) | (sy.brk_lo)]
            if len(syb) >= 8:
                fr = ((syb.brk_hi & syb.back_in_hi) | (syb.brk_lo & syb.back_in_lo)).mean()
                fa = ((ally.brk_hi & ally.back_in_hi) | (ally.brk_lo & ally.back_in_lo)).mean()
                yrs.append(fr > fa)
        rows.append(dict(pm_zone=lab, n=len(s),
                         break_rate_pct=round(((s.brk_hi) | (s.brk_lo)).mean() * 100, 1),
                         false_break_pct=round(false_rt, 1),
                         yrs_more_false_than_avg=f"{sum(yrs)}/{len(yrs)}" if yrs else "-"))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from tabulate import tabulate as tb
    df = build_frame()
    TBL.mkdir(parents=True, exist_ok=True)
    df.to_csv(TBL / "PMZ_daily.csv", index=False)
    t1, t2, t3 = h1(df), h2(df), h3(df)
    t1.to_csv(TBL / "PMZ_h1.csv", index=False); t2.to_csv(TBL / "PMZ_h2.csv", index=False)
    t3.to_csv(TBL / "PMZ_h3.csv", index=False)
    print("\n=== H1: does the morning test/break the PM zone? (+ distance-matched control) ===")
    print(tb(t1.T.reset_index().rename(columns={"index": "metric", 0: "value"}), headers="keys", showindex=False))
    print("\n=== H2: gap x PM-extension -> morning open->10:29 return ===")
    print(tb(t2, headers="keys", showindex=False))
    print("\n=== H3: PM-zone width -> first-hour breakout quality ===")
    print(tb(t3, headers="keys", showindex=False))
