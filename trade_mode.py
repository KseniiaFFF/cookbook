import time
import hmac
import hashlib
import requests
import logging


from config import BASE_URL
from functools import lru_cache
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)

balance_cache_time = {}
balance_cache = {}


def sign(secret_key: str, query: str):
    if isinstance(query, dict):
        query = "&".join([f"{k}={v}" for k, v in query.items()])
    return hmac.new(
        secret_key.encode(),
        query.encode(),
        hashlib.sha256
    ).hexdigest()


def get_server_time(base_url=BASE_URL):
    try:
        url = f"{base_url}/fapi/v1/time"
        response = requests.get(url, timeout=5)
        return response.json()["serverTime"]
    except Exception as e:
        logger.exception(f'Time sync error {e}')
        return int(time.time() * 1000)


@lru_cache(maxsize=1)
def get_exchange_info():

    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_symbol_info(symbol):

    data = get_exchange_info()

    for s in data["symbols"]:
        if s["symbol"] == symbol.upper():
            return s
    return None


def adjust_price_precision(symbol: str, price: float) -> str | None:

    info = get_symbol_info(symbol)
    if not info:
        raise ValueError(f"No symbol info: {symbol}")

    price_filter = next(f for f in info["filters"] if f["filterType"] == "PRICE_FILTER")

    tick = Decimal(price_filter["tickSize"])
    price = Decimal(str(price))

    adjusted = (price / tick).to_integral_value(rounding=ROUND_DOWN) * tick

    return format(adjusted, "f")

#возвращает корректное количество строкой, используя информацию из get_symbol_info_cached
# def adjust_quantity_precision(symbol: str, qty: float) -> str:

#     info = get_symbol_info(symbol)

#     if not info:
#         raise ValueError(f"No symbol info: {symbol}")

#     lot_filter = next(f for f in info["filters"] if f["filterType"] == "LOT_SIZE")

#     step = Decimal(lot_filter["stepSize"])
#     min_qty = Decimal(lot_filter["minQty"])

#     qty = Decimal(str(qty))

#     adjusted = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step

#     if adjusted < min_qty:
#         adjusted = min_qty

#     return format(adjusted, "f")

def normalize_quantity(symbol: str, qty: float) -> str:

    info = get_symbol_info(symbol)

    if not info:
        raise ValueError(f"No symbol info: {symbol}")

    lot_filter = next(
        f for f in info["filters"]
        if f["filterType"] == "LOT_SIZE"
    )

    max_qty_filter = next(
        (f for f in info["filters"] if f["filterType"] == "MARKET_LOT_SIZE"), None)

    step = Decimal(lot_filter["stepSize"])
    min_qty = Decimal(lot_filter["minQty"])
    max_qty = Decimal(max_qty_filter["maxQty"]) if max_qty_filter else Decimal("1000000")

    qty = Decimal(str(qty))

    # округление вниз до step
    normalized = (qty // step) * step

    if normalized > max_qty:
        normalized = max_qty * Decimal("0.95")

    # защита от нуля
    if normalized <= 0:
        normalized = min_qty

    # защита от minQty
    if normalized < min_qty:
        normalized = min_qty

    # финальная нормализация (чистый формат Binance)
    normalized = normalized.quantize(step, rounding=ROUND_DOWN)

    return format(normalized, "f")


def place_market_order(api_key, secret_key, symbol, side, quantity):

    qty = normalize_quantity(symbol, quantity)

    params = {
        "symbol" : symbol,
        "side" : side,
        "type" : "MARKET",
        "quantity" : qty,
        "timestamp" : int(__import__("time").time() * 1000),
        "recvWindow" : 5000
    }
    
    query = "&".join([f"{k}={v}" for k, v in params.items()])

    signature = sign(secret_key, query)

    url = f"{BASE_URL}/fapi/v1/order?{query}&signature={signature}"

    headers = {
        "X-MBX-APIKEY" : api_key
    }

    r = requests.post(
        url,
        headers=headers,
        timeout=10
    )

    try:
        data = r.json()

    except Exception:
        logger.error(r.text)
        return None
    
    if r.status_code != 200:
        logger.error(f"Order error: {data}")
        return None
    
    return data


def get_order(api_key: str, secret_key: str, symbol: str, order_id: int):

    params = {
        "symbol": symbol,
        "orderId" : order_id,
        "timestamp" : int(__import__("time").time() * 1000)
    }

    query = "&".join([f"{k}={v}" for k, v in params.items()])
    signature = sign(secret_key, query)

    url = f"{BASE_URL}/fapi/v1/order?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    r = requests.get(url, headers=headers, timeout=10)

    if r.status_code != 200:
        logger.warning(f"Order fetch error: {r.text}")
        return None

    return r.json()


def get_open_orders(api_key, secret_key, symbol):

    params = {
        "symbol" : symbol,
        "timestamp" : int(time.time() * 1000)
    }

    query = "&".join([f"{k}={v}" for k, v in params.items()])
    sig = sign(secret_key, query)
    url = f"{BASE_URL}/fapi/v1/openOrders?{query}&signature={sig}"
    headers = {"X-MBX-APIKEY": api_key}

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            error_data = r.json() if r.text else {}
            code = error_data.get("code")

            if code == -1121:
                logger.warning(f"Символ {symbol}  невалиден или еще не активен на тестнет")
                return[]
            
            logger.warning(f"Ошибка получения открытых ордеров: {r.text}")
            return []
        return r.json()
    except Exception:
        logger.exception(f"Ошибка запроса открытых ордеров {symbol}")
        return []


price_cache = {}
price_cache_time = {}

def get_mark_price(symbol):

    now = time.time()

    if symbol in price_cache and now - price_cache_time.get(symbol, 0) < 3:
        return price_cache[symbol]
    
    url = f"{BASE_URL}/fapi/v1/premiumIndex"

    params = {
        "symbol" : symbol
    }

    r = requests.get(url, params=params, timeout=5)

    data = r.json()

    price = float(data["markPrice"])
    price_cache[symbol] = price
    price_cache_time[symbol] = now
    return price


def set_leverage(api_key: str, secret_key: str, symbol: str, leverage: int):
    leverage = max(1, min(5, int(leverage)))

    params = {
        "symbol": symbol,
        "leverage": leverage,
        "timestamp": int(time.time() * 1000),
        "recvWindow": 5000
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    signature = sign(secret_key, query)

    url = f"{BASE_URL}/fapi/v1/leverage?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    r = requests.post(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Set leverage error: {r.text}")
    return r.json()


def calculate_sl_tp_from_deposit_risk(entry_price: float, direction: str, sl_distance: float, deposit_usdt: float, risk_percent: float = 3, rr_ratio: float = 2.5):

    if entry_price <= 0:
        raise ValueError("entry price must be > 0")
    
    if sl_distance <= 0:
        raise ValueError("sl_distance must be > 0")
    
    if deposit_usdt <= 0:
        raise ValueError("deposit_usdt must be > 0")
    
    risk_usdt = deposit_usdt * (risk_percent / 100)
    # sl_pct = threshold_percent / 100
    # sl_distance = entry_price * sl_pct

    qty = risk_usdt / sl_distance

    side = direction.upper()

    if side == "LONG":
        stop_loss = entry_price - sl_distance
        take_profit = entry_price + (sl_distance * rr_ratio)

    elif side == "SHORT":
        stop_loss = entry_price + sl_distance
        take_profit = entry_price - (sl_distance * rr_ratio)
    else:
        raise ValueError("direction must be LONG or SHORT")
    
    if stop_loss <= 0 or take_profit <= 0:
        raise ValueError("SL/TP is invalid (<=0)")
    
    return {
        "qty": qty,
        # "leverage": leverage,
        "stop_loss" : stop_loss,
        "take_profit" : take_profit,
        "risk_usdt" : risk_usdt,
        "sl_distance": sl_distance
    }


# def get_futures_usdt_balance(api_key: str, secret_key: str) -> float:

#     global last_balance_time, cached_balance

#     now = time.time()
#     if now - last_balance_time < 8:
#         return cached_balance

#     params = {
#         "timestamp": int(time.time() * 1000),
#         "recvWindow": 5000
#     }

#     query = "&".join([f"{k}={v}" for k, v in params.items()])

#     signature = sign(secret_key, query)

#     url = f"{BASE_URL}/fapi/v2/balance?{query}&signature={signature}"
#     headers = {"X-MBX-APIKEY": api_key}

#     r = requests.get(url, headers=headers, timeout=10)

#     if r.status_code != 200:
#         raise RuntimeError(f"Balance fetch error: {r.text}")
    
#     data = r.json()

#     usdt_row = next((item for item in data if item.get("asset") == "USDT"), None)

#     if not usdt_row:
#         raise RuntimeError("USDT balance not found")
    
#     cached_balance = float(usdt_row["availableBalance"])

#     last_balance_time = now
    
#     return cached_balance

def get_futures_usdt_balance(api_key: str, secret_key: str) -> float:

    now = time.time()

    if (
        api_key in balance_cache
        and now - balance_cache_time.get(api_key, 0) < 8
    ):
        return balance_cache[api_key]

    params = {
        "timestamp": int(time.time() * 1000),
        "recvWindow": 5000
    }

    query = "&".join([f"{k}={v}" for k, v in params.items()])

    signature = sign(secret_key, query)

    url = f"{BASE_URL}/fapi/v2/balance?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    r = requests.get(url, headers=headers, timeout=10)

    if r.status_code != 200:
        raise RuntimeError(f"Balance fetch error: {r.text}")

    data = r.json()

    usdt_row = next(
        (item for item in data if item.get("asset") == "USDT"),
        None
    )

    if not usdt_row:
        raise RuntimeError("USDT balance not found")

    # balance = float(usdt_row["availableBalance"])
    balance = float(usdt_row["balance"])

    balance_cache[api_key] = balance
    balance_cache_time[api_key] = now

    return balance


def get_open_position_amt(api_key: str, secret_key: str, symbol: str) -> float:
    params = {
        "timestamp": int(time.time() * 1000),
        "recvWindow": 5000
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    signature = sign(secret_key, query)

    url = f"{BASE_URL}/fapi/v2/positionRisk?{query}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Position fetch error: {r.text}")

    data = r.json()
    row = next((x for x in data if x.get("symbol") == symbol), None)
    if not row:
        return 0.0

    return abs(float(row.get("positionAmt", 0.0)))


# def place_conditional_order(params: dict):

#     try:
   
#         query = "&".join([f"{k}={v}" for k, v in params.items()])
#         signature = sign(API_SECRET, query)
        
#         url = f"{BASE_URL}/fapi/v1/algoOrder?{query}&signature={signature}"
#         headers = {"X-MBX-APIKEY": API_KEY}

#         r = requests.post(url, headers=headers, timeout=10)

#         data = r.json()

#         if r.status_code != 200:
#             logger.error(f"Conditional order error: {data}")
#             return None
#         return data
    
#     except Exception as e:
#         logger.exception("Ошибка place_algo_order")
#         return None
    
def place_conditional_order(api_key, secret_key, params: dict):

    try:

        query = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = sign(secret_key, query)

        url = f"{BASE_URL}/fapi/v1/algoOrder?{query}&signature={signature}"

        headers = {"X-MBX-APIKEY": api_key}

        r = requests.post(url, headers=headers, timeout=10)

        data = r.json()

        if r.status_code != 200:
            logger.error(f"Conditional order error: {data}")
            return None

        return data

    except Exception:
        logger.exception("Ошибка place_conditional_order")
        return None


def execute_signal(signal, api_key, secret_key):

    try:
        symbol = signal.symbol

        side = "BUY" if signal.direction == "LONG" else "SELL"
        opposite_side = "SELL" if side == "BUY" else "BUY"

        set_leverage(api_key, secret_key, symbol, 5)

        open_orders = get_open_orders(api_key, secret_key, symbol)

        position_amt = get_open_position_amt(api_key,secret_key,symbol)

        if position_amt > 0:
            print(f"Symbol: {symbol}. Pos open.")
            return

        if open_orders:
            print(f" Skip {symbol}. Open")
            return


        price = get_mark_price(symbol)
        deposit_usdt = get_futures_usdt_balance(api_key, secret_key)

        sl_tp = calculate_sl_tp_from_deposit_risk(
            entry_price=price,
            direction=signal.direction,
            sl_distance=float(signal.sl_distance),
            deposit_usdt=deposit_usdt,
            risk_percent=3,
            rr_ratio=2.5
        )

        qty = sl_tp["qty"]
        qty_str = normalize_quantity(symbol, qty)

        result = place_market_order(
            api_key=api_key,
            secret_key=secret_key,
            symbol=symbol,
            side=side,
            quantity=float(qty_str)
        )

        if not result:
            print(f"❌ Не удалось открыть позицию {symbol}")
            return

        print("Order result:", result)


        sl_side = opposite_side
        
        # sl_params = {
        #         "symbol": symbol,
        #         "side": sl_side,
        #         # "type": "STOP_MARKET",
        #         "algoType": "STOP_MARKET",
        #         "triggerPrice": str(round(sl_tp["stop_loss"], 6)),
        #         # "stopPrice": str(round(sl_tp["stop_loss"], 6)),
        #         "closePosition": "true",
        #         # "timeInForce": "GTC",
        #         "workingType": "MARK_PRICE",
        #         "timestamp": get_server_time(BASE_URL)
        #     }

        # tp_params = {
        #         "symbol": symbol,
        #         "side": sl_side,  # SELL если LONG, BUY если SHORT
        #         # "type": "TAKE_PROFIT_MARKET",
        #         "algoType": "TAKE_PROFIT_MARKET",
        #         "triggerPrice": str(round(sl_tp["take_profit"], 6)),
        #         # "stopPrice": str(round(sl_tp["take_profit"], 6)),
        #         "closePosition": "true",
        #         # "timeInForce": "GTC",
        #         "workingType": "MARK_PRICE",
        #         "timestamp": get_server_time(BASE_URL)
        #     }


        sl_params = {
            "symbol": symbol,
            "side": sl_side,
            "type": "STOP_MARKET",
            "algoType": "CONDITIONAL",           
            "triggerPrice": adjust_price_precision(symbol, sl_tp["stop_loss"]),
            "closePosition": "true",
            "workingType": "MARK_PRICE",
            "timestamp": int(time.time() * 1000)
        }

        tp_params = {
            "symbol": symbol,
            "side": sl_side,
            "type": "TAKE_PROFIT_MARKET",
            "algoType": "CONDITIONAL",           
            "triggerPrice": adjust_price_precision(symbol, sl_tp["take_profit"]),
            "closePosition": "true",
            "workingType": "MARK_PRICE",
            "timestamp": int(time.time() * 1000)
        }

        sl_result = place_conditional_order(api_key, secret_key, sl_params)
        tp_result = place_conditional_order(api_key, secret_key, tp_params)

        print(f"SL: {sl_tp['stop_loss']:.4f} → {'✅' if sl_result else '❌'}")
        print(f"TP: {sl_tp['take_profit']:.4f} → {'✅' if tp_result else '❌'}")

    except Exception as e:
        logger.exception(f"Ошибка при исполнении сигнала {signal.symbol}")
        print(f"Ошибка исполнения сигнала: {e}")