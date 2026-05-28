import time

from binance_info import start_scanner
from log_settings import set


set()
start_scanner()

while True:
    time.sleep(1)