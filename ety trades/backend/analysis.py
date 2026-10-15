from __future__ import annotations
from typing import List, Dict
import math

def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result

def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains, losses = [], []
    for a, b in zip(values[-period-1:-1], values[-period:]):
        delta = b - a
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyse_prices(prices: List[float]) -> Dict:
    prices = [float(x) for x in prices if x is not None]
    if len(prices) < 30:
        return {"signal": "WAIT", "confidence": 0, "reason": "At least 30 price points are required.",
                "ema9": None, "ema21": None, "rsi14": None, "momentum_pct": 0}
    e9, e21 = ema(prices[-60:], 9), ema(prices[-60:], 21)
    rv = rsi(prices, 14)
    momentum = ((prices[-1] - prices[-6]) / prices[-6] * 100) if prices[-6] else 0
    score = 0
    score += 1 if e9 > e21 else -1
    score += 1 if momentum > 0 else (-1 if momentum < 0 else 0)
    score += 1 if 50 < rv < 70 else (-1 if 30 < rv < 50 else 0)
    if rv >= 75 or rv <= 25:
        score = 0
    signal = "CALL" if score >= 2 else ("PUT" if score <= -2 else "WAIT")
    confidence = min(95, int(50 + abs(score) * 15)) if signal != "WAIT" else 0
    return {"signal": signal, "confidence": confidence, "ema9": round(e9, 6),
            "ema21": round(e21, 6), "rsi14": round(rv, 2),
            "momentum_pct": round(momentum, 4),
            "reason": f"EMA9 {'above' if e9 > e21 else 'below'} EMA21; RSI {rv:.1f}; 5-step momentum {momentum:.3f}%."}

def analyse_digits(prices: List[float]) -> Dict:
    digits = []
    for p in prices[-100:]:
        s = f"{p:.8f}".rstrip("0").replace(".", "")
        if s:
            digits.append(int(s[-1]))
    if len(digits) < 30:
        return {"signal": "WAIT", "confidence": 0, "frequencies": {}, "reason": "Insufficient digit history."}
    counts = {str(i): digits.count(i) for i in range(10)}
    # Descriptive frequency only; a hot/cold digit is not predictive by itself.
    most = max(range(10), key=lambda i: counts[str(i)])
    least = min(range(10), key=lambda i: counts[str(i)])
    return {"signal": "WAIT", "confidence": 0, "frequencies": counts,
            "most_frequent_digit": most, "least_frequent_digit": least,
            "reason": "Digit frequencies are descriptive. No digit bet is recommended from frequency alone."}
