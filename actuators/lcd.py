# actuators/lcd.py
import smbus
import time
from utils.shared_state import state

I2C_ADDR = 0x27   # Change if your LCD address is different
LCD_WIDTH = 16

LCD_CHR = 1
LCD_CMD = 0
LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_BACKLIGHT = 0x08
ENABLE = 0b00000100

bus = smbus.SMBus(1)

# ------------------ LCD LOW LEVEL ------------------
def lcd_toggle_enable(bits):
    time.sleep(0.0005)
    bus.write_byte(I2C_ADDR, bits | ENABLE)
    time.sleep(0.0005)
    bus.write_byte(I2C_ADDR, bits & ~ENABLE)
    time.sleep(0.0005)

def lcd_byte(bits, mode):
    bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
    bits_low = mode | ((bits << 4) & 0xF0) | LCD_BACKLIGHT
    bus.write_byte(I2C_ADDR, bits_high)
    lcd_toggle_enable(bits_high)
    bus.write_byte(I2C_ADDR, bits_low)
    lcd_toggle_enable(bits_low)

def lcd_init():
    lcd_byte(0x33, LCD_CMD)
    lcd_byte(0x32, LCD_CMD)
    lcd_byte(0x06, LCD_CMD)
    lcd_byte(0x0C, LCD_CMD)
    lcd_byte(0x28, LCD_CMD)
    lcd_byte(0x01, LCD_CMD)
    time.sleep(0.005)

def lcd_string(message, line):
    message = message.ljust(LCD_WIDTH, " ")[:LCD_WIDTH]  # Ensure max 16 chars
    lcd_byte(line, LCD_CMD)
    for i in range(LCD_WIDTH):
        lcd_byte(ord(message[i]), LCD_CHR)

# ------------------ LCD LOOP ------------------
def lcd_loop():
    lcd_init()
    while True:
        with state.lock:
            temp = state.temperature or 0.0
            hum = state.humidity or 0.0
            occupied = "Occ" if state.motion else "Emp"   # Abbreviate
            led_status = "LON" if state.led_on else "LOF"
            window_status = "WON" if state.window_open else "WOF"
            alert = "ALERT!" if state.alarm_active else ""

        # Line 1: Temperature & Humidity
        lcd_string(f"T:{temp:.1f}C H:{hum:.1f}%", LCD_LINE_1)

        # Line 2: Room + Device + Alerts (stable)
        line2 = f"{occupied} {led_status} {window_status} {alert}"
        lcd_string(line2, LCD_LINE_2)

        time.sleep(1)  # Update every second
