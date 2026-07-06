"""
analytics.py — Analyses A–G, all conditioned on TIME OF DAY (no day-type taxonomy).

Design notes:
  * Aggregates use the 247 CLEAN days only (is_clean). Sample sizes reported in every table.
  * Intraday returns are fat-tailed -> medians + IQR everywhere, never bare means.
  * Causal stats only (ATR/VWAP built causally upstream). ZigZag (E) is a retrospective
    labeller by design — its pivot timestamp is the extreme; confirmation lags by construction.
    That is the intended tool for data-driven pivot discovery, not a tradeable signal.

Returns a dict {name -> DataFrame}; also persisted to output/tables/*.csv by report.py.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "output"
N_MIN = 390
TICK = 0.01


# ---------------------------------------------------------------- helpers
def load():
    m = pd.read_parquet(OUT_DIR / "minute.parquet")
    d = pd.read_parquet(OUT_DIR / "daily.parquet")
    return m, d


def _bucket15(minute_index: pd.Series) -> pd.Series:
    """15-min bucket label like '09:30' for the start of each 15-min block."""
    blk = (minute_index // 15) * 15
    h = 9 + (30 + blk) // 60
    mm = (30 + blk) % 60
    return pd.Series([f"{int(a):02d}:{int(b):02d}" for a, b in zip(h, mm)], index=minute_index.index)


def _clk(minute_index: int) -> str:
    tot = 9 * 60 + 30 + int(minute_index)
    return f"{tot // 60:02d}:{tot % 60:02d}"


def _iqr(s: pd.Series):
    return s.quantile(0.25), s.quantile(0.75)


# ================================================================ A. minute-of-day profile
def analysis_A(m: pd.DataFrame) -> pd.DataFrame:
    c = m[m.is_clean].copy()
    c["up"] = (c["close"] > c["open"]).astype(float)
    c["abs_ret_bps"] = c["ret_bps"].abs()

    grp = c.groupby("minute_index")
    out = pd.DataFrame({"minute_index": np.arange(N_MIN)})
    out["clock"] = out["minute_index"].map(_clk)
    out["n_days"] = grp.size().reindex(out.minute_index).values

    def stat(col, q):
        return grp[col].quantile(q).reindex(out.minute_index).values
    for col, pre in [("ret_bps", "ret_bps"), ("range", "range"),
                     ("move_atr", "moveatr"), ("volume", "vol"), ("abs_ret_bps", "absret_bps")]:
        out[f"{pre}_med"] = stat(col, 0.50)
        out[f"{pre}_q25"] = stat(col, 0.25)
        out[f"{pre}_q75"] = stat(col, 0.75)
    out["pct_up"] = grp["up"].mean().reindex(out.minute_index).values * 100.0

    # continuation-vs-reversal: P(sign(ret_{m+1}) == sign(ret_m)) across days
    piv = c.pivot_table(index="date", columns="minute_index", values="ret_bps")
    piv = piv.reindex(columns=np.arange(N_MIN))
    sign = np.sign(piv)
    cont = (sign.values[:, :-1] == sign.values[:, 1:]) & (sign.values[:, :-1] != 0)
    valid = (sign.values[:, :-1] != 0) & ~np.isnan(piv.values[:, 1:])
    with np.errstate(invalid="ignore"):
        cont_ratio = np.nansum(cont, axis=0) / np.maximum(np.nansum(valid, axis=0), 1)
    cr = np.full(N_MIN, np.nan); cr[:-1] = cont_ratio
    out["cont_ratio"] = cr            # >0.5 momentum, <0.5 mean-reversion (for next bar)
    return out


# ================================================================ B. event-timing distributions
def analysis_B(d: pd.DataFrame) -> dict:
    c = d[d.is_clean].copy()
    # largest directional move of the day = LOD<->HOD leg; it begins at min(hod,lod)
    c["bigmove_start"] = c[["hod_minute", "lod_minute"]].min(axis=1)
    c["bigmove_up"] = c["hod_minute"] > c["lod_minute"]   # low first -> up move

    def bucket_hist(series, name):
        b = _bucket15(series)
        h = b.value_counts().reindex(_bucket_order()).fillna(0).astype(int)
        return pd.DataFrame({"bucket": h.index, f"{name}_count": h.values,
                             f"{name}_pct": (h.values / h.sum() * 100).round(2)})

    hod_b = bucket_hist(c["hod_minute"], "hod")
    lod_b = bucket_hist(c["lod_minute"], "lod")
    big_b = bucket_hist(c["bigmove_start"], "bigmove_start")
    merged = hod_b.merge(lod_b, on="bucket").merge(big_b, on="bucket")
    merged["n_days"] = len(c)

    # per-minute counts too (for fine histograms)
    minute_hist = pd.DataFrame({"minute_index": np.arange(N_MIN)})
    minute_hist["clock"] = minute_hist["minute_index"].map(_clk)
    minute_hist["hod_count"] = c["hod_minute"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values
    minute_hist["lod_count"] = c["lod_minute"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values
    minute_hist["bigmove_start_count"] = c["bigmove_start"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values

    summary = pd.DataFrame({
        "metric": ["HOD_minute", "LOD_minute", "bigmove_start_minute"],
        "median": [c.hod_minute.median(), c.lod_minute.median(), c.bigmove_start.median()],
        "q25": [c.hod_minute.quantile(.25), c.lod_minute.quantile(.25), c.bigmove_start.quantile(.25)],
        "q75": [c.hod_minute.quantile(.75), c.lod_minute.quantile(.75), c.bigmove_start.quantile(.75)],
        "n_days": len(c),
    })
    summary["median_clock"] = summary["median"].apply(lambda x: _clk(int(round(x))))
    return {"B_timing_buckets": merged, "B_timing_minutes": minute_hist, "B_timing_summary": summary}


def _bucket_order():
    out = []
    for blk in range(0, N_MIN, 15):
        h = 9 + (30 + blk) // 60
        mm = (30 + blk) % 60
        out.append(f"{int(h):02d}:{int(mm):02d}")
    return out


# ================================================================ C. opening-range mechanics
def analysis_C(m: pd.DataFrame, d: pd.DataFrame, fakeout_n: int = 5, go_atr: float = 0.5) -> dict:
    c = d[d.is_clean].copy().set_index("date")
    rows = []
    for w in (5, 15, 30):
        rec = {"or_window": w}
        broke_hi = broke_lo = fakeout = go = fail = 0
        first_break_times = []
        n = 0
        for date, g in m[m.is_clean].groupby("date"):
            g = g.sort_values("minute_index")
            orh, orl = c.loc[date, f"or{w}_high"], c.loc[date, f"or{w}_low"]
            atr_day = g["atr"].median()
            post = g[g["minute_index"] >= w]
            n += 1
            hi_break = post[post["high"] > orh]
            lo_break = post[post["low"] < orl]
            t_hi = hi_break["minute_index"].iloc[0] if len(hi_break) else np.inf
            t_lo = lo_break["minute_index"].iloc[0] if len(lo_break) else np.inf
            if len(hi_break): broke_hi += 1
            if len(lo_break): broke_lo += 1
            if t_hi == np.inf and t_lo == np.inf:
                continue
            # first side to break
            if t_hi <= t_lo:
                side, t0, lvl, sign = "hi", t_hi, orh, 1
            else:
                side, t0, lvl, sign = "lo", t_lo, orl, -1
            first_break_times.append(t0)
            # fakeout: closes back inside [orl,orh] within fakeout_n bars after break
            win = g[(g["minute_index"] > t0) & (g["minute_index"] <= t0 + fakeout_n)]
            back_inside = ((win["close"] <= orh) & (win["close"] >= orl)).any()
            # break-and-go: extends beyond break level by go_atr*ATR within fakeout_n bars (in break direction)
            if sign == 1:
                went = (win["high"].max() - orh) >= go_atr * atr_day if len(win) else False
            else:
                went = (orl - win["low"].min()) >= go_atr * atr_day if len(win) else False
            if back_inside:
                fakeout += 1; fail += 1
            elif went:
                go += 1
            else:
                fail += 1
        rec.update({
            "n_days": n,
            "break_hi_rate": round(broke_hi / n * 100, 1),
            "break_lo_rate": round(broke_lo / n * 100, 1),
            "either_break_rate": round(len(first_break_times) / n * 100, 1),
            "fakeout_rate": round(fakeout / max(len(first_break_times), 1) * 100, 1),
            "break_and_go_rate": round(go / max(len(first_break_times), 1) * 100, 1),
            "break_and_fail_rate": round(fail / max(len(first_break_times), 1) * 100, 1),
            "first_break_med_minute": np.median(first_break_times),
            "first_break_med_clock": _clk(int(np.median(first_break_times))),
        })
        rows.append(rec)
    return {"C_or_mechanics": pd.DataFrame(rows)}


# ================================================================ D. prior-day level interaction
def analysis_D(m: pd.DataFrame, d: pd.DataFrame, react_n: int = 30, rev_atr: float = 1.0) -> dict:
    """Prior-day level interaction, APPROACH-DIRECTION AWARE.

    Revision notes (post-audit):
      * Days whose prior day is partial/thin are excluded (prior_is_full) — their PDH/PDL are wrong.
      * A 'PDH touch' only counts as a resistance test if the day OPENED BELOW PDH and traded up
        to it. Days opening above PDH are a different event (level acts as potential support on a
        retest from above) and are scored separately. Mirror logic for PDL. The earlier pooled
        version mixed these and understated the true reversal rates.
    """
    cd = d[(d.is_clean) & (d.get("prior_is_full", True))].set_index("date")
    touch_rows = []
    bucket_touch = {"PDH": [], "PDL": []}
    cats = {"PDH_resistance_from_below": [0, 0], "PDH_support_retest_from_above": [0, 0],
            "PDL_support_from_above": [0, 0], "PDL_resistance_retest_from_below": [0, 0]}
    open_pos = {"open_above_PDH": 0, "open_below_PDL": 0, "open_inside_range": 0}
    gapfill_times = []
    # base-rate-controlled RACE test: from the first touch, which comes first —
    # 1 ATR rejection (away from level) or 1 ATR breakthrough (beyond level)?
    # At a random price point this race is ~50/50; a real S/R level should skew it.
    race = {"PDH_touch": {"reject": 0, "break": 0, "both": 0},
            "PDL_touch": {"reject": 0, "break": 0, "both": 0},
            "control_random_minute": {"reject": 0, "break": 0, "both": 0}}
    rng_race = np.random.default_rng(4)

    def _race(g, t0, lvl, atr, away_is_down, horizon=60):
        lo, hi = g["low"].values, g["high"].values
        for t in range(t0 + 1, min(t0 + 1 + horizon, len(g))):
            if away_is_down:
                rej, brk = lo[t] <= lvl - atr, hi[t] >= lvl + atr
            else:
                rej, brk = hi[t] >= lvl + atr, lo[t] <= lvl - atr
            if rej and brk:
                return "both"
            if rej:
                return "reject"
            if brk:
                return "break"
        return None
    for date, g in m[m.is_clean].groupby("date"):
        if date not in cd.index or pd.isna(cd.loc[date, "pdh"]):
            continue
        g = g.sort_values("minute_index").reset_index(drop=True)
        pdh, pdl, pdc = cd.loc[date, "pdh"], cd.loc[date, "pdl"], cd.loc[date, "pdc"]
        o = g["open"].iloc[0]
        atr_day = g["atr"].median()
        gap = cd.loc[date, "gap"]
        if o > pdh:
            open_pos["open_above_PDH"] += 1
        elif o < pdl:
            open_pos["open_below_PDL"] += 1
        else:
            open_pos["open_inside_range"] += 1

        def react(t0, lvl, direction):
            """direction -1: reversal = fall rev_atr*ATR below lvl-touch; +1: rise above."""
            win = g[(g["minute_index"] > t0) & (g["minute_index"] <= t0 + react_n)]
            if not len(win):
                return False
            if direction < 0:
                return (lvl - win["low"].min()) >= rev_atr * atr_day
            return (win["high"].max() - lvl) >= rev_atr * atr_day

        # PDH as resistance: only meaningful when open is below it
        if o < pdh:
            hit = g[g["high"] >= pdh]
            if len(hit):
                t0 = int(hit["minute_index"].iloc[0])
                cats["PDH_resistance_from_below"][0] += 1
                if react(t0, pdh, -1):
                    cats["PDH_resistance_from_below"][1] += 1
                bucket_touch["PDH"].append(t0)
                touch_rows.append({"date": date, "level": "PDH", "touch_minute": t0})
                r = _race(g, t0, pdh, atr_day, away_is_down=True)
                if r:
                    race["PDH_touch"][r] += 1
        else:   # opened above PDH -> does a retest from above bounce (support)?
            hit = g[g["low"] <= pdh]
            if len(hit):
                t0 = int(hit["minute_index"].iloc[0])
                cats["PDH_support_retest_from_above"][0] += 1
                if react(t0, pdh, +1):
                    cats["PDH_support_retest_from_above"][1] += 1
        # PDL as support: only meaningful when open is above it
        if o > pdl:
            hit = g[g["low"] <= pdl]
            if len(hit):
                t0 = int(hit["minute_index"].iloc[0])
                cats["PDL_support_from_above"][0] += 1
                if react(t0, pdl, +1):
                    cats["PDL_support_from_above"][1] += 1
                bucket_touch["PDL"].append(t0)
                touch_rows.append({"date": date, "level": "PDL", "touch_minute": t0})
                r = _race(g, t0, pdl, atr_day, away_is_down=False)
                if r:
                    race["PDL_touch"][r] += 1
        # control: race from one random morning minute around its own close (no level)
        t0c = int(rng_race.integers(15, 120))
        r = _race(g, t0c, g["close"].iloc[t0c], atr_day, away_is_down=True)
        if r:
            race["control_random_minute"][r] += 1
        else:   # opened below PDL -> retest from below rejects (resistance)?
            hit = g[g["high"] >= pdl]
            if len(hit):
                t0 = int(hit["minute_index"].iloc[0])
                cats["PDL_resistance_retest_from_below"][0] += 1
                if react(t0, pdl, -1):
                    cats["PDL_resistance_retest_from_below"][1] += 1

        # gap fill: first return to pdc
        if gap > 0:      # gap up -> fill when low<=pdc
            f = g[g["low"] <= pdc]
        elif gap < 0:    # gap down -> fill when high>=pdc
            f = g[g["high"] >= pdc]
        else:
            f = g.iloc[[0]]
        if len(f):
            gapfill_times.append({"date": date, "gap_pct": cd.loc[date, "gap_pct"],
                                  "fill_minute": int(f["minute_index"].iloc[0]), "filled": True})
        else:
            gapfill_times.append({"date": date, "gap_pct": cd.loc[date, "gap_pct"],
                                  "fill_minute": np.nan, "filled": False})

    touch_df = pd.DataFrame(touch_rows)
    # time-of-day bucket distribution of first TRUE touch (approach-consistent only)
    def bucket_table(name):
        ts = pd.Series(bucket_touch[name], name="minute_index")
        b = _bucket15(ts.to_frame()["minute_index"]) if len(ts) else pd.Series([], dtype=str)
        cnt = b.value_counts().reindex(_bucket_order()).fillna(0).astype(int)
        return pd.DataFrame({"bucket": cnt.index, f"{name}_touch_count": cnt.values})
    pdh_b = bucket_table("PDH"); pdl_b = bucket_table("PDL")
    touch_buckets = pdh_b.merge(pdl_b, on="bucket")

    label = {"PDH_resistance_from_below": "PDH tested from below (true resistance test)",
             "PDH_support_retest_from_above": "PDH retested from above (gap-over, support?)",
             "PDL_support_from_above": "PDL tested from above (true support test)",
             "PDL_resistance_retest_from_below": "PDL retested from below (gap-under, resistance?)"}
    rev_summary = pd.DataFrame([
        {"interaction": label[k], "key": k, "touches": n, "reversals": r,
         "reversal_rate_pct": round(r / max(n, 1) * 100, 1)}
        for k, (n, r) in cats.items()
    ])
    rev_summary["n_days_usable"] = len(cd)
    open_pos_tbl = pd.DataFrame([{"where": k, "n_days": v,
                                  "pct": round(v / max(sum(open_pos.values()), 1) * 100, 1)}
                                 for k, v in open_pos.items()])

    race_rows = []
    for k, v in race.items():
        dec = v["reject"] + v["break"]
        p = v["reject"] / max(dec, 1)
        z = (p - 0.5) / np.sqrt(0.25 / dec) if dec else np.nan
        race_rows.append({"event": k, "reject_first": v["reject"], "break_first": v["break"],
                          "ambiguous_both": v["both"],
                          "pct_reject_first": round(p * 100, 1), "z_vs_coinflip": round(z, 2)})
    race_tbl = pd.DataFrame(race_rows)

    gf = pd.DataFrame(gapfill_times)
    gf_summary = pd.DataFrame([{
        "n_gap_days": len(gf),
        "fill_rate_pct": round(gf["filled"].mean() * 100, 1),
        "fill_med_minute": gf.loc[gf.filled, "fill_minute"].median(),
        "fill_med_clock": _clk(int(gf.loc[gf.filled, "fill_minute"].median())) if gf.filled.any() else "NA",
        "fill_q25": gf.loc[gf.filled, "fill_minute"].quantile(.25),
        "fill_q75": gf.loc[gf.filled, "fill_minute"].quantile(.75),
    }])
    return {"D_touch_buckets": touch_buckets, "D_reversal_summary": rev_summary,
            "D_race_test": race_tbl, "D_open_position": open_pos_tbl,
            "D_gapfill_summary": gf_summary, "D_gapfill_detail": gf}


# ================================================================ E. ATR ZigZag reversal pivots
def zigzag_atr(g: pd.DataFrame, k: float = 3.0):
    """ATR-thresholded zigzag on close. Reversal confirmed when price retraces k*ATR
    from the running extreme. Returns list of pivots (minute_index, price, type)."""
    g = g.sort_values("minute_index").reset_index(drop=True)
    px = g["close"].to_numpy()
    mi = g["minute_index"].to_numpy()
    atr = g["atr"].to_numpy()
    atr_med = np.nanmedian(atr)
    if not np.isfinite(atr_med) or atr_med <= 0:
        return []
    thr = lambda i: k * (atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else atr_med)
    pivots = []
    direction = 0          # 0 unknown, +1 up leg, -1 down leg
    ext_i = 0              # index of current extreme
    for i in range(1, len(px)):
        if direction >= 0 and px[i] > px[ext_i]:
            ext_i = i
        elif direction <= 0 and px[i] < px[ext_i]:
            ext_i = i
        if direction >= 0 and px[i] <= px[ext_i] - thr(ext_i):
            # confirmed HIGH pivot at ext_i
            pivots.append((int(mi[ext_i]), float(px[ext_i]), "high"))
            direction = -1; ext_i = i
        elif direction <= 0 and px[i] >= px[ext_i] + thr(ext_i):
            pivots.append((int(mi[ext_i]), float(px[ext_i]), "low"))
            direction = 1; ext_i = i
        if direction == 0:
            # establish initial direction once moved thr from start
            if px[i] >= px[0] + thr(0):
                direction = 1; ext_i = i
            elif px[i] <= px[0] - thr(0):
                direction = -1; ext_i = i
    return pivots


def analysis_E(m: pd.DataFrame, k: float = 3.0) -> dict:
    rows = []
    for date, g in m[m.is_clean].groupby("date"):
        pivs = zigzag_atr(g, k=k)
        atr_med = g["atr"].median()
        prev_price = None
        for j, (mi, px, typ) in enumerate(pivs):
            mag_atr = abs(px - prev_price) / atr_med if prev_price is not None else np.nan
            mag_pct = abs(px - prev_price) / prev_price * 100 if prev_price is not None else np.nan
            rows.append({"date": date, "minute_index": mi, "clock": _clk(mi),
                         "price": px, "type": typ, "seq": j,
                         "mag_atr": mag_atr, "mag_pct": mag_pct})
            prev_price = px
    piv = pd.DataFrame(rows)

    # histogram by 15-min bucket, split high/low, with effect size vs uniform
    piv["bucket"] = _bucket15(piv["minute_index"])
    order = _bucket_order()
    n_buckets = len(order)
    def hist(sub, name):
        cnt = sub["bucket"].value_counts().reindex(order).fillna(0).astype(int)
        total = cnt.sum()
        exp = total / n_buckets
        ratio = cnt / exp                      # >1 = over-represented
        # binomial z-score vs uniform p=1/n_buckets
        p = 1 / n_buckets
        z = (cnt - total * p) / np.sqrt(total * p * (1 - p))
        return pd.DataFrame({"bucket": order, f"{name}_count": cnt.values,
                             f"{name}_ratio_vs_unif": ratio.round(2).values,
                             f"{name}_z": z.round(2).values})
    all_h = hist(piv, "all")
    hi_h = hist(piv[piv.type == "high"], "high")
    lo_h = hist(piv[piv.type == "low"], "low")
    bucket_tbl = all_h.merge(hi_h, on="bucket").merge(lo_h, on="bucket")

    # minute-level histogram
    minute_tbl = pd.DataFrame({"minute_index": np.arange(N_MIN)})
    minute_tbl["clock"] = minute_tbl["minute_index"].map(_clk)
    minute_tbl["pivot_count"] = piv["minute_index"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values
    minute_tbl["high_pivot_count"] = piv[piv.type == "high"]["minute_index"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values
    minute_tbl["low_pivot_count"] = piv[piv.type == "low"]["minute_index"].value_counts().reindex(np.arange(N_MIN)).fillna(0).astype(int).values

    # dominant reversal windows (top buckets by z)
    dom = bucket_tbl.sort_values("all_z", ascending=False).head(6)[["bucket", "all_count", "all_ratio_vs_unif", "all_z"]]

    summary = pd.DataFrame([{
        "n_days": m[m.is_clean].date.nunique(),
        "k_atr": k,
        "total_pivots": len(piv),
        "pivots_per_day_med": piv.groupby("date").size().median(),
        "high_pivots": int((piv.type == "high").sum()),
        "low_pivots": int((piv.type == "low").sum()),
        "mag_atr_med": round(piv.mag_atr.median(), 2),
        "mag_pct_med": round(piv.mag_pct.median(), 3),
    }])
    return {"E_pivots": piv, "E_pivot_buckets": bucket_tbl, "E_pivot_minutes": minute_tbl,
            "E_dominant_windows": dom, "E_summary": summary}


# ================================================================ F. normalization & robustness
def analysis_F(m: pd.DataFrame, d: pd.DataFrame) -> dict:
    c = m[m.is_clean].copy()
    clean_days = sorted(c.date.unique())
    half = len(clean_days) // 2
    h1, h2 = set(clean_days[:half]), set(clean_days[half:])
    c["half"] = np.where(c.date.isin(h1), "H1", "H2")

    # minute median return profile per half + correlation
    prof = c.groupby(["half", "minute_index"])["ret_bps"].median().unstack(0)
    prof = prof.reindex(np.arange(N_MIN))
    stab = prof.dropna()
    corr = stab["H1"].corr(stab["H2"]) if {"H1", "H2"} <= set(prof.columns) else np.nan
    prof_out = prof.reset_index().rename(columns={"minute_index": "minute_index"})
    prof_out["clock"] = prof_out["minute_index"].map(_clk)

    # event timing by half (HOD/LOD medians)
    cd = d[d.is_clean].copy()
    cd["half"] = np.where(cd.date.isin(h1), "H1", "H2")
    half_tbl = cd.groupby("half").agg(
        n_days=("date", "size"),
        hod_med=("hod_minute", "median"), lod_med=("lod_minute", "median"),
        close_pos_med=("close_pos", "median"), range_med=("day_range", "median"),
    ).reset_index()
    half_tbl["hod_med_clock"] = half_tbl["hod_med"].apply(lambda x: _clk(int(x)))
    half_tbl["lod_med_clock"] = half_tbl["lod_med"].apply(lambda x: _clk(int(x)))

    # weekday split (clock feature, allowed)
    cd["weekday"] = pd.to_datetime(cd.date).dt.day_name()
    wd_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    wd_tbl = cd.groupby("weekday").agg(
        n_days=("date", "size"),
        hod_med=("hod_minute", "median"), lod_med=("lod_minute", "median"),
        range_med=("day_range", "median"), close_pos_med=("close_pos", "median"),
        ret_med=("rth_close", lambda s: ((cd.loc[s.index, "rth_close"] / cd.loc[s.index, "rth_open"] - 1) * 1e4).median()),
    ).reindex(wd_order).reset_index()

    stab_summary = pd.DataFrame([{
        "minute_profile_H1H2_corr": round(corr, 3),
        "n_days_H1": len(h1), "n_days_H2": len(h2),
    }])
    return {"F_minute_profile_halves": prof_out, "F_halves_summary": half_tbl,
            "F_weekday": wd_tbl, "F_stability_summary": stab_summary}


# ================================================================ G. optional clustering
def analysis_G(m: pd.DataFrame, step: int = 5, k_range=range(2, 9)) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    c = m[m.is_clean].copy()
    # normalized intraday path: cumulative return from open, sampled every `step` min, z-normalized per day
    piv = c.pivot_table(index="date", columns="minute_index", values="close")
    piv = piv.reindex(columns=np.arange(N_MIN)).dropna()
    opens = piv.iloc[:, 0]
    path = piv.div(opens, axis=0).sub(1.0).mul(100.0)        # % from open
    cols = np.arange(0, N_MIN, step)
    X = path.iloc[:, cols].to_numpy()
    # normalize each day to unit std so shape (not amplitude) drives clustering
    Xn = (X - X.mean(axis=1, keepdims=True)) / (X.std(axis=1, keepdims=True) + 1e-9)

    scores = []
    best = None
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xn)
        sil = silhouette_score(Xn, km.labels_)
        scores.append({"k": k, "inertia": round(km.inertia_, 2), "silhouette": round(sil, 3)})
        if best is None or sil > best[1]:
            best = (k, sil, km)
    score_tbl = pd.DataFrame(scores)
    k_best, sil_best, km = best
    labels = pd.DataFrame({"date": path.index, "cluster": km.labels_})
    # mean path per cluster (full resolution, % from open)
    mean_paths = path.copy()
    mean_paths["cluster"] = km.labels_
    cluster_mean = mean_paths.groupby("cluster").median()
    cluster_mean.columns = [f"m{int(x)}" for x in cluster_mean.columns]
    cluster_mean = cluster_mean.reset_index()
    sizes = labels.cluster.value_counts().sort_index()
    size_tbl = pd.DataFrame({"cluster": sizes.index, "n_days": sizes.values,
                             "pct": (sizes.values / sizes.sum() * 100).round(1)})
    summary = pd.DataFrame([{"k_best": k_best, "silhouette_best": round(sil_best, 3),
                             "n_days": len(path), "sample_step_min": step}])
    return {"G_kselect": score_tbl, "G_cluster_sizes": size_tbl,
            "G_cluster_labels": labels, "G_cluster_median_paths": cluster_mean,
            "G_summary": summary}


# ================================================================ run all
def run_all():
    m, d = load()
    res = {}
    res["A_minute_profile"] = analysis_A(m)
    res.update(analysis_B(d))
    res.update(analysis_C(m, d))
    res.update(analysis_D(m, d))
    res.update(analysis_E(m))
    res.update(analysis_F(m, d))
    res.update(analysis_G(m))
    return res, m, d


if __name__ == "__main__":
    res, m, d = run_all()
    for k, v in res.items():
        print(f"{k:30s} {tuple(v.shape)}")
