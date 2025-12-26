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

        self._poll_stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._using_edge_detect = False

    def start(self) -> None:
        # Ensure a clean state. Some kernels/drivers keep edge detect state if a previous
        # process exited without cleanup.
        try:
            GPIO.cleanup(self._pin)
        except Exception:
            pass

        try:
            GPIO.remove_event_detect(self._pin)
        except Exception:
            pass

        self._poll_stop.clear()

        # First attempt: match the user's working standalone test (no pull-up/down).
        GPIO.setup(self._pin, GPIO.IN)
        try:
            GPIO.add_event_detect(self._pin, GPIO.RISING, bouncetime=50)
            GPIO.add_event_callback(self._pin, self._handle_rising_edge)
            self._using_edge_detect = True
            return
        except RuntimeError:
            pass

        # Second attempt: add a pull-down to stabilize floating inputs.
        try:
            try:
                GPIO.remove_event_detect(self._pin)
            except Exception:
                pass
            GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(self._pin, GPIO.RISING, bouncetime=50)
            GPIO.add_event_callback(self._pin, self._handle_rising_edge)
            self._using_edge_detect = True
            return
        except RuntimeError as e:
            # Final fallback: polling (never crash the master).
            self._using_edge_detect = False
            self._poll_thread = threading.Thread(target=self._poll_loop, name="SOUND_POLL", daemon=True)
            self._poll_thread.start()

    def stop(self) -> None:
        self._poll_stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=0.5)

        try:
            GPIO.remove_event_detect(self._pin)
        except Exception:
            pass

    def _poll_loop(self) -> None:
        last = GPIO.input(self._pin)
        while not self._poll_stop.is_set():
            cur = GPIO.input(self._pin)
            if cur == 1 and last == 0:
                self._handle_rising_edge(self._pin)
            last = cur
            time.sleep(0.01)

    def _handle_rising_edge(self, _channel: int) -> None:
        now = time.time()

        # Reset clap sequence if user waited too long between claps (matches test script).
        if self._last_clap_time and (now - self._last_clap_time) > self._max_double_clap_time:
            self._clap_count = 0

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
