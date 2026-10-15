# DERIV AI TRADING PRO

A local web dashboard and Python backend for Deriv market analysis and controlled automated trading.

## Important
- Starts in **PAPER / DEMO-SAFE mode**. Paper mode analyses live public ticks but does not place real orders.
- Demo or real trading requires a Deriv API token with the required permissions and an App ID.
- Real trading is deliberately gated by `LIVE_TRADING_ENABLED=true`, an explicit UI confirmation, and a separate live-account selection.
- No strategy can guarantee profit or recover losses in three trades. The recovery counter is a maximum number of *additional qualified opportunities*, not a promise to win.
- Start with demo credentials. Never share your token with anyone. Do not commit `.env`.

## Requirements
- Python 3.10+
- A Deriv account and Deriv App ID
- A Deriv API token with `read` and `trade` permissions for automated execution
- Internet connection

## Install (Windows PowerShell)
```powershell
cd deriv_ai_trading_pro
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and set your Deriv App ID. Keep `LIVE_TRADING_ENABLED=false` initially.

## Run
```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000

## Demo workflow
1. Create an API token in your Deriv account with read/trade permissions. Use a **demo** token/account first.
2. Enter App ID and token in the dashboard. The token is held in the backend process memory only for this session; it is not written to disk.
3. Select `Demo`, connect, and confirm the account is virtual.
4. Run analysis first. Paper mode is always available without a token.
5. To place demo orders, turn on Demo Auto Trading and set a small stake. Use the dashboard stop button at any time.

## Enabling real trading
Real trading is disabled by default. To enable the option:
1. Stop the bot and close the app.
2. Set `LIVE_TRADING_ENABLED=true` in `.env`.
3. Restart the server.
4. Connect using a real-account token, explicitly select `Real`, and confirm the warning in the UI.
5. Start with the minimum affordable stake. The configured stake is capped by risk controls.

Do not expose this local server to the public internet. Use HTTPS, authentication, secure secret storage and rate limiting before any deployment.

## Included trading categories
- Rise/Fall: `CALL` / `PUT`
- Higher/Lower: `HIGHER` / `LOWER`
- Over/Under: `DIGITOVER` / `DIGITUNDER`
- Even/Odd: `DIGITEVEN` / `DIGITODD`
- Matches/Differs: `DIGITMATCH` / `DIGITDIFF`
- Multipliers: `MULTUP` / `MULTDOWN`
- Accumulators: `ACCU`

Contract availability varies by symbol, account jurisdiction and Deriv product. The app asks Deriv for a proposal before every purchase; unsupported combinations are rejected and logged.

## Analysis engine
The built-in signal is an educational heuristic based on EMA 9/21, RSI 14, MACD and recent momentum. Digit contracts additionally use recent last-digit frequencies. It is not a trained predictive AI model and does not imply a profitable edge. Use backtesting and demo forward-testing before risking funds.

## Risk defaults
- Initial suggested balance range: USD 5–10
- Suggested stake: USD 0.25 (editable)
- Per-trade stake cap: 2% of current balance
- Daily loss stop: 10% of session starting balance
- Maximum consecutive losses: 3
- Maximum recovery attempts after a loss: 3
- No martingale / no automatic stake doubling
- Stop trading when confidence is low, daily loss limit is hit, or API errors occur.

## Tests
```powershell
python -m unittest discover -s tests -v
```

## API notes
The backend uses Deriv's WebSocket API v3 endpoint (`wss://ws.derivws.com/websockets/v3`) with `authorize`, `ticks_history`, `proposal`, `buy`, `proposal_open_contract`, `balance` and `active_symbols` requests. Check current Deriv docs before deployment:
- https://developers.deriv.me/docs/intro/api-overview/
- https://developers.deriv.com/docs/data/active-symbols/
- https://developers.deriv.com/docs/trading/proposal/
- https://developers.deriv.com/docs/trading/buy/

This is an independent sample application and is not affiliated with or endorsed by Deriv.

## Render deployment configuration
In your Render Web Service, open **Environment** and add:
- `DERIV_APP_ID` = your numeric **Legacy Deriv API App ID** (not your account login ID, API token, or new OAuth client ID)
- `LIVE_TRADING_ENABLED` = `false`

Save the changes and trigger a redeploy. Then open `/api/config`. It should return `"status":"configured"` and `"app_id_configured":true`. If it still says `not_configured`, the variable was not saved on the correct Render service, contains a placeholder/non-numeric value, or the service has not restarted with the new environment.

This project currently uses the Legacy Deriv WebSocket v3 endpoint (`ws.derivws.com/websockets/v3?app_id=...`) and legacy `authorize` token flow. A new-platform OAuth client ID/PAT is not a drop-in replacement; migrate the API client to the newer REST + OTP WebSocket flow before using new-platform credentials.
