# master_pi/sound_sensor.py

import threading
import time
from typing import Callable

import RPi.GPIO as GPIO


class DoubleClapDetector:
    def __init__(
        self,
        pin: int,
        on_sound: Callable[[bool], None],
        on_double_clap: Callable[[], None],
        min_clap_interval: float = 0.15,
        max_double_clap_time: float = 0.8,
    ):
        self._pin = pin
        self._on_sound = on_sound
        self._on_double_clap = on_double_clap

        self._min_clap_interval = min_clap_interval
        self._max_double_clap_time = max_double_clap_time

        self._last_clap_time = 0.0
        self._clap_count = 0

    def start(self) -> None:
        GPIO.setup(self._pin, GPIO.IN)
        GPIO.add_event_detect(self._pin, GPIO.RISING, bouncetime=40)
        GPIO.add_event_callback(self._pin, self._handle_rising_edge)

    def stop(self) -> None:
        try:
            GPIO.remove_event_detect(self._pin)
        except Exception:
            pass

    def _handle_rising_edge(self, _channel: int) -> None:
        now = time.time()

        # Filter tiny noise
        if now - self._last_clap_time < self._min_clap_interval:
            return

        self._clap_count += 1

        # UI feedback flag
        self._on_sound(True)

        def reset_flag():
            time.sleep(0.25)
            self._on_sound(False)

        threading.Thread(target=reset_flag, daemon=True).start()

        # Double clap
        if self._clap_count == 2 and (now - self._last_clap_time <= self._max_double_clap_time):
            self._clap_count = 0
            self._on_double_clap()
        elif self._clap_count > 2:
            self._clap_count = 1

        self._last_clap_time = now
