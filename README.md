# BTC15 V21 — Trading markers and market context
Preserves V20 chart styling and Coinbase live 10-second chart.
Adds visible automatic paper BUY and SELL markers, reason, $10 illustrative stake, entry, target, stop, last exit and P&L. Browser-local open position persistence with a 15-minute max recovery window. BTC spot-direction simulation only; not a real order.
Adds best-effort public Polymarket/Kalshi read-only indicative quotes in a small chip. These may be unavailable because of CORS, contract mapping, or API changes. They are NOT integrated into entry/exit eligibility and NOT real fill quotes. Polymarket outcome prices are indicative, not asks; Kalshi ask is displayed when available. Do not compare prices or outcomes without confirming strike, time window and settlement index.
Stops use V20's existing simulated net-return/flip/time logic; the visible target/stop are illustrative BTC price levels, not exact contract prices. Chart style unchanged.
No claims of guaranteed profitability, venue price parity, durable server-side execution, or proprietary Bucko replication.
