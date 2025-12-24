



import time
import threading
import RPi.GPIO as GPIO

from utils.shared_state import state
SOUND_PIN = 6                  # The pin your sensor *actually* works on
MIN_CLAP_INTERVAL = 0.15        # Ignore tiny noise spikes
MAX_DOUBLE_CLAP_TIME = 0.8  
_last_clap_time = 0
_clap_count = 0


def _mark_sound_detected():
    """Updates the shared state for UI feedback."""
    with state.lock:
        state.sound_detected = True

    # Turn off the flag shortly after
    def reset():
        time.sleep(0.25)
        with state.lock:
            state.sound_detected = False

    threading.Thread(target=reset, daemon=True).start()

def _handle_rising_edge(channel):
    global _last_clap_time, _clap_count

    now = time.time()

    # Filter tiny noise
    if now - _last_clap_time < MIN_CLAP_INTERVAL:
        return


    _clap_count += 1
    _mark_sound_detected()
    print(f"[SOUND] Clap {_clap_count}")

    # Check for double-clap
    if _clap_count == 2 and (now - _last_clap_time <= MAX_DOUBLE_CLAP_TIME):
        print("[SOUND] DOUBLE CLAP detected ? request LED toggle")
        with state.lock:
            state.request_led_toggle = True
        _clap_count = 0
    elif _clap_count > 2:
        _clap_count = 1  # reset after weird spikes

    _last_clap_time = now

def sound_loop():
    """
    Configures interrupt and keeps cleanup-safe logic running.
    """
    print(f"[SOUND] Initializing sound sensor on GPIO{SOUND_PIN}")

    GPIO.setup(SOUND_PIN, GPIO.IN)
    GPIO.add_event_detect(SOUND_PIN, GPIO.RISING, bouncetime=40)
    GPIO.add_event_callback(SOUND_PIN, _handle_rising_edge)

    try:
        while True:
            # Reset clap sequence if user waits too long
            if time.time() - _last_clap_time > MAX_DOUBLE_CLAP_TIME:
                global _clap_count
                _clap_count = 0
            time.sleep(0.05)

    except KeyboardInterrupt:
        GPIO.remove_event_detect(SOUND_PIN)
        print("[SOUND] Stopped.")


