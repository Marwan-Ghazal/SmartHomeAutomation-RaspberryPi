# peripheral_pi/system_state.py

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PeripheralState:
    # Sensors
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    motion: bool = False
    flame_detected: bool = False
    laser_beam_ok: bool = False
    crossing_detected: bool = False
    door_closed: bool = False

    # Master (remote)
    master_led_on: bool = False

    # Actuators
    door_locked: bool = False
    laser_on: bool = False
    safety_laser_enabled: bool = False

    # For LCD / status
    alarm: bool = False

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


state = PeripheralState()
