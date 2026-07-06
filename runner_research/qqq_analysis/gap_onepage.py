"""
gap_onepage.py — 1-page TRADER sheet for the gap-down bounce. Visual-first, minimal text.
Data: T_gapfade_paths.csv (median path), S_runner_gap_buckets.csv, U_exit_ladder.csv, U_mae.csv.
Output: output/gap_onepage.html
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
GREEN = "#26a69a"; RED = "#ef5350"; AMBER = "#ffb74d"; BLUE = "#42a5f5"; PURPLE = "#ab47bc"
DIM = "#7d8895"; FAINT = "#5c6773"; GRIDC = "#232c37"; PANEL = "#12161c"


def _clk(mi):
    t = 9 * 60 + 30 + int(mi)
    return f"{t//60:02d}:{t%60:02d}"


def main_chart(t4: pd.DataFrame, W=1140, H=430) -> str:
    """Median event-day path with entry / stop / exit annotations."""
    x = t4.minute.to_numpy()
    yev = t4.event_med_pct.to_numpy()
    yre = t4.rest_med_pct.to_numpy()
    pad_l, pad_r, pad_t, pad_b = 64, 30, 30, 46
    vmin = min(yev.min(), yre.min(), -1.15) - 0.12
    vmax = max(yev.max(), yre.max()) + 0.18
    sx = (W - pad_l - pad_r) / 389
    sy = (H - pad_t - pad_b) / (vmax - vmin)
    X = lambda mi: pad_l + mi * sx
    Y = lambda v: H - pad_b - (v - vmin) * sy

    entry_v = float(yev[30]); exit_v = float(yev[240])
    stop_v = entry_v - 1.0

    o = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    # grid + time axis
    for mi in (0, 30, 60, 120, 180, 240, 300, 360, 389):
        o.append(f'<line x1="{X(mi):.0f}" y1="{pad_t}" x2="{X(mi):.0f}" y2="{H-pad_b}" stroke="{GRIDC}" stroke-width="1"/>')
        o.append(f'<text x="{X(mi):.0f}" y="{H-16}" font-size="13" fill="{FAINT}" text-anchor="middle">{_clk(mi)}</text>')
    for v in np.arange(np.ceil(vmin*2)/2, vmax, 0.5):
        o.append(f'<line x1="{pad_l}" y1="{Y(v):.0f}" x2="{W-pad_r}" y2="{Y(v):.0f}" stroke="{GRIDC}" stroke-width="1"/>')
        o.append(f'<text x="{pad_l-8}" y="{Y(v)+4:.0f}" font-size="12" fill="{FAINT}" text-anchor="end">{v:+.1f}%</text>')
    o.append(f'<line x1="{pad_l}" y1="{Y(0):.0f}" x2="{W-pad_r}" y2="{Y(0):.0f}" stroke="{DIM}" stroke-width="1.4" stroke-dasharray="2,4"/>')
    o.append(f'<text x="{W-pad_r-4}" y="{Y(0)-6:.0f}" font-size="12" fill="{DIM}" text-anchor="end">open</text>')

    # low-formation zone 09:30-10:00
    o.append(f'<rect x="{X(0):.0f}" y="{pad_t}" width="{X(30)-X(0):.0f}" height="{H-pad_t-pad_b}" fill="{RED}" opacity="0.07"/>')
    o.append(f'<text x="{X(15):.0f}" y="{pad_t+18}" font-size="12" fill="{RED}" text-anchor="middle" opacity="0.9">low forms here (64%)</text>')
    # hold zone
    o.append(f'<rect x="{X(30):.0f}" y="{pad_t}" width="{X(240)-X(30):.0f}" height="{H-pad_t-pad_b}" fill="{GREEN}" opacity="0.05"/>')

    # paths
    pts_r = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(x, yre))
    o.append(f'<polyline points="{pts_r}" fill="none" stroke="{FAINT}" stroke-width="1.8" opacity="0.8"/>')
    pts_e = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(x, yev))
    o.append(f'<polyline points="{pts_e}" fill="none" stroke="{GREEN}" stroke-width="3"/>')
    o.append(f'<text x="{X(330):.0f}" y="{Y(yre[330])+20:.0f}" font-size="13" fill="{FAINT}">normal day</text>')
    o.append(f'<text x="{X(300):.0f}" y="{Y(yev[300])-12:.0f}" font-size="14" fill="{GREEN}" font-weight="bold">gap-down day (median, n=47)</text>')

    # ENTRY marker
    o.append(f'<circle cx="{X(30):.0f}" cy="{Y(entry_v):.0f}" r="9" fill="{AMBER}"/>')
    o.append(f'<text x="{X(30)+14:.0f}" y="{Y(entry_v)+5:.0f}" font-size="15" fill="{AMBER}" font-weight="bold">BUY 10:00 — even if red</text>')
    # STOP line
    o.append(f'<line x1="{X(30):.0f}" y1="{Y(stop_v):.0f}" x2="{X(240):.0f}" y2="{Y(stop_v):.0f}" stroke="{RED}" stroke-width="2" stroke-dasharray="7,5"/>')
    o.append(f'<text x="{X(36):.0f}" y="{Y(stop_v)+18:.0f}" font-size="14" fill="{RED}" font-weight="bold">STOP −1.0% (hit 6/47)</text>')
    # EXIT marker
    o.append(f'<circle cx="{X(240):.0f}" cy="{Y(exit_v):.0f}" r="9" fill="{BLUE}"/>')
    o.append(f'<text x="{X(240):.0f}" y="{Y(exit_v)-16:.0f}" font-size="15" fill="{BLUE}" font-weight="bold" text-anchor="middle">SELL 13:30</text>')
    o.append("</svg>")
    return "".join(o)


def mini_bars(vals, labs, color, title, W=340, H=210, fmt="{:.0f}", highlight=None, base=None):
    n = len(vals)
    pad_l, pad_b, pad_t = 14, 34, 34
    step = (W - pad_l - 10) / n
    bw = step * 0.68
    vmax = max(max(vals), 0.0001); vmin = min(min(vals), 0)
    rng = vmax - vmin
    y0 = pad_t + (H - pad_t - pad_b) * (vmax / rng) if vmin < 0 else H - pad_b
    sc = (H - pad_t - pad_b) / rng
    o = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    o.append(f'<text x="{W/2:.0f}" y="18" font-size="13" fill="#c9d1d9" text-anchor="middle" font-weight="bold">{title}</text>')
    o.append(f'<line x1="{pad_l}" y1="{y0:.0f}" x2="{W-8}" y2="{y0:.0f}" stroke="{GRIDC}" stroke-width="1.5"/>')
    for i, (v, lb) in enumerate(zip(vals, labs)):
        xx = pad_l + i * step + (step - bw) / 2
        h = abs(v) * sc
        y = y0 - h if v >= 0 else y0
        col = color if v >= 0 else RED
        if highlight is not None and i in highlight:
            col = AMBER
        o.append(f'<rect x="{xx:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,1):.1f}" rx="3" fill="{col}"/>')
        vy = y - 6 if v >= 0 else y + h + 14
        o.append(f'<text x="{xx+bw/2:.1f}" y="{vy:.1f}" font-size="12" fill="{DIM}" text-anchor="middle">{fmt.format(v)}</text>')
        o.append(f'<text x="{xx+bw/2:.1f}" y="{H-10}" font-size="11" fill="{FAINT}" text-anchor="middle">{lb}</text>')
    if base is not None:
        by = y0 - base * sc
        o.append(f'<line x1="{pad_l}" y1="{by:.1f}" x2="{W-8}" y2="{by:.1f}" stroke="{DIM}" stroke-width="1.2" stroke-dasharray="4,4"/>')
    o.append("</svg>")
    return "".join(o)


def build():
    t4 = pd.read_csv(TBL / "T_gapfade_paths.csv")
    s2 = pd.read_csv(TBL / "S_runner_gap_buckets.csv")
    u1 = pd.read_csv(TBL / "U_exit_ladder.csv").set_index("exit")
    u2 = pd.read_csv(TBL / "U_mae.csv").set_index("group")

    gb = s2[(s2.col == "gap_over_prange") & (s2.target == "Y_up_trail")]
    c_main = main_chart(t4)
    c_gap = mini_bars(list(gb.rate_pct), ["gap⇊", "", "flat", "", "gap⇈"], BLUE,
                      "P(runner day) by overnight gap", fmt="{:.0f}%", highlight=[0],
                      base=float(gb.base_pct.iloc[0]))
    c_exit = mini_bars([float(u1.loc[k, "med_bps"]) for k in ("11:00", "12:00", "13:30", "close")],
                       ["11:00", "12:00", "13:30", "close"], GREEN,
                       "median bps by exit time", fmt="{:+.0f}", highlight=[2])
    c_mae = mini_bars([float(u2.loc["winners", "mae_P90"]), float(u2.loc["losers", "mae_P50"]),
                       float(u2.loc["losers", "mae_P75"])],
                      ["winners P90", "losers P50", "losers P75"], PURPLE,
                      "dip below entry before end (%)", fmt="{:.2f}")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gap-Down Bounce — 1-Page Playbook</title>
<style>
  body{{margin:0;background:#0b0e11;color:#c9d1d9;font-family:Consolas,Menlo,'SF Mono',monospace;padding:22px 3vw 30px}}
  .wrap{{max-width:1200px;margin:0 auto}}
  .top{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px}}
  h1{{font-size:clamp(22px,3vw,34px);margin:0;line-height:1.05}}
  .kicker{{color:{AMBER};letter-spacing:3px;font-size:11px;margin-bottom:6px}}
  .pills{{display:flex;gap:10px;flex-wrap:wrap}}
  .pill{{background:{PANEL};border:1px solid {GRIDC};border-radius:10px;padding:8px 14px;text-align:center}}
  .pill b{{display:block;font-size:20px;color:{GREEN}}}
  .pill small{{color:{FAINT};font-size:10px;letter-spacing:1px}}
  .rules{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:14px 0}}
  .rule{{background:{PANEL};border:1px solid {GRIDC};border-radius:12px;padding:10px 14px;display:flex;gap:12px;align-items:center}}
  .rule .ic{{font-size:26px}}
  .rule b{{color:#fff;font-size:15px;display:block}}
  .rule span{{color:{DIM};font-size:12px}}
  .panel{{background:{PANEL};border:1px solid {GRIDC};border-radius:14px;padding:10px 14px;margin-bottom:12px}}
  .minis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
  .warnline{{margin-top:12px;border:1px solid rgba(239,83,80,.5);background:rgba(239,83,80,.08);border-radius:10px;
    padding:9px 16px;color:{DIM};font-size:12.5px;text-align:center}}
  .warnline b{{color:{RED}}}
  svg text{{font-family:Consolas,Menlo,monospace}}
  @media print{{body{{background:#fff}}}}
</style></head><body><div class="wrap">
<div class="top">
  <div><div class="kicker">QQQ · GAP-DOWN BOUNCE · 47 EVENTS / 247 DAYS · 2025-26</div>
  <h1>Gap down big? Buy the panic at 10:00.</h1></div>
  <div class="pills">
    <div class="pill"><b>+47 bps</b><small>MEDIAN W/ PM CHECK (n=19)</small></div>
    <div class="pill"><b>68%</b><small>HIT RATE W/ PM CHECK</small></div>
    <div class="pill"><b>+20 / 60%</b><small>ALL EVENTS, NO PM CHECK (n=47)</small></div>
    <div class="pill"><b>~2–4 / mo</b><small>FREQUENCY</small></div>
  </div>
</div>

<div class="rules">
  <div class="rule"><div class="ic">🌅</div><div><b>Gap ≤ −0.35× yest. range</b><span>vs yesterday's RTH close — the setup</span></div></div>
  <div class="rule"><div class="ic">🔍</div><div><b>PM must have bounced</b><span>open ≥0.3% off premarket low → +47 bps · open ON the PM low → −11, skip it</span></div></div>
  <div class="rule"><div class="ic">🎯</div><div><b>Buy 10:00 close</b><span>red vs open is fine — waiting for green costs edge</span></div></div>
  <div class="rule"><div class="ic">🛑</div><div><b>Stop −1.0% hard</b><span>winners never dip that far (P90 0.74%)</span></div></div>
  <div class="rule"><div class="ic">⏰</div><div><b>Sell 13:30</b><span>leg tops ~13:23 — close gives half back</span></div></div>
</div>

<div class="panel">{c_main}</div>

<div class="minis">
  <div class="panel">{c_gap}</div>
  <div class="panel">{c_exit}</div>
  <div class="panel">{c_mae}</div>
</div>

<div class="warnline"><b>⚠ IN-SAMPLE, ONE YEAR (+32% drift regime), n=47 → 19 with the PM check.</b>
 Not validated — each refinement round deepens selection bias. Goes live only if it survives 2022–24
 out-of-sample. Risk ≤1% equity vs the stop. Costs modelled 1 tick/side.</div>
</div></body></html>"""
    path = OUT / "gap_onepage.html"
    path.write_text(html, encoding="utf-8")
    print(f"[gap_onepage] wrote {path} ({path.stat().st_size//1024} KB)")
    return path


if __name__ == "__main__":
    build()
