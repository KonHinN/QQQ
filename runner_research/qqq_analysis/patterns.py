"""
patterns.py — Analysis J: intraday pattern taxonomy (day-level + morning block motifs).

Three complementary angles, cross-checked:
  J1. RULE-BASED day categories — transparent definitions (trend day, range day, V-reversal,
      fade day, ...) with frequencies and per-category stats. Mutually exclusive, exhaustive.
  J2. SHAPE CLUSTERING — k-means on z-normalized intraday paths at several k, named by their
      median path; silhouette reported honestly (days are a continuum, clusters are soft).
  J3. MORNING MOTIFS — sign sequence of the three 30-min blocks 09:30-11:00 (e.g. "+-+" =
      up-down-up) counted against an independence null, plus what each motif implies for the
      rest of the day (11:00->close) — the actionable linkage.

All aggregates: 247 clean days; robustness = H1 vs H2 halves. Outputs -> output/tables/J_*.csv
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, _clk, N_MIN

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
RNG = np.random.default_rng(21)


# ---------------------------------------------------------------- shared frames
def day_features(m, d):
    d = d[d.is_clean].copy().sort_values("date").reset_index(drop=True)
    piv = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
           .reindex(columns=np.arange(N_MIN)).dropna())
    path = piv.div(piv.iloc[:, 0], axis=0).sub(1).mul(100)          # % from open
    d = d[d.date.isin(path.index)].reset_index(drop=True)
    d["oc_move"] = d.rth_close - d.rth_open
    d["oc_over_range"] = d.oc_move.abs() / d.day_range               # 1 = pure trend, 0 = round trip
    d["dirn"] = np.sign(d.oc_move)
    half = len(d) // 2
    d["half"] = ["H1"] * half + ["H2"] * (len(d) - half)
    return d, path


# ================================================================ J1. rule-based taxonomy
def classify_day(r):
    """Mutually exclusive, ordered rules. Extremes checked first, shape second."""
    early_ext = min(r.hod_minute, r.lod_minute) <= 60          # an extreme inside first hour
    late_rev = r.oc_over_range <= 0.35
    if r.oc_over_range >= 0.65 and r.dirn > 0:
        return "trend_up"
    if r.oc_over_range >= 0.65 and r.dirn < 0:
        return "trend_down"
    # V / inverted-V: opposite extreme printed early, then closed near the other end
    if r.lod_minute <= 90 and r.close_pos >= 0.6:
        return "V_reversal_up"        # sold off early, reversed up
    if r.hod_minute <= 90 and r.close_pos <= 0.4:
        return "A_reversal_down"      # rallied early, faded down (inverted V)
    if late_rev and r.hod_minute >= 300:
        return "late_pop_fade"        # high printed late but closed off it
    if late_rev and r.lod_minute >= 300:
        return "late_drop_recover"
    if r.oc_over_range <= 0.35:
        return "range_chop"
    return "drift"                    # moderate directional, 0.35-0.65


def rule_taxonomy(d):
    d = d.copy()
    d["category"] = d.apply(classify_day, axis=1)
    order = ["trend_up", "trend_down", "V_reversal_up", "A_reversal_down",
             "late_pop_fade", "late_drop_recover", "range_chop", "drift"]
    rows = []
    for cat in order:
        sub = d[d.category == cat]
        if not len(sub):
            continue
        h1 = (sub.half == "H1").sum(); h2 = (sub.half == "H2").sum()
        rows.append({
            "category": cat, "n_days": len(sub), "pct_of_days": round(len(sub) / len(d) * 100, 1),
            "n_H1": h1, "n_H2": h2,
            "range_med": round(sub.day_range.median(), 2),
            "gap_pct_med": round(sub.gap_pct.median(), 3),
            "close_pos_med": round(sub.close_pos.median(), 2),
            "hod_min_med": sub.hod_minute.median(), "lod_min_med": sub.lod_minute.median(),
            "example_dates": ", ".join(sub.date.head(3)),
        })
    tab = pd.DataFrame(rows)
    return tab, d[["date", "half", "category"]]


# ================================================================ J2. shape clustering (named)
def shape_clusters(path, d, ks=(3, 4, 5, 6, 8)):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    cols = np.arange(0, N_MIN, 5)
    X = path.iloc[:, cols].to_numpy()
    Xn = (X - X.mean(axis=1, keepdims=True)) / (X.std(axis=1, keepdims=True) + 1e-9)
    sel_rows, best = [], {}
    for k in ks:
        km = KMeans(n_clusters=k, n_init=20, random_state=42).fit(Xn)
        sil = silhouette_score(Xn, km.labels_)
        sel_rows.append({"k": k, "silhouette": round(sil, 3)})
        best[k] = km
    # use k=5 for an interpretable read (silhouette reported alongside)
    k_show = 5
    km = best[k_show]
    lab = pd.Series(km.labels_, index=path.index, name="cluster")
    med_paths = path.groupby(lab).median()

    def name_cluster(p):
        """Name by median-path landmarks: value at 11:00 (idx 90) and 13:00 (idx 210),
        mid-morning dip, and where the close ends relative to the path."""
        p = p.values
        end, at11, at13 = p[-1], p[90], p[210]
        if end > 0:
            if p[60:150].min() < -0.15:
                return "morning_dip_recover"          # V: down first ~hour, recover into close
            if at11 > 0.6 * end:
                return "fast_morning_rally_hold"      # most of the day's gain done by 11:00
            return "steady_grind_up"                  # low at open, climbs all day
        if at13 <= end:
            return "early_top_trend_down"             # sells off hard, midday low
        return "slow_bleed_into_close"                # early top, keeps leaking to the bell
    rows = []
    for c in med_paths.index:
        p = med_paths.loc[c]
        sub_d = d[d.date.isin(lab[lab == c].index)]
        rows.append({"cluster": int(c), "auto_name": name_cluster(p),
                     "n_days": int((lab == c).sum()),
                     "pct": round((lab == c).mean() * 100, 1),
                     "n_H1": int((sub_d.half == "H1").sum()), "n_H2": int((sub_d.half == "H2").sum()),
                     "close_pos_med": round(sub_d.close_pos.median(), 2),
                     "range_med": round(sub_d.day_range.median(), 2)})
    names = pd.DataFrame(rows)
    med_out = med_paths.copy()
    med_out.columns = [f"m{int(c)}" for c in med_out.columns]
    med_out = med_out.reset_index()
    return pd.DataFrame(sel_rows), names, med_out, lab.reset_index().rename(columns={"index": "date"})


# ================================================================ J3. morning motifs
def morning_motifs(m, d, path):
    """Sign sequence of 30-min block returns 09:30-11:00 (3 legs) => 8 motifs.
    Tested vs independence null; linked to rest-of-day (11:00 -> close)."""
    piv = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
           .reindex(columns=np.arange(N_MIN)).dropna())
    opens = m[m.is_clean].groupby("date")["open"].first()
    b = {}
    b0 = piv[29].div(opens.reindex(piv.index)) - 1          # 09:30-10:00 (vs day open)
    b1 = piv[59].div(piv[29]) - 1                           # 10:00-10:30
    b2 = piv[89].div(piv[59]) - 1                           # 10:30-11:00
    rest = piv[389].div(piv[89]) - 1                        # 11:00 -> close
    sgn = lambda s: np.where(s >= 0, "+", "-")
    motif = pd.Series([a + bb + c for a, bb, c in zip(sgn(b0), sgn(b1), sgn(b2))],
                      index=piv.index, name="motif")
    df = pd.DataFrame({"motif": motif, "b0": b0 * 1e4, "b1": b1 * 1e4, "b2": b2 * 1e4,
                       "rest_bps": rest * 1e4})
    df["half"] = ["H1"] * (len(df) // 2) + ["H2"] * (len(df) - len(df) // 2)

    # independence null: per-leg up-probabilities
    p_up = [float((s >= 0).mean()) for s in (b0, b1, b2)]
    rows = []
    for mt, sub in df.groupby("motif"):
        exp_p = np.prod([p_up[i] if mt[i] == "+" else 1 - p_up[i] for i in range(3)])
        n, N = len(sub), len(df)
        z = (n - N * exp_p) / np.sqrt(N * exp_p * (1 - exp_p))
        rest_med = sub.rest_bps.median()
        pos = (sub.rest_bps > 0).mean() * 100
        rows.append({"motif": mt, "read": {"+": "up", "-": "down"}[mt[0]] + "-" +
                                          {"+": "up", "-": "down"}[mt[1]] + "-" +
                                          {"+": "up", "-": "down"}[mt[2]],
                     "n_days": n, "pct": round(n / N * 100, 1),
                     "expected_pct_if_independent": round(exp_p * 100, 1),
                     "z_vs_independent": round(z, 2),
                     "rest_of_day_med_bps": round(rest_med, 1),
                     "rest_up_pct": round(pos, 1),
                     "n_H1": int((sub.half == "H1").sum()), "n_H2": int((sub.half == "H2").sum())})
    tab = pd.DataFrame(rows).sort_values("n_days", ascending=False).reset_index(drop=True)

    # H1/H2 check of the rest-of-day linkage for the biggest motifs
    stab_rows = []
    for mt, sub in df.groupby("motif"):
        if len(sub) < 20:
            continue
        stab_rows.append({"motif": mt,
                          "rest_med_H1": round(sub[sub.half == "H1"].rest_bps.median(), 1),
                          "rest_med_H2": round(sub[sub.half == "H2"].rest_bps.median(), 1),
                          "n_H1": int((sub.half == "H1").sum()),
                          "n_H2": int((sub.half == "H2").sum())})
    stab = pd.DataFrame(stab_rows)
    return tab, stab, df.reset_index().rename(columns={"index": "date"})


# ================================================================ J4. early recognition
def early_recognition(m, d, rule_lab):
    """Can the category be recognized by 11:00, and does it predict the afternoon?
    Answer: morning shapes the *label* (partly mechanically) but NOT the afternoon."""
    piv = (m[m.is_clean].pivot_table(index="date", columns="minute_index", values="close")
           .reindex(columns=np.arange(N_MIN)).dropna())
    op = m[m.is_clean].groupby("date")["open"].first().reindex(piv.index)
    morn = (piv[89] / op - 1) * 1e4
    rest = (piv[389] / piv[89] - 1) * 1e4
    df = pd.DataFrame({"morn": morn, "rest": rest}).join(rule_lab.set_index("date"))
    cont = (np.sign(df.morn) == np.sign(df.rest)).mean() * 100
    corr = df.morn.corr(df.rest)
    df["strong_morn"] = df.morn.abs() > df.morn.abs().quantile(2 / 3)
    rows = []
    for s, sub in df.groupby("strong_morn"):
        rows.append({"subset": "strong directional morning (top tercile |0930-1100|)" if s
                               else "weak/mixed morning",
                     "n_days": len(sub),
                     "P_ends_as_trend_day_pct": round(sub.category.isin(["trend_up", "trend_down"]).mean() * 100, 1),
                     "P_ends_as_reversal_day_pct": round(sub.category.isin(["V_reversal_up", "A_reversal_down"]).mean() * 100, 1),
                     "P_afternoon_continues_pct": round((np.sign(sub.morn) == np.sign(sub.rest)).mean() * 100, 1),
                     "afternoon_med_bps": round(sub.rest.median(), 1)})
    tab = pd.DataFrame(rows)
    head = pd.DataFrame([{"P_afternoon_same_sign_as_morning_pct": round(cont, 1),
                          "corr_morning_vs_rest": round(corr, 3),
                          "baseline_P_trend_day_pct": round(df.category.isin(["trend_up", "trend_down"]).mean() * 100, 1),
                          "note": "morning->afternoon prediction is NULL; strong morning raises the trend-day LABEL partly mechanically"}])
    return head, tab


# ================================================================ run
def run(write=True):
    m, d0 = load()
    d, path = day_features(m, d0)
    rule_tab, rule_lab = rule_taxonomy(d)
    ksel, cl_names, cl_paths, cl_lab = shape_clusters(path, d)
    motif_tab, motif_stab, motif_days = morning_motifs(m, d, path)
    er_head, er_tab = early_recognition(m, d, rule_lab)

    # cross-tab: rule category vs shape cluster (do the two views agree?)
    merged = rule_lab.merge(cl_lab.rename(columns={"cluster": "shape_cluster"}), on="date")
    xtab = pd.crosstab(merged.category, merged.shape_cluster)
    xtab = xtab.reset_index()

    res = {"J_rule_taxonomy": rule_tab, "J_rule_labels": rule_lab,
           "J_shape_kselect": ksel, "J_shape_clusters": cl_names,
           "J_shape_median_paths": cl_paths, "J_shape_labels": cl_lab,
           "J_morning_motifs": motif_tab, "J_motif_stability": motif_stab,
           "J_motif_days": motif_days, "J_rule_vs_shape": xtab,
           "J_early_recognition": er_head, "J_early_recognition_detail": er_tab}
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[patterns] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    r = run()
    pd.set_option("display.width", 220)
    print("\n=== J1 rule-based day taxonomy ===")
    print(r["J_rule_taxonomy"].drop(columns="example_dates").to_string(index=False))
    print("\n=== J2 shape clusters (k=5; silhouettes:", r["J_shape_kselect"].to_dict("records"), ") ===")
    print(r["J_shape_clusters"].to_string(index=False))
    print("\n=== J3 morning motifs (09:30-10:00-10:30-11:00 legs) ===")
    print(r["J_morning_motifs"].to_string(index=False))
    print("\n=== motif rest-of-day stability H1/H2 ===")
    print(r["J_motif_stability"].to_string(index=False))
