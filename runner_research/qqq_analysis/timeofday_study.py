"""
timeofday_study.py — Fresh time-of-day structure study, QQQ only, 2018-01 .. 2026-06.

Deliberately assumes NOTHING from the 1-year Phase-1 study. Every statistic is computed per
YEAR (8 samples: 2018..2024 + the 2025-26 file) so each pattern gets a stability verdict:
a time-of-day pattern is STRUCTURAL only if it repeats in (almost) every year.

  T1 volatility by minute   median |1-min close move| (bps), per year, raw + shape-normalized
  T2 volume by minute       each minute's share of the day's volume, per year
  T3 signed drift           26 x 15-min buckets: per-day bucket return -> yearly means ->
                            cross-year sign consistency + t-stat, Bonferroni(26)
  T4 HOD/LOD timing         when the day's high/low prints (15-min buckets), per year
  T5 the day's dominant leg biggest low->high or high->low swing: start/end minute, per year
  T6 close micro-script     per-minute mean signed bps 15:45-15:59, per year consistency

Hygiene per file: RTH 390-bar days only, boundary days dropped (same as oos harness).
Outputs -> tables/TOD_*.csv + output/tod_data.json (for the visual page)
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats as sst

from oos_playbooks import load_file

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
FILES = [(str(y), Path(f"../oos_data/QQQ_1min_{y}.csv")) for y in range(2018, 2025)] + \
        [("2025+", Path("../QQQ_1min_1y_TH.csv"))]
NB = 26                      # 15-min buckets
BUCKET_LAB = [f"{9+(30+b*15)//60:02d}:{(30+b*15)%60:02d}" for b in range(NB)]


def load_all():
    parts = []
    for yr, p in FILES:
        minute, _ = load_file(p)
        m = minute[minute.is_clean]
        ok = m.groupby("date")["minute_index"].size() == 390
        m = m[m.date.isin(ok[ok].index)]
        m = m[["date", "minute_index", "open", "high", "low", "close", "volume"]].copy()
        m["year"] = yr
        parts.append(m)
        print(f"[{yr}] {m.date.nunique()} days")
    return pd.concat(parts, ignore_index=True)


def run():
    m = load_all()
    m = m.sort_values(["year", "date", "minute_index"])
    g = m.groupby(["year", "date"], sort=False)
    m["ret_bps"] = g["close"].pct_change() * 1e4
    years = [y for y, _ in FILES]

    # ---------------- T1 volatility smile + T2 volume share
    t1 = m.dropna(subset=["ret_bps"]).groupby(["year", "minute_index"]).ret_bps \
          .apply(lambda s: s.abs().median()).unstack(0)
    day_vol = m.groupby(["year", "date"]).volume.transform("sum")
    m["vol_share"] = m.volume / day_vol * 100
    t2 = m.groupby(["year", "minute_index"]).vol_share.mean().unstack(0)

    # ---------------- T3 signed drift by 15-min bucket
    m["bucket"] = (m.minute_index // 15).clip(upper=NB - 1)
    bo = m.groupby(["year", "date", "bucket"]).open.first()
    bc = m.groupby(["year", "date", "bucket"]).close.last()
    bret = ((bc / bo - 1) * 1e4).rename("bps").reset_index()
    rows = []
    for b in range(NB):
        s = bret[bret.bucket == b]
        ym = s.groupby("year").bps.mean().reindex(years)
        pooled = s.bps
        t, p = sst.ttest_1samp(pooled, 0)
        rows.append(dict(bucket=BUCKET_LAB[b], mean_bps=round(pooled.mean(), 2),
                         med_bps=round(pooled.median(), 2),
                         yrs_pos=int((ym > 0).sum()), n_years=len(ym.dropna()),
                         t=round(t, 2), p=round(p, 5), bonf_sig=bool(p < 0.05 / NB),
                         yearly=[round(v, 2) for v in ym]))
    t3 = pd.DataFrame(rows)

    # ---------------- T4 HOD/LOD timing
    pivh = m.pivot_table(index=["year", "date"], columns="minute_index", values="high")
    pivl = m.pivot_table(index=["year", "date"], columns="minute_index", values="low")
    hod = pivh.idxmax(axis=1) // 15
    lod = pivl.idxmin(axis=1) // 15
    t4h = (hod.groupby(level=0).value_counts(normalize=True) * 100).unstack(fill_value=0) \
        .reindex(columns=range(NB), fill_value=0)
    t4l = (lod.groupby(level=0).value_counts(normalize=True) * 100).unstack(fill_value=0) \
        .reindex(columns=range(NB), fill_value=0)

    # ---------------- T5 dominant leg start/end
    pivc = m.pivot_table(index=["year", "date"], columns="minute_index", values="close")
    legs = []
    for (yr, dt), row in pivc.iterrows():
        c = row.to_numpy()
        cmin, cmax = np.minimum.accumulate(c), np.maximum.accumulate(c)
        up = c / cmin - 1; dn = c / cmax - 1
        iu, idn = int(np.argmax(up)), int(np.argmin(dn))
        if up[iu] >= -dn[idn]:
            end = iu; start = int(np.argmin(c[:iu + 1])); size = up[iu]
        else:
            end = idn; start = int(np.argmax(c[:idn + 1])); size = -dn[idn]
        legs.append(dict(year=yr, start=start, end=end, size_bps=size * 1e4))
    t5 = pd.DataFrame(legs)
    t5s = t5.groupby("year").agg(
        start_by_1030_pct=("start", lambda s: round((s < 60).mean() * 100, 1)),
        end_1000_1100_pct=("end", lambda s: round(((s >= 30) & (s < 90)).mean() * 100, 1)),
        end_after_1500_pct=("end", lambda s: round((s >= 330).mean() * 100, 1)),
        med_size_bps=("size_bps", lambda s: round(s.median(), 0))).reindex(years)

    # ---------------- T6 close micro-script (last 15 minutes, per minute)
    last = m[m.minute_index >= 375].dropna(subset=["ret_bps"])
    t6 = last.groupby(["year", "minute_index"]).ret_bps.mean().unstack(0).reindex(columns=years)
    t6_pos = last.groupby("minute_index").ret_bps.apply(lambda s: (s > 0).mean() * 100)

    # ---------------- save
    TBL.mkdir(parents=True, exist_ok=True)
    t1.to_csv(TBL / "TOD_vol_smile.csv"); t2.to_csv(TBL / "TOD_volume_u.csv")
    t3.drop(columns="yearly").to_csv(TBL / "TOD_drift_buckets.csv", index=False)
    t4h.to_csv(TBL / "TOD_hod.csv"); t4l.to_csv(TBL / "TOD_lod.csv")
    t5s.to_csv(TBL / "TOD_leg_clock.csv"); t6.to_csv(TBL / "TOD_close_script.csv")

    # shape stability: cross-year Spearman of the smile / U curves
    def shape_corr(t):
        c = t.corr(method="spearman").values
        return round(c[np.triu_indices_from(c, 1)].min(), 3)
    smile_min_corr, volu_min_corr = shape_corr(t1), shape_corr(t2)

    (OUT / "tod_data.json").write_text(json.dumps(dict(
        years=years,
        smile={y: [round(v, 2) for v in t1[y]] for y in years},
        volu={y: [round(v, 3) for v in t2[y]] for y in years},
        drift=t3.to_dict("records"),
        hod={y: [round(v, 1) for v in t4h.loc[y]] for y in years},
        lod={y: [round(v, 1) for v in t4l.loc[y]] for y in years},
        leg=t5s.reset_index().to_dict("records"),
        close={y: [round(v, 2) for v in t6[y]] for y in years},
        close_pos=[round(v, 1) for v in t6_pos],
        smile_min_corr=smile_min_corr, volu_min_corr=volu_min_corr,
        bucket_labels=BUCKET_LAB)))
    return t1, t3, t5s, t6, smile_min_corr, volu_min_corr


if __name__ == "__main__":
    from tabulate import tabulate as tb
    t1, t3, t5s, t6, sc, vc = run()
    print(f"\nsmile shape: min cross-year Spearman {sc} | volume U: {vc}")
    print("\n=== T3 signed drift, 15-min buckets (pooled ~2000 days) ===")
    print(tb(t3.drop(columns="yearly"), headers="keys", showindex=False))
    print("\n=== T5 dominant-leg clock, per year ===")
    print(tb(t5s.reset_index(), headers="keys", showindex=False))
    print("\n=== T6 close script: mean bps per minute 15:45-15:59, by year ===")
    print(tb(t6.round(2).reset_index(), headers="keys", showindex=False))
