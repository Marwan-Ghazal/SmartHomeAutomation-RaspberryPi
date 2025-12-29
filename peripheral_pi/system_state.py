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

    # Master (remote)
    master_led_on: bool = False

    # Actuators
    window_open: bool = False
    laser_on: bool = False

    # For LCD / status
    alarm: bool = False

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


state = PeripheralState()
