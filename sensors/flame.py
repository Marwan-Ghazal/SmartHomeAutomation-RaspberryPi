import RPi.GPIO as GPIO
import time

# GPIO pin connected to DO
FLAME_PIN = 24  # your pin

GPIO.setmode(GPIO.BCM)
GPIO.setup(FLAME_PIN, GPIO.IN)

try:
    while True:
        if GPIO.input(FLAME_PIN) == 0:
            print("?? Flame detected!")
        else:
            print("No flame.")
        time.sleep(0.5)

except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup()
