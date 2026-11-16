V15 paper-exit patch
- Avoid triggering ordinary stop loss from the immediate bid/ask spread alone.
- Wait 20 seconds before ordinary adverse-price stops, while retaining immediate emergency stop at 25% net paper loss.
- Retain 75-second expiry buffer and 8% net take-profit.
- Estimate entry bid using current quoted spread; this is an approximation, not a saved execution quote.
- Paper-only. Not validated profitable. Streamlit restarts can reset SQLite records.
- Keep all modules together; upload root files, not the outer folder.
