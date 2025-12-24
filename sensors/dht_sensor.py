# sensors/dht_reader.py
import time
import board
import adafruit_dht

from utils.shared_state import state

# DHT11 on GPIO4 -> board.D4
dht = adafruit_dht.DHT11(board.D4)

def dht_loop():
    while True:
        try:
            temp = dht.temperature
            hum = dht.humidity
            if temp is not None and hum is not None:
                with state.lock:
                    state.temperature = float(temp)
                    state.humidity = float(hum)
                    state.last_update = time.time()
        except Exception:
            # Ignore transient read errors
            pass

        time.sleep(2)
