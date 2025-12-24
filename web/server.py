# web/server.py
from flask import Flask, render_template, jsonify, request

from utils.shared_state import state
from actuators import led, buzzer, stepper
from sensors import laser_control

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/state")
def api_state():
    with state.lock:
        data = {
            "temperature": state.temperature,
            "humidity": state.humidity,
            "motion": state.motion,
            "sound_detected": state.sound_detected,
            "led_on": state.led_on,
            "buzzer_on": state.buzzer_on,
            "laser_on": state.laser_on,
            "window_open": state.window_open,
            "alarm_active": state.alarm_active,
        }
    return jsonify(data)


@app.route("/api/toggle_led", methods=["POST"])
def api_toggle_led():
    try:
        new_state = led.toggle_led()
        return jsonify({"led_on": new_state})
    except Exception as e:
        print("ERROR in /api/toggle_led:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/toggle_laser", methods=["POST"])
def api_toggle_laser():
    try:
        with state.lock:
            new_state = not state.laser_on
        laser_control.set_laser(new_state)
        return jsonify({"laser_on": new_state})
    except Exception as e:
        print("ERROR in /api/toggle_laser:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop_buzzer", methods=["POST"])
def api_stop_buzzer():
    try:
        with state.lock:
            state.stop_buzzer_requested = True
        buzzer.set_buzzer(False)
        return jsonify({"buzzer_on": False})
    except Exception as e:
        print("ERROR in /api/stop_buzzer:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/open_window", methods=["POST"])
def api_open_window():
    try:
        from threading import Thread
        Thread(target=stepper.open_window, daemon=True).start()
        return jsonify({"status": "opening"})
    except Exception as e:
        print("ERROR in /api/open_window:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/close_window", methods=["POST"])
def api_close_window():
    try:
        from threading import Thread
        Thread(target=stepper.close_window, daemon=True).start()
        return jsonify({"status": "closing"})
    except Exception as e:
        print("ERROR in /api/close_window:", e)
        return jsonify({"error": str(e)}), 500
