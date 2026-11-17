# BTC15 V25 — Polymarket contract-priced PAPER trading

This is an experimental, browser-run paper simulator. Replace only `terminal.html` in a backed-up V24 deployment. Existing V24 dark chart and live Coinbase stream are retained.

## Implemented
- Finds the current Polymarket 15-minute event by its UTC slot slug and requires a single open market, UP/DOWN outcome tokens, and a matching end timestamp.
- Fetches the CLOB BUY ask and SELL bid for both outcome tokens, and rejects invalid, stale, wide-spread, too-expensive, or late entries. A/B technical signals are required.
- Opens a simulated $10 contract position at the observed BUY ask. Exits at a fresh SELL bid from the **same token and market**. Logs the buy/sell prices, simulated P&L, fees, reasons, and chart markers. Uses 1% illustrative fees on each side (not a verified venue fee schedule).
- Closes on illustrative net-return thresholds (+12%/-15%), 240 seconds, opposite A/B signal, emergency loss (-35%), or within 30 seconds of expiry, if a matching live SELL bid exists. No fabricated exits if quotes are missing. Any position not closed before expiry remains unresolved until independently reconciled.
- Kalshi market YES/NO asks appear for context but are **not** used for simulated fills or claimed equivalent to Polymarket outcomes.
- Keeps trade history and the open position in browser-local storage. This is **not** a 24/7 background worker; no trades execute while the browser is closed. Reloads and sleeping tabs can miss exits.

## Not yet verified / not implemented
- Real API/browser CORS success in Streamlit Cloud, actual fillability, market-rule/settlement equivalence, order-book depth, slippage, correct venue fee tier, Kalshi contract paper execution, persistent server-side monitoring, automated reconciliation of expiry, or backtesting with historical venue quotes.
- The 1% per-leg fee is a *model assumption*. Actual fee treatment varies. Paper P&L is indicative, not realized money.
- This version is not validated as profitable and does not place real orders.

## Safety and troubleshooting
If the CLOB or Gamma API is blocked or unavailable, the app intentionally shows NO PAPER ENTRY. It does not silently fall back to spot-price P&L. Test on a separate branch before replacing a working deployment.
