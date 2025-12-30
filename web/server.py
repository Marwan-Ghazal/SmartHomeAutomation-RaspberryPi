 # web/server.py
import json
import os
import threading
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template, request

try:
    from master_pi import config as master_config
except Exception:
    master_config = None

app = Flask(__name__, template_folder="templates", static_folder="static")

_MQTT_HOST = os.getenv("SMARTHOME_MQTT_HOST", getattr(master_config, "MQTT_HOST", "localhost"))
_MQTT_PORT = int(os.getenv("SMARTHOME_MQTT_PORT", str(getattr(master_config, "MQTT_PORT", 1883))))
_MQTT_BASE_TOPIC = os.getenv(
    "SMARTHOME_MQTT_BASE_TOPIC", getattr(master_config, "MQTT_BASE_TOPIC", "smarthome")
).rstrip("/")

_state_lock = threading.Lock()
_latest_state: Dict[str, Any] = {}
_state_version = 0
_state_changed = threading.Condition(_state_lock)

_mqtt_started = False
_mqtt_lock = threading.Lock()
_mqtt_client: Optional[mqtt.Client] = None


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/state")
def api_state():
    _ensure_mqtt_started()
    with _state_lock:
        s = dict(_latest_state)

    data = {
        "temperature": s.get("temperature_c"),
        "humidity": s.get("humidity_pct"),
        "motion": bool(s.get("motion", False)),
        "flame_detected": bool(s.get("flame_detected", False)),
        "laser_beam_ok": bool(s.get("laser_beam_ok", False)),
        "crossing_detected": bool(s.get("crossing_detected", False)),
        "safety_laser_enabled": bool(s.get("safety_laser_enabled", False)),
        "sound_detected": bool(s.get("sound_detected", False)),
        "led_on": bool(s.get("led_on", False)),
        "buzzer_on": bool(s.get("buzzer_on", False)),
        "laser_on": bool(s.get("laser_on", False)),
        "window_open": bool(s.get("window_open", False)),
        "alarm_active": bool(s.get("alarm_active", False)),
        "clap_toggle_enabled": bool(s.get("clap_toggle_enabled", True)),
        "sound_led_mode_enabled": bool(s.get("sound_led_mode_enabled", False)),
        "motion_led_mode_enabled": bool(s.get("motion_led_mode_enabled", False)),
    }
    return jsonify(data)


@app.route("/api/stream")
def api_stream():
    _ensure_mqtt_started()

    def gen():
        last_ver = -1
        while True:
            with _state_changed:
                if _state_version == last_ver:
                    _state_changed.wait(timeout=15.0)
                if _state_version != last_ver:
                    payload = dict(_latest_state)
                    last_ver = _state_version
                else:
                    payload = None

            if payload is None:
                yield ":keepalive\n\n"
                continue

            data = {
                "temperature": payload.get("temperature_c"),
                "humidity": payload.get("humidity_pct"),
                "motion": bool(payload.get("motion", False)),
                "flame_detected": bool(payload.get("flame_detected", False)),
                "laser_beam_ok": bool(payload.get("laser_beam_ok", False)),
                "crossing_detected": bool(payload.get("crossing_detected", False)),
                "safety_laser_enabled": bool(payload.get("safety_laser_enabled", False)),
                "sound_detected": bool(payload.get("sound_detected", False)),
                "led_on": bool(payload.get("led_on", False)),
                "buzzer_on": bool(payload.get("buzzer_on", False)),
                "laser_on": bool(payload.get("laser_on", False)),
                "window_open": bool(payload.get("window_open", False)),
                "alarm_active": bool(payload.get("alarm_active", False)),
                "clap_toggle_enabled": bool(payload.get("clap_toggle_enabled", True)),
                "sound_led_mode_enabled": bool(payload.get("sound_led_mode_enabled", False)),
                "motion_led_mode_enabled": bool(payload.get("motion_led_mode_enabled", False)),
            }
            yield f"event: state\ndata: {json.dumps(data)}\n\n"

    return Response(gen(), mimetype="text/event-stream")


@app.route("/api/toggle_led", methods=["POST"])
def api_toggle_led():
    try:
        _ensure_mqtt_started()
        with _state_lock:
            new_state = not bool(_latest_state.get("led_on", False))
        _mqtt_publish_cmd("master/led", {"on": new_state})
        return jsonify({"led_on": new_state})
    except Exception as e:
        print("ERROR in /api/toggle_led:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mode/clap_toggle", methods=["POST"])
def api_mode_clap_toggle():
    try:
        _ensure_mqtt_started()
        body = request.get_json(silent=True) or {}
        on = body.get("on")
        if not isinstance(on, bool):
            return jsonify({"error": "missing boolean 'on'"}), 400
        _mqtt_publish_cmd("master/mode/clap_toggle", {"on": on})
        return jsonify({"clap_toggle_enabled": on})
    except Exception as e:
        print("ERROR in /api/mode/clap_toggle:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mode/sound_led", methods=["POST"])
def api_mode_sound_led():
    try:
        _ensure_mqtt_started()
        body = request.get_json(silent=True) or {}
        on = body.get("on")
        if not isinstance(on, bool):
            return jsonify({"error": "missing boolean 'on'"}), 400
        _mqtt_publish_cmd("master/mode/sound_led", {"on": on})
        return jsonify({"sound_led_mode_enabled": on})
    except Exception as e:
        print("ERROR in /api/mode/sound_led:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mode/motion_led", methods=["POST"])
def api_mode_motion_led():
    try:
        _ensure_mqtt_started()
        body = request.get_json(silent=True) or {}
        on = body.get("on")
        if not isinstance(on, bool):
            return jsonify({"error": "missing boolean 'on'"}), 400
        _mqtt_publish_cmd("master/mode/motion_led", {"on": on})
        return jsonify({"motion_led_mode_enabled": on})
    except Exception as e:
        print("ERROR in /api/mode/motion_led:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/toggle_laser", methods=["POST"])
def api_toggle_laser():
    try:
        _ensure_mqtt_started()
        with _state_lock:
            new_state = not bool(_latest_state.get("safety_laser_enabled", False))
        _mqtt_publish_cmd("peripheral/safety_laser", {"on": new_state})
        return jsonify({"safety_laser_enabled": new_state})
    except Exception as e:
        print("ERROR in /api/toggle_laser:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop_buzzer", methods=["POST"])
def api_stop_buzzer():
    try:
        _ensure_mqtt_started()
        _mqtt_publish_cmd("master/alarm", {"on": False})
        return jsonify({"buzzer_on": False})
    except Exception as e:
        print("ERROR in /api/stop_buzzer:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/open_window", methods=["POST"])
def api_open_window():
    try:
        _ensure_mqtt_started()
        _mqtt_publish_cmd("peripheral/window", {"action": "OPEN"})
        return jsonify({"status": "opening"})
    except Exception as e:
        print("ERROR in /api/open_window:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/close_window", methods=["POST"])
def api_close_window():
    try:
        _ensure_mqtt_started()
        _mqtt_publish_cmd("peripheral/window", {"action": "CLOSE"})
        return jsonify({"status": "closing"})
    except Exception as e:
        print("ERROR in /api/close_window:", e)
        return jsonify({"error": str(e)}), 500


def _mqtt_topic(suffix: str) -> str:
    suffix = suffix.lstrip("/")
    return f"{_MQTT_BASE_TOPIC}/{suffix}" if suffix else _MQTT_BASE_TOPIC


def _mqtt_publish_cmd(path: str, payload: object) -> None:
    if _mqtt_client is None:
        raise RuntimeError("MQTT client not started")
    _mqtt_client.publish(_mqtt_topic(f"cmd/{path}"), json.dumps(payload), qos=0, retain=False)


def _on_mqtt_connect(_client, _userdata, _flags, rc, _properties=None):
    if rc != 0:
        print(f"[WEB][MQTT] Connect failed rc={rc}")
        return
    _client.subscribe(_mqtt_topic("state"))


def _on_mqtt_message(_client, _userdata, msg):
    global _state_version
    if msg.topic != _mqtt_topic("state"):
        return

    try:
        payload = msg.payload.decode("utf-8", errors="ignore")
        data = json.loads(payload)
        if not isinstance(data, dict):
            return
    except Exception:
        return

    with _state_changed:
        _latest_state.clear()
        _latest_state.update(data)
        _state_version += 1
        _state_changed.notify_all()


def _ensure_mqtt_started() -> None:
    global _mqtt_started, _mqtt_client
    with _mqtt_lock:
        if _mqtt_started:
            return

        client = mqtt.Client(client_id=f"{_MQTT_BASE_TOPIC}-web")
        client.on_connect = _on_mqtt_connect
        client.on_message = _on_mqtt_message
        client.reconnect_delay_set(min_delay=1, max_delay=10)

        client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=30)
        client.loop_start()

        _mqtt_client = client
        _mqtt_started = True


if __name__ == "__main__":
    _ensure_mqtt_started()
    app.run(host="0.0.0.0", port=5000, debug=False)
