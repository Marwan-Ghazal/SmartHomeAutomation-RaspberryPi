// web/static/script.js

async function apiPost(url) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return res.json();
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

async function fetchState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();

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
    const alarmPill = document.getElementById("alarm-pill");

    updatePill(motionPill, data.motion, "Motion detected", "No motion");
    updatePill(soundPill, data.sound_detected, "Sound detected", "Quiet");
    updatePill(alarmPill, data.alarm_active, "Alarm active", "Inactive", data.alarm_active);

    // Buttons
    const btnLed = document.getElementById("btn-led");
    const btnLaser = document.getElementById("btn-laser");

    if (data.led_on) {
      btnLed.classList.add("btn-active");
      btnLed.textContent = "LED: ON";
    } else {
      btnLed.classList.remove("btn-active");
      btnLed.textContent = "LED: OFF";
    }

    if (data.laser_on) {
      btnLaser.classList.add("btn-active");
      btnLaser.textContent = "Laser: ON";
    } else {
      btnLaser.classList.remove("btn-active");
      btnLaser.textContent = "Laser: OFF";
    }

  } catch (err) {
    console.error("Error fetching state:", err);
  }
}

function setupControls() {
  const btnLed = document.getElementById("btn-led");
  const btnLaser = document.getElementById("btn-laser");
  const btnStopBuzzer = document.getElementById("btn-stop-buzzer");
  const btnOpenWindow = document.getElementById("btn-open-window");
  const btnCloseWindow = document.getElementById("btn-close-window");

  btnLed.addEventListener("click", async () => {
    await apiPost("/api/toggle_led");
    fetchState();
  });

  btnLaser.addEventListener("click", async () => {
    await apiPost("/api/toggle_laser");
    fetchState();
  });

  btnStopBuzzer.addEventListener("click", async () => {
    await apiPost("/api/stop_buzzer");
    fetchState();
  });

  btnOpenWindow.addEventListener("click", async () => {
    await apiPost("/api/open_window");
  });

  btnCloseWindow.addEventListener("click", async () => {
    await apiPost("/api/close_window");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupControls();
  fetchState();
  setInterval(fetchState, 1000); // live updates every second
});
