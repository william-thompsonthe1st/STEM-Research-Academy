(() => {
  const bigPressed = new Set();
  const scoutPressed = {a: new Set(), b: new Set()};
  const speed = document.querySelector('#speed');
  const speedValue = document.querySelector('#speed-value');
  const direction = document.querySelector('#direction');
  const status = document.querySelector('#pi-status');
  const host = document.querySelector('#host');
  const cameraMessage = document.querySelector('#camera-message');
  const cameraImage = document.querySelector('[data-stream-for="3tsahur"]');
  const cameraFeeds = [...document.querySelectorAll('[data-stream-for][data-stream-src]')];
  const toast = document.querySelector('#toast');
  const session = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const initialServerTime = Number(document.querySelector('meta[name="server-time-ms"]')?.content);
  let serverClockOffset = Number.isFinite(initialServerTime) ? initialServerTime - Date.now() : 0;
  let bigSequence = 0;
  let lastVector = '';
  let lastCameraRetryAt = 0;
  let activeRobotTab = '3tsahur';
  const scoutSequences = {a: 0, b: 0};
  const scoutStatusInFlight = {a: false, b: false};
  const visionEnabled = {'3tsahur': false, 'larp-a': false, 'larp-b': false};
  const visionInFlight = {'3tsahur': false, 'larp-a': false, 'larp-b': false};
  const bigKeys = new Set(['w', 'a', 's', 'd', 'q', 'e']);
  const scoutKeys = {
    a: {ArrowLeft: 'left', ArrowUp: 'forward', ArrowDown: 'back', ArrowRight: 'right'},
    b: {j: 'left', i: 'forward', k: 'back', l: 'right'}
  };
  const labels = {
    '1,0,0': 'Moving forward', '-1,0,0': 'Moving backward',
    '0,1,0': 'Strafing left', '0,-1,0': 'Strafing right',
    '0,0,1': 'Rotating left', '0,0,-1': 'Rotating right', '0,0,0': 'Standing by'
  };

  // At most one request per robot may be active. If input changes while that
  // request is running, only the newest command is retained. An urgent stop
  // aborts the active fetch and goes to the front immediately.
  function createLatestChannel(url, onFailure = () => {}) {
    let active = null;
    let pending = null;
    let generation = 0;

    async function pump() {
      if (active || !pending) return;
      const payload = pending;
      pending = null;
      const controller = new AbortController();
      const currentGeneration = ++generation;
      active = {controller, generation: currentGeneration};
      const timeout = window.setTimeout(() => controller.abort(), 180);
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
          cache: 'no-store',
          signal: controller.signal
        });
        if (!response.ok && response.status !== 409) throw new Error(`request failed: ${response.status}`);
      } catch (error) {
        if (error.name !== 'AbortError') onFailure(error);
      } finally {
        window.clearTimeout(timeout);
        if (active?.generation === currentGeneration) active = null;
        if (pending) pump();
      }
    }

    return (payload, urgent = false) => {
      pending = payload;
      if (urgent && active) {
        active.controller.abort();
        active = null;
      }
      pump();
    };
  }

  function commandTiming() {
    const issuedAt = Math.round(Date.now() + serverClockOffset);
    return {issued_at_ms: issuedAt, expires_at_ms: issuedAt + 300};
  }

  function showControlFailure() {
    status.classList.add('offline');
    status.innerHTML = '<i></i> Control delayed';
    showToast('Command link delayed - watchdog stopped the motors');
  }

  const queueBig = createLatestChannel('/api/drive', showControlFailure);
  const queueScouts = {
    a: createLatestChannel('/api/scouts/a/drive'),
    b: createLatestChannel('/api/scouts/b/drive')
  };

  function bigVector() {
    return {
      forward: Number(bigPressed.has('w')) - Number(bigPressed.has('s')),
      strafe: Number(bigPressed.has('a')) - Number(bigPressed.has('d')),
      rotate: Number(bigPressed.has('q')) - Number(bigPressed.has('e')),
      speed: Number(speed.value) / 100
    };
  }

  function renderKeys() {
    document.querySelectorAll('[data-key]').forEach(key => key.classList.toggle('active', bigPressed.has(key.dataset.key)));
  }

  function sendBig(force = false, override = null, urgent = false) {
    if (document.querySelector('#deadman')?.checked && !override && document.body.dataset.deadman !== 'held') return;
    const command = override || bigVector();
    const signature = JSON.stringify(command);
    const moving = command.forward || command.strafe || command.rotate;
    if (!force && !moving && signature === lastVector) return;
    lastVector = signature;
    direction.textContent = labels[`${command.forward},${command.strafe},${command.rotate}`] || 'Combined movement';
    queueBig({...command, session, sequence: ++bigSequence, ...commandTiming()}, urgent);
  }

  function killBig(show = false) {
    bigPressed.clear();
    renderKeys();
  direction.textContent = '3TSahur stopped';
    lastVector = '';
    sendBig(true, {forward: 0, strafe: 0, rotate: 0, speed: 0}, true);
  if (show) showToast('3TSahur kill switch activated');
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    window.setTimeout(() => toast.classList.remove('show'), 2200);
  }

  const scoutMotion = {
    left: {x: -100, y: 0}, forward: {x: 0, y: 100},
    stop: {x: 0, y: 0}, back: {x: 0, y: -100}, right: {x: 100, y: 0}
  };

  function activeScoutMotion(id) {
    const motions = scoutPressed[id];
    const x = Number(motions.has('right')) - Number(motions.has('left'));
    const y = Number(motions.has('forward')) - Number(motions.has('back'));
    if (y > 0) return 'forward';
    if (y < 0) return 'back';
    if (x < 0) return 'left';
    if (x > 0) return 'right';
    return 'stop';
  }

  function sendScout(id, motion, urgent = false) {
    if (document.querySelector('#deadman')?.checked && motion !== 'stop' && document.body.dataset.deadman !== 'held') return;
    const controls = document.querySelector(`[data-scout="${id}"]`);
    const vector = scoutMotion[motion] || scoutMotion.stop;
    const speedLimit = Number(controls.querySelector('input').value);
    queueScouts[id]({
      ...vector,
      speed: speedLimit,
      session,
      sequence: ++scoutSequences[id],
      ...commandTiming()
    }, urgent);
  }

  function renderScoutButtons(id, motion = activeScoutMotion(id)) {
    document.querySelectorAll(`[data-scout="${id}"] [data-motion]`).forEach(button => {
      button.classList.toggle('active', motion !== 'stop' && button.dataset.motion === motion);
    });
  }

  function killScout(id, show = false) {
    scoutPressed[id].clear();
    renderScoutButtons(id, 'stop');
    sendScout(id, 'stop', true);
  if (show) showToast(`LARP Scout ${id.toUpperCase()} kill switch activated`);
  }

  function killAll(show = false) {
    killBig(false);
    killScout('a');
    killScout('b');
    if (show) showToast('ALL ROBOTS STOPPED');
  }

  const robotTabs = [...document.querySelectorAll('[role="tab"][data-tab]')];
  const robotPanels = [...document.querySelectorAll('[role="tabpanel"][data-tab-panel]')];

  function activateOnlySelectedCamera(id) {
    activeRobotTab = id;
    // MJPEG feeds are continuous network traffic. Keep exactly one feed open
    // so the shared 2.4 GHz Pi hotspot always has room for control packets.
    cameraFeeds.forEach(feed => {
      if (feed.dataset.streamFor === id) {
        if (!feed.getAttribute('src')) feed.src = feed.dataset.streamSrc;
      } else {
        feed.removeAttribute('src');
      }
    });
  }

  function selectRobotTab(id, focus = false) {
    const selectedTab = robotTabs.find(tab => tab.dataset.tab === id);
    if (!selectedTab) return;
    const changingTabs = selectedTab.getAttribute('aria-selected') !== 'true';
    robotTabs.forEach(tab => {
      const selected = tab === selectedTab;
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    robotPanels.forEach(panel => {
      const selected = panel.dataset.tabPanel === id;
      panel.classList.toggle('active', selected);
      panel.hidden = !selected;
    });
    activateOnlySelectedCamera(id);
    // A tab change changes the operator's visual context. Stop all movement
    // before showing another robot so a held or touch command cannot continue.
    if (changingTabs) killAll();
    if (focus) selectedTab.focus();
  }

  function clearVisionOverlay(source) {
    const canvas = document.querySelector(`[data-vision-overlay="${source}"]`);
    if (!canvas) return;
    const context = canvas.getContext('2d');
    context.clearRect(0, 0, canvas.width, canvas.height);
  }

  function renderVision(source, data) {
    const button = document.querySelector(`[data-vision-toggle="${source}"]`);
    const label = document.querySelector(`[data-vision-status="${source}"]`);
    const canvas = document.querySelector(`[data-vision-overlay="${source}"]`);
    button.setAttribute('aria-pressed', String(Boolean(data.enabled)));
    button.textContent = `${data.enabled ? 'Vision on' : 'Vision off'} · C`;
    if (!data.enabled) {
      label.textContent = 'Vision ready when enabled';
      clearVisionOverlay(source);
      return;
    }
    if (!data.available) {
      label.textContent = data.error ? `Vision unavailable: ${data.error}` : 'Starting vision worker…';
      clearVisionOverlay(source);
      return;
    }
    const detections = data.detections || [];
    label.textContent = detections.length ? `${detections.length} person${detections.length === 1 ? '' : 's'} detected` : 'No person detected';
    const bounds = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(bounds.width));
    canvas.height = Math.max(1, Math.round(bounds.height));
    const context = canvas.getContext('2d');
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!data.frame_width || !data.frame_height) return;
    const scaleX = canvas.width / data.frame_width;
    const scaleY = canvas.height / data.frame_height;
    context.strokeStyle = '#b9ff38'; context.fillStyle = '#b9ff38'; context.lineWidth = 2;
    context.font = '700 12px ui-monospace, monospace';
    detections.forEach(box => {
      const x = box.x1 * scaleX, y = box.y1 * scaleY;
      const width = (box.x2 - box.x1) * scaleX, height = (box.y2 - box.y1) * scaleY;
      context.strokeRect(x, y, width, height);
      context.fillText(`PERSON ${Math.round(box.confidence * 100)}%`, x + 3, Math.max(13, y - 5));
    });
  }

  async function refreshVision(source) {
    if (!visionEnabled[source] || visionInFlight[source]) return;
    visionInFlight[source] = true;
    try {
      const response = await fetch(`/api/vision/${source}`, {cache: 'no-store'});
      renderVision(source, await response.json());
    } catch (_) {
      renderVision(source, {enabled: true, available: false, error: 'status request failed'});
    } finally {
      visionInFlight[source] = false;
    }
  }

  async function toggleVision(source) {
    const enabled = !visionEnabled[source];
    visionEnabled[source] = enabled;
    renderVision(source, {enabled, available: null, detections: []});
    try {
      const response = await fetch(`/api/vision/${source}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({enabled}), cache: 'no-store'});
      if (!response.ok) throw new Error(`request failed: ${response.status}`);
      renderVision(source, await response.json());
      showToast(`${source === '3tsahur' ? '3TSahur' : source === 'larp-a' ? 'LARP Scout A' : 'LARP Scout B'} vision ${enabled ? 'enabled' : 'disabled'}`);
    } catch (_) {
      visionEnabled[source] = false;
      renderVision(source, {enabled: false, available: null, detections: []});
      showToast('Vision unavailable - robot controls remain active');
    }
  }

  function keyMotion(event, id) {
    return scoutKeys[id][id === 'a' ? event.key : event.key.toLowerCase()];
  }

  window.addEventListener('keydown', event => {
    const key = event.key.toLowerCase();
    if (event.key === 'Escape') {
      event.preventDefault();
      killAll(true);
      return;
    }
    if (key === ' ') {
      event.preventDefault();
      killBig(true);
      return;
    }
    if (key === 'c' && !event.repeat) {
      event.preventDefault();
      toggleVision(activeRobotTab);
      return;
    }
    if (bigKeys.has(key)) {
      event.preventDefault();
      if (event.repeat) return;
      bigPressed.add(key);
      renderKeys();
      sendBig(true);
      return;
    }
    for (const id of ['a', 'b']) {
      const motion = keyMotion(event, id);
      if (!motion) continue;
      event.preventDefault();
      if (event.repeat) return;
      scoutPressed[id].add(motion);
      renderScoutButtons(id);
      sendScout(id, activeScoutMotion(id));
      return;
    }
  });

  window.addEventListener('keyup', event => {
    const key = event.key.toLowerCase();
    if (bigKeys.has(key)) {
      event.preventDefault();
      bigPressed.delete(key);
      renderKeys();
      sendBig(true, null, bigPressed.size === 0);
      return;
    }
    for (const id of ['a', 'b']) {
      const motion = keyMotion(event, id);
      if (!motion) continue;
      event.preventDefault();
      scoutPressed[id].delete(motion);
      renderScoutButtons(id);
      const nextMotion = activeScoutMotion(id);
      sendScout(id, nextMotion, nextMotion === 'stop');
      return;
    }
  });

  window.addEventListener('blur', () => killAll());
  document.addEventListener('visibilitychange', () => { if (document.hidden) killAll(); });
  window.addEventListener('pagehide', () => killAll());
  document.querySelector('#stop').addEventListener('click', () => killBig(true));
  document.querySelector('#kill-all').addEventListener('click', () => killAll(true));
  document.querySelectorAll('[data-vision-toggle]').forEach(button => button.addEventListener('click', () => toggleVision(button.dataset.visionToggle)));
  speed.addEventListener('input', () => { speedValue.value = `${speed.value}%`; sendBig(true); });

  robotTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectRobotTab(tab.dataset.tab));
    tab.addEventListener('keydown', event => {
      let nextIndex = null;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % robotTabs.length;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index - 1 + robotTabs.length) % robotTabs.length;
      if (event.key === 'Home') nextIndex = 0;
      if (event.key === 'End') nextIndex = robotTabs.length - 1;
      if (nextIndex === null) return;
      event.preventDefault();
      selectRobotTab(robotTabs[nextIndex].dataset.tab, true);
    });
  });

  document.querySelectorAll('.scout-controls').forEach(controls => {
    const id = controls.dataset.scout;
    const slider = controls.querySelector('input');
    const output = controls.querySelector('output');
    slider.addEventListener('input', () => { output.value = `${slider.value}%`; });
    controls.querySelectorAll('[data-motion]').forEach(button => {
      const motion = button.dataset.motion;
      if (motion === 'stop') {
        button.addEventListener('click', () => killScout(id, true));
        return;
      }
      button.addEventListener('pointerdown', event => {
        event.preventDefault();
        button.setPointerCapture?.(event.pointerId);
        scoutPressed[id].add(motion);
        renderScoutButtons(id);
        sendScout(id, activeScoutMotion(id));
      });
      ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => button.addEventListener(type, () => {
        scoutPressed[id].delete(motion);
        renderScoutButtons(id);
        const nextMotion = activeScoutMotion(id);
        sendScout(id, nextMotion, nextMotion === 'stop');
      }));
    });
  });

  async function refreshStatus() {
    const requestStartedAt = Date.now();
    try {
      const response = await fetch('/api/status', {cache: 'no-store'});
      const data = await response.json();
      const responseReceivedAt = Date.now();
      if (Number.isFinite(data.server_time_ms)) {
        serverClockOffset = data.server_time_ms - ((requestStartedAt + responseReceivedAt) / 2);
      }
      const hardwareReady = data.gpio === 'hardware';
      cameraProfile.value = data.camera_profile || 'balanced';
      document.querySelector('#health-panel').innerHTML = `<dt>Pi control</dt><dd>${hardwareReady ? 'ready' : 'simulation'}</dd><dt>Camera</dt><dd>${data.camera_available ? `${data.camera_width}x${data.camera_height} @ ${data.camera_fps}` : 'unavailable'}</dd><dt>Network</dt><dd>${location.host}</dd>`;
      status.classList.toggle('offline', !hardwareReady);
      status.innerHTML = `<i></i> ${hardwareReady ? 'Pi controls ready' : 'GPIO unavailable - motors disabled'}`;
      host.textContent = `${data.hostname} / ${location.host}`;
      cameraMessage.classList.toggle('hidden', data.camera_available);
      cameraMessage.textContent = data.camera_error
        ? `Camera unavailable: ${data.camera_error}`
        : data.camera_device ? `Opening ${data.camera_device}...` : 'Looking for Logitech C270...';
      if (!data.camera_available && data.camera_error && Date.now() - lastCameraRetryAt > 5000) {
        lastCameraRetryAt = Date.now();
        if (activeRobotTab === '3tsahur') cameraImage.src = `${cameraImage.dataset.streamSrc}?retry=${lastCameraRetryAt}`;
      }
    } catch (_) {
      status.classList.add('offline');
      status.innerHTML = '<i></i> Disconnected';
    }
  }

  function renderCsiSensor(id, data, online) {
    const sensor = document.querySelector(`#scout-${id}-csi`);
    const state = document.querySelector(`#scout-${id}-csi-state`);
    const levelOutput = document.querySelector(`#scout-${id}-csi-level`);
    const meter = document.querySelector(`#scout-${id}-csi-meter`);
    const meterTrack = meter.parentElement;
    const level = Math.max(0, Math.min(100, Number(data.motion_level) || 0));
    const detected = online && Boolean(data.motion);
    sensor.classList.toggle('detected', detected);
    meter.style.width = `${level}%`;
    meterTrack.setAttribute('aria-valuenow', String(Math.round(level)));
    levelOutput.value = online ? `${Math.round(level)}%` : '--';
    state.textContent = !online
      ? 'Awaiting Scout telemetry'
      : detected ? 'Possible presence - check video' : 'No strong disturbance';
  }

  async function refreshScout(id) {
    if (scoutStatusInFlight[id]) return;
    scoutStatusInFlight[id] = true;
    const panel = document.querySelector(`[data-scout-panel="${id}"]`);
    const statusElement = document.querySelector(`#scout-${id}-status`);
    const connectionElement = document.querySelector(`#scout-${id}-connection`);
    const motionElement = document.querySelector(`#scout-${id}-motion`);
    try {
      const response = await fetch(`/api/scouts/${id}/status`, {cache: 'no-store'});
      const data = await response.json();
      const connected = Boolean(data.connected || data.online);
      panel.classList.toggle('scout-connected', connected);
      statusElement.classList.toggle('waiting', !connected);
      statusElement.classList.toggle('offline', !connected);
      statusElement.innerHTML = `<i></i> ${data.online ? 'Ready' : connected ? 'Connected' : 'Waiting'}`;
      connectionElement.textContent = connected ? 'LARP connected to 3TSahur-Swarm' : 'Waiting for LARP heartbeat';
      motionElement.textContent = data.online
        ? `${data.motion ? 'CSI disturbance' : 'CSI idle'} / ${Math.round(data.motion_level || 0)}%`
        : connected ? 'Heartbeat received' : 'Scout not connected';
      renderCsiSensor(id, data, Boolean(data.online));
      sampleCalibration(id, Math.max(0, Math.min(100, Number(data.motion_level) || 0)));
    } catch (_) {
      panel.classList.remove('scout-connected');
      statusElement.classList.add('offline');
      statusElement.innerHTML = '<i></i> Waiting';
      connectionElement.textContent = 'Waiting for LARP heartbeat';
      motionElement.textContent = 'Scout not connected';
      renderCsiSensor(id, {}, false);
    } finally {
      scoutStatusInFlight[id] = false;
    }
  }

  // These are safety heartbeats, not a request flood: each channel retains
  // only its latest command and never builds a queue.
  window.setInterval(() => { if (bigPressed.size) sendBig(true); }, 80);
  window.setInterval(() => {
    for (const id of ['a', 'b']) if (scoutPressed[id].size) sendScout(id, activeScoutMotion(id));
  }, 100);
  window.setInterval(refreshStatus, 3000);
  window.setInterval(() => { refreshScout('a'); refreshScout('b'); }, 2000);
  window.setInterval(() => {
    const id = activeRobotTab === 'larp-a' ? 'a' : activeRobotTab === 'larp-b' ? 'b' : null;
    if (id) refreshScout(id);
  }, 750);
  window.setInterval(() => refreshVision(activeRobotTab), 500);
  const deadman = document.querySelector('#deadman');
  const cameraProfile = document.querySelector('#camera-profile');
  let lastGamepadSignature = '';
  let lastGamepadSentAt = 0;
  let gamepadWasMoving = false;
  const calibration = {a: null, b: null};
  function reportEvent(kind, source, message) { fetch('/api/events', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind, source, message}), cache: 'no-store'}).catch(() => {}); }
  async function refreshEvents() { try { const data = await (await fetch('/api/events', {cache: 'no-store'})).json(); document.querySelector('#event-list').innerHTML = (data.events || []).slice(0, 8).map(e => `<li><time>${new Date(e.at_ms).toLocaleTimeString()}</time> ${e.message}</li>`).join('') || '<li>No mission events yet.</li>'; } catch (_) {} }
  async function takeSnapshot(source) { try { const response = await fetch(`/api/snapshots/${source}`, {method: 'POST', cache: 'no-store'}); const data = await response.json(); if (!response.ok) throw Error(data.error); window.open(data.url, '_blank', 'noopener'); showToast('Snapshot saved'); refreshEvents(); } catch (error) { showToast(error.message || 'Snapshot unavailable'); } }
  function startCalibration(id) { calibration[id] = {until: Date.now() + 20000, values: []}; document.querySelector(`#scout-${id}-calibration`).value = 'Calibrating… keep area clear'; reportEvent('calibration', `larp-${id}`, 'CSI calibration started'); }
  function sampleCalibration(id, level) { const item = calibration[id]; if (!item) return; item.values.push(level); if (Date.now() < item.until) return; const baseline = item.values.reduce((a, b) => a + b, 0) / Math.max(1, item.values.length); document.querySelector(`#scout-${id}-calibration`).value = `Baseline ${Math.round(baseline)}% · suggested alert ${Math.min(100, Math.round(baseline + 15))}%`; calibration[id] = null; refreshEvents(); }
  document.querySelectorAll('[data-snapshot]').forEach(button => button.addEventListener('click', () => takeSnapshot(button.dataset.snapshot)));
  document.querySelectorAll('[data-calibrate]').forEach(button => button.addEventListener('click', () => startCalibration(button.dataset.calibrate)));
  deadman.addEventListener('change', () => { killAll(); reportEvent('safety', 'dashboard', `Dead-man mode ${deadman.checked ? 'enabled' : 'disabled'}`); });
  cameraProfile.addEventListener('change', async () => { const profile = cameraProfile.value; killBig(); try { const response = await fetch('/api/camera/profile', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({profile}), cache: 'no-store'}); const data = await response.json(); if (!response.ok) throw Error(data.error); cameraImage.removeAttribute('src'); window.requestAnimationFrame(() => { if (activeRobotTab === '3tsahur') cameraImage.src = `${cameraImage.dataset.streamSrc}?profile=${Date.now()}`; }); reportEvent('camera-profile', '3tsahur', `Camera profile: ${profile}`); showToast(`Camera set to ${data.width}x${data.height} @ ${data.fps} FPS`); } catch (error) { showToast(error.message || 'Camera profile unavailable'); } });
  window.addEventListener('keydown', event => { if (deadman.checked && event.key === 'Shift') document.body.dataset.deadman = 'held'; });
  window.addEventListener('keyup', event => { if (deadman.checked && event.key === 'Shift') { delete document.body.dataset.deadman; killAll(); } });
  window.setInterval(refreshEvents, 2000);
  window.setInterval(() => { const pad = navigator.getGamepads?.()[0]; if (!pad || activeRobotTab !== '3tsahur') return; const held = Boolean(pad.buttons[0]?.pressed); if (deadman.checked && !held) { delete document.body.dataset.deadman; if (gamepadWasMoving) killBig(); gamepadWasMoving = false; lastGamepadSignature = ''; return; } if (deadman.checked) document.body.dataset.deadman = 'held'; const forward = Math.abs(pad.axes[1] || 0) > .18 ? -(pad.axes[1] || 0) : 0; const strafe = Math.abs(pad.axes[0] || 0) > .18 ? pad.axes[0] : 0; const rotate = Math.abs(pad.axes[2] || 0) > .18 ? pad.axes[2] : 0; const moving = Boolean(forward || strafe || rotate); const command = {forward, strafe, rotate, speed: Number(speed.value) / 100}; const signature = JSON.stringify(command); const now = performance.now(); if (moving && (signature !== lastGamepadSignature || now - lastGamepadSentAt >= 80)) { sendBig(true, command); lastGamepadSignature = signature; lastGamepadSentAt = now; } else if (!moving && gamepadWasMoving) { sendBig(true, {forward: 0, strafe: 0, rotate: 0, speed: 0}, true); lastGamepadSignature = ''; } gamepadWasMoving = moving; }, 100);
  activateOnlySelectedCamera(activeRobotTab);
  refreshStatus();
  refreshScout('a');
  refreshScout('b');
  refreshEvents();
})();
