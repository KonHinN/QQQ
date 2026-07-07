"""
skip_battery.py — "When NOT to trade": skip-condition battery for the final early-low-hold
playbook (check 11:00, big-body-skip + PM-strength filters ON). QQQ 2018-2026.

Already-adopted skips (context, not retested): checklist fails (~60% of days flat) ·
big-body yesterday · session low under the PM low. Already-refuted skip: recency gate
("pattern cold lately") — skips the BEST trades.

Candidates tested here (all knowable at/before 11:00; DEV 2018-21 -> frozen cutoffs -> VAL 2022-26):
  CALENDAR   fomc_day    FOMC decision day (hardcoded calendar 2018-2026 — verify before live;
                         14:00 announcement lands mid-hold)
             opex        monthly options expiration (3rd Friday; deterministic)
             monday      the "early & small" weekday lean from the up-leg study
  REGIME     high_vol    trailing 20d mean daily range in its top tercile (DEV cutoff, frozen)
  SETUP      gap_crash   gap <= -0.35 x prior range (the old bounce-book event days)
             extended    price already far off the LOD at 11:00 (top DEV tercile, frozen)
             tight_vwap  entry barely above VWAP (bottom DEV tercile, frozen) — instant-whipsaw risk

Output -> tables/SKIP_dev.csv / SKIP_val.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

import ingest
from oos_playbooks import load_file
from premarket import premarket_daily
from check_ladder import trades

TBL = Path(__file__).resolve().parent / "output" / "tables"
CHECK_T = 90
DEV = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2018, 2019, 2020, 2021)]
VAL = [f"../qqq_full/QQQ_1min_{y}.csv" for y in (2022, 2023, 2024, 2025, 2026)]

FOMC = {  # decision (2nd) days; 2020 includes the two emergency cuts. APPROXIMATE — verify.
 "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
 "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
 "2020-01-29","2020-03-03","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
 "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
 "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
 "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
 "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
 "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
 "2026-01-28","2026-03-18","2026-04-29","2026-06-17"}


def is_opex(dt: pd.Timestamp) -> bool:
    return dt.weekday() == 4 and 15 <= dt.day <= 21


def frame(files) -> pd.DataFrame:
    per = []
    for f in files:
        raw = ingest.load_raw(Path(f))
        minute, daily = load_file(Path(f))
        m = minute[minute.is_clean]
        ok = m.groupby("date")["minute_index"].size() == 390
        m = m[m.date.isin(ok[ok].index)].sort_values(["date", "minute_index"])
        pl = m.pivot_table(index="date", columns="minute_index", values="low")
        pc = m.pivot_table(index="date", columns="minute_index", values="close")
        pv = m.pivot_table(index="date", columns="minute_index", values="vwap_rth")
        pmd = premarket_daily(raw).set_index("date")
        dd = daily[daily.is_clean].sort_values("date").reset_index(drop=True)
        dd["body"] = (dd.rth_close - dd.rth_open) / dd.rth_open * 100
        ab = dd.body.abs()
        bigbody = dict(zip(dd.date, (ab >= ab.rolling(20, min_periods=10).quantile(.8).shift(1))
                           .shift(1).fillna(False).astype(bool)))
        dd["range_pct"] = dd.day_range / dd.rth_open * 100
        vol20 = dd.range_pct.rolling(20, min_periods=10).mean().shift(1)
        volmap = dict(zip(dd.date, vol20))
        dd["gop"] = dd.gap / dd.day_range.shift(1)
        gopmap = dict(zip(dd.date, dd.gop))

        tr = trades(f, CHECK_T, 1).rename("bps").to_frame()
        tr["year"] = Path(f).stem[-4:]
        rows = []
        for dt in tr.index:
            if dt not in pmd.index or pmd.loc[dt, "pm_bars"] < 60:
                continue
            low_sofar = float(pl.loc[dt, :CHECK_T].min())
            if bigbody.get(dt, False) or low_sofar <= float(pmd.loc[dt, "pm_low"]):
                continue                                   # final-playbook filters
            c11 = float(pc.loc[dt, CHECK_T]); v11 = float(pv.loc[dt, CHECK_T])
            ts = pd.Timestamp(dt)
            rows.append(dict(date=dt, year=tr.loc[dt, "year"], bps=tr.loc[dt, "bps"],
                             fomc_day=dt in FOMC, opex=is_opex(ts), monday=ts.weekday() == 0,
                             vol20=volmap.get(dt, np.nan),
                             gap_crash=bool(gopmap.get(dt, np.nan) <= -0.35),
                             ext_pct=(c11 / low_sofar - 1) * 100,
                             vwap_bps=(c11 / v11 - 1) * 1e4))
        per.append(pd.DataFrame(rows))
    return pd.concat(per, ignore_index=True)


def battery(T: pd.DataFrame, cuts: dict, label: str) -> pd.DataFrame:
    T = T.copy()
    T["high_vol"] = T.vol20 >= cuts["vol_hi"]
    T["extended"] = T.ext_pct >= cuts["ext_hi"]
    T["tight_vwap"] = T.vwap_bps <= cuts["vwap_lo"]
    feats = ["fomc_day", "opex", "monday", "high_vol", "gap_crash", "extended", "tight_vwap"]
    rows = []
    for c in feats:
        m = T[c].fillna(False).astype(bool)
        on, off = T[m], T[~m]
        yrs = []
        for y in sorted(T.year.unique()):
            s = T[T.year == y]; sm = s[c].fillna(False).astype(bool)
            if sm.sum() >= 6:
                yrs.append(s[sm].bps.mean() < s.bps.mean())     # skip helps if ON-mean below base
        rows.append(dict(skip_if=c, n_skip=int(m.sum()),
                         mean_skipped=round(on.bps.mean(), 1) if len(on) else np.nan,
                         mean_kept=round(off.bps.mean(), 1),
                         diff=round((off.bps.mean() - on.bps.mean()), 1) if len(on) else np.nan,
                         yrs_skip_helps=f"{sum(yrs)}/{len(yrs)}" if yrs else "-"))
    out = pd.DataFrame(rows).sort_values("diff", ascending=False)
    print(f"\n=== {label} (base mean {T.bps.mean():.1f} bps, n={len(T)}) — 'diff' = kept minus skipped ===")
    from tabulate import tabulate as tb
    print(tb(out, headers="keys", showindex=False))
    return out


if __name__ == "__main__":
    Tdev = frame(DEV)
    cuts = dict(vol_hi=Tdev.vol20.quantile(2/3), ext_hi=Tdev.ext_pct.quantile(2/3),
                vwap_lo=Tdev.vwap_bps.quantile(1/3))
    print(f"frozen DEV cutoffs: vol20>={cuts['vol_hi']:.2f}%  ext>={cuts['ext_hi']:.2f}%  vwap<={cuts['vwap_lo']:.1f}bps")
    dev = battery(Tdev, cuts, "DEV 2018-2021")
    TBL.mkdir(parents=True, exist_ok=True)
    dev.to_csv(TBL / "SKIP_dev.csv", index=False)
    Tval = frame(VAL)
    val = battery(Tval, cuts, "VAL 2022-2026 (frozen cutoffs)")
    val.to_csv(TBL / "SKIP_val.csv", index=False)
