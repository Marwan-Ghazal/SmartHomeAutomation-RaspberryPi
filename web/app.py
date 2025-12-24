from flask import Flask, render_template, jsonify
from utils.state import state

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state")
def api_state():
    with state.lock:
        return jsonify(
            temperature=state.temperature,
            humidity=state.humidity,
            motion=state.motion,
            sound=state.sound,
            led_on=state.led_on,
            buzzer_on=state.buzzer_on,
            window_open=state.window_open,
            laser_on=state.laser_on,
        )
