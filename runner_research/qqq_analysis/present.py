"""
present.py — Self-contained web PRESENTATION (slide deck) of the findings.

Different from dashboard.html (a chart grid): this is a curated narrative deck —
one idea per slide, big takeaway + supporting chart, keyboard/click navigation.
Dark trading-terminal theme. Plotly inlined once -> works fully offline.

Output: output/presentation.html
"""
from __future__ import annotations
from pathlib import Path
import plotly.io as pio

from analytics import run_all
import binning
import persistence
import patterns
import report as R

OUT = Path(__file__).resolve().parent / "output"
BG, PANEL, GRID, FG = R.BG, R.PANEL, R.GRID, R.FG
GREEN, RED, AMBER, BLUE, PURPLE = R.GREEN, R.RED, R.AMBER, R.BLUE, R.PURPLE


def _chart(fig, first=False):
    fig.update_layout(autosize=True, height=None, margin=dict(l=60, r=30, t=60, b=50))
    return pio.to_html(fig, include_plotlyjs=(True if first else False),
                       full_html=False, config={"responsive": True, "displayModeBar": False})


def build():
    res, m, d = run_all()
    res.update(binning.run(write=False))
    res.update(persistence.run(write=False))
    res.update(patterns.run(write=False))
    A = res["A_minute_profile"]; Bs = res["B_timing_summary"]
    C = res["C_or_mechanics"]; Dr = res["D_reversal_summary"]; Dg = res["D_gapfill_summary"]
    Drace = res["D_race_test"]
    Es = res["E_summary"].iloc[0]; Eb = res["E_pivot_buckets"]
    Fs = res["F_stability_summary"].iloc[0]; Fh = res["F_halves_summary"]
    Gs = res["G_summary"].iloc[0]; Gsz = res["G_cluster_sizes"]

    open_rng = A.loc[A.minute_index == 0, "range_med"].iloc[0]
    lunch_rng = A.loc[(A.minute_index >= 180) & (A.minute_index <= 210), "range_med"].median()
    close_rng = A.loc[A.minute_index == 389, "range_med"].iloc[0]
    open_vol = A.loc[A.minute_index == 0, "vol_med"].iloc[0] / 1e3
    close_vol = A.loc[A.minute_index == 389, "vol_med"].iloc[0] / 1e3

    # ---- build charts
    c_avg = _chart(R.fig_avg_path(m), first=True)
    c_smile = _chart(R.fig_A_volsmile(A))
    c_hodlod = _chart(R.fig_B_timing(res["B_timing_minutes"]))
    c_piv = _chart(R.fig_E_pivots(res["E_pivot_minutes"], Eb))
    c_pivz = _chart(R.fig_E_zscore(Eb))
    c_pdhl = _chart(R.fig_D_touch(res["D_touch_buckets"], res["D_race_test"]))
    c_or = _chart(R.fig_C_or(C))
    c_halves = _chart(R.fig_F_halves(res["F_minute_profile_halves"]))
    c_clusters = _chart(R.fig_G_clusters(res["G_cluster_median_paths"], Gsz))
    c_hstab = _chart(R.fig_H_stability(res["H_resolution_stability"]))
    c_hadapt = _chart(R.fig_H_adaptive(res["H_profile_adaptive"]))
    Hs = res["H_resolution_stability"].set_index("bin_min")
    c_idom = _chart(R.fig_I_domclock(res["I_dominant_swing_clock"]))
    c_ireg = _chart(R.fig_I_regime(res["I_regime_persistence"]))
    c_ipers = _chart(R.fig_I_persistence(res["I_signature_persistence"]))
    Ireg = res["I_regime_persistence"].set_index("feature")
    Isig = res["I_signature_persistence"]
    consec = Isig[Isig.test.str.startswith("consec")].iloc[0]
    c_jtax = _chart(R.fig_J_taxonomy(res["J_rule_taxonomy"]))
    c_jshape = _chart(R.fig_J_shapes(res["J_shape_median_paths"], res["J_shape_clusters"]))
    c_jmotif = _chart(R.fig_J_motifs(res["J_morning_motifs"]))
    Jt = res["J_rule_taxonomy"].set_index("category")
    Jer = res["J_early_recognition"].iloc[0]

    def slide(kicker, title, chart_html, bullets, tag=""):
        b = "".join(f"<li>{x}</li>" for x in bullets)
        return f"""<section class="slide">
          <div class="col-text">
            <div class="kicker">{kicker}</div>
            <h2>{title}</h2>
            <ul>{b}</ul>
            {f'<div class="tag {tag[0]}">{tag[1]}</div>' if tag else ''}
          </div>
          <div class="col-chart">{chart_html}</div>
        </section>"""

    # ---- cover
    cover = f"""<section class="slide cover">
      <div class="cover-inner">
        <div class="kicker">DATA-DRIVEN · TIME-OF-DAY · NO IMPOSED DAY TYPES</div>
        <h1>QQQ Intraday<br>Time-of-Day Patterns</h1>
        <p class="sub">1-minute RTH candles · 09:30–15:59 ET · 30 Jun 2025 → 30 Jun 2026<br>
        247 clean trading days · RTH-anchored VWAP · medians + IQR throughout</p>
        <div class="kpis">
          <div class="kpi"><span>{Bs.loc[0,'median_clock']}</span>median HOD</div>
          <div class="kpi"><span>{Bs.loc[1,'median_clock']}</span>median LOD</div>
          <div class="kpi"><span>{int(Es.total_pivots)}</span>ZigZag pivots</div>
          <div class="kpi"><span>{Drace.loc[0,'pct_reject_first']:.0f}%/{Drace.loc[1,'pct_reject_first']:.0f}%</span>PDH/PDL reject-race ≈ coin-flip</div>
        </div>
        <p class="hint">→  arrow keys / click / swipe to navigate</p>
      </div>
    </section>"""

    slides = [cover]

    slides.append(f"""<section class="slide list-slide">
      <div class="kicker">EXECUTIVE SUMMARY</div>
      <h2>Seven time-of-day findings</h2>
      <table class="big">
        <tr><th>#</th><th>Pattern</th><th>Number</th><th>Robust H1↔H2</th></tr>
        <tr><td>1</td><td><b>Volatility smile</b> — range dies into lunch, expands into close</td><td>${open_rng:.2f} → ${lunch_rng:.2f} → ${close_rng:.2f}</td><td class="ok">✅</td></tr>
        <tr><td>2</td><td><b>Volume U-shape</b></td><td>{open_vol:.0f}k → {close_vol:.0f}k</td><td class="ok">✅</td></tr>
        <tr><td>3</td><td><b>Reversals cluster at the open</b></td><td>{Eb.loc[0,'all_ratio_vs_unif']:.2f}× uniform · z={Eb.loc[0,'all_z']:.1f}</td><td class="ok">✅</td></tr>
        <tr><td>4</td><td><b>Bimodal HOD/LOD timing</b></td><td>HOD {Bs.loc[0,'median_clock']} · LOD {Bs.loc[1,'median_clock']}</td><td class="ok">✅</td></tr>
        <tr><td>5</td><td><b>Prior-day levels are NOT reversal magnets</b> (audit reversal)</td><td>reject-race: PDH {Drace.loc[0,'pct_reject_first']:.0f}% · PDL {Drace.loc[1,'pct_reject_first']:.0f}% vs control {Drace.loc[2,'pct_reject_first']:.0f}%</td><td class="bad">❌ refuted</td></tr>
        <tr><td>6</td><td><b>Opening-range breaks mostly fake out</b></td><td>{C.loc[0,'fakeout_rate']:.0f}% fakeout · {C.loc[0,'break_and_go_rate']:.0f}% go</td><td class="warn">⚠️</td></tr>
        <tr><td>7</td><td><b>Signed minute-return profile is noise</b></td><td>H1↔H2 corr {Fs.minute_profile_H1H2_corr:.2f}</td><td class="bad">❌</td></tr>
      </table>
    </section>""")

    slides.append(slide("A · THE AVERAGE DAY", "The median path barely drifts — but the envelope fans out",
        c_avg,
        ["The <b>median</b> intraday path stays within a few basis points of the open — no reliable directional drift.",
         "The <b>IQR band</b> widens steadily through the day: dispersion, not direction, is what accumulates.",
         "Trade the <i>range</i> and <i>timing</i>, not a presumed intraday trend."]))

    slides.append(slide("A · VOLATILITY SMILE", "Range and volume collapse into lunch, erupt into the close",
        c_smile,
        [f"Open 1-min range <b>${open_rng:.2f}</b> → lunch <b>${lunch_rng:.2f}</b> → close <b>${close_rng:.2f}</b>.",
         f"Volume U-shape: <b>{open_vol:.0f}k</b> at the open, ~65k at lunch, <b>{close_vol:.0f}k</b> into the 15:59 print.",
         "The single most robust, textbook-clean pattern in the dataset."],
        ("ok", "SURVIVES H1/H2")))

    slides.append(slide("B · EVENT TIMING", "Highs and lows are bimodal — open or close, rarely mid-day",
        c_hodlod,
        [f"Median HOD <b>{Bs.loc[0,'median_clock']}</b>, median LOD <b>{Bs.loc[1,'median_clock']}</b> — but each clusters in the <b>first or last 30 min</b>.",
         "When the high prints early, the low tends to print late (and vice-versa).",
         f"The day's largest leg most often <i>begins</i> by <b>{Bs.loc[2,'median_clock']}</b> — this is the data-driven 'early extreme → later reversal'."]))

    slides.append(slide("E · REVERSAL DETECTION (FOCUS)", "Algorithmic pivots concentrate hard at the open",
        c_piv,
        [f"ATR×{Es.k_atr:.0f} ZigZag labelled <b>{int(Es.total_pivots)} pivots</b> ({int(Es.pivots_per_day_med)}/day; median swing {Es.mag_pct_med:.2f}%).",
         "No manual tagging, no day-type bias — pure price action.",
         "Highs (green) and lows (red) share the same opening concentration; a weaker second cluster forms in the early afternoon."],
        ("ok", "PURE PRICE ACTION")))

    slides.append(slide("E · WHERE REVERSALS CONCENTRATE", "09:30–09:44 dominates every other window",
        c_pivz,
        [f"Binomial z vs a uniform distribution: the opening bucket hits <b>z ≈ {Eb.loc[0,'all_z']:.0f}</b> ({Eb.loc[0,'all_ratio_vs_unif']:.2f}× expected).",
         "Pivots are <i>never</i> placed at minute 0 (ZigZag needs a prior leg) — this is real opening churn at minutes ~3–11, not an anchoring artifact.",
         "Secondary bumps (13:15–14:45) mark the lunch-lull breakout, but far weaker."],
        ("ok", "EFFECT SIZE REPORTED")))

    slides.append(slide("D · PRIOR-DAY LEVELS — THE AUDIT REVERSAL", "\"Turns X% of touches\" was the movement base rate in disguise",
        c_pdhl,
        [f"The old criterion (≥1 ATR away within 30 min) fires from <b>any random minute 78–83%</b> of the time — so \"79–83% turn at PDH/PDL\" proved nothing.",
         f"Honest test — the <b>race</b>: from first touch, does 1-ATR rejection or 1-ATR breakthrough come first? Control ≈ 50/50.",
         f"<b>PDH: {Drace.loc[0,'pct_reject_first']:.0f}% reject — a coin flip.</b> PDL: {Drace.loc[1,'pct_reject_first']:.0f}% reject (z={Drace.loc[1,'z_vs_coinflip']:.1f}) — if anything, weak <i>continuation through</i> the prior low.",
         f"What survives: touch <i>timing</i> (morning-clustered) and gap-fill timing ({Dg.loc[0,'fill_rate_pct']:.0f}% fill, median <b>{Dg.loc[0,'fill_med_clock']}</b>). The levels get visited on a clock — they just don't turn price."],
        ("bad", "POPULAR BELIEF, REFUTED")))

    slides.append(slide("C · OPENING RANGE", "The break is more often a trap than a launch",
        c_or,
        [f"OR extremes break nearly every day, but <b>{C.loc[0,'fakeout_rate']:.0f}%</b> of first 5-min-OR breaks close back inside within 5 bars.",
         f"Only <b>{C.loc[0,'break_and_go_rate']:.0f}%</b> are clean break-and-go.",
         "The fade tendency is structural; which side ultimately wins is <i>not</i> predictable from time alone."],
        ("warn", "DIRECTION VARIES")))

    slides.append(slide("F · ROBUSTNESS (THE HONEST SLIDE)", "The signed minute-return profile is a regime artifact",
        c_halves,
        [f"First-half vs second-half minute-median returns correlate just <b>{Fs.minute_profile_H1H2_corr:.2f}</b> — essentially zero.",
         f"Daily range roughly <b>doubled</b> H1→H2 (${Fh.loc[0,'range_med']:.1f}→${Fh.loc[1,'range_med']:.1f}): a volatility-regime shift.",
         "Absolute-dollar patterns don't transfer; timing, shape and ATR-normalized patterns do. Never trade an individual minute."],
        ("bad", "DOES NOT SURVIVE")))

    slides.append(slide("H · PER-MINUTE vs BLOCKS", "Coarser bins aren't better — 5-min is the sweet spot",
        c_hstab,
        [f"Range &amp; volume repeat almost perfectly at <b>any</b> bin width (corr ≥0.98) — no coarsening needed.",
         f"Signed returns peak at <b>5-min</b> (corr {Hs.loc[5,'ret_H1H2_corr']:.2f}, 3× the 1-min value) then <b>collapse to negative at ≥15-min</b>.",
         "A uniform 15-min grid <i>destroys</i> the real return micro-structure. ATR-normalizing doesn't rescue it either."],
        ("warn", "MEASURED, NOT ASSUMED")))

    slides.append(slide("H · ADAPTIVE GRID + BOOTSTRAP CI", "Fine at open/close reveals a closing ramp-then-fade",
        c_hadapt,
        ["Adaptive grid: 1-min at the open &amp; close, 5-min ramps, 15-min midday — resolution where the signal lives.",
         "With bootstrap 95% CIs, several buckets become <b>significantly non-zero</b> (coloured bars).",
         "<b>15:47→15:57 ramp</b> (15:57 = +0.91 bps, 62% up) then a <b>significantly negative 15:59 close</b> (−0.67 bps) — the melt-up unwinding into the auction."],
        ("ok", "NEW SIGNIFICANT STRUCTURE")))

    slides.append(slide("G · EMERGENT ARCHETYPES (OPTIONAL)", "Days form a continuum, not clean types",
        c_clusters,
        [f"K-means on shape-normalized paths: silhouette picks <b>k={int(Gs.k_best)}</b> (score {Gs.silhouette_best:.2f}) — basically up-day vs down-day.",
         f"Cluster sizes: {', '.join(f'{int(r.n_days)} ({r.pct:.0f}%)' for _,r in Gsz.iterrows())}.",
         "The weak silhouette <i>confirms</i> the brief's premise: don't impose a day-type taxonomy. Discovery only."],
        ("warn", "OPTIONAL / DISCOVERY")))

    # ---- Analysis I arc: the user's "recurring reversal clock" hypothesis (v2.0, post-audit)
    dl = res["I_direction_linkage"].iloc[0]
    stab = res["I_clock_stability"]
    wk = res["I_weekday_recurrence"].iloc[0]
    slides.append(f"""<section class="slide list-slide">
      <div class="kicker">I · YOUR HYPOTHESIS — RE-TESTED &amp; UPGRADED (v2.0)</div>
      <h2>"Certain time blocks reverse — and repeat on later days, by day type"</h2>
      <table class="big">
        <tr><th>Claim</th><th>Verdict</th><th>Evidence</th></tr>
        <tr><td><b>1.</b> Reversals concentrate in certain blocks</td><td class="ok">✅ SUPPORTED</td><td>biggest leg <i>starts</i> 09:30–10:30 (67%), <i>ends</i> — the major turn — 10:00–11:00 (52%)</td></tr>
        <tr><td><b>1b.</b> The morning leg extends the opening drive (new)</td><td class="ok">✅ SUPPORTED</td><td>early legs match opening 30-min direction {dl.pct_same_dir_as_opening_drive:.0f}% (z={dl.z_vs_coinflip:.1f})</td></tr>
        <tr><td><b>1c.</b> The clock is stable across the year (new)</td><td class="ok">✅ STRONG</td><td>terminal turn in 10:00–11:00: {stab.iloc[0].end_in_1000_1100_pct}% (H1) vs {stab.iloc[1].end_in_1000_1100_pct}% (H2)</td></tr>
        <tr><td><b>2.</b> The <i>specific</i> block recurs on later days</td><td class="bad">❌ NOT SUPPORTED</td><td>consec-day cosine z={consec.z} (p={consec.p_value}); no weekly (lag-5) spike</td></tr>
        <tr><td><b>2b.</b> …incl. same weekday next week (new)</td><td class="bad">❌ NOT SUPPORTED</td><td>weekday-matched cos {wk.same_weekday_next_week_cos} ≈ random {wk.distant_random_cos}</td></tr>
        <tr><td><b>3a.</b> Volatility regime persists (hot→hot)</td><td class="ok">✅ STRONG</td><td>post-open range lag-1 autocorr {Ireg.loc['post-open range (vol)','lag1_autocorr']} (z={Ireg.loc['post-open range (vol)','z']})</td></tr>
        <tr><td><b>3b.</b> Reversal clock is regime-specific</td><td class="bad">❌ NOT SUPPORTED</td><td>hot days resemble each other no more than random</td></tr>
        <tr><td><b>3c.</b> Trending days cluster</td><td class="bad">❌ NOT SUPPORTED</td><td>trend-strength lag-1 autocorr {Ireg.loc['trend strength','lag1_autocorr']} (~0)</td></tr>
      </table>
      <p class="sub">Every test compares to a day-order <b>shuffle null</b>. Audit fix: the first pass reported the swing's <i>end</i> time labelled as its <i>start</i> — now both are separated.</p>
    </section>""")

    slides.append(slide("I · THE REVERSAL CLOCK, CORRECTED", "Launch 09:30–10:30 · extend the opening drive · turn 10:00–11:00",
        c_idom,
        ["The day's biggest leg <b>launches 09:30–10:30 on 67% of days</b> (blue bars; 09:30 block alone = 42%).",
         f"When it starts early it <b>extends the opening 30-min drive</b> — same direction <b>{dl.pct_same_dir_as_opening_drive:.0f}%</b> of the time (z={dl.z_vs_coinflip:.1f}), not a fade.",
         "It <b>terminates — the major reversal — at 10:00–11:00 on 52% of days</b> (amber bars): this is the block you've been seeing.",
         f"Rock-stable across the year: {stab.iloc[0].end_in_1000_1100_pct}% (H1) vs {stab.iloc[1].end_in_1000_1100_pct}% (H2)."],
        ("ok", "HYPOTHESIS 2.0 — CONFIRMED & SHARPENED")))

    slides.append(slide("I · WHY IT FEELS LIKE IT 'REPEATS'", "Volatility clusters — the magnitude repeats, not the timing",
        c_ireg,
        [f"Post-open range &amp; daily range are <b>strongly autocorrelated day-to-day (≈0.40, z&gt;6)</b>: hot days follow hot days.",
         "<b>Trend strength does NOT persist</b> (≈0) — a trend day doesn't beget another.",
         "Stable reversal clock × clustered big-volatility days = several dramatic days in a row at ~the same time → <i>feels</i> like a repeating block."]))

    slides.append(slide("I · BUT THE BLOCK DOESN'T ROTATE-AND-RECUR", "No day-specific block that reappears N days later",
        c_ipers,
        ["Block-level persistence sits inside the chance band at <b>every lag 1–10</b> — including lag 5 (a week).",
         f"The sharper weekday-matched test agrees: same-weekday-next-week similarity ({wk.same_weekday_next_week_cos}) ≈ distant-random ({wk.distant_random_cos}).",
         "So there's no evidence a block that reverses today is more likely to reverse again on a <i>specific</i> future day.",
         "<b>Takeaway:</b> trade the structural clock (opening drive → 10:00–11:00 turn) and the volatility regime — not a day-specific recurrence."],
        ("bad", "SHUFFLE-NULL: NOT DISTINCT")))

    # ---- Analysis J arc: pattern taxonomy
    slides.append(slide("J · DAY-TYPE TAXONOMY", "Reversal days outnumber trend days",
        c_jtax,
        [f"Transparent rules (trend = |O→C| ≥65% of range; reversal = early opposite extreme + close in far third).",
         f"<b>V-reversal up is the single most common day ({Jt.loc['V_reversal_up','pct_of_days']}%)</b>: early selloff → reverse → close high.",
         f"Reversal days total <b>~37%</b> vs trend days <b>~29%</b> vs chop <b>~16%</b>.",
         f"Trend-<i>down</i> days carry the biggest ranges (median ${Jt.loc['trend_down','range_med']:.2f}) — down moves are more violent."]))

    slides.append(slide("J · THE FIVE RECURRING SHAPES", "Data picks five soft archetypes — 60% up-family, 40% down-family",
        c_jshape,
        ["K-means on shape-normalized paths, named by their median path: <b>steady grind-up (29%)</b>, <b>early-top trend-down (23%)</b>, <b>fast morning rally &amp; hold (17%)</b>, <b>slow bleed into close (17%)</b>, <b>morning dip &amp; recover (14%)</b>.",
         "Silhouette ~0.17: boundaries are soft — days form a continuum, these are the ridges, not boxes.",
         "The shape mix drifts with regime (rally-hold is H2-heavy, dip-recover H1-heavy) — expect the census to move year to year."]))

    slides.append(slide("J · MORNING MOTIFS &amp; EARLY RECOGNITION", "\"Up-down-up\" is not a rhythm — and 11:00 can't see the afternoon",
        c_jmotif,
        ["Sign motifs of the three 30-min legs 09:30→11:00: <b>every motif matches the randomness null</b> (all |z| ≤ 1.1). Morning legs are serially independent.",
         f"Morning→afternoon continuation: <b>{Jer.P_afternoon_same_sign_as_morning_pct}%</b> (corr {Jer.corr_morning_vs_rest}) — a coin flip at every magnitude, both halves.",
         "A strong morning does raise P(day ends labelled 'trend day') to 45% vs 29% base — but that's <i>mechanical</i> (the morning IS most of the trend), not a forecast.",
         "<b>The taxonomy is hindsight, not foresight.</b> What's knowable live: volatility regime, the structural clock, time-of-day sizing."],
        ("warn", "DESCRIPTIVE, NOT PREDICTIVE")))

    slides.append(f"""<section class="slide list-slide">
      <div class="kicker">TAKEAWAYS & CAVEATS</div>
      <h2>What to trust</h2>
      <div class="two-col">
        <div>
          <h3 class="ok">Robust (H1 &amp; H2)</h3>
          <ul>
            <li>Volatility smile &amp; volume U-shape</li>
            <li>Reversals concentrate at the open (z≈{Eb.loc[0,'all_z']:.0f})</li>
            <li>Bimodal HOD/LOD timing</li>
            <li>Opening drive → 10:00–11:00 terminal turn ({res['I_clock_stability'].iloc[0].end_in_1000_1100_pct:.0f}%/{res['I_clock_stability'].iloc[1].end_in_1000_1100_pct:.0f}% by half)</li>
            <li>Opening-range fade tendency</li>
            <li>Volatility clustering day-to-day (0.44)</li>
          </ul>
        </div>
        <div>
          <h3 class="bad">Do NOT trust</h3>
          <ul>
            <li>Any "minute X drifts up" claim (corr {Fs.minute_profile_H1H2_corr:.2f})</li>
            <li><b>PDH/PDL as reversal magnets — refuted by the race test</b> ({Drace.loc[0,'pct_reject_first']:.0f}%/{Drace.loc[1,'pct_reject_first']:.0f}% ≈ coin-flip)</li>
            <li>Absolute-dollar magnitudes (range doubled mid-year)</li>
            <li>ZigZag as a real-time signal — it's a <i>retrospective</i> labeller</li>
          </ul>
          <h3 class="warn">Scope</h3>
          <ul><li>Single instrument (QQQ), single year. One volatility-regime shift inside the sample.</li></ul>
        </div>
      </div>
    </section>""")

    n = len(slides)
    dots = "".join(f'<button class="dot" data-i="{i}"></button>' for i in range(n))
    body = "".join(slides)

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QQQ Intraday Patterns — Presentation</title>
<style>
  :root{{--bg:{BG};--panel:{PANEL};--grid:{GRID};--fg:{FG};--green:{GREEN};--red:{RED};--amber:{AMBER};--blue:{BLUE}}}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:var(--bg);color:var(--fg);
    font-family:Consolas,Menlo,'SF Mono',monospace;overflow:hidden}}
  #deck{{height:100vh;width:100vw}}
  .slide{{position:absolute;inset:0;padding:5vh 6vw;opacity:0;visibility:hidden;
    transition:opacity .45s ease;display:grid;grid-template-columns:38% 62%;gap:3vw;align-items:center}}
  .slide.active{{opacity:1;visibility:visible}}
  .slide.cover,.slide.list-slide{{display:block}}
  .kicker{{color:var(--amber);letter-spacing:3px;font-size:13px;margin-bottom:14px}}
  h1{{font-size:min(6vw,64px);line-height:1.05;margin:.1em 0;font-weight:700}}
  h2{{font-size:min(3.4vw,34px);line-height:1.15;margin:.1em 0 .6em;font-weight:600}}
  h3{{font-size:16px;margin:1em 0 .3em;letter-spacing:1px}}
  .col-text ul{{list-style:none;padding:0;margin:0}}
  .col-text li{{position:relative;padding-left:22px;margin:16px 0;font-size:clamp(14px,1.35vw,19px);line-height:1.5;color:#d7dee6}}
  .col-text li::before{{content:"▸";position:absolute;left:0;color:var(--blue)}}
  .col-chart{{height:82vh;background:var(--panel);border:1px solid var(--grid);border-radius:12px;padding:6px;overflow:hidden}}
  .col-chart .plotly-graph-div{{width:100%!important;height:100%!important}}
  b{{color:#fff}} i{{color:#9fb2c4}}
  .tag{{display:inline-block;margin-top:18px;padding:6px 14px;border-radius:20px;font-size:12px;letter-spacing:2px}}
  .tag.ok{{background:rgba(38,166,154,.15);color:var(--green);border:1px solid var(--green)}}
  .tag.warn{{background:rgba(255,183,77,.12);color:var(--amber);border:1px solid var(--amber)}}
  .tag.bad{{background:rgba(239,83,80,.12);color:var(--red);border:1px solid var(--red)}}
  /* cover */
  .cover-inner{{max-width:1000px;margin:8vh auto 0}}
  .sub{{color:#8b97a4;font-size:clamp(13px,1.4vw,18px);line-height:1.7;margin:1.4em 0}}
  .hint{{color:#5c6773;font-size:13px;margin-top:3em}}
  .kpis{{display:flex;flex-wrap:wrap;gap:16px;margin:2em 0 0}}
  .kpi{{background:var(--panel);border:1px solid var(--grid);border-radius:10px;padding:16px 22px;min-width:150px}}
  .kpi span{{display:block;font-size:28px;color:var(--amber);font-weight:700}}
  .kpi{{color:#8b97a4;font-size:13px;letter-spacing:1px}}
  /* tables / lists */
  table.big{{width:100%;border-collapse:collapse;margin-top:1em;font-size:clamp(12px,1.25vw,17px)}}
  table.big th,table.big td{{text-align:left;padding:12px 14px;border-bottom:1px solid var(--grid)}}
  table.big th{{color:#8b97a4;letter-spacing:1px;font-weight:600}}
  table.big td.ok,.ok{{color:var(--green)}} table.big td.warn,.warn{{color:var(--amber)}} table.big td.bad,.bad{{color:var(--red)}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:4vw;margin-top:1em}}
  .two-col ul{{padding-left:18px}} .two-col li{{margin:10px 0;line-height:1.5;color:#d7dee6}}
  /* chrome */
  #bar{{position:fixed;top:0;left:0;height:3px;background:var(--amber);width:0;z-index:50;transition:width .3s}}
  #nav{{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);display:flex;gap:14px;align-items:center;z-index:50}}
  #nav button.arw{{background:var(--panel);border:1px solid var(--grid);color:var(--fg);
    width:38px;height:38px;border-radius:50%;cursor:pointer;font-size:16px}}
  #nav button.arw:hover{{border-color:var(--amber);color:var(--amber)}}
  .dots{{display:flex;gap:7px}}
  .dot{{width:9px;height:9px;border-radius:50%;border:none;background:#33404d;cursor:pointer;padding:0}}
  .dot.on{{background:var(--amber)}}
  #count{{position:fixed;bottom:22px;right:26px;color:#5c6773;font-size:13px;z-index:50}}
  #title-tag{{position:fixed;top:16px;left:24px;color:#5c6773;font-size:12px;letter-spacing:2px;z-index:50}}
</style></head><body>
<div id="bar"></div>
<div id="title-tag">QQQ · INTRADAY TIME-OF-DAY PATTERNS</div>
<div id="deck">{body}</div>
<div id="count"></div>
<div id="nav">
  <button class="arw" id="prev">‹</button>
  <div class="dots">{dots}</div>
  <button class="arw" id="next">›</button>
</div>
<script>
  const slides=[...document.querySelectorAll('.slide')];
  const dots=[...document.querySelectorAll('.dot')];
  let i=0;
  function resizeCharts(el){{
    if(!window.Plotly) return;
    el.querySelectorAll('.plotly-graph-div').forEach(d=>{{try{{Plotly.Plots.resize(d);}}catch(e){{}}}});
  }}
  function show(n){{
    i=Math.max(0,Math.min(slides.length-1,n));
    slides.forEach((s,k)=>s.classList.toggle('active',k===i));
    dots.forEach((d,k)=>d.classList.toggle('on',k===i));
    document.getElementById('bar').style.width=((i)/(slides.length-1)*100)+'%';
    document.getElementById('count').textContent=(i+1)+' / '+slides.length;
    setTimeout(()=>resizeCharts(slides[i]),60);
  }}
  document.getElementById('next').onclick=()=>show(i+1);
  document.getElementById('prev').onclick=()=>show(i-1);
  dots.forEach(d=>d.onclick=()=>show(+d.dataset.i));
  document.addEventListener('keydown',e=>{{
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' ')show(i+1);
    if(e.key==='ArrowLeft'||e.key==='PageUp')show(i-1);
    if(e.key==='Home')show(0); if(e.key==='End')show(slides.length-1);
  }});
  let x0=null;
  document.addEventListener('touchstart',e=>x0=e.touches[0].clientX,{{passive:true}});
  document.addEventListener('touchend',e=>{{if(x0===null)return;
    const dx=e.changedTouches[0].clientX-x0; if(Math.abs(dx)>50)show(i+(dx<0?1:-1)); x0=null;}});
  // advance on click of chart-free area
  document.getElementById('deck').addEventListener('click',e=>{{
    if(e.target.closest('.col-chart,#nav,a,button'))return;
    show(i+1);
  }});
  window.addEventListener('resize',()=>resizeCharts(slides[i]));
  show(0);
</script>
</body></html>"""

    path = OUT / "presentation.html"
    path.write_text(html, encoding="utf-8")
    print(f"[present] wrote {path}  ({path.stat().st_size//1024} KB, {n} slides)")
    return path


if __name__ == "__main__":
    build()
