# sensors/pir_reader.py
import time
import RPi.GPIO as GPIO

from utils.shared_state import state

PIR_PIN = 5

def setup_pir():
    GPIO.setup(PIR_PIN, GPIO.IN)

def pir_loop():
    setup_pir()
    while True:
        motion = GPIO.input(PIR_PIN) == 1
        with state.lock:
            state.motion = motion
            state.last_update = time.time()
        time.sleep(0.1)
