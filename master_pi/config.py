# master_pi/config.py

# UART
SERIAL_PORT = "/dev/serial0"  # or /dev/ttyAMA0 depending on your Pi model/config
SERIAL_BAUDRATE = 115200
SERIAL_RECONNECT_DELAY_SEC = 2.0

# GPIO (BCM numbering)
LED_PIN = 21
BUZZER_PIN = 23
SOUND_PIN = 6

# Automation
TEMP_HIGH_C = 30.0
ALARM_BEEP_SECONDS = 30.0

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE_SEC = 30
MQTT_BASE_TOPIC = "smarthome"
