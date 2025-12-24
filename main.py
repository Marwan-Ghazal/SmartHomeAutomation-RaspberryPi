# main.py
import threading
import time
import RPi.GPIO as GPIO

from utils.shared_state import state

# Sensors
from sensors.dht_sensor import dht_loop
from sensors.pir_sensor import pir_loop
from sensors.sound_sensor import sound_loop
from sensors.laser_control import setup_laser

# Actuators
from actuators.led import setup_led, toggle_led
from actuators.buzzer import setup_buzzer, beep, temp_alarm_worker
from actuators.stepper import setup_stepper
from actuators.lcd import lcd_loop  # LCD thread
from actuators.stepper import open_window

# Web server
from web.server import app

# ---------------- Constants ----------------
TEMP_HIGH = 30.0
CLAP_INTERVAL = 2.0

# ---------------- Helpers ----------------
def start_thread(target, name):
    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()
    return t

# ---------------- Automation ----------------
def automation_loop():
    while True:
        with state.lock:
            temp = state.temperature
            alarm_active = state.alarm_active
            toggle_requested = state.request_led_toggle
            state.request_led_toggle = False  # consume event

        # Double clap -> toggle LED
        if toggle_requested:
            new_state = toggle_led()
            threading.Thread(target=beep, args=(0.15,), daemon=True).start()
            print(f"[AUTO] LED toggled ? {'ON' if new_state else 'OFF'}")

        # Temperature alarm -> buzzer + window
        if temp is not None and temp >= TEMP_HIGH and not alarm_active:
            with state.lock:
                state.alarm_active = True
                state.stop_buzzer_requested = False

            threading.Thread(target=temp_alarm_worker, daemon=True).start()
            threading.Thread(target=open_window, daemon=True).start()

        time.sleep(0.05)

# ---------------- Web Server ----------------
def run_web_server():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

# ---------------- Main ----------------
if __name__ == "__main__":
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Setup actuators
    setup_led()
    setup_buzzer()
    setup_stepper()
    setup_laser()

    # Start sensor threads
    start_thread(dht_loop, "DHT")
    start_thread(pir_loop, "PIR")
    start_thread(sound_loop, "SOUND")

    # Automation thread
    start_thread(automation_loop, "AUTOMATION")

    # LCD display thread
    start_thread(lcd_loop, "LCD")

    # Web server thread
    threading.Thread(target=run_web_server, name="WEB", daemon=True).start()

    print("System running. Open http://<PI-IP>:5000 in your browser.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Shutting down.")
