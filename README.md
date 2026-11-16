# BTC15 Intelligence Terminal — v2

A **paper-only** Streamlit research dashboard for Polymarket's BTC 15-minute UP/DOWN markets. It does not place orders, handle wallet credentials, promise a win rate, or claim verified live predictions.

## Quick start

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local address shown by Streamlit (normally `http://localhost:8501`). To make it accessible from other devices, deploy to Streamlit Community Cloud or a secured persistent server. A deployed website requires you to provision hosting; the ZIP is not itself a hosted site. This code was syntax-checked and five unit tests passed in the development environment; live APIs and the complete Streamlit UI were **not** end-to-end tested.

## New in v2

- Current UTC 15-minute market discovery with UP/DOWN token mapping and market rule display.
- Polymarket Gamma `eventMetadata.priceToBeat` prioritized, website crypto-price endpoint as a fallback. The value is labeled `SOURCE_REPORTED`, **not independently Chainlink-verified**; unavailable values block paper entry.
- Binance 1-minute BTC spot chart with EMA 9/21/55, RSI, MACD histogram, rolling 15/60/180-minute support and resistance, and volatility. Binance spot is a **proxy**, not settlement feed.
- CLOB bids/asks, spread, top-level depth, fixed-dollar simulated sweep VWAP, and liquidity/fillability checks.
- Market snapshot SQLite logging and CSV exports; the snapshot table records prices, sources, time left, and indicators.
- Manual paper orders at simulated order-book VWAP, fee assumptions, break-even threshold, and paper P&L. Settlement requires an externally verified outcome and an evidence note. The app does not verify the evidence.
- Binance historical downloader (up to 60 days through UI) and CSV import. A non-overlapping, chronological 60/20/20 split trains logistic regression, calibrates with Platt scaling on the middle segment only, and scores untouched holdout using Brier, log loss, ECE, accuracy and a reliability table. Labels are **spot proxies**, not Polymarket resolutions. This model is not activated for live signals.
- Optional CSV audit of externally collected settlement-matched predictions and timestamped ask quotes. Requires `timestamp,slug,prob_up,up_ask,down_ask,actual_up,seconds_left`; estimates hypothetical $1-per-trade returns under explicit, unrealistic instantaneous-fill assumptions. The app cannot authenticate the uploaded data.
- Data health and stale/missing-candle checks; all live signals are **WAIT — UNCALIBRATED** or **WAIT — DATA NOT READY**.

## Critical limitations

1. The official settlement source and rule version must be verified independently against each Polymarket contract. Gamma/website price-to-beat reports do not constitute cryptographic Chainlink proof. Recent 15-minute markets may use Chainlink TWAP rather than spot ticks.
2. Market books and candles are **polled**, not tick-synchronized; data can become stale before the browser refreshes. For professional collection, build separate WebSocket ingest workers with clock-sync monitoring.
3. The model's proxy backtest cannot establish market profitability or live calibration. You need **official resolved outcomes, recorded contemporaneous executable asks and book depth, and strict out-of-sample predictions**. Historical token midpoint prices are not historical executable asks.
4. Simulated paper fills do not account for order-book cancellations, latency, partial fills, adverse selection, dynamic fee schedules, or real execution. The fee slider is an **assumption**, not a verified exchange fee.
5. The dashboard uses a local SQLite file. On ephemeral Streamlit hosting, records may disappear after a restart. For production use Postgres or another managed database with backups and worker-side collection.
6. Continuous Streamlit refresh only runs while a session is active. This is not an always-on background service.
7. No real-money execution, no wallets, no trading keys, no validated automatic UP/DOWN recommendations. Never interpret illustrative proxy percentages as trustworthy win probabilities.

## Files

- `app.py` — Streamlit dashboard
- `engine.py` — original spot and API utilities
- `advanced.py` — market bundle, book depth, zones, history downloader, chronological proxy evaluation, paper database and market-level audit
- `test_advanced.py` — deterministic unit tests (`python -m unittest -v test_advanced`)
- `requirements.txt` — dependencies

## API references

- `https://gamma-api.polymarket.com/events?slug=btc-updown-15m-{epoch}`
- `https://clob.polymarket.com/book?token_id=...`
- `https://clob.polymarket.com/prices-history?market=...`
- `https://polymarket.com/api/crypto/crypto-price` (undocumented, can change)
- `https://api.binance.com/api/v3/klines`

All external services can change, block requests, or return incomplete results. Validate current docs and rules before relying on this application.

## Version 3 — continuous collection and validation center

The app now includes a separate persistent snapshot collector, data-quality checks, a user-attested outcome evidence registry, rolling expanding-window spot-proxy diagnostics, and a fail-closed signal gate. **These additions do not establish a profitable trading edge.** No trading keys or real-money execution are included.

### Recommended: run dashboard + collector together

```bash
docker compose up --build -d
```

Open `http://localhost:8501`. Docker must be installed. Both services share a persistent named volume (`btc15_data`), so snapshot capture continues even if you close the browser. Keep the machine/server running. Stop with `docker compose down` (do **not** use `-v` unless you intend to delete the volume).

### Without Docker

Run these in separate terminal windows from this directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

```bash
python collector.py --interval 10 --db data/observations.db
```

### Tests

```bash
python -m unittest discover -v
```

### Scope, provenance and hard limitations

- Polymarket market metadata reference prices are **SOURCE_REPORTED**, not independently verified Chainlink values. The `ORACLE_VERIFIED` state is intentionally never assigned by the current API adapter.
- Spot candles from Binance or Coinbase are proxies, not settlement feeds. The collector records their provenance and freshness.
- The new collector polls approximately every 10 seconds; these are timestamped REST observations, **not** a tick-accurate synchronized websocket or historical tick archive. Some calls can fail or be delayed.
- User-entered official outcomes are stored as **USER_ATTESTED**, not independently verified. They are not eligible for an automatic live model confidence score.
- The rolling diagnostic is expanding-window **uncalibrated spot-proxy** evaluation. It cannot prove the strategy works on Polymarket or supply live probabilities.
- Signal gating always returns WAIT until independently oracle-verified reference data, calibrated settlement-matched predictions, and satisfactory quality gates are present. There is no mechanism to bypass this from the dashboard.
- No autonomous paper signals are emitted without those requirements; manual paper entries remain available in the original tab.
- The app does not automatically settle positions. Manual settlements need evidence notes and are not verified by the app.
- Data is stored in SQLite. For multiple replicas, use a managed transactional database and migrate tables. Protect your deployment with authentication and HTTPS; the included Compose file exposes a local port and does not configure authentication.
- Do not deploy this as a public internet-facing service without authentication, HTTPS, backup, monitoring, and rate-limit controls. Do not enter wallet keys into the dashboard.
- Actual fees depend on Polymarket's current market rules and API; the fee slider is a research assumption. Historical quote replay cannot assume full fills or zero latency.

### Further work requiring external infrastructure/data

Independent Chainlink oracle verification, historical official resolution reconciliation, authenticated tick/order-book stream collection, latency-measured replay, calibrated models trained on verified settlement outcomes, monitoring/alerting, cloud hosting, and independent profitability audits require reliable external data, hosting and operational validation. They are **not** completed by this source-code release.

## V5 selective paper scalp screening
The live terminal now shows PAPER SCALP UP or PAPER SCALP DOWN only when trend confirmation, market timing, order-book depth, spread, and entry-price constraints pass. Otherwise it shows NO ENTRY. This is NOT a statistically validated profit signal. Illustrative target prices do not guarantee an executable exit. The candle chart uses closed 1-minute spot candles and refreshes at a configurable 2–60 second cadence; it is not tick-level streaming. Streamlit Cloud may suspend idle apps and does not run the separate collector as an always-on worker.

## V6 near-real-time scalp chart
- New `microstructure.py`: Coinbase BTC-USD public recent-trades polling, deduplicated per Streamlit session. Default dashboard refresh is 2 seconds; actual polling interval and API response time can vary.
- Current minute's provisional candle is built from *observed* Coinbase trades and overlaid on closed historical candles. It is **not** a complete tick feed; trades can be missed between polls, on app sleep, or during network outages. Historical closed candles can be from Binance, so price discontinuities are possible.
- Price bands are mechanically derived from confirmed rolling pivot highs/lows, with ATR-based width. These are heuristic support/resistance proxies, not verified institutional demand/supply zones.
- Both Polymarket contract books show top-five-level USD bid/ask resting depth and imbalance. This does not measure aggressive order flow or guarantee fills.
- PAPER UP/DOWN markers only annotate candidates already passing V5's conservative filter; they are not validated trade recommendations. Live spot trade freshness (>15 seconds) suppresses the display of an existing candidate. Indicators and screening still use completed bars; the provisional candle is visual context only.
- Streamlit Community Cloud cannot guarantee uninterrupted subsecond/tick capture, nor persistent data between restarts. A dedicated websocket service and managed storage are needed for production tick completeness.
- Deploy by uploading `app.py`, `microstructure.py`, and the other included files to the root of the existing GitHub repo, then committing. The Streamlit app should redeploy automatically.

## V7 closed-candle confirmation upgrade
- Adds `confirmations.py` with independently implemented, non-repainting EMA 9/21/55 trend, 12-candle close break of structure, decisive directional candle, and 1.15x median volume confirmation.
- A PAPER scalp signal is suppressed unless all four confirmations pass; otherwise NO ENTRY.
- Adds observed Coinbase aggressive spot buying/selling flow, distinct from Polymarket contract depth.
- Allows a 1-second Streamlit refresh interval, but REST polling is **not** tick-by-tick streaming and may be rate-limited. Continuous WebSocket infrastructure is still required for reliable subsecond feeds.
- No real-money trading and no claim of replicating Bucko's proprietary strategy or having a validated edge.
- Tested with `pytest -q` (21 tests).

## V8: in-browser WebSocket streaming chart

The Live terminal now embeds a Lightweight Charts v4 candlestick chart. It subscribes directly from the browser to Coinbase Exchange's public `matches` channel for `BTC-USD` (`wss://ws-feed.exchange.coinbase.com`). The current 1-minute candle changes with observed trades without a Streamlit rerun. There is a feed-status indicator, last-trade age, 60-second inferred aggressive trade flow, confirmed pivot-derived supply/demand price lines, and a source-reported price-to-beat line. The old snapshot chart remains under an expander.

**Caveats:** Browser WebSocket connectivity and CDN access are required. The feed can drop messages or disconnect, and this implementation does not reconstruct missed trades after reconnection. Closed historical bars and the streaming exchange may differ in provenance. The chart is Coinbase BTC-USD spot, not Chainlink oracle settlement data or Polymarket order execution. Pivot-derived zones are descriptive, not independently verified liquidity. The chart does not claim proprietary Bucko signals or automatically execute orders. Streamlit reruns may recreate the iframe; for production-grade persistent tick capture and execution research, use a separate always-on backend and database.

## V9 visual overlay
The streaming Coinbase chart now paints translucent historical swing-pivot supply/demand rectangles and unfilled three-candle fair-value gaps, and attaches historical paper LONG/SHORT confirmation arrows to their closed candles. The final candle is treated as provisional and excluded from signal generation. These overlays are price-action heuristics, **not** Bucko's undisclosed proprietary indicator, validated trade opportunities, or live real-money entry instructions. Existing Streamlit-side NO ENTRY filters still apply; arrows are historical technical confirmations, not trade executions. Chart data and Polymarket settlement references may differ. The browser WebSocket can disconnect or miss trades. This version does not execute orders.
