"""
onepage.py — THE one-page in-house playbook (for a trader with zero context).

Single self-contained HTML page, fits one screen / prints one landscape page.
Centerpiece: an annotated trade chart with TIMING (clock axis, deadlines) and LEVELS
(OR high/low, entry limit, stop) drawn exactly where they live.
Output: output/playbook_onepage.html
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent / "output"
G = "#26a69a"; R = "#ef5350"; A = "#ffb74d"; B = "#42a5f5"; P = "#ab47bc"
DIM = "#7d8895"; FA = "#5c6773"; GR = "#232b35"; PAN = "#12161c"


def x_of(hh, mm, x0=70, x1=1290):
    """clock -> x pixel; axis spans 09:30..11:05"""
    t = hh * 60 + mm
    return x0 + (t - 570) / (665 - 570) * (x1 - x0)


def main_chart():
    ORH, ORL = 150, 320                       # y pixels for the OR levels
    ENT = ORH + (ORL - ORH) * 0.25            # 25% back inside
    xs = x_of
    path = (f"M{xs(9,30)},{280} L{xs(9,36)},{240} L{xs(9,42)},{300} L{xs(9,48)},{200} "
            f"L{xs(9,54)},{265} L{xs(10,0)},{190} "
            f"L{xs(10,4)},{ORH-12} L{xs(10,8)},{ORH-38} "
            f"L{xs(10,13)},{ORH-6} L{xs(10,17)},{ENT} "
            f"L{xs(10,22)},{ORH-30} L{xs(10,30)},{ORH-60} L{xs(10,40)},{ORH-85} "
            f"L{xs(10,50)},{ORH-96} L{xs(10,59)},{ORH-104}")
    ticks = "".join(
        f'<line x1="{xs(h,m)}" y1="380" x2="{xs(h,m)}" y2="388" stroke="{FA}"/>'
        f'<text x="{xs(h,m)}" y="404" font-size="13" fill="{FA}" text-anchor="middle">{h:02d}:{m:02d}</text>'
        for h, m in [(9,30),(9,45),(10,0),(10,15),(10,30),(10,45),(11,0)])
    return f"""<svg viewBox="0 0 1400 470" style="width:100%">
      <rect x="{xs(9,30)}" y="{ORH}" width="{xs(10,0)-xs(9,30)}" height="{ORL-ORH}" fill="rgba(66,165,245,0.09)"/>
      <text x="{xs(9,31)}" y="{ORH+22}" font-size="14" fill="{B}">OPENING RANGE</text>
      <text x="{xs(9,31)}" y="{ORH+40}" font-size="12" fill="{FA}">first 30 min · typ. ~$3.6 wide</text>
      <line x1="{xs(9,30)}" y1="{ORH}" x2="1290" y2="{ORH}" stroke="{DIM}" stroke-width="1.6"/>
      <text x="1296" y="{ORH+4}" font-size="13" fill="{DIM}">OR HIGH</text>
      <line x1="{xs(9,30)}" y1="{ORL}" x2="1290" y2="{ORL}" stroke="{R}" stroke-width="1.6" stroke-dasharray="7,5"/>
      <text x="1296" y="{ORL+4}" font-size="13" fill="{R}">STOP</text>
      <line x1="{xs(10,0)}" y1="{ENT}" x2="1290" y2="{ENT}" stroke="{A}" stroke-width="1.6" stroke-dasharray="7,5"/>
      <text x="1296" y="{ENT+4}" font-size="13" fill="{A}">ENTRY</text>
      <line x1="{xs(10,30)}" y1="70" x2="{xs(10,30)}" y2="380" stroke="{A}" stroke-width="1.5" stroke-dasharray="4,4"/>
      <text x="{xs(10,30)-8}" y="86" font-size="13" fill="{A}" text-anchor="end">10:30 — cancel if not filled ▸</text>
      <line x1="{xs(10,59)}" y1="70" x2="{xs(10,59)}" y2="380" stroke="{G}" stroke-width="1.5" stroke-dasharray="4,4"/>
      <text x="{xs(10,59)-6}" y="86" font-size="13" fill="{G}" text-anchor="end">10:59 — exit everything</text>
      <path d="{path}" fill="none" stroke="{G}" stroke-width="3.2"/>
      <circle cx="{xs(10,4)}" cy="{ORH-12}" r="7" fill="{R}"/>
      <text x="{xs(10,4)-10}" y="{ORH-44}" font-size="14" fill="{R}" text-anchor="end">① BREAK — do NOT buy here</text>
      <text x="{xs(10,4)-10}" y="{ORH-26}" font-size="12" fill="{FA}" text-anchor="end">(1-min close above OR high, before 10:30)</text>
      <circle cx="{xs(10,17)}" cy="{ENT}" r="8" fill="{A}"/>
      <text x="{xs(10,17)+12}" y="{ENT+30}" font-size="14" fill="{A}">② YOUR FILL — limit sits 25% back inside the range</text>
      <text x="{xs(10,17)+12}" y="{ENT+48}" font-size="12" fill="{FA}">entry price = OR high − 0.25 × (OR high − OR low), placed the moment ① prints</text>
      <circle cx="{xs(10,59)}" cy="{ORH-104}" r="8" fill="{G}"/>
      <text x="{xs(10,59)-14}" y="{ORH-116}" font-size="14" fill="{G}" text-anchor="end">③ EXIT at 10:59 sharp</text>
      <line x1="{xs(9,30)}" y1="380" x2="1290" y2="380" stroke="{GR}" stroke-width="1.5"/>
      {ticks}
    </svg>"""


def short_strip():
    ORH, ORL = 40, 130
    ENT = ORL - (ORL - ORH) * 0.25
    xs = x_of
    path = (f"M{xs(9,30)},{75} L{xs(9,40)},{105} L{xs(9,50)},{60} L{xs(10,0)},{100} "
            f"L{xs(10,5)},{ORL+10} L{xs(10,9)},{ORL+30} L{xs(10,14)},{ORL+4} L{xs(10,18)},{ENT} "
            f"L{xs(10,26)},{ORL+28} L{xs(10,40)},{ORL+55} L{xs(10,59)},{ORL+68}")
    return f"""<svg viewBox="0 0 1400 230" style="width:100%">
      <rect x="{xs(9,30)}" y="{ORH}" width="{xs(10,0)-xs(9,30)}" height="{ORL-ORH}" fill="rgba(66,165,245,0.09)"/>
      <line x1="{xs(9,30)}" y1="{ORH}" x2="1290" y2="{ORH}" stroke="{R}" stroke-width="1.4" stroke-dasharray="7,5"/>
      <text x="1296" y="{ORH+4}" font-size="12" fill="{R}">STOP</text>
      <line x1="{xs(9,30)}" y1="{ORL}" x2="1290" y2="{ORL}" stroke="{DIM}" stroke-width="1.4"/>
      <text x="1296" y="{ORL+4}" font-size="12" fill="{DIM}">OR LOW</text>
      <line x1="{xs(10,0)}" y1="{ENT}" x2="1290" y2="{ENT}" stroke="{A}" stroke-width="1.4" stroke-dasharray="7,5"/>
      <text x="1296" y="{ENT+4}" font-size="12" fill="{A}">ENTRY</text>
      <path d="{path}" fill="none" stroke="{R}" stroke-width="2.8"/>
      <circle cx="{xs(10,5)}" cy="{ORL+10}" r="6" fill="{R}"/>
      <circle cx="{xs(10,18)}" cy="{ENT}" r="7" fill="{A}"/>
      <circle cx="{xs(10,59)}" cy="{ORL+68}" r="7" fill="{G}"/>
      <text x="{xs(9,31)}" y="215" font-size="13" fill="{DIM}">SHORT — exact mirror: break BELOW OR low → limit 25% back up inside → stop = OR HIGH → exit 10:59.</text>
      <text x="{xs(10,32)}" y="72" font-size="13" fill="{A}">EXTRA GATE: shorts only if QQQ already moved ≥ 0.5% from</text>
      <text x="{xs(10,32)}" y="90" font-size="13" fill="{A}">today's open at the break. Slow morning ⇒ no shorts.</text>
    </svg>"""


def build():
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QQQ OR-break — one-page playbook</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;background:#0b0e11;color:#c9d1d9;font-family:Consolas,Menlo,'SF Mono',monospace;padding:22px 30px}}
  h1{{font-size:26px;margin:0 0 2px;font-weight:700}}
  .sub{{color:{DIM};font-size:13px;margin-bottom:14px}}
  .panel{{background:{PAN};border:1px solid {GR};border-radius:12px;padding:10px 14px;margin-bottom:12px}}
  .cols{{display:grid;grid-template-columns:1.25fr 1fr;gap:12px}}
  .rules li{{margin:7px 0;font-size:13.5px;line-height:1.5;color:#d7dee6}}
  .rules{{padding-left:20px;margin:6px 0}}
  b{{color:#fff}}
  .warn{{color:{A}}} .bad{{color:{R}}} .good{{color:{G}}}
  .statgrid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:4px}}
  .stat{{background:#171d25;border:1px solid {GR};border-radius:8px;padding:8px 10px;text-align:center}}
  .stat span{{display:block;font-size:19px;font-weight:700;color:{A}}}
  .stat{{font-size:11px;color:{DIM}}}
  h3{{font-size:14px;margin:2px 0 6px;font-weight:600;letter-spacing:1px}}
  .foot{{color:{FA};font-size:11px;line-height:1.5;margin-top:10px}}
  table{{width:100%;border-collapse:collapse;font-size:12.5px}}
  td{{padding:4px 6px;border-bottom:1px solid {GR};color:#d7dee6}}
  td:first-child{{color:{DIM};white-space:nowrap}}
  @media print{{body{{background:#fff;color:#000}} }}
</style></head><body>
<h1>QQQ opening-range break — the pullback trade <span style="color:{FA};font-size:15px;font-weight:400">· in-house playbook · one trade max per day · morning only</span></h1>
<div class="sub">You are NOT buying the breakout. You are letting the breakout happen, then buying the dip back toward the broken level, and selling before 11:00. That's the whole trade.</div>

<div class="panel">{main_chart()}</div>
<div class="panel">{short_strip()}</div>

<div class="cols">
  <div class="panel">
    <h3 class="warn">THE SEVEN RULES</h3>
    <ol class="rules">
      <li><b>09:30–10:00 — mark the box.</b> Note the high and low of the first 30 minutes (the "OR"). Typical width ≈ $3.6.</li>
      <li><b>Wait for the break.</b> First 1-minute <b>close</b> outside the box, any time before 10:30. No break by 10:30 → <b>no trade today</b> (~25% of days).</li>
      <li><b class="bad">Never take the break itself.</b> ~3 in 4 first breaks come back inside. Even the winners pull back before going.</li>
      <li><b>Place one limit order</b> 25% back inside the box (long: OR high − 0.25×range · short: OR low + 0.25×range). <b>Longs: any break. Shorts: only if QQQ is already ≥0.5% away from today's open</b> when it breaks.</li>
      <li><b>10:30 not filled → cancel. Done for the day.</b> Late fills are disproportionately the failures.</li>
      <li><b>Bracket it:</b> stop = the far side of the box. Exit <b>everything at 10:59</b> — win, lose, or flat. Do NOT exit early just because price touches the broken line again; that's normal (it happens on ~85% of winners).</li>
      <li><b>Size:</b> shares = (1% of account) ÷ (entry − stop). Never exceed 4× account value in notional.</li>
    </ol>
  </div>
  <div class="panel">
    <h3 class="good">WHAT TO EXPECT (1 year of data, 61 trades)</h3>
    <div class="statgrid">
      <div class="stat"><span>~5</span>trades / month</div>
      <div class="stat"><span>62%</span>winners</div>
      <div class="stat"><span>1 in 5</span>hit the stop</div>
      <div class="stat"><span>−3.8%</span>worst equity dip @1% risk</div>
      <div class="stat"><span>+11%</span>year, $10k @1% risk</div>
      <div class="stat"><span>~40min</span>avg time in trade</div>
    </div>
    <h3 style="margin-top:12px" class="warn">WHILE YOU'RE IN — the health meter</h3>
    <table>
      <tr><td>price stays within 25% of the box beyond your entry</td><td class="good">healthy — 8 or 9 in 10 of these trend</td></tr>
      <tr><td>price digs 50–75% back into the box</td><td class="warn">coin flip — let the bracket decide, don't add</td></tr>
      <tr><td>price crosses the whole box</td><td class="bad">dead — that's your stop, take it</td></tr>
      <tr><td>price loiters at the broken line after ~10:35</td><td class="warn">usually a loser — but do NOT exit on the touch; wait for stop or 10:59 (bailing there sells the low)</td></tr>
    </table>
    <h3 style="margin-top:12px" class="bad">NEVER</h3>
    <ol class="rules">
      <li>Never chase the breakout candle. Never re-enter after a stop. Never hold past 10:59 or overnight.</li>
      <li>Never trade the lunch hours; the afternoon is a different game this playbook does not cover.</li>
      <li>Never treat yesterday's high/low as a bounce point — tested, it's a coin flip.</li>
    </ol>
  </div>
</div>

<div class="foot">Basis: 247 trading days of QQQ 1-minute data (Jun 2025–Jun 2026), every rule tested against statistical nulls and split-year stability; backtest includes costs, pessimistic stop fills, and a causal short filter.
Status: validated on ONE year, IN-SAMPLE — treat sizes as provisional until the out-of-sample review clears. Internal use only · not investment advice · questions → research desk.</div>
</body></html>"""
    p = OUT / "playbook_onepage.html"
    p.write_text(html, encoding="utf-8")
    print(f"[onepage] wrote {p} ({p.stat().st_size//1024} KB)")


if __name__ == "__main__":
    build()
