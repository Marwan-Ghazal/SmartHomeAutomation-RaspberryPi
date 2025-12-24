# actuators/buzzer_control.py
import time
import threading
import RPi.GPIO as GPIO

from utils.shared_state import state

BUZZER_PIN = 23

def setup_buzzer():
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    with state.lock:
        state.buzzer_on = False

def set_buzzer(on: bool):
    GPIO.output(BUZZER_PIN, GPIO.HIGH if on else GPIO.LOW)
    with state.lock:
        state.buzzer_on = on

def beep(duration: float = 0.15):
    """Short feedback beep (for clap toggle etc.)."""
    set_buzzer(True)
    time.sleep(duration)
    set_buzzer(False)

def temp_alarm_worker():
    """
    Alarm buzzer for up to 30 seconds or until stop_buzzer_requested is True.
    Runs in its own thread.
    """
    with state.lock:
        state.stop_buzzer_requested = False
        state.alarm_active = True

    set_buzzer(True)
    start = time.time()

    try:
        while time.time() - start < 30:
            with state.lock:
                if state.stop_buzzer_requested:
                    break
            time.sleep(0.1)
    finally:
        set_buzzer(False)
        with state.lock:
            state.alarm_active = False
            state.stop_buzzer_requested = False

