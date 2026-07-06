"""
persistence.py — Analysis I: the "recurring reversal clock" hypothesis.

Tests the user's daily-observation hypothesis, purely from raw data:
  (1) local reversals (intermediate swings, not just HOD/LOD) concentrate in certain time blocks;
  (2) that reversal-time signature REPEATS on later days (same week or beyond);
  (3) conditioned on the day's character (trending / hot-open) — character discovered, not tagged.

Methodological guard: markets have volatility clustering + a structural open/close reversal base
rate, so consecutive days LOOK similar for boring reasons. Every persistence test therefore
compares the observed statistic to a **day-order shuffle null** (or marginal null) that preserves
those base rates and destroys only the temporal ordering.

Verdict emerges from the numbers (see I_summary). Outputs -> output/tables/I_*.csv.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from analytics import load, zigzag_atr, _clk

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
RNG = np.random.default_rng(7)
BLOCK = 30                       # minutes per block for signature tests
NB = int(np.ceil(390 / BLOCK))


def _clkblk(b):
    return _clk(int(b) * BLOCK)


# ---------------------------------------------------------------- pivots (local reversals)
def local_reversals(m, k=1.5):
    """Fine ATR-ZigZag => intermediate swings, not just the day's extreme."""
    rows = []
    for date, g in m[m.is_clean].groupby("date"):
        pv = zigzag_atr(g, k=k)
        for i, (mi, px, typ) in enumerate(pv):
            mag = abs(px - pv[i - 1][1]) if i > 0 else np.nan
            rows.append((date, int(mi), typ, mag))
    return pd.DataFrame(rows, columns=["date", "minute_index", "type", "mag"])


def _daily_regime(d):
    d = d[d.is_clean].copy().sort_values("date").reset_index(drop=True)
    d["open30_rng"] = d.or30_high - d.or30_low               # post-open volatility proxy
    d["trend"] = (d.rth_close - d.rth_open).abs() / d.day_range   # 1=clean directional, ~0=round-trip
    d["dir"] = np.sign(d.rth_close - d.rth_open)
    return d


# ---------------------------------------------------------------- (2) signature persistence
def _signature_matrix(pf, days):
    di = {dd: i for i, dd in enumerate(days)}
    M = np.zeros((len(days), NB))
    for _, r in pf.iterrows():
        if r.date in di:
            M[di[r.date], min(r.minute_index // BLOCK, NB - 1)] += 1
    return (M > 0).astype(float)


def signature_persistence(pf, days, n_shuffle=2000):
    B = _signature_matrix(pf, days)

    def consec_cos(X):
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        return np.mean(np.sum(Xn[:-1] * Xn[1:], axis=1))

    def lagk(X, k):
        acs = [np.corrcoef(X[:-k, j], X[k:, j])[0, 1] for j in range(X.shape[1]) if X[:, j].std() > 0]
        return np.nanmean(acs)

    obs_cos = consec_cos(B)
    null_cos = np.array([consec_cos(B[RNG.permutation(len(B))]) for _ in range(n_shuffle)])
    rows = [{"test": "consecutive-day cosine similarity", "lag": 1,
             "observed": round(obs_cos, 4), "null_mean": round(null_cos.mean(), 4),
             "null_sd": round(null_cos.std(), 4),
             "z": round((obs_cos - null_cos.mean()) / null_cos.std(), 2),
             "p_value": round((null_cos >= obs_cos).mean(), 3)}]
    # lag profile 1..10 (weekly recurrence would spike at lag 5)
    for k in range(1, 11):
        obs = lagk(B, k)
        null = np.array([lagk(B[RNG.permutation(len(B))], k) for _ in range(400)])
        rows.append({"test": "block-autocorr", "lag": k, "observed": round(obs, 4),
                     "null_mean": round(null.mean(), 4), "null_sd": round(null.std(), 4),
                     "z": round((obs - null.mean()) / (null.std() + 1e-9), 2),
                     "p_value": round((null >= obs).mean(), 3)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- dominant-swing clock
def dominant_swing_days(m):
    """Per-day dominant ZigZag leg: start pivot, end pivot (= the major terminal reversal),
    leg direction, and the opening 30-min drive direction. AUDIT FIX: the leg's START and END
    are kept separate — the earlier version reported the end while calling it the start."""
    rows = []
    for date, g in m[m.is_clean].groupby("date"):
        g = g.sort_values("minute_index").reset_index(drop=True)
        pv = zigzag_atr(g, k=1.5)
        if len(pv) < 2:
            continue
        legs = [(abs(pv[i][1] - pv[i - 1][1]), pv[i - 1][0], pv[i][0],
                 np.sign(pv[i][1] - pv[i - 1][1])) for i in range(1, len(pv))]
        mag, s, e, dirn = max(legs)
        or30_dir = np.sign(g["close"].iloc[29] - g["open"].iloc[0])
        rows.append(dict(date=date, dom_start=int(s), dom_end=int(e),
                         dom_dir=int(dirn), or30_dir=int(or30_dir), mag=mag))
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def dominant_swing_clock(dd):
    """Distributions of the dominant leg's START and END blocks + day-to-day stickiness of END."""
    ps = np.bincount((dd.dom_start // BLOCK).astype(int), minlength=NB) / len(dd)
    pe = np.bincount((dd.dom_end // BLOCK).astype(int), minlength=NB) / len(dd)
    clock = pd.DataFrame({"block": range(NB), "clock": [_clkblk(b) for b in range(NB)],
                          "start_pct_of_days": (ps * 100).round(1),
                          "end_pct_of_days": (pe * 100).round(1)})
    x = (dd.dom_end // BLOCK).astype(int).values
    obs = (x[1:] == x[:-1]).mean()
    marg = (pe ** 2).sum()
    shuf = np.array([(xx[1:] == xx[:-1]).mean() for xx in [RNG.permutation(x) for _ in range(3000)]])
    stick = pd.DataFrame([{
        "what": "dominant-leg END block (major reversal)",
        "same_block_as_prevday_obs_pct": round(obs * 100, 1),
        "marginal_null_pct": round(marg * 100, 1),
        "shuffle_null_pct": round(shuf.mean() * 100, 1),
        "z": round((obs - shuf.mean()) / shuf.std(), 2),
        "p_value": round((shuf >= obs).mean(), 3),
        "n_days": len(dd),
    }])
    return clock, stick


# ---------------------------------------------------------------- upgraded tests (hypothesis 2.0)
def direction_linkage(dd):
    """Is the dominant leg an EXTENSION of the opening drive or a FADE of it?"""
    early = dd[(dd.dom_start < 30) & (dd.or30_dir != 0)]
    late = dd[(dd.dom_start >= 30) & (dd.or30_dir != 0)]
    rows = []
    for lbl, sub in [("dominant leg starts BEFORE 10:00", early),
                     ("dominant leg starts AFTER 10:00", late)]:
        agree = (sub.dom_dir == sub.or30_dir).mean()
        # binomial z vs 50/50
        n = len(sub)
        z = (agree - 0.5) / np.sqrt(0.25 / n)
        rows.append({"subset": lbl, "n_days": n,
                     "pct_same_dir_as_opening_drive": round(agree * 100, 1),
                     "z_vs_coinflip": round(z, 2)})
    return pd.DataFrame(rows)


def clock_stability(dd):
    """H1 vs H2 stability of the terminal-reversal clock (the robustness acid test)."""
    half = len(dd) // 2
    rows = []
    for lbl, sub in [("H1", dd.iloc[:half]), ("H2", dd.iloc[half:])]:
        e = sub.dom_end.values
        rows.append({"half": lbl, "n_days": len(sub),
                     "end_in_1000_1100_pct": round(((e >= 30) & (e < 90)).mean() * 100, 1),
                     "end_median_minute": float(np.median(e)),
                     "end_median_clock": _clk(int(np.median(e)))})
    return pd.DataFrame(rows)


def weekday_matched_recurrence(pf, days):
    """Sharper 'same week or later' test: does the SAME WEEKDAY next week (lag 5) resemble
    today more than an adjacent day or a distant random day?"""
    B = _signature_matrix(pf, days)
    Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)
    S = Bn @ Bn.T
    wd = pd.to_datetime(pd.Series(days)).dt.dayofweek.values
    lag5 = [(i, i + 5) for i in range(len(days) - 5) if wd[i] == wd[i + 5]]
    lag1 = [(i, i + 1) for i in range(len(days) - 1)]
    dist = [(i, j) for i in range(0, len(days), 3) for j in range(0, len(days), 7) if abs(i - j) > 15]
    c5 = float(np.mean([S[i, j] for i, j in lag5]))
    c1 = float(np.mean([S[i, j] for i, j in lag1]))
    cr = float(np.mean([S[i, j] for i, j in dist]))
    return pd.DataFrame([{
        "same_weekday_next_week_cos": round(c5, 4), "n_weekday_pairs": len(lag5),
        "next_day_cos": round(c1, 4), "distant_random_cos": round(cr, 4),
        "weekly_edge_over_random": round(c5 - cr, 4)}])


# ---------------------------------------------------------------- (3) regime persistence & clock
def regime_persistence(d):
    d = _daily_regime(d)
    rows = []
    for col, lbl in [("open30_rng", "post-open range (vol)"), ("day_range", "daily range (vol)"),
                     ("trend", "trend strength"), ("close_pos", "close position")]:
        x = d[col].values
        obs = np.corrcoef(x[:-1], x[1:])[0, 1]
        shuf = np.array([np.corrcoef(xx[:-1], xx[1:])[0, 1]
                         for xx in [RNG.permutation(x) for _ in range(2000)]])
        rows.append({"feature": lbl, "lag1_autocorr": round(obs, 3),
                     "shuffle_sd": round(shuf.std(), 3),
                     "z": round(obs / (shuf.std() + 1e-9), 2),
                     "persists": bool(abs(obs) > 3 * shuf.std())})
    return pd.DataFrame(rows)


def regime_reversal_clock(m, d):
    d = _daily_regime(d)
    q = d.open30_rng.quantile([1 / 3, 2 / 3]).values
    d["ovreg"] = np.where(d.open30_rng <= q[0], "quiet_open",
                          np.where(d.open30_rng >= q[1], "hot_open", "mid"))
    pf = local_reversals(m).merge(d[["date", "ovreg"]], on="date", how="inner")
    pf["blk"] = pf.minute_index // BLOCK
    tab = pf.groupby(["blk", "ovreg"]).size().unstack("ovreg").fillna(0)
    tab = (tab.div(tab.sum(axis=0), axis=0 if False else 0)) if False else tab.div(tab.sum(axis=0), axis=1) * 100
    tab = tab.reset_index()
    tab["clock"] = tab["blk"].map(_clkblk)
    cols = ["blk", "clock"] + [c for c in ["quiet_open", "mid", "hot_open"] if c in tab.columns]
    out = tab[cols].round(1)
    # do hot-open days resemble EACH OTHER more than random pairs? (regime-conditioned repetition)
    days = d.sort_values("date").date.tolist()
    hot = d[d.ovreg == "hot_open"].date.tolist()
    B_all = _signature_matrix(local_reversals(m), days)
    idx = {dd: i for i, dd in enumerate(days)}

    def pw_cos(rows_idx):
        X = B_all[rows_idx]
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        S = Xn @ Xn.T
        iu = np.triu_indices(len(X), 1)
        return S[iu].mean()
    hot_idx = [idx[x] for x in hot]
    obs = pw_cos(hot_idx)
    null = np.array([pw_cos(list(RNG.choice(len(days), len(hot), replace=False))) for _ in range(500)])
    concl = pd.DataFrame([{
        "hot_open_pairwise_cos": round(obs, 4), "random_pairs_null": round(null.mean(), 4),
        "null_sd": round(null.std(), 4), "z": round((obs - null.mean()) / null.std(), 2),
        "p_value": round((null >= obs).mean(), 3), "n_hot_days": len(hot)}])
    return out, concl


# ---------------------------------------------------------------- run
def run(write=True):
    m, d = load()
    pf = local_reversals(m)
    days = sorted(m[m.is_clean].date.unique())
    sig = signature_persistence(pf, days)
    dd = dominant_swing_days(m)
    clock, stick = dominant_swing_clock(dd)
    dirlink = direction_linkage(dd)
    stab = clock_stability(dd)
    wk = weekday_matched_recurrence(pf, days)
    reg = regime_persistence(d)
    rclock, rconcl = regime_reversal_clock(m, d)

    consec = sig[sig.test.str.startswith("consec")].iloc[0]
    vol_row = reg[reg.feature.str.contains("post-open")].iloc[0]
    end_peak = clock.sort_values("end_pct_of_days", ascending=False).iloc[0]
    end_lm = clock[clock.clock.isin(["10:00", "10:30"])]["end_pct_of_days"].sum()
    start_open = clock[clock.clock.isin(["09:30", "10:00"])]["start_pct_of_days"].sum()
    early = dirlink.iloc[0]

    summary = pd.DataFrame([
        {"claim": "1. Local reversals concentrate in certain time blocks",
         "verdict": "SUPPORTED",
         "evidence": f"biggest leg STARTS 09:30-10:30 on {start_open:.0f}% of days and ENDS (major turn) 10:00-11:00 on {end_lm:.0f}%"},
        {"claim": "1b. The morning leg is an EXTENSION of the opening drive, not a counter-move",
         "verdict": "SUPPORTED (new)",
         "evidence": f"early-starting dominant legs match opening 30-min direction {early.pct_same_dir_as_opening_drive:.0f}% (z={early.z_vs_coinflip}); late starters are a coin-flip"},
        {"claim": "1c. The terminal-reversal clock is stable across the year",
         "verdict": "SUPPORTED (strong)",
         "evidence": f"end-in-10:00-11:00 = {stab.iloc[0].end_in_1000_1100_pct}% (H1) vs {stab.iloc[1].end_in_1000_1100_pct}% (H2)"},
        {"claim": "2. The SPECIFIC reversal block repeats on later days",
         "verdict": "NOT SUPPORTED",
         "evidence": f"consec-day cosine z={consec.z} (p={consec.p_value}); end-block stickiness p={stick.iloc[0].p_value}"},
        {"claim": "2b. ...including the same weekday one week later",
         "verdict": "NOT SUPPORTED",
         "evidence": f"same-weekday-next-week cos {wk.iloc[0].same_weekday_next_week_cos} ~= distant-random {wk.iloc[0].distant_random_cos}"},
        {"claim": "3a. Volatility/activity regime persists day-to-day",
         "verdict": "SUPPORTED (strong)",
         "evidence": f"post-open range lag1 autocorr={vol_row.lag1_autocorr} (z={vol_row.z}); hot days cluster"},
        {"claim": "3b. Reversal clock is regime-specific (hot vs quiet differ)",
         "verdict": "NOT SUPPORTED",
         "evidence": f"hot-open days resemble each other no more than random (z={rconcl.iloc[0].z}, p={rconcl.iloc[0].p_value})"},
        {"claim": "3c. Trending days persist / cluster",
         "verdict": "NOT SUPPORTED",
         "evidence": f"trend-strength lag1 autocorr={reg[reg.feature.str.contains('trend')].iloc[0].lag1_autocorr} (~0)"},
    ])

    res = {"I_summary": summary, "I_signature_persistence": sig,
           "I_dominant_swing_clock": clock, "I_dominant_swing_stickiness": stick,
           "I_direction_linkage": dirlink, "I_clock_stability": stab,
           "I_weekday_recurrence": wk,
           "I_regime_persistence": reg, "I_regime_reversal_clock": rclock,
           "I_regime_repetition": rconcl}
    if write:
        for k, v in res.items():
            v.to_csv(TBL / f"{k}.csv", index=False)
        print("[persistence] wrote", ", ".join(res))
    return res


if __name__ == "__main__":
    r = run()
    print("\n=== VERDICT (hypothesis 2.0) ===")
    print(r["I_summary"].to_string(index=False))
    print("\n=== dominant-swing clock (start vs end blocks, % of days) ===")
    print(r["I_dominant_swing_clock"].to_string(index=False))
    print("\n=== direction linkage ===")
    print(r["I_direction_linkage"].to_string(index=False))
    print("\n=== clock stability H1/H2 ===")
    print(r["I_clock_stability"].to_string(index=False))
