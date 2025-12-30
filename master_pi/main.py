# master_pi/main.py

import argparse
import threading
import time
from typing import Dict, Optional

import RPi.GPIO as GPIO

import config
from gpio_devices import Buzzer, Led
from mqtt_gateway import MqttGateway
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
                state.flame_detected = bool(msg.get("flame_detected", False))
                state.laser_beam_ok = bool(msg.get("laser_beam_ok", False))
                state.crossing_detected = bool(msg.get("crossing_detected", False))
                state.window_open = bool(msg.get("window_open", False))
                state.laser_on = bool(msg.get("laser_on", False))
                state.safety_laser_enabled = bool(msg.get("safety_laser_enabled", False))
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

    def send_master_led_state(is_on: bool) -> None:
        link.send({"t": "EVENT", "name": "MASTER_LED", "value": bool(is_on), "ts": now_ms()})

    timed_led_lock = threading.Lock()
    timed_led_token = 0

    def cancel_timed_led() -> None:
        nonlocal timed_led_token
        with timed_led_lock:
            timed_led_token += 1

    def start_timed_led(duration_s: float) -> None:
        nonlocal timed_led_token
        with timed_led_lock:
            timed_led_token += 1
            token = timed_led_token

        def worker() -> None:
            led.set(True)
            with state.lock:
                state.led_on = True
            send_master_led_state(True)
            mqtt.publish_event("timed_led_on", {"seconds": duration_s})

            end_at = time.time() + duration_s
            while time.time() < end_at:
                with timed_led_lock:
                    if token != timed_led_token:
                        return
                time.sleep(0.05)

            with timed_led_lock:
                if token != timed_led_token:
                    return

            led.set(False)
            with state.lock:
                state.led_on = False
            send_master_led_state(False)

        threading.Thread(target=worker, daemon=True).start()

    def set_modes(*, clap: Optional[bool] = None, sound: Optional[bool] = None, motion: Optional[bool] = None) -> None:
        # Clap toggle and Sound LED mode are mutually exclusive.
        with state.lock:
            if clap is not None:
                state.clap_toggle_enabled = bool(clap)
                if state.clap_toggle_enabled:
                    state.sound_led_mode_enabled = False

            if sound is not None:
                state.sound_led_mode_enabled = bool(sound)
                if state.sound_led_mode_enabled:
                    state.clap_toggle_enabled = False

            if motion is not None:
                state.motion_led_mode_enabled = bool(motion)

    def on_mqtt_command(path: str, payload: object) -> None:
        obj = payload if isinstance(payload, dict) else {}

        if path == "master/led":
            on = obj.get("on")
            if isinstance(on, bool):
                cancel_timed_led()
                led.set(on)
                with state.lock:
                    state.led_on = on
                send_master_led_state(on)
            return

        if path == "master/mode/clap_toggle":
            on = obj.get("on")
            if isinstance(on, bool):
                set_modes(clap=on)
            return

        if path == "master/mode/sound_led":
            on = obj.get("on")
            if isinstance(on, bool):
                set_modes(sound=on)
            return

        if path == "master/mode/motion_led":
            on = obj.get("on")
            if isinstance(on, bool):
                set_modes(motion=on)
            return

        if path == "master/alarm":
            on = obj.get("on")
            if isinstance(on, bool):
                if on:
                    ensure_alarm_started()
                else:
                    with state.lock:
                        state.alarm_active = False
                        state.buzzer_on = False
                    link.send({"t": "CMD", "name": "ALARM", "value": False})
            return

        if path == "peripheral/window":
            action = obj.get("action")
            if action in {"OPEN", "CLOSE"}:
                link.send({"t": "CMD", "name": "WINDOW", "value": action})
            return

        if path == "peripheral/laser":
            on = obj.get("on")
            if isinstance(on, bool):
                link.send({"t": "CMD", "name": "LASER", "value": on})
            return

        if path == "peripheral/safety_laser":
            on = obj.get("on")
            if isinstance(on, bool):
                with state.lock:
                    state.safety_laser_enabled = on
                link.send({"t": "CMD", "name": "SAFETY_LASER", "value": on})
            return

        if path == "peripheral/alarm":
            on = obj.get("on")
            if isinstance(on, bool):
                link.send({"t": "CMD", "name": "ALARM", "value": on})
            return

    mqtt = MqttGateway(
        host=config.MQTT_HOST,
        port=config.MQTT_PORT,
        keepalive_sec=config.MQTT_KEEPALIVE_SEC,
        base_topic=config.MQTT_BASE_TOPIC,
        on_command=on_mqtt_command,
    )
    mqtt.start()

    def mqtt_state_loop() -> None:
        while True:
            with state.lock:
                snapshot = state.to_dict()
            mqtt.publish_state(snapshot)
            time.sleep(0.5)

    threading.Thread(target=mqtt_state_loop, name="MQTT_STATE", daemon=True).start()

    def set_sound_flag(on: bool) -> None:
        with state.lock:
            state.sound_detected = on

        if on:
            with state.lock:
                sound_mode = state.sound_led_mode_enabled
            if sound_mode:
                start_timed_led(5.0)

    def on_double_clap() -> None:
        with state.lock:
            enabled = state.clap_toggle_enabled
        if not enabled:
            return
        new_state = led.toggle()
        threading.Thread(target=buzzer.beep, args=(0.15,), daemon=True).start()
        with state.lock:
            state.led_on = new_state
        print(f"[SOUND] Double clap -> LED {'ON' if new_state else 'OFF'}")
        send_master_led_state(new_state)
        mqtt.publish_event("double_clap_led", {"on": new_state})

    sound: Optional[DoubleClapDetector] = None
    if args.mode == "normal":
        with state.lock:
            state.led_on = False
        send_master_led_state(False)

        sound = DoubleClapDetector(
            pin=config.SOUND_PIN,
            on_sound=set_sound_flag,
            on_double_clap=on_double_clap,
        )
        sound.start()

    last_motion = False

    def motion_led_loop() -> None:
        nonlocal last_motion
        while True:
            with state.lock:
                enabled = state.motion_led_mode_enabled
                motion = bool(state.motion)

            if enabled and motion and not last_motion:
                start_timed_led(10.0)

            last_motion = motion
            time.sleep(0.05)

    threading.Thread(target=motion_led_loop, name="MOTION_LED", daemon=True).start()

    def alarm_worker() -> None:
        # Alarm pattern runs locally on Master (buzzer is on Master)
        with state.lock:
            state.buzzer_on = True
        start = time.time()
        while time.time() - start < config.ALARM_BEEP_SECONDS:
            with state.lock:
                if not state.alarm_active:
                    break
            buzzer.beep(0.25)
            time.sleep(0.25)

        with state.lock:
            state.alarm_active = False
            state.buzzer_on = False

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

    last_flame = False

    def flame_alarm_loop() -> None:
        nonlocal last_flame
        while True:
            with state.lock:
                flame = bool(state.flame_detected)

            if flame and not last_flame:
                print("[AUTO] Flame detected -> alarm")
                ensure_alarm_started()
                mqtt.publish_event("flame_detected", {"on": True})

            last_flame = flame
            time.sleep(0.05)

    threading.Thread(target=flame_alarm_loop, name="FLAME_ALARM", daemon=True).start()

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
        if sound is not None:
            sound.stop()
        mqtt.stop()
        link.stop()
        GPIO.cleanup()
        print("[MASTER] Stopped.")


if __name__ == "__main__":
    main()
