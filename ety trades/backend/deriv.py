import json, itertools
import websockets

class DerivError(Exception): pass

class DerivClient:
    def __init__(self, app_id: str, token: str = ""):
        if not app_id or app_id == "YOUR_DERIV_APP_ID":
            raise DerivError("Set DERIV_APP_ID in .env first.")
        self.url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
        self.token = token
        self._ids = itertools.count(1)

    async def request(self, payload: dict, authorize: bool = False):
        async with websockets.connect(self.url, open_timeout=15, close_timeout=5) as ws:
            if authorize and self.token:
                await ws.send(json.dumps({"authorize": self.token, "req_id": next(self._ids)}))
                auth = json.loads(await ws.recv())
                if auth.get("error"):
                    raise DerivError(auth["error"].get("message", "Authorization failed"))
            payload = dict(payload)
            payload["req_id"] = next(self._ids)
            await ws.send(json.dumps(payload))
            while True:
                response = json.loads(await ws.recv())
                if response.get("req_id") == payload["req_id"] or "error" in response:
                    if response.get("error"):
                        raise DerivError(response["error"].get("message", "Deriv API error"))
                    return response

    async def authorize(self):
        return await self.request({"authorize": self.token})

    async def balance(self):
        return await self.request({"balance": 1}, authorize=True)

    async def symbols(self):
        return await self.request({"active_symbols": "brief", "product_type": "basic"})

    async def history(self, symbol: str, count: int = 100):
        return await self.request({"ticks_history": symbol, "count": count, "end": "latest",
                                   "style": "ticks"})

    async def proposal(self, symbol: str, contract_type: str, amount: float, currency: str,
                       duration: int = 5, duration_unit: str = "t", barrier: str = None,
                       growth_rate: float = None):
        p = {"proposal": 1, "amount": amount, "basis": "stake", "contract_type": contract_type,
             "currency": currency, "duration": duration, "duration_unit": duration_unit,
             "underlying_symbol": symbol}
        if barrier is not None: p["barrier"] = str(barrier)
        if growth_rate is not None: p["growth_rate"] = growth_rate
        return await self.request(p, authorize=True)

    async def buy(self, proposal_id: str, price: float):
        return await self.request({"buy": proposal_id, "price": price}, authorize=True)

    async def contract_status(self, contract_id: int):
        return await self.request({"proposal_open_contract": 1, "contract_id": contract_id},
                                  authorize=True)
