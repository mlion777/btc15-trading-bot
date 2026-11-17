# BTC15 V20: live browser chart and browser-persistent paper simulation

## What changed from V19
- Fixed first-live-candle conflict with historical 1-minute candles (clear old series before 10-second updates).
- Live 10-second candle updates directly from Coinbase WebSocket; no Streamlit page reload.
- 10-second EMAs are updated with each trade; 1-minute history is initial context only.
- Rolling 10/30-second and 1/5/15-minute confluence votes; requires adequate completed bars. Short timeframes warm up over time.
- Browser-local completed paper-trade history persists across refreshes, with a reset button. Open positions do NOT persist, so browser refreshes while a trade is open invalidate that trade. No 24/7 execution.
- Stale-feed age display and automatic reconnect.
- Technical A/B/C grades shown on chart; they are NOT win probabilities.

## Important limitations
This is NOT a production trading system. This does NOT connect to Polymarket, simulate real contract bid/ask fills, or place real orders. It uses Coinbase BTC spot directional P&L and an assumed friction rate, so reported returns are NOT Polymarket P&L. Browser localStorage is not a durable multi-device ledger. Zone rendering is price-line boundaries rather than filled rectangles. The exact Bucko proprietary indicator is unavailable. Subminute history only builds from received trades; there is no complete tick backfill. Live connection depends on Coinbase WebSocket and external chart CDN, and has NOT been verified on the user's deployed Streamlit app. No profit guarantee. Install as a separate test app/branch.
