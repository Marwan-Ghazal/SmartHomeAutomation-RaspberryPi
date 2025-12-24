# peripheral_pi/main.py

import argparse
import threading
import time
from typing import Dict

import RPi.GPIO as GPIO

import config
from devices import Laser, StepperWindow
from lcd import I2cLcd
from sensors import dht_loop, make_dht_reader, pir_loop
from system_state import state
from uart_link import SerialLink


def now_ms() -> int:
    return int(time.time() * 1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["normal", "quiet"], default="normal")
    args = parser.parse_args()

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    laser = Laser(config.LASER_PIN)
    window = StepperWindow(config.STEPPER_PINS, config.STEPS_PER_REV, config.STEPPER_DELAY_SEC)
    laser.setup()
    window.setup()

    lcd = I2cLcd(config.I2C_ADDR, width=config.LCD_WIDTH)
    lcd.init()

    def on_uart_message(msg: Dict) -> None:
        t = msg.get("t")

        if t == "PING":
            link.send({"t": "PONG", "id": msg.get("id"), "ts": now_ms()})
            return

        if t != "CMD":
            return

        name = msg.get("name")
        val = msg.get("value")

        if name == "LASER":
            on = bool(val)
            laser.set(on)
            with state.lock:
                state.laser_on = on
            return

        if name == "WINDOW":
            if val == "OPEN":
                threading.Thread(target=_open_window, daemon=True).start()
            elif val == "CLOSE":
                threading.Thread(target=_close_window, daemon=True).start()
            return

        if name == "ALARM":
            with state.lock:
                state.alarm = bool(val)
            return

    link = SerialLink(
        port=config.SERIAL_PORT,
        baudrate=config.SERIAL_BAUDRATE,
        on_message=on_uart_message,
        reconnect_delay_sec=config.SERIAL_RECONNECT_DELAY_SEC,
    )
    link.start()

    def _open_window() -> None:
        window.open()
        with state.lock:
            state.window_open = True

    def _close_window() -> None:
        window.close()
        with state.lock:
            state.window_open = False

    def set_motion(motion: bool) -> None:
        changed = False
        with state.lock:
            if state.motion != motion:
                state.motion = motion
                changed = True
        if changed:
            link.send({"t": "EVENT", "name": "MOTION", "value": motion, "ts": now_ms()})

    def set_dht(t_c, h_pct) -> None:
        with state.lock:
            if t_c is not None:
                state.temperature_c = t_c
            if h_pct is not None:
                state.humidity_pct = h_pct

    dht_read_once = make_dht_reader(config.DHT_MODEL, config.DHT_BOARD_PIN)

    threading.Thread(target=pir_loop, args=(config.PIR_PIN, set_motion), daemon=True).start()
    threading.Thread(target=dht_loop, args=(config.DHT_SAMPLE_SEC, dht_read_once, set_dht), daemon=True).start()

    def lcd_loop() -> None:
        while True:
            with state.lock:
                t = state.temperature_c
                h = state.humidity_pct
                occ = "Occ" if state.motion else "Emp"
                win = "WON" if state.window_open else "WOF"
                las = "LAS" if state.laser_on else "---"
                alarm = "ALRT" if state.alarm else ""

            t_str = f"T:{t:.1f}C" if t is not None else "T:--.-C"
            h_str = f"H:{h:.0f}%" if h is not None else "H:--%"
            lcd.write_line(f"{t_str} {h_str}", I2cLcd.LCD_LINE_1)
            lcd.write_line(f"{occ} {win} {las} {alarm}", I2cLcd.LCD_LINE_2)
            time.sleep(config.LCD_UPDATE_SEC)

    def state_tx_loop() -> None:
        period = 1.0 / max(0.5, config.STATE_HZ)
        while True:
            with state.lock:
                msg = {
                    "t": "STATE",
                    "ts": now_ms(),
                    "temperature_c": state.temperature_c,
                    "humidity_pct": state.humidity_pct,
                    "motion": state.motion,
                    "window_open": state.window_open,
                    "laser_on": state.laser_on,
                    "alarm": state.alarm,
                }
            link.send(msg)
            time.sleep(period)

    threading.Thread(target=lcd_loop, daemon=True).start()
    threading.Thread(target=state_tx_loop, daemon=True).start()

    if args.mode != "quiet":
        print("[PERIPHERAL] Running.")
        print(f"[PERIPHERAL] UART: {config.SERIAL_PORT} @ {config.SERIAL_BAUDRATE}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        GPIO.cleanup()
        print("[PERIPHERAL] Stopped.")


if __name__ == "__main__":
    main()
