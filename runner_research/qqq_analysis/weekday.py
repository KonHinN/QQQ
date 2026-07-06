"""
weekday.py — Analysis L: day-of-week effects, tested honestly.

n ~= 48-52 days per weekday => low power. Guard rails:
  * Kruskal-Wallis across the 5 weekdays per metric (not 10 pairwise fishing trips).
  * 12 tests total => Bonferroni threshold ~0.004; anything 0.004 < p < 0.05 is only a "lead".
  * Every lead must hold the same SIGN in both H1 and H2 to survive.

Outputs -> output/tables/L_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

from analytics import load
from persistence import dominant_swing_days

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
WDS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _daily():
    _, d = load()
    d = d[d.is_clean].copy().sort_values("date").reset_index(drop=True)
    d["wd"] = pd.to_datetime(d.date).dt.day_name()
    d["ret_bps"] = (d.rth_close / d.rth_open - 1) * 1e4
    d["oc_over_range"] = (d.rth_close - d.rth_open).abs() / d.day_range
    half = len(d) // 2
    d["half"] = ["H1"] * half + ["H2"] * (len(d) - half)
    return d


def summary_table(d):
    g = d.groupby("wd")
    tab = pd.DataFrame({
        "n_days": g.size(),
        "ret_med_bps": g.ret_bps.median().round(1),
        "pct_up_days": (g.ret_bps.apply(lambda x: (x > 0).mean()) * 100).round(1),
        "range_med": g.day_range.median().round(2),
        "gap_med_bps": (g.gap_pct.median() * 100).round(1),
        "hod_med_min": g.hod_minute.median(),
        "lod_med_min": g.lod_minute.median(),
        "close_pos_med": g.close_pos.median().round(2),
        "trendiness_med": g.oc_over_range.median().round(2),
    }).reindex(WDS).reset_index()
    return tab


def tests_table(d):
    rows = []
    for col in ["ret_bps", "day_range", "gap_pct", "hod_minute", "lod_minute",
                "close_pos", "oc_over_range"]:
        groups = [d[d.wd == w][col].dropna().values for w in WDS]
        h, p = stats.kruskal(*groups)
        rows.append({"test": f"Kruskal-Wallis {col} across weekdays",
                     "stat": round(h, 2), "p_value": round(p, 4)})
    for w in WDS:
        x = d[d.wd == w].ret_bps.values
        s, p = stats.wilcoxon(x)
        rows.append({"test": f"Wilcoxon {w} return vs 0",
                     "stat": round(float(s), 1), "p_value": round(p, 4)})
    t = pd.DataFrame(rows)
    n_tests = len(t)
    t["bonferroni_threshold"] = round(0.05 / n_tests, 4)
    t["significant_after_correction"] = t.p_value < 0.05 / n_tests
    return t


def stability_table(d):
    rows = []
    for w in WDS:
        s = d[d.wd == w]
        h1 = s[s.half == "H1"]; h2 = s[s.half == "H2"]
        rows.append({"weekday": w,
                     "ret_med_H1": round(h1.ret_bps.median(), 1),
                     "ret_med_H2": round(h2.ret_bps.median(), 1),
                     "ret_same_sign": bool(np.sign(h1.ret_bps.median()) == np.sign(h2.ret_bps.median())),
                     "gap_med_H1": round(h1.gap_pct.median() * 100, 1),
                     "gap_med_H2": round(h2.gap_pct.median() * 100, 1),
                     "gap_same_sign": bool(np.sign(h1.gap_pct.median()) == np.sign(h2.gap_pct.median()))})
    return pd.DataFrame(rows)


def taxonomy_by_weekday():
    lab = pd.read_csv(TBL / "J_rule_labels.csv")
    lab["wd"] = pd.to_datetime(lab.date).dt.day_name()
    lab["cat3"] = lab.category.map(lambda c: "trend" if c.startswith("trend")
                                   else ("reversal" if ("reversal" in c) else "other"))
    ct = pd.crosstab(lab.wd, lab.cat3).reindex(WDS)
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    out = ct.reset_index()
    out["chi2_p_value"] = round(p, 3)
    return out


def clock_by_weekday(m):
    dd = dominant_swing_days(m)
    dd["wd"] = pd.to_datetime(dd.date).dt.day_name()
    rows = []
    for w in WDS:
        s = dd[dd.wd == w]
        rows.append({"weekday": w, "n_days": len(s),
                     "dom_end_in_1000_1100_pct": round(((s.dom_end >= 30) & (s.dom_end < 90)).mean() * 100, 1),
                     "dom_end_med_min": float(s.dom_end.median())})
    groups = [dd[dd.wd == w].dom_end.values for w in WDS]
    _, p = stats.kruskal(*groups)
    t = pd.DataFrame(rows)
    t["kw_p_across_weekdays"] = round(p, 3)
    return t


def run(write=True):
    m, _ = load()
    d = _daily()
    res = {"L_weekday_summary": summary_table(d),
           "L_weekday_tests": tests_table(d),
           "L_weekday_stability": stability_table(d),
           "L_weekday_taxonomy": taxonomy_by_weekday(),
           "L_weekday_clock": clock_by_weekday(m)}
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[weekday] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    r = run()
    for k, v in r.items():
        print(f"\n=== {k} ===")
        print(v.to_string(index=False))
