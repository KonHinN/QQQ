"""
upleg_timing.py — When does the day's BEST UP-LEG start? Pooled + per-year + by weekday.
QQQ 2018-01 .. 2026-06 (~2,000 days).

Up-leg = the day's maximum low -> later-high swing on 1-min bars (intrabar extremes,
same object as the Phase-1.5 "runner" target). Per day: start minute (where the leg's low
was set), end minute (the leg high), size in bps.

  U1 start/end time histograms (15-min buckets), pooled + per-year stability
  U2 by weekday: n, median size, % start <10:00, % start <10:30, median start/end clock,
     per-year consistency of each weekday's size vs the week's median (8 samples)
  U3 weekday x start-bucket rates for the chart page

Outputs -> tables/UPLEG_*.csv + output/upleg_data.json
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

from oos_playbooks import load_file

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
FILES = [(str(y), Path(f"../oos_data/QQQ_1min_{y}.csv")) for y in range(2018, 2025)] + \
        [("2025+", Path("../QQQ_1min_1y_TH.csv"))]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri"]
CLK = lambda t: f"{(570+int(t))//60:02d}:{(570+int(t))%60:02d}"


def legs_for_file(yr: str, p: Path) -> pd.DataFrame:
    minute, _ = load_file(p)
    m = minute[minute.is_clean]
    ok = m.groupby("date")["minute_index"].size() == 390
    m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
    rows = []
    for dt, g in m.groupby("date", sort=True):
        lo = g.low.to_numpy(); hi = g.high.to_numpy()
        cmin = np.minimum.accumulate(lo)
        leg = (hi - cmin) / cmin
        i = int(np.argmax(leg))
        j = int(np.max(np.where(lo[:i + 1] <= cmin[i] + 1e-9)))
        rows.append(dict(year=yr, date=dt, start=j, end=i, size_bps=leg[i] * 1e4))
    df = pd.DataFrame(rows)
    df["wd"] = pd.to_datetime(df.date).dt.weekday.map(dict(enumerate(WD)))
    return df


def run():
    legs = pd.concat([legs_for_file(y, p) for y, p in FILES], ignore_index=True)
    years = [y for y, _ in FILES]
    legs["sb"] = legs.start // 15
    legs["eb"] = legs.end // 15

    # U1 histograms per year (percent of days)
    def hists(col):
        h = (legs.groupby("year")[col].value_counts(normalize=True) * 100) \
            .unstack(fill_value=0).reindex(columns=range(26), fill_value=0).reindex(years)
        return h
    hs, he = hists("sb"), hists("eb")
    pooled_s = hs.mean(); pooled_e = he.mean()
    start_by_10 = (legs.start < 30).mean() * 100
    start_by_1030 = (legs.start < 60).mean() * 100
    start_by_10_yr = legs.groupby("year").start.apply(lambda s: (s < 30).mean() * 100)

    # U2 weekday table
    rows = []
    week_med = legs.size_bps.median()
    for w in WD:
        s = legs[legs.wd == w]
        # per-year: is this weekday's median size above that year's all-day median?
        yr_sign = []
        for y in years:
            sy = legs[legs.year == y]
            swy = sy[sy.wd == w]
            if len(swy) >= 20:
                yr_sign.append(swy.size_bps.median() > sy.size_bps.median())
        rows.append(dict(
            weekday=w, n=len(s), med_size_bps=round(s.size_bps.median(), 0),
            yrs_size_above_med=f"{sum(yr_sign)}/{len(yr_sign)}",
            start_lt_10=round((s.start < 30).mean() * 100, 1),
            start_lt_1030=round((s.start < 60).mean() * 100, 1),
            med_start=CLK(s.start.median()), med_end=CLK(s.end.median()),
            end_after_15=round((s.end >= 330).mean() * 100, 1)))
    u2 = pd.DataFrame(rows)

    # U3 weekday x start-bucket (% of that weekday's days)
    u3 = (legs.groupby("wd").sb.value_counts(normalize=True) * 100) \
        .unstack(fill_value=0).reindex(index=WD).reindex(columns=range(26), fill_value=0)

    TBL.mkdir(parents=True, exist_ok=True)
    hs.to_csv(TBL / "UPLEG_start_hist.csv"); he.to_csv(TBL / "UPLEG_end_hist.csv")
    u2.to_csv(TBL / "UPLEG_weekday.csv", index=False)
    u3.round(1).to_csv(TBL / "UPLEG_wd_start.csv")

    labels = [CLK(b * 15) for b in range(26)]
    (OUT / "upleg_data.json").write_text(json.dumps(dict(
        years=years, labels=labels,
        start_hist={y: [round(v, 1) for v in hs.loc[y]] for y in years},
        pooled_start=[round(v, 1) for v in pooled_s],
        pooled_end=[round(v, 1) for v in pooled_e],
        weekday=u2.to_dict("records"),
        wd_start={w: [round(v, 1) for v in u3.loc[w]] for w in WD},
        start_by_10=round(start_by_10, 1), start_by_1030=round(start_by_1030, 1),
        start_by_10_yr=[round(v, 1) for v in start_by_10_yr.reindex(years)])))
    return legs, hs, u2, pooled_s


if __name__ == "__main__":
    from tabulate import tabulate as tb
    legs, hs, u2, ps = run()
    print(f"\nup-leg starts before 10:00 on {round((legs.start<30).mean()*100,1)}% of days "
          f"(per year: {[round(v,1) for v in legs.groupby('year').start.apply(lambda s:(s<30).mean()*100)]})")
    print(f"starts before 10:30: {round((legs.start<60).mean()*100,1)}%  | "
          f"starts after 14:00: {round((legs.start>=270).mean()*100,1)}%")
    print("\n=== start-time histogram, pooled (top 8 buckets, % of days) ===")
    top = ps.sort_values(ascending=False).head(8)
    print(tb([(CLK(b*15), round(v,1)) for b,v in top.items()], headers=["bucket","% of days"]))
    print("\n=== by weekday ===")
    print(tb(u2, headers="keys", showindex=False))
