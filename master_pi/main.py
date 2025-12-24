# master_pi/main.py

import argparse
import threading
import time
from typing import Dict, Optional

import RPi.GPIO as GPIO

import config
from gpio_devices import Buzzer, Led
from sound_sensor import DoubleClapDetector
from system_state import state
from uart_link import SerialLink


def now_ms() -> int:
    return int(time.time() * 1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["normal", "ping"], default="normal")
    args = parser.parse_args()

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    led = Led(config.LED_PIN)
    buzzer = Buzzer(config.BUZZER_PIN)
    led.setup()
    buzzer.setup()

    ping_wait: Dict[str, float] = {}

    def on_uart_message(msg: Dict) -> None:
        t = msg.get("t")

        if t == "PING":
            link.send({"t": "PONG", "id": msg.get("id"), "ts": now_ms()})
            return

        if t == "PONG":
            pid = str(msg.get("id"))
            if pid in ping_wait:
                rtt_ms = now_ms() - int(ping_wait.pop(pid))
                print(f"[PING] pong id={pid} rtt={rtt_ms}ms")
            return

        if t == "STATE":
            with state.lock:
                state.temperature_c = msg.get("temperature_c")
                state.humidity_pct = msg.get("humidity_pct")
                state.motion = bool(msg.get("motion", False))
                state.window_open = bool(msg.get("window_open", False))
                state.laser_on = bool(msg.get("laser_on", False))
                state.peripheral_alarm = bool(msg.get("alarm", False))
            return

        if t == "EVENT":
            # Reserved for phase-1 event streaming; keep for extensibility.
            return

    link = SerialLink(
        port=config.SERIAL_PORT,
        baudrate=config.SERIAL_BAUDRATE,
        on_message=on_uart_message,
        reconnect_delay_sec=config.SERIAL_RECONNECT_DELAY_SEC,
    )
    link.start()

    def set_sound_flag(on: bool) -> None:
        with state.lock:
            state.sound_detected = on

    def on_double_clap() -> None:
        new_state = led.toggle()
        threading.Thread(target=buzzer.beep, args=(0.15,), daemon=True).start()
        with state.lock:
            state.led_on = new_state
        print(f"[SOUND] Double clap -> LED {'ON' if new_state else 'OFF'}")

    sound = DoubleClapDetector(
        pin=config.SOUND_PIN,
        on_sound=set_sound_flag,
        on_double_clap=on_double_clap,
    )
    sound.start()

    def alarm_worker() -> None:
        # Alarm pattern runs locally on Master (buzzer is on Master)
        start = time.time()
        while time.time() - start < config.ALARM_BEEP_SECONDS:
            with state.lock:
                if not state.alarm_active:
                    break
            buzzer.beep(0.25)
            time.sleep(0.25)

        with state.lock:
            state.alarm_active = False

        # Tell peripheral to clear LCD alert
        link.send({"t": "CMD", "name": "ALARM", "value": False})

    def ensure_alarm_started() -> None:
        with state.lock:
            if state.alarm_active:
                return
            state.alarm_active = True

        link.send({"t": "CMD", "name": "ALARM", "value": True})
        link.send({"t": "CMD", "name": "WINDOW", "value": "OPEN"})
        threading.Thread(target=alarm_worker, daemon=True).start()

    print("[MASTER] Running.")
    print(f"[MASTER] UART: {config.SERIAL_PORT} @ {config.SERIAL_BAUDRATE}")

    try:
        if args.mode == "ping":
            # Sends ping every second. Peripheral should be running (any mode).
            i = 0
            while True:
                pid = str(i)
                ping_wait[pid] = now_ms()
                link.send({"t": "PING", "id": pid, "ts": now_ms()})
                i += 1
                time.sleep(1.0)

        # normal mode
        while True:
            with state.lock:
                temp = state.temperature_c
                alarm_active = state.alarm_active

            if temp is not None and temp >= config.TEMP_HIGH_C and not alarm_active:
                print(f"[AUTO] High temp {temp:.1f}C >= {config.TEMP_HIGH_C:.1f}C -> alarm + open window")
                ensure_alarm_started()

            time.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        sound.stop()
        link.stop()
        GPIO.cleanup()
        print("[MASTER] Stopped.")


if __name__ == "__main__":
    main()
