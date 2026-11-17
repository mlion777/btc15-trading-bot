# BTC15 V26 — Selective A/B and sustained trends

Replace `terminal.html` only. Chart styling remains the same.

- Grade C is never shown as a trade recommendation or eligible for a new paper trade. Grade A requires 1m, 5m and 15m aligned timeframe votes plus micro confirmation. Grade B requires 1m and 5m aligned votes plus micro confirmation. These are heuristics, not calibrated probabilities.
- Requires a stable A/B side and grade for 40 seconds before any paper entry. A new trade is limited to **one per 15-minute contract slot** in the current browser (localStorage); avoids churning/reversals in the same window.
- No exits on signal flips. Paper exits use a -35% emergency threshold, +12% target / -15% stop only after 60 seconds, a 420-second maximum hold, or exit 45 seconds before expiry. These thresholds are *untested hypotheses* and can lose money; holding longer is not automatically better.
- Keeps 1-minute historical context while the first 36 genuine 10-second bars build, then switches once to the live 10-second chart; avoids giant candles and zoom resets on every tick.
- Contract paper trading uses best-effort Polymarket CLOB quotes, illustrative 1% fee per side, and is not a verified executable strategy. Kalshi remains informational only. Browser must remain open. If quotes are unavailable, new entries are blocked. This is not a promise of a high win rate.
- V26 uses a fresh local browser paper ledger to prevent earlier V25 C-grade/flip trades from appearing in the new history. Prior V25 history is not deleted.
