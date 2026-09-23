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

export function renderPresence(data) {
  if (!data) return;

  // Render resident & pet locations
  const locContainer = document.getElementById('presence-locations-grid');
  if (locContainer && data.locations) {
    let html = '';
    const locs = data.locations;
    const known = data.known_entities || {};
    const allEntities = [...(known.people || []), ...(known.pets || [])];

    allEntities.forEach(ent => {
      const key = ent.name.toLowerCase();
      const loc = locs[key];
      const isOnline = loc && loc.minutes_ago < 60;
      const statusBadge = isOnline
        ? `<span style="color:#22c55e; font-weight:bold;">🟢 Active (${Math.round(loc.minutes_ago)}m ago)</span>`
        : `<span style="color:var(--term-text-muted); font-weight:bold;">⚪ Inactive (${loc ? Math.round(loc.minutes_ago) + 'm ago' : 'No recent sighting'})</span>`;

      const snapshotImg = loc && loc.snapshot
        ? `<div style="margin-top:6px; border:1px solid var(--term-border-dim); border-radius:3px; overflow:hidden; max-height:90px; background:#000;">
             <img src="/api/presence/snapshot/${loc.snapshot}" alt="${ent.name}" style="width:100%; height:90px; object-fit:cover;" loading="lazy">
           </div>`
        : `<div style="margin-top:6px; height:45px; background:rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; font-size:0.7rem; color:var(--term-text-muted);">No snapshot</div>`;

      html += `
        <div style="background:var(--term-bg); border:1px solid var(--term-border-dim); border-radius:4px; padding:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:bold; color:var(--term-text-bright);">${ent.name}</span>
            <span style="font-size:0.7rem; font-family:monospace;">${statusBadge}</span>
          </div>
          <div style="font-size:0.72rem; color:var(--term-text-muted); margin-top:2px;">${ent.role || ent.breed || ent.species}</div>
          ${snapshotImg}
          <div style="font-size:0.68rem; color:var(--term-text-muted); margin-top:4px;">Last: ${loc ? loc.last_seen : 'Unknown'}</div>
        </div>
      `;
    });
    locContainer.innerHTML = html;
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
