"""
or_deck.py — Rich visual web deck for Analysis M (OR-break -> pullback -> 11:00).

Data-driven: histograms and tournament bars are computed from output/tables/M_*.csv at build
time and rendered as inline SVG — self-contained, no plotly, opens offline.
Output: output/or_break_deck.html   (navigation identical to playbook.html)
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
def bars_svg(values, labels, color, W=760, H=300, ann=None, ylab="", highlight=None,
             neg_color=None, fmt="{:.0f}", colors=None):
    """Simple vertical bar chart. values: list of floats; labels under bars.
    colors: optional per-bar color list overriding `color`."""
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
        col = color if v >= 0 else (neg_color or RED)
        if colors is not None:
            col = colors[i]
        if highlight is not None and i in highlight:
            col = AMBER
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,1):.1f}" rx="3" fill="{col}"/>')
        vy = y - 8 if v >= 0 else y + h + 16
        out.append(f'<text x="{x+bw/2:.1f}" y="{vy:.1f}" font-size="13" fill="{DIM}" text-anchor="middle">{fmt.format(v)}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{H-14}" font-size="12" fill="{FAINT}" text-anchor="middle">{lb}</text>')
    if ylab:
        out.append(f'<text x="16" y="{pad_t+8}" font-size="12" fill="{FAINT}">{ylab}</text>')
    if ann:
        out.append(ann)
    out.append("</svg>")
    return "".join(out)


def hist_svg(series, bins, color, W=760, H=300, xfmt=lambda e: f"{e:.0f}", ylab="days",
             vlines=None, unit=""):
    """Histogram with annotated vertical lines: vlines=[(x_value,label,color)]."""
    cnt, edges = np.histogram(series.dropna(), bins=bins)
    n = len(cnt)
    pad_l, pad_b, pad_t = 50, 46, 24
    step = (W - pad_l - 20) / n
    bw = step * 0.86
    vmax = cnt.max()
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
        out.append(f'<text x="{x:.1f}" y="{H-16}" font-size="12" fill="{FAINT}" text-anchor="middle">{xfmt(edges[i])}</text>')
    if vlines:
        def x_of(v):
            return pad_l + (v - edges[0]) / (edges[-1] - edges[0]) * (n * step)
        for v, lab, col in vlines:
            x = x_of(v)
            out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{y0}" stroke="{col}" stroke-width="2" stroke-dasharray="6,4"/>')
            out.append(f'<text x="{x+6:.1f}" y="{pad_t+14}" font-size="13" fill="{col}">{lab}</text>')
    out.append(f'<text x="14" y="{pad_t+6}" font-size="12" fill="{FAINT}">{ylab}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- build
def build():
    base = pd.read_csv(TBL / "M_base_rates.csv")
    tour = pd.read_csv(TBL / "M_entry_tournament.csv")
    geo = pd.read_csv(TBL / "M_pullback_geometry.csv")
    d15 = pd.read_csv(TBL / "M_days_or15.csv")
    d5 = pd.read_csv(TBL / "M_days_or5.csv")
    d30 = pd.read_csv(TBL / "M_days_or30.csv")

    g15 = geo.set_index("or_window").loc[15]
    b15 = base[(base.or_window == 15) & (base.subset == "all breaks")].iloc[0]
    t15 = d15[d15.trended]
    t5 = d5[d5.trended]; t30 = d30[d30.trended]

    # ---- charts
    c_trend = bars_svg(
        [base[(base.or_window == w) & (base.subset == "all breaks")].trend_to_11_pct.iloc[0] for w in (5, 15, 30)],
        ["OR5", "OR15", "OR30"], GREEN, W=520, H=260, ylab="% trend to 11:00", fmt="{:.0f}%")
    c_updown = bars_svg(
        [base[(base.or_window == 5) & (base.subset == "up breaks")].ext_med_atr.iloc[0],
         base[(base.or_window == 5) & (base.subset == "down breaks")].ext_med_atr.iloc[0],
         base[(base.or_window == 15) & (base.subset == "up breaks")].ext_med_atr.iloc[0],
         base[(base.or_window == 15) & (base.subset == "down breaks")].ext_med_atr.iloc[0]],
        ["OR5 up", "OR5 down", "OR15 up", "OR15 down"], GREEN, W=520, H=260,
        ylab="median extension (ATR)", fmt="{:.1f}")

    c_depth = hist_svg(t15.pb_depth_atr, bins=np.arange(-1, 13, 1), color=BLUE, W=780, H=320,
                       xfmt=lambda e: f"{e:.0f}", ylab="trend days",
                       vlines=[(0, "OR level", AMBER),
                               (float(t15.pb_depth_atr.median()), f"median {t15.pb_depth_atr.median():.1f} ATR inside", RED)])
    c_when = hist_svg(t15[t15.pb_when >= 0].pb_when, bins=np.arange(15, 92, 5), color=PURPLE, W=780, H=320,
                      xfmt=lambda e: _clk(e), ylab="trend days",
                      vlines=[(float(t15[t15.pb_when >= 0].pb_when.median()),
                               f"median {_clk(int(t15[t15.pb_when>=0].pb_when.median()))}", AMBER)])

    tt = tour[tour.or_window == 15].set_index("entry")
    order = ["E1_immediate", "E2_confirm2", "E3_hold5", "E4_or_retest", "E5_vwap_pullback"]
    lbl = ["chase the\nbreak", "2-bar\nconfirm", "hold\n5 bars", "OR-level\nretest", "VWAP\npullback"]
    c_tour15 = bars_svg([float(tt.loc[o, "mean_bps"]) for o in order],
                        [l.replace("\n", " ") for l in lbl], "#37474f", W=780, H=300,
                        ylab="mean bps/trade (net, OR15)", highlight=[4], fmt="{:+.1f}")
    t30t = tour[tour.or_window == 30].set_index("entry")
    c_tour30 = bars_svg([float(t30t.loc[o, "mean_bps"]) for o in order],
                        [l.replace("\n", " ") for l in lbl], "#37474f", W=780, H=300,
                        ylab="mean bps/trade (net, OR30)", highlight=[4], fmt="{:+.1f}")
    e5_15 = tt.loc["E5_vwap_pullback"]; e5_30 = t30t.loc["E5_vwap_pullback"]

    # ---- Analysis N charts (retracement scale)
    try:
        ntd = pd.read_csv(TBL / "N_trend_by_depth.csv")
        nl = pd.read_csv(TBL / "N_limit_ladder.csv")
        n15 = ntd[ntd.or_window == 15]
        health_cols = [GREEN, GREEN, AMBER, RED, RED]
        c_health = bars_svg(list(n15.p_trend_pct), list(n15.bucket), GREEN, W=780, H=300,
                            ylab="P(trend) %", colors=health_cols, fmt="{:.0f}%")
        l30 = nl[nl.or_window == 30].set_index("retrace_pct")
        rungs = [0, 25, 38, 50, 62, 75, 100]
        c_ladder = bars_svg([float(l30.loc[r, "mean_bps"]) for r in rungs],
                            [f"{r}%" for r in rungs], "#37474f", W=780, H=300,
                            ylab="mean bps/trade (net, OR30 ladder)", highlight=[1, 3], fmt="{:+.1f}")
        HAVE_N = True
    except Exception:
        HAVE_N = False

    # ---- anatomy SVG (hand-drawn, annotated with the real stats)
    anatomy = f"""<svg viewBox="0 0 1100 430" style="width:100%">
      <rect x="60" y="150" width="1010" height="1.5" fill="{GRIDC}"/>
      <rect x="60" y="255" width="1010" height="1.5" fill="{GRIDC}"/>
      <text x="66" y="142" font-size="14" fill="{FAINT}">OR high</text>
      <text x="66" y="276" font-size="14" fill="{FAINT}">OR low</text>
      <rect x="60" y="150" width="120" height="105" fill="rgba(66,165,245,0.07)"/>
      <text x="66" y="172" font-size="13" fill="{BLUE}">opening</text>
      <text x="66" y="189" font-size="13" fill="{BLUE}">range</text>
      <rect x="620" y="30" width="240" height="380" fill="rgba(171,71,188,0.10)" stroke="{PURPLE}" stroke-dasharray="5,4"/>
      <text x="632" y="50" font-size="14" fill="#d29ce0">10:00–11:00 turn window</text>
      <path d="M65,225 L95,195 L120,240 L150,175 L175,215 L200,160 L228,142
               L258,168 L285,205 L310,238 L335,222
               L365,196 L395,150 L430,118 L470,96 L520,78 L570,66 L640,58 L700,54"
            fill="none" stroke="{GREEN}" stroke-width="3.5"/>
      <path d="M700,54 C740,52 780,62 820,74 L860,84" fill="none" stroke="{GREEN}" stroke-width="3.5" stroke-dasharray="7,5" opacity="0.8"/>
      <circle cx="228" cy="142" r="8" fill="{RED}"/>
      <text x="196" y="118" font-size="14" fill="{RED}">first break ~09:48</text>
      <text x="196" y="100" font-size="13" fill="{FAINT}">(74% close back inside)</text>
      <circle cx="310" cy="238" r="8" fill="{AMBER}"/>
      <path d="M310,300 L310,252" stroke="{AMBER}" stroke-width="2"/>
      <text x="236" y="322" font-size="14" fill="{AMBER}">pullback bottom ~09:54–10:17</text>
      <text x="236" y="341" font-size="13" fill="{FAINT}">median {g15.pb_depth_med_atr:.1f} ATR back inside · retests level {g15.retest_or_level_pct:.0f}%</text>
      <circle cx="700" cy="54" r="8" fill="#d29ce0"/>
      <text x="718" y="88" font-size="14" fill="#d29ce0">terminal turn (52% of days)</text>
      <path d="M395,150 L360,150" stroke="{AMBER}" stroke-width="2" marker-end="none" stroke-dasharray="3,3"/>
      <text x="368" y="392" font-size="14" fill="{GREEN}">ride the second approach → exit by 10:59</text>
      <rect x="352" y="372" width="14" height="8" fill="{GREEN}"/>
    </svg>"""

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
      <div class="kicker">ANALYSIS M · OR BREAK → PULLBACK → 11:00 · 247 DAYS</div>
      <h1>Don't buy the break.<br>Buy the pullback.</h1>
      <p class="sub">Morning opening-range breaks that trend into 11:00 — when to enter, at what level,
      and why chasing loses. Every number below is computed from the data, split-year checked.</p>
      <div class="pills">
        <div class="pill"><span>{b15.trend_to_11_pct:.0f}%</span>of first breaks trend to 11:00</div>
        <div class="pill"><span>{g15.retest_or_level_pct:.0f}%</span>of trend days retest the OR level</div>
        <div class="pill"><span>{_clk(int(t15[t15.pb_when>=0].pb_when.median()))}</span>median pullback bottom (OR15)</div>
        <div class="pill"><span>{e5_30.mean_bps:+.1f} bps</span>VWAP-pullback entry (OR30, net)</div>
      </div>
      <p class="sub" style="color:{FAINT};margin-top:3vh">→ arrow keys · click · swipe</p>
    </div></section>""")

    slides.append(slide("THE TRADE, END TO END", "Anatomy of a continuation morning",
        f'<div class="panel">{anatomy}</div>'
        f'<p class="sub" style="margin-top:1.5vh">Break → fakeout pullback → second approach → trend → the 10:00–11:00 terminal window. '
        f'The entry lives at the <b style="color:{AMBER}">amber dot</b>, not the <b style="color:{RED}">red one</b>.</p>'))

    slides.append(rowslide("M(a) · BASE RATES", "Half of first breaks carry to 11:00",
        [f"First break (close beyond the OR extreme, by 10:30) occurs on <b>96–99%</b> of days (OR5/15).",
         f"It reaches ≥1 ATR beyond the level at 10:59 on <b>~51–53%</b> — every OR window agrees.",
         "So the coin is fair on <i>whether</i> — the edge must come from <i>how you enter</i>."],
        c_trend))

    slides.append(rowslide("M(a) · DIRECTION ASYMMETRY", "This year, up-breaks travelled 3–4× further",
        [f"Median extension beyond the level at 10:59: OR5 <b>up +2.8 ATR</b> vs <b>down +0.6 ATR</b>.",
         "A drift-year artifact until proven otherwise — sub-slices by side flip between halves.",
         "Treat direction symmetrically in rules; let Phase-2 OOS decide if the asymmetry is real."],
        c_updown, ("warn", "REGIME-SUSPECT")))

    slides.append(rowslide("M(c) · THE FAKEOUT IS NORMAL", "Even trend days come back — deep",
        [f"Distribution of the deepest pullback after the break, on days that <i>did</i> trend (OR15, n={int(g15.n_trend_days)}).",
         f"<b>{g15.retest_or_level_pct:.0f}%</b> retest the OR level; median goes <b>{g15.pb_depth_med_atr:.1f} ATR back inside the range</b> (q75 {g15.pb_depth_q75_atr:.1f}).",
         f"Only <b>{g15.straight_run_pct:.0f}%</b> run straight without a meaningful pullback.",
         "A limit at the OR level fills ~9 out of 10 winners — chasing pays a premium for the other 1."],
        c_depth, ("ok", "PLACE THE LIMIT, DON'T CHASE")))

    slides.append(rowslide("M(c) · WHEN THE PULLBACK BOTTOMS", "The entry window is 09:45–10:15",
        [f"Timing of the pullback low on OR15 trend days: median <b>{_clk(int(t15[t15.pb_when>=0].pb_when.median()))}</b>, IQR {_clk(int(t15[t15.pb_when>=0].pb_when.quantile(.25)))}–{_clk(int(t15[t15.pb_when>=0].pb_when.quantile(.75)))}.",
         f"OR5 trend days bottom earlier (median {_clk(int(t5[t5.pb_when>=0].pb_when.median()))}), OR30 later (median {_clk(int(t30[t30.pb_when>=0].pb_when.median()))}).",
         "Minutes after the fakeout-prone first break — and just before the leg that terminates 10:00–11:00.",
         "Patience window ≈ 15–25 minutes. If no pullback comes, the straight-runners (~8%) leave without you — accept it."],
        c_when))

    slides.append(rowslide("M(b) · ENTRY TOURNAMENT (OR15)", "Chasing and confirming both lose",
        ["Five entry rules, same exit (10:59 close), net 0.4 bps, no look-ahead.",
         f"Chase the break: <b>{tt.loc['E1_immediate','mean_bps']:+.1f} bps</b> and flips sign between halves. 2-bar confirm: <b>{tt.loc['E2_confirm2','mean_bps']:+.1f}</b>. Waiting without a pullback just worsens the price.",
         f"OR-level retest: fills {tt.loc['E4_or_retest','fill_rate_pct']:.0f}%, ~breakeven — right level, but it also catches the fakeout days.",
         f"<b style='color:{AMBER}'>VWAP pullback: {tt.loc['E5_vwap_pullback','mean_bps']:+.1f} bps, positive in BOTH halves ({tt.loc['E5_vwap_pullback','mean_H1']:+.1f}/{tt.loc['E5_vwap_pullback','mean_H2']:+.1f})</b> — and the lowest adverse excursion ({tt.loc['E5_vwap_pullback','mae_med_atr']:.1f} vs {tt.loc['E1_immediate','mae_med_atr']:.1f} ATR)."],
        c_tour15))

    slides.append(rowslide("M(b) · ENTRY TOURNAMENT (OR30)", "The pattern repeats, louder",
        [f"Same tournament on the 30-min OR: VWAP pullback <b>{e5_30.mean_bps:+.1f} bps/trade, {e5_30.hit_pct:.0f}% hit, t = {e5_30.t_stat}</b>.",
         f"Positive in both halves ({e5_30.mean_H1:+.1f} / {e5_30.mean_H2:+.1f}) — the only entry family that survives the split anywhere.",
         f"Fill rate {t30t.loc['E5_vwap_pullback','fill_rate_pct']:.0f}%: VWAP isn't always tagged — the trade simply doesn't exist those days.",
         "t < 2 on 110 trades. A consistent lead, not a proven edge — 15 rule×window combos were tested, so selection bias is real."],
        c_tour30, ("warn", "LEAD — VALIDATE OOS")))

    if HAVE_N:
        n15g = pd.read_csv(TBL / "N_retrace_geometry.csv")
        tg = n15g[(n15g.or_window == 15) & (n15g.outcome == "trended")].iloc[0]
        fg = n15g[(n15g.or_window == 15) & (n15g.outcome == "failed")].iloc[0]
        slides.append(rowslide("N · THE RETRACEMENT SCALE (0–100% OF THE OR)", "Depth is a live health meter",
            [f"Rescale the pullback: 0% = the broken level, 100% = the far side of the range.",
             f"Trend days retrace a median <b>{tg.max_ret_med_pct:.0f}%</b> and essentially never traverse fully ({tg.full_traverse_pct:.0f}%). Failed breaks: median <b>{fg.max_ret_med_pct:.0f}%</b>, full traverse {fg.full_traverse_pct:.0f}%.",
             "P(trend) decays strictly with depth: <b>88% → 74% → 51% → 28% → 7%</b> across the buckets (OR15).",
             f"Practical rules: <b>beyond ~60–75% the break is probably dead</b>; the far side of the OR is the natural hard stop. (Descriptive scale — depth and outcome are partly linked by construction.)"],
            c_health, ("ok", "MONITOR DEPTH, NOT HOPE")))
        l25 = l30.loc[25]; l50 = l30.loc[50]
        slides.append(rowslide("N · THE LIMIT LADDER", "Shallow rungs earn; deep rungs are adverse selection",
            [f"Rest a limit at r% retracement (levels frozen at break time), exit 10:59, net of costs.",
             f"<b>Sweet spot 25–50%</b>: the only rungs positive in both halves — 25%: {l25.mean_bps:+.1f} bps ({l25.mean_H1:+.1f}/{l25.mean_H2:+.1f}), 50%: {l50.mean_bps:+.1f} bps ({l50.mean_H1:+.1f}/{l50.mean_H2:+.1f}), t≈1.0–1.3.",
             f"Deeper is NOT cheaper: P(day trends | filled) collapses from ~50% at the level to <b>7–8% at full traverse</b>. On OR15 every rung ≥62% loses outright; here on OR30 samples thin out (n≤51), 75% goes negative, and the +3.1 at 100% is n=17 noise.",
             f"Depth does buy tighter risk: median MAE {l30.loc[0,'mae_med_atr']:.1f} ATR at the level → {l50.mae_med_atr:.1f} ATR at 50%. Fill rates: {l25.fill_rate_pct:.0f}% at 25%, {l50.fill_rate_pct:.0f}% at 50%."],
            c_ladder, ("warn", "t < 2 — VALIDATE OOS")))

    slides.append(slide("THE DISTILLED RULE", "The pullback playbook",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card"><h3 style="color:{RED}">1 · Never chase</h3><p>The first close beyond the OR extreme is 74% likely to come back — and even eventual winners retrace a median {g15.pb_depth_med_atr:.1f} ATR back inside. The break is information, not an entry.</p></div>
        <div class="card"><h3 style="color:{AMBER}">2 · Place, don't take</h3><p>Limit at the OR level (fills {g15.retest_or_level_pct:.0f}% of winners) or wait for the session-VWAP tag — the best-tested definition of "deep enough".</p></div>
        <div class="card"><h3 style="color:{BLUE}">3 · The window is 09:45–10:15</h3><p>That's where pullback bottoms cluster. No pullback by then? The ~8% straight-runners leave without you. Accept it.</p></div>
        <div class="card"><h3 style="color:{GREEN}">4 · Direction = the drive</h3><p>Trade the break's own direction (it extends the opening drive 82% of the time). Both sides — the up/down asymmetry is regime-suspect.</p></div>
        <div class="card"><h3 style="color:#d29ce0">5 · Out by 11:00</h3><p>The dominant leg terminates 10:00–11:00 on 52% of days. Exit 10:59 was the tested rule; trailing beyond needs a fresh reason.</p></div>
        <div class="card" style="border-color:rgba(255,183,77,.5)"><h3 style="color:{AMBER}">6 · It's a lead</h3><p>Best variant: +4.6 bps net, t = 1.41, one year, one instrument. Phase-2 out-of-sample validation before capital — no exceptions.</p></div>
        </div>"""))

    n = len(slides)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OR-Break Pullback Study — QQQ</title>
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
<div id="bar"></div><div id="brand">QQQ · OR-BREAK PULLBACK STUDY · ANALYSIS M</div>
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
    path = OUT / "or_break_deck.html"
    path.write_text(html, encoding="utf-8")
    print(f"[or_deck] wrote {path} ({path.stat().st_size//1024} KB, {n} slides)")
    return path


if __name__ == "__main__":
    build()
