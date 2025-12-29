# peripheral_pi/sensors.py

import time
from typing import Callable, Optional, Tuple

import RPi.GPIO as GPIO


def pir_loop(pin: int, on_motion: Callable[[bool], None]) -> None:
    GPIO.setup(pin, GPIO.IN)
    while True:
        motion = GPIO.input(pin) == 1
        on_motion(motion)
        time.sleep(0.1)


def flame_loop(pin: int, on_flame: Callable[[bool], None], *, active_low: bool = True, poll_sec: float = 0.1) -> None:
    pud = GPIO.PUD_UP if active_low else GPIO.PUD_DOWN
    GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
    while True:
        val = GPIO.input(pin)
        flame = (val == 0) if active_low else (val == 1)
        on_flame(flame)
        time.sleep(poll_sec)


def make_dht_reader(model: str, board_pin: str):
    import board
    import adafruit_dht

    pin = getattr(board, board_pin)
    dht = adafruit_dht.DHT11(pin) if model.upper() == "DHT11" else adafruit_dht.DHT22(pin)

    def read_once() -> Tuple[Optional[float], Optional[float]]:
        try:
            t = dht.temperature
            h = dht.humidity
            if t is None or h is None:
                return None, None
            return float(t), float(h)
        except Exception:
            return None, None

    return read_once


def dht_loop(sample_sec: float, read_once: Callable[[], Tuple[Optional[float], Optional[float]]], on_read: Callable[[Optional[float], Optional[float]], None]) -> None:
    while True:
        t, h = read_once()
        on_read(t, h)
        time.sleep(sample_sec)
