import RPi.GPIO as GPIO
from utils.state import state
from config import LASER_PIN

def setup_laser():
    GPIO.setup(LASER_PIN, GPIO.OUT, initial=GPIO.LOW)

def set_laser(on: bool):
    GPIO.output(LASER_PIN, GPIO.HIGH if on else GPIO.LOW)
    with state.lock:
        state.laser_on = on
