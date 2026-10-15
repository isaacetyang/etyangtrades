import asyncio, os, json, time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from .deriv import DerivClient, DerivError
from .analysis import analyse_prices, analyse_digits
from .risk import RiskManager

load_dotenv()
APP_ID = os.getenv("DERIV_APP_ID", "").strip()
APP_ID_CONFIGURED = APP_ID.isdigit()
LIVE_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
app = FastAPI(title="Deriv AI Trading Pro", version="1.0.0")
BASE = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")
sessions = {}
bot_tasks = {}

class ConnectRequest(BaseModel):
    token: str = Field(min_length=5)
    account_mode: str = "demo"

class AnalyseRequest(BaseModel):
    token: str = ""
    symbol: str = "R_10"

@app.get("/")
async def home():
    return FileResponse(BASE / "frontend" / "index.html")

@app.get("/api/config")
async def config():
    return {
        "status": "configured" if APP_ID_CONFIGURED else "not_configured",
        "app_id_configured": APP_ID_CONFIGURED,
        "live_trading_enabled": LIVE_ENABLED,
        "default_mode": "paper",
        "message": ("Deriv App ID is configured." if APP_ID_CONFIGURED else
                    "Missing or invalid DERIV_APP_ID. Add your numeric legacy Deriv App ID in Render Environment Variables, then redeploy.")
    }

@app.get("/api/health")
async def health():
    return {"ok": True, "app_id_configured": APP_ID_CONFIGURED}

@app.post("/api/connect")
async def connect(req: ConnectRequest):
    if not APP_ID_CONFIGURED:
        raise HTTPException(503, "Deriv App ID is not configured on the server. Add DERIV_APP_ID in Render Environment Variables and redeploy.")
    mode = req.account_mode.lower()
    if mode not in ("demo", "real"):
        raise HTTPException(400, "Account mode must be demo or real.")
    if mode == "real" and not LIVE_ENABLED:
        raise HTTPException(403, "Real trading is disabled in server configuration.")
    try:
        client = DerivClient(APP_ID, req.token)
        result = await client.authorize()
        auth = result.get("authorize", {})
        virtual = bool(auth.get("is_virtual", 0))
        if mode == "demo" and not virtual:
            raise HTTPException(400, "Selected Demo but the supplied token belongs to a real account.")
        if mode == "real" and virtual:
            raise HTTPException(400, "Selected Real but the supplied token belongs to a virtual account.")
        sid = str(int(time.time() * 1000))
        account_balance = float(auth.get("balance", 0) or 0)
        sessions[sid] = {"token": req.token, "mode": mode, "currency": auth.get("currency", "USD"),
                         "loginid": auth.get("loginid", ""), "balance": account_balance}
        return {"session_id": sid, "loginid": auth.get("loginid"), "currency": auth.get("currency"),
                "balance": account_balance, "is_virtual": virtual}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400, str(e))

def get_client(session_id: str):
    s = sessions.get(session_id)
    if not s: raise HTTPException(401, "Connect your Deriv account first.")
    return DerivClient(APP_ID, s["token"]), s

@app.get("/api/symbols")
async def symbols(session_id: str):
    client, _ = get_client(session_id)
    try:
        data = await client.symbols()
        return {"symbols": data.get("active_symbols", [])}
    except Exception as e: raise HTTPException(400, str(e))

@app.post("/api/analyse")
async def analyse(req: AnalyseRequest):
    try:
        client = DerivClient(APP_ID, req.token) if req.token else DerivClient(APP_ID)
        data = await client.history(req.symbol, 150)
        prices = data.get("history", {}).get("prices", [])
        return {"symbol": req.symbol, "analysis": analyse_prices(prices),
                "digits": analyse_digits(prices), "points": len(prices),
                "latest_price": prices[-1] if prices else None}
    except Exception as e: raise HTTPException(400, str(e))

@app.get("/api/balance")
async def balance(session_id: str):
    client, _ = get_client(session_id)
    try:
        r = await client.balance()
        return r.get("balance", {})
    except Exception as e: raise HTTPException(400, str(e))

@app.websocket("/ws/bot")
async def bot_socket(ws: WebSocket):
    await ws.accept()
    task = None
    stop_event = asyncio.Event()
    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action")
            if action == "start":
                if task and not task.done():
                    await ws.send_json({"type":"error","message":"Bot is already running."}); continue
                task = asyncio.create_task(run_bot(ws, msg, stop_event))
            elif action == "stop":
                stop_event.set()
                if task: task.cancel()
                await ws.send_json({"type":"status","message":"Bot stop requested."})
    except WebSocketDisconnect:
        stop_event.set()
        if task: task.cancel()
    except Exception as e:
        try: await ws.send_json({"type":"error","message":str(e)})
        except: pass

async def run_bot(ws, cfg, stop_event):
    sid = cfg.get("session_id")
    session = sessions.get(sid) if sid else None
    mode = cfg.get("mode", "paper")
    live_orders = mode in ("demo_auto", "real_auto")
    if live_orders and not session:
        await ws.send_json({"type":"error","message":"Connect a Deriv account before enabling execution."}); return
    if mode == "real_auto" and (not LIVE_ENABLED or not cfg.get("confirm_real")):
        await ws.send_json({"type":"error","message":"Real trading requires server enablement and explicit confirmation."}); return
    if mode == "demo_auto" and session and session["mode"] != "demo":
        await ws.send_json({"type":"error","message":"Demo auto mode requires a virtual account."}); return
    if mode == "real_auto" and session and session["mode"] != "real":
        await ws.send_json({"type":"error","message":"Real auto mode requires a real account."}); return
    client = DerivClient(APP_ID, session["token"] if session else "")
    risk = RiskManager()
    balance = float(session["balance"]) if session else float(cfg.get("paper_balance", 10))
    risk.begin_session(balance)
    requested_stake = float(cfg.get("stake", 0.25))
    symbol = cfg.get("symbol", "R_10")
    contract_type = cfg.get("contract_type", "CALL")
    min_conf = int(cfg.get("min_confidence", 70))
    currency = session["currency"] if session else "USD"
    recovery_mode = False
    await ws.send_json({"type":"status","message":f"Engine started in {mode.upper()} mode. No profit is guaranteed."})
    try:
        while not stop_event.is_set():
            try:
                hist = await client.history(symbol, 150)
                prices = hist.get("history", {}).get("prices", [])
                analysis = analyse_prices(prices)
                await ws.send_json({"type":"analysis","analysis":analysis,"symbol":symbol,
                                    "latest_price":prices[-1] if prices else None})
                if analysis["signal"] == "WAIT" or analysis["confidence"] < min_conf:
                    await ws.send_json({"type":"status","message":"Waiting: signal does not meet confidence threshold."})
                    await asyncio.sleep(5); continue
                selected_type = contract_type
                if contract_type in ("CALL","PUT"):
                    selected_type = analysis["signal"]
                # Digit and special contract types are never auto-selected from price trend.
                elif contract_type in ("DIGITOVER","DIGITUNDER","DIGITEVEN","DIGITODD","DIGITMATCH","DIGITDIFF","ACCU","MULTUP","MULTDOWN"):
                    await ws.send_json({"type":"status","message":"This contract needs its own validated strategy/parameters. Automatic entry skipped; use proposal preview/manual mode."})
                    await asyncio.sleep(10); continue
                allowed, reason = risk.can_trade(balance, recovery=recovery_mode)
                stake = risk.stake_for(balance, requested_stake)
                if not allowed or stake <= 0:
                    await ws.send_json({"type":"risk_stop","message":reason or "Stake is below minimum."}); break
                if not live_orders:
                    await ws.send_json({"type":"paper_trade","symbol":symbol,"contract_type":selected_type,
                                        "stake":stake,"confidence":analysis["confidence"],
                                        "message":"Paper signal only; no order sent."})
                    await asyncio.sleep(10); continue
                proposal = await client.proposal(symbol, selected_type, stake, currency, duration=5, duration_unit="t")
                p = proposal.get("proposal", {})
                buy = await client.buy(p["id"], float(p.get("ask_price", stake)))
                contract_id = buy.get("buy", {}).get("contract_id")
                await ws.send_json({"type":"trade_open","contract_id":contract_id,"stake":stake,
                                    "contract_type":selected_type,"symbol":symbol})
                final = None
                for _ in range(90):
                    await asyncio.sleep(2)
                    status = await client.contract_status(int(contract_id))
                    poc = status.get("proposal_open_contract", {})
                    if poc.get("is_sold"):
                        final = poc; break
                if final is None:
                    await ws.send_json({"type":"status","message":"Contract still open or status timeout; bot will pause for safety."})
                    break
                profit = float(final.get("profit", 0))
                risk.record_result(profit, was_recovery=recovery_mode)
                balance += profit
                await ws.send_json({"type":"trade_closed","contract_id":contract_id,"profit":profit,
                                    "balance_estimate":balance,"status":final.get("status")})
                recovery_mode = profit < 0
                if recovery_mode:
                    await ws.send_json({"type":"recovery","attempts_used":risk.recovery_attempts,
                                        "max_attempts":risk.max_recovery_attempts,
                                        "message":"Loss recorded. Reassessing; no stake escalation."})
                if risk.consecutive_losses >= risk.max_consecutive_losses:
                    await ws.send_json({"type":"risk_stop","message":"Three consecutive losses. Trading stopped."}); break
                if risk.starting_balance and risk.daily_pnl <= -(risk.starting_balance * risk.daily_loss_limit_pct / 100):
                    await ws.send_json({"type":"risk_stop","message":"Daily loss limit reached. Trading stopped."}); break
                await asyncio.sleep(3)
            except asyncio.CancelledError: raise
            except Exception as e:
                await ws.send_json({"type":"error","message":str(e)})
                await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    finally:
        await ws.send_json({"type":"status","message":"Trading engine stopped."})
