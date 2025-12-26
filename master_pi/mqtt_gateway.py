import json
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt


def _topic(base: str, suffix: str) -> str:
    base = base.rstrip("/")
    suffix = suffix.lstrip("/")
    return f"{base}/{suffix}" if suffix else base


def _parse_bool(payload: str) -> Optional[bool]:
    p = payload.strip().lower()
    if p in {"1", "true", "on", "yes"}:
        return True
    if p in {"0", "false", "off", "no"}:
        return False
    return None


class MqttGateway:
    def __init__(
        self,
        host: str,
        port: int,
        keepalive_sec: int,
        base_topic: str,
        on_command: Callable[[str, object], None],
        logger: Callable[[str], None] = print,
    ):
        self._host = host
        self._port = port
        self._keepalive = keepalive_sec
        self._base = base_topic.rstrip("/")
        self._on_command = on_command
        self._log = logger

        self._client = mqtt.Client(client_id=f"{self._base}-master")
        self._client.enable_logger()

        self._client.will_set(_topic(self._base, "master/status"), payload="offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)

        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True

        try:
            self._client.connect(self._host, self._port, self._keepalive)
            self._client.loop_start()
        except Exception as e:
            self._log(f"[MQTT] Disabled (cannot connect to broker {self._host}:{self._port}): {e}")

    def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    def publish_state(self, state_obj: dict) -> None:
        try:
            self._client.publish(_topic(self._base, "state"), json.dumps(state_obj), qos=0, retain=True)
        except Exception:
            pass

    def publish_event(self, name: str, value: object) -> None:
        msg = {"ts": int(time.time() * 1000), "name": name, "value": value}
        try:
            self._client.publish(_topic(self._base, "events"), json.dumps(msg), qos=0, retain=False)
        except Exception:
            pass

    def _on_connect(self, _client, _userdata, _flags, rc, _properties=None):
        if rc == 0:
            self._log("[MQTT] Connected")
            self._client.publish(_topic(self._base, "master/status"), payload="online", retain=True)
            self._client.subscribe(_topic(self._base, "cmd/#"))
        else:
            self._log(f"[MQTT] Connect failed rc={rc}")

    def _on_disconnect(self, _client, _userdata, rc, _properties=None):
        if rc != 0:
            self._log(f"[MQTT] Disconnected rc={rc} (will retry)")

    def _on_message(self, _client, _userdata, msg):
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
        except Exception:
            return

        base_cmd = _topic(self._base, "cmd/")
        if not topic.startswith(base_cmd):
            return

        cmd_path = topic[len(base_cmd) :].strip("/")
        if not cmd_path:
            return

        # Accept either JSON objects or simple string payloads.
        parsed: object = payload
        try:
            parsed = json.loads(payload)
        except Exception:
            b = _parse_bool(payload)
            if b is not None:
                parsed = {"on": b}

        try:
            self._on_command(cmd_path, parsed)
        except Exception as e:
            self._log(f"[MQTT] Command handler error: {e}")
