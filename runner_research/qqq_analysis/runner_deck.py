"""
runner_deck.py — Web deck for Analyses S (runner-day precursors) + T (gap-down bounce).

Data-driven from output/tables/S_*.csv and T_*.csv (+ a rebuild of the S frame for the
up-leg histogram). Inline SVG, self-contained, offline. Output: output/runner_study.html
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"

GREEN = "#26a69a"; RED = "#ef5350"; AMBER = "#ffb74d"; BLUE = "#42a5f5"; PURPLE = "#ab47bc"
DIM = "#7d8895"; FAINT = "#5c6773"; GRIDC = "#1e2630"


def _clk(mi):
    t = 9 * 60 + 30 + int(mi)
    return f"{t // 60:02d}:{t % 60:02d}"


# ---------------------------------------------------------------- svg helpers
def bars_svg(values, labels, color, W=760, H=300, ylab="", highlight=None, fmt="{:.0f}",
             baseline=None, base_label=""):
    n = len(values)
    pad_l, pad_b, pad_t = 54, 44, 26
    bw = (W - pad_l - 20) / n * 0.72
    step = (W - pad_l - 20) / n
    vmax = max(max(values), 0.0001)
    vmin = min(min(values), 0)
    rng = vmax - vmin
    y0 = pad_t + (H - pad_t - pad_b) * (vmax / rng) if vmin < 0 else H - pad_b
    scale = (H - pad_t - pad_b) / rng
    out = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    out.append(f'<line x1="{pad_l}" y1="{y0}" x2="{W-10}" y2="{y0}" stroke="{GRIDC}" stroke-width="1.5"/>')
    for i, (v, lb) in enumerate(zip(values, labels)):
        x = pad_l + i * step + (step - bw) / 2
        h = abs(v) * scale
        y = y0 - h if v >= 0 else y0
        col = color if v >= 0 else RED
        if highlight is not None and i in highlight:
            col = AMBER
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,1):.1f}" rx="3" fill="{col}"/>')
        vy = y - 8 if v >= 0 else y + h + 16
        out.append(f'<text x="{x+bw/2:.1f}" y="{vy:.1f}" font-size="13" fill="{DIM}" text-anchor="middle">{fmt.format(v)}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{H-14}" font-size="12" fill="{FAINT}" text-anchor="middle">{lb}</text>')
    if baseline is not None:
        by = y0 - baseline * scale
        out.append(f'<line x1="{pad_l}" y1="{by:.1f}" x2="{W-10}" y2="{by:.1f}" stroke="{DIM}" stroke-width="1.2" stroke-dasharray="5,4"/>')
        out.append(f'<text x="{W-12}" y="{by-6:.1f}" font-size="12" fill="{DIM}" text-anchor="end">{base_label}</text>')
    if ylab:
        out.append(f'<text x="16" y="{pad_t+8}" font-size="12" fill="{FAINT}">{ylab}</text>')
    out.append("</svg>")
    return "".join(out)


def hist_svg(series, bins, color, W=760, H=300, xfmt=lambda e: f"{e:.1f}", ylab="days",
             vlines=None):
    cnt, edges = np.histogram(np.asarray(series, dtype=float), bins=bins)
    n = len(cnt)
    pad_l, pad_b, pad_t = 50, 46, 24
    step = (W - pad_l - 20) / n
    bw = step * 0.86
    vmax = max(cnt.max(), 1)
    scale = (H - pad_t - pad_b) / vmax
    y0 = H - pad_b
    out = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    out.append(f'<line x1="{pad_l}" y1="{y0}" x2="{W-10}" y2="{y0}" stroke="{GRIDC}" stroke-width="1.5"/>')
    for i, c in enumerate(cnt):
        x = pad_l + i * step + (step - bw) / 2
        h = c * scale
        out.append(f'<rect x="{x:.1f}" y="{y0-h:.1f}" width="{bw:.1f}" height="{max(h,0.5):.1f}" rx="2" fill="{color}" opacity="0.9"/>')
    tick_every = max(1, n // 8)
    for i in range(0, n + 1, tick_every):
        x = pad_l + i * step
        out.append(f'<text x="{x:.1f}" y="{H-14}" font-size="12" fill="{FAINT}" text-anchor="middle">{xfmt(edges[i])}</text>')
    if vlines:
        span = edges[-1] - edges[0]
        for xv, lab, col in vlines:
            x = pad_l + (xv - edges[0]) / span * (W - pad_l - 20 - (step - bw))
            out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{y0}" stroke="{col}" stroke-width="1.6" stroke-dasharray="5,4"/>')
            out.append(f'<text x="{x+6:.1f}" y="{pad_t+14}" font-size="13" fill="{col}">{lab}</text>')
    out.append(f'<text x="14" y="{pad_t+6}" font-size="12" fill="{FAINT}">{ylab}</text>')
    out.append("</svg>")
    return "".join(out)


def lines_svg(x, series, W=760, H=320, ylab="% from open", x_ticks=None):
    """series: list of (values, color, label)."""
    pad_l, pad_b, pad_t = 56, 44, 26
    all_v = np.concatenate([np.asarray(v, float) for v, *_ in series])
    vmin, vmax = np.nanmin(all_v), np.nanmax(all_v)
    m = (vmax - vmin) * 0.1
    vmin -= m; vmax += m
    sx = (W - pad_l - 16) / (x[-1] - x[0])
    sy = (H - pad_t - pad_b) / (vmax - vmin)
    out = [f'<svg viewBox="0 0 {W} {H}" style="width:100%">']
    y0 = H - pad_b - (0 - vmin) * sy
    out.append(f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{W-16}" y2="{y0:.1f}" stroke="{GRIDC}" stroke-width="1.5"/>')
    for tick in (x_ticks or []):
        tx = pad_l + (tick - x[0]) * sx
        out.append(f'<line x1="{tx:.1f}" y1="{pad_t}" x2="{tx:.1f}" y2="{H-pad_b}" stroke="{GRIDC}" stroke-width="1"/>')
        out.append(f'<text x="{tx:.1f}" y="{H-16}" font-size="12" fill="{FAINT}" text-anchor="middle">{_clk(tick)}</text>')
    for vals, col, lab in series:
        pts = " ".join(f"{pad_l+(xx-x[0])*sx:.1f},{H-pad_b-(v-vmin)*sy:.1f}"
                       for xx, v in zip(x, vals) if np.isfinite(v))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.2"/>')
    ly = pad_t + 6
    for vals, col, lab in series:
        out.append(f'<rect x="{pad_l+12}" y="{ly-9}" width="16" height="4" fill="{col}"/>')
        out.append(f'<text x="{pad_l+34}" y="{ly-4}" font-size="13" fill="{col}">{lab}</text>')
        ly += 20
    out.append(f'<text x="12" y="{pad_t+4}" font-size="12" fill="{FAINT}">{ylab}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- build
def build():
    s1 = pd.read_csv(TBL / "S_runner_precursors.csv")
    s2 = pd.read_csv(TBL / "S_runner_gap_buckets.csv")
    s0 = pd.read_csv(TBL / "S_runner_target_pctls.csv").iloc[0]
    t1 = pd.read_csv(TBL / "T_gapfade_timing.csv").iloc[0]
    th = pd.read_csv(TBL / "T_gapfade_leglow_hist.csv")
    t2 = pd.read_csv(TBL / "T_gapfade_timerules.csv")
    t3 = pd.read_csv(TBL / "T_gapfade_system_overlap.csv")
    t4 = pd.read_csv(TBL / "T_gapfade_paths.csv")

    # up-leg distribution for the target slide
    from runners import build_frame
    d = build_frame(pd.read_parquet(OUT / "daily.parquet"))
    upleg = d.up_leg_pct.dropna()

    # ---------------- charts
    c_upleg = hist_svg(upleg, bins=np.arange(0, 4.6, 0.25), color=BLUE,
                       xfmt=lambda e: f"{e:.1f}%", vlines=[
                           (float(s0.P80_full), f"P80 {s0.P80_full}%", AMBER),
                           (1.6, "1.6% (H2 P80)", GREEN)])

    prim = s1[s1.target == "Y_up_trail"].set_index("feature")
    feats = ["big_up1", "big_up2", "thrust_pause", "pause1", "up3", "prior_trend_up",
             "gap_up", "fomc", "nfp_rule"]
    flabs = ["big up\nt-1", "big up\nt-2", "thrust→\npause", "pause\nt-1", "3 up\ncloses",
             "trend day\nt-1", "gap\nup", "FOMC", "NFP*"]
    flabs = [x.replace("\n", " ") for x in flabs]
    c_lift = bars_svg([float(prim.loc[f, "diff_pp"]) for f in feats], flabs, GREEN,
                      ylab="Δ pp vs base", highlight=[feats.index("up3")], fmt="{:+.1f}",
                      baseline=0.0, W=860)

    gb = s2[(s2.col == "gap_over_prange") & (s2.target == "Y_up_trail")]
    c_gap = bars_svg(list(gb.rate_pct), ["Q1 big gap dn", "Q2", "Q3", "Q4", "Q5 big gap up"],
                     BLUE, ylab="% runner days", highlight=[0], fmt="{:.0f}%",
                     baseline=float(gb.base_pct.iloc[0]), base_label=f"base {gb.base_pct.iloc[0]:.0f}%")

    # leg-low histogram from saved 30-min bins
    c_when = bars_svg(list(th.n), [_clk(int(b.strip("[").split(",")[0])) for b in th.bin],
                      PURPLE, ylab="days", fmt="{:.0f}", W=860)

    mi = t4.minute.to_numpy()
    c_path = lines_svg(mi, [(t4.event_med_pct.to_numpy(), GREEN, f"big gap-down days (n={int(t1.n_event)})"),
                            (t4.rest_med_pct.to_numpy(), DIM, "all other days")],
                       x_ticks=[0, 60, 120, 180, 240, 300, 360])

    ev2 = t2[t2.group == "event"].set_index("rule")
    ct2 = t2[t2.group == "control"].set_index("rule")
    rules = ["open_to_1059", "1000_to_1059", "open_to_close", "1000_to_close"]
    rlabs = ["open→10:59", "10:00→10:59", "open→close", "10:00→close"]
    c_rules = bars_svg([float(ev2.loc[r, "med_bps"]) for r in rules], rlabs, GREEN,
                       ylab="median net bps (event days)", fmt="{:+.1f}",
                       highlight=[3], baseline=0.0)

    up3r = prim.loc["up3"]; tp = prim.loc["thrust_pause"]
    tpt = s1[(s1.feature == "thrust_pause") & (s1.target == "Y_trend_up")].iloc[0]
    b1t = s1[(s1.feature == "big_up1") & (s1.target == "Y_trend_up")].iloc[0]
    nfpw = s1[(s1.feature == "nfp_rule") & (s1.target == "Y_wide")].iloc[0]
    sys_ev = t3[t3.group == "event"].iloc[0]; sys_ne = t3[t3.group == "non_event"].iloc[0]

    def slide(kicker, title, body, tag=""):
        t = f'<div class="tag {tag[0]}">{tag[1]}</div>' if tag else ""
        return f'<section class="slide"><div class="inner"><div class="kicker">{kicker}</div><h2>{title}</h2>{body}{t}</div></section>'

    def rowslide(kicker, title, bullets, vis, tag=""):
        b = "".join(f"<li>{x}</li>" for x in bullets)
        t = f'<div class="tag {tag[0]}">{tag[1]}</div>' if tag else ""
        return f"""<section class="slide"><div class="row">
          <div class="txt"><div class="kicker">{kicker}</div><h2>{title}</h2><ul>{b}</ul>{t}</div>
          <div class="vis"><div class="panel">{vis}</div></div></div></section>"""

    slides = []
    slides.append(f"""<section class="slide"><div class="inner">
      <div class="kicker">ANALYSIS S + T · WHAT COMES BEFORE A RUNNER DAY · 247 DAYS</div>
      <h1>Yesterday's candles won't<br>tell you. The gap might.</h1>
      <p class="sub">Runner day = the biggest intraday up-leg (low → later high) clears the trailing
      80th percentile. We tested every prior-day (t-1..t-3) and overnight hypothesis with matched
      nulls, split-year checks and Bonferroni control.</p>
      <div class="pills">
        <div class="pill"><span>{s0.P80_full}%</span>P80 of the daily up-leg (1.6% = H2's P80)</div>
        <div class="pill"><span>1 / 10</span>features survive Bonferroni — and it's a NEGATIVE signal</div>
        <div class="pill"><span>{gb.rate_pct.iloc[0]:.0f}%</span>runner rate after a big gap DOWN (vs {gb.base_pct.iloc[0]:.0f}% base)</div>
        <div class="pill"><span>{t1.pct_low_before_1030:.0f}%</span>of gap-down bounce lows are set by 10:30</div>
      </div>
      <p class="sub" style="color:{FAINT};margin-top:3vh">→ arrow keys · click · swipe</p>
    </div></section>""")

    slides.append(rowslide("S0 · THE TARGET", "\"Hit 1.6%\" is the recent regime's P80",
        [f"Runner metric: the day's <b>maximum up-leg</b> — from any low to any later high (1-min bars).",
         f"Full-year P80 = <b>{s0.P80_full}%</b>, but the mid-year vol regime shift splits it: H1 <b>{s0.P80_H1}%</b> vs H2 <b>{s0.P80_H2}%</b> — your 1.6% is exactly H2's P80.",
         f"A fixed 1.6% bar tags only <b>{s0.fixed_1p6_hit_pct}%</b> of days across the year and would quietly select the loud half.",
         f"So the study's target is the <b>trailing 60-day P80</b> (causal, no look-ahead) — \"a big day by recent standards\". Fixed 1.6% kept as a robustness column."],
        c_upleg))

    slides.append(rowslide("S1 · THE HYPOTHESIS BATTERY", "Nine precursors, one survivor",
        [f"Bars: change in runner probability (pp vs {prim.diff_pp.notna().sum() and prim.base_pct.iloc[0]:.0f}% base) for each feature known before the open. n = 217 days after causal warm-up.",
         f"<b style='color:{AMBER}'>3 consecutive up closes</b> is the only Bonferroni survivor (m=10): runner rate <b>{up3r.rate_pct}% vs {up3r.base_pct}%</b>, p = {up3r.p_binom}, same sign in both halves — a <i>negative</i> signal.",
         f"Wide days collapse too ({s1[(s1.feature=='up3')&(s1.target=='Y_wide')].iloc[0].rate_pct}% vs {s1[(s1.feature=='up3')&(s1.target=='Y_wide')].iloc[0].base_pct}%): streaks predict <b>contraction</b>, echoing Phase 1's \"volatility clusters, direction doesn't\".",
         "Everything else fails the battery at Bonferroni level. The details that matter are on the next slides."],
        c_lift, ("warn", "m = 10 TESTS · BONFERRONI 0.005")))

    slides.append(slide("S1 · YOUR HYPOTHESES, SCORED", "Two dead, one alive-but-small",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card"><h3 style="color:{RED}">"Big up candle t-1 → runs today" — REFUTED</h3>
        <p>Runner rate 22.7% vs 27.2% base (n=22); trend-day rate <b>4.5% vs 17.5%</b>. And two big up
        candles in a row happened <b>once</b> all year — big days don't chain, they exhaust.</p></div>
        <div class="card"><h3 style="color:{AMBER}">"Thrust then pause → runs" — ALIVE, n=11</h3>
        <p>Big up candle at t-2 + small body at t-1: runner rate {tp.rate_pct}% (lift {tp.lift}), trend-day rate
        <b>{tpt.rate_pct}% vs {tpt.base_pct}%</b> (lift {tpt.lift}), same sign in both halves. p = {tpt.p_binom}, CI includes zero.
        The right shape of idea — needs the OOS years to reach a verdict.</p></div>
        <div class="card"><h3 style="color:{RED}">"Gap up is good" — INVERTED</h3>
        <p>Any gap up: runner rate {prim.loc['gap_up','rate_pct']}% vs {prim.loc['gap_up','base_pct']}% base. Big gap up (>0.2× prior range):
        ~16%. The "too much gap is bad" half of your hypothesis was right — but so is <i>moderate</i> gap up.
        The runners live on the <b>gap-down</b> side.</p></div>
        <div class="card"><h3 style="color:{BLUE}">"Econ releases → runs" — VOL ONLY</h3>
        <p>FOMC days (n=7): more range, no up-runs. NFP-rule days: wide-day rate <b>{nfpw.rate_pct}% vs {nfpw.base_pct}%</b>
        (p={nfpw.p_binom}) but direction ~nothing. News buys volatility, not direction.
        (Flags approximate — verified calendar is a Phase-2 item.)</p></div>
        </div>"""))

    slides.append(rowslide("S2 · THE GAP LADDER", "Runners are born gapping down",
        [f"Overnight gap scaled by yesterday's range, quintiles. Runner rate falls monotonically from <b>{gb.rate_pct.iloc[0]:.0f}%</b> (big gap down) to <b>{gb.rate_pct.iloc[4]:.0f}%</b> (big gap up).",
         f"Same-sign in both halves: Q1 = 31.6% / 48.0% vs base, Q5 = 5.3% / 12.0% (H1 / H2).",
         "Mechanically sensible: a gap-down hands the day a cheap low to run from; a gap-up has already spent the move.",
         f"<b>Regime warning:</b> this was a +32% drift year — \"buy the gap-down\" is what such a year rewards by construction. #1 OOS candidate (2022 bear year is the acid test)."],
        c_gap, ("warn", "REGIME-SUSPECT · VALIDATE OOS")))

    slides.append(rowslide("T1 · ANATOMY OF THE BOUNCE", "The low is set in the first 30 minutes",
        [f"Big gap-down days (gap ≤ −0.35× prior range): n = {int(t1.n_event)}, median gap {t1.med_gap_pct}%.",
         f"The up-leg's low is set at median minute <b>{int(t1.med_leg_low_min)}</b> ({_clk(int(t1.med_leg_low_min))}); <b>{t1.pct_low_before_1000}%</b> by 10:00, <b>{t1.pct_low_before_1030}%</b> by 10:30.",
         f"The leg tops out at median minute {int(t1.med_leg_high_min)} (<b>{_clk(int(t1.med_leg_high_min))}</b>) — the bounce is a morning entry, an afternoon exit.",
         f"{t1.pct_close_above_open}% close above the open, but only <b>{t1.pct_gap_filled}%</b> tag yesterday's close — trade the bounce, don't demand the gap fill."],
        c_when))

    slides.append(rowslide("T4 · THE MEDIAN DAY", "Two different sessions after the bell",
        [f"Median intraday path (% from open, 1-min): gap-down days grind <b>up and away</b> from the first half hour; other days are flat noise.",
         "The divergence starts right where the leg-lows cluster (09:30–10:00) and never mean-reverts intraday.",
         "This is the S2 gap ladder made visible — same data, no new claim."],
        c_path))

    slides.append(rowslide("T2 · CAN A CLOCK TRADE IT?", "Net of costs, the drift is real but left-tailed",
        [f"Pre-registered time rules on event days, 1 tick/side costs, vs the same rule on all other days (control).",
         f"open→close: median <b>{ev2.loc['open_to_close','med_bps']:+.1f} bps</b> (control {ct2.loc['open_to_close','med_bps']:+.1f}), hit {ev2.loc['open_to_close','hit_pct']:.0f}%. open→10:59: <b>{ev2.loc['open_to_1059','med_bps']:+.1f} bps</b>.",
         f"<b style='color:{AMBER}'>10:00→close is the most consistent</b>: {ev2.loc['1000_to_close','med_bps']:+.1f} bps median, H1 {ev2.loc['1000_to_close','med_H1']:+.1f} / H2 {ev2.loc['1000_to_close','med_H2']:+.1f} — the only rule healthy in both halves on both legs.",
         f"Means sit well below medians ({ev2.loc['open_to_close','mean_bps']:+.1f} vs {ev2.loc['open_to_close','med_bps']:+.1f}) — some gap-downs keep falling. Naked time-entries need a stop; n = {int(ev2.loc['open_to_close','n'])}."],
        c_rules, ("warn", "FAT LEFT TAIL — STOP REQUIRED")))

    slides.append(slide("T3 · DOES THE SYSTEM ALREADY OWN THIS?", "Gap-down days are the OR30 system's best days",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card"><h3 style="color:{GREEN}">On event days</h3><p>{int(sys_ev.n_trades)} system trades
        ({int(sys_ev.n_long)} long): median <b>{sys_ev.med_bps:+.1f} bps</b>, mean {sys_ev.mean_bps:+.1f},
        hit rate <b>{sys_ev.hit_pct:.0f}%</b>.</p></div>
        <div class="card"><h3 style="color:{DIM}">On all other days</h3><p>{int(sys_ne.n_trades)} trades:
        median {sys_ne.med_bps:+.1f} bps, mean {sys_ne.mean_bps:+.1f}, hit rate {sys_ne.hit_pct:.0f}%.</p></div>
        <div class="card"><h3 style="color:{AMBER}">Interpretation</h3><p>The break→pullback mechanics already
        harvest the bounce when it triggers — but it only triggers on {int(sys_ev.n_trades)}/{int(t1.n_event)} event days.
        A gap-down <i>size-up or standalone entry</i> is a natural Phase-2 pre-registered test.</p></div>
        <div class="card" style="border-color:rgba(255,183,77,.5)"><h3 style="color:{RED}">n = {int(sys_ev.n_trades)}</h3>
        <p>Eleven trades. This cell cannot be distinguished from luck on one year. Do not size up on this evidence.</p></div>
        </div>"""))

    slides.append(slide("STATUS", "What we'd take to Phase 2",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card"><h3 style="color:{AMBER}">1 · Gap-down → runner (S2/T)</h3><p>Strongest, most
        coherent finding: monotone ladder, both halves, visible in the median path, tradable with a clock.
        But it rhymes perfectly with a drift-year artifact. Verdict belongs to 2022–2024 data.</p></div>
        <div class="card"><h3 style="color:{AMBER}">2 · Streak contraction (S1)</h3><p>The only Bonferroni
        survivor: after 3 up closes, big legs and wide days both collapse. Use as a <i>filter</i> candidate
        (skip runner-hunting after streaks), not a trade.</p></div>
        <div class="card"><h3 style="color:{BLUE}">3 · Thrust → pause (S1)</h3><p>Your best original
        hypothesis. Lift ~2× on trend days, both halves, n=11. Pre-register and wait for OOS.</p></div>
        <div class="card"><h3 style="color:{DIM}">4 · Dead</h3><p>Big-candle continuation (inverted),
        gap-up momentum (inverted), econ-day direction (vol only). Same lesson as Phase 1:
        yesterday's <i>direction</i> tells you almost nothing about today's.</p></div>
        </div>
        <p class="sub" style="margin-top:2.5vh">Everything above is in-sample on 2025-26. Nothing is a
        proven edge. The OOS gate (HANDOFF §6) applies unchanged.</p>"""))

    n = len(slides)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Runner-Day Precursors — QQQ</title>
<style>
  :root{{--bg:#0b0e11;--panel:#12161c;--grid:#1e2630;--fg:#c9d1d9;--dim:#7d8895;--faint:#5c6773}}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:Consolas,Menlo,'SF Mono',monospace;overflow:hidden}}
  .slide{{position:absolute;inset:0;padding:5vh 6vw;opacity:0;visibility:hidden;transition:opacity .4s ease;display:flex;flex-direction:column;justify-content:center}}
  .slide.active{{opacity:1;visibility:visible}}
  .inner{{max-width:1250px;margin:0 auto;width:100%}}
  .kicker{{color:{AMBER};letter-spacing:3px;font-size:13px;margin-bottom:12px}}
  h1{{font-size:min(5.6vw,58px);line-height:1.06;margin:.1em 0;font-weight:700}}
  h2{{font-size:min(3.4vw,36px);line-height:1.15;margin:.1em 0 .5em;font-weight:600}}
  h3{{font-size:clamp(14px,1.5vw,19px);margin:0 0 6px;font-weight:600}}
  .sub{{color:var(--dim);font-size:clamp(13px,1.35vw,17px);line-height:1.65}}
  b{{color:#fff}} i{{color:#9fb2c4}}
  .pills{{display:flex;flex-wrap:wrap;gap:14px;margin-top:3vh}}
  .pill{{background:var(--panel);border:1px solid var(--grid);border-radius:10px;padding:13px 18px;min-width:150px;color:var(--dim);font-size:12px;letter-spacing:1px}}
  .pill span{{display:block;font-size:24px;color:{AMBER};font-weight:700}}
  .row{{display:flex;gap:3.5vw;align-items:center;max-width:1350px;margin:0 auto;width:100%}}
  .row>.txt{{flex:0 0 42%}}
  .row>.vis{{flex:1;min-width:0}}
  .panel{{background:var(--panel);border:1px solid var(--grid);border-radius:14px;padding:1.6vh 1.2vw}}
  ul{{list-style:none;padding:0;margin:0}}
  li{{position:relative;padding-left:20px;margin:13px 0;font-size:clamp(12px,1.25vw,17px);line-height:1.55;color:#d7dee6}}
  li::before{{content:"▸";position:absolute;left:0;color:{BLUE}}}
  .tag{{display:inline-block;margin-top:14px;padding:6px 14px;border-radius:20px;font-size:12px;letter-spacing:2px;border:1px solid}}
  .tag.ok{{color:{GREEN};border-color:{GREEN};background:rgba(38,166,154,.12)}}
  .tag.warn{{color:{AMBER};border-color:{AMBER};background:rgba(255,183,77,.12)}}
  .grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
  .card{{background:var(--panel);border:1px solid var(--grid);border-radius:12px;padding:16px 18px}}
  .card p{{margin:4px 0 0;color:var(--dim);font-size:clamp(12px,1.15vw,15px);line-height:1.55}}
  svg text{{font-family:Consolas,Menlo,monospace}}
  #bar{{position:fixed;top:0;left:0;height:3px;background:{AMBER};width:0;z-index:50;transition:width .3s}}
  #nav{{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);display:flex;gap:12px;align-items:center;z-index:50}}
  #nav button.arw{{background:var(--panel);border:1px solid var(--grid);color:var(--fg);width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:15px}}
  .dots{{display:flex;gap:6px}}
  .dot{{width:8px;height:8px;border-radius:50%;border:none;background:#33404d;cursor:pointer;padding:0}}
  .dot.on{{background:{AMBER}}}
  #count{{position:fixed;bottom:20px;right:24px;color:var(--faint);font-size:12px;z-index:50}}
  #brand{{position:fixed;top:14px;left:22px;color:var(--faint);font-size:11px;letter-spacing:2px;z-index:50}}
</style></head><body>
<div id="bar"></div><div id="brand">QQQ · RUNNER-DAY PRECURSORS · ANALYSES S + T</div>
{''.join(slides)}
<div id="count"></div>
<div id="nav"><button class="arw" id="prev">‹</button><div class="dots" id="dots"></div><button class="arw" id="next">›</button></div>
<script>
  const slides=[...document.querySelectorAll('.slide')];
  const dotsBox=document.getElementById('dots');
  slides.forEach((s,k)=>{{const b=document.createElement('button');b.className='dot';b.onclick=()=>show(k);dotsBox.appendChild(b);}});
  const dots=[...document.querySelectorAll('.dot')];
  let i=0;
  function show(n){{
    i=Math.max(0,Math.min(slides.length-1,n));
    slides.forEach((s,k)=>s.classList.toggle('active',k===i));
    dots.forEach((d,k)=>d.classList.toggle('on',k===i));
    document.getElementById('bar').style.width=(i/(slides.length-1)*100)+'%';
    document.getElementById('count').textContent=(i+1)+' / '+slides.length;
  }}
  document.getElementById('next').onclick=()=>show(i+1);
  document.getElementById('prev').onclick=()=>show(i-1);
  document.addEventListener('keydown',e=>{{
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' ')show(i+1);
    if(e.key==='ArrowLeft'||e.key==='PageUp')show(i-1);
    if(e.key==='Home')show(0); if(e.key==='End')show(slides.length-1);
  }});
  let x0=null;
  document.addEventListener('touchstart',e=>x0=e.touches[0].clientX,{{passive:true}});
  document.addEventListener('touchend',e=>{{if(x0===null)return;const dx=e.changedTouches[0].clientX-x0;if(Math.abs(dx)>50)show(i+(dx<0?1:-1));x0=null;}});
  document.addEventListener('click',e=>{{if(e.target.closest('#nav,a,button'))return;show(i+1);}});
  show(0);
</script></body></html>"""
    path = OUT / "runner_study.html"
    path.write_text(html, encoding="utf-8")
    print(f"[runner_deck] wrote {path} ({path.stat().st_size//1024} KB, {n} slides)")
    return path


if __name__ == "__main__":
    build()
