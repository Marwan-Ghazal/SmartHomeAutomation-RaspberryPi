# actuators/led_control.py
import RPi.GPIO as GPIO
from utils.shared_state import state

LED_PIN = 21

def setup_led():
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
    with state.lock:
        state.led_on = False

def set_led(on: bool):
    GPIO.output(LED_PIN, GPIO.HIGH if on else GPIO.LOW)
    with state.lock:
        state.led_on = on

def toggle_led() -> bool:
    with state.lock:
        new_state = not state.led_on
    set_led(new_state)
    return new_state
