"""
or_playbook_deck.py — The complete OR-break playbook, LONG + SHORT, as a rich web deck.

Trader-friendly narrative; every chart computed from the Q/N/O tables at build time
(inline SVG, self-contained, offline). Output: output/or_playbook.html
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from or_deck import bars_svg, hist_svg, GREEN, RED, AMBER, BLUE, PURPLE, DIM, FAINT, GRIDC, _clk

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"


def build():
    qs = pd.read_csv(TBL / "Q_side_summary.csv")
    qr = pd.read_csv(TBL / "Q_side_rule_stack.csv")
    qh = pd.read_csv(TBL / "Q_side_health_meter.csv")
    ql = pd.read_csv(TBL / "Q_side_ladder_r25.csv")
    n15 = pd.read_csv(TBL / "N_days_or15.csv")

    def q(df, w, side, **kw):
        m = (df.or_window == w) & (df.side == side)
        for k, v in kw.items():
            m &= df[k] == v
        return df[m].iloc[0]

    L15 = q(qr, 15, "long_up_break", filter="none"); S15 = q(qr, 15, "short_down_break", filter="none")
    L30 = q(qr, 30, "long_up_break", filter="none"); S30 = q(qr, 30, "short_down_break", filter="none")
    S30d = q(qr, 30, "short_down_break", filter="strong drive (top tercile)")
    L30d = q(qr, 30, "long_up_break", filter="strong drive (top tercile)")

    # ---- charts
    c_sym = bars_svg(
        [q(qs, 15, "long_up_break").trend_to_11_pct, q(qs, 15, "short_down_break").trend_to_11_pct,
         q(qs, 30, "long_up_break").trend_to_11_pct, q(qs, 30, "short_down_break").trend_to_11_pct],
        ["long OR15", "short OR15", "long OR30", "short OR30"],
        GREEN, W=760, H=280, ylab="% of breaks trending to 11:00", fmt="{:.0f}%",
        colors=[GREEN, RED, GREEN, RED])
    c_retr = bars_svg(
        [q(qs, 15, "long_up_break").trendday_max_retrace_med_pct, q(qs, 15, "short_down_break").trendday_max_retrace_med_pct,
         q(qs, 30, "long_up_break").trendday_max_retrace_med_pct, q(qs, 30, "short_down_break").trendday_max_retrace_med_pct],
        ["long OR15", "short OR15", "long OR30", "short OR30"],
        BLUE, W=760, H=280, ylab="trend-day median max retracement (% of OR)", fmt="{:.0f}%")

    hl = qh[(qh.or_window == 15) & (qh.side == "long_up_break")]
    hs = qh[(qh.or_window == 15) & (qh.side == "short_down_break")]
    cols5 = [GREEN, GREEN, AMBER, RED, RED]
    c_hm_l = bars_svg(list(hl.p_trend_pct), list(hl.bucket), GREEN, W=760, H=250,
                      ylab="LONG · P(trend) %", colors=cols5, fmt="{:.0f}%")
    c_hm_s = bars_svg(list(hs.p_trend_pct), list(hs.bucket), GREEN, W=760, H=250,
                      ylab="SHORT · P(trend) %", colors=cols5, fmt="{:.0f}%")

    c_econ = bars_svg(
        [float(L15.mean_bps), float(S15.mean_bps), float(L30.mean_bps), float(S30.mean_bps),
         float(L30d.mean_bps), float(S30d.mean_bps)],
        ["L·15", "S·15", "L·30", "S·30", "L·30+drv", "S·30+drv"],
        "#37474f", W=780, H=300, ylab="rule stack, mean bps/trade (net, with stop)",
        colors=[GREEN, RED, GREEN, RED, GREEN, AMBER], fmt="{:+.1f}")

    t15 = n15[n15.trended]
    c_when = hist_svg(t15[t15.pb_when >= 0].pb_when if "pb_when" in t15 else pd.Series(dtype=float),
                      bins=np.arange(15, 92, 5), color=PURPLE, W=760, H=260,
                      xfmt=lambda e: _clk(e), ylab="trend days") if "pb_when" in t15 else None

    def slide(kicker, title, body, tag=""):
        t = f'<div class="tag {tag[0]}">{tag[1]}</div>' if tag else ""
        return f'<section class="slide"><div class="inner"><div class="kicker">{kicker}</div><h2>{title}</h2>{body}{t}</div></section>'

    def rowslide(kicker, title, bullets, vis, tag=""):
        b = "".join(f"<li>{x}</li>" for x in bullets)
        t = f'<div class="tag {tag[0]}">{tag[1]}</div>' if tag else ""
        return f"""<section class="slide"><div class="row">
          <div class="txt"><div class="kicker">{kicker}</div><h2>{title}</h2><ul>{b}</ul>{t}</div>
          <div class="vis"><div class="panel">{vis}</div></div></div></section>"""

    # mirrored anatomy
    anatomy = f"""<svg viewBox="0 0 1100 470" style="width:100%">
      <text x="60" y="30" font-size="15" fill="{GREEN}">LONG · break above OR high</text>
      <rect x="60" y="88" width="1010" height="1.5" fill="{GRIDC}"/>
      <rect x="60" y="150" width="1010" height="1.5" fill="{GRIDC}"/>
      <rect x="60" y="88" width="110" height="62" fill="rgba(66,165,245,0.08)"/>
      <path d="M65,130 L90,105 L112,140 L135,98 L168,80 L196,96 L222,128 L252,118 L285,96 L320,74 L370,58 L430,48 L520,44"
            fill="none" stroke="{GREEN}" stroke-width="3"/>
      <circle cx="168" cy="80" r="6" fill="{RED}"/><circle cx="222" cy="128" r="6" fill="{AMBER}"/>
      <text x="540" y="48" font-size="13" fill="{FAINT}">→ ride to 10:59</text>
      <text x="60" y="255" font-size="15" fill="{RED}">SHORT · break below OR low — the mirror</text>
      <rect x="60" y="300" width="1010" height="1.5" fill="{GRIDC}"/>
      <rect x="60" y="362" width="1010" height="1.5" fill="{GRIDC}"/>
      <rect x="60" y="300" width="110" height="62" fill="rgba(66,165,245,0.08)"/>
      <path d="M65,320 L90,345 L112,310 L135,352 L168,372 L196,354 L222,322 L252,332 L285,354 L320,378 L370,394 L430,404 L520,408"
            fill="none" stroke="{RED}" stroke-width="3"/>
      <circle cx="168" cy="372" r="6" fill="{RED}"/><circle cx="222" cy="322" r="6" fill="{AMBER}"/>
      <text x="540" y="412" font-size="13" fill="{FAINT}">→ ride to 10:59</text>
      <text x="520" y="255" font-size="13" fill="{FAINT}">red dot = first break (don't chase) · amber dot = 25% pullback entry</text>
    </svg>"""

    slides = []
    slides.append(f"""<section class="slide"><div class="inner">
      <div class="kicker">THE COMPLETE OR-BREAK PLAYBOOK · LONG + SHORT · 247 DAYS, SPLIT-YEAR VERIFIED</div>
      <h1>One structure.<br>Two directions.<br>Different gates.</h1>
      <p class="sub">The break-pullback-trend machine is symmetric. The pay, this year, was not.
      Longs trade the base rules; shorts demand a harder filter.</p>
      <div class="pills">
        <div class="pill"><span>50–56%</span>trend rate, both sides</div>
        <div class="pill"><span>~25%</span>trend-day retracement, both sides</div>
        <div class="pill"><span>{L30.mean_bps:+.1f} bps</span>long rule stack (OR30)</div>
        <div class="pill"><span>{S30d.mean_bps:+.1f} bps</span>short + strong drive (n=12!)</div>
      </div>
      <p class="sub" style="color:{FAINT};margin-top:3vh">→ arrow keys · click · swipe</p>
    </div></section>""")

    slides.append(slide("THE SHAPE OF THE TRADE", "Same anatomy, mirrored",
        f'<div class="panel">{anatomy}</div>'))

    slides.append(slide("THE SHARED RULE STACK", "Six rules, either direction",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card"><h3 style="color:{RED}">1 · Never chase the break</h3><p>First close beyond the OR extreme fakes out 74% of the time. Even winners retrace ~25% of the range. The break is information.</p></div>
        <div class="card"><h3 style="color:{AMBER}">2 · Rest the limit at 25%</h3><p>25% retracement of the OR, placed the moment the break prints. Fills ~9 in 10 eventual winners at a better price than chasing.</p></div>
        <div class="card"><h3 style="color:{BLUE}">3 · Cancel unfilled at 10:30</h3><p>Fills that would arrive later are disproportionately the reversals (OR30: +3.4 → +5.4 bps with the cutoff).</p></div>
        <div class="card"><h3 style="color:{PURPLE}">4 · Stop = far side of the OR</h3><p>Full traverse means the break failed (P(trend) collapses to ≤10%). Risk ≈ 0.75 × OR ≈ 15 bps. Never abort on a mere level touch — that sells the low.</p></div>
        <div class="card"><h3 style="color:{GREEN}">5 · Exit 10:59</h3><p>The day's leg terminates 10:00–11:00 on 52% of days. The turn window ends legs; it doesn't flip them.</p></div>
        <div class="card"><h3 style="color:{AMBER}">6 · Gate by drive</h3><p>Longs may trade the base stack. Shorts: only on strong opening-drive mornings (top tercile). See the economics slide.</p></div>
        </div>"""))

    slides.append(rowslide("SYMMETRY CHECK · STRUCTURE", "The machine works both ways",
        ["Trend-to-11:00 rate: <b>50–56% on every side × window</b> — no directional bias in the structure.",
         "Trend-day max retracement: <b>~19–26% of the OR both ways</b> — the 25% rung is right for shorts too.",
         "The depth health-meter is monotonic on both sides (next slide).",
         "Timing is shared: pullback bottoms cluster 09:54–10:17; the terminal turn window is 10:00–11:00 regardless of direction."],
        c_sym, ("ok", "STRUCTURE IS DIRECTION-BLIND")))

    slides.append(rowslide("SYMMETRY CHECK · DEPTH", "One health meter, two directions",
        ["P(trend | max retracement) decays monotonically for longs <b>93 → 80 → 48 → 27 → 3%</b>…",
         "…and for shorts <b>84 → 67 → 56 → 28 → 10%</b> (OR15 buckets 0–25 / 25–50 / 50–75 / 75–100 / >100%).",
         "Same rule both ways: <b>beyond ~60–75% retracement the break is dying; full traverse = dead.</b>",
         "This is why the far side of the OR is the stop, long or short."],
        f"{c_hm_l}<div style='height:10px'></div>{c_hm_s}"))

    slides.append(rowslide("THE ASYMMETRY · ECONOMICS", "Longs paid on the base rules. Shorts didn't.",
        [f"Full rule stack with stop — longs: <b>{L15.mean_bps:+.1f} bps (OR15)</b> / <b>{L30.mean_bps:+.1f} (OR30)</b>, both halves positive on OR30.",
         f"Shorts unfiltered: <b>{S15.mean_bps:+.1f} / {S30.mean_bps:+.1f} bps</b> at a 43–44% hit rate — thin, and OR15 flips between halves.",
         f"<b style='color:{AMBER}'>Shorts + strong drive (OR30): {S30d.mean_bps:+.1f} bps, {S30d.hit_pct:.0f}% hit, t = {S30d.t_stat}, halves {S30d.mean_H1:+.1f}/{S30d.mean_H2:+.1f}</b> — the biggest per-trade number in the study…",
         f"…on <b>n = {int(S30d.n_trades)}</b>. The most promising and least proven cell. A violent down-drive that still gives a 25% pullback has paid hard.",
         "Whether the long/short gap is structure or a drift-year artifact is exactly what Phase-2 OOS decides."],
        c_econ, ("warn", "GATE SHORTS BY DRIVE")))

    slides.append(rowslide("LONG PAGE", "The base trade",
        [f"Break above OR high by 10:30 → limit at 25% retracement → cancel 10:30 → stop at OR low → out 10:59.",
         f"OR15: <b>{L15.mean_bps:+.1f} bps</b>, {L15.hit_pct:.0f}% hit, {L15.p_offered_1R_pct:.0f}% of fills offer ≥1R, {L15.p_stop_first_pct:.0f}% stop out.",
         f"OR30: <b>{L30.mean_bps:+.1f} bps</b>, {L30.hit_pct:.0f}% hit — H1/H2 {L30.mean_H1:+.1f}/{L30.mean_H2:+.1f}, both positive.",
         f"Strong-drive filter lifts OR30 to {L30d.mean_bps:+.1f} bps (n={int(L30d.n_trades)}) — optional for longs, mandatory for shorts."],
        bars_svg([float(L15.mean_bps), float(L30.mean_bps), float(L30d.mean_bps)],
                 ["OR15 base", "OR30 base", "OR30 +drive"], GREEN, W=680, H=280,
                 ylab="mean bps/trade (net)", fmt="{:+.1f}"), ("ok", "TRADE THE BASE STACK")))

    slides.append(rowslide("SHORT PAGE", "Same skeleton, harder gate",
        [f"Break below OR low by 10:30 → limit at 25% retracement (a bounce <i>up</i> into the level) → cancel 10:30 → stop at OR high → out 10:59.",
         f"Unfiltered shorts were thin this year: {S15.mean_bps:+.1f}/{S30.mean_bps:+.1f} bps, hit 43–44% — <b>do not trade the base stack short</b>.",
         f"<b>Gate: top-tercile opening drive.</b> OR30 gated shorts: <b>{S30d.mean_bps:+.1f} bps, {S30d.hit_pct:.0f}% hit, {S30d.mean_H1:+.1f}/{S30d.mean_H2:+.1f} by half</b> — and only {S30d.p_stop_first_pct:.0f}% stop out.",
         f"Caveat in bold: <b>n = {int(S30d.n_trades)} trades</b>. This is a hypothesis with excellent manners, not a proven edge.",
         "Down moves are the violent ones (trend-down days carry the widest ranges) — when the gate opens, size for volatility."],
        bars_svg([float(S15.mean_bps), float(S30.mean_bps), float(S30d.mean_bps)],
                 ["OR15 base", "OR30 base", "OR30 +drive"], RED, W=680, H=280,
                 ylab="mean bps/trade (net)", colors=[RED, RED, AMBER], fmt="{:+.1f}"),
        ("warn", "STRONG DRIVE ONLY · n=12")))

    slides.append(slide("CHEAT SHEET · BOTH DIRECTIONS", "Print this",
        f"""<div class="grid2" style="margin-top:2vh">
        <div class="card" style="border-color:rgba(38,166,154,.5)"><h3 style="color:{GREEN}">LONG · base trade</h3>
          <p>break ↑ OR high by 10:30<br>limit at −25% of OR · cancel 10:30<br>stop = OR low · exit 10:59<br>
          expect: fill ~2/3 of breaks · ≥1R on ~40% of fills<br>{L15.mean_bps:+.1f}/{L30.mean_bps:+.1f} bps (OR15/30)</p></div>
        <div class="card" style="border-color:rgba(239,83,80,.5)"><h3 style="color:{RED}">SHORT · gated trade</h3>
          <p>break ↓ OR low by 10:30 <b>+ strong opening drive</b><br>limit at +25% of OR · cancel 10:30<br>stop = OR high · exit 10:59<br>
          skip entirely on weak-drive mornings<br>{S30d.mean_bps:+.1f} bps gated (n={int(S30d.n_trades)}) vs {S30.mean_bps:+.1f} ungated</p></div>
        <div class="card"><h3 style="color:{AMBER}">Shared health meter</h3>
          <p>retracement &lt;25% = healthy · 50–75% = dying · full traverse = dead (stop)<br>
          never abort on a late level touch — it sells the low</p></div>
        <div class="card"><h3 style="color:{BLUE}">Shared clock</h3>
          <p>break ~09:48–10:04 · pullback bottoms 09:54–10:17<br>terminal turn 10:00–11:00 (52% of days) · afternoon = new game (50/50)</p></div>
        </div>
        <p class="sub" style="margin-top:2vh;color:{FAINT}">247 clean days · medians+IQR · H1/H2 verified · costs 0.4 bps included ·
        all expectancies t &lt; 2.1 — Phase-2 out-of-sample validation before capital · past frequencies, not investment advice</p>"""))

    n = len(slides)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OR-Break Playbook — Long &amp; Short</title>
<style>
  :root{{--bg:#0b0e11;--panel:#12161c;--grid:#1e2630;--fg:#c9d1d9;--dim:#7d8895;--faint:#5c6773}}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:Consolas,Menlo,'SF Mono',monospace;overflow:hidden}}
  .slide{{position:absolute;inset:0;padding:5vh 6vw;opacity:0;visibility:hidden;transition:opacity .4s ease;display:flex;flex-direction:column;justify-content:center}}
  .slide.active{{opacity:1;visibility:visible}}
  .inner{{max-width:1250px;margin:0 auto;width:100%}}
  .kicker{{color:{AMBER};letter-spacing:3px;font-size:13px;margin-bottom:12px}}
  h1{{font-size:min(5.4vw,56px);line-height:1.06;margin:.1em 0;font-weight:700}}
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
  li{{position:relative;padding-left:20px;margin:12px 0;font-size:clamp(12px,1.22vw,16px);line-height:1.55;color:#d7dee6}}
  li::before{{content:"▸";position:absolute;left:0;color:{BLUE}}}
  .tag{{display:inline-block;margin-top:14px;padding:6px 14px;border-radius:20px;font-size:12px;letter-spacing:2px;border:1px solid}}
  .tag.ok{{color:{GREEN};border-color:{GREEN};background:rgba(38,166,154,.12)}}
  .tag.warn{{color:{AMBER};border-color:{AMBER};background:rgba(255,183,77,.12)}}
  .grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
  .card{{background:var(--panel);border:1px solid var(--grid);border-radius:12px;padding:16px 18px}}
  .card p{{margin:4px 0 0;color:var(--dim);font-size:clamp(12px,1.12vw,15px);line-height:1.6}}
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
<div id="bar"></div><div id="brand">QQQ · OR-BREAK PLAYBOOK · LONG + SHORT</div>
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
    path = OUT / "or_playbook.html"
    path.write_text(html, encoding="utf-8")
    print(f"[or_playbook] wrote {path} ({path.stat().st_size//1024} KB, {n} slides)")
    return path


if __name__ == "__main__":
    build()
