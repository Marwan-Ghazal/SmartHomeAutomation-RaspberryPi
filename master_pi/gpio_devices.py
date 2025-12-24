# master_pi/gpio_devices.py

import time
import RPi.GPIO as GPIO


class Led:
    def __init__(self, pin: int):
        self._pin = pin

    def setup(self) -> None:
        GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.LOW)

    def set(self, on: bool) -> None:
        GPIO.output(self._pin, GPIO.HIGH if on else GPIO.LOW)

    def toggle(self) -> bool:
        new_state = not (GPIO.input(self._pin) == GPIO.HIGH)
        self.set(new_state)
        return new_state


class Buzzer:
    def __init__(self, pin: int):
        self._pin = pin

    def setup(self) -> None:
        GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.LOW)

    def set(self, on: bool) -> None:
        GPIO.output(self._pin, GPIO.HIGH if on else GPIO.LOW)

    def beep(self, seconds: float = 0.15) -> None:
        self.set(True)
        time.sleep(seconds)
        self.set(False)
