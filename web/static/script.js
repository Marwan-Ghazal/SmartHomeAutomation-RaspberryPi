// web/static/script.js

async function apiPost(url, body = null) {
  const opts = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  };
  if (body !== null) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = {};
  }
  if (!res.ok) {
    return { ...data, _http_status: res.status };
  }
  return data;
}

let lastFlameDetected = false;
let lastFireModalAtMs = 0;

function openFireModal() {
  const modal = document.getElementById("fire-modal");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function closeFireModal() {
  const modal = document.getElementById("fire-modal");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
}

function maybeShowFireModal() {
  const now = Date.now();
  const cooldownOk = now - lastFireModalAtMs > 5000;
  if (!lastFlameDetected && cooldownOk) {
    openFireModal();
    lastFireModalAtMs = now;
  }
  lastFlameDetected = true;
}

function updatePill(element, isOn, onText, offText, alert = false) {
  element.classList.remove("pill-on", "pill-off", "pill-alert");
  if (alert) {
    element.classList.add("pill-alert");
    element.textContent = onText;
  } else if (isOn) {
    element.classList.add("pill-on");
    element.textContent = onText;
  } else {
    element.classList.add("pill-off");
    element.textContent = offText;
  }
}

function renderState(data) {
  data = applyPendingModes(data);

  // Temperature
  const tempText = document.getElementById("temp-text");
  const tempBar = document.getElementById("temp-bar");
  if (data.temperature !== null) {
    tempText.textContent = data.temperature.toFixed(1) + " deg C";
    const t = Math.max(0, Math.min(40, data.temperature));
    tempBar.style.width = String((t / 40) * 100) + "%";
  } else {
    tempText.textContent = "-- deg C";
    tempBar.style.width = "0%";
  }

  // Humidity
  const humText = document.getElementById("hum-text");
  const humBar = document.getElementById("hum-bar");
  if (data.humidity !== null) {
    humText.textContent = data.humidity.toFixed(1) + " %";
    const h = Math.max(0, Math.min(100, data.humidity));
    humBar.style.width = String(h) + "%";
  } else {
    humText.textContent = "-- %";
    humBar.style.width = "0%";
  }

  // Motion / sound / alarm
  const motionPill = document.getElementById("motion-pill");
  const soundPill = document.getElementById("sound-pill");
  const flamePill = document.getElementById("flame-pill");
  const beamPill = document.getElementById("beam-pill");
  const doorPill = document.getElementById("door-pill");
  const alarmPill = document.getElementById("alarm-pill");

  updatePill(motionPill, data.motion, "Motion detected", "No motion");
  updatePill(soundPill, data.sound_detected, "Sound detected", "Quiet");
  if (flamePill) updatePill(flamePill, data.flame_detected, "FIRE!", "Safe", data.flame_detected);

  if (beamPill) {
    if (!data.safety_laser_enabled) {
      updatePill(beamPill, false, "Disabled", "Disabled");
    } else if (data.crossing_detected || !data.laser_beam_ok) {
      updatePill(beamPill, true, "Crossing", "Beam OK", true);
    } else {
      updatePill(beamPill, true, "Beam OK", "Beam OK");
    }
  }

  if (doorPill) {
    if (data.door_closed) {
      updatePill(doorPill, true, data.door_locked ? "Closed + Locked" : "Closed", "Open");
    } else {
      updatePill(doorPill, false, "Open", "Open", true);
    }
  }

  updatePill(alarmPill, data.alarm_active, "Alarm active", "Inactive", data.alarm_active);

  if (data.flame_detected) {
    maybeShowFireModal();
  } else {
    lastFlameDetected = false;
  }

  // Buttons
  const btnLed = document.getElementById("btn-led");
  const btnLaser = document.getElementById("btn-laser");

  const btnLockDoor = document.getElementById("btn-lock-door");

  const swClap = document.getElementById("sw-clap");
  const swSound = document.getElementById("sw-sound");
  const swMotion = document.getElementById("sw-motion");

  if (data.led_on) {
    btnLed.classList.add("btn-active");
    btnLed.textContent = "LED: ON";
  } else {
    btnLed.classList.remove("btn-active");
    btnLed.textContent = "LED: OFF";
  }

  if (data.safety_laser_enabled) {
    btnLaser.classList.add("btn-active");
    btnLaser.textContent = "Safety Laser: ON";
  } else {
    btnLaser.classList.remove("btn-active");
    btnLaser.textContent = "Safety Laser: OFF";
  }

  if (btnLockDoor) {
    btnLockDoor.disabled = !data.door_closed || data.door_locked;
    if (data.door_closed && !data.door_locked) {
      btnLockDoor.classList.add("btn-active");
    } else {
      btnLockDoor.classList.remove("btn-active");
    }
  }

  if (swClap) swClap.checked = !!data.clap_toggle_enabled;
  if (swSound) swSound.checked = !!data.sound_led_mode_enabled;
  if (swMotion) swMotion.checked = !!data.motion_led_mode_enabled;
}

let pollingStarted = false;
function startPolling() {
  if (pollingStarted) return;
  pollingStarted = true;
  setInterval(fetchState, 1000);
}

let pendingModes = null;
let pendingUntilMs = 0;

function setPendingModes(partial) {
  const now = Date.now();
  pendingModes = { ...(pendingModes || {}), ...partial };
  pendingUntilMs = now + 800;
}

function applyPendingModes(data) {
  const now = Date.now();
  if (!pendingModes || now > pendingUntilMs) {
    pendingModes = null;
    pendingUntilMs = 0;
    return data;
  }

  const merged = { ...data, ...pendingModes };

  const keys = Object.keys(pendingModes);
  const confirmed = keys.every((k) => data[k] === pendingModes[k]);
  if (confirmed) {
    pendingModes = null;
    pendingUntilMs = 0;
    return data;
  }

  return merged;
}

function startSseState() {
  try {
    const es = new EventSource("/api/stream");

    es.addEventListener("state", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        renderState(data);
      } catch (e) {
        // ignore
      }
    });

    es.onerror = () => {
      try {
        es.close();
      } catch (e) {
        // ignore
      }
      startPolling();
    };

    return true;
  } catch (e) {
    return false;
  }
}

async function fetchState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();
    renderState(data);

  } catch (err) {
    console.error("Error fetching state:", err);
  }
}

function setupControls() {
  const btnLed = document.getElementById("btn-led");
  const btnLaser = document.getElementById("btn-laser");
  const btnLockDoor = document.getElementById("btn-lock-door");

  const btnFireClose = document.getElementById("btn-fire-close");
  if (btnFireClose) {
    btnFireClose.addEventListener("click", () => {
      closeFireModal();
    });
  }

  const swClap = document.getElementById("sw-clap");
  const swSound = document.getElementById("sw-sound");
  const swMotion = document.getElementById("sw-motion");

  btnLed.addEventListener("click", async () => {
    await apiPost("/api/toggle_led");
    fetchState();
  });

  btnLaser.addEventListener("click", async () => {
    await apiPost("/api/toggle_laser");
    fetchState();
  });

  if (btnLockDoor) {
    btnLockDoor.addEventListener("click", async () => {
      const res = await apiPost("/api/lock_door");
      if (res && res.error === "door_open") {
        alert("Door is open, you can't lock it.");
      }
      fetchState();
    });
  }

  if (swClap) {
    swClap.addEventListener("change", async () => {
      const on = swClap.checked;
      setPendingModes({ clap_toggle_enabled: on, sound_led_mode_enabled: on ? false : undefined });
      await apiPost("/api/mode/clap_toggle", { on });
      setTimeout(fetchState, 900);
    });
  }

  if (swSound) {
    swSound.addEventListener("change", async () => {
      const on = swSound.checked;
      setPendingModes({ sound_led_mode_enabled: on, clap_toggle_enabled: on ? false : undefined });
      await apiPost("/api/mode/sound_led", { on });
      setTimeout(fetchState, 900);
    });
  }

  if (swMotion) {
    swMotion.addEventListener("change", async () => {
      const on = swMotion.checked;
      setPendingModes({ motion_led_mode_enabled: on });
      await apiPost("/api/mode/motion_led", { on });
      setTimeout(fetchState, 900);
    });
  }
}


function setupFaceUnlock() {
  const video = document.getElementById('video-feed');
  const canvas = document.getElementById('capture-canvas');
  const btnUnlock = document.getElementById('btn-face-unlock');
  const statusText = document.getElementById('face-status');

  if (!video || !btnUnlock || !statusText) return;

  if (!window.isSecureContext && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    statusText.innerText = "Camera blocked: open this page on localhost or use HTTPS.";
    statusText.style.color = "red";
    return;
  }

  // Request Camera
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    statusText.innerText = "Starting camera...";
    statusText.style.color = "#888";
    navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } })
      .then(stream => {
        video.srcObject = stream;
        return video.play();
      })
      .catch(err => {
        console.error("Camera access denied:", err);
        statusText.innerText = "Camera blocked/denied. Allow permission in the browser.";
        statusText.style.color = "red";
      });
  } else {
    statusText.innerText = "Camera API not supported";
    statusText.style.color = "red";
  }

  btnUnlock.addEventListener('click', async () => {
    if (!video.srcObject) {
      statusText.innerText = "Camera not ready";
      return;
    }

    // Capture frame
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, 320, 240);
    const dataUrl = canvas.toDataURL('image/jpeg');
    
    statusText.innerText = "Verifying...";
    statusText.style.color = "#888"; // reset color
    
    try {
      const result = await apiPost('/api/face_check', { image: dataUrl });
      
      if (result.authorized) {
        statusText.innerText = `Access GRANTED: ${result.name}`;
        statusText.style.color = "green";
      } else {
        const extra = result && result._http_status === 503 && result.detail ? ` (${result.detail})` : "";
        statusText.innerText = `Access DENIED: ${result.error || "Unknown"}${extra}`;
        statusText.style.color = "red";
      }
    } catch (e) {
      statusText.innerText = "Error connecting to server";
      statusText.style.color = "red";
    }
    
    // Reset status message after a few seconds
    setTimeout(() => {
        statusText.innerText = "Ready";
        statusText.style.color = "#888";
    }, 5000);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupControls();
  setupFaceUnlock();
  fetchState();
  const ok = startSseState();
  if (!ok) {
    startPolling();
  }
});
