# BTC15 V18 — chart-only research terminal

Install `app.py`, `strategy.py`, `paper.py`, and `requirements.txt` in the repository root. Do not overwrite your existing bot without backing it up. Streamlit Community Cloud entrypoint: `app.py`.

- One chart only. Coinbase 1-minute candlesticks, EMA 9/21/34, causal FVG rectangles, actual recorded paper LONG/SHORT and EXIT markers.
- Collects public Coinbase recent trades and retains them in a local SQLite cache to reconstruct 1/5/10/15/30-second bars. Builds 1/2/3/5/15-minute bars from Coinbase 1-minute candles. **Subminute history requires warm-up and can be incomplete.** These are technical timeframes; not all have sufficient history immediately.
- Uses 1m trend, 5m non-conflict and subminute confirmation; only opens paper positions when sufficient data is available and latest trade is fresh. Signals are independent research heuristics, not Bucko's proprietary code or validated win probabilities.
- Automatic **BTC spot-price paper P&L**, not Polymarket UP/DOWN contract trading. $10 illustrative exposure per trade, assumed 8 bps fee and 3 bps slippage per side, +0.8% net profit exit, -0.55% net stop, 4m max hold. Short is simulated only, not an actual margin position.
- Simulated trades saved in `paper_trades.sqlite3`; tick cache in `ticks.sqlite3`. On Streamlit Community Cloud local storage is **ephemeral** and may reset on redeploy/restart. The 5-second refresh runs only while app session is active. No unattended 24/7 trading guarantee.
- Important: Coinbase's public REST endpoint may throttle or return sparse tick history. Never extrapolate subminute candles from minute bars. If data is insufficient, WAIT is correct.
- No real orders, exchange keys, or live trading. No claimed profit performance. Does not reproduce TradingView or Bucko code 1:1.
