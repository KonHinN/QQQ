"""
ingest.py — Load, clean, RTH-filter and derive fields for QQQ 1-min analysis.

Pins (do not change without re-validating):
  * timestamp_et is the clock, parsed DAY-FIRST '%d/%m/%Y %H:%M'.
  * RTH filter = 09:30:00..15:59:00 ET inclusive -> 390 minutes/day, minute_index 0..389.
  * RTH-anchored VWAP recomputed from 09:30 each day (provided vwap col is pre-market anchored, discarded).
  * 5 days excluded from AGGREGATES (kept in raw table), flagged full/holiday_thin/boundary_partial.
  * All date join keys are STRINGS ('YYYY-MM-DD') to avoid silent empty joins.

Outputs (written to output/):
  minute.parquet   — per-minute table, all 252 days, with flags + derived fields
  daily.parquet    — per-day table, all 252 days, with derived fields + prior-day levels
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config
CSV_PATH = Path(__file__).resolve().parent.parent / "QQQ_1min_1y_TH.csv"
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RTH_START = dt.time(9, 30, 0)
RTH_END = dt.time(15, 59, 0)          # inclusive -> 390 bars
N_MIN = 390
TICK = 0.01                            # QQQ tick size
ATR_LEN = 14

# day flags
BOUNDARY_PARTIAL = {"2025-06-30", "2026-06-30"}
HOLIDAY_THIN = {"2025-07-03", "2025-11-28", "2025-12-24"}
EXCLUDE = BOUNDARY_PARTIAL | HOLIDAY_THIN   # excluded from aggregates


# ---------------------------------------------------------------- load + RTH
def load_raw(path: Path = CSV_PATH) -> pd.DataFrame:
    """Load CSV, parse ET clock day-first, attach date string + minute_index for RTH bars."""
    df = pd.read_csv(path)
    df["et"] = pd.to_datetime(df["timestamp_et"], format="%d/%m/%Y %H:%M")
    df["date"] = df["et"].dt.strftime("%Y-%m-%d")        # STRING join key
    df["time"] = df["et"].dt.time
    return df


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep 09:30:00..15:59:00 ET, assign minute_index 0..389 (0 = 09:30)."""
    mask = (df["et"].dt.time >= RTH_START) & (df["et"].dt.time <= RTH_END)
    rth = df.loc[mask].sort_values("et").reset_index(drop=True)
    # minute_index from 09:30 of that day
    mins = rth["et"].dt.hour * 60 + rth["et"].dt.minute
    rth["minute_index"] = (mins - (9 * 60 + 30)).astype(int)
    return rth


def flag_days(rth: pd.DataFrame) -> pd.DataFrame:
    """Per-date flag: full / holiday_thin / boundary_partial. Also is_clean bool."""
    def _flag(d: str) -> str:
        if d in BOUNDARY_PARTIAL:
            return "boundary_partial"
        if d in HOLIDAY_THIN:
            return "holiday_thin"
        return "full"
    flags = pd.DataFrame({"date": sorted(rth["date"].unique())})
    flags["day_flag"] = flags["date"].map(_flag)
    flags["is_clean"] = ~flags["date"].isin(EXCLUDE)
    return flags


# ---------------------------------------------------------------- per-minute derived
def _wilder_atr(g: pd.DataFrame, n: int = ATR_LEN) -> pd.Series:
    """Wilder ATR on 1-min bars, reset per day (no overnight gap leakage), no look-ahead.
    First bar TR = high-low (no prior close inside the day)."""
    h, l, c = g["high"].to_numpy(), g["low"].to_numpy(), g["close"].to_numpy()
    pc = np.empty_like(c); pc[0] = np.nan; pc[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    atr = np.full_like(tr, np.nan)
    if len(tr) >= n:
        atr[n - 1] = tr[:n].mean()                      # seed = SMA of first n TRs
        for i in range(n, len(tr)):
            atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return pd.Series(atr, index=g.index)


def derive_minute(rth: pd.DataFrame, daily_prior: pd.DataFrame) -> pd.DataFrame:
    """Per-minute derived fields. Operates per-day; all rolling stats causal (no look-ahead)."""
    rth = rth.sort_values(["date", "minute_index"]).reset_index(drop=True)
    g = rth.groupby("date", sort=False)

    # return vs prior bar (within day; first bar NaN)
    rth["ret"] = g["close"].pct_change()
    rth["ret_bps"] = rth["ret"] * 1e4
    rth["range"] = rth["high"] - rth["low"]

    # RTH-anchored VWAP (typical price, cumulative, reset each day)
    tp = (rth["high"] + rth["low"] + rth["close"]) / 3.0
    tpv = tp * rth["volume"]
    rth["cum_tpv"] = g.apply(lambda x: tpv.loc[x.index].cumsum(), include_groups=False).reset_index(level=0, drop=True)
    rth["cum_vol"] = g["volume"].cumsum()
    rth["vwap_rth"] = rth["cum_tpv"] / rth["cum_vol"]

    # ATR(14) per day + ATR-units move
    rth["atr"] = g.apply(lambda x: _wilder_atr(x), include_groups=False).reset_index(level=0, drop=True)
    rth["move_atr"] = (rth["close"] - rth["open"]) / rth["atr"]     # bar move in ATR units
    rth["ret_atr"] = (rth["close"] - g["close"].shift(1)) / rth["atr"]

    # running HOD/LOD with the minute_index at which each was (last) set
    rth["run_hod"] = g["high"].cummax()
    rth["run_lod"] = g["low"].cummin()
    is_new_high = rth["high"] >= rth["run_hod"] - 1e-9
    is_new_low = rth["low"] <= rth["run_lod"] + 1e-9
    rth["hod_minute_sofar"] = np.where(is_new_high, rth["minute_index"], np.nan)
    rth["lod_minute_sofar"] = np.where(is_new_low, rth["minute_index"], np.nan)
    rth["hod_minute_sofar"] = g["hod_minute_sofar"].ffill().fillna(0).astype(int)
    rth["lod_minute_sofar"] = g["lod_minute_sofar"].ffill().fillna(0).astype(int)

    # distance to prior-day H/L/C (ticks + %)
    pd_levels = daily_prior.set_index("date")[["pdh", "pdl", "pdc", "prior_is_full"]]
    rth = rth.merge(pd_levels, left_on="date", right_index=True, how="left")
    for lvl in ("pdh", "pdl", "pdc"):
        rth[f"dist_{lvl}_tick"] = (rth["close"] - rth[lvl]) / TICK
        rth[f"dist_{lvl}_pct"] = (rth["close"] - rth[lvl]) / rth[lvl] * 100.0

    return rth


# ---------------------------------------------------------------- per-day derived
def derive_daily(rth: pd.DataFrame) -> pd.DataFrame:
    """Per-day RTH O/H/L/C, HOD/LOD minutes, range, close-pos, OR 5/15/30, prior-day, gap."""
    rows = []
    for d, g in rth.groupby("date", sort=True):
        g = g.sort_values("minute_index")
        o = g["open"].iloc[0]
        c = g["close"].iloc[-1]
        h = g["high"].max()
        l = g["low"].min()
        hod_min = int(g.loc[g["high"].idxmax(), "minute_index"])
        lod_min = int(g.loc[g["low"].idxmin(), "minute_index"])
        rng = h - l
        close_pos = (c - l) / rng if rng > 0 else np.nan
        rec = dict(date=d, rth_open=o, rth_high=h, rth_low=l, rth_close=c,
                   hod_minute=hod_min, lod_minute=lod_min, day_range=rng,
                   close_pos=close_pos, n_bars=len(g))
        for w in (5, 15, 30):
            seg = g[g["minute_index"] < w]
            rec[f"or{w}_high"] = seg["high"].max()
            rec[f"or{w}_low"] = seg["low"].min()
        rows.append(rec)
    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # prior RTH day levels (shift by 1 in trading-day order)
    daily["pdh"] = daily["rth_high"].shift(1)
    daily["pdl"] = daily["rth_low"].shift(1)
    daily["pdc"] = daily["rth_close"].shift(1)
    daily["gap"] = daily["rth_open"] - daily["pdc"]
    daily["gap_pct"] = daily["gap"] / daily["pdc"] * 100.0
    # prior-day integrity: PDH/PDL/PDC from a partial/thin day are unreliable.
    # (e.g. 2025-07-01's prior day 2025-06-30 starts at 11:27 — its "high" misses the morning.)
    prior_date = daily["date"].shift(1)
    daily["prior_is_full"] = prior_date.map(
        lambda x: (x is not None) and (x not in EXCLUDE) if pd.notna(x) else False)
    return daily


# ---------------------------------------------------------------- orchestration
def build(write: bool = True):
    raw = load_raw()
    rth = filter_rth(raw)
    flags = flag_days(rth)
    rth = rth.merge(flags, on="date", how="left")

    daily = derive_daily(rth)
    daily = daily.merge(flags, on="date", how="left")

    minute = derive_minute(rth, daily[["date", "pdh", "pdl", "pdc", "prior_is_full"]])

    keep_min = ["date", "et", "minute_index", "day_flag", "is_clean",
                "open", "high", "low", "close", "volume", "trade_count",
                "ret", "ret_bps", "range", "vwap_rth", "atr", "move_atr", "ret_atr",
                "run_hod", "run_lod", "hod_minute_sofar", "lod_minute_sofar",
                "pdh", "pdl", "pdc", "prior_is_full",
                "dist_pdh_tick", "dist_pdh_pct", "dist_pdl_tick", "dist_pdl_pct",
                "dist_pdc_tick", "dist_pdc_pct"]
    minute = minute[keep_min]

    if write:
        minute.to_parquet(OUT_DIR / "minute.parquet", index=False)
        daily.to_parquet(OUT_DIR / "daily.parquet", index=False)
        print(f"[ingest] minute.parquet {minute.shape}  daily.parquet {daily.shape}")
        print(f"[ingest] clean days: {int(daily['is_clean'].sum())}  excluded: {int((~daily['is_clean']).sum())}")
    return minute, daily


if __name__ == "__main__":
    build()
