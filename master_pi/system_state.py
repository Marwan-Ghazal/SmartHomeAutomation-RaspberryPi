# master_pi/system_state.py

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemState:
    # Local (Master Pi)
    led_on: bool = False
    buzzer_on: bool = False
    sound_detected: bool = False

    # Remote (Peripheral Pi)
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    motion: bool = False
    window_open: bool = False
    laser_on: bool = False
    peripheral_alarm: bool = False

    # Derived / control flags
    alarm_active: bool = False

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "led_on": self.led_on,
            "buzzer_on": self.buzzer_on,
            "sound_detected": self.sound_detected,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "motion": self.motion,
            "window_open": self.window_open,
            "laser_on": self.laser_on,
            "peripheral_alarm": self.peripheral_alarm,
            "alarm_active": self.alarm_active,
        }


state = SystemState()
