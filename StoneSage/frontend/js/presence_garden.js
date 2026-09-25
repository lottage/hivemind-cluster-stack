/**
 * StoneSage Real Presence, Courage Computer Voice & Landscape Garden Cockpit.
 * Connects to /api/presence/* and /api/garden/* endpoints.
 */

export async function fetchPresenceState() {
  try {
    const res = await fetch('/api/presence/status');
    const json = await res.json();
    if (!json.ok) return null;
    renderPresence(json.data);
    return json.data;
  } catch (e) {
    console.warn('Presence fetch failed:', e);
    return null;
  }
}

// Identity key shared with the backend (frigate_presence.norm_name, wildlife_admin.prefix): 'Aunt May' -> 'aunt-may'
const normName = (n) => n.trim().toLowerCase().replace(/ /g, '-').replace(/'/g, '').replace(/[^a-z0-9-]/g, '');

async function postJSON(url, body) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return res.json();
}

// "✗ Wrong" / "Correct as" on a card, and the "+ New profile" form. Corrections go back to where the sighting came
// from (Frigate event or sentry snapshot); correcting to a person also trains Frigate's face recognition.
function bindCorrections(grid) {
  const form = document.getElementById('presence-new-profile');
  let pending = null;  // the card waiting for a new profile to be created

  const apply = async (row, action, name) => {
    const note = document.createElement('span');
    note.style.cssText = 'font-size:0.68rem; color:var(--term-accent-gold);';
    note.textContent = 'saving…';
    row.replaceChildren(note);
    const res = await postJSON('/api/presence/correct', { source: row.dataset.src, ref: row.dataset.ref, action, name });
    const trained = res.faces_trained ? ` · ${res.faces_trained} face(s) learned` : res.face_registered === true ? ' · face learned' : '';
    note.textContent = res.ok ? (action === 'reject' ? 'hidden' : `now ${name}${trained}`) : `error: ${res.error}`;
    if (res.ok) setTimeout(fetchPresenceState, 800);
  };

  grid.onchange = (e) => {
    const sel = e.target.closest('select[data-correct]');
    if (!sel || !sel.value) return;
    const row = sel.closest('[data-src]');
    if (sel.value === '__new__') {
      pending = row;
      form.style.display = 'block';
      document.getElementById('np-name').focus();
      sel.value = '';
      return;
    }
    if (confirm(`This sighting shown as ${row.dataset.shown} is really ${sel.value}?`)) apply(row, 'relabel', sel.value);
    else sel.value = '';
  };
  grid.onclick = async (e) => {
    const rej = e.target.closest('button[data-correct="reject"]');
    if (rej) {
      const row = rej.closest('[data-src]');
      if (confirm(`Hide this sighting of ${row.dataset.shown}? (It is kept aside, not deleted.)`)) apply(row, 'reject', '');
      return;
    }
    if (e.target.id === 'np-cancel') { form.style.display = 'none'; pending = null; return; }
    if (e.target.id !== 'np-save') return;
    const kind = document.getElementById('np-kind').value;
    const extra = document.getElementById('np-extra').value.trim();
    const body = { name: document.getElementById('np-name').value.trim(), kind,
                   traits: document.getElementById('np-traits').value.trim(),
                   [kind === 'person' ? 'role' : 'species']: extra };
    const status = document.getElementById('np-status');
    status.textContent = 'saving…';
    const res = await postJSON('/api/presence/profiles', body);
    if (!res.ok) { status.textContent = `error: ${res.error}`; return; }
    form.style.display = 'none';
    if (pending) await apply(pending, 'relabel', res.profile.name);
    pending = null;
    fetchPresenceState();
  };
}

export function renderPresence(data) {
  if (!data) return;

  // Render resident & pet locations
  const locContainer = document.getElementById('presence-locations-grid');
  if (locContainer && data.locations) {
    let html = '';
    const locs = data.locations;
    const known = data.known_entities || {};
    const allEntities = [...(known.people || []), ...(known.pets || [])];
    if (locs.someone) allEntities.push({ name: 'Someone', role: 'Person Frigate could not identify' });

    const profileNames = [...(known.people || []), ...(known.pets || [])].map((e) => e.name);

    allEntities.forEach(ent => {
      const key = normName(ent.name);
      const loc = locs[key];
      const isOnline = loc && loc.minutes_ago < 60;
      const statusBadge = loc && loc.minutes_ago === 0
        ? `<span style="color:#22c55e; font-weight:bold;">🟢 In view now</span>`
        : isOnline
        ? `<span style="color:#22c55e; font-weight:bold;">🟢 Active (${Math.round(loc.minutes_ago)}m ago)</span>`
        : `<span style="color:var(--term-text-muted); font-weight:bold;">⚪ Inactive (${loc ? Math.round(loc.minutes_ago) + 'm ago' : 'No recent sighting'})</span>`;

      // Frigate sightings carry an event id (snapshot proxied by StoneSage); sentry sightings a snapshot filename
      const snapSrc = loc && loc.source === 'frigate' && loc.event_id ? `/api/frigate/snapshot/${loc.event_id}`
        : loc && loc.snapshot ? `/api/presence/snapshot/${loc.snapshot}` : null;
      const snapshotImg = snapSrc
        ? `<div style="margin-top:6px; border:1px solid var(--term-border-dim); border-radius:3px; overflow:hidden; max-height:90px; background:#000;">
             <img src="${snapSrc}" alt="${ent.name}" style="width:100%; height:90px; object-fit:cover;" loading="lazy">
           </div>`
        : `<div style="margin-top:6px; height:45px; background:rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; font-size:0.7rem; color:var(--term-text-muted);">No snapshot</div>`;
      const lastSeen = !loc ? 'Unknown'
        : loc.last_seen || new Date(loc.mtime * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
      const via = loc && loc.source === 'frigate' ? ' · Frigate' : '';
      // Correction controls: only for a sighting that has an image to judge
      const src = loc && loc.source === 'frigate' && loc.event_id ? ['frigate', loc.event_id]
        : loc && loc.snapshot ? ['sentry', loc.snapshot] : null;
      const correct = !src ? '' : `
          <div style="display:flex; gap:4px; margin-top:4px;" data-src="${src[0]}" data-ref="${src[1]}" data-shown="${ent.name}">
            <button type="button" class="preset-btn" style="padding:1px 6px; font-size:0.68rem;" data-correct="reject" title="Not a real sighting of ${ent.name}: hide it">✗ Wrong</button>
            <select class="form-input" style="flex:1; font-size:0.68rem; padding:1px 2px;" data-correct="relabel">
              <option value="">Correct as…</option>
              ${profileNames.filter((n) => n !== ent.name).map((n) => `<option value="${n}">${n}</option>`).join('')}
              <option value="__new__">+ New profile…</option>
            </select>
          </div>`;

      html += `
        <div style="background:var(--term-bg); border:1px solid var(--term-border-dim); border-radius:4px; padding:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:bold; color:var(--term-text-bright);">${ent.name}</span>
            <span style="font-size:0.7rem; font-family:monospace;">${statusBadge}</span>
          </div>
          <div style="font-size:0.72rem; color:var(--term-text-muted); margin-top:2px;">${ent.role || ent.breed || ent.species}</div>
          ${snapshotImg}
          <div style="font-size:0.68rem; color:var(--term-text-muted); margin-top:4px;">Last: ${lastSeen}${loc && loc.camera ? ` · ${loc.camera}` : ''}${via}</div>${correct}
        </div>
      `;
    });
    locContainer.innerHTML = html + `
      <div id="presence-new-profile" style="display:none; grid-column:1/-1; background:var(--term-bg); border:1px dashed var(--term-accent-gold); border-radius:4px; padding:8px; font-size:0.74rem;">
        <b>New recognition profile</b>
        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
          <input class="form-input" id="np-name" placeholder="Name" maxlength="30" style="flex:1; min-width:110px;">
          <select class="form-input" id="np-kind"><option value="person">Person</option><option value="pet">Pet</option></select>
          <input class="form-input" id="np-extra" placeholder="Role (e.g. Visitor) / species (e.g. cat)" style="flex:1; min-width:140px;">
        </div>
        <input class="form-input" id="np-traits" placeholder="Looks like… (helps the vision model, e.g. tall, grey beard, red jacket)" maxlength="300" style="width:100%; margin-top:6px;">
        <div style="display:flex; gap:6px; margin-top:6px;">
          <button type="button" class="preset-btn" id="np-save">[Save &amp; apply]</button>
          <button type="button" class="preset-btn" id="np-cancel">[Cancel]</button>
          <span id="np-status" style="color:var(--term-text-muted); align-self:center;"></span>
        </div>
      </div>`;
    bindCorrections(locContainer);
  }

  // Render Appliance Status
  const appContainer = document.getElementById('presence-appliances-box');
  if (appContainer && data.appliances) {
    const d = data.appliances.dryer || {};
    const w = data.appliances.washer || {};
    const dBadge = d.is_running
      ? `<span style="color:#22c55e; font-weight:bold;">RUNNING (${d.remaining_time || 'active'})</span>`
      : (d.finished_recently ? `<span style="color:#eab308; font-weight:bold;">FINISHED (${Math.round(d.last_cycle_minutes_ago || 0)}m ago)</span>` : `<span style="color:var(--term-text-muted);">IDLE / OFF</span>`);
    const wBadge = w.is_running
      ? `<span style="color:#22c55e; font-weight:bold;">RUNNING (${w.remaining_time || 'active'})</span>`
      : (w.finished_recently ? `<span style="color:#eab308; font-weight:bold;">FINISHED (${Math.round(w.last_cycle_minutes_ago || 0)}m ago)</span>` : `<span style="color:var(--term-text-muted);">IDLE / OFF</span>`);

    appContainer.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
        <div style="background:var(--term-bg); padding:6px; border:1px solid var(--term-border-dim); border-radius:3px;">
          <div style="font-size:0.72rem; color:var(--term-text-muted);">🧺 LG DRYER</div>
          <div style="font-size:0.82rem; font-weight:bold; margin-top:2px;">${dBadge}</div>
        </div>
        <div style="background:var(--term-bg); padding:6px; border:1px solid var(--term-border-dim); border-radius:3px;">
          <div style="font-size:0.72rem; color:var(--term-text-muted);">🫧 LG WASHER</div>
          <div style="font-size:0.82rem; font-weight:bold; margin-top:2px;">${wBadge}</div>
        </div>
      </div>
    `;
  }
}

// ------------------------------------------------------------ live cameras ----
// One tile per camera in config.json camera_ui (backend/camera_ui.py):
//   webrtc   Frigate/go2rtc. StoneSage only relays the SDP offer/answer; video flows go2rtc -> browser.
//   hls      Home Assistant's own stream (solar driveway), proxied through StoneSage; the browser plays HLS natively.
//   snapshot still frame with a refresh button; the server keeps battery cameras to one wake per min_refresh_s.
// PTZ cameras get arrows and their HA presets.
const livePeers = [];
const liveVideos = [];

function stopLive() {
  while (livePeers.length) {
    const pc = livePeers.pop();
    try { pc.close(); } catch (e) { /* already closed */ }
  }
  while (liveVideos.length) {  // HLS: stop fetching so HA ends the stream (~30 s later)
    const v = liveVideos.pop();
    v.pause(); v.removeAttribute('src'); v.load();
  }
  const grid = document.getElementById('presence-live-grid');
  if (grid) grid.innerHTML = '';
}

function iceGathered(pc, ms = 1500) {
  if (pc.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => { if (pc.iceGatheringState === 'complete') resolve(); };
    pc.addEventListener('icegatheringstatechange', done);
    setTimeout(resolve, ms);  // host candidates are enough on the LAN; don't wait for slow STUN
  });
}

function setStatus(status, text, live = false) {
  status.textContent = text;
  status.style.color = live ? '#22c55e' : 'var(--term-text-muted)';
}

// When a stream fails, send the browser's own ICE view to StoneSage's log (candidate types and pair states):
// the only place that shows why one device connects and another does not.
async function reportIceFailure(pc, stream, status) {
  try {
    const all = [];
    (await pc.getStats()).forEach((s) => all.push(s));
    const byId = Object.fromEntries(all.map((s) => [s.id, s]));
    const cand = (c) => (c ? `${c.candidateType}/${c.protocol} ${c.address || c.ip || '?'}:${c.port}` : '?');
    const report = {
      stream, ua: navigator.userAgent, page: location.origin,
      local: all.filter((s) => s.type === 'local-candidate').map(cand),
      remote: all.filter((s) => s.type === 'remote-candidate').map(cand),
      pairs: all.filter((s) => s.type === 'candidate-pair').map((p) =>
        `${cand(byId[p.localCandidateId])} -> ${cand(byId[p.remoteCandidateId])}: ${p.state} req=${p.requestsSent || 0} resp=${p.responsesReceived || 0}`),
    };
    status.title = report.pairs.join('\n') || 'no candidate pairs';
    await fetch('/api/cameras/webrtc-report', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(report),
    });
  } catch (e) { /* diagnostics only */ }
}

async function playWebRTC(video, status, stream) {
  const pc = new RTCPeerConnection();
  livePeers.push(pc);
  const media = new MediaStream();
  video.srcObject = media;
  pc.ontrack = (e) => media.addTrack(e.track);
  pc.onconnectionstatechange = () => {
    const s = pc.connectionState;
    setStatus(status, { connected: '● LIVE', failed: 'connection failed', disconnected: 'reconnecting…' }[s] || s, s === 'connected');
    if (s === 'failed') reportIceFailure(pc, stream, status);
  };
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.addTransceiver('audio', { direction: 'recvonly' });
  await pc.setLocalDescription(await pc.createOffer());
  await iceGathered(pc);
  const res = await fetch('/api/cameras/webrtc', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stream, offer: { sdp: pc.localDescription.sdp } }),
  });
  const json = await res.json();
  if (!json.ok) throw new Error(json.error || 'signalling failed');
  await pc.setRemoteDescription(json.answer);
}

async function playHLS(video, status, entity) {
  if (!video.canPlayType('application/vnd.apple.mpegurl')) throw new Error('this browser cannot play HLS');
  setStatus(status, 'waking camera…');
  const res = await fetch('/api/cameras/hls', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entity }),
  });
  const json = await res.json();
  if (!json.ok) throw new Error(json.error || 'stream failed');
  liveVideos.push(video);
  video.addEventListener('playing', () => setStatus(status, '● LIVE (HA)', true));
  video.addEventListener('error', () => setStatus(status, 'stream ended'));
  video.src = json.url;
  await video.play().catch(() => { /* autoplay rules: muted video still starts on its own */ });
}

async function loadSnapshot(img, status, entity, force) {
  setStatus(status, force ? 'waking camera…' : 'loading…');
  const res = await fetch(`/api/cameras/snapshot?entity=${encodeURIComponent(entity)}${force ? '&force=1' : ''}`);
  if (!res.ok) { setStatus(status, (await res.json().catch(() => ({}))).error || `HTTP ${res.status}`); return; }
  const age = parseInt(res.headers.get('X-Snapshot-Age') || '0', 10);
  if (img.dataset.blob) URL.revokeObjectURL(img.dataset.blob);
  img.dataset.blob = URL.createObjectURL(await res.blob());
  img.src = img.dataset.blob;
  setStatus(status, age < 5 ? 'snapshot · just now' : `snapshot · ${age < 120 ? age + ' s' : Math.round(age / 60) + ' min'} old`);
}

async function ptz(entity, action, preset, status) {
  setStatus(status, action === 'preset' ? `moving to ${preset.trim()}…` : `moving ${action}…`);
  const res = await fetch('/api/cameras/ptz', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ entity, action, preset }),
  });
  const json = await res.json();
  setStatus(status, json.ok ? 'moved' : `PTZ: ${json.error}`);
}

function tileHTML(c, i) {
  const media = c.live === 'snapshot'
    ? `<img id="cam-img-${i}" alt="${c.name}" style="width:100%; aspect-ratio:16/9; object-fit:cover; display:block; background:#000;">`
    : `<video id="cam-vid-${i}" autoplay muted playsinline style="width:100%; aspect-ratio:16/9; display:block; background:#000;" title="Click to toggle sound"></video>`;
  const btn = 'class="preset-btn" style="padding:2px 8px; font-size:0.72rem;"';
  const ptzHTML = !c.ptz ? '' : `
    <div style="display:flex; flex-wrap:wrap; gap:4px; align-items:center; padding:4px 6px; background:var(--term-bg); border-top:1px dashed var(--term-border-dim);">
      <button type="button" ${btn} data-cam="${i}" data-ptz="left" title="Pan left">◀</button>
      <button type="button" ${btn} data-cam="${i}" data-ptz="up" title="Tilt up">▲</button>
      <button type="button" ${btn} data-cam="${i}" data-ptz="down" title="Tilt down">▼</button>
      <button type="button" ${btn} data-cam="${i}" data-ptz="right" title="Pan right">▶</button>
      ${(c.ptz.presets || []).map((p) => `<button type="button" ${btn} data-cam="${i}" data-ptz="preset" data-preset="${p.replace(/"/g, '&quot;')}">${p.trim()}</button>`).join('')}
    </div>`;
  const refresh = c.live === 'snapshot'
    ? `<button type="button" ${btn} data-cam="${i}" data-refresh="1" title="${c.min_refresh_s ? `Battery camera: at most one new frame every ${Math.round(c.min_refresh_s / 60)} min` : 'New snapshot'}">⟳ Refresh</button>` : '';
  return `
    <div style="background:#000; border:1px solid var(--term-border-dim); border-radius:4px; overflow:hidden;">
      ${media}
      <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; padding:4px 6px; font-size:0.72rem; background:var(--term-bg);">
        <span style="font-weight:bold; color:var(--term-text-bright);">${c.name}</span>
        <span style="display:flex; gap:6px; align-items:center;">
          <span id="cam-status-${i}" style="font-family:monospace; color:var(--term-text-muted);">connecting…</span>${refresh}
        </span>
      </div>${ptzHTML}
    </div>`;
}

async function startLive() {
  const grid = document.getElementById('presence-live-grid');
  if (!grid) return;
  stopLive();
  grid.innerHTML = '<div style="color:var(--term-text-muted); font-size:0.75rem;">Connecting to cameras…</div>';
  let cams = [];
  try {
    cams = (await (await fetch('/api/cameras/live')).json()).cameras || [];
  } catch (e) { /* shown below */ }
  if (!cams.length) {
    grid.innerHTML = '<div style="color:var(--term-text-muted); font-size:0.75rem;">No cameras configured (config.json camera_ui).</div>';
    return;
  }
  grid.innerHTML = cams.map(tileHTML).join('');
  grid.onclick = (e) => {
    const b = e.target.closest('[data-cam]');
    if (!b) return;
    const i = +b.dataset.cam;
    const status = document.getElementById(`cam-status-${i}`);
    if (b.dataset.refresh) return loadSnapshot(document.getElementById(`cam-img-${i}`), status, cams[i].entity, true);
    if (b.dataset.ptz) return ptz(cams[i].entity, b.dataset.ptz, b.dataset.preset || '', status);
  };
  cams.forEach((c, i) => {
    const status = document.getElementById(`cam-status-${i}`);
    if (c.live === 'snapshot') { loadSnapshot(document.getElementById(`cam-img-${i}`), status, c.entity, false); return; }
    const video = document.getElementById(`cam-vid-${i}`);
    video.addEventListener('click', () => { video.muted = !video.muted; });
    const play = c.live === 'webrtc' ? playWebRTC(video, status, c.stream) : playHLS(video, status, c.entity);
    play.catch((e) => setStatus(status, e.message));
  });
}

export function showPresenceTab(which) {
  const live = which === 'live';
  document.getElementById('presence-locations-grid').style.display = live ? 'none' : 'grid';
  document.getElementById('presence-live-grid').style.display = live ? 'grid' : 'none';
  document.getElementById('presence-tab-people').classList.toggle('active', !live);
  document.getElementById('presence-tab-live').classList.toggle('active', live);
  if (live) startLive(); else stopLive();  // only hold camera streams open while someone is watching
}

// Close the streams when the page is hidden (phone locked, tab switched); reopen on return
document.addEventListener('visibilitychange', () => {
  const liveOn = document.getElementById('presence-tab-live')?.classList.contains('active');
  if (!liveOn) return;
  if (document.hidden) stopLive(); else startLive();
});

export async function askCourage(query) {
  const inputEl = document.getElementById('courage-query-input');
  const q = query || (inputEl ? inputEl.value.trim() : '');
  if (!q) return;

  const respBox = document.getElementById('courage-response-box');
  const audioEl = document.getElementById('courage-audio-player');
  const btn = document.getElementById('courage-ask-btn');

  if (respBox) respBox.innerHTML = '<span style="color:var(--term-accent-gold);">Thinking with biting sarcasm...</span>';
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/presence/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const json = await res.json();
    if (json.ok && json.data) {
      const ans = json.data;
      if (respBox) {
        respBox.innerHTML = `
          <div style="color:var(--term-accent-gold); font-weight:bold; margin-bottom:4px;">💻 COURAGE COMPUTER:</div>
          <div style="font-size:0.88rem; line-height:1.4; color:var(--term-text-bright);">${ans.response}</div>
        `;
      }
      if (ans.audio_base64 && audioEl) {
        audioEl.src = `data:audio/wav;base64,${ans.audio_base64}`;
        audioEl.style.display = 'block';
        audioEl.play().catch(e => console.log('Audio autoplay prevented:', e));
      }
    } else {
      if (respBox) respBox.innerText = `Error: ${json.error || 'Failed to query'}`;
    }
  } catch (e) {
    if (respBox) respBox.innerText = `Error: ${e.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

export async function fetchGardenState() {
  try {
    const res = await fetch('/api/garden/status');
    const json = await res.json();
    if (!json.ok) return null;
    renderGarden(json.data);
    return json.data;
  } catch (e) {
    console.warn('Garden fetch failed:', e);
    return null;
  }
}

export function renderGarden(data) {
  if (!data) return;

  // Battery and rain delay badges
  const battEl = document.getElementById('garden-battery-badge');
  if (battEl) battEl.innerText = `🔋 Battery: ${data.battery_level}%`;

  const rainBtn = document.getElementById('garden-rain-delay-btn');
  if (rainBtn) {
    rainBtn.innerText = data.rain_delay_active ? '[🌧️ RAIN DELAY: ACTIVE]' : '[☀️ RAIN DELAY: OFF]';
    rainBtn.style.color = data.rain_delay_active ? '#38bdf8' : 'var(--term-text-bright)';
  }

  // Render 4 Zones
  const zonesGrid = document.getElementById('garden-zones-grid');
  if (zonesGrid && data.zones) {
    let html = '';
    for (const [key, z] of Object.entries(data.zones)) {
      const isOpen = z.is_open;
      const statusBadge = isOpen
        ? `<span style="color:#22c55e; font-weight:bold; background:rgba(34,197,94,0.15); padding:2px 6px; border-radius:3px; border:1px solid #16a34a;">🌊 OPEN</span>`
        : `<span style="color:var(--term-text-muted); background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:3px; border:1px solid var(--term-border-dim);">CLOSED</span>`;

      html += `
        <div style="background:var(--term-bg); border:1px solid var(--term-border-dim); border-radius:4px; padding:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:bold; color:var(--term-text-bright);">${z.name}</span>
            ${statusBadge}
          </div>
          <div style="font-size:0.72rem; color:var(--term-text-muted); margin:4px 0;">${z.description}</div>
          <div style="font-size:0.70rem; color:var(--term-text-muted); font-family:monospace; margin-bottom:8px;">
            Last: ${z.last_watered ? z.last_watered.replace('T', ' ').substring(0, 16) : 'None'}
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" class="term-cmd-btn" style="flex:1; background:var(--term-accent-blue); color:#fff; font-weight:bold;" onclick="window.controlGardenZone('${key}', 'open', 15)">
              [OPEN 15m]
            </button>
            <button type="button" class="term-cmd-btn" style="color:var(--term-accent-red); font-weight:bold;" onclick="window.controlGardenZone('${key}', 'close')">
              [CLOSE]
            </button>
          </div>
        </div>
      `;
    }
    zonesGrid.innerHTML = html;
  }
}

export async function controlGardenZone(zone, action, durationMinutes = 15) {
  try {
    const res = await fetch('/api/garden/zone/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ zone, action, duration_minutes: durationMinutes })
    });
    const json = await res.json();
    if (json.ok) {
      fetchGardenState();
    } else {
      alert(`Zone command error: ${json.error || 'Failed'}`);
    }
  } catch (e) {
    alert(`Zone command error: ${e.message}`);
  }
}

export async function toggleRainDelay() {
  try {
    const cur = document.getElementById('garden-rain-delay-btn')?.innerText.includes('ACTIVE');
    const res = await fetch('/api/garden/rain_delay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !cur })
    });
    const json = await res.json();
    if (json.ok) {
      fetchGardenState();
    }
  } catch (e) {
    console.error('Rain delay error:', e);
  }
}

export async function emergencyCloseAll() {
  try {
    const res = await fetch('/api/garden/close_all', { method: 'POST' });
    const json = await res.json();
    if (json.ok) {
      fetchGardenState();
    }
  } catch (e) {
    console.error('Emergency close error:', e);
  }
}

// Bind to window for HTML onclick handlers
window.askCourage = askCourage;
window.controlGardenZone = controlGardenZone;
window.toggleRainDelay = toggleRainDelay;
window.emergencyCloseAll = emergencyCloseAll;
window.fetchPresenceState = fetchPresenceState;
window.fetchGardenState = fetchGardenState;
window.showPresenceTab = showPresenceTab;
