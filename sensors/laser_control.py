# sensors/laser_control.py  (acts as actuator)
import RPi.GPIO as GPIO

from utils.shared_state import state

LASER_PIN = 12

def setup_laser():
    GPIO.setup(LASER_PIN, GPIO.OUT, initial=GPIO.LOW)
    with state.lock:
        state.laser_on = False

def set_laser(on: bool):
    GPIO.output(LASER_PIN, GPIO.HIGH if on else GPIO.LOW)
    with state.lock:
        state.laser_on = on
