import threading
from dataclasses import dataclass, field

@dataclass
class SystemState:
    # sensors
    temperature: float | None = None
    humidity: float | None = None
    motion: bool = False
    sound: bool = False

    # actuators
    led_on: bool = False
    buzzer_on: bool = False
    window_open: bool = False
    laser_on: bool = False

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

state = SystemState()
