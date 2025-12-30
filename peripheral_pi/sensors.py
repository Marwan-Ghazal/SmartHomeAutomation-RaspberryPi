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


class Mcp3008:
    def __init__(self, bus: int = 0, device: int = 0, *, cs_pin: Optional[int] = None, max_speed_hz: int = 1350000):
        import spidev

        self._cs_pin = cs_pin
        if self._cs_pin is not None:
            GPIO.setup(self._cs_pin, GPIO.OUT, initial=GPIO.HIGH)

        self._spi = spidev.SpiDev()
        self._spi.open(bus, device)
        self._spi.max_speed_hz = max_speed_hz
        if self._cs_pin is not None:
            self._spi.no_cs = True

    def read_channel(self, channel: int) -> int:
        if channel < 0 or channel > 7:
            raise ValueError("MCP3008 channel must be 0..7")

        if self._cs_pin is not None:
            GPIO.output(self._cs_pin, GPIO.LOW)
        try:
            adc = self._spi.xfer2([1, (8 + channel) << 4, 0])
            return ((adc[1] & 3) << 8) + adc[2]
        finally:
            if self._cs_pin is not None:
                GPIO.output(self._cs_pin, GPIO.HIGH)

    def close(self) -> None:
        try:
            self._spi.close()
        except Exception:
            pass


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
