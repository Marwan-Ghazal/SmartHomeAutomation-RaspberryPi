# utils/shared_state.py
import threading

class SharedState:
    def __init__(self):
        # Lock for thread-safe access
        self.lock = threading.Lock()

        # ------------------ SENSOR READINGS ------------------
        self.temperature = None       # Current temperature in Celsius
        self.humidity = None          # Current humidity %
        self.motion = False           # True if PIR detects motion (room occupied)
        self.sound_detected = False   # True if sound sensor detects noise

        # ------------------ ACTUATORS ------------------
        self.led_on = False           # LED ON/OFF status
        self.laser_on = False         # Laser ON/OFF status
        self.buzzer_on = False        # Buzzer ON/OFF status
        self.window_open = False      # Window (stepper) open/closed

        # ------------------ AUTOMATION FLAGS ------------------
        self.request_led_toggle = False       # Set True when double-clap detected
        self.stop_buzzer_requested = False   # Set True to stop alarm buzzer
        self.alarm_active = False            # True if temperature alarm or other alert active

# ------------------ SINGLE GLOBAL STATE INSTANCE ------------------
state = SharedState()
