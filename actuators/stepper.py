# actuators/stepper_control.py
import time
import RPi.GPIO as GPIO

from utils.shared_state import state

IN1 = 17
IN2 = 18
IN3 = 27
IN4 = 22

STEPPER_PINS = [IN1, IN2, IN3, IN4]

STEP_SEQUENCE = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
]

STEPS_PER_REV = 2048  # typical for 28BYJ-48

def setup_stepper():
    for pin in STEPPER_PINS:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    with state.lock:
        state.window_open = False

def _rotate_steps(steps: int, direction: int = 1, delay: float = 0.002):
    sequence = STEP_SEQUENCE if direction == 1 else list(reversed(STEP_SEQUENCE))
    for i in range(steps):
        pattern = sequence[i % len(sequence)]
        for pin, val in zip(STEPPER_PINS, pattern):
            GPIO.output(pin, GPIO.HIGH if val else GPIO.LOW)
        time.sleep(delay)
    # turn off coils
    for pin in STEPPER_PINS:
        GPIO.output(pin, GPIO.LOW)

def open_window():
    """Rotate 360 degrees to open window."""
    _rotate_steps(STEPS_PER_REV, direction=1)
    with state.lock:
        state.window_open = True

def close_window():
    """Rotate 360 degrees opposite direction to close window."""
    _rotate_steps(STEPS_PER_REV, direction=0)
    with state.lock:
        state.window_open = False
