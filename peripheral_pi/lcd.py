# peripheral_pi/lcd.py

import time

from smbus2 import SMBus


class I2cLcd:
    LCD_CHR = 1
    LCD_CMD = 0
    LCD_LINE_1 = 0x80
    LCD_LINE_2 = 0xC0
    LCD_BACKLIGHT = 0x08
    ENABLE = 0b00000100

    def __init__(self, i2c_addr: int, width: int = 16, bus_id: int = 1):
        self._addr = i2c_addr
        self._width = width
        self._bus = SMBus(bus_id)

    def _toggle_enable(self, bits: int) -> None:
        time.sleep(0.0005)
        self._bus.write_byte(self._addr, bits | self.ENABLE)
        time.sleep(0.0005)
        self._bus.write_byte(self._addr, bits & ~self.ENABLE)
        time.sleep(0.0005)

    def _byte(self, bits: int, mode: int) -> None:
        bits_high = mode | (bits & 0xF0) | self.LCD_BACKLIGHT
        bits_low = mode | ((bits << 4) & 0xF0) | self.LCD_BACKLIGHT
        self._bus.write_byte(self._addr, bits_high)
        self._toggle_enable(bits_high)
        self._bus.write_byte(self._addr, bits_low)
        self._toggle_enable(bits_low)

    def init(self) -> None:
        self._byte(0x33, self.LCD_CMD)
        self._byte(0x32, self.LCD_CMD)
        self._byte(0x06, self.LCD_CMD)
        self._byte(0x0C, self.LCD_CMD)
        self._byte(0x28, self.LCD_CMD)
        self._byte(0x01, self.LCD_CMD)
        time.sleep(0.005)

    def write_line(self, message: str, line: int) -> None:
        msg = message.ljust(self._width, " ")[: self._width]
        self._byte(line, self.LCD_CMD)
        for i in range(self._width):
            self._byte(ord(msg[i]), self.LCD_CHR)
