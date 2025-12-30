# peripheral_pi/main.py

import argparse
import threading
import time
from typing import Dict

import RPi.GPIO as GPIO

import config
from devices import DoorLock, Laser
from lcd import I2cLcd
from sensors import Mcp3008, dht_loop, flame_loop, hall_loop, make_dht_reader, pir_loop
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

    laser = Laser(config.LASER_PIN, active_low=config.LASER_ACTIVE_LOW)
    door_lock = DoorLock(config.STEPPER_PINS, config.STEPS_PER_REV, config.STEPPER_DELAY_SEC)
    laser.setup()
    door_lock.setup()

    lcd = I2cLcd(config.I2C_ADDR, width=config.LCD_WIDTH)
    lcd.init()

    def on_uart_message(msg: Dict) -> None:
        t = msg.get("t")

        if t == "PING":
            link.send({"t": "PONG", "id": msg.get("id"), "ts": now_ms()})
            return

        if t == "EVENT":
            if msg.get("name") == "MASTER_LED":
                with state.lock:
                    state.master_led_on = bool(msg.get("value", False))
            return

        if t != "CMD":
            return

        name = msg.get("name")
        val = msg.get("value")

        if name == "LASER":
            on = bool(val)
            print(f"[PERIPHERAL] CMD LASER on={on}")
            try:
                laser.set(on)
            except Exception as e:
                print(f"[PERIPHERAL] Laser.set failed (LASER cmd) on={on}: {e}")
            with state.lock:
                state.laser_on = on
            return

        if name == "SAFETY_LASER":
            enabled = bool(val)
            print(
                f"[PERIPHERAL] CMD SAFETY_LASER enabled={enabled} pin={config.LASER_PIN} active_low={getattr(config, 'LASER_ACTIVE_LOW', False)}"
            )
            try:
                laser.set(bool(enabled))
            except Exception as e:
                print(f"[PERIPHERAL] Laser.set failed (SAFETY_LASER cmd) enabled={enabled}: {e}")
            with state.lock:
                state.safety_laser_enabled = enabled
                state.laser_on = enabled
            return

        if name == "DOOR_LOCK":
            if val == "LOCK":
                threading.Thread(target=_lock_door, daemon=True).start()
            elif val == "UNLOCK":
                threading.Thread(target=_unlock_door, daemon=True).start()
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

    def _lock_door() -> None:
        with state.lock:
            closed = bool(state.door_closed)
        if not closed:
            print("[DOOR] Refusing to lock: door is open")
            return
        if getattr(config, "DOOR_LOCK_INVERT", False):
            door_lock.unlock()
        else:
            door_lock.lock()
        with state.lock:
            state.door_locked = True

    def _unlock_door() -> None:
        if getattr(config, "DOOR_LOCK_INVERT", False):
            door_lock.lock()
        else:
            door_lock.unlock()
        with state.lock:
            state.door_locked = False

    def set_motion(motion: bool) -> None:
        changed = False
        with state.lock:
            if state.motion != motion:
                state.motion = motion
                changed = True
        if changed:
            link.send({"t": "EVENT", "name": "MOTION", "value": motion, "ts": now_ms()})

    def set_flame(flame: bool) -> None:
        with state.lock:
            state.flame_detected = bool(flame)

    def set_door_closed(closed: bool) -> None:
        with state.lock:
            state.door_closed = bool(closed)
            if not state.door_closed:
                state.door_locked = False

    def set_dht(t_c, h_pct) -> None:
        with state.lock:
            if t_c is not None:
                state.temperature_c = t_c
            if h_pct is not None:
                state.humidity_pct = h_pct

    dht_read_once = make_dht_reader(config.DHT_MODEL, config.DHT_BOARD_PIN)

    adc = Mcp3008(config.SPI_BUS, config.SPI_DEVICE, cs_pin=config.LDR_CS_PIN)

    threading.Thread(target=pir_loop, args=(config.PIR_PIN, set_motion), daemon=True).start()
    threading.Thread(
        target=hall_loop,
        args=(config.HALL_PIN, set_door_closed),
        kwargs={"active_low": config.HALL_ACTIVE_LOW, "poll_sec": config.HALL_POLL_SEC},
        daemon=True,
    ).start()
    threading.Thread(target=dht_loop, args=(config.DHT_SAMPLE_SEC, dht_read_once, set_dht), daemon=True).start()
    threading.Thread(
        target=flame_loop,
        args=(config.FLAME_PIN, set_flame),
        kwargs={"active_low": config.FLAME_ACTIVE_LOW, "poll_sec": config.FLAME_POLL_SEC},
        daemon=True,
    ).start()

    def safety_laser_loop() -> None:
        baseline = None
        last_beam_ok = False
        last_crossing = False

        while True:
            try:
                with state.lock:
                    enabled = bool(state.safety_laser_enabled)

                if not enabled:
                    if baseline is not None:
                        baseline = None
                    if last_beam_ok:
                        last_beam_ok = False
                    if last_crossing:
                        last_crossing = False

                    with state.lock:
                        state.laser_beam_ok = False
                        state.crossing_detected = False

                    time.sleep(0.1)
                    continue

                # Keep forcing the emitter on while enabled.
                with state.lock:
                    if not state.laser_on:
                        laser.set(True)
                        state.laser_on = True

                if baseline is None:
                    # Calibration phase: don't report crossing yet.
                    with state.lock:
                        state.laser_beam_ok = False
                        state.crossing_detected = False

                    samples = []
                    for _ in range(max(1, int(config.LDR_CALIB_SAMPLES))):
                        samples.append(adc.read_channel(config.LDR_CHANNEL))
                        time.sleep(max(0.001, float(config.LDR_POLL_SEC)))
                    baseline = sum(samples) / max(1, len(samples))
                    last_beam_ok = False

                reading = adc.read_channel(config.LDR_CHANNEL)
                # Hysteresis avoids flicker and prevents 'beam ok forever' due to
                # a low threshold ratio.
                ratio = float(config.LDR_THRESHOLD_RATIO)
                hysteresis = 0.05

                if config.LDR_BEAM_HIGH:
                    thr_on = float(baseline) * ratio
                    thr_off = float(baseline) * max(0.0, ratio - hysteresis)
                    if last_beam_ok:
                        beam_ok = reading >= thr_off
                    else:
                        beam_ok = reading >= thr_on
                else:
                    thr_on = float(baseline) * ratio
                    thr_off = float(baseline) * (ratio + hysteresis)
                    if last_beam_ok:
                        beam_ok = reading <= thr_off
                    else:
                        beam_ok = reading <= thr_on

                crossing = enabled and (not beam_ok)
                if crossing != last_crossing:
                    if crossing:
                        print("[SECURITY] Someone is crossing (laser beam interrupted)")
                    else:
                        print("[SECURITY] Beam restored")
                    last_crossing = crossing
                last_beam_ok = bool(beam_ok)

                with state.lock:
                    state.laser_beam_ok = bool(beam_ok)
                    state.crossing_detected = bool(crossing)

                time.sleep(max(0.01, float(config.LDR_POLL_SEC)))
            except Exception as e:
                print(f"[SECURITY] Safety laser loop error: {e}")
                time.sleep(0.2)

    def lcd_loop() -> None:
        while True:
            with state.lock:
                t = state.temperature_c
                h = state.humidity_pct
                occ = "Occ" if state.motion else "Emp"
                led = "LON" if state.master_led_on else "LOF"
                dor = "DCL" if state.door_closed else "DOP"
                las = "LAS" if state.laser_on else "---"
                alarm = "ALRT" if state.alarm else ""

            t_str = f"T:{t:.1f}C" if t is not None else "T:--.-C"
            h_str = f"H:{h:.0f}%" if h is not None else "H:--%"
            lcd.write_line(f"{t_str} {h_str}", I2cLcd.LCD_LINE_1)
            lcd.write_line(f"{occ} {led} {dor} {las} {alarm}", I2cLcd.LCD_LINE_2)
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
                    "flame_detected": state.flame_detected,
                    "laser_beam_ok": state.laser_beam_ok,
                    "crossing_detected": state.crossing_detected,
                    "door_closed": state.door_closed,
                    "door_locked": state.door_locked,
                    "laser_on": state.laser_on,
                    "safety_laser_enabled": state.safety_laser_enabled,
                    "alarm": state.alarm,
                }
            link.send(msg)
            time.sleep(period)

    threading.Thread(target=lcd_loop, daemon=True).start()
    threading.Thread(target=state_tx_loop, daemon=True).start()
    threading.Thread(target=safety_laser_loop, daemon=True).start()

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
