import RPi.GPIO as GPIO
import time

SOUND_PIN = 6        # KY-038 D0 pin
LED_PIN = 21          # LED output pin (GPIO 21)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SOUND_PIN, GPIO.IN)
GPIO.setup(LED_PIN, GPIO.OUT)

clap_count = 0
last_clap_time = 0
led_state = False

MAX_DOUBLE_CLAP_TIME = 0.8   # Max time between clap 1 and 2
MIN_CLAP_INTERVAL = 0.15     # Prevents noise from counting as clap

def handle_clap(channel):
    global clap_count, last_clap_time, led_state

    now = time.time()

    # Ignore pulses too close together (noise or long vibrations)
    if now - last_clap_time < MIN_CLAP_INTERVAL:
        return

    clap_count += 1
    print(f"Clap {clap_count}")

    # Check if double clap happened
    if clap_count == 2 and (now - last_clap_time) <= MAX_DOUBLE_CLAP_TIME:
        led_state = not led_state
        GPIO.output(LED_PIN, led_state)
        print(f"LED {'ON' if led_state else 'OFF'}")
        clap_count = 0  # Reset after toggling

    last_clap_time = now


print("Double-clap system ready. Clap twice!")

GPIO.add_event_detect(SOUND_PIN, GPIO.RISING, bouncetime=50)
GPIO.add_event_callback(SOUND_PIN, handle_clap)

try:
    while True:
        # Reset if user waited too long between claps
        if time.time() - last_clap_time > MAX_DOUBLE_CLAP_TIME:
            clap_count = 0
        time.sleep(0.1)

except KeyboardInterrupt:
    GPIO.cleanup()
    print("Program stopped.")
    
