# BTC15 V27 — live supply and demand overlay

Replace **terminal.html only** on top of V26. The original chart, A/B trading rules, paper trading, market-price checks, and streaming architecture remain unchanged.

Requested custom colors (opposite the usual convention):
- **SUPPLY = GREEN** filled rectangle
- **DEMAND = RED** filled rectangle

Zones are estimated from three completed 10-second candles, with recent 1-minute candle history used to seed initial zones. A bullish fair-value imbalance is labeled DEMAND and a bearish imbalance SUPPLY. Zones are automatically removed when a *completed* candle closes beyond the relevant invalidation boundary. They redraw in place as new candles stream, and on chart zoom, pan, and resize. The overlay does not block chart interaction.

The overlay is a technical visualization, not proof of actual resting liquidity. V27 has syntax checks but has not been tested in the deployed browser. No claims of guaranteed profits.
