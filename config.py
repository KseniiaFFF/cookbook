import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, "signals.txt")
FILE_PATH_TEST = os.path.join(BASE_DIR, "back_signals.txt")
BASE_URL = "https://fapi.binance.com"
# BASE_URL = "https://testnet.binancefuture.com"
MIN_VOLUME = 100_000_000
INTERVAL = "5m"
LIMIT = 50
# CHANGE_THRESHOLD = 1.0
IMPULSE_CANDLES = 3
COMPRESSION_CANDLES = 2
WATCH_COMPRESSION_MAX  = 0.7
READY_COMPRESSION_MAX = 0.4
#0.4
WATCH_PULLBACK_MAX  = 0.8
READY_PULLBACK_MAX = 0.35
#0.35
MIN_SCORE = 2
#2

MAX_PAIRS = 350
CACHE_LIFETIME = 120
KLINES_CACHE_TTL = 60
SIGNAL_COOLDOWN = 600 

