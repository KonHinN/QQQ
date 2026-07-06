"""
report.py — Build deliverables from analytics results:
  1. output/tables/*.csv         (every aggregate table)
  2. output/QQQ_intraday_tables.xlsx   (one sheet per analysis A-G)
  3. output/dashboard.html       (self-contained dark plotly dashboard)
  4. output/FINDINGS.md          (markdown findings report)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

from analytics import run_all, _clk, _bucket_order, N_MIN

OUT = Path(__file__).resolve().parent / "output"
TBL = OUT / "tables"
TBL.mkdir(parents=True, exist_ok=True)

# ---- dark trading-terminal palette
BG = "#0b0e11"; PANEL = "#12161c"; GRID = "#1e2630"; FG = "#c9d1d9"
GREEN = "#26a69a"; RED = "#ef5350"; AMBER = "#ffb74d"; BLUE = "#42a5f5"; PURPLE = "#ab47bc"
pio.templates["term"] = go.layout.Template(layout=dict(
    paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(color=FG, family="Consolas,Menlo,monospace", size=12),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
    colorway=[GREEN, RED, AMBER, BLUE, PURPLE],
))


# ======================================================== Excel (one sheet per A-G)
SHEET_MAP = {
    "A": ["A_minute_profile"],
    "B": ["B_timing_summary", "B_timing_buckets", "B_timing_minutes"],
    "C": ["C_or_mechanics"],
    "D": ["D_race_test", "D_reversal_summary", "D_open_position", "D_gapfill_summary",
          "D_touch_buckets", "D_gapfill_detail"],
    "E": ["E_summary", "E_dominant_windows", "E_pivot_buckets", "E_pivot_minutes", "E_pivots"],
    "F": ["F_stability_summary", "F_halves_summary", "F_weekday", "F_minute_profile_halves"],
    "G": ["G_summary", "G_kselect", "G_cluster_sizes", "G_cluster_median_paths", "G_cluster_labels"],
    "H": ["H_resolution_stability", "H_profile_adaptive", "H_profile_5min", "H_profile_15min"],
    "I": ["I_summary", "I_dominant_swing_clock", "I_dominant_swing_stickiness",
          "I_direction_linkage", "I_clock_stability", "I_weekday_recurrence",
          "I_signature_persistence", "I_regime_persistence", "I_regime_reversal_clock",
          "I_regime_repetition"],
    "J": ["J_rule_taxonomy", "J_shape_clusters", "J_shape_kselect", "J_morning_motifs",
          "J_motif_stability", "J_early_recognition", "J_early_recognition_detail",
          "J_rule_vs_shape", "J_rule_labels", "J_shape_labels"],
    "K": ["K_backtest"],
    "L": ["L_weekday_summary", "L_weekday_tests", "L_weekday_stability",
          "L_weekday_taxonomy", "L_weekday_clock"],
    "M": ["M_base_rates", "M_entry_tournament", "M_pullback_geometry"],
    "N": ["N_limit_ladder", "N_retrace_geometry", "N_trend_by_depth"],
    "O": ["O_cutoff_grid", "O_retest_time_outcome", "O_last_touch", "O_abort_test"],
    "P": ["P_definition_sweep", "P_trade_frame", "P_predictors", "P_money_test"],
    "Q": ["Q_side_summary", "Q_side_rule_stack", "Q_side_ladder_r25", "Q_side_health_meter"],
    "R": ["R_system_stats", "R_ledger"],
}
SHEET_TITLE = {
    "A": "A_minute_profile", "B": "B_event_timing", "C": "C_opening_range",
    "D": "D_priorday_levels", "E": "E_reversal_pivots", "F": "F_robustness", "G": "G_clustering",
    "H": "H_time_resolution", "I": "I_reversal_clock_persist", "J": "J_pattern_taxonomy",
    "K": "K_backtest", "L": "L_weekday", "M": "M_or_break_entries",
    "N": "N_retracement_ladder", "O": "O_time_filters", "P": "P_tradable_day",
    "Q": "Q_long_vs_short", "R": "R_system_backtest",
}


def write_tables_and_excel(res: dict):
    for name, df in res.items():
        df.to_csv(TBL / f"{name}.csv", index=False)
    xlsx = OUT / "QQQ_intraday_tables.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        for letter, names in SHEET_MAP.items():
            sheet = SHEET_TITLE[letter]
            row = 0
            for nm in names:
                df = res[nm]
                hdr = pd.DataFrame({f"# {nm}  (n_rows={len(df)})": []})
                hdr.to_excel(xw, sheet_name=sheet, startrow=row, index=False)
                row += 1
                df.to_excel(xw, sheet_name=sheet, startrow=row, index=False)
                row += len(df) + 3
    print(f"[report] wrote {xlsx}")
    return xlsx


# ======================================================== dashboard pieces
def fig_A_volsmile(A):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=A.clock, y=A.vol_med, name="Volume (median)", marker_color="#26343f",
                opacity=0.7, secondary_y=True)
    fig.add_scatter(x=A.clock, y=A.range_med, name="Range median", line=dict(color=AMBER, width=2))
    fig.add_scatter(x=A.clock, y=A.range_q75, name="Range Q75", line=dict(color=AMBER, width=0.5, dash="dot"))
    fig.add_scatter(x=A.clock, y=A.range_q25, name="Range Q25", line=dict(color=AMBER, width=0.5, dash="dot"),
                    fill="tonexty", fillcolor="rgba(255,183,77,0.10)")
    fig.update_xaxes(title="ET clock", nticks=14)
    fig.update_yaxes(title="1-min range ($)", secondary_y=False)
    fig.update_yaxes(title="volume", secondary_y=True, showgrid=False)
    fig.update_layout(template="term", title="A · Volatility smile & volume U-shape (247 clean days)",
                      legend=dict(orientation="h", y=1.12), height=420)
    return fig


def fig_A_contratio(A):
    col = [GREEN if v >= 0.5 else RED for v in A.cont_ratio.fillna(0.5)]
    fig = go.Figure()
    fig.add_bar(x=A.clock, y=A.cont_ratio - 0.5, marker_color=col, name="cont-0.5")
    fig.add_hline(y=0, line_color=FG, line_width=1)
    fig.update_yaxes(title="continuation ratio − 0.5", tickformat="+.2f")
    fig.update_xaxes(title="ET clock", nticks=14)
    fig.update_layout(template="term", height=360,
                      title="A · Continuation vs reversal of next minute (green=momentum, red=mean-revert)")
    return fig


def fig_path_heatmap(m):
    c = m[m.is_clean]
    piv = c.pivot_table(index="date", columns="minute_index", values="close").reindex(columns=np.arange(N_MIN)).dropna()
    path = piv.div(piv.iloc[:, 0], axis=0).sub(1).mul(100)
    fig = go.Figure(go.Heatmap(z=path.values, x=[_clk(i) for i in range(N_MIN)], y=path.index,
                               colorscale="RdYlGn", zmid=0, zmin=-2, zmax=2,
                               colorbar=dict(title="% from<br>open")))
    fig.update_layout(template="term", height=520, title="Intraday path heatmap — % from 09:30 open (rows=days)",
                      xaxis=dict(nticks=14), yaxis=dict(showticklabels=False, title="247 clean days"))
    return fig


def fig_avg_path(m):
    c = m[m.is_clean]
    piv = c.pivot_table(index="date", columns="minute_index", values="close").reindex(columns=np.arange(N_MIN)).dropna()
    path = piv.div(piv.iloc[:, 0], axis=0).sub(1).mul(100)
    med = path.median(); q25 = path.quantile(.25); q75 = path.quantile(.75)
    x = [_clk(i) for i in range(N_MIN)]
    fig = go.Figure()
    fig.add_scatter(x=x, y=q75, line=dict(width=0, color=BLUE), name="Q75", showlegend=False)
    fig.add_scatter(x=x, y=q25, line=dict(width=0, color=BLUE), name="IQR band", fill="tonexty",
                    fillcolor="rgba(66,165,245,0.15)")
    fig.add_scatter(x=x, y=med, line=dict(color=BLUE, width=2.5), name="Median path")
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=420, title="Average intraday path (median % from open) ± IQR band",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="% from open"))
    return fig


def fig_B_timing(Bmin):
    fig = go.Figure()
    fig.add_bar(x=Bmin.clock, y=Bmin.hod_count, name="HOD", marker_color=GREEN, opacity=0.8)
    fig.add_bar(x=Bmin.clock, y=-Bmin.lod_count, name="LOD", marker_color=RED, opacity=0.8)
    fig.update_layout(template="term", barmode="overlay", height=420,
                      title="B · When the day's HIGH (up) and LOW (down) occur — per-minute counts",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="day count (HOD + / LOD −)"))
    return fig


def fig_C_or(C):
    fig = go.Figure()
    w = C.or_window.astype(str) + "-min OR"
    fig.add_bar(x=w, y=C.break_and_go_rate, name="break & go", marker_color=GREEN)
    fig.add_bar(x=w, y=C.fakeout_rate, name="fakeout (back inside)", marker_color=RED)
    fig.update_layout(template="term", barmode="group", height=400,
                      title="C · Opening-range break quality: break-and-go vs fakeout (% of first breaks)",
                      yaxis=dict(title="% of breaking days"), xaxis=dict(title="opening-range window"))
    return fig


def fig_D_touch(Dtb, Drace):
    fig = make_subplots(rows=1, cols=2, column_widths=[0.55, 0.45],
                        subplot_titles=("First TRUE touch of PDH/PDL by time of day",
                                        "Race test: 1-ATR reject vs 1-ATR break first"))
    fig.add_bar(x=Dtb.bucket, y=Dtb.PDH_touch_count, name="PDH from below", marker_color=GREEN, row=1, col=1)
    fig.add_bar(x=Dtb.bucket, y=Dtb.PDL_touch_count, name="PDL from above", marker_color=RED, row=1, col=1)
    lab = {"PDH_touch": "PDH touch", "PDL_touch": "PDL touch",
           "control_random_minute": "control<br>(random minute)"}
    x = [lab[e] for e in Drace.event]
    fig.add_bar(x=x, y=Drace.pct_reject_first, name="% reject first", marker_color=AMBER,
                text=[f"{v:.0f}%<br>z={z:+.1f}" for v, z in zip(Drace.pct_reject_first, Drace.z_vs_coinflip)],
                textposition="outside", showlegend=False, row=1, col=2)
    fig.add_hline(y=50, line_color=FG, line_dash="dash", row=1, col=2,
                  annotation_text="coin-flip")
    fig.update_layout(template="term", barmode="stack", height=440,
                      title="D · Prior-day levels: touch timing is real — but the touch itself is a coin-flip race")
    fig.update_xaxes(nticks=14, row=1, col=1)
    fig.update_yaxes(title="touch count", row=1, col=1)
    fig.update_yaxes(title="% rejection wins the race", range=[0, 100], row=1, col=2)
    return fig


def fig_E_pivots(Emin, Ebuckets):
    fig = go.Figure()
    fig.add_bar(x=Emin.clock, y=Emin.high_pivot_count, name="high pivots", marker_color=GREEN, opacity=0.8)
    fig.add_bar(x=Emin.clock, y=-Emin.low_pivot_count, name="low pivots", marker_color=RED, opacity=0.8)
    fig.update_layout(template="term", barmode="overlay", height=440,
                      title="E · ZigZag reversal pivots by time of day (high + / low −) — ATR×3 threshold",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="pivot count"))
    return fig


def fig_E_zscore(Eb):
    fig = go.Figure()
    col = [GREEN if z >= 1.96 else (AMBER if z >= 0 else "#37474f") for z in Eb.all_z]
    fig.add_bar(x=Eb.bucket, y=Eb.all_z, marker_color=col, name="z")
    fig.add_hline(y=1.96, line_color=AMBER, line_dash="dash", annotation_text="p=0.05")
    fig.update_layout(template="term", height=360,
                      title="E · Pivot concentration vs uniform (binomial z by 15-min bucket)",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="z-score"))
    return fig


def fig_F_halves(Fprof):
    fig = go.Figure()
    fig.add_scatter(x=Fprof.clock, y=Fprof.H1, name="H1 (first half)", line=dict(color=BLUE, width=1.5))
    fig.add_scatter(x=Fprof.clock, y=Fprof.H2, name="H2 (second half)", line=dict(color=AMBER, width=1.5))
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=380,
                      title="F · Minute median return profile: H1 vs H2 stability check (bps)",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="median return (bps)"))
    return fig


def fig_G_clusters(Gpaths, Gsizes):
    fig = go.Figure()
    cols = [c for c in Gpaths.columns if c.startswith("m")]
    x = [_clk(int(c[1:])) for c in cols]
    palette = [GREEN, RED, AMBER, BLUE, PURPLE, "#26c6da", "#d4e157", "#ff7043"]
    for _, r in Gpaths.iterrows():
        cl = int(r["cluster"])
        n = int(Gsizes.loc[Gsizes.cluster == cl, "n_days"].iloc[0])
        pct = float(Gsizes.loc[Gsizes.cluster == cl, "pct"].iloc[0])
        fig.add_scatter(x=x, y=r[cols].values, name=f"cluster {cl} (n={n}, {pct}%)",
                        line=dict(color=palette[cl % len(palette)], width=2))
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=420,
                      title="G · Emergent day archetypes — median intraday path per k-means cluster",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="% from open"))
    return fig


def fig_H_stability(Hs):
    fig = go.Figure()
    fig.add_scatter(x=Hs.bin_min, y=Hs.ret_H1H2_corr, name="signed return", line=dict(color=BLUE, width=2.5),
                    mode="lines+markers")
    fig.add_scatter(x=Hs.bin_min, y=Hs.range_H1H2_corr, name="range", line=dict(color=AMBER, width=2), mode="lines+markers")
    fig.add_scatter(x=Hs.bin_min, y=Hs.volume_H1H2_corr, name="volume", line=dict(color=GREEN, width=2), mode="lines+markers")
    fig.add_vline(x=5, line_color="#5c6773", line_dash="dash", annotation_text="5-min sweet spot")
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=400,
                      title="H · Profile stability (H1↔H2 correlation) vs bin width — bigger = more repeatable",
                      xaxis=dict(title="bin width (minutes)", type="log", tickvals=[1, 3, 5, 10, 15, 30, 60]),
                      yaxis=dict(title="H1↔H2 correlation", range=[-0.4, 1.05]))
    return fig


def fig_H_adaptive(Had):
    col = [GREEN if (s and v > 0) else (RED if (s and v < 0) else "#37474f")
           for s, v in zip(Had.ret_sig, Had.ret_bps_med)]
    fig = go.Figure()
    fig.add_bar(x=Had.clock, y=Had.ret_bps_med, marker_color=col, name="median return",
                error_y=dict(type="data", symmetric=False,
                             array=(Had.ret_bps_ci_hi - Had.ret_bps_med),
                             arrayminus=(Had.ret_bps_med - Had.ret_bps_ci_lo),
                             color="#5c6773", thickness=1))
    fig.add_hline(y=0, line_color=FG, line_width=1)
    fig.update_layout(template="term", height=420,
                      title="H · Adaptive-grid median return (bps) with bootstrap 95% CI — coloured = CI excludes 0",
                      xaxis=dict(title="ET clock (bucket start · fine at open/close, coarse midday)", nticks=18),
                      yaxis=dict(title="median return (bps)"))
    return fig


def fig_I_domclock(clock):
    fig = go.Figure()
    fig.add_bar(x=clock.clock, y=clock.start_pct_of_days, name="leg STARTS (launch)", marker_color=BLUE, opacity=0.85)
    fig.add_bar(x=clock.clock, y=clock.end_pct_of_days, name="leg ENDS (major reversal)", marker_color=AMBER, opacity=0.9)
    fig.update_layout(template="term", barmode="group", height=430,
                      title="I · The day's biggest swing: launch vs terminal-reversal time (% of days)",
                      xaxis=dict(title="ET clock (30-min block)", nticks=13),
                      yaxis=dict(title="% of days"))
    fig.add_annotation(x="10:00", y=float(clock.end_pct_of_days.max()),
                       text="major turn:<br>10:00–11:00 on 52%", showarrow=True,
                       arrowcolor=AMBER, font=dict(color=AMBER), ay=-45)
    return fig


def fig_I_regime(reg):
    col = [GREEN if p else "#37474f" for p in reg.persists]
    fig = go.Figure()
    fig.add_bar(x=reg.feature, y=reg.lag1_autocorr, marker_color=col,
                error_y=dict(type="data", array=3 * reg.shuffle_sd, color="#5c6773", thickness=1))
    fig.add_hline(y=0, line_color=FG, line_width=1)
    fig.update_layout(template="term", height=400,
                      title="I · Does the day's character carry over to tomorrow? (lag-1 autocorr ±3σ null)",
                      yaxis=dict(title="lag-1 autocorrelation"),
                      xaxis=dict(title="green = persists beyond chance"))
    return fig


def fig_I_persistence(sig):
    lag = sig[sig.test == "block-autocorr"]
    fig = go.Figure()
    fig.add_scatter(x=lag.lag, y=lag.null_mean + 2 * lag.null_sd, line=dict(width=0, color="#33404d"), showlegend=False)
    fig.add_scatter(x=lag.lag, y=lag.null_mean - 2 * lag.null_sd, line=dict(width=0, color="#33404d"),
                    fill="tonexty", fillcolor="rgba(120,130,145,0.15)", name="chance range (±2σ)")
    fig.add_scatter(x=lag.lag, y=lag.observed, line=dict(color=RED, width=2.5), mode="lines+markers",
                    name="observed persistence")
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=400,
                      title="I · Does a specific reversal block recur N days later? (lag 5 = weekly) — it does not",
                      xaxis=dict(title="lag (trading days)", dtick=1),
                      yaxis=dict(title="block-autocorrelation"))
    return fig


def fig_J_taxonomy(J):
    J = J.sort_values("n_days")
    col = {"trend_up": GREEN, "trend_down": RED, "V_reversal_up": "#66bb6a",
           "A_reversal_down": "#e57373", "late_pop_fade": AMBER, "late_drop_recover": AMBER,
           "range_chop": "#78909c", "drift": "#5c6773"}
    fig = go.Figure()
    fig.add_bar(y=J.category, x=J.pct_of_days, orientation="h",
                marker_color=[col.get(c, BLUE) for c in J.category],
                text=[f"{p}%  (n={n}, H1/H2 {a}/{b})" for p, n, a, b in
                      zip(J.pct_of_days, J.n_days, J.n_H1, J.n_H2)],
                textposition="outside")
    fig.update_layout(template="term", height=430,
                      title="J · Rule-based day taxonomy — how often each day type occurs (247 days)",
                      xaxis=dict(title="% of days", range=[0, J.pct_of_days.max() * 1.45]),
                      yaxis=dict(title=""))
    return fig


def fig_J_shapes(Jpaths, Jnames):
    fig = go.Figure()
    palette = {"steady_grind_up": GREEN, "fast_morning_rally_hold": "#66bb6a",
               "morning_dip_recover": BLUE, "early_top_trend_down": RED,
               "slow_bleed_into_close": "#e57373"}
    cols = [c for c in Jpaths.columns if c.startswith("m")]
    x = [_clk(int(c[1:])) for c in cols]
    for _, r in Jpaths.iterrows():
        cl = int(r["cluster"])
        row = Jnames[Jnames.cluster == cl].iloc[0]
        fig.add_scatter(x=x, y=r[cols].values, name=f"{row.auto_name} ({row.pct}%)",
                        line=dict(color=palette.get(row.auto_name, AMBER), width=2.5))
    fig.add_hline(y=0, line_color=FG, line_width=1, line_dash="dot")
    fig.update_layout(template="term", height=460,
                      title="J · The five recurring day shapes — median path per cluster (% from open)",
                      xaxis=dict(title="ET clock", nticks=14), yaxis=dict(title="% from open"))
    return fig


def fig_J_motifs(Jm):
    fig = make_subplots(rows=1, cols=2, column_widths=[0.5, 0.5],
                        subplot_titles=("Morning motif frequency vs independence null",
                                        "Rest of day (11:00→close) after each motif"))
    fig.add_bar(x=Jm.read, y=Jm.pct, name="observed %", marker_color=BLUE, row=1, col=1)
    fig.add_scatter(x=Jm.read, y=Jm.expected_pct_if_independent, name="expected if random",
                    mode="markers", marker=dict(color=AMBER, size=10, symbol="diamond"), row=1, col=1)
    col = [GREEN if v > 0 else RED for v in Jm.rest_of_day_med_bps]
    fig.add_bar(x=Jm.read, y=Jm.rest_of_day_med_bps, marker_color=col, showlegend=False, row=1, col=2)
    fig.add_hline(y=0, line_color=FG, line_width=1, row=1, col=2)
    fig.update_layout(template="term", height=430,
                      title="J · Morning motifs (three 30-min legs, 09:30–11:00): frequencies are random, prediction is null")
    fig.update_yaxes(title="% of days", row=1, col=1)
    fig.update_yaxes(title="median bps", row=1, col=2)
    fig.update_xaxes(tickangle=35)
    return fig


def build_dashboard(res, m):
    figs = [
        fig_avg_path(m), fig_A_volsmile(res["A_minute_profile"]),
        fig_path_heatmap(m), fig_A_contratio(res["A_minute_profile"]),
        fig_B_timing(res["B_timing_minutes"]),
        fig_C_or(res["C_or_mechanics"]),
        fig_D_touch(res["D_touch_buckets"], res["D_race_test"]),
        fig_E_pivots(res["E_pivot_minutes"], res["E_pivot_buckets"]),
        fig_E_zscore(res["E_pivot_buckets"]),
        fig_F_halves(res["F_minute_profile_halves"]),
        fig_G_clusters(res["G_cluster_median_paths"], res["G_cluster_sizes"]),
        fig_H_stability(res["H_resolution_stability"]),
        fig_H_adaptive(res["H_profile_adaptive"]),
        fig_I_domclock(res["I_dominant_swing_clock"]),
        fig_I_regime(res["I_regime_persistence"]),
        fig_I_persistence(res["I_signature_persistence"]),
        fig_J_taxonomy(res["J_rule_taxonomy"]),
        fig_J_shapes(res["J_shape_median_paths"], res["J_shape_clusters"]),
        fig_J_motifs(res["J_morning_motifs"]),
    ]
    parts = []
    for i, f in enumerate(figs):
        parts.append(pio.to_html(f, include_plotlyjs=(True if i == 0 else False), full_html=False))
    Es = res["E_summary"].iloc[0]; Bs = res["B_timing_summary"]
    Cs = res["C_or_mechanics"]; Dr = res["D_reversal_summary"]
    kpi = f"""
    <div class='kpis'>
      <div class='kpi'><span>247</span>clean trading days</div>
      <div class='kpi'><span>{Bs.loc[0,'median_clock']}</span>median HOD time</div>
      <div class='kpi'><span>{Bs.loc[1,'median_clock']}</span>median LOD time</div>
      <div class='kpi'><span>{int(Es.total_pivots)}</span>ZigZag pivots ({int(Es.pivots_per_day_med)}/day)</div>
      <div class='kpi'><span>{Cs.loc[0,'fakeout_rate']:.0f}%</span>OR5 fakeout rate</div>
      <div class='kpi'><span>{res['D_race_test'].loc[0,'pct_reject_first']:.0f}% / {res['D_race_test'].loc[1,'pct_reject_first']:.0f}%</span>PDH / PDL reject-race (≈coin-flip)</div>
    </div>"""
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
    <title>QQQ Intraday Time-of-Day Patterns</title>
    <style>
      body{{background:{BG};color:{FG};font-family:Consolas,Menlo,monospace;margin:0;padding:24px}}
      h1{{font-weight:600;letter-spacing:1px;border-bottom:1px solid {GRID};padding-bottom:12px}}
      .sub{{color:#7d8895;margin-top:-6px;font-size:13px}}
      .kpis{{display:flex;flex-wrap:wrap;gap:14px;margin:22px 0}}
      .kpi{{background:{PANEL};border:1px solid {GRID};border-radius:8px;padding:14px 18px;min-width:150px}}
      .kpi span{{display:block;font-size:22px;color:{AMBER};font-weight:700}}
      .card{{background:{PANEL};border:1px solid {GRID};border-radius:10px;margin:18px 0;padding:8px}}
      .note{{color:#7d8895;font-size:12px;margin:18px 4px}}
    </style></head><body>
    <h1>QQQ · Intraday Time-of-Day Pattern Dashboard</h1>
    <div class='sub'>1-min RTH (09:30–15:59 ET) · 30 Jun 2025 → 30 Jun 2026 · 247 clean days · RTH-anchored VWAP · medians + IQR</div>
    {kpi}
    """ + "".join(f"<div class='card'>{p}</div>" for p in parts) + f"""
    <div class='note'>Caveats: single instrument, single year. Returns are fat-tailed (medians used throughout).
    ZigZag pivots are a retrospective labeller (confirmation lags) — descriptive, not a tradeable signal.
    The minute-level median <i>return</i> profile is NOT stable H1↔H2 (corr≈{res['F_stability_summary'].iloc[0,0]});
    volatility-shape, event-timing and level-reversal patterns are far more robust. See FINDINGS.md.</div>
    </body></html>"""
    path = OUT / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    print(f"[report] wrote {path}  ({path.stat().st_size//1024} KB)")
    return path


# ======================================================== Markdown findings
def build_markdown(res, m, d):
    A = res["A_minute_profile"]; Bs = res["B_timing_summary"]; Bm = res["B_timing_minutes"]
    C = res["C_or_mechanics"]; Dr = res["D_reversal_summary"]; Dg = res["D_gapfill_summary"]
    Es = res["E_summary"].iloc[0]; Edom = res["E_dominant_windows"]
    Fs = res["F_stability_summary"].iloc[0]; Fh = res["F_halves_summary"]; Fw = res["F_weekday"]
    Gs = res["G_summary"].iloc[0]; Gsz = res["G_cluster_sizes"]

    # vol-smile numbers
    open_rng = A.loc[A.minute_index == 0, "range_med"].iloc[0]
    lunch_rng = A.loc[(A.minute_index >= 180) & (A.minute_index <= 210), "range_med"].median()
    close_rng = A.loc[A.minute_index == 389, "range_med"].iloc[0]
    open_vol = A.loc[A.minute_index == 0, "vol_med"].iloc[0]
    lunch_vol = A.loc[(A.minute_index >= 180) & (A.minute_index <= 210), "vol_med"].median()
    close_vol = A.loc[A.minute_index == 389, "vol_med"].iloc[0]

    def tbl(df, cols=None):
        df = df[cols] if cols else df
        return df.to_markdown(index=False)

    md = f"""# QQQ Intraday Time-of-Day Patterns — Findings

**Data**: QQQ 1-minute candles, RTH 09:30–15:59 ET (390 bars/day), 30 Jun 2025 → 30 Jun 2026.
**Sample**: 247 clean full days (5 excluded: 2× boundary-partial, 3× holiday-thin). VWAP recomputed
anchored at 09:30. All stats are **medians + IQR** (intraday returns are fat-tailed; means mislead).
Effect sizes reported; patterns cross-checked first-half (H1, n={int(Fs.n_days_H1)}) vs second-half (H2, n={int(Fs.n_days_H2)}).

> **Approach**: purely data-driven, conditioned on *time of day* only. No day-type taxonomy, no manual
> tagging. Reversal points are labelled algorithmically by an ATR-thresholded ZigZag.

---

## Headline patterns (strongest, time-of-day)

| # | Pattern | Number | Robust H1↔H2? |
|---|---------|--------|----------------|
| 1 | **Volatility smile** — range collapses into lunch, expands into the close | open 1-min range **${open_rng:.2f}** → lunch **${lunch_rng:.2f}** → close **${close_rng:.2f}** | ✅ yes |
| 2 | **Volume U-shape** | open **{open_vol/1e3:.0f}k** → lunch **{lunch_vol/1e3:.0f}k** → close **{close_vol/1e3:.0f}k** | ✅ yes |
| 3 | **Opening drives the day's extremes & reversals** | {int(res['E_pivot_buckets'].loc[0,'all_count'])} pivots in 09:30–09:44 bucket, **{res['E_pivot_buckets'].loc[0,'all_ratio_vs_unif']:.2f}×** uniform (z={res['E_pivot_buckets'].loc[0,'all_z']:.1f}) | ✅ yes |
| 4 | **HOD/LOD timing** | median HOD **{Bs.loc[0,'median_clock']}**, LOD **{Bs.loc[1,'median_clock']}**; biggest leg starts **{Bs.loc[2,'median_clock']}** | ✅ timing stable |
| 5 | **Prior-day levels are NOT reversal magnets** (audit reversal) | race test at touch: PDH reject **{res['D_race_test'].loc[0,'pct_reject_first']:.0f}%** vs control **{res['D_race_test'].loc[2,'pct_reject_first']:.0f}%** — coin-flip; PDL leans **continuation** ({res['D_race_test'].loc[1,'pct_reject_first']:.0f}% reject, z={res['D_race_test'].loc[1,'z_vs_coinflip']:.1f}) | ❌ refuted |
| 6 | **OR fakeouts are common** | OR5 fakeout **{C.loc[0,'fakeout_rate']:.0f}%**, only **{C.loc[0,'break_and_go_rate']:.0f}%** break-and-go | ⚠️ direction varies |
| 7 | **Minute-level signed return profile is NOISE** | H1↔H2 corr **{Fs.minute_profile_H1H2_corr:.2f}** | ❌ regime artifact |

---

## A · Minute-of-day profile

The classic intraday **volatility smile** is the single clearest pattern. The first RTH minute (09:30)
has a median 1-min range of **${open_rng:.2f}** and median volume **{open_vol/1e3:.0f}k**. Both decay through the
morning to a **lunch lull** (~12:00–13:00) of roughly **${lunch_rng:.2f}** range and **{lunch_vol/1e3:.0f}k** volume, then
re-expand into **power hour**, peaking at the 15:59 closing print (**${close_rng:.2f}** range, **{close_vol/1e3:.0f}k** volume).

- **% up-candles** hovers near 50% all day (no persistent directional drift minute-to-minute).
- **Continuation ratio** (does the next minute extend the current move?) sits close to 0.50 — i.e. minute-to-minute
  moves are near a coin-flip, with mild momentum in the first few minutes after the open and mild mean-reversion
  mid-morning. This is small and not a reliable edge.

## B · Event-timing distributions

| metric | median | Q25 | Q75 | n |
|--------|--------|-----|-----|---|
| HOD minute | {Bs.loc[0,'median_clock']} ({Bs.loc[0,'median']:.0f}) | {int(Bs.loc[0,'q25'])} | {int(Bs.loc[0,'q75'])} | {int(Bs.loc[0,'n_days'])} |
| LOD minute | {Bs.loc[1,'median_clock']} ({Bs.loc[1,'median']:.0f}) | {int(Bs.loc[1,'q25'])} | {int(Bs.loc[1,'q75'])} | {int(Bs.loc[1,'n_days'])} |
| biggest-leg start | {Bs.loc[2,'median_clock']} ({Bs.loc[2,'median']:.0f}) | {int(Bs.loc[2,'q25'])} | {int(Bs.loc[2,'q75'])} | {int(Bs.loc[2,'n_days'])} |

The HOD/LOD distributions are **strongly bimodal** — extremes cluster either in the **first 30 minutes**
or in the **final 30 minutes**, with a thin middle. This is the data-driven version of "early extreme →
later reversal": when the high prints early, the low tends to print late (and vice-versa). The day's single
largest directional leg most often *begins* in the opening 15 minutes (median start {Bs.loc[2,'median_clock']}).

## C · Opening-range mechanics

{tbl(C, ['or_window','either_break_rate','fakeout_rate','break_and_go_rate','first_break_med_clock'])}

Opening-range extremes get broken nearly every day, but the break is **more often a fakeout than a trend
launch**: for the 5-minute OR, **{C.loc[0,'fakeout_rate']:.0f}%** of first breaks close back inside within 5 bars and only
**{C.loc[0,'break_and_go_rate']:.0f}%** are clean break-and-go. The fade tendency around the opening range is one of the more
actionable structural results here, though *which* side ultimately wins is not predictable from time alone.

## D · Prior-day level interaction (the co-lens) — REVISED TWICE, now refuted as a turn signal

> **Audit revision (two rounds).** (1) The earlier pooled version counted gap-over days as
> "touches" (68 of 145 PDH touches) and 4 days used levels from partial prior days — both fixed
> (approach-direction split, n=243 days with a full prior session). (2) More fundamentally: the
> "turns away X% of touches" criterion (≥1 ATR within 30 min) has a **base rate of ~78–83% from
> ANY random minute** — the apparent 79–83% turn rates at PDH/PDL are exactly the base rate.

The honest test is a **race**: from the first touch, which comes first — a 1-ATR *rejection* (away
from the level) or a 1-ATR *breakthrough* (beyond it)? A random price point races ~50/50; a real
support/resistance level should skew toward rejection. It does not:

{tbl(res['D_race_test'])}

- **PDH first touch: a coin flip** ({res['D_race_test'].loc[0,'pct_reject_first']:.0f}% reject vs control {res['D_race_test'].loc[2,'pct_reject_first']:.0f}%).
- **PDL first touch leans the other way** — only {res['D_race_test'].loc[1,'pct_reject_first']:.0f}% reject (z={res['D_race_test'].loc[1,'z_vs_coinflip']:.1f}): weak evidence of
  **continuation through** the prior low, not a bounce. (Not significant at 5%; single year.)
- What **is** real: touch *timing*. True touches concentrate in the morning (PDH median ~09:57,
  PDL ~10:13), consistent with the early-extreme pattern in B — the levels get *visited* on a
  clock, they just don't reliably *turn* price.
- **Gap fill**: {Dg.loc[0,'fill_rate_pct']:.0f}% of days fill the prior-day close gap, median fill **{Dg.loc[0,'fill_med_clock']}** (early when it happens).

This is the audit's most valuable output: a popular trading belief ("PDH/PDL act as magnets that
reverse price") is **not supported** in this dataset once the movement base rate is controlled for.

## E · Reversal-point detection (ATR-ZigZag, the focus)

ATR×{Es.k_atr:.0f} ZigZag on 1-min closes labelled **{int(Es.total_pivots)} pivots** ({int(Es.pivots_per_day_med)}/day median;
{int(Es.high_pivots)} highs, {int(Es.low_pivots)} lows; median swing **{Es.mag_pct_med:.2f}%** / {Es.mag_atr_med:.1f} ATR).

**Dominant reversal windows** (15-min buckets, ranked by binomial z vs a uniform 09:30–16:00 distribution):

{tbl(Edom)}

The **09:30–09:44** window dominates overwhelmingly (z≈{res['E_pivot_buckets'].loc[0,'all_z']:.0f}) — reversals concentrate at the
open. Pivots at exactly 09:30 are *not* counted (the ZigZag requires a prior leg), so this is real opening
churn at minutes ~3–11, not an anchoring artifact. Secondary, much weaker clusters appear in the **early
afternoon (13:15–14:45)** as the lunch lull breaks. High-pivots and low-pivots share the same opening
concentration; afternoon highs slightly lead afternoon lows.

## F · Normalization & robustness

| half | n | HOD med | LOD med | range med | close-pos med |
|------|---|---------|---------|-----------|----------------|
| H1 | {int(Fh.loc[0,'n_days'])} | {Fh.loc[0,'hod_med_clock']} | {Fh.loc[0,'lod_med_clock']} | {Fh.loc[0,'range_med']:.2f} | {Fh.loc[0,'close_pos_med']:.2f} |
| H2 | {int(Fh.loc[1,'n_days'])} | {Fh.loc[1,'hod_med_clock']} | {Fh.loc[1,'lod_med_clock']} | {Fh.loc[1,'range_med']:.2f} | {Fh.loc[1,'close_pos_med']:.2f} |

**What survives the split:** the volatility smile, volume U-shape, opening reversal concentration, bimodal
HOD/LOD timing, and prior-day-level reversal rates all reproduce in both halves.

**What does NOT:** the *signed* minute-by-minute median return profile has an H1↔H2 correlation of only
**{Fs.minute_profile_H1H2_corr:.2f}** — essentially zero. Any specific "minute X tends to go up" claim is a regime artifact and
must be discarded. Daily range roughly **doubled** H1→H2 ({Fh.loc[0,'range_med']:.2f}→{Fh.loc[1,'range_med']:.2f}), a volatility-regime
shift — so absolute-dollar levels don't transfer; ATR-normalised and timing-based patterns do.

Weekday (a clock feature) shows only mild differences:

{tbl(Fw[['weekday','n_days','hod_med','lod_med','range_med','close_pos_med']])}

## G · Optional — emergent day archetypes (k-means on normalized paths)

Silhouette selects **k={int(Gs.k_best)}** (score {Gs.silhouette_best:.2f}) on shape-normalized intraday paths — essentially
an **up-trend day vs down-trend day** split rather than a rich taxonomy. Cluster sizes:

{tbl(Gsz)}

The weak silhouette confirms days form a **continuum**, not clean discrete types — which is exactly why the
brief forbids an imposed day-type taxonomy. Treated as discovery only.

---

## H · Time resolution — per-minute vs blocks (which bin width is best?)

Coarser bins are *not* automatically better. Measuring **H1↔H2 profile correlation** (repeatability) against
bin width shows:

{tbl(res['H_resolution_stability'])}

- **Range & volume** are already near-perfectly repeatable at *every* resolution (corr ≥0.98) — the vol smile
  and volume U-shape don't need coarsening; that's why they're the headline-robust findings.
- **Signed returns** peak at **5-min** (corr {res['H_resolution_stability'].set_index('bin_min').loc[5,'ret_H1H2_corr']:.2f}, a 3× lift over 1-min) then **collapse to negative at ≥15-min**.
  A uniform 15-min grid *destroys* the only real return structure and leaves half-specific noise.
- ATR-normalising returns does **not** rescue coarse bins (it makes 15–30-min *worse*) — the return signal is
  genuinely weak and short-horizon, not a magnitude artifact.

**Recommendation: an adaptive grid** — 1-min at the open (09:30–09:44) and the close (15:45–15:59), 5-min in
the ramps, 15-min through the midday lull. With that grid + **bootstrap 95% CIs**, several bucket returns become
statistically distinguishable from zero (CI excludes 0) — structure the noisy per-minute view could not confirm:

{tbl(res['H_profile_adaptive'][res['H_profile_adaptive'].ret_sig][['clock','width_min','n_obs','ret_bps_med','ret_bps_ci_lo','ret_bps_ci_hi','pct_up']])}

The clearest is a **closing ramp-then-fade**: 15:47→15:57 all significantly positive (15:57 = +0.91 bps, 62%
up-candles), immediately followed by a significantly **negative** 15:59 closing print (−0.67 bps, 43% up) — the
end-of-day melt-up unwinding into the auction. A mid-morning drift (≈10:05–10:20) is the other survivor.

## I · The "recurring reversal clock" hypothesis — REVISED & UPGRADED (v2.0)

Testing the observation that *specific time blocks reverse, and that pattern repeats on later days,
conditioned on day type*. Guard: volatility clustering + the structural open/close base rate make
consecutive days look alike for boring reasons, so every test is compared to a **day-order shuffle null**.

> **Audit revision.** The first pass reported the dominant swing's *end* time while calling it the
> *start*. Both are now computed and labelled correctly — and the corrected picture is sharper.

{tbl(res['I_summary'])}

**The upgraded mechanism (hypothesis 2.0), fully data-backed:**

{tbl(res['I_dominant_swing_clock'][(res['I_dominant_swing_clock'].start_pct_of_days >= 4) | (res['I_dominant_swing_clock'].end_pct_of_days >= 4)])}

1. **Launch**: the day's biggest swing *starts* in the opening hour — 09:30–10:30 on **~67% of days**
   (09:30 block alone = 42%).
2. **Direction**: when it starts early it is an **extension of the opening 30-min drive, not a fade** —
   same direction **{res['I_direction_linkage'].iloc[0].pct_same_dir_as_opening_drive:.0f}%** of the time (z={res['I_direction_linkage'].iloc[0].z_vs_coinflip:.1f} vs coin-flip). Legs that start after 10:00 are a coin-flip.
3. **Terminal reversal**: that drive *ends* — the major intraday turn — in the **10:00–11:00 window on
   ~52% of days**. This is almost certainly the reversal block you observe.
4. **Stability**: the 10:00–11:00 terminal-reversal rate is **{res['I_clock_stability'].iloc[0].end_in_1000_1100_pct}% in H1 vs {res['I_clock_stability'].iloc[1].end_in_1000_1100_pct}% in H2** — as stable as
   a time-of-day pattern gets in this dataset.

**What the data does *not* support** — a block that recurs on particular *later* days:
- Consecutive-day reversal-signature similarity is **not** above the shuffle null (cosine z≈1, p≈0.16).
- The lag-1…10 autocorrelation is flat with **no lag-5 (weekly) spike**, and the sharper weekday-matched
  test agrees: same-weekday-next-week similarity ≈ distant-random ({res['I_weekday_recurrence'].iloc[0].same_weekday_next_week_cos} vs {res['I_weekday_recurrence'].iloc[0].distant_random_cos}).
- Terminal-block "stickiness" day-to-day matches its marginal distribution (p≈{res['I_dominant_swing_stickiness'].iloc[0].p_value}).
- Hot-open days do **not** resemble each other more than random pairs — the clock isn't regime-specific.

**The real mechanism behind the felt repetition** — regime persistence:

{tbl(res['I_regime_persistence'])}

Post-open range and daily range are **strongly autocorrelated day-to-day (≈0.40, z>6)** — classic volatility
clustering: hot days follow hot days. *Trend strength does not persist* (≈0). So what repeats is the
**magnitude/activity regime**, not the reversal *timing*.

**Hypothesis 2.0, in one sentence:** *the opening 30-min drive extends into a directional leg that
terminates in a major reversal at 10:00–11:00 on half of all days; volatility clustering strings several
dramatic instances together, which reads to the eye as "the same block keeps reversing this week" —
but the schedule is structural (same window nearly every day), not day-specific.*

## J · Intraday pattern taxonomy — what day types actually exist

Three angles, cross-checked: transparent **rules**, data-driven **shape clustering**, and morning
**sign motifs** vs a randomness null.

**J1 — rule-based day types** (mutually exclusive; trend = |open→close| ≥65% of range, reversal =
early opposite extreme + close in far third):

{tbl(res['J_rule_taxonomy'].drop(columns='example_dates'))}

The single most common day type is the **V-reversal up** (early selloff, reverse, close high — 23%).
Reversal days together (37%) **outnumber trend days (29%)** and chop (16%). Trend-down days carry the
largest ranges (median ${res['J_rule_taxonomy'].set_index('category').loc['trend_down','range_med']:.2f}) — down moves are more violent. Category frequencies are
broadly balanced H1/H2.

**J2 — five recurring shapes** (k-means on z-normalized paths; silhouette ~0.17 ⇒ soft boundaries,
days are a continuum):

{tbl(res['J_shape_clusters'])}

Up-family (grind-up, fast-rally-hold, dip-recover) ≈60% of days; down-family (early-top trend-down,
slow-bleed) ≈40% — consistent with the year's upward drift. Note `fast_morning_rally_hold` is
H2-heavy (12/31) and `morning_dip_recover` H1-heavy (21/13): shape mix drifts with regime.

**J3 — morning motifs** (sign of the three 30-min legs 09:30→11:00, e.g. "up-down-up"):

{tbl(res['J_morning_motifs'][['motif','read','n_days','pct','expected_pct_if_independent','z_vs_independent','rest_of_day_med_bps','rest_up_pct']])}

Every motif's frequency matches the independence null (all |z| ≤ 1.1) — **morning legs are
serially independent coin flips**; "up-down-up" is not a special rhythm. And the rest-of-day
linkage is unstable across halves (e.g. down-up-down: +21.9 bps H1 vs −15.2 bps H2).

**J4 — can you recognize the day type by 11:00?** Mostly no, in the way that matters:

{tbl(res['J_early_recognition_detail'])}

Morning→afternoon sign continuation is **{res['J_early_recognition'].iloc[0]['P_afternoon_same_sign_as_morning_pct']}%** (corr {res['J_early_recognition'].iloc[0]['corr_morning_vs_rest']}) — a coin flip, stable in both
halves and at every morning-magnitude tercile. A strong directional morning does raise the odds the
day *ends up labelled* a trend day (45% vs 29% base) — but that is largely **mechanical** (the morning
move itself is most of the trend), not a forecast: the afternoon after a strong morning is still 50/50.
**The taxonomy is descriptive (hindsight), not predictive (foresight).** What *is* knowable in real
time: the volatility regime (yesterday's range), the structural clock (opening drive → 10:00–11:00
turn window), and time-of-day risk sizing.

## K · Backtest — does the playbook survive costs? (mostly no; one lead worth pursuing)

Time-based rules only, direction known at entry, round-trip cost 0.4 bps (2 ticks):

{tbl(res['K_backtest'][res['K_backtest'].subset.str.contains('net')][['strategy','subset','n_trades','hit_rate_pct','mean_bps','t_stat','mean_H1','mean_H2']])}

- **Enter at 09:45 with the 15-min drive, exit 11:00 (S1)**: the only positive lead. On
  **big-drive days** (top tercile, known at entry): **+7.7 bps/trade net, 61% hit rate**, and
  strikingly stable H1/H2 (+7.6/+7.7) — but t=1.34 (n=82), **not statistically significant**.
- **Waiting until 10:00 (S2/S3) is too late** — the leg starts 09:30–10:30 and much of it is
  spent by 10:00; big-drive days go *negative*.
- **Fading at 11:00 (S4) loses** (−3.4 bps) — the turn window marks where the morning leg *ends*,
  not a reliable direction flip (consistent with J4's coin-flip afternoon).
- Verdict: the structural clock is real **descriptively** but is **not a tradable edge as a naive
  time rule on this one year of data**. The S1 big-drive variant is the only candidate worth
  testing on more data/instruments before any real-money conclusion.

## L · Day-of-week effects — one internally consistent lead, everything else is noise

n ≈ 48–52 days per weekday ⇒ low power. 12 tests run (Bonferroni threshold ≈ 0.004); leads with
0.004 < p < 0.05 must also hold the same sign in both H1 and H2.

{tbl(res['L_weekday_summary'])}

- **Nothing survives multiple-testing correction.** The two nominal hits — weekday gap
  differences (KW p=0.040) and Monday's positive return (Wilcoxon p=0.041) — are both above the
  corrected threshold.
- **The only internally consistent lead: Monday.** Positive median return in BOTH halves
  (+11.4 / +36.4 bps), 60% up days, and a positive weekend gap in both halves (+30.3 / +6.9 bps) —
  a weekend-premium flavour. Treat as a lead to test on more data, not a tradable fact.
- **Thursday's −11 bps and Friday's +17 bps flip sign between halves** — regime noise, discard.
- **The structural clock needs no weekday adjustment**: dominant-leg turn lands in 10:00–11:00 on
  48–56% of days on *every* weekday (KW p=0.36).
- **Day-type mix is identical across weekdays** (χ² p=0.82) — Mondays are not "trendier",
  Fridays are not "choppier". The taxonomy is weekday-blind.

{tbl(res['L_weekday_stability'])}

## M · OR-break continuation to 11:00 — timing, level, and pullback entries

Setup: first CLOSE beyond the opening-range extreme (by 10:30) = the break; exit all entries at
10:59 (inside the turn window); "trended" = ≥1 day-ATR beyond the OR extreme at exit; costs 0.4 bps.

**(a) Base rates** — the first break trends to 11:00 on **~51–53% of break days** for every OR
window (5/15/30 min). Up-breaks extended much further than down-breaks this (upward-drifting)
year: OR5 median extension +2.8 ATR vs +0.6 ATR.

**(b) Entry tournament:**

{tbl(res['M_entry_tournament'][['or_window','entry','fill_rate_pct','n','hit_pct','mean_bps','t_stat','mae_med_atr','mean_H1','mean_H2']])}

- **Chasing the break (E1) or waiting for bar-confirmations (E2/E3) does not work** — means near
  zero or negative, and every immediate/confirm variant flips sign between halves.
- **The only entry family positive in BOTH halves: pullback-to-VWAP (E5)** on OR15 (+2.4 bps,
  H1 +3.4/H2 +1.3) and OR30 (+4.6 bps, t=1.41, H1 +1.3/H2 +7.9). It also carries the **lowest
  adverse excursion** (median MAE 3.6–4.2 ATR vs ~6 for chasing). Sub-slices (side, break time)
  all flip between halves — only the aggregate is stable. Still t<2 ⇒ **lead, not proof**.

**(c) Pullback geometry on days that DID trend** (the level/timing answer):

{tbl(res['M_pullback_geometry'])}

- **Even on eventual trend days, the break almost always comes back**: the OR level is retested
  on **83–89%** of trending days; only ~8–13% run straight without a meaningful pullback.
- The median pullback goes **~2.4 ATR back INSIDE the range** (q75 ~4–5 ATR) — a limit order AT
  the OR level fills on ~85% of trend days, and there is usually room well inside the level.
- **Pullback bottoms cluster 09:45–10:00** (OR5: median 09:47; OR15: 10:00; OR30: 10:18) — i.e.
  the entry window is the *second* approach, minutes after the fakeout-prone first break
  (median break 09:37–09:48), and it dovetails with the structural clock: enter on the pullback
  bottom, ride to the 10:00–11:00 terminal window, exit.

**Bottom line:** the data supports the hypothesis's *structure* — break → pullback → trend into
11:00 — but rejects the naive execution (chasing). Timing: pullback window 09:45–10:00. Level:
at/inside the OR extreme (it retests 85%+ even on trend days) or session VWAP (best tested proxy).
All entry-rule profits remain statistically unproven on one year — Phase-2 OOS applies.

## N · Pullback scaled as % retracement into the OR (0–100%)

Scale: 0% = the broken OR extreme, 100% = full traverse to the opposite side. Two products:

**N(a) The limit ladder (tradable, no look-ahead)** — rest a limit at rung r% after the break
(levels known at break time), exit 10:59, net 0.4 bps:

{tbl(res['N_limit_ladder'][['or_window','retrace_pct','fill_rate_pct','n_trades','hit_pct','mean_bps','t_stat','mae_med_atr','p_trend_given_fill_pct','mean_H1','mean_H2']])}

- **The sweet spot is shallow-to-mid: 25–50% retracement.** OR30 rungs at 25% and 50% are the
  only ones positive in both halves (+1.5/+5.3 and +3.0/+7.4 bps; t≈1.0–1.3).
- **Deep fills are adverse selection, not bargains**: P(day trends | filled) decays from ~50% at
  the level to **7–8% at full traverse**; rungs ≥62% go negative. The "discount" is a warning.
- Depth also buys tighter risk: median MAE shrinks from ~5 ATR (0% rung) to ~3 ATR (50%).

**N(b) Geometry — retracement depth is a live health meter:**

{tbl(res['N_retrace_geometry'])}

Trend days pull back a **median 19–26%** into the range and essentially never fully traverse
(0–3%); failed breaks retrace a median 60–98% and fully traverse 20–49% of the time.
P(trend | max retracement bucket) is strictly monotonic (OR15): 0–25% → **88%**, 25–50% → 74%,
50–75% → 51%, 75–100% → 28%, beyond the far side → **7%**. (Descriptive/hindsight — depth and
outcome are partly mechanically linked — but as a *monitoring* rule it is directly usable:
**a retracement beyond ~60–75% of the OR means the break is probably dead; the far side of the
OR is the natural hard stop.**)

Consistency check: the M-analysis median pullback (2.4 ATR inside) corresponds to ~25% of a
typical OR15 range — the two scales agree.

## O · Time filters on the retest — cutting "false pullbacks" by the clock

Hypothesis tested: a pullback that returns to the broken OR level LATE is the reversal, not a
pullback — so cancel late entries / abort on late touches. Verdict: **one part refuted, one part
confirmed-but-untradable, one modest survivor.**

**O(a) Refuted — first-retest lateness does NOT predict failure.** P(trend | first retest time)
is flat: OR15 <10:00 → 48.5%, 10:00–10:14 → 51.3%, 10:15–10:29 → 56.2% (late is, if anything,
slightly *better*). The only strong cell is "never retests" → 100% (the straight-runners, by
near-definition).

**O(b) Confirmed as a clock — but hindsight.** On trend days the level goes quiet early
(last touch median **10:25–10:32**, q90 ~10:55); on failed days price is still touching it at
**10:59** (median = q90). "Still at the level after ~10:30–10:45" is a genuine reversal tell.

**O(d) …but ACTING on it destroys value.** Exit-on-late-touch (after 10:30) vs hold to 10:59 on
25%-rung fills: OR30 **+3.4 → −1.6 bps** (hit 53% → 43%); OR15 +1.9 → +1.6 with an H1 sign flip.
Aborting on the touch systematically sells the pullback low — the discriminator is real but the
trigger price is the worst available.

{tbl(res['O_abort_test'])}

**O(c) The modest survivor — cancel the UNFILLED limit after ~10:30.** Entry-side time filter on
the 25% rung: OR30 cancel-by-10:30 → **+5.35 bps, t=1.30, H1/H2 = +4.4/+6.2** (vs +3.36 with no
cutoff). At the 0% rung no cutoff helps (negative everywhere). Same league as the other leads
(t<2): Phase-2 OOS material.

{tbl(res['O_cutoff_grid'][(res['O_cutoff_grid'].rung_pct==25)][['or_window','cancel_after','n_trades','hit_pct','mean_bps','t_stat','mean_H1','mean_H2']])}

## P · Defining (and predicting) a "worth trading" OR-break day

**P(a) Definition.** A fixed k×ATR extension line is a poor definition — the extension
distribution is **bimodal** (56% clear 0.5 ATR, 53% clear 1 ATR, 47% clear 2 ATR: days either go
or they don't; k barely selects). The recommended definition is the **trade frame (R-multiples)**:
entry at the 25% retracement rung, hard stop at the far side of the OR (risk = 0.75 × OR range),
day is *tradable* if the position offered ≥ 1R before the stop:

{tbl(res['P_trade_frame'])}

- On OR15, ~**40% of fills offer ≥1R** (median offered 0.85R), 37% stop out first; risk ≈ 2.9
  day-ATR ≈ 15 bps — comfortably above costs, so the frame is economic; win rate is the binding
  constraint, not friction.
- OR30's far-side stop (3.8 ATR) is too wide — only 22% reach 1R; use the OR15 frame or a
  tighter stop for OR30.
- ⚠️ **Scale trap**: R-based "tradability" mechanically favours *narrow* ORs (small risk unit ⇒
  1R is easy) while bps favour *wide* ORs — narrow-OR days reach 1R most often (53%) yet earn the
  worst bps (−1.3); wide-OR days reach 1R least (28%) yet earn +15.8 bps. Define by R for risk
  discipline, but judge economics in bps.

**P(b/c) Prediction with break-time information** (causal features, terciles, H1/H2 checked):

{tbl(res['P_money_test'])}

- Full rule stack **with the hard stop** is the best-behaved variant so far: OR15 +3.2 bps and
  OR30 +4.7 bps, **both halves positive on both windows**, bounded risk (t ≈ 1.0–1.1).
- The only filter that adds money without an H1/H2 flip: **strong opening drive** (OR30 top
  tercile: **+15.2 bps, 59% hit, t = 1.68, H1/H2 = +19.0/+11.7** — n = 29) — convergent with the
  Analysis-K strong-drive lead. Prior-day range (hot regime) helps OR30 too (+12.3, both halves
  positive, n = 28) — convergent with volatility clustering.
- Most other candidate filters (gap size, opening volume ratio, OR width, break time) are flat or
  flip between halves — no additional signal.

**Recommended definition, in one line:** *a tradable day = a break that fills the 25% rung by
10:30 on a strong-drive morning and offers ≥1R against a far-side stop; expect that on roughly
1 fill in 3, sized so that 1R ≈ 15 bps.* All tiny samples (n ≈ 29–156): Phase-2 OOS before capital.

## Q · Long vs short: the same playbook, asymmetric pay (this year)

Conditioning M/N/P on break side:

{tbl(res['Q_side_summary'])}

- **Geometry is side-symmetric.** Trend rate ~50–56% both ways; trend-day max retracement ~25%
  both ways; the depth health-meter is monotonic on both sides (long 93→80→48→27→3%; short
  84→67→56→28→10%). The playbook's *structure* — pullback entry, 25% rung, far-side stop,
  cancel 10:30, exit 10:59 — applies unchanged to shorts.
- **Economics were long-favoured in this drift-up year:**

{tbl(res['Q_side_rule_stack'])}

  Longs: +5.0/+6.6 bps (OR15/OR30). Shorts unfiltered: +1.5/+1.9 with a 44/43% hit rate — thin.
- **The exception: strong-drive shorts.** OR30 down-breaks on top-tercile drive mornings:
  **+23.9 bps, 67% hit, t = 2.03, H1/H2 = +16.4/+31.4** — the largest per-trade figure in the
  study and the first t>2… on **n = 12**. Treat as the most promising and least proven cell:
  a hard down-drive that still pulls back 25% is rare but has paid violently.
- Interpretation: don't skip shorts — gate them harder (strong drive required); longs can trade
  the base stack. Whether the asymmetry is regime (drift year) or structure is a Phase-2 question.

## R · System backtest — $10,000, full playbook, one year (IN-SAMPLE)

System: OR30 break by 10:30 → limit at 25% retracement, cancel 10:30 → stop at the far side →
exit 10:59. Longs ungated; shorts only on strong-drive mornings, with the drive threshold computed
**causally** (trailing 66.7th percentile of prior break-days, 30-day warm-up — no look-ahead in
the gate). Sizing: fixed-fractional risk of current equity per trade, 4x leverage cap, whole
shares, pessimistic same-bar stops, 1 tick/side costs.

{tbl(res['R_system_stats'])}

At the recommended **1% risk**: 61 trades (50 long, 11 short), **+11.0%** on the year,
**max drawdown −3.8%**, 62% win rate, avg +0.19R, only 21% stop-outs, both halves profitable
($399/$697). Shorts contributed ~35% of profit from 18% of trades. Buy-and-hold made +32.4% in
this drift year but with a −12.2% drawdown and full-time exposure; the system is in the market
~35 minutes on 61 of 247 days — per unit of drawdown the two are comparable (2.9x vs 2.7x),
and at 2% risk the system reaches +20.9% with −5.7% DD (3.7x).

**Read the caveats before believing any of it:** (1) the rules were *selected on this same year*
— this is an in-sample demonstration of behaviour and risk profile, not an expected return;
(2) the per-trade Sharpe (~3.5) is flattered because idle days contribute no variance;
(3) 61 trades is a small book; (4) the short gate is n=11. Phase-2 OOS remains the gate before
any real capital. Equity curve: `output/equity_curve.html`.

## Caveats

- **Single instrument, single year** (QQQ, Jun-2025→Jun-2026). A pronounced volatility-regime shift occurred
  between the two halves (daily range ~doubled); patterns that depend on absolute magnitude do not transfer.
- **No look-ahead** in any rolling stat (ATR, VWAP, running HOD/LOD are causal). The ZigZag is retrospective
  by construction — descriptive for *where* reversals cluster, **not** a real-time signal.
- Use **medians + IQR**; means are dominated by fat tails. Effect sizes (ratio-vs-uniform, binomial z,
  H1/H2 correlation) are reported alongside every "a pattern exists" claim.
- The signed minute-return profile is noise — do not trade individual minutes.
"""
    path = OUT / "FINDINGS.md"
    path.write_text(md, encoding="utf-8")
    print(f"[report] wrote {path}")
    return path


def main():
    import binning, persistence, patterns, backtest, weekday
    res, m, d = run_all()
    res.update(binning.run(write=False))
    res.update(persistence.run(write=False))
    res.update(patterns.run(write=False))
    res["K_backtest"] = backtest.run(write=False)
    res.update(weekday.run(write=False))
    import or_break, retrace, timecut
    res.update({k: v for k, v in or_break.run(write=False).items()
                if not k.startswith("M_days")})
    res.update({k: v for k, v in retrace.run(write=False).items()
                if not k.startswith("N_days")})
    res.update({k: v for k, v in timecut.run(write=False).items()
                if not k.startswith("O_days")})
    import tradable, sides
    res.update({k: v for k, v in tradable.run(write=False).items()
                if not k.startswith("P_days")})
    res.update(sides.run(write=False))
    import system_backtest
    res.update({k: v for k, v in system_backtest.run(write=False).items()
                if k != "R_trade_candidates"})
    write_tables_and_excel(res)
    build_dashboard(res, m)
    build_markdown(res, m, d)
    print("[report] done.")


if __name__ == "__main__":
    main()
