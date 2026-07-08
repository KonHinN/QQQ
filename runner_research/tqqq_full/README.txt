TQQQ 1-minute bars — 2018 through 07/2026
============================================
Source:        Alpaca Market Data, SIP feed (paid, full-tape consolidated)
Adjustment:    RAW / UNADJUSTED (never dividend-adjusted; reflects actual traded prices)
Session:       Extended hours 04:00-19:59 ET (premarket + regular + postmarket)
Timezone:      America/New_York (DST-aware)
Timestamp fmt: day-first  DD/MM/YYYY HH:MM  (bar START time, ET)
Columns:       timestamp_et, open, high, low, close, volume, trade_count
Files:         one CSV per calendar year (TQQQ_1min_YYYY.csv), 2018..2026
2026 file:     partial year, through most recent session
Note 1:        trade-only bars — minutes with zero trades are absent (no synthetic fill).
Note 2:        TQQQ = ProShares UltraPro QQQ (3x leveraged). Underwent a 2:1 split on
               2022-01-13. Because adjustment=RAW, prices are UNADJUSTED for that split
               (pre-split bars show the actual higher traded price of the day).
