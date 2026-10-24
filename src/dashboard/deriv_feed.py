"""Deriv real-time feed — new developer-portal API (2026).

REST  : https://api.derivws.com  (Bearer PAT + Deriv-App-ID)
WS    : public  wss://api.derivws.com/trading/v1/options/ws/public   (market ticks)
WS    : OTP    wss://api.derivws.com/trading/v1/options/ws/{real,demo}
creds : env  DERIV_PAT_TOKEN, DERIV_APP_ID_NEW, DERIV_ACCOUNT_REAL, DERIV_ACCOUNT_DEMO
Read-only by design — this module never sends trading actions.
"""

import asyncio
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    websockets = None
    HAS_WEBSOCKETS = False

REST_BASE = "https://api.derivws.com"
WS_PUBLIC = "wss://api.derivws.com/trading/v1/options/ws/public"
DEFAULT_SYMBOLS = ["R_10", "R_25", "R_50", "R_100"]

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_lock = threading.Lock()
_tweets = {}
_ticker_thread = None
_stop = threading.Event()


def ready() -> bool:
    """True when PAT auth plus app id are present."""
    return bool(os.getenv("DERIV_PAT_TOKEN") and os.getenv("DERIV_APP_ID_NEW"))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('DERIV_PAT_TOKEN', '')}",
        "Deriv-App-ID": os.environ.get("DERIV_APP_ID_NEW", ""),
        "Content-Type": "application/json",
    }


def _rest(path: str, body: bytes = b"{}") -> dict:
    req = urllib.request.Request(
        REST_BASE + path, data=body or None, headers=_headers(), method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def accounts() -> dict:
    """List Deriv option accounts -> {ticket: row dict} keyed by account_type."""
    return {a.get("account_type", "?"): a for a in _rest("/trading/v1/options/accounts", None).get("data", [])}


def balance(mode: str = "demo"):
    """REST account balance for 'real' or 'demo' mode (cash account)."""
    try:
        return accounts().get(mode)
    except Exception:
        return None


def _otp_url(account_id: str) -> str:
    url = _rest(f"/trading/v1/options/accounts/{account_id}/otp").get("data", {}).get("url")
    if not url:
        raise RuntimeError("OTP request returned no url")
    return url


def account_realtime(account_id: str, trades: int = 8) -> dict:
    """One-shote authenticated WS pull: balance (streamed), portfolio, recent trades."""
    out = {"balance": None, "currency": None, "loginid": account_id,
           "positions": [], "trades": [], "ts": datetime.now(timezone.utc).isoformat()}
    async def _run():
        async with websockets.connect(_otp_url(account_id)) as ws:
            await ws.send(json.dumps({"balance": 1, "req_id": 1}))
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            b = r.get("balance") or {}
            out["balance"] = b.get("balance")
            out["currency"] = b.get("currency")
            await ws.send(json.dumps({"portfolio": 1, "req_id": 2}))
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            out["positions"] = (r.get("portfolio") or {}).get("contracts", [])
            await ws.send(json.dumps({"profit_table": 1, "limit": trades, "sort": "DESC",
                                      "description": 1, "req_id": 3}))
            r = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            out["trades"] = (r.get("profit_table") or {}).get("transactions", [])
    asyncio.run(_run())
    return out


def _ticker_main(symbols):
    global _tweets
    while not _stop.is_set():
        if not HAS_WEBSOCKETS:
            return
        try:
            async def _run():
                async with websockets.connect(WS_PUBLIC) as ws:
                    reqs = [{"ticks": s, "subscribe": 1, "req_id": i + 1}
                            for i, s in enumerate(symbols)]
                    for req in reqs:
                        await ws.send(json.dumps(req))
                    while not _stop.is_set():
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                        tick = msg.get("tick")
                        if tick and tick.get("symbol"):
                            with _lock:
                                _tweets[tick["symbol"]] = {"quote": tick.get("quote"),
                                                           "epoch": tick.get("epoch")}
            asyncio.run(_run())
        except Exception:
            _stop.wait(timeout=6.0)  # retry with backoff; daemon thread


def start_ticks(symbols=None):
    """Idempotent: launch background public-tick stream in process."""
    global _ticker_thread
    symbols = symbols or DEFAULT_SYMBOLS
    if not HAS_WEBSOCKETS or (_ticker_thread and _ticker_thread.is_alive()):
        return
    _stop.clear()
    _ticker_thread = threading.Thread(target=_ticker_main, args=(symbols,), daemon=True,
                                      name="deriv-ticker")
    _ticker_thread.start()


def latest_ticks() -> dict:
    with _lock:
        return dict(_tweets)


def stop_ticks():
    _stop.set()
