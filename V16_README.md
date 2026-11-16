# BTC15 V16 — chart-first terminal (paper only)

This is a clean package built from the V15 exit-fix release, retaining its dependencies.

## Changes
- Chart-first layout with large 690px native Plotly candlestick panel, supply/demand bands, EMA9/21/55, and source-reported price-to-beat line.
- LONG/SHORT WATCH annotation on chart for current directional watch, separate from actual paper-entry markers.
- Recorded simulated entries marked with upward/downward triangles at the corresponding candle and timestamp.
- Compact dark trading-terminal CSS, collapsed settings sidebar, and recent paper P&L, win rate, count and open positions.
- Retains 15-minute countdown, ask quotes, existing paper-entry filters and V15 stop-loss rules.
- No real trades, no broker keys, no claim to replicate proprietary Bucko AI signal code.

## Deploy
Back up the existing repository, then replace root application files with the contents of this ZIP. Keep Streamlit secrets/configuration. `app.py` and `requirements.txt` must be at repository root. Do not upload the enclosing folder.

## Known limitations
- Not tested on the user's deployed Streamlit instance.
- A Streamlit Community Cloud app may sleep and local SQLite data may be ephemeral. Continuous autonomous trading needs persistent hosting/storage.
- Market data, oracle reference, fills and actual spread/fees may differ. Signal votes are not calibrated probabilities.
- Existing V15 exit rules remain experimental and are not guaranteed to maximize profit.
