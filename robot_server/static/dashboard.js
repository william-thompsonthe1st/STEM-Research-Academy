(() => {
  const bigPressed = new Set();
  const scoutPressed = {a: new Set(), b: new Set()};
  const speed = document.querySelector('#speed');
  const speedValue = document.querySelector('#speed-value');
  const direction = document.querySelector('#direction');
  const status = document.querySelector('#pi-status');
  const host = document.querySelector('#host');
  const cameraMessage = document.querySelector('#camera-message');
  const cameraImage = document.querySelector('.video');
  const toast = document.querySelector('#toast');
  const session = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const initialServerTime = Number(document.querySelector('meta[name="server-time-ms"]')?.content);
  let serverClockOffset = Number.isFinite(initialServerTime) ? initialServerTime - Date.now() : 0;
  let bigSequence = 0;
  let lastVector = '';
  let lastCameraRetryAt = 0;
  const scoutSequences = {a: 0, b: 0};
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
  speed.addEventListener('input', () => { speedValue.value = `${speed.value}%`; sendBig(true); });

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
      status.classList.toggle('offline', !hardwareReady);
      status.innerHTML = `<i></i> ${hardwareReady ? 'Pi controls ready' : 'GPIO unavailable - motors disabled'}`;
      host.textContent = `${data.hostname} / ${location.host}`;
      cameraMessage.classList.toggle('hidden', data.camera_available);
      cameraMessage.textContent = data.camera_error
        ? `Camera unavailable: ${data.camera_error}`
        : data.camera_device ? `Opening ${data.camera_device}...` : 'Looking for Logitech C270...';
      if (!data.camera_available && data.camera_error && Date.now() - lastCameraRetryAt > 5000) {
        lastCameraRetryAt = Date.now();
        cameraImage.src = `/camera.mjpg?retry=${lastCameraRetryAt}`;
      }
    } catch (_) {
      status.classList.add('offline');
      status.innerHTML = '<i></i> Disconnected';
    }
  }

  async function refreshScout(id) {
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
    } catch (_) {
      panel.classList.remove('scout-connected');
      statusElement.classList.add('offline');
      statusElement.innerHTML = '<i></i> Waiting';
      connectionElement.textContent = 'Waiting for LARP heartbeat';
      motionElement.textContent = 'Scout not connected';
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
  refreshStatus();
  refreshScout('a');
  refreshScout('b');
})();
