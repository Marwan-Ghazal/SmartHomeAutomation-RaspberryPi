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

    # Modes (controlled from website)
    clap_toggle_enabled: bool = True
    sound_led_mode_enabled: bool = False
    motion_led_mode_enabled: bool = False

    # Remote (Peripheral Pi)
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    motion: bool = False
    flame_detected: bool = False
    laser_beam_ok: bool = False
    crossing_detected: bool = False
    door_closed: bool = False
    door_locked: bool = False
    laser_on: bool = False
    safety_laser_enabled: bool = False
    peripheral_alarm: bool = False

    # Derived / control flags
    alarm_active: bool = False

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "led_on": self.led_on,
            "buzzer_on": self.buzzer_on,
            "sound_detected": self.sound_detected,
            "clap_toggle_enabled": self.clap_toggle_enabled,
            "sound_led_mode_enabled": self.sound_led_mode_enabled,
            "motion_led_mode_enabled": self.motion_led_mode_enabled,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "motion": self.motion,
            "flame_detected": self.flame_detected,
            "laser_beam_ok": self.laser_beam_ok,
            "crossing_detected": self.crossing_detected,
            "door_closed": self.door_closed,
            "door_locked": self.door_locked,
            "laser_on": self.laser_on,
            "safety_laser_enabled": self.safety_laser_enabled,
            "peripheral_alarm": self.peripheral_alarm,
            "alarm_active": self.alarm_active,
        }


state = SystemState()
