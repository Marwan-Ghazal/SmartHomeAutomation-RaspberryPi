# peripheral_pi/devices.py

import time
from typing import List

import RPi.GPIO as GPIO


class Laser:
    def __init__(self, pin: int, *, active_low: bool = False):
        self._pin = pin
        self._active_low = active_low

    def setup(self) -> None:
        initial = GPIO.HIGH if self._active_low else GPIO.LOW
        GPIO.setup(self._pin, GPIO.OUT, initial=initial)

    def set(self, on: bool) -> None:
        if self._active_low:
            GPIO.output(self._pin, GPIO.LOW if on else GPIO.HIGH)
        else:
            GPIO.output(self._pin, GPIO.HIGH if on else GPIO.LOW)


class StepperWindow:
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

    def __init__(self, pins: List[int], steps_per_rev: int, delay_sec: float):
        self._pins = pins
        self._steps_per_rev = steps_per_rev
        self._delay_sec = delay_sec

    def setup(self) -> None:
        for pin in self._pins:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    def _rotate(self, steps: int, direction: int) -> None:
        seq = self.STEP_SEQUENCE if direction == 1 else list(reversed(self.STEP_SEQUENCE))
        for i in range(steps):
            pattern = seq[i % len(seq)]
            for pin, val in zip(self._pins, pattern):
                GPIO.output(pin, GPIO.HIGH if val else GPIO.LOW)
            time.sleep(self._delay_sec)

        for pin in self._pins:
            GPIO.output(pin, GPIO.LOW)

    def open(self) -> None:
        self._rotate(self._steps_per_rev, direction=1)

    def close(self) -> None:
        self._rotate(self._steps_per_rev, direction=0)


class DoorLock:
    def __init__(self, pins: List[int], steps_per_rev: int, delay_sec: float):
        self._stepper = StepperWindow(pins, steps_per_rev, delay_sec)

    def setup(self) -> None:
        self._stepper.setup()

    def lock(self) -> None:
        self._stepper.close()

    def unlock(self) -> None:
        self._stepper.open()
