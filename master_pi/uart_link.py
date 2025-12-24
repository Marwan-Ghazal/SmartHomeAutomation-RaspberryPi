# master_pi/uart_link.py

import json
import queue
import threading
import time
from typing import Callable, Dict, Optional

import serial
from serial import SerialException


class SerialLink:
    """Newline-delimited JSON link with auto-reconnect.

    Frame: one JSON object per line (UTF-8), terminated by '\n'.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        on_message: Callable[[Dict], None],
        reconnect_delay_sec: float = 2.0,
        logger: Callable[[str], None] = print,
    ):
        self._port = port
        self._baudrate = baudrate
        self._on_message = on_message
        self._reconnect_delay_sec = reconnect_delay_sec
        self._log = logger

        self._tx: "queue.Queue[Dict]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="UART", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def send(self, msg: Dict) -> None:
        # Best-effort; drop if extremely overloaded.
        try:
            self._tx.put_nowait(msg)
        except queue.Full:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            ser = None
            try:
                ser = serial.Serial(
                    self._port,
                    self._baudrate,
                    timeout=0.2,
                    write_timeout=0.5,
                )
                self._log(f"[UART] Connected: {self._port} @ {self._baudrate}")

                while not self._stop.is_set():
                    # Drain TX queue first
                    while True:
                        try:
                            msg = self._tx.get_nowait()
                        except queue.Empty:
                            break

                        try:
                            line = json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n"
                            ser.write(line.encode("utf-8"))
                        except Exception as e:
                            self._log(f"[UART] TX error: {e}")
                            break

                    # RX
                    raw = ser.readline()
                    if not raw:
                        continue

                    try:
                        text = raw.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        continue

                    if not text:
                        continue

                    try:
                        msg = json.loads(text)
                    except json.JSONDecodeError:
                        self._log(f"[UART] Malformed JSON: {text[:200]}")
                        continue

                    if not isinstance(msg, dict):
                        continue

                    try:
                        self._on_message(msg)
                    except Exception as e:
                        # Never let a callback crash the UART thread.
                        self._log(f"[UART] on_message error: {e}")

            except (OSError, SerialException) as e:
                self._log(f"[UART] Disconnected: {e}")
            finally:
                try:
                    if ser is not None:
                        ser.close()
                except Exception:
                    pass

            # Backoff
            time.sleep(self._reconnect_delay_sec)
