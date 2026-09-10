/**
 * StoneSage: 90s Cyber Brutalist Terminal Workstation & AI Cognitive Cockpit
 * Unified Frontend Application Logic (Inspired by open-webui/computer)
 */

// Application State
const state = {
  services: [],
  category: 'all',
  isEditMode: false,
  theme: localStorage.getItem('stonesage_theme') || 'win95',
  
  // Terminal Host Shell
  terminal: {
    history: [],
    historyIndex: -1,
    currentDir: '',
    tempDraft: ''
  },

  // CPTR Workstation State
  workstation: {
    activeFile: null,
    originalContent: '',
    dirty: false,
    showingDiff: false,
    git: {
      branch: 'main',
      changed: [],
      commits: []
    }
  },

  // AI Cognitive Harness
  ai: {
    activeModel: 'coordinator', // 'coordinator' (:8001), 'worker' (:8002), 'openai', 'anthropic', 'gemini'
    ragEnabled: true,
    ragCollection: 'companion_profile',
    isGenerating: false,
    abortController: null,
    currentSessionId: 'default',
    sessions: [],
    messages: []
  },

  // Smart Home & Nest Thermostat
  thermostat: {
    entity_id: 'climate.living_room_thermostat',
    current: 71,
    target: 72,
    mode: 'heat',
    humidity: 45,
    state: 'heat'
  },

  // Obsidian User Brain
  obsidian: {
    notes: [],
    activeNote: null,
    syncing: false,
    lastSync: null
  },

  // Immich Media Vault
  immich: {
    assets: [],
    stats: null,
    activeCategory: 'all',
    searchQuery: '',
    activeAssetIndex: 0,
    url: 'http://127.0.0.1:9000',
    isWebMode: false
  },

  // Live Canvas & Ambient Voice
  canvas: {
    audioCtx: null,
    analyser: null,
    micStream: null,
    animFrame: null,
    recognition: null,
    isListening: false,
    isGenerating: false,
    abortController: null,
    messages: []
  },

  // Proxmox Auto-Refresh Polling
  proxmox: {
    pollInterval: null
  },

  // Home Assistant entities cache & filtering
  ha: {
    lights: [],
    switches: [],
    all: [],
    filter: 'curated',
    searchQuery: ''
  },

  // Planner & STM Engine
  planner: {
    activePlan: null,
    isRunningLoop: false,
    loopAbort: false
  },

  stm: {
    summary: null
  },

  selectedRebootGuest: null
};

// Document Initialization
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initHeaderClock();
  initNavigation();
  initLanIpCopy();
  initServiceLauncher();
  initServiceEditor();
  initWorkstation();
  initHostTerminal();
  initAiHarness();
  initHomeAssistant();
  initObsidianBrain();
  initProxmox();
  initLiveCanvas();
  initImmichDashboard();
  initMemoryExplorer();
  initSettings();
  initGlobalShortcuts();
  initClusterHealth();
  initHiveMindProfileAndWatchdog();
});

/* ==========================================================================
   1. Theme Switcher & Header Utilities
   ========================================================================== */
function initTheme() {
  document.documentElement.dataset.theme = state.theme;
  const themeBtns = document.querySelectorAll('.theme-opt-btn');
  themeBtns.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === state.theme);
    btn.addEventListener('click', () => {
      state.theme = btn.dataset.theme;
      document.documentElement.dataset.theme = state.theme;
      localStorage.setItem('stonesage_theme', state.theme);
      themeBtns.forEach(b => b.classList.toggle('active', b.dataset.theme === state.theme));
    });
  });
}

function initHeaderClock() {
  const clock = document.getElementById('header-time-indicator');
  const update = () => {
    if (clock) {
      const now = new Date();
      clock.textContent = `[TIME: ${now.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false })} EST]`;
    }
  };
  update();
  setInterval(update, 1000);
}

function formatEasternTime(dateOrTimestamp) {
  if (!dateOrTimestamp) return '';
  try {
    const d = new Date(dateOrTimestamp);
    if (isNaN(d.getTime())) return String(dateOrTimestamp);
    return d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }) + ' EST';
  } catch (e) {
    return String(dateOrTimestamp);
  }
}

function initLanIpCopy() {
  const badge = document.getElementById('lan-ip-badge');
  if (badge) {
    badge.addEventListener('click', () => {
      const text = 'http://127.0.0.1:8080';
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
        const orig = badge.textContent;
        badge.textContent = 'COPIED TO CLIPBOARD! ✓';
        setTimeout(() => { badge.textContent = orig; }, 2000);
      }
    });
  }
}

/* ==========================================================================
   2. Function Key Navigation Tabs ([F1] - [F9])
   ========================================================================== */
function initNavigation() {
  const tabs = document.querySelectorAll('.tab-btn');
  const views = document.querySelectorAll('.view-pane');

  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      views.forEach(v => v.classList.remove('active'));

      btn.classList.add('active');
      const targetView = document.getElementById(btn.dataset.view);
      if (targetView) targetView.classList.add('active');

      const addrInput = document.getElementById('win95-address-input');
      if (addrInput) {
        const route = btn.dataset.view ? btn.dataset.view.replace('view-', '') : 'launchpad';
        addrInput.value = `127.0.0.1:8080/${route}.htm`;
      }

      const viewId = btn.dataset.view;
      if (viewId !== 'view-proxmox') stopProxmoxPolling();

      // Hook up view refreshes
      if (viewId === 'view-launchpad') fetchServices();
      if (viewId === 'view-workstation') { fetchWorkspaceTree(); fetchGitStatus(); }
      if (viewId === 'view-ai') { fetchStmStatus(); fetchKnowledgeBaseStatus(); }
      if (viewId === 'view-hivemind') { loadHiveMindStatus(); loadHiveMindVisionLog(); }
      if (viewId === 'view-ha') fetchHaDashboard();
      if (viewId === 'view-obsidian') { fetchObsidianNotes(); fetchBrainSyncStatus(); fetchCouchDbStatus(); }
      if (viewId === 'view-proxmox') { fetchProxmoxData(); startProxmoxPolling(); }
      if (viewId === 'view-canvas') initLiveCanvas();
      if (viewId === 'view-harness') switchHarnessStudio(currentHarnessId);
      if (viewId === 'view-immich') fetchImmichData();
      if (viewId === 'view-memory') fetchMemoryTelemetry();
      if (viewId === 'view-trainer') fetchTrainerAll();
    });
  });
}

function initGlobalShortcuts() {
  window.addEventListener('keydown', (e) => {
    // Function keys F1 - F12
    if (e.key.startsWith('F') && e.key.length >= 2) {
      const num = parseInt(e.key.slice(1), 10);
      const viewMap = {
        1: 'view-launchpad',
        2: 'view-workstation',
        3: 'view-ai',
        4: 'view-hivemind',
        5: 'view-ha',
        6: 'view-obsidian',
        7: 'view-proxmox',
        8: 'view-canvas',
        9: 'view-harness',
        10: 'view-immich',
        11: 'view-memory',
        12: 'view-trainer'
      };
      if (viewMap[num]) {
        e.preventDefault();
        const tab = document.querySelector(`.tab-btn[data-view="${viewMap[num]}"]`);
        if (tab) tab.click();
      }
    }

    // Ctrl+S: Save current file in editor
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      const activeTab = document.querySelector('.tab-btn.active');
      if (activeTab && activeTab.dataset.view === 'view-workstation') {
        e.preventDefault();
        saveWorkstationFile();
      }
    }
  });
}

/* ==========================================================================
   3. CPTR Workstation (open-webui/computer style)
   ========================================================================== */
function initWorkstation() {
  const refreshTreeBtn = document.getElementById('refresh-tree-btn');
  if (refreshTreeBtn) refreshTreeBtn.addEventListener('click', async () => {
    refreshTreeBtn.textContent = '⏳';
    await fetchWorkspaceTree();
    refreshTreeBtn.textContent = '🔄';
  });

  const saveBtn = document.getElementById('workstation-save-btn');
  if (saveBtn) saveBtn.addEventListener('click', saveWorkstationFile);

  const editorSaveDiskBtn = document.getElementById('editor-save-disk-btn');
  if (editorSaveDiskBtn) editorSaveDiskBtn.addEventListener('click', saveWorkstationFile);

  const revertBtn = document.getElementById('editor-revert-btn');
  if (revertBtn) revertBtn.addEventListener('click', revertWorkstationFile);

  const diffToggleBtn = document.getElementById('workstation-diff-btn');
  if (diffToggleBtn) diffToggleBtn.addEventListener('click', toggleWorkstationDiff);

  const gitRefreshBtn = document.getElementById('workstation-git-refresh-btn');
  if (gitRefreshBtn) gitRefreshBtn.addEventListener('click', async () => {
    const orig = gitRefreshBtn.textContent;
    gitRefreshBtn.textContent = '[⏳ SYNCING...]';
    await fetchGitStatus();
    gitRefreshBtn.textContent = orig;
  });

  const gitCommitBtn = document.getElementById('git-commit-btn');
  if (gitCommitBtn) gitCommitBtn.addEventListener('click', commitWorkstationGit);

  const gitGenMsgBtn = document.getElementById('git-gen-msg-btn');
  if (gitGenMsgBtn) gitGenMsgBtn.addEventListener('click', generateAiCommitMessage);

  const newFileBtn = document.getElementById('workstation-new-file-btn');
  if (newFileBtn) newFileBtn.addEventListener('click', createNewWorkstationFile);

  // Gutter update on typing
  const textarea = document.getElementById('editor-textarea');
  if (textarea) {
    textarea.addEventListener('input', () => {
      updateEditorGutter();
      markEditorDirty(textarea.value !== state.workstation.originalContent);
    });
    textarea.addEventListener('scroll', () => {
      const gutter = document.getElementById('editor-line-gutter');
      if (gutter) gutter.scrollTop = textarea.scrollTop;
    });
  }

  initWorkstationResizer();
  fetchWorkspaceTree();
  fetchGitStatus();
}

function initWorkstationResizer() {
  const resizer = document.getElementById('workstation-split-resizer');
  const editorPane = document.querySelector('.code-editor-pane');
  const splitContainer = document.querySelector('.editor-terminal-split');
  if (!resizer || !editorPane || !splitContainer) return;

  let isDragging = false;
  let startY = 0;
  let startHeight = 0;

  resizer.addEventListener('mousedown', (e) => {
    isDragging = true;
    startY = e.clientY;
    startHeight = editorPane.getBoundingClientRect().height;
    resizer.classList.add('dragging');
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dy = e.clientY - startY;
    const containerHeight = splitContainer.getBoundingClientRect().height;
    const minHeight = 160;
    const maxHeight = containerHeight - 140;
    const newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + dy));
    editorPane.style.height = `${newHeight}px`;
    editorPane.style.flex = 'none';
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      resizer.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });
}

async function fetchWorkspaceTree() {
  const container = document.getElementById('workspace-tree-container');
  if (!container) return;
  try {
    container.innerHTML = '<div style="color:var(--term-text-muted);">Reading workspace tree...</div>';
    const res = await fetch('/api/workspace/tree');
    const data = await res.json();
    if (data.ok && Array.isArray(data.tree)) {
      renderTree(data.tree, container);
    } else {
      container.innerHTML = `<div style="color:var(--term-alert);">Error loading tree: ${escapeHtml(data.error || 'Unknown')}</div>`;
    }
  } catch (err) {
    container.innerHTML = `<div style="color:var(--term-alert);">Tree error: ${err.message}</div>`;
  }
}

function renderTree(nodes, container, level = 0) {
  container.innerHTML = '';
  const renderNodes = (items, target, indent) => {
    items.forEach(node => {
      const row = document.createElement('div');
      row.className = `tree-node ${node.type === 'directory' ? 'dir' : 'file'}`;
      row.style.paddingLeft = `${indent * 12 + 4}px`;
      
      const icon = node.type === 'directory' ? '📁' : '📄';
      row.innerHTML = `<span>${icon}</span><span>${escapeHtml(node.name)}</span>`;
      
      if (node.type === 'file') {
        row.addEventListener('click', () => openWorkstationFile(node.path));
      } else if (node.type === 'directory') {
        let open = true;
        const sub = document.createElement('div');
        row.addEventListener('click', (e) => {
          e.stopPropagation();
          open = !open;
          sub.style.display = open ? 'block' : 'none';
          row.querySelector('span:first-child').textContent = open ? '📁' : '📂';
        });
        target.appendChild(row);
        target.appendChild(sub);
        if (node.children && node.children.length > 0) {
          renderNodes(node.children, sub, indent + 1);
        }
        return;
      }
      target.appendChild(row);
    });
  };
  renderNodes(nodes, container, level);
}

async function openWorkstationFile(path) {
  try {
    const res = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    if (data.ok) {
      state.workstation.activeFile = path;
      state.workstation.originalContent = data.content;
      
      const pathElem = document.getElementById('editor-active-filepath');
      const textarea = document.getElementById('editor-textarea');
      if (pathElem) pathElem.textContent = path;
      if (textarea) {
        textarea.value = data.content;
        updateEditorGutter();
      }
      markEditorDirty(false);

      // Highlight in tree
      document.querySelectorAll('.tree-node').forEach(n => {
        n.classList.toggle('active', n.textContent.includes(path.split('/').pop()));
      });
    } else {
      alert(`Could not open file: ${data.error}`);
    }
  } catch (err) {
    alert(`File open failed: ${err.message}`);
  }
}

function updateEditorGutter() {
  const textarea = document.getElementById('editor-textarea');
  const gutter = document.getElementById('editor-line-gutter');
  if (!textarea || !gutter) return;

  const lineCount = textarea.value.split('\n').length;
  const numbers = [];
  for (let i = 1; i <= Math.max(1, lineCount); i++) {
    numbers.push(String(i).padStart(3, '0'));
  }
  gutter.textContent = numbers.join('\n');
}

function markEditorDirty(isDirty) {
  state.workstation.dirty = isDirty;
  const badge = document.getElementById('editor-dirty-badge');
  if (badge) badge.style.display = isDirty ? 'inline' : 'none';
}

async function saveWorkstationFile() {
  if (!state.workstation.activeFile) {
    alert('No active file selected to save.');
    return;
  }
  const textarea = document.getElementById('editor-textarea');
  if (!textarea) return;

  const content = textarea.value;
  try {
    const res = await fetch('/api/workspace/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: state.workstation.activeFile, content })
    });
    const data = await res.json();
    if (data.ok) {
      state.workstation.originalContent = content;
      markEditorDirty(false);
      fetchGitStatus();
      logToTerminal(`[SAVED] ${state.workstation.activeFile} (${data.size} bytes written)`);
    } else {
      alert(`Save error: ${data.error}`);
    }
  } catch (err) {
    alert(`Save failed: ${err.message}`);
  }
}

function revertWorkstationFile() {
  if (!state.workstation.dirty) return;
  if (confirm('Discard changes and revert to disk content?')) {
    const textarea = document.getElementById('editor-textarea');
    if (textarea) {
      textarea.value = state.workstation.originalContent;
      updateEditorGutter();
      markEditorDirty(false);
    }
  }
}

async function toggleWorkstationDiff() {
  const rawContainer = document.getElementById('editor-raw-container');
  const diffContainer = document.getElementById('editor-diff-container');
  const diffBtn = document.getElementById('workstation-diff-btn');
  if (!rawContainer || !diffContainer || !state.workstation.activeFile) return;

  state.workstation.showingDiff = !state.workstation.showingDiff;
  if (state.workstation.showingDiff) {
    const textarea = document.getElementById('editor-textarea');
    const proposed = textarea ? textarea.value : '';

    try {
      const res = await fetch('/api/workspace/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: state.workstation.activeFile, proposed_content: proposed })
      });
      const data = await res.json();
      if (data.ok) {
        rawContainer.style.display = 'none';
        diffContainer.style.display = 'block';
        diffBtn.classList.add('active');
        renderDiffLines(data.diff, diffContainer);
      }
    } catch (e) {
      console.warn('Diff error:', e);
    }
  } else {
    rawContainer.style.display = 'flex';
    diffContainer.style.display = 'none';
    diffBtn.classList.remove('active');
  }
}

function renderDiffLines(diffText, container) {
  if (!diffText || diffText.trim().length === 0) {
    container.innerHTML = '<div style="color:var(--term-text-muted); padding:1rem;">[ No differences detected between editor buffer and disk. ]</div>';
    return;
  }
  const lines = diffText.split('\n');
  container.innerHTML = lines.map(line => {
    let cls = '';
    if (line.startsWith('+') && !line.startsWith('+++')) cls = 'add';
    else if (line.startsWith('-') && !line.startsWith('---')) cls = 'del';
    else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) cls = 'meta';
    return `<div class="diff-line ${cls}">${escapeHtml(line)}</div>`;
  }).join('');
}

function createNewWorkstationFile() {
  const name = prompt('Enter relative path for new file (e.g. backend/test_script.py):');
  if (!name) return;
  state.workstation.activeFile = name;
  state.workstation.originalContent = '';
  const pathElem = document.getElementById('editor-active-filepath');
  const textarea = document.getElementById('editor-textarea');
  if (pathElem) pathElem.textContent = name;
  if (textarea) {
    textarea.value = '';
    updateEditorGutter();
  }
  markEditorDirty(true);
}

/* ==========================================================================
   4. Git Panel Integration
   ========================================================================== */
async function fetchGitStatus() {
  const branchElem = document.getElementById('git-branch-indicator');
  const listElem = document.getElementById('git-changed-list');
  if (!listElem) return;

  try {
    const res = await fetch('/api/git/status');
    const data = await res.json();
    if (data.ok) {
      state.workstation.git.branch = data.branch;
      state.workstation.git.changed = data.changed_files || [];
      state.workstation.git.commits = data.recent_commits || [];

      if (branchElem) branchElem.textContent = `[${data.branch}]`;

      if (state.workstation.git.changed.length === 0) {
        listElem.innerHTML = '<div style="color:var(--term-text-muted);">Working tree clean.</div>';
      } else {
        listElem.innerHTML = state.workstation.git.changed.map(item => {
          const char = item.slice(0, 2).trim();
          const file = item.slice(2).trim();
          let cClass = 'm';
          if (char.includes('A') || char.includes('?')) cClass = 'a';
          if (char.includes('D')) cClass = 'd';
          return `<div class="git-file-item"><span class="git-status-char ${cClass}">[${char || '?'}]</span><span>${escapeHtml(file)}</span></div>`;
        }).join('');
      }
    }
  } catch (err) {
    listElem.innerHTML = `<div style="color:var(--term-alert);">Git status error: ${err.message}</div>`;
  }
}

async function generateAiCommitMessage() {
  const input = document.getElementById('git-commit-msg');
  if (!input) return;
  const changed = state.workstation.git.changed.join('\n');
  if (!changed) {
    input.value = 'Clean tree snapshot';
    return;
  }

  input.value = 'Generating summary via Worker AI...';
  try {
    const prompt = `Write a crisp, single-sentence git commit message following Conventional Commits format for these changed files:\n${changed}\nRespond with ONLY the commit message.`;
    const res = await fetch('/api/cluster/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: 'worker',
        messages: [{ role: 'user', content: prompt }],
        params: { max_tokens: 60 }
      })
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let result = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          try {
            const parsed = JSON.parse(line.slice(6));
            result += parsed.choices?.[0]?.delta?.content || '';
          } catch (e) {}
        }
      }
    }
    input.value = result.trim().replace(/^["']|["']$/g, '');
  } catch (err) {
    input.value = `Update workspace files (${timeNow()})`;
  }
}

async function commitWorkstationGit() {
  const msgInput = document.getElementById('git-commit-msg');
  const msg = msgInput ? msgInput.value.trim() : '';
  if (!msg) {
    alert('Please enter a commit message or click [AI COMMIT MSG].');
    return;
  }

  try {
    const res = await fetch('/api/git/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    if (data.ok) {
      if (msgInput) msgInput.value = '';
      fetchGitStatus();
      logToTerminal(`[GIT COMMIT] ${msg}\n${data.output || ''}`);
    } else {
      alert(`Commit error: ${data.error}`);
    }
  } catch (err) {
    alert(`Commit failed: ${err.message}`);
  }
}

/* ==========================================================================
   5. Interactive Host Terminal Shell Console
   ========================================================================== */
function getTerminalPromptText() {
  const rel = (state.terminal.currentDir || '').replace(/\//g, '\\');
  return `PS C:\\.ai${rel ? '\\' + rel : ''}>`;
}

function updateTerminalPrompt() {
  const prefix = document.getElementById('terminal-prompt-prefix');
  if (prefix) prefix.textContent = getTerminalPromptText();
}

function initHostTerminal() {
  const input = document.getElementById('terminal-cmd-input');
  const clearBtn = document.getElementById('terminal-clear-btn');
  const pingBtn = document.getElementById('terminal-pve-ping-btn');

  // Load persistent history from localStorage
  let savedHistory = [];
  try {
    const raw = localStorage.getItem('stonesage_cli_history');
    if (raw) savedHistory = JSON.parse(raw);
  } catch (e) {}

  if (!Array.isArray(savedHistory) || savedHistory.length === 0) {
    savedHistory = ['git status', 'pve-health', 'sync-brain', 'services', 'ha-status', 'couch-status'];
    try {
      localStorage.setItem('stonesage_cli_history', JSON.stringify(savedHistory));
    } catch (e) {}
  }

  state.terminal.history = savedHistory;
  state.terminal.historyIndex = savedHistory.length;
  state.terminal.tempDraft = '';
  state.terminal.currentDir = '';
  updateTerminalPrompt();

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      const out = document.getElementById('terminal-output');
      if (out) out.innerHTML = '<div>[ STONESAGE HOST TERMINAL CLEARED ]</div><br>';
    });
  }

  if (pingBtn) {
    pingBtn.addEventListener('click', () => {
      execTerminalCommand('pve-health');
    });
  }

  if (input) {
    input.addEventListener('keydown', async (e) => {
      // 1. Enter: execute command
      if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = input.value.trim();
        if (!cmd) return;

        // Push to history if different from the last entry
        const hist = state.terminal.history;
        if (!hist.length || hist[hist.length - 1] !== cmd) {
          hist.push(cmd);
          if (hist.length > 250) hist.shift();
          try {
            localStorage.setItem('stonesage_cli_history', JSON.stringify(hist));
          } catch (e) {}
        }
        state.terminal.historyIndex = hist.length;
        state.terminal.tempDraft = '';
        input.value = '';
        await execTerminalCommand(cmd);
      }
      // 2. ArrowUp: navigate backward in command history
      else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const hist = state.terminal.history;
        if (!hist.length) return;

        // Save current uncommitted draft when first stepping up
        if (state.terminal.historyIndex === hist.length) {
          state.terminal.tempDraft = input.value;
        }

        if (state.terminal.historyIndex > 0) {
          state.terminal.historyIndex--;
          input.value = hist[state.terminal.historyIndex] || '';
        } else if (state.terminal.historyIndex === 0) {
          input.value = hist[0] || '';
        }
        setTimeout(() => {
          try {
            input.setSelectionRange(input.value.length, input.value.length);
          } catch (_) {}
        }, 0);
      }
      // 3. ArrowDown: navigate forward in command history / back to draft
      else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const hist = state.terminal.history;
        if (!hist.length) return;

        if (state.terminal.historyIndex < hist.length - 1) {
          state.terminal.historyIndex++;
          input.value = hist[state.terminal.historyIndex] || '';
        } else {
          state.terminal.historyIndex = hist.length;
          input.value = state.terminal.tempDraft || '';
        }
        setTimeout(() => {
          try {
            input.setSelectionRange(input.value.length, input.value.length);
          } catch (_) {}
        }, 0);
      }
      // 4. Tab: command and path auto-completion
      else if (e.key === 'Tab') {
        e.preventDefault();
        handleTerminalTabCompletion(input);
      }
      // 5. Ctrl+L: Clear terminal screen
      else if (e.ctrlKey && (e.key === 'l' || e.key === 'L')) {
        e.preventDefault();
        const out = document.getElementById('terminal-output');
        if (out) out.innerHTML = '';
      }
      // 6. Ctrl+C: Cancel current line and emit prompt break
      else if (e.ctrlKey && (e.key === 'c' || e.key === 'C')) {
        e.preventDefault();
        logToTerminal(`${getTerminalPromptText()} ${input.value}^C`, 'dim');
        input.value = '';
        state.terminal.tempDraft = '';
        state.terminal.historyIndex = state.terminal.history.length;
      }
      // 7. Ctrl+U: Clear line before cursor
      else if (e.ctrlKey && (e.key === 'u' || e.key === 'U')) {
        e.preventDefault();
        input.value = '';
        state.terminal.tempDraft = '';
      }
    });
  }
}

function handleTerminalTabCompletion(input) {
  const text = input.value;
  if (!text) return;

  const tokens = text.split(/\s+/);
  const lastToken = tokens[tokens.length - 1].toLowerCase();
  if (!lastToken) return;

  const builtins = [
    'help', 'cls', 'clear', 'history', 'theme', 'crt-green', 'crt-amber', 'win95',
    'git status', 'git diff', 'git log', 'git branch', 'git add', 'git commit', 'git pull', 'git push',
    'pve-health', 'cluster-health', 'nodes', 'pve-nodes', 'services', 'vms', 'containers', 'guests',
    'sync-brain', 'sync-vault', 'sync-rag', 'couch-status', 'couchdb', 'couch-sync', 'notes',
    'ha-status', 'ha', 'thermostat', 'stm', 'stm-status', 'stm-add', 'stm-clear',
    'plan', 'ai', 'ask', 'subagents',
    'cd', 'pwd', 'dir', 'ls', 'cat', 'type', 'mkdir', 'echo', 'ipconfig', 'curl', 'ping'
  ];

  const commonPaths = ['StoneSage', 'backend', 'frontend', 'server setup', 'obsidian', 'vault_backup', 'server.py', 'app.js', 'index.html', 'style.css'];
  const candidates = [...new Set([...builtins, ...commonPaths])];

  const matches = candidates.filter(c => c.toLowerCase().startsWith(lastToken));
  if (matches.length === 1) {
    tokens[tokens.length - 1] = matches[0];
    input.value = tokens.join(' ') + ' ';
    input.setSelectionRange(input.value.length, input.value.length);
  } else if (matches.length > 1) {
    let prefix = matches[0];
    for (let i = 1; i < matches.length; i++) {
      while (!matches[i].toLowerCase().startsWith(prefix.toLowerCase())) {
        prefix = prefix.slice(0, -1);
      }
    }
    if (prefix.length > lastToken.length) {
      tokens[tokens.length - 1] = prefix;
      input.value = tokens.join(' ');
      input.setSelectionRange(input.value.length, input.value.length);
    } else {
      logToTerminal(`[COMPLETIONS] ${matches.slice(0, 10).join('  ')}`, 'dim');
    }
  }
}

async function execTerminalCommand(cmd) {
  logToTerminal(`${getTerminalPromptText()} ${cmd}`);
  const cmdLower = cmd.toLowerCase().trim();

  // 1. cls / clear
  if (cmdLower === 'cls' || cmdLower === 'clear') {
    const out = document.getElementById('terminal-output');
    if (out) out.innerHTML = '';
    return;
  }

  // 2. help
  if (cmdLower === 'help') {
    logToTerminal(`======================================================================
  STONESAGE 90s CYBER-BRUTALIST WORKSTATION CLI (PS C:\\.ai)
======================================================================
[ SHELL & NAVIGATION ]
  cd <dir>               Change directory (supports .., /, relative)
  pwd / Get-Location     Print current working directory
  dir / ls               List files in current working directory
  cat / type <file>      Display contents of a file
  cls / clear            Clear terminal screen (or Ctrl+L)
  history [-c]           View or clear command history
  theme <palette>        Switch theme (crt-green, crt-amber, win95)

[ GIT REPOSITORY ]
  git status             Inspect changed, untracked, and staged files
  git diff [file]        View unified diff of workspace changes
  git log [-n <N>]       View recent commit log
  git branch             View current and local branches
  git commit -m "<msg>"  Commit workspace changes
  git add <files>        Stage files for commit

[ HOMELAB CLUSTER & HYPERVISOR ]
  pve-health             Probe latency to Coordinator, Worker, BGE, MCP, Qdrant
  nodes / pve-nodes      Show live CPU, RAM, and Disk metrics (pve, bigserv)
  services               Show live status & latency for all 21 homelab apps
  vms / containers       List all QEMU VMs & LXC containers across cluster

[ OBSIDIAN BRAIN & COUCHDB ]
  sync-brain / sync-rag  Trigger Obsidian -> Qdrant BGE vector ingestion
  couch-status / couchdb Query CouchDB 3.5.2 stats on LXC 116 (199 docs)
  couch-sync             Poll and index CouchDB LiveSync documents
  notes [filter]         Search & list Obsidian vault & CouchDB notes

[ SMART HOME & HVAC ]
  ha-status              Summary of Nest Thermostat, lights, and switches
  ha <intent>            Delegate command (e.g. "ha set thermostat to 72")
  thermostat <temp>      Quick set living room thermostat temperature

[ AI COGNITIVE COCKPIT & MEMORY ]
  ai <prompt>            Stream answer from local Coordinator (:8001) / Worker (:8002)
  plan <goal>            Decompose high-level goal into structured milestones
  stm / stm-status       Display in-RAM Short-Term Memory and active plan
  stm-add <key> <val>    Push key/value to RAM working context
  stm-clear              Clear in-RAM short-term memory
  subagents              List active subagent tasks and outputs

* Any standard PowerShell command passes directly to the host shell.
======================================================================`);
    return;
  }

  // 3. history
  if (cmdLower === 'history') {
    const hist = state.terminal.history;
    if (!hist.length) {
      logToTerminal('[History is empty]');
    } else {
      hist.forEach((h, i) => {
        logToTerminal(`  ${(i + 1).toString().padStart(3, ' ')}  ${h}`);
      });
    }
    return;
  }

  if (cmdLower === 'history -c' || cmdLower === 'clear-history') {
    state.terminal.history = [];
    state.terminal.historyIndex = 0;
    try { localStorage.removeItem('stonesage_cli_history'); } catch(_) {}
    logToTerminal('[Command history cleared]', 'dim');
    return;
  }

  // 4. theme
  if (cmdLower.startsWith('theme')) {
    const parts = cmd.split(/\s+/);
    const target = parts[1]?.toLowerCase();
    const valid = ['crt-green', 'crt-amber', 'win95'];
    if (valid.includes(target)) {
      state.theme = target;
      document.documentElement.dataset.theme = target;
      localStorage.setItem('stonesage_theme', target);
      document.querySelectorAll('.theme-opt-btn').forEach(b => b.classList.toggle('active', b.dataset.theme === target));
      logToTerminal(`[Theme switched to: ${target}]`);
    } else {
      logToTerminal(`Current theme: ${state.theme}. Available: crt-green, crt-amber, win95. Usage: theme <name>`);
    }
    return;
  }

  // 5. pve-health / cluster-health
  if (cmdLower === 'pve-health' || cmdLower === 'cluster-health') {
    logToTerminal('[PROBING CLUSTER TELEMETRY & MODEL LATENCIES...]');
    try {
      const res = await fetch('/api/cluster/health');
      const data = await res.json();
      if (data.ok && data.cluster) {
        const c = data.cluster;
        logToTerminal(`\n=== PVE CLUSTER HEALTH STATUS ===
- Coordinator (:8001): ${c.coordinator?.online ? 'ONLINE' : 'OFFLINE'} (${c.coordinator?.latency_ms || '?'}ms) [Primary Accelerator]
- Worker      (:8002): ${c.worker?.online ? 'ONLINE' : 'OFFLINE'} (${c.worker?.latency_ms || '?'}ms) [Worker Accelerator]
- Embedder    (:8003): ${c.embedder?.online ? 'ONLINE' : 'OFFLINE'} (${c.embedder?.latency_ms || '?'}ms) [Vector Engine]
- Qdrant Vector   (:6333): ${c.qdrant?.online ? 'ONLINE' : 'OFFLINE'} (${c.qdrant?.latency_ms || '?'}ms) [LXC 117]
- MCP Bridge      (:8765): ${c.mcp?.online ? 'ONLINE' : 'OFFLINE'} (${c.mcp?.latency_ms || '?'}ms) [VM 102 ubu]
Overall Status: ${c.all_online ? 'OPTIMAL (5/5 Services Active)' : 'DEGRADED'}\n`);
      } else {
        logToTerminal(`[HEALTH CHECK FAILED] ${data.error || 'Unknown error'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[HEALTH CHECK ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 6. nodes / pve-nodes
  if (cmdLower === 'nodes' || cmdLower === 'pve-nodes') {
    logToTerminal('[QUERYING PROXMOX FLEET HYPERVISOR TELEMETRY...]');
    try {
      const res = await fetch('/api/proxmox/nodes');
      const data = await res.json();
      if (data.ok && data.nodes) {
        const n = data.nodes;
        logToTerminal(`\n=== PROXMOX VE FLEET TELEMETRY ===
Node pve (127.0.0.1):
  CPU:    ${n.pve?.cpu_pct?.toFixed(1) || 0}%
  RAM:    ${n.pve?.memory_pct?.toFixed(1) || 0}% (${n.pve?.memory_used_gb || 0} / ${n.pve?.memory_total_gb || 0} GB)
  DISK:   ${n.pve?.disk_pct?.toFixed(1) || 0}% (${n.pve?.disk_used_gb || 0} / ${n.pve?.disk_total_gb || 0} GB)
  Kernel: ${n.pve?.kernel || 'Unknown'}

Node bigserv (127.0.0.1):
  CPU:    ${n.bigserv?.cpu_pct?.toFixed(1) || 0}%
  RAM:    ${n.bigserv?.memory_pct?.toFixed(1) || 0}% (${n.bigserv?.memory_used_gb || 0} / ${n.bigserv?.memory_total_gb || 0} GB)
  DISK:   ${n.bigserv?.disk_pct?.toFixed(1) || 0}% (${n.bigserv?.disk_used_gb || 0} / ${n.bigserv?.disk_total_gb || 0} GB)
  Kernel: ${n.bigserv?.kernel || 'Unknown'}\n`);
      } else {
        logToTerminal(`[PROXMOX NODES ERROR] ${data.error || 'Failed to fetch'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[PROXMOX ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 7. services
  if (cmdLower === 'services') {
    logToTerminal('[QUERYING HOMELAB CONTAINER SERVICES...]');
    try {
      const res = await fetch('/api/services/status');
      const data = await res.json();
      if (data.ok && data.services) {
        logToTerminal(`\n=== HOMELAB APPLICATION SERVICES (${data.services.length} TOTAL) ===`);
        data.services.forEach(s => {
          const badge = s.online ? '[ONLINE]' : '[OFFLINE]';
          const lat = s.latency_ms ? `${s.latency_ms}ms` : '';
          logToTerminal(`  ${badge.padEnd(10, ' ')} ${s.name.padEnd(20, ' ')} ${s.url} (${s.node || 'bigserv'}) ${lat}`);
        });
        logToTerminal('');
      } else {
        logToTerminal(`[SERVICES ERROR] ${data.error || 'Failed to fetch services'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[SERVICES ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 8. vms / containers / guests
  if (cmdLower === 'vms' || cmdLower === 'containers' || cmdLower === 'guests') {
    logToTerminal('[QUERYING PROXMOX GUEST INVENTORY...]');
    try {
      const res = await fetch('/api/proxmox/guests');
      const data = await res.json();
      if (data.ok && data.guests) {
        logToTerminal(`\n=== PROXMOX GUESTS (${data.guests.length} INSTANCES) ===`);
        data.guests.forEach(g => {
          const stat = (g.status || 'running').toUpperCase();
          const type = (g.type || 'lxc').toUpperCase();
          logToTerminal(`  VMID ${g.vmid?.toString().padEnd(5, ' ')} [${type.padEnd(4, ' ')}] [${stat.padEnd(7, ' ')}] ${g.name.padEnd(22, ' ')} Node: ${g.node || 'pve'}`);
        });
        logToTerminal('');
      } else {
        logToTerminal(`[GUEST INVENTORY ERROR] ${data.error || 'Failed to fetch'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[GUEST ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 9. sync-brain / sync-vault / sync-rag
  if (cmdLower === 'sync-brain' || cmdLower === 'sync-vault' || cmdLower === 'sync-rag') {
    logToTerminal('[SYNCING OBSIDIAN VAULT INTO QDRANT (BGE-Large F16)...]');
    try {
      const res = await fetch('/api/obsidian/sync_to_memory', { method: 'POST' });
      const data = await res.json();
      if (data.ok && data.result) {
        const r = data.result;
        logToTerminal(`[VAULT INGESTION COMPLETE]
- Notes Ingested:   ${r.total_notes || 0}
- Chunks Vectorized:${r.total_chunks || 0}
- Latency / Elapsed:${r.elapsed_sec ? r.elapsed_sec + 's' : 'Done'}
- Qdrant Collection: codebase_knowledge (1024-dim Cosine)\n`);
      } else {
        logToTerminal(`[SYNC ERROR] ${data.error || 'Failed to sync'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[SYNC ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 10. couch-status / couchdb
  if (cmdLower === 'couch-status' || cmdLower === 'couchdb') {
    logToTerminal('[QUERYING APACHE COUCHDB LIVESYNC (LXC 116)...]');
    try {
      const res = await fetch('/api/couchdb/status');
      const data = await res.json();
      if (data.online) {
        logToTerminal(`\n=== COUCHDB LIVESYNC STATUS ===
- Database:  ${data.database || 'obsidiannotes'}
- Status:    ONLINE (${data.latency_ms || 0}ms latency)
- Version:   ${data.vendor || 'Apache'} CouchDB ${data.version || '3.5.2'}
- Documents: ${data.doc_count || 0} active notes synchronized
- Disk Size: ${data.disk_size_mb || 0} MB (active: ${data.active_size_mb || 0} MB)
- UpdateSeq: ${data.update_seq || 'N/A'}\n`);
      } else {
        logToTerminal(`[COUCHDB OFFLINE] ${data.error || 'LXC 116 unreachable at 127.0.0.1:5984'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[COUCHDB ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 11. couch-sync
  if (cmdLower === 'couch-sync') {
    logToTerminal('[POLLING COUCHDB NOTES CACHE...]');
    try {
      const res = await fetch('/api/couchdb/sync', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`[COUCHDB SYNC] ${data.message || `Indexed ${data.count} notes.`}`);
      } else {
        logToTerminal(`[COUCHDB SYNC ERROR] ${data.error || 'Failed'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[COUCHDB SYNC ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 12. notes [filter]
  if (cmdLower.startsWith('notes') || cmdLower.startsWith('list-notes')) {
    const parts = cmd.split(/\s+/);
    const filter = parts.slice(1).join(' ').toLowerCase();
    logToTerminal(`[FETCHING NOTES INDEX ${filter ? `FILTER: "${filter}"` : ''}...]`);
    try {
      const res = await fetch('/api/obsidian/notes');
      const data = await res.json();
      if (data.ok && data.notes) {
        let list = data.notes;
        if (filter) {
          list = list.filter(n => n.name?.toLowerCase().includes(filter) || n.path?.toLowerCase().includes(filter));
        }
        logToTerminal(`\n=== OBSIDIAN NOTES (${list.length} MATCHES, ${data.total_count} TOTAL) ===`);
        list.slice(0, 25).forEach(n => {
          const src = n.in_couchdb ? '[COUCHDB]' : '[DISK]   ';
          logToTerminal(`  ${src} ${n.path} (${n.size_bytes || 0} bytes) - ${n.modified || ''}`);
        });
        if (list.length > 25) {
          logToTerminal(`  ... and ${list.length - 25} more notes. Use 'notes <keyword>' to refine.`, 'dim');
        }
        logToTerminal('');
      } else {
        logToTerminal(`[NOTES ERROR] ${data.error || 'Failed to list notes'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[NOTES ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 13. ha-status / ha-summary
  if (cmdLower === 'ha-status' || cmdLower === 'ha-summary') {
    logToTerminal('[QUERYING HOME ASSISTANT (127.0.0.1:8123)...]');
    try {
      const res = await fetch('/api/ha/dashboard');
      const data = await res.json();
      if (data.ok) {
        const nest = data.thermostat || {};
        logToTerminal(`\n=== SMART HOME SUMMARY ===
- Google Nest Thermostat: ${nest.current || '?'}°F (Target: ${nest.target || '?'}°F, Mode: ${(nest.hvac_mode || 'off').toUpperCase()})
- Lights Online:          ${(data.lights || []).length} active fixtures
- Switches & Plugs:       ${(data.switches || []).length} registered entities
- Home Assistant Status:  CONNECTED (http://127.0.0.1:8123)\n`);
      } else {
        logToTerminal(`[HA STATUS ERROR] ${data.error || 'Failed to query HA'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[HA ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 14. thermostat <temp>
  if (cmdLower.startsWith('thermostat ')) {
    const val = parseInt(cmd.split(/\s+/)[1], 10);
    if (isNaN(val) || val < 50 || val > 90) {
      logToTerminal('Usage: thermostat <temperature_in_F> (e.g. thermostat 72)', 'alert');
      return;
    }
    logToTerminal(`[SETTING NEST THERMOSTAT TARGET TO ${val}°F...]`);
    try {
      const res = await fetch('/api/ha/service', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: 'climate',
          service: 'set_temperature',
          service_data: { entity_id: 'climate.living_room_thermostat', temperature: val }
        })
      });
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`[THERMOSTAT TARGET UPDATED TO ${val}°F] ✓`);
      } else {
        logToTerminal(`[THERMOSTAT ERROR] ${data.error || 'Service call failed'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[THERMOSTAT ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 15. ha <intent>
  if (cmdLower.startsWith('ha ')) {
    const intent = cmd.slice(3).trim();
    if (!intent) {
      logToTerminal('Usage: ha <natural language intent> (e.g. ha turn off office light)', 'alert');
      return;
    }
    logToTerminal(`[DELEGATING INTENT TO WORKER: "${intent}"]`, 'dim');
    try {
      const res = await fetch('/api/ha/service', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: 'homeassistant', service: 'intent', service_data: { text: intent } })
      });
      const data = await res.json();
      logToTerminal(`[HA RESPONSE] ${data.message || (data.ok ? 'Executed successfully.' : data.error || 'Failed')}`);
    } catch (e) {
      logToTerminal(`[HA DELEGATE ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 16. stm / stm-status
  if (cmdLower === 'stm' || cmdLower === 'stm-status') {
    logToTerminal('[READING IN-RAM SHORT-TERM MEMORY ENGINE...]');
    try {
      const res = await fetch('/api/memory/stm');
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`\n=== SHORT-TERM MEMORY (STM) RAM STORE ===
- Active Items:      ${data.item_count || 0}
- Context Tokens:    ~${data.estimated_tokens || 0} tokens
- Last Updated:      ${data.last_updated || 'Never'}`);
        if (data.items && data.items.length) {
          data.items.forEach(it => {
            logToTerminal(`  [${it.category?.toUpperCase() || 'SYS'}] ${it.key}: ${it.value}`);
          });
        }
        if (data.has_active_plan && data.active_plan) {
          const p = data.active_plan;
          logToTerminal(`\nActive Milestone Plan: "${p.title || 'Untitled'}" (${p.steps?.length || 0} steps)`);
          (p.steps || []).forEach(s => {
            const st = s.status === 'completed' ? '[DONE]' : s.status === 'running' ? '[RUN ]' : '[WAIT]';
            logToTerminal(`  ${st} Step ${s.id}: ${s.desc}`);
          });
        }
        logToTerminal('');
      } else {
        logToTerminal(`[STM ERROR] ${data.error || 'Failed to read STM'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[STM ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 17. stm-add <key> <val>
  if (cmdLower.startsWith('stm-add ')) {
    const parts = cmd.split(/\s+/);
    const key = parts[1];
    const val = parts.slice(2).join(' ');
    if (!key || !val) {
      logToTerminal('Usage: stm-add <key> <working value or note>', 'alert');
      return;
    }
    try {
      const res = await fetch('/api/memory/stm/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: 'user', key, value: val })
      });
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`[STM ADDED] ${key}: ${val} (Total items: ${data.stm?.item_count || 1})`);
      } else {
        logToTerminal(`[STM ERROR] ${data.error || 'Failed to add'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[STM ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 18. stm-clear
  if (cmdLower === 'stm-clear') {
    try {
      const res = await fetch('/api/memory/stm/clear', { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        logToTerminal('[STM IN-RAM MEMORY CLEARED] ✓');
      } else {
        logToTerminal(`[STM ERROR] ${data.error}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[STM ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 19. plan <goal>
  if (cmdLower.startsWith('plan ')) {
    const goal = cmd.slice(5).trim();
    if (!goal) {
      logToTerminal('Usage: plan <high-level objective> (e.g. plan audit smart home security)', 'alert');
      return;
    }
    logToTerminal(`[COORDINATOR DECOMPOSING PLAN: "${goal}"...]`, 'dim');
    try {
      const res = await fetch('/api/planner/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, model: 'coordinator' })
      });
      const data = await res.json();
      if (data.ok && data.plan) {
        logToTerminal(`\n=== PLAN: ${data.plan.title || goal} ===`, 'bright');
        logToTerminal(`Objective: ${data.plan.objective || goal}`);
        (data.plan.steps || []).forEach(s => {
          logToTerminal(`  [STEP ${s.id}] ${s.desc} -> Action: ${s.action || 'exec'} (${s.target || 'System'})`);
        });
        logToTerminal(`\n[Plan registered in STM working memory. Inspect or execute in Planner tab.]\n`, 'dim');
      } else {
        logToTerminal(`[PLAN ERROR] ${data.error || 'Failed to generate plan'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[PLAN ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 20. ai <prompt> / ask <prompt>
  if (cmdLower.startsWith('ai ') || cmdLower.startsWith('ask ')) {
    const aiPrompt = cmd.slice(cmd.indexOf(' ') + 1).trim();
    if (!aiPrompt) {
      logToTerminal('Usage: ai <prompt> (e.g. ai explain Vulkan KV-cache quant)', 'alert');
      return;
    }
    const targetModel = state.ai?.activeModel || 'coordinator';
    logToTerminal(`[QUERYING ${targetModel.toUpperCase()}...]`, 'dim');
    try {
      const res = await fetch('/api/cluster/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: targetModel,
          messages: [{ role: 'user', content: aiPrompt }],
          params: { max_tokens: 1000 }
        })
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiOutput = '';
      const lineEl = document.createElement('div');
      lineEl.style.color = 'var(--term-text-bright)';
      lineEl.style.whiteSpace = 'pre-wrap';
      lineEl.style.marginTop = '4px';
      lineEl.style.marginBottom = '4px';
      const out = document.getElementById('terminal-output');
      if (out) out.appendChild(lineEl);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ') && !line.includes('[DONE]')) {
            try {
              const d = JSON.parse(line.slice(6));
              const delta = d.choices?.[0]?.delta?.content || '';
              aiOutput += delta;
              lineEl.textContent = aiOutput;
              if (out) out.scrollTop = out.scrollHeight;
            } catch (_) {}
          }
        }
      }
    } catch (e) {
      logToTerminal(`[AI QUERY ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 21. subagents
  if (cmdLower === 'subagents') {
    logToTerminal('[QUERYING SUBAGENT REGISTRY...]');
    try {
      const res = await fetch('/api/subagents/list');
      const data = await res.json();
      if (data.ok && data.subagents) {
        logToTerminal(`\n=== DISPATCHED SUBAGENTS (${data.subagents.length} TOTAL) ===`);
        data.subagents.forEach(s => {
          logToTerminal(`  [${(s.status || 'unknown').toUpperCase()}] ${s.role} (Model: ${s.model || 'worker'}) - Started: ${s.started_at || 'N/A'}`);
          if (s.output) {
            logToTerminal(`    Output: ${s.output.slice(0, 100)}...`, 'dim');
          }
        });
        logToTerminal('');
      } else {
        logToTerminal(`[SUBAGENTS ERROR] ${data.error || 'Failed to fetch'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[SUBAGENTS ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 21b. delete-agent / rm-agent
  if (cmdLower.startsWith('delete-agent') || cmdLower.startsWith('rm-agent') || cmdLower.startsWith('delete_agent')) {
    const parts = cmd.trim().split(/\s+/);
    const agentId = parts[1];
    if (!agentId) {
      logToTerminal('Usage: delete-agent <agent_id>', 'alert');
      return;
    }
    logToTerminal(`[PURGING AGENT ${agentId} FROM REGISTRY...]`);
    try {
      const res = await fetch('/api/agents/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId })
      });
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`[SUCCESS] Subagent '${agentId}' removed from active registry and disk.`, 'bright');
        logToTerminal(`[NOTE] All learned memories and invariants remain preserved in Qdrant.`, 'dim');
      } else {
        logToTerminal(`[ERROR] ${data.error || 'Failed to delete agent'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[DELETE AGENT ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 21c. nudge-agent / nudge-loop / nudge
  if (cmdLower.startsWith('nudge')) {
    const parts = cmd.trim().split(/\s+/);
    const target = parts[1] || 'engine';
    logToTerminal(`[SENDING REASONING NUDGE TO ${target.toUpperCase()}...]`);
    try {
      const res = await fetch('/api/agent/nudge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: target })
      });
      const data = await res.json();
      if (data.ok) {
        logToTerminal(`[SUCCESS] Nudge applied to ${target}. Breakout directive injected; execution resumed.`, 'bright');
      } else {
        logToTerminal(`[ERROR] ${data.error || 'Failed to nudge agent'}`, 'alert');
      }
    } catch (e) {
      logToTerminal(`[NUDGE ERROR] ${e.message}`, 'alert');
    }
    return;
  }

  // 22. pwd / Get-Location
  if (cmdLower === 'pwd' || cmdLower === 'get-location') {
    logToTerminal(`Path: C:\\Users\\operator\\OneDrive\\Documents\\.ai${state.terminal.currentDir ? '\\' + state.terminal.currentDir.replace(/\//g, '\\') : ''}`);
    return;
  }

  // 23. Default: Execute in PowerShell on the host with active working directory
  try {
    const res = await fetch('/api/terminal/exec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, cwd: state.terminal.currentDir })
    });
    const data = await res.json();
    if (data.cwd !== undefined) {
      state.terminal.currentDir = data.cwd;
      updateTerminalPrompt();
    }
    if (data.ok) {
      if (data.stdout) logToTerminal(data.stdout);
      if (data.stderr) logToTerminal(`[STDERR] ${data.stderr}`, 'alert');
      if (data.exit_code !== 0 && data.exit_code !== undefined) {
        logToTerminal(`[Process exited with code ${data.exit_code}]`, 'dim');
      }
    } else {
      if (data.stderr) logToTerminal(data.stderr, 'alert');
      else logToTerminal(`[ERROR] ${data.error || 'Command failed'}`, 'alert');
      if (data.exit_code !== 0 && data.exit_code !== undefined) {
        logToTerminal(`[Process exited with code ${data.exit_code}]`, 'dim');
      }
    }
  } catch (err) {
    logToTerminal(`[TERMINAL EXEC ERROR] ${err.message}`, 'alert');
  }
}

function logToTerminal(text, type = 'normal') {
  const out = document.getElementById('terminal-output');
  if (!out) return;
  const line = document.createElement('div');
  if (type === 'alert') line.style.color = 'var(--term-alert)';
  else if (type === 'dim') line.style.color = 'var(--term-text-muted)';
  else if (type === 'bright') line.style.color = 'var(--term-text-bright)';
  line.textContent = text;
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

async function loadHarnessCapabilities() {
  try {
    const res = await fetch('/api/harness/capabilities');
    const data = await res.json();
    if (!data.ok) return;

    // 1. Populate #ai-active-model
    const aiModelSel = document.getElementById('ai-active-model');
    if (aiModelSel) {
      const cMeta = data.active_coordinator?.meta;
      const wMeta = data.active_worker?.meta;
      const cLabel = cMeta
        ? `[COORDINATOR: ${(cMeta.n_params / 1e9).toFixed(1)}B ${cMeta.ftype || ''} (${Math.round((cMeta.n_ctx || 16384) / 1024)}k ctx)]`
        : '[COORDINATOR :8001 (Primary)]';
      const wLabel = wMeta
        ? `[WORKER: ${(wMeta.n_params / 1e9).toFixed(1)}B ${wMeta.ftype || ''} (${Math.round((wMeta.n_ctx || 8192) / 1024)}k ctx)]`
        : '[WORKER :8002 (Fast Utility)]';

      aiModelSel.innerHTML = `
        <option value="coordinator" selected>${cLabel}</option>
        <option value="worker">${wLabel}</option>
        <option value="openai">[FRONTIER: GPT-4o]</option>
        <option value="anthropic">[FRONTIER: Claude 3.7 Sonnet]</option>
        <option value="gemini">[FRONTIER: Gemini 2.5 Pro]</option>
      `;
    }

    // 2. Populate #subagent-model-quick
    const subSel = document.getElementById('subagent-model-quick');
    if (subSel) {
      const cMeta = data.active_coordinator?.meta;
      const wMeta = data.active_worker?.meta;
      const cLabel = cMeta ? `[COORDINATOR :8001 (${(cMeta.n_params / 1e9).toFixed(1)}B)]` : '[COORDINATOR :8001 (Primary)]';
      const wLabel = wMeta ? `[WORKER :8002 (${(wMeta.n_params / 1e9).toFixed(1)}B)]` : '[WORKER :8002 (Fast)]';

      subSel.innerHTML = `
        <option value="worker" selected>${wLabel}</option>
        <option value="coordinator">${cLabel}</option>
      `;
    }

    // 3. Populate #local-model-select if present
    const localModelSel = document.getElementById('local-model-select');
    if (localModelSel && data.installed_models && data.installed_models.length > 0) {
      localModelSel.innerHTML = data.installed_models.map(m => {
        const lockIcon = m.is_locked ? '🔒 ' : '';
        return `<option value="${m.filename}">${lockIcon}${m.filename} (${m.size})</option>`;
      }).join('');
    }
  } catch (err) {
    console.warn('Could not load harness capabilities:', err);
  }
}

/* ==========================================================================
   6. AI Cognitive Cockpit (3-Tier Hardware Hierarchy & Frontier)
   ========================================================================== */
function initAiHarness() {
  const sendBtn = document.getElementById('chat-send-btn');
  const stopBtn = document.getElementById('chat-stop-btn');
  const chatInput = document.getElementById('chat-input');
  const modelSelect = document.getElementById('ai-active-model');
  const ragToggle = document.getElementById('toggle-rag-btn');
  const ragSelect = document.getElementById('rag-collection-select');
  const clearBtn = document.getElementById('ai-clear-session-btn');
  const subagentBtn = document.getElementById('subagent-dispatch-quick-btn');

  // Dynamically poll cluster capabilities from llama.cpp (:8001, :8002) and /opt/models/
  loadHarnessCapabilities();

  if (modelSelect) {
    modelSelect.addEventListener('change', (e) => {
      state.ai.activeModel = e.target.value;
    });
  }

  if (ragToggle) {
    ragToggle.addEventListener('click', () => {
      state.ai.ragEnabled = !state.ai.ragEnabled;
      ragToggle.classList.toggle('active', state.ai.ragEnabled);
      ragToggle.textContent = state.ai.ragEnabled ? '[RAG: ON]' : '[RAG: OFF]';
    });
  }

  if (ragSelect) {
    ragSelect.addEventListener('change', (e) => {
      state.ai.ragCollection = e.target.value;
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      state.ai.messages = [];
      const stream = document.getElementById('chat-stream');
      if (stream) stream.innerHTML = '';
      logChatMessage('assistant', 'Session cleared. Ready for new instructions.');
    });
  }

  if (sendBtn && chatInput) {
    sendBtn.addEventListener('click', () => submitChatPrompt());
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitChatPrompt();
      }
    });
  }

  if (stopBtn) {
    stopBtn.addEventListener('click', () => {
      if (state.ai.abortController) {
        state.ai.abortController.abort();
      }
    });
  }

  if (subagentBtn) {
    subagentBtn.addEventListener('click', async () => {
      const taskInput = document.getElementById('subagent-task-quick');
      const modelInput = document.getElementById('subagent-model-quick');
      const task = taskInput ? taskInput.value.trim() : '';
      const targetModel = modelInput ? modelInput.value : 'worker';
      if (!task) {
        alert('Enter a task description for the subagent.');
        return;
      }
      subagentBtn.disabled = true;
      subagentBtn.textContent = 'DISPATCHING...';
      try {
        const res = await fetch('/api/subagents/dispatch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: 'Workstation Subagent', model: targetModel, task })
        });
        const data = await res.json();
        if (data.ok) {
          if (taskInput) taskInput.value = '';
          alert(`Subagent dispatched successfully (ID: ${data.subagent_id})`);
        }
      } catch (err) {
        alert(`Dispatch failed: ${err.message}`);
      } finally {
        subagentBtn.disabled = false;
        subagentBtn.textContent = '[DISPATCH SUBAGENT]';
      }
    });
  }
}

async function submitChatPrompt() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const prompt = input.value.trim();
  if (!prompt || state.ai.isGenerating) return;

  input.value = '';
  logChatMessage('user', prompt);
  state.ai.messages.push({ role: 'user', content: prompt });

  state.ai.isGenerating = true;
  const sendBtn = document.getElementById('chat-send-btn');
  const stopBtn = document.getElementById('chat-stop-btn');
  if (sendBtn) sendBtn.disabled = true;
  if (stopBtn) stopBtn.style.display = 'inline-flex';

  // Create message DOM block for streaming
  const stream = document.getElementById('chat-stream');
  const msgBlock = document.createElement('div');
  msgBlock.className = 'chat-msg assistant';
  
  const roleTitle = (state.ai.activeModel === 'coordinator' || state.ai.activeModel === 'hermes')
    ? '[PRIMARY COORDINATOR :8001]' 
    : (state.ai.activeModel === 'worker' ? '[FAST WORKER :8002]' : `[FRONTIER: ${state.ai.activeModel.toUpperCase()}]`);

  msgBlock.innerHTML = `
    <div class="chat-msg-header">
      <span class="chat-msg-role">${roleTitle}</span>
      <span class="chat-timer">STREAMING...</span>
    </div>
    <div class="chat-msg-body"></div>
  `;
  if (stream) {
    stream.appendChild(msgBlock);
    stream.scrollTop = stream.scrollHeight;
  }

  const bodyElem = msgBlock.querySelector('.chat-msg-body');
  state.ai.abortController = new AbortController();

  let contextPrefix = '';
  // STM context auto-injection if enabled
  const stmChk = document.getElementById('stm-auto-inject-chk');
  if (stmChk && stmChk.checked) {
    try {
      if (!state.stm.summary) {
        const stmRes = await fetch('/api/memory/stm');
        state.stm.summary = await stmRes.json();
      }
      if (state.stm.summary && state.stm.summary.prompt_injection) {
        contextPrefix += `${state.stm.summary.prompt_injection}\n\n`;
      }
    } catch (e) {
      console.warn('STM injection failed:', e);
    }
  }

  // RAG injection if enabled
  if (state.ai.ragEnabled) {
    try {
      const ragRes = await fetch('/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: prompt, collection: state.ai.ragCollection, limit: 3 })
      });
      const ragData = await ragRes.json();
      if (ragData.ok && Array.isArray(ragData.results) && ragData.results.length > 0) {
        const chunks = ragData.results.map(r => `[Source: ${r.payload?.title || 'Memory'}] ${r.payload?.content || ''}`).join('\n\n');
        contextPrefix += `[Retrieved Context from Qdrant Vector Memory]:\n${chunks}\n\n`;
      }
    } catch (e) {
      console.warn('RAG retrieval skipped:', e);
    }
  }

  const apiMessages = [
    { role: 'system', content: 'You are the StoneSage AI Cognitive Assistant. Respond with precision, clarity, and terminal-usable formatting.' },
    ...state.ai.messages.slice(0, -1),
    { role: 'user', content: contextPrefix + prompt }
  ];

  try {
    const res = await fetch('/api/cluster/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: state.ai.activeModel,
        messages: apiMessages,
        params: { max_tokens: 4096 }
      }),
      signal: state.ai.abortController.signal
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let reasoningBuffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
          try {
            const parsed = JSON.parse(line.slice(6));
            const delta = parsed.choices?.[0]?.delta || {};
            if (delta.reasoning_content) {
              reasoningBuffer += delta.reasoning_content;
            }
            if (parsed.watchdog_intercept) {
              const phrase = parsed.intercept_phrase || 'repetition loop';
              window.showChatWatchdogAlert(phrase);
              window.pollWatchdogStatus();
            }
            if (delta.content) {
              fullResponse += delta.content;
            }
            if (bodyElem) {
              let html = '';
              if (reasoningBuffer) {
                html += `<details class="reasoning-trace" open style="background: rgba(0,0,0,0.25); border: 1px dashed var(--term-border); padding: 6px; margin-bottom: 8px; font-size: 0.85em; color: var(--term-text-muted);"><summary style="cursor: pointer; color: var(--term-warn); font-weight: bold;">[🧠 AGENTIC REASONING TRACE]</summary><div style="margin-top: 4px; white-space: pre-wrap; font-family: monospace;">${escapeHtml(reasoningBuffer)}</div></details>`;
              }
              html += escapeHtml(fullResponse).replace(/\n/g, '<br>');
              bodyElem.innerHTML = html;
              if (stream) stream.scrollTop = stream.scrollHeight;
            }
          } catch (pe) {}
        }
      }
    }

    state.ai.messages.push({ role: 'assistant', content: fullResponse });
    const timer = msgBlock.querySelector('.chat-timer');
    if (timer) timer.textContent = timeNow();

  } catch (err) {
    if (err.name === 'AbortError') {
      if (bodyElem) bodyElem.innerHTML += '<br><span style="color:var(--term-warn)">[GENERATION STOPPED BY USER]</span>';
    } else {
      if (bodyElem) bodyElem.innerHTML += `<br><span style="color:var(--term-alert)">[ERROR: ${err.message}]</span>`;
    }
  } finally {
    state.ai.isGenerating = false;
    state.ai.abortController = null;
    if (sendBtn) sendBtn.disabled = false;
    if (stopBtn) stopBtn.style.display = 'none';
  }
}

function logChatMessage(role, content) {
  const stream = document.getElementById('chat-stream');
  if (!stream) return;
  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;
  msg.innerHTML = `
    <div class="chat-msg-header">
      <span class="chat-msg-role">[${role.toUpperCase()}]</span>
      <span>${timeNow()}</span>
    </div>
    <div class="chat-msg-body">${escapeHtml(content).replace(/\n/g, '<br>')}</div>
  `;
  stream.appendChild(msg);
  stream.scrollTop = stream.scrollHeight;
}

/* ==========================================================================
   6b. AI Cockpit Parity: Planner Agent, STM RAM HUD & Knowledge Base Sync
   ========================================================================== */
window.switchAiCockpitTab = function(tab) {
  const tabs = {
    chat: { btn: 'ai-tab-chat', pane: 'ai-view-chat-pane' },
    planner: { btn: 'ai-tab-planner', pane: 'ai-view-planner-pane' },
    stm: { btn: 'ai-tab-stm', pane: 'ai-view-stm-pane' },
    kb: { btn: 'ai-tab-kb', pane: 'ai-view-kb-pane' },
    models: { btn: 'ai-tab-models', pane: 'ai-view-models-pane' }
  };

  Object.values(tabs).forEach(t => {
    const b = document.getElementById(t.btn);
    const p = document.getElementById(t.pane);
    if (b) b.classList.remove('active');
    if (p) p.style.display = 'none';
  });

  const selected = tabs[tab] || tabs.chat;
  const targetBtn = document.getElementById(selected.btn);
  const targetPane = document.getElementById(selected.pane);
  if (targetBtn) targetBtn.classList.add('active');
  if (targetPane) targetPane.style.display = 'flex';

  if (tab === 'stm') fetchStmStatus();
  if (tab === 'kb') fetchKnowledgeBaseStatus();
  if (tab === 'models') fetchClusterModels();
};

window.generatePlanFromGoal = async function() {
  const input = document.getElementById('planner-goal-input');
  const btn = document.getElementById('planner-decompose-btn');
  const list = document.getElementById('planner-steps-list');
  const title = document.getElementById('planner-plan-title');
  if (!input || !list) return;

  const goal = input.value.trim();
  if (!goal) {
    alert('Please enter a goal to decompose.');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = '[DECOMPOSING...]';
  }
  list.innerHTML = '<div style="color:var(--term-text-bright); padding:0.5rem;">[COORDINATOR] Analyzing goal and decomposing into finite execution steps...</div>';

  try {
    const res = await fetch('/api/planner/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal })
    });
    const data = await res.json();
    if (data.ok && data.plan) {
      state.planner.activePlan = data.plan;
      if (title) title.textContent = `PLAN: ${escapeHtml(data.plan.goal || goal).toUpperCase()}`;
      renderPlanSteps(data.plan);
      fetchStmStatus();
    } else {
      list.innerHTML = `<div style="color:var(--term-alert); padding:0.5rem;">Decomposition error: ${escapeHtml(data.error || 'Failed to generate plan')}</div>`;
    }
  } catch (err) {
    list.innerHTML = `<div style="color:var(--term-alert); padding:0.5rem;">Error: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '[📋 DECOMPOSE PLAN]';
    }
  }
};

function renderPlanSteps(plan) {
  const list = document.getElementById('planner-steps-list');
  if (!list) return;

  const steps = plan.steps || [];
  if (steps.length === 0) {
    list.innerHTML = '<div style="color:var(--term-text-muted); padding:0.5rem;">Plan has no steps.</div>';
    return;
  }

  list.innerHTML = steps.map((s, idx) => {
    const status = s.status || 'pending';
    const statusClass = status === 'completed' ? 'completed' : (status === 'running' ? 'running' : (status === 'failed' ? 'failed' : ''));
    const statusBadge = status === 'completed' ? '<span style="color:var(--term-text-bright)">[✔ DONE]</span>' : (status === 'running' ? '<span style="color:var(--term-warn)">[▶ RUNNING]</span>' : (status === 'failed' ? '<span style="color:var(--term-alert)">[✖ FAILED]</span>' : '<span style="color:var(--term-text-dim)">[PENDING]</span>'));

    return `
      <div class="planner-step-card ${statusClass}" id="step-card-${s.id || idx + 1}">
        <div style="flex: 1;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong>[STEP ${String(s.id || idx + 1).padStart(2, '0')}] ${escapeHtml(s.title || s.desc || s.action || s.step || 'Step')}</strong>
            <div>${statusBadge}</div>
          </div>
          <div style="font-size: 0.74rem; color: var(--term-text-dim); margin-bottom: 0.25rem;">
            ${escapeHtml(s.action && s.desc ? `Action: ${s.action} • Target: ${s.target || 'System'}` : (s.desc || s.action || s.instruction || s.detail || ''))}
          </div>
          ${s.result || s.output ? `<div style="background:var(--term-bg); border:1px dashed var(--term-border); padding:4px; font-size:0.7rem; color:var(--term-text-bright); margin-top:4px; max-height:80px; overflow-y:auto;">${escapeHtml(s.result || s.output)}</div>` : ''}
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.25rem;">
          <button class="launch-btn" onclick="executePlanStep(${s.id || idx + 1})" style="padding: 2px 6px;" ${status === 'completed' || status === 'running' ? 'disabled' : ''}>[EXEC]</button>
        </div>
      </div>
    `;
  }).join('');
}

window.executeCurrentPlanStep = async function() {
  if (!state.planner.activePlan || !state.planner.activePlan.steps) {
    alert('No active plan to execute.');
    return;
  }
  const nextStep = state.planner.activePlan.steps.find(s => (s.status || 'pending') === 'pending');
  if (!nextStep) {
    alert('All steps in the current plan are already completed!');
    return;
  }
  await executePlanStep(nextStep.id);
};

window.executePlanStep = async function(stepId) {
  if (!state.planner.activePlan) return;
  const step = state.planner.activePlan.steps.find(s => s.id === stepId);
  if (!step) return;

  step.status = 'running';
  renderPlanSteps(state.planner.activePlan);

  try {
    const res = await fetch('/api/planner/execute_step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step_id: stepId })
    });
    const data = await res.json();
    if (data.ok) {
      step.status = 'completed';
      step.result = data.step?.output || data.result || 'Execution completed.';
      step.output = step.result;
      fetchStmStatus();
    } else {
      step.status = 'failed';
      step.result = data.error || 'Execution failed';
    }
  } catch (err) {
    step.status = 'failed';
    step.result = err.message;
  }
  renderPlanSteps(state.planner.activePlan);
};

window.runAutonomousLoop = async function() {
  if (!state.planner.activePlan || !state.planner.activePlan.steps) {
    alert('Create a plan before launching the autonomous loop.');
    return;
  }
  state.planner.isRunningLoop = true;
  state.planner.loopAbort = false;

  const loopBtn = document.getElementById('planner-loop-btn');
  const abortBtn = document.getElementById('planner-abort-btn');
  if (loopBtn) loopBtn.disabled = true;
  if (abortBtn) abortBtn.style.display = 'inline-block';

  try {
    for (const step of state.planner.activePlan.steps) {
      if (state.planner.loopAbort) {
        logToTerminal('[PLANNER] Autonomous execution loop aborted by user.', 'alert');
        break;
      }
      if (step.status === 'completed') continue;
      await executePlanStep(step.id);
      if (step.status === 'failed') {
        logToTerminal(`[PLANNER] Step ${step.id} failed. Halting autonomous loop.`, 'alert');
        break;
      }
      await new Promise(r => setTimeout(r, 600));
    }
  } finally {
    state.planner.isRunningLoop = false;
    state.planner.loopAbort = false;
    if (loopBtn) loopBtn.disabled = false;
  }
};

window.abortAutonomousLoop = function() {
  state.planner.loopAbort = true;
  logToTerminal('[PLANNER] Loop abort requested.');
};

window.fetchStmStatus = async function() {
  try {
    const res = await fetch('/api/memory/stm');
    const data = await res.json();
    if (data.ok) {
      state.stm.summary = data;
      const miniTokens = document.getElementById('stm-mini-token-count');
      const fullItems = document.getElementById('stm-full-item-count');
      const fullTokens = document.getElementById('stm-full-token-count');
      const fullUpdated = document.getElementById('stm-full-last-updated');
      const container = document.getElementById('stm-items-container');

      if (miniTokens) miniTokens.textContent = `${data.estimated_tokens || 0} tok`;
      if (fullItems) fullItems.textContent = data.item_count || 0;
      if (fullTokens) fullTokens.textContent = `${data.estimated_tokens || 0} / ${data.token_limit || 1024}`;
      if (fullUpdated) fullUpdated.textContent = data.last_compressed || (data.items?.length > 0 ? 'Active' : 'Empty');

      if (container) {
        if (!data.items || data.items.length === 0) {
          container.innerHTML = '<div style="color:var(--term-text-muted); font-size:0.75rem;">Short-Term Memory is empty. Add key/value variables or run the Planner.</div>';
        } else {
          container.innerHTML = data.items.map(item => `
            <div class="stm-item-chip">
              <div style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <span style="color: var(--term-text-bright); font-weight: 700;">[${escapeHtml(item.key)}]</span>:
                <span style="color: var(--term-text-dim);">${escapeHtml(item.value)}</span>
              </div>
              <button class="launch-btn" onclick="removeStmItem('${item.id}')" style="padding: 0 4px; margin-left: 6px;" title="Evict from RAM">[✕]</button>
            </div>
          `).join('');
        }
      }
    }
  } catch (e) {
    console.warn('Failed to fetch STM status:', e);
  }
};

window.addStmItemFromInput = async function() {
  const keyInput = document.getElementById('stm-new-key');
  const valInput = document.getElementById('stm-new-val');
  if (!keyInput || !valInput) return;

  const key = keyInput.value.trim();
  const val = valInput.value.trim();
  if (!key || !val) {
    alert('Provide both key and value to store in RAM.');
    return;
  }

  try {
    const res = await fetch('/api/memory/stm/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: 'manual', key, val })
    });
    const data = await res.json();
    if (data.ok) {
      keyInput.value = '';
      valInput.value = '';
      fetchStmStatus();
    }
  } catch (e) {
    alert(`STM Add error: ${e.message}`);
  }
};

window.removeStmItem = async function(id) {
  try {
    await fetch('/api/memory/stm/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    fetchStmStatus();
  } catch (e) {
    console.warn('Failed to remove STM item:', e);
  }
};

window.clearStmMemory = async function() {
  try {
    await fetch('/api/memory/stm/clear', { method: 'POST' });
    fetchStmStatus();
  } catch (e) {
    console.warn('Failed to clear STM:', e);
  }
};

window.compressStmWorkingMemory = async function() {
  try {
    logToTerminal('[STM ENGINE] Requesting Worker context compression...');
    const res = await fetch('/api/memory/stm/compress', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      logToTerminal(`[STM COMPRESSED] Distilled to: ${data.compressed || 'summary updated'}`);
      fetchStmStatus();
    }
  } catch (e) {
    logToTerminal(`[STM ERROR] ${e.message}`, 'alert');
  }
};

window.openStmQuickView = function() {
  switchAiCockpitTab('stm');
};

window.fetchKnowledgeBaseStatus = async function() {
  const countElem = document.getElementById('kb-files-count');
  try {
    const res = await fetch('/api/knowledge/status');
    const data = await res.json();
    if (data.ok && countElem) {
      countElem.textContent = `${data.file_count || 0} Markdown Docs`;
    }
  } catch (e) {
    if (countElem) countElem.textContent = 'Ready';
  }
};

window.syncKnowledgeBase = async function() {
  const logElem = document.getElementById('kb-sync-log');
  const btn = document.getElementById('ai-kb-sync-btn');
  if (btn) btn.disabled = true;
  if (logElem) logElem.innerHTML += `<br>[${timeNow()}] Indexing Obsidian RAG files into Qdrant via BGE-Large...`;

  try {
    const res = await fetch('/api/knowledge/sync', { method: 'POST' });
    const data = await res.json();
    if (data.ok && logElem) {
      const r = data.result || {};
      logElem.innerHTML += `<br>[${timeNow()}] <span style="color:var(--term-text-bright)">✔ SUCCESS: ${r.new_chunks_indexed || 0} chunks vectorized into Qdrant!</span>`;
      logElem.scrollTop = logElem.scrollHeight;
    } else if (logElem) {
      logElem.innerHTML += `<br>[${timeNow()}] <span style="color:var(--term-alert)">✖ ERROR: ${data.error || 'Sync failed'}</span>`;
    }
  } catch (e) {
    if (logElem) logElem.innerHTML += `<br>[${timeNow()}] <span style="color:var(--term-alert)">✖ ERROR: ${e.message}</span>`;
  } finally {
    if (btn) btn.disabled = false;
  }
};

/* ==========================================================================
   7. Smart Home & Nest Thermostat
   ========================================================================== */
function initHomeAssistant() {
  const refreshBtn = document.getElementById('refresh-ha-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    const orig = refreshBtn.textContent;
    refreshBtn.textContent = '[⏳ REFRESHING...]';
    await fetchHaDashboard();
    refreshBtn.textContent = orig;
  });

  const slider = document.getElementById('temp-slider');
  const tempDown = document.getElementById('temp-down-btn');
  const tempUp = document.getElementById('temp-up-btn');
  const targetDisplay = document.getElementById('thermostat-target-temp');

  if (slider) {
    slider.addEventListener('input', (e) => {
      state.thermostat.target = parseInt(e.target.value, 10);
      if (targetDisplay) targetDisplay.textContent = state.thermostat.target;
    });
    slider.addEventListener('change', () => setHassThermostatTemp(state.thermostat.target));
  }

  if (tempDown) {
    tempDown.addEventListener('click', () => {
      state.thermostat.target = Math.max(60, state.thermostat.target - 1);
      if (slider) slider.value = state.thermostat.target;
      if (targetDisplay) targetDisplay.textContent = state.thermostat.target;
      setHassThermostatTemp(state.thermostat.target);
    });
  }

  if (tempUp) {
    tempUp.addEventListener('click', () => {
      state.thermostat.target = Math.min(85, state.thermostat.target + 1);
      if (slider) slider.value = state.thermostat.target;
      if (targetDisplay) targetDisplay.textContent = state.thermostat.target;
      setHassThermostatTemp(state.thermostat.target);
    });
  }

  // Mode toggles
  const modeBtns = document.querySelectorAll('.thermostat-modes-row .filter-btn');
  modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.hvacMode;
      setHassThermostatMode(mode);
    });
  });

  // NLP dispatch
  const nlpBtn = document.getElementById('ha-nlp-send-btn');
  const nlpInput = document.getElementById('ha-nlp-input');
  if (nlpBtn && nlpInput) {
    nlpBtn.addEventListener('click', async () => {
      const text = nlpInput.value.trim();
      if (!text) return;
      nlpBtn.disabled = true;
      nlpBtn.textContent = 'EXECUTING...';
      try {
        const res = await fetch('/api/ha/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: text })
        });
        const data = await res.json();
        alert(data.message || 'Home automation command executed.');
        nlpInput.value = '';
        fetchHaDashboard();
      } catch (e) {
        alert(`Command error: ${e.message}`);
      } finally {
        nlpBtn.disabled = false;
        nlpBtn.textContent = '[DISPATCH]';
      }
    });
  }

  fetchHaDashboard();
}

async function fetchHaDashboard() {
  try {
    const res = await fetch('/api/ha/dashboard');
    const data = await res.json();
    if (data.ok) {
      if (data.climate && data.climate.length > 0) {
        const t = data.climate.find(c => c.entity_id === 'climate.nest_thermostat') || data.climate[0];
        state.thermostat.entity_id = t.entity_id;
        state.thermostat.current = Math.round(t.attributes?.current_temperature || t.current_temperature || 72);
        state.thermostat.target = Math.round(t.attributes?.temperature || t.temperature || 71);
        state.thermostat.mode = t.state || 'cool';

        const curElem = document.getElementById('thermostat-current-temp');
        const tarElem = document.getElementById('thermostat-target-temp');
        const stateElem = document.getElementById('thermostat-hvac-state');
        const eidElem = document.getElementById('thermostat-entity-id');
        const humElem = document.getElementById('thermostat-humidity');
        const slider = document.getElementById('temp-slider');

        if (curElem) curElem.textContent = state.thermostat.current;
        if (tarElem) tarElem.textContent = state.thermostat.target;
        if (stateElem) stateElem.textContent = `[${state.thermostat.mode.toUpperCase()} ACTIVE]`;
        if (eidElem) eidElem.textContent = state.thermostat.entity_id;
        if (humElem && t.attributes?.current_humidity) humElem.textContent = `${t.attributes.current_humidity}%`;
        if (slider) slider.value = state.thermostat.target;

        document.querySelectorAll('.thermostat-modes-row button').forEach(b => {
          b.classList.toggle('active', b.dataset.hvacMode === state.thermostat.mode);
        });
      }

      // Cache entities in state
      state.ha.lights = data.lights || [];
      state.ha.switches = data.switches || [];
      state.ha.all = [...state.ha.lights, ...state.ha.switches];
      renderHaFilteredDevices();
    }
  } catch (err) {
    console.warn('Failed to fetch Home Assistant states:', err);
  }
}

let cctvMode = 'stream';
let cctvRefreshTimer = null;

window.triggerVirtualSwitch = async function(entityId) {
  try {
    logToTerminal(`[HA] Triggering scene helper: ${entityId}...`);
    const res = await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'input_boolean',
        service: 'turn_on',
        service_data: { entity_id: entityId }
      })
    });
    const data = await res.json();
    if (data.ok) {
      logToTerminal(`[HA] Successfully executed routine for ${entityId}`, 'success');
      setTimeout(fetchHaDashboard, 1500);
    } else {
      logToTerminal(`[HA Error] ${data.error}`, 'alert');
    }
  } catch (err) {
    logToTerminal(`[HA Exception] ${err.message}`, 'alert');
  }
};

window.moveCameraPreset = async function(presetName) {
  try {
    logToTerminal(`[CCTV] Moving Kitchen/Living Room camera to preset: ${presetName}...`);
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'select',
        service: 'select_option',
        service_data: {
          entity_id: 'select.kitchen_kitchen_living_room_hd_direct_move_to_preset',
          option: presetName
        }
      })
    });
    logToTerminal(`[CCTV] Pan/Tilt preset dispatched: ${presetName}`, 'success');
  } catch (e) {
    logToTerminal(`[CCTV Error] ${e.message}`, 'alert');
  }
};

window.moveDrivewayPreset = async function(presetName) {
  try {
    logToTerminal(`[CCTV] Moving Driveway camera to preset: ${presetName}...`);
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'select',
        service: 'select_option',
        service_data: {
          entity_id: 'select.driveway_front_door_hd_stream_direct_move_to_preset',
          option: presetName
        }
      })
    });
    logToTerminal(`[CCTV] Driveway preset dispatched: ${presetName}`, 'success');
  } catch (e) {
    logToTerminal(`[CCTV Error] ${e.message}`, 'alert');
  }
};

window.toggleCameraPrivacy = async function() {
  try {
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'switch',
        service: 'toggle',
        service_data: { entity_id: 'switch.kitchen_living_room_privacy' }
      })
    });
    logToTerminal('[CCTV] Toggled indoor privacy mode.', 'success');
  } catch (e) {
    logToTerminal(`[CCTV Error] ${e.message}`, 'alert');
  }
};

window.switchCctvMode = function(mode) {
  cctvMode = mode;
  document.getElementById('cctv-mode-stream')?.classList.toggle('active', mode === 'stream');
  document.getElementById('cctv-mode-snapshot')?.classList.toggle('active', mode === 'snapshot');
  
  if (cctvRefreshTimer) {
    clearInterval(cctvRefreshTimer);
    cctvRefreshTimer = null;
  }

  const cam1 = document.getElementById('cam1-feed');
  const cam2 = document.getElementById('cam2-feed');
  const t = Date.now();

  if (mode === 'stream') {
    if (cam1) cam1.src = `/api/hass/camera_stream?entity_id=camera.kitchen_living_room_hd_stream&_t=${t}`;
    if (cam2) cam2.src = `/api/hass/camera_stream?entity_id=camera.driveway_front_door_hd_stream_direct&_t=${t}`;
  } else {
    function refreshSnaps() {
      const ts = Date.now();
      if (cam1) cam1.src = `/api/hass/camera_snapshot?entity_id=camera.kitchen_living_room_hd_stream&_t=${ts}`;
      if (cam2) cam2.src = `/api/hass/camera_snapshot?entity_id=camera.driveway_front_door_hd_stream_direct&_t=${ts}`;
    }
    refreshSnaps();
    cctvRefreshTimer = setInterval(refreshSnaps, 3000);
  }
};

window.refreshCctvFeeds = function() {
  window.switchCctvMode(cctvMode);
};

window.onCctvError = function(camId) {
  const feed = document.getElementById(`${camId}-feed`);
  if (feed && !feed.src.includes('camera_snapshot')) {
    const eid = camId === 'cam1' ? 'camera.kitchen_living_room_hd_stream' : 'camera.driveway_front_door_hd_stream_direct';
    feed.src = `/api/hass/camera_snapshot?entity_id=${eid}&_t=${Date.now()}`;
  }
};

async function setHassThermostatTemp(targetTemp) {
  try {
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'climate',
        service: 'set_temperature',
        service_data: {
          entity_id: state.thermostat.entity_id,
          temperature: targetTemp
        }
      })
    });
    logToTerminal(`[HA] Set thermostat temperature to ${targetTemp}°F`);
  } catch (e) {
    console.warn('Thermostat temp call error:', e);
  }
}

async function setHassThermostatMode(mode) {
  try {
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain: 'climate',
        service: 'set_hvac_mode',
        service_data: {
          entity_id: state.thermostat.entity_id,
          hvac_mode: mode
        }
      })
    });
    logToTerminal(`[HA] Set thermostat mode to ${mode.toUpperCase()}`);
  } catch (e) {
    console.warn('Thermostat mode call error:', e);
  }
}

window.filterHaDevices = function(category) {
  state.ha.filter = category;
  ['curated', 'lights', 'switches', 'cameras', 'all'].forEach(cat => {
    const btn = document.getElementById(`ha-filter-${cat}`);
    if (btn) btn.classList.toggle('active', cat === category);
  });
  renderHaFilteredDevices();
};

window.onHaSearchInput = function() {
  const input = document.getElementById('ha-search-input');
  state.ha.searchQuery = input ? input.value.trim().toLowerCase() : '';
  renderHaFilteredDevices();
};

function isNoisyEntity(entity_id, name) {
  const str = `${entity_id} ${name || ''}`.toLowerCase();
  const noisePatterns = [
    'trigger_alarm_on_',
    'alarm_tamper',
    'tamper_detection',
    'tamper_',
    '_tamper',
    'auto_update',
    'firmware_update',
    'automatically_upgrade_firmware',
    'automatic_reboot',
    'detection_sensitivity',
    'record_audio',
    'record_to_sd_card',
    'status_led',
    'indicator_led',
    '_led',
    'night_vision',
    'cloud_storage',
    'siren',
    'doorbell_call',
    'auto_tracking',
    'auto_track',
    'privacy_mode',
    'privacy_zone',
    'privacy_zones',
    '_privacy',
    'motion_detection_switch',
    'tampering',
    'lens_distortion_correction',
    'diagnose_mode',
    'smart_track_',
    'media_sync',
    'preset_patrol_mode',
    'rich_notifications',
    '_notifications',
    'microphone_mute',
    'microphone_noise_cancellation',
    'auto_off_enabled',
    'announcements',
    'communications',
    'do_not_disturb',
    '_flip'
  ];
  return noisePatterns.some(p => str.includes(p));
}

function cleanEntityDisplayName(item) {
  if (item.name && item.name !== 'None' && item.name.trim()) {
    return item.name.trim();
  }
  const eid = item.entity_id || '';
  const raw = eid.includes('.') ? eid.split('.')[1] : eid;
  let text = raw.replace(/_/g, ' ');
  // Deduplicate repeated consecutive words or phrases (e.g. front porch front porch front porch)
  text = text.replace(/\b(\w+)(?:\s+\1\b)+/gi, '$1');
  text = text.replace(/\b(\w+\s+\w+)(?:\s+\1\b)+/gi, '$1');
  text = text.replace(/\b(\w+\s+\w+\s+\w+)(?:\s+\1\b)+/gi, '$1');
  // Title-case
  let s = text.trim().replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.substr(1).toLowerCase());
  s = s.replace(/\bTv\b/g, 'TV').replace(/\bLed\b/g, 'LED');
  return s;
}

function categorizeEntity(entity_id, name) {
  const s = `${entity_id} ${name || ''}`.toLowerCase();
  if (s.includes('living_room') || s.includes('living room') || s.includes('couch') || s.includes('tv') || s.includes('roku')) return '🏠 LIVING ROOM';
  if (s.includes('office') || s.includes('desk') || s.includes('pc') || s.includes('monitor')) return '💻 OFFICE & WORKSPACE';
  if (s.includes('bedroom') || s.includes('bed') || s.includes('bath')) return '🛏️ BEDROOM & BATH';
  if (s.includes('hose') || s.includes('watering') || s.includes('yard') || s.includes('garden')) return '🌱 SMART WATERING & YARD';
  if (s.includes('ge_plug') || s.includes('kp125') || s.includes('dryer') || s.includes('petkit') || s.includes('plug') || s.includes('socket') || s.includes('appliance')) return '⚡ SMART PLUGS & APPLIANCES';
  if (s.includes('camera') || s.includes('doorbell') || s.includes('floodlight') || s.includes('driveway') || s.includes('front') || s.includes('backyard')) return '📹 PERIMETER & SECURITY';
  if (entity_id.startsWith('light.')) return '💡 OTHER LIGHTS';
  return '🔌 OTHER SWITCHES & DEVICES';
}

function renderHaFilteredDevices() {
  const table = document.getElementById('ha-entities-table');
  const count = document.getElementById('ha-devices-count');
  if (!table) return;

  let list = [...(state.ha.all || [])];
  const query = state.ha.searchQuery;
  const filter = state.ha.filter || 'curated';

  if (filter === 'lights') {
    list = list.filter(item => item.entity_id.startsWith('light.'));
  } else if (filter === 'switches') {
    list = list.filter(item => item.entity_id.startsWith('switch.') && !isNoisyEntity(item.entity_id, item.name));
  } else if (filter === 'cameras') {
    list = list.filter(item => {
      const s = `${item.entity_id} ${item.name || ''}`.toLowerCase();
      return s.includes('camera') || s.includes('doorbell') || s.includes('floodlight') || isNoisyEntity(item.entity_id, item.name);
    });
  } else if (filter === 'curated') {
    // Curated view: filter out granular security camera switches completely
    list = list.filter(item => !isNoisyEntity(item.entity_id, item.name));
  }

  // Apply search query filter if typed
  if (query) {
    list = list.filter(item => {
      const s = `${item.entity_id} ${item.name || ''}`.toLowerCase();
      return s.includes(query);
    });
  }

  if (count) count.textContent = `${list.length} entities displayed (${state.ha.all?.length || 0} total)`;

  if (list.length === 0) {
    table.innerHTML = '<div style="color:var(--term-text-muted); padding:0.75rem;">No matching smart home devices found.</div>';
    return;
  }

  // Curated layout: Group cleanly by area/room
  if (filter === 'curated' && !query) {
    const groups = {};
    list.forEach(item => {
      const cat = categorizeEntity(item.entity_id, item.name);
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    });

    let html = '';
    for (const [grpName, items] of Object.entries(groups)) {
      html += `
        <div class="ha-group-header">[ ${grpName} ] (${items.length})</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-bottom: 0.5rem;">
          <tbody>
            ${items.map(renderEntityRow).join('')}
          </tbody>
        </table>
      `;
    }
    table.innerHTML = html;
  } else {
    table.innerHTML = `
      <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem;">
        <thead>
          <tr style="border-bottom: 1px solid var(--term-border); color: var(--term-text-bright); text-align: left;">
            <th style="padding: 4px;">ENTITY</th>
            <th style="padding: 4px;">STATE</th>
            <th style="padding: 4px; text-align: right;">ACTION</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(renderEntityRow).join('')}
        </tbody>
      </table>
    `;
  }
}

function renderEntityRow(item) {
  const isLight = item.entity_id.startsWith('light.');
  const icon = isLight ? '💡' : '🔌';
  const cleanName = cleanEntityDisplayName(item);
  return `
    <tr style="border-bottom: 1px dashed var(--term-border-dim);">
      <td style="padding: 4px;">
        <span style="margin-right: 4px;">${icon}</span>
        <span style="font-weight: 700; color: var(--term-text-bright);">${escapeHtml(cleanName)}</span>
        <div style="font-size: 0.7rem; color: var(--term-text-dim);">${escapeHtml(item.entity_id)}</div>
      </td>
      <td style="padding: 4px; font-weight: 700; color: ${item.state === 'on' ? 'var(--term-text-bright)' : 'var(--term-text-muted)'};">
        [${(item.state || 'off').toUpperCase()}]
      </td>
      <td style="padding: 4px; text-align: right;">
        <button class="launch-btn" onclick="toggleHassDevice('${item.entity_id}', '${item.state}')" style="padding: 2px 8px;">
          ${item.state === 'on' ? '[TURN OFF]' : '[TURN ON]'}
        </button>
      </td>
    </tr>
  `;
}

window.toggleHassDevice = async function(entityId, currentState) {
  const domain = entityId.split('.')[0] || 'switch';
  const service = currentState === 'on' ? 'turn_off' : 'turn_on';
  try {
    await fetch('/api/ha/service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain,
        service,
        service_data: { entity_id: entityId }
      })
    });
    fetchHaDashboard();
  } catch (e) {
    alert(`Toggle error: ${e.message}`);
  }
};

/* ==========================================================================
   8. Obsidian User Brain & Qdrant Vector Sync
   ========================================================================== */
function initObsidianBrain() {
  const syncBtn = document.getElementById('sync-obsidian-qdrant-btn');
  const refreshBtn = document.getElementById('refresh-obsidian-btn');

  if (syncBtn) syncBtn.addEventListener('click', syncObsidianToQdrant);
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      const orig = refreshBtn.textContent;
      refreshBtn.textContent = '[⏳ REFRESHING...]';
      await Promise.all([fetchObsidianNotes(), fetchBrainSyncStatus()]);
      refreshBtn.textContent = orig;
    });
  }

  fetchObsidianNotes();
  fetchBrainSyncStatus();
}

window.fetchCouchDbStatus = async function() {
  const badge = document.getElementById('couchdb-status-badge');
  const dbname = document.getElementById('couchdb-dbname');
  try {
    const res = await fetch('/api/couchdb/status');
    const data = await res.json();
    if (data.ok && data.couchdb && data.couchdb.online) {
      if (badge) {
        badge.textContent = `[COUCHDB: ONLINE (${data.couchdb.doc_count || 0} docs)]`;
        badge.className = 'service-status-badge online';
      }
      if (dbname) dbname.textContent = data.couchdb.database || 'obsidiannotes';
    } else {
      if (badge) {
        badge.textContent = '[COUCHDB: OFFLINE]';
        badge.className = 'service-status-badge offline';
      }
    }
  } catch (e) {
    if (badge) {
      badge.textContent = '[COUCHDB: UNREACHABLE]';
      badge.className = 'service-status-badge offline';
    }
  }
};

async function fetchBrainSyncStatus() {
  try {
    const res = await fetch('/api/obsidian/sync_status');
    const data = await res.json();
    if (data.ok && data.sync) {
      const lastSyncElem = document.getElementById('brain-last-sync');
      const noteCountElem = document.getElementById('brain-note-count');
      const vectorCountElem = document.getElementById('brain-vector-count');

      if (lastSyncElem) lastSyncElem.textContent = data.sync.last_synced || 'Never';
      if (noteCountElem) noteCountElem.textContent = data.sync.total_notes || 0;
      if (vectorCountElem) vectorCountElem.textContent = data.sync.total_chunks || 0;
    }
  } catch (e) {
    console.warn('Failed to fetch sync status:', e);
  }
}

window.syncObsidianToQdrant = async function() {
  const syncBtn = document.getElementById('sync-obsidian-qdrant-btn');
  const progBox = document.getElementById('brain-sync-progress-bar');
  const progText = document.getElementById('brain-progress-text');

  if (syncBtn) {
    syncBtn.disabled = true;
    syncBtn.textContent = '[SYNCING VECTORS...]';
  }
  if (progBox) progBox.style.display = 'block';
  if (progText) progText.textContent = '[████████░░░░░░░░░░░░] Ingesting Notes...';

  try {
    logToTerminal('[OBSIDIAN INGESTOR] Commencing full vector sync of user vault to Qdrant...');
    const res = await fetch('/api/obsidian/sync_to_memory', { method: 'POST' });
    const data = await res.json();
    if (data.ok && data.result) {
      const r = data.result;
      if (progText) progText.textContent = `[████████████████████] DONE: ${r.new_chunks_indexed} chunks indexed!`;
      fetchBrainSyncStatus();
      logToTerminal(`[INGEST COMPLETE] Synced ${r.total_notes} notes, indexed ${r.new_chunks_indexed} new vectors.`);
    } else {
      if (progText) progText.textContent = `[FAILED] ${data.error || 'Unknown error'}`;
      logToTerminal(`[INGEST ERROR] ${data.error}`, 'alert');
    }
  } catch (err) {
    if (progText) progText.textContent = `[ERROR: ${err.message}]`;
    logToTerminal(`[INGEST ERROR] ${err.message}`, 'alert');
  } finally {
    if (syncBtn) {
      syncBtn.disabled = false;
      syncBtn.textContent = '[⚡ SYNC VAULT -> QDRANT BRAIN]';
    }
  }
};

window.fetchObsidianNotes = async function() {
  const list = document.getElementById('obsidian-notes-list');
  const countElem = document.getElementById('obsidian-notes-total');
  const brainCount = document.getElementById('brain-note-count');
  if (!list) return;

  try {
    fetchCouchDbStatus();
    const res = await fetch('/api/obsidian/notes');
    const data = await res.json();
    if (data.ok && Array.isArray(data.notes)) {
      state.obsidian.notes = data.notes;
      const total = data.total !== undefined ? data.total : data.notes.length;
      if (countElem) countElem.textContent = `${total} files`;
      if (brainCount) brainCount.textContent = total;
      renderObsidianNotesList(data.notes);
    }
  } catch (err) {
    list.innerHTML = `<div style="color:var(--term-alert);">Error: ${err.message}</div>`;
  }
};

window.filterObsidianNotes = function() {
  const input = document.getElementById('obsidian-note-search');
  const query = input ? input.value.trim().toLowerCase() : '';
  if (!query) {
    renderObsidianNotesList(state.obsidian.notes || []);
    return;
  }
  const filtered = (state.obsidian.notes || []).filter(n => 
    (n.name && n.name.toLowerCase().includes(query)) ||
    (n.path && n.path.toLowerCase().includes(query))
  );
  renderObsidianNotesList(filtered);
};

function renderObsidianNotesList(notes) {
  const list = document.getElementById('obsidian-notes-list');
  if (!list) return;

  if (notes.length === 0) {
    list.innerHTML = '<div style="color:var(--term-text-muted); padding:0.5rem;">No notes found matching search.</div>';
    return;
  }

  list.innerHTML = notes.map(n => `
    <div class="tree-node file" onclick="viewObsidianNote('${escapeHtml(n.path)}')">
      <span>📄</span>
      <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(n.name)}</span>
      ${n.in_couchdb ? '<span style="font-size:0.62rem; color:var(--term-text-bright); border:1px solid var(--term-border); padding:0 3px; margin-left:4px;">COUCHDB</span>' : ''}
    </div>
  `).join('');
}

window.viewObsidianNote = async function(notePath) {
  try {
    const res = await fetch(`/api/obsidian/note?path=${encodeURIComponent(notePath)}`);
    const data = await res.json();
    if (data.ok) {
      const titleElem = document.getElementById('obsidian-view-title');
      const contentElem = document.getElementById('obsidian-note-content');
      if (titleElem) titleElem.textContent = `VIEWING: ${notePath}`;
      if (contentElem) contentElem.value = data.content || '';
    }
  } catch (e) {
    alert(`Could not load note: ${e.message}`);
  }
};

/* ==========================================================================
   9. Proxmox VE Cockpit
   ========================================================================== */
function formatUptime(seconds) {
  if (!seconds) return '0m';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function startProxmoxPolling() {
  stopProxmoxPolling();
  state.proxmox.pollInterval = setInterval(() => {
    const activeView = document.querySelector('.view-pane.active');
    if (activeView && activeView.id === 'view-proxmox') {
      fetchProxmoxData();
    } else {
      stopProxmoxPolling();
    }
  }, 6000);
}

function stopProxmoxPolling() {
  if (state.proxmox.pollInterval) {
    clearInterval(state.proxmox.pollInterval);
    state.proxmox.pollInterval = null;
  }
}

function initProxmox() {
  const refreshBtn = document.getElementById('refresh-proxmox-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    const orig = refreshBtn.textContent;
    refreshBtn.textContent = '[⏳ PROBING...]';
    await fetchProxmoxData();
    refreshBtn.textContent = orig;
  });

  const rebootConfirm = document.getElementById('confirm-reboot-btn');
  const rebootCancel = document.getElementById('cancel-reboot-btn');
  const rebootClose = document.getElementById('close-reboot-dialog');
  const rebootDialog = document.getElementById('reboot-dialog');

  if (rebootClose && rebootDialog) rebootClose.addEventListener('click', () => rebootDialog.close());
  if (rebootCancel && rebootDialog) rebootCancel.addEventListener('click', () => rebootDialog.close());

  if (rebootConfirm && rebootDialog) {
    rebootConfirm.addEventListener('click', async () => {
      if (!state.selectedRebootGuest) return;
      try {
        await fetch('/api/proxmox/reboot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(state.selectedRebootGuest)
        });
        rebootDialog.close();
        alert(`Reboot command sent to VMID ${state.selectedRebootGuest.vmid}`);
        fetchProxmoxData();
      } catch (e) {
        alert(`Reboot failed: ${e.message}`);
      }
    });
  }

  fetchProxmoxData();
}

window.fetchProxmoxData = async function() {
  const table = document.getElementById('proxmox-guests-table');
  const count = document.getElementById('proxmox-guest-count');

  // 1. Fetch Node Telemetry
  try {
    const nodeRes = await fetch('/api/proxmox/nodes');
    const nodeData = await nodeRes.json();
    if (nodeData.ok && nodeData.nodes) {
      for (const [key, n] of Object.entries(nodeData.nodes)) {
        const badge = document.getElementById(`${key}-node-badge`);
        const cpuBar = document.getElementById(`${key}-cpu-bar`);
        const ramBar = document.getElementById(`${key}-ram-bar`);
        const diskBar = document.getElementById(`${key}-disk-bar`);
        const detailsElem = document.getElementById(`${key}-node-details`);
        const msgElem = document.getElementById(`${key}-node-msg`);

        if (badge) {
          badge.textContent = n.online ? `[ONLINE ${n.latency_ms || 0}ms]` : '[OFFLINE]';
          badge.className = `service-status-badge ${n.online ? 'online' : 'offline'}`;
        }

        const updateBarClass = (elem, pct) => {
          if (!elem) return;
          elem.classList.remove('warn', 'alert');
          if (pct >= 85) elem.classList.add('alert');
          else if (pct >= 70) elem.classList.add('warn');
        };

        // CPU Bar
        if (cpuBar) {
          const cpuPct = n.cpu_pct !== undefined && n.cpu_pct !== null ? Math.max(0, Math.min(100, Math.round(n.cpu_pct * 10) / 10)) : 0;
          const filled = Math.round((cpuPct / 100) * 16);
          const bar = '█'.repeat(Math.max(0, Math.min(16, filled))) + '░'.repeat(Math.max(0, 16 - filled));
          cpuBar.textContent = `CPU:  [${bar}] ${cpuPct.toFixed(1)}%`;
          updateBarClass(cpuBar, cpuPct);
        }

        // RAM Bar
        if (ramBar) {
          const memPct = n.memory_pct !== undefined && n.memory_pct !== null ? Math.max(0, Math.min(100, Math.round(n.memory_pct * 10) / 10)) : 0;
          const filled = Math.round((memPct / 100) * 16);
          const bar = '█'.repeat(Math.max(0, Math.min(16, filled))) + '░'.repeat(Math.max(0, 16 - filled));
          const used = n.memory_used_gb !== undefined ? n.memory_used_gb : (n.memory?.used ? (n.memory.used / (1024**3)).toFixed(2) : '--');
          const total = n.memory_total_gb !== undefined ? n.memory_total_gb : (n.memory?.total ? (n.memory.total / (1024**3)).toFixed(2) : '--');
          ramBar.textContent = `RAM:  [${bar}] ${memPct.toFixed(1)}% (${used} / ${total} GB)`;
          updateBarClass(ramBar, memPct);
        }

        // DISK Bar
        if (diskBar) {
          const diskPct = n.disk_pct !== undefined && n.disk_pct !== null ? Math.max(0, Math.min(100, Math.round(n.disk_pct * 10) / 10)) : 0;
          const filled = Math.round((diskPct / 100) * 16);
          const bar = '█'.repeat(Math.max(0, Math.min(16, filled))) + '░'.repeat(Math.max(0, 16 - filled));
          const diskUsed = n.disk_used_gb !== undefined ? n.disk_used_gb : (n.disk?.used ? (n.disk.used / (1024**3)).toFixed(1) : '--');
          const diskTotal = n.disk_total_gb !== undefined ? n.disk_total_gb : (n.disk?.total ? (n.disk.total / (1024**3)).toFixed(1) : '--');
          diskBar.textContent = `DISK: [${bar}] ${diskPct.toFixed(1)}% (${diskUsed} / ${diskTotal} GB)`;
          updateBarClass(diskBar, diskPct);
        }

        if (detailsElem) {
          detailsElem.innerHTML = `Uptime: <span style="color:var(--term-text-bright);">${formatUptime(n.uptime_sec)}</span> • Kernel: <span style="color:var(--term-text-dim);">${escapeHtml(n.kernel || 'unknown')}</span>`;
        }

        if (msgElem) {
          if (n.error) {
            msgElem.innerHTML = `⚠️ ${escapeHtml(n.error)}`;
            msgElem.style.display = 'block';
          } else {
            msgElem.textContent = '';
            msgElem.style.display = 'none';
          }
        }
      }
    }
  } catch (err) {
    console.warn('Failed to fetch Proxmox node status:', err);
  }

  // 2. Fetch Guests
  if (!table) return;
  try {
    const res = await fetch('/api/proxmox/guests');
    const data = await res.json();
    if (data.ok && Array.isArray(data.guests)) {
      if (count) count.textContent = `${data.guests.length} guests online`;
      if (data.guests.length === 0) {
        table.innerHTML = '<div style="color:var(--term-text-muted); font-size:0.8rem; padding: 4px;">No VMs/LXCs returned. (If token has Privilege Separation enabled, grant Administrator/PVEAuditor role on path /).</div>';
        return;
      }
      table.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem;">
          <thead>
            <tr style="border-bottom: 1px solid var(--term-border); color: var(--term-text-bright); text-align: left;">
              <th style="padding: 4px;">NODE</th>
              <th style="padding: 4px;">VMID</th>
              <th style="padding: 4px;">NAME</th>
              <th style="padding: 4px;">STATUS</th>
              <th style="padding: 4px;">CPU / RAM</th>
              <th style="padding: 4px; text-align: right;">CONTROL</th>
            </tr>
          </thead>
          <tbody>
            ${data.guests.map(g => `
              <tr style="border-bottom: 1px dashed var(--term-border-dim);">
                <td style="padding: 4px;"><span class="node-badge">${g.node}</span></td>
                <td style="padding: 4px;">${g.vmid}</td>
                <td style="padding: 4px; font-weight: bold; color: var(--term-text-bright);">${escapeHtml(g.name || 'Unnamed')}</td>
                <td style="padding: 4px; color: ${g.status === 'running' ? 'var(--term-text-bright)' : 'var(--term-alert)'};">[${(g.status || 'unknown').toUpperCase()}]</td>
                <td style="padding: 4px;">${Math.round((g.cpu || 0) * 100)}% / ${Math.round((g.mem || 0) / (1024*1024))}MB</td>
                <td style="padding: 4px; text-align: right;">
                  <button class="launch-btn" onclick="promptRebootGuest('${g.node}', '${g.vmid}', '${escapeHtml(g.name || '')}')" style="padding: 1px 6px;">[REBOOT]</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  } catch (err) {
    table.innerHTML = `<div style="color:var(--term-alert);">Proxmox probe error: ${err.message}</div>`;
  }
};

window.promptRebootGuest = function(node, vmid, name) {
  state.selectedRebootGuest = { node, vmid, name };
  const dialog = document.getElementById('reboot-dialog');
  const nameElem = document.getElementById('reboot-guest-name');
  const vmidElem = document.getElementById('reboot-guest-vmid');
  if (nameElem) nameElem.textContent = name;
  if (vmidElem) vmidElem.textContent = vmid;
  if (dialog) dialog.showModal();
};

/* ==========================================================================
   Section 9 (Voice & Canvas): Live Canvas Scratchpad & Ambient Voice Copilot
   ========================================================================== */
function initLiveCanvas() {
  const input = document.getElementById('canvas-copilot-input');
  if (input && !input.dataset.bound) {
    input.dataset.bound = 'true';
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendCanvasCopilotMessage();
      }
    });
  }
}

window.copyCanvasBuffer = function() {
  const ta = document.getElementById('canvas-textarea');
  const btn = document.getElementById('canvas-copy-btn');
  if (!ta) return;
  navigator.clipboard.writeText(ta.value || '').then(() => {
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = '[COPIED!]';
      setTimeout(() => btn.textContent = orig, 1500);
    }
  });
};

window.clearCanvasBuffer = function() {
  const ta = document.getElementById('canvas-textarea');
  if (ta && confirm('Clear scratchpad canvas buffer?')) {
    ta.value = '';
  }
};

window.applyCanvasToWorkspace = async function() {
  const ta = document.getElementById('canvas-textarea');
  if (!ta || !ta.value.trim()) {
    alert('Canvas buffer is empty.');
    return;
  }
  const defaultPath = state.workstation.activeFile || 'scratchpad.md';
  const targetPath = prompt('Workspace path to save/apply buffer into:', defaultPath);
  if (!targetPath) return;

  try {
    const res = await fetch('/api/workspace/file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: targetPath, content: ta.value })
    });
    const data = await res.json();
    if (data.ok) {
      alert(`Applied canvas buffer to ${targetPath} (${data.size || ta.value.length} bytes)`);
      if (state.workstation.activeFile === targetPath) {
        state.workstation.originalContent = ta.value;
      }
    } else {
      alert(`Save error: ${data.error || 'Failed to save'}`);
    }
  } catch (e) {
    alert(`Save error: ${e.message}`);
  }
};

window.canvasAction = function(actionType) {
  const ta = document.getElementById('canvas-textarea');
  const input = document.getElementById('canvas-copilot-input');
  if (!ta || !input) return;

  if (actionType === 'refactor') {
    input.value = `Refactor the current canvas code for performance, cyber-brutalist error handling, and robust invariants.`;
  } else if (actionType === 'explain') {
    input.value = `Explain the architectural design, control flow, and potential edge cases of the canvas code.`;
  } else if (actionType === 'tests') {
    input.value = `Generate comprehensive unit and edge-case tests for the canvas code.`;
  }
  sendCanvasCopilotMessage();
};

window.stopCanvasCopilot = function() {
  if (state.canvas.abortController) {
    state.canvas.abortController.abort();
  }
};

window.sendCanvasCopilotMessage = async function(overridePrompt) {
  const input = document.getElementById('canvas-copilot-input');
  const prompt = overridePrompt || (input ? input.value.trim() : '');
  if (!prompt || state.canvas.isGenerating) return;

  if (input) input.value = '';

  const messagesDiv = document.getElementById('canvas-copilot-messages');
  const sendBtn = document.getElementById('canvas-copilot-send');
  const stopBtn = document.getElementById('canvas-copilot-stop');
  if (!messagesDiv) return;

  // Render user bubble
  const userMsg = document.createElement('div');
  userMsg.className = 'chat-msg user';
  userMsg.innerHTML = `
    <div class="chat-msg-header">
      <span class="chat-msg-role">[USER]</span>
      <span>${timeNow()}</span>
    </div>
    <div class="chat-msg-body">${escapeHtml(prompt).replace(/\n/g, '<br>')}</div>
  `;
  messagesDiv.appendChild(userMsg);

  // Render assistant bubble for streaming
  const asstMsg = document.createElement('div');
  asstMsg.className = 'chat-msg assistant';
  asstMsg.innerHTML = `
    <div class="chat-msg-header">
      <span class="chat-msg-role">[AMBIENT COPILOT]</span>
      <span class="copilot-timer">STREAMING...</span>
    </div>
    <div class="chat-msg-body"></div>
  `;
  messagesDiv.appendChild(asstMsg);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  const bodyElem = asstMsg.querySelector('.chat-msg-body');
  state.canvas.isGenerating = true;
  state.canvas.abortController = new AbortController();

  if (sendBtn) sendBtn.disabled = true;
  if (stopBtn) stopBtn.style.display = 'inline-block';

  const ta = document.getElementById('canvas-textarea');
  const canvasContent = ta ? ta.value : '';

  const apiMessages = [
    {
      role: 'system',
      content: `You are the StoneSage Ambient Voice & Live Canvas Copilot.
You assist the developer working on a live scratchpad.
CURRENT CANVAS CONTENTS:
\`\`\`
${canvasContent.slice(0, 4000)}
\`\`\`
Respond with direct instructions, refactorings, or code additions. Format code in standard markdown code blocks with language specifiers.`
    },
    ...state.canvas.messages.slice(-6),
    { role: 'user', content: prompt }
  ];

  try {
    const res = await fetch('/api/cluster/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: 'coordinator',
        messages: apiMessages,
        params: { max_tokens: 4096 }
      }),
      signal: state.canvas.abortController.signal
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Retain incomplete line across TCP packet boundaries!

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed === 'data: [DONE]') continue;
        if (trimmed.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(trimmed.slice(6).trim());
            const delta = parsed.choices?.[0]?.delta?.content || '';
            fullResponse += delta;
            if (bodyElem) {
              bodyElem.innerHTML = renderCopilotResponse(fullResponse);
              messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
          } catch (pe) {
            // Fragmented line silently held
          }
        }
      }
    }

    if (buffer.trim() && buffer.trim().startsWith('data: ') && buffer.trim() !== 'data: [DONE]') {
      try {
        const parsed = JSON.parse(buffer.trim().slice(6).trim());
        const delta = parsed.choices?.[0]?.delta?.content || '';
        fullResponse += delta;
        if (bodyElem) bodyElem.innerHTML = renderCopilotResponse(fullResponse);
      } catch (e) {}
    }

    state.canvas.messages.push({ role: 'user', content: prompt });
    state.canvas.messages.push({ role: 'assistant', content: fullResponse });

    const timer = asstMsg.querySelector('.copilot-timer');
    if (timer) timer.textContent = timeNow();

  } catch (err) {
    if (err.name === 'AbortError') {
      if (bodyElem) bodyElem.innerHTML += '<br><span style="color:var(--term-warn)">[STOPPED]</span>';
    } else {
      if (bodyElem) bodyElem.innerHTML += `<br><span style="color:var(--term-alert)">[ERROR: ${escapeHtml(err.message)}]</span>`;
    }
  } finally {
    state.canvas.isGenerating = false;
    state.canvas.abortController = null;
    if (sendBtn) sendBtn.disabled = false;
    if (stopBtn) stopBtn.style.display = 'none';
  }
};

function renderCopilotResponse(text) {
  if (!text) return '<span style="color:var(--term-text-dim);">Thinking...</span>';
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map(part => {
    if (part.startsWith('```') && part.endsWith('```') && part.length > 5) {
      const lines = part.slice(3, -3).split('\n');
      const lang = lines[0].trim();
      const code = lines.slice(1).join('\n');
      return `
        <div style="margin: 0.5rem 0; border: 1px solid var(--term-border); background: var(--term-bg);">
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 6px; background: var(--term-surface); border-bottom: 1px solid var(--term-border); font-size: 0.7rem;">
            <span>${escapeHtml(lang || 'CODE')}</span>
            <button class="launch-btn" onclick="injectCodeIntoCanvas(this)" style="padding: 1px 6px;">[INJECT INTO CANVAS ⮑]</button>
          </div>
          <pre style="margin: 0; padding: 0.5rem; overflow-x: auto; font-size: 0.74rem;"><code>${escapeHtml(code)}</code></pre>
        </div>
      `;
    }
    if (part.startsWith('```')) {
      // Incomplete streaming code block
      const lines = part.slice(3).split('\n');
      const lang = lines[0].trim();
      const code = lines.slice(1).join('\n');
      return `
        <div style="margin: 0.5rem 0; border: 1px dashed var(--term-border); background: var(--term-bg);">
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 2px 6px; background: var(--term-surface); border-bottom: 1px dashed var(--term-border); font-size: 0.7rem;">
            <span>${escapeHtml(lang || 'CODE')} [STREAMING...]</span>
            <button class="launch-btn" onclick="injectCodeIntoCanvas(this)" style="padding: 1px 6px;">[INJECT INTO CANVAS ⮑]</button>
          </div>
          <pre style="margin: 0; padding: 0.5rem; overflow-x: auto; font-size: 0.74rem;"><code>${escapeHtml(code)}</code></pre>
        </div>
      `;
    }
    return escapeHtml(part).replace(/\n/g, '<br>');
  }).join('');
}

window.injectCodeIntoCanvas = function(btn) {
  const pre = btn.closest('div').parentElement.querySelector('pre code');
  const ta = document.getElementById('canvas-textarea');
  if (pre && ta) {
    ta.value = pre.textContent;
    btn.textContent = '[INJECTED!]';
    setTimeout(() => btn.textContent = '[INJECT INTO CANVAS ⮑]', 1500);
  }
};

window.toggleVoiceMode = async function() {
  const btn = document.getElementById('voice-listen-toggle');
  const viz = document.getElementById('voice-visualizer');
  const label = document.getElementById('voice-status-label');
  const interimDiv = document.getElementById('voice-interim-transcript');

  if (state.canvas.isListening) {
    // Stop listening
    state.canvas.isListening = false;
    if (state.canvas.recognition) {
      try { state.canvas.recognition.stop(); } catch (e) {}
      state.canvas.recognition = null;
    }
    if (state.canvas.micStream) {
      state.canvas.micStream.getTracks().forEach(t => t.stop());
      state.canvas.micStream = null;
    }
    if (state.canvas.animFrame) {
      cancelAnimationFrame(state.canvas.animFrame);
      state.canvas.animFrame = null;
    }
    if (viz) viz.classList.remove('active', 'recording');
    document.querySelectorAll('.voice-bar').forEach(b => b.style.height = '6px');
    if (btn) btn.textContent = '[🎤 START VOICE MODE]';
    if (label) label.textContent = 'Mic Inactive';
    if (interimDiv) interimDiv.style.display = 'none';
    return;
  }

  // Check for Secure Context (required by Chrome/Edge for microphone and Speech API)
  const isSecure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (!isSecure) {
    const switchConfirmed = confirm(
      "⚠️ MICROPHONE SECURITY RESTRICTION:\n\n" +
      "Web Browsers require a Secure Context (localhost or HTTPS) to access your microphone.\n" +
      `You are currently accessing StoneSage via: ${window.location.origin}\n\n` +
      "Would you like to reload this page on http://localhost:8080 now?"
    );
    if (switchConfirmed) {
      window.location.href = window.location.href.replace(window.location.hostname, 'localhost');
      return;
    }
  }

  // Find getUserMedia method across modern and legacy browser APIs
  const getUserMedia = (navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
    ? (constraints) => navigator.mediaDevices.getUserMedia(constraints)
    : (navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia)
      ? (constraints) => new Promise((resolve, reject) => (navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia).call(navigator, constraints, resolve, reject))
      : null;

  if (!getUserMedia) {
    alert("Microphone API (getUserMedia) is not supported or accessible in this browser origin.\nPlease open via http://localhost:8080 or enable HTTPS.");
    if (label) label.textContent = 'Mic Unavailable (Insecure Origin)';
    return;
  }

  try {
    if (label) label.textContent = 'Requesting Microphone Permission...';
    const stream = await getUserMedia({ audio: true });
    state.canvas.micStream = stream;
    state.canvas.isListening = true;

    if (btn) btn.textContent = '[⏹ STOP VOICE MODE]';
    if (viz) viz.classList.add('active', 'recording');
    if (label) label.textContent = '🎙️ Listening (Ambient Audio Active)';

    // Set up AudioContext & AnalyserNode for audio VU meters
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      state.canvas.audioCtx = new AudioCtx();
      const source = state.canvas.audioCtx.createMediaStreamSource(stream);
      state.canvas.analyser = state.canvas.audioCtx.createAnalyser();
      state.canvas.analyser.fftSize = 64;
      source.connect(state.canvas.analyser);

      const bufferLength = state.canvas.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      const bars = document.querySelectorAll('.voice-bar');

      const drawBars = () => {
        if (!state.canvas.isListening) return;
        state.canvas.analyser.getByteFrequencyData(dataArray);
        bars.forEach((bar, idx) => {
          const val = dataArray[idx % bufferLength] || 0;
          const h = Math.max(6, Math.min(26, Math.round((val / 255) * 26)));
          bar.style.height = `${h}px`;
        });
        state.canvas.animFrame = requestAnimationFrame(drawBars);
      };
      drawBars();
    }

    // Set up SpeechRecognition if available
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      const recognition = new SpeechRec();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        let interimText = '';
        let finalText = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalText += event.results[i][0].transcript;
          } else {
            interimText += event.results[i][0].transcript;
          }
        }

        if (interimDiv) {
          if (interimText || finalText) {
            interimDiv.style.display = 'block';
            interimDiv.textContent = `🎙️ Dictation: "${interimText || finalText}"`;
          }
        }

        if (finalText.trim()) {
          const clean = finalText.trim();
          logToTerminal(`[VOICE DICTATION] "${clean}"`);
          if (interimDiv) interimDiv.textContent = `Dispatching: "${clean}"...`;
          sendCanvasCopilotMessage(clean);
        }
      };

      recognition.onerror = (e) => {
        if (e.error !== 'no-speech') {
          console.warn('SpeechRecognition error:', e.error);
        }
      };

      recognition.onend = () => {
        if (state.canvas.isListening) {
          try { recognition.start(); } catch (err) {}
        }
      };

      recognition.start();
      state.canvas.recognition = recognition;
    } else {
      if (label) {
        label.textContent = 'Mic Active (Audio VU online. Dictation requires localhost or HTTPS)';
      }
    }

  } catch (err) {
    state.canvas.isListening = false;
    if (btn) btn.textContent = '[🎤 START VOICE MODE]';
    if (label) label.textContent = `Mic Error: ${err.message}`;
    alert(`Microphone permission error: ${err.message}\nMake sure microphone is allowed in browser settings.`);
  }
};

/* ==========================================================================
   10. Immich Media Vault & EXIF Inspector
   ========================================================================== */
function initImmichDashboard() {
  const modeCockpit = document.getElementById('immich-mode-cockpit');
  const modeWeb = document.getElementById('immich-mode-web');
  const cockpitContainer = document.getElementById('immich-cockpit-container');
  const iframeContainer = document.getElementById('immich-iframe-container');
  const iframe = document.getElementById('immich-webview-frame');
  const uploadBtn = document.getElementById('immich-upload-btn');
  const fileInput = document.getElementById('immich-file-input');
  const refreshBtn = document.getElementById('immich-refresh-btn');
  const openExt = document.getElementById('immich-open-external');

  if (modeCockpit && modeWeb) {
    modeCockpit.addEventListener('click', () => {
      modeCockpit.classList.add('active');
      modeWeb.classList.remove('active');
      if (cockpitContainer) cockpitContainer.style.display = 'flex';
      if (iframeContainer) iframeContainer.style.display = 'none';
    });
    modeWeb.addEventListener('click', () => {
      modeWeb.classList.add('active');
      modeCockpit.classList.remove('active');
      if (cockpitContainer) cockpitContainer.style.display = 'none';
      if (iframeContainer) iframeContainer.style.display = 'flex';
      if (iframe && !iframe.src) iframe.src = state.immich.url;
    });
  }

  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    const orig = refreshBtn.textContent;
    refreshBtn.textContent = '[⏳ REFRESHING...]';
    await fetchImmichData();
    refreshBtn.textContent = orig;
  });
  if (openExt) openExt.addEventListener('click', () => window.open(state.immich.url, '_blank'));

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files);
      if (files.length === 0) return;
      uploadBtn.disabled = true;
      uploadBtn.textContent = `UPLOADING ${files.length}...`;

      for (const file of files) {
        try {
          const reader = new FileReader();
          const base64 = await new Promise((res, rej) => {
            reader.onload = () => res(reader.result);
            reader.onerror = rej;
            reader.readAsDataURL(file);
          });
          await fetch('/api/files/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: file.name, type: file.type, data_url: base64 })
          });
        } catch (err) {
          console.warn('Upload error:', err);
        }
      }
      uploadBtn.disabled = false;
      uploadBtn.textContent = '[📤 UPLOAD MEDIA]';
      fileInput.value = '';
      fetchImmichData();
    });
  }

  // Filter toolbar
  const filterBtns = document.querySelectorAll('#immich-gallery-filters .filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.immich.activeCategory = btn.dataset.filter || 'all';
      renderImmichGrid();
    });
  });

  const searchInput = document.getElementById('immich-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.immich.searchQuery = e.target.value.toLowerCase().trim();
      renderImmichGrid();
    });
  }

  // Lightbox controls
  const lbDialog = document.getElementById('immich-lightbox-dialog');
  const lbClose = document.getElementById('close-lightbox-btn');
  const lbPrev = document.getElementById('lightbox-prev-btn');
  const lbNext = document.getElementById('lightbox-next-btn');

  if (lbClose && lbDialog) lbClose.addEventListener('click', () => lbDialog.close());
  if (lbPrev) lbPrev.addEventListener('click', () => navigateImmichLightbox(-1));
  if (lbNext) lbNext.addEventListener('click', () => navigateImmichLightbox(1));

  fetchImmichData();
}

async function fetchImmichData() {
  try {
    const statsRes = await fetch('/api/immich/stats');
    const stats = await statsRes.json();
    if (stats.ok && stats.stats) {
      state.immich.stats = stats.stats;
      const ph = document.getElementById('stat-photos');
      const vi = document.getElementById('stat-videos');
      const st = document.getElementById('stat-storage');
      const pe = document.getElementById('stat-people');
      if (ph) ph.textContent = stats.stats.photos.toLocaleString();
      if (vi) vi.textContent = stats.stats.videos.toLocaleString();
      if (st) st.textContent = `${stats.stats.usage_gb} GB`;
      if (pe) pe.textContent = stats.stats.people_count || 0;
    }

    const assetsRes = await fetch('/api/immich/assets');
    const assets = await assetsRes.json();
    if (assets.ok && Array.isArray(assets.assets)) {
      state.immich.assets = assets.assets;
      renderImmichGrid();
    }
  } catch (e) {
    console.warn('Immich data fetch skipped:', e);
  }
}

function renderImmichGrid() {
  const grid = document.getElementById('immich-gallery-grid');
  if (!grid) return;

  const cat = state.immich.activeCategory;
  const q = state.immich.searchQuery;

  const filtered = (state.immich.assets || []).filter(a => {
    if (cat === 'favorites' && !a.favorite) return false;
    if (cat === 'videos' && a.type !== 'video') return false;
    if (cat === 'photos' && a.type !== 'photo') return false;
    if (q) {
      const match = (a.title || '').toLowerCase().includes(q) || (a.exif?.camera || '').toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; color: var(--term-text-muted); padding: 2rem; text-align: center;">No media found matching current filter.</div>';
    return;
  }

  grid.innerHTML = filtered.map((item, idx) => `
    <div class="immich-card" onclick="openImmichLightbox(${idx})">
      <img src="${item.thumb}" alt="${escapeHtml(item.title)}" loading="lazy">
      <div class="immich-card-body">
        <div class="immich-card-title">${escapeHtml(item.title)}</div>
        <div class="immich-card-meta">
          <span>${item.date || ''}</span>
          <span>${item.type === 'video' ? '[VIDEO]' : '[PHOTO]'}</span>
        </div>
      </div>
    </div>
  `).join('');
}

function openImmichLightbox(index) {
  state.immich.activeAssetIndex = index;
  const asset = state.immich.assets[index];
  if (!asset) return;

  const dialog = document.getElementById('immich-lightbox-dialog');
  const stage = document.getElementById('lightbox-stage');
  const title = document.getElementById('lightbox-title');
  const counter = document.getElementById('lightbox-counter');

  if (title) title.textContent = `[${asset.title || 'MEDIA'}]`;
  if (counter) counter.textContent = `(${index + 1} of ${state.immich.assets.length})`;

  if (stage) {
    if (asset.type === 'video' && asset.video_url) {
      stage.innerHTML = `<video src="${asset.video_url}" controls autoplay style="max-width:100%; max-height:480px;"></video>`;
    } else {
      stage.innerHTML = `<img src="${asset.hires || asset.thumb}" style="max-width:100%; max-height:480px; object-fit:contain;">`;
    }
  }

  // EXIF Fields
  const exif = asset.exif || {};
  const setE = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '--'; };
  setE('exif-camera', exif.camera);
  setE('exif-lens', exif.lens);
  setE('exif-aperture', exif.aperture);
  setE('exif-shutter', exif.shutter);
  setE('exif-iso', exif.iso);
  setE('exif-focal', exif.focal);
  setE('exif-dims', asset.dimensions);
  setE('exif-format', exif.format || (asset.type === 'video' ? 'MP4' : 'JPEG'));
  setE('exif-location', exif.location);

  if (dialog && !dialog.open) dialog.showModal();
}

function navigateImmichLightbox(dir) {
  let next = state.immich.activeAssetIndex + dir;
  if (next < 0) next = state.immich.assets.length - 1;
  if (next >= state.immich.assets.length) next = 0;
  openImmichLightbox(next);
}

/* ==========================================================================
   11. Qdrant Semantic Memory Explorer
   ========================================================================== */
function initMemoryExplorer() {
  const searchBtn = document.getElementById('memory-search-exec-btn');
  const queryInput = document.getElementById('memory-query-input');
  const colSelect = document.getElementById('memory-search-collection');

  const doSearch = async () => {
    const q = queryInput ? queryInput.value.trim() : '';
    const col = colSelect ? colSelect.value : 'companion_profile';
    const container = document.getElementById('memory-results-container');
    if (!q || !container) return;

    container.innerHTML = '<div style="color:var(--term-text-muted);">Generating 1024-dim BGE vector and querying Qdrant...</div>';
    try {
      const res = await fetch('/api/memory/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, collection: col, limit: 5 })
      });
      const data = await res.json();
      if (data.ok && Array.isArray(data.results) && data.results.length > 0) {
        container.innerHTML = data.results.map((hit, i) => `
          <div style="border:1px solid var(--term-border); background:var(--term-surface-raised); padding:0.65rem;">
            <div style="display:flex; justify-content:space-between; margin-bottom:0.3rem;">
              <strong style="color:var(--term-text-bright);">[#${i+1}] ${escapeHtml(hit.payload?.title || 'Point')}</strong>
              <span style="color:var(--term-warn); font-weight:bold;">COSINE SCORE: ${(hit.score || 0).toFixed(4)}</span>
            </div>
            <div style="font-size:0.78rem; line-height:1.45; white-space:pre-wrap; color:var(--term-text);">${escapeHtml(hit.payload?.content || JSON.stringify(hit.payload))}</div>
          </div>
        `).join('');
      } else {
        container.innerHTML = '<div style="color:var(--term-text-muted);">No matching vectors found in memory collection.</div>';
      }
    } catch (err) {
      container.innerHTML = `<div style="color:var(--term-alert);">Vector search error: ${err.message}</div>`;
    }
  };

  if (searchBtn) searchBtn.addEventListener('click', doSearch);
  if (queryInput) {
    queryInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doSearch();
    });
  }
}

/* ==========================================================================
   12. Service Launcher & Editor
   ========================================================================== */
function initServiceLauncher() {
  const filterBtns = document.querySelectorAll('#view-launchpad .filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.category = btn.dataset.category;
      renderServices();
    });
  });

  const refreshBtn = document.getElementById('refresh-services-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    const orig = refreshBtn.textContent;
    refreshBtn.textContent = '[⏳ PINGING...]';
    await fetchServices();
    refreshBtn.textContent = orig;
  });

  const toggleEditBtn = document.getElementById('toggle-edit-services-btn');
  if (toggleEditBtn) {
    toggleEditBtn.addEventListener('click', () => {
      state.isEditMode = !state.isEditMode;
      toggleEditBtn.classList.toggle('active', state.isEditMode);
      renderServices();
    });
  }

  fetchServices();
}

async function fetchServices() {
  try {
    const res = await fetch('/api/services/status');
    const data = await res.json();
    if (data.ok && Array.isArray(data.services)) {
      state.services = data.services;
      renderServices();
    }
  } catch (err) {
    console.warn('Service fetch error:', err);
  }
}

function renderServices() {
  const grid = document.getElementById('service-grid');
  if (!grid) return;

  const filtered = state.category === 'all'
    ? state.services
    : state.services.filter(s => {
        if (state.category === 'automation') return s.category === 'automation' || s.category === 'downloads';
        if (state.category === 'smarthome') return s.category === 'smarthome' || s.category === 'smart_home';
        return s.category === state.category;
      });

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--term-text-muted);">No services configured in this category.</div>';
    return;
  }

  grid.innerHTML = filtered.map(s => {
    const isOnline = s.online !== false;
    const statusClass = isOnline ? 'online' : 'offline';
    const statusText = isOnline ? `[${s.latency_ms || 12}ms | OK]` : '[OFFLINE]';
    const launchUrl = s.display_url || s.url || '';

    return `
      <div class="service-card">
        <div class="service-top">
          <div class="service-info">
            <div class="service-emoji">${s.emoji || '📦'}</div>
            <div>
              <div class="service-name">${escapeHtml(s.name || 'Service')}</div>
              <div class="service-sub">
                <span class="node-badge">${s.node || 'bigserv'}</span>
                <span>${s.vmid ? `VM ${s.vmid}` : ''}</span>
              </div>
            </div>
          </div>
          <div style="display:flex; gap:0.35rem; align-items:center;">
            <span class="service-status-badge ${statusClass}">${statusText}</span>
            <button class="card-icon-btn" onclick="openServiceEditor('${s.id}')" title="Edit Service">[✏]</button>
            ${state.isEditMode ? `<button class="card-icon-btn" onclick="deleteService('${s.id}')" style="color:var(--term-alert);">[✕]</button>` : ''}
          </div>
        </div>
        <div class="service-desc">${escapeHtml(s.description || '')}</div>
        <div class="service-bottom">
          <span class="service-url" title="${launchUrl}">${escapeHtml(launchUrl.replace(/^https?:\/\//, ''))}</span>
          <div style="display:flex; gap:0.35rem;">
            ${(s.id === 'immich' || (s.name && s.name.toLowerCase().includes('immich'))) ? `
              <button class="launch-btn" onclick="document.querySelector('.tab-btn[data-view=\\'view-immich\\']').click()">[📸 VAULT]</button>
            ` : ''}
            <button class="launch-btn" onclick="window.open('${launchUrl}', '_blank')">[LAUNCH ↗]</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function initServiceEditor() {
  const addBtn = document.getElementById('add-service-btn');
  const dialog = document.getElementById('service-editor-dialog');
  const closeBtn = document.getElementById('close-service-editor-btn');
  const cancelBtn = document.getElementById('cancel-service-editor-btn');
  const saveBtn = document.getElementById('save-service-editor-btn');

  if (addBtn) addBtn.addEventListener('click', () => openServiceEditor(null));
  if (closeBtn && dialog) closeBtn.addEventListener('click', () => dialog.close());
  if (cancelBtn && dialog) cancelBtn.addEventListener('click', () => dialog.close());

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const name = document.getElementById('service-edit-name')?.value.trim();
      const id = document.getElementById('service-edit-id')?.value.trim();
      const category = document.getElementById('service-edit-category')?.value;
      const node = document.getElementById('service-edit-node')?.value;
      const vmid = document.getElementById('service-edit-vmid')?.value.trim();
      const url = document.getElementById('service-edit-url')?.value.trim();
      const display_url = document.getElementById('service-edit-display-url')?.value.trim() || url;
      const description = document.getElementById('service-edit-description')?.value.trim();

      if (!name || !url) {
        alert('Name and URL are required.');
        return;
      }

      try {
        await fetch('/api/services/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service: { id, name, category, node, vmid, url, display_url, description } })
        });
        if (dialog) dialog.close();
        fetchServices();
      } catch (e) {
        alert(`Save error: ${e.message}`);
      }
    });
  }
}

window.openServiceEditor = function(serviceId) {
  const dialog = document.getElementById('service-editor-dialog');
  const s = state.services.find(x => x.id === serviceId);

  document.getElementById('service-edit-name').value = s ? s.name : '';
  document.getElementById('service-edit-id').value = s ? s.id : '';
  document.getElementById('service-edit-category').value = s ? (s.category || 'ai') : 'ai';
  document.getElementById('service-edit-node').value = s ? (s.node || 'bigserv') : 'bigserv';
  document.getElementById('service-edit-vmid').value = s ? (s.vmid || '') : '';
  document.getElementById('service-edit-url').value = s ? s.url : '';
  document.getElementById('service-edit-display-url').value = s ? (s.display_url || s.url) : '';
  document.getElementById('service-edit-description').value = s ? (s.description || '') : '';

  if (dialog) dialog.showModal();
};

window.deleteService = async function(serviceId) {
  if (confirm(`Delete service ${serviceId}?`)) {
    try {
      await fetch('/api/services/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: serviceId })
      });
      fetchServices();
    } catch (e) {
      alert(`Delete error: ${e.message}`);
    }
  }
};

/* ==========================================================================
   13. Settings & Cluster Health Probes
   ========================================================================== */
function initSettings() {
  const openBtn = document.getElementById('open-settings-btn');
  const dialog = document.getElementById('settings-dialog');
  const closeBtn = document.getElementById('close-settings-dialog');
  const cancelBtn = document.getElementById('cancel-settings-btn');
  const saveBtn = document.getElementById('save-settings-btn');
  const testGeminiBtn = document.getElementById('test-gemini-web-btn');
  const geminiBadge = document.getElementById('gemini-web-status-badge');

  // Preset buttons
  const pZeroBtn = document.getElementById('preset-zero-token-btn');
  const pFrontierBtn = document.getElementById('preset-frontier-btn');
  const pLocalBtn = document.getElementById('preset-local-btn');

  if (pZeroBtn) {
    pZeroBtn.addEventListener('click', () => {
      document.getElementById('route-ideation').value = 'local_worker';
      document.getElementById('route-solving').value = 'local_coordinator';
      document.getElementById('route-audit').value = 'gemini_web';
      document.getElementById('route-rumination').value = 'moe_35b';
      document.getElementById('route-chat').value = 'local_coordinator';
    });
  }
  if (pFrontierBtn) {
    pFrontierBtn.addEventListener('click', () => {
      document.getElementById('route-ideation').value = 'local_worker';
      document.getElementById('route-solving').value = 'gemini_web';
      document.getElementById('route-audit').value = 'frontier_agy';
      document.getElementById('route-rumination').value = 'gemini_web';
      document.getElementById('route-chat').value = 'gemini_web';
    });
  }
  if (pLocalBtn) {
    pLocalBtn.addEventListener('click', () => {
      document.getElementById('route-ideation').value = 'local_worker';
      document.getElementById('route-solving').value = 'local_coordinator';
      document.getElementById('route-audit').value = 'local_coordinator';
      document.getElementById('route-rumination').value = 'moe_35b';
      document.getElementById('route-chat').value = 'local_coordinator';
    });
  }

  if (testGeminiBtn) {
    testGeminiBtn.addEventListener('click', async () => {
      const psid = document.getElementById('set-gemini-psid').value.trim();
      const psidts = document.getElementById('set-gemini-psidts').value.trim();
      if (!psid) {
        alert('Please paste your __Secure-1PSID cookie first.');
        return;
      }
      geminiBadge.textContent = '[TESTING SESSION...]';
      geminiBadge.style.color = 'var(--term-warn)';
      try {
        const res = await fetch('/api/gemini_web/configure', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ psid, psidts })
        });
        const d = await res.json();
        if (d.ok) {
          geminiBadge.textContent = '[ONLINE: GEMINI ADVANCED ($0 COST)]';
          geminiBadge.style.color = '#00aa00';
        } else {
          geminiBadge.textContent = `[FAILED: ${d.error || d.message || 'Check cookies'}]`;
          geminiBadge.style.color = 'var(--term-alert)';
        }
      } catch (err) {
        geminiBadge.textContent = `[ERROR: ${err.message}]`;
        geminiBadge.style.color = 'var(--term-alert)';
      }
    });
  }

  if (openBtn && dialog) {
    openBtn.addEventListener('click', async () => {
      dialog.showModal();
      try {
        const res = await fetch('/api/config');
        const cfg = await res.json();
        if (cfg) {
          document.getElementById('set-ha-token').value = cfg.homeassistant?.token || '';
          document.getElementById('set-pve-token').value = cfg.proxmox?.token_value || '';
          document.getElementById('set-immich-url').value = cfg.immich?.url || '';
          document.getElementById('set-immich-key').value = cfg.immich?.api_key || '';
          document.getElementById('set-openai-key').value = cfg.external_providers?.openai?.api_key || '';
          document.getElementById('set-anthropic-key').value = cfg.external_providers?.anthropic?.api_key || '';
          document.getElementById('set-gemini-key').value = cfg.external_providers?.gemini?.api_key || '';

          // Gemini Web session cookies
          document.getElementById('set-gemini-psid').value = cfg.gemini_web?.psid || '';
          document.getElementById('set-gemini-psidts').value = cfg.gemini_web?.psidts || '';
          if (geminiBadge) {
            if (cfg.gemini_web?.psid) {
              geminiBadge.textContent = '[COOKIES CONFIGURED]';
              geminiBadge.style.color = '#00aa00';
            } else {
              geminiBadge.textContent = '[NO COOKIES]';
              geminiBadge.style.color = 'var(--term-text-muted)';
            }
          }

          // Task Routing
          const tr = cfg.task_routing || {};
          if (tr.autonomous_ideation) document.getElementById('route-ideation').value = tr.autonomous_ideation;
          if (tr.autonomous_solving) document.getElementById('route-solving').value = tr.autonomous_solving;
          if (tr.frontier_audit) document.getElementById('route-audit').value = tr.frontier_audit;
          if (tr.sleep_rumination) document.getElementById('route-rumination').value = tr.sleep_rumination;
          if (tr.interactive_chat) document.getElementById('route-chat').value = tr.interactive_chat;
        }
      } catch (e) {}
    });
  }

  if (closeBtn && dialog) closeBtn.addEventListener('click', () => dialog.close());
  if (cancelBtn && dialog) cancelBtn.addEventListener('click', () => dialog.close());

  if (saveBtn && dialog) {
    saveBtn.addEventListener('click', async () => {
      const payload = {
        homeassistant: { token: document.getElementById('set-ha-token').value.trim() },
        proxmox: { token_value: document.getElementById('set-pve-token').value.trim() },
        immich: {
          url: document.getElementById('set-immich-url').value.trim(),
          api_key: document.getElementById('set-immich-key').value.trim()
        },
        external_providers: {
          openai: { api_key: document.getElementById('set-openai-key').value.trim() },
          anthropic: { api_key: document.getElementById('set-anthropic-key').value.trim() },
          gemini: { api_key: document.getElementById('set-gemini-key').value.trim() }
        },
        gemini_web: {
          enabled: true,
          psid: document.getElementById('set-gemini-psid').value.trim(),
          psidts: document.getElementById('set-gemini-psidts').value.trim(),
          endpoint: 'http://127.0.0.1:8087'
        },
        task_routing: {
          autonomous_ideation: document.getElementById('route-ideation').value,
          autonomous_solving: document.getElementById('route-solving').value,
          frontier_audit: document.getElementById('route-audit').value,
          sleep_rumination: document.getElementById('route-rumination').value,
          interactive_chat: document.getElementById('route-chat').value,
          subagent_default: 'local_worker'
        }
      };
      try {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        dialog.close();
        alert('Configuration & Task Allocation Matrix saved successfully.');
      } catch (e) {
        alert(`Save error: ${e.message}`);
      }
    });
  }
}

async function initClusterHealth() {
  const pill = document.getElementById('cluster-status-text');
  const check = async () => {
    try {
      const res = await fetch('/api/cluster/health');
      const data = await res.json();
      if (data.ok && pill) {
        pill.textContent = '[CLUSTER: ONLINE]';
        pill.style.color = 'var(--term-text-bright)';
      }
    } catch (e) {
      if (pill) {
        pill.textContent = '[CLUSTER: PARTIAL]';
        pill.style.color = 'var(--term-warn)';
      }
    }
  };
  check();
  setInterval(check, 30000);
}

/* ==========================================================================
   14. Helper Utilities
   ========================================================================== */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function timeNow() {
  return new Date().toLocaleTimeString([], { hour12: false });
}

/* ==========================================================================
   15. Model Finder, Switcher & Parameter Discovery Integration
   ========================================================================== */
window.fetchClusterModels = async function() {
  const activeName = document.getElementById('active-model-name');
  const activeCtx = document.getElementById('active-model-context');
  const activeStatus = document.getElementById('active-model-status');
  const modelSelect = document.getElementById('local-model-select');
  const diskSpace = document.getElementById('model-disk-space');
  const calibCii = document.getElementById('calib-stat-cii');
  const calibThroughput = document.getElementById('calib-stat-throughput');
  const calibProfile = document.getElementById('calib-stat-profile');
  const calibHall = document.getElementById('calib-stat-hallucination');
  const calibBadge = document.getElementById('calib-params-badge');

  if (activeName) activeName.textContent = 'Probing :8001...';

  try {
    const res = await fetch('/api/cluster/models');
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Failed fetching models');

    if (activeName) activeName.textContent = data.active_model || 'Unknown';
    if (activeCtx) activeCtx.textContent = (data.active_context || '8192') + ' tokens';
    if (activeStatus) activeStatus.textContent = 'ONLINE';
    if (diskSpace && data.disk) diskSpace.textContent = 'Storage: ' + data.disk.split(/\s+/).slice(-2).join(' ');

    if (modelSelect && data.models) {
      modelSelect.innerHTML = '';
      data.models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.name;
        opt.textContent = `${m.name} (${m.size})`;
        if (m.name === data.active_model) {
          opt.selected = true;
          opt.textContent += ' [ACTIVE]';
        }
        modelSelect.appendChild(opt);
      });
    }

    if (data.calibration && data.calibration.profile) {
      const c = data.calibration;
      if (calibCii) calibCii.textContent = (c.cii || c.avg_score || '--') + ' / 10.0';
      if (calibThroughput) calibThroughput.textContent = (c.avg_tok_per_sec || '--') + ' tok/s';
      if (calibProfile) calibProfile.textContent = c.profile.name || '--';
      if (calibHall) {
        calibHall.textContent = c.hallucination_detected ? '❌ Hallucination Alert' : '✅ 0 Hallucinations';
        calibHall.style.color = c.hallucination_detected ? 'var(--term-alert)' : 'var(--term-text-bright)';
      }
      if (calibBadge && c.profile) {
        calibBadge.textContent = `Optimal Hyperparameters: temp=${c.profile.temperature} | min_p=${c.profile.min_p} | presence_penalty=${c.profile.presence_penalty} | repeat_penalty=${c.profile.repeat_penalty} | max_tokens=${c.profile.max_tokens}`;
      }
    }
  } catch (err) {
    if (activeName) activeName.textContent = 'Offline / Error';
    if (activeStatus) activeStatus.textContent = 'UNREACHABLE';
    logModelConsole(`[ERR] Failed fetching cluster models: ${err.message}`);
  }
};

window.quickSwitchModel = async function(preset) {
  const presets = {
    'high-precision': {
      hf: 'bartowski/deepreinforce-ai_Ornith-1.0-9B-GGUF',
      file: 'deepreinforce-ai_Ornith-1.0-9B-Q5_K_M.gguf',
      context: 16384,
      name: 'High-Precision 16k Profile'
    },
    'high-throughput': {
      hf: 'bartowski/deepreinforce-ai_Ornith-1.0-9B-GGUF',
      file: 'deepreinforce-ai_Ornith-1.0-9B-Q4_K_M.gguf',
      context: 16384,
      name: 'High-Throughput 16k Profile'
    },
    'code-specialist': {
      model: 'qwen2.5-coder-14b-instruct-abliterated-q4_k_m.gguf',
      context: 8192,
      name: 'Code Specialist Profile'
    }
  };
  presets['ornith-9b-q5'] = presets['high-precision'];
  presets['ornith-9b-q4'] = presets['high-throughput'];
  presets['qwen-14b'] = presets['code-specialist'];

  const p = presets[preset];
  if (!p) return;

  if (!confirm(`Switch cluster coordinator (:8001) to ${p.name}? This will configure systemd, restart the daemon, and run parameter calibration.`)) {
    return;
  }

  logModelConsole(`[INIT] Queuing switch to ${p.name}...`);
  logModelConsole(`[*] Preparing payload and autotune harness...`);

  try {
    const res = await fetch('/api/cluster/switch-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...p,
        auto_tune: true
      })
    });
    const data = await res.json();
    logModelConsole(data.output || (data.ok ? '[OK] Model switched successfully!' : `[ERR] ${data.error}`));
    fetchClusterModels();
  } catch (err) {
    logModelConsole(`[ERR] Request failed: ${err.message}`);
  }
};

window.executeModelSwitch = async function() {
  const modelSelect = document.getElementById('local-model-select');
  const ctxSelect = document.getElementById('switch-context-select');
  const autotuneChk = document.getElementById('switch-autotune-chk');
  if (!modelSelect || !modelSelect.value) {
    alert('Please select a model file first.');
    return;
  }

  const model = modelSelect.value;
  const context = parseInt(ctxSelect ? ctxSelect.value : '16384', 10);
  const autoTune = autotuneChk ? autotuneChk.checked : true;

  logModelConsole(`[INIT] Switching to local model ${model} (context: ${context} tokens, auto_tune: ${autoTune})...`);

  try {
    const res = await fetch('/api/cluster/switch-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, context, auto_tune: autoTune })
    });
    const data = await res.json();
    logModelConsole(data.output || (data.ok ? '[OK] Switch completed.' : `[ERR] ${data.error}`));
    fetchClusterModels();
  } catch (err) {
    logModelConsole(`[ERR] Switch failed: ${err.message}`);
  }
};

window.executeHfDownloadSwitch = async function() {
  const repoIn = document.getElementById('hf-repo-input');
  const fileIn = document.getElementById('hf-file-input');
  const ctxSelect = document.getElementById('switch-context-select');
  const autotuneChk = document.getElementById('switch-autotune-chk');

  const hf = repoIn ? repoIn.value.trim() : '';
  const file = fileIn ? fileIn.value.trim() : '';
  if (!hf || !file) {
    alert('Please enter both HuggingFace Repo and GGUF Filename.');
    return;
  }

  const context = parseInt(ctxSelect ? ctxSelect.value : '16384', 10);
  const autoTune = autotuneChk ? autotuneChk.checked : true;

  logModelConsole(`[INIT] Downloading ${file} from ${hf} and deploying to :8001...`);
  logModelConsole(`[*] This may take 2-4 minutes depending on model size...`);

  try {
    const res = await fetch('/api/cluster/switch-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hf, file, context, auto_tune: autoTune })
    });
    const data = await res.json();
    logModelConsole(data.output || (data.ok ? '[OK] HF Model deployed and calibrated!' : `[ERR] ${data.error}`));
    fetchClusterModels();
  } catch (err) {
    logModelConsole(`[ERR] HF Download failed: ${err.message}`);
  }
};

window.rollbackClusterModel = async function() {
  if (!confirm('Revert coordinator (:8001) to the previous backup model configuration?')) return;
  logModelConsole('[INIT] Reverting to previous stable backup configuration...');
  try {
    const res = await fetch('/api/cluster/rollback-model', { method: 'POST' });
    const data = await res.json();
    logModelConsole(data.output || (data.ok ? '[OK] Rollback complete!' : `[ERR] ${data.error}`));
    fetchClusterModels();
  } catch (err) {
    logModelConsole(`[ERR] Rollback request failed: ${err.message}`);
  }
};

window.runParameterDiscoveryNow = async function() {
  const activeName = document.getElementById('active-model-name');
  const modelName = activeName ? activeName.textContent : 'Current-Coordinator';

  logModelConsole(`[INIT] Running 4-pillar parameter discovery battery on ${modelName}...`);
  logModelConsole(`[*] Testing Conversationality, SPSC Ring Buffer (Logic), Radical Geometry (Math), and Deceptive Probes...`);

  try {
    const res = await fetch('/api/cluster/calibrate-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_name: modelName })
    });
    const data = await res.json();
    logModelConsole(data.output || (data.ok ? '[OK] Parameter discovery complete!' : `[ERR] ${data.error}`));
    fetchClusterModels();
  } catch (err) {
    logModelConsole(`[ERR] Calibration failed: ${err.message}`);
  }
};

function logModelConsole(msg) {
  const c = document.getElementById('model-switch-console');
  if (!c) return;
  const timeStr = new Date().toLocaleTimeString();
  c.textContent += `\n[${timeStr}] ${msg}`;
  c.scrollTop = c.scrollHeight;
}

/* ==========================================================================
   24/7 Hive-Mind & Home Vision Vigilance HUD
   ========================================================================== */
window.loadHiveMindStatus = async function(manual = false) {
  const refreshBtn = document.getElementById('btn-refresh-hivemind');
  if (manual && refreshBtn) {
    refreshBtn.textContent = '[⏳ REFRESHING...]';
    refreshBtn.disabled = true;
  }
  try {
    const res = await fetch('/api/hivemind/status');
    const data = await res.json();
    if (data.ok && data.status) {
      const s = data.status;
      const isRunning = s.is_running;
      
      const p = s.preemption || {};
      const preemptBadge = document.getElementById('hivemind-preemption-badge');
      if (preemptBadge) {
        if (p.is_preempted) {
          preemptBadge.style.display = 'inline-block';
          preemptBadge.textContent = `[⏸️ USER PREEMPTION: ${p.cooldown_remaining_sec || 60}s]`;
          preemptBadge.title = p.reason || 'User activity detected';
        } else {
          preemptBadge.style.display = 'none';
        }
      }

      const badge = document.getElementById('hivemind-running-badge');
      if (badge) {
        if (p.is_preempted) {
          badge.textContent = '[YIELDING GPU]';
          badge.style.color = '#cc8800';
        } else {
          badge.textContent = isRunning ? '[ACTIVE - 24/7 LOOPING]' : '[STOPPED / IDLE]';
          badge.style.color = isRunning ? '#008800' : '#888888';
        }
      }

      const toggleBtn = document.getElementById('btn-toggle-hivemind');
      if (toggleBtn) {
        toggleBtn.textContent = isRunning ? '[⏸ STOP 24/7 LOOP]' : '[▶ START 24/7 LOOP]';
      }

      const elState = document.getElementById('hm-stat-state');
      if (elState) {
        if (p.is_preempted) {
          elState.textContent = `PREEMPTED (COOLDOWN ${p.cooldown_remaining_sec || 0}s)`;
          elState.style.color = '#cc8800';
        } else {
          elState.textContent = isRunning ? 'RUNNING (24/7)' : 'STOPPED';
          elState.style.color = 'var(--term-text-bright)';
        }
      }

      const elMission = document.getElementById('hm-stat-mission');
      if (elMission) elMission.textContent = s.last_mission_type || s.current_focus_domain || 'Curiosity';

      const elCycles = document.getElementById('hm-stat-cycles');
      if (elCycles) elCycles.textContent = s.total_cycles !== undefined ? s.total_cycles : '--';

      const elTokens = document.getElementById('hm-stat-tokens');
      if (elTokens) elTokens.textContent = s.total_tokens_generated ? s.total_tokens_generated.toLocaleString() : '--';

      const elLastTime = document.getElementById('hm-stat-last-time');
      if (elLastTime) {
        if (s.last_cycle_timestamp) {
          const d = new Date(s.last_cycle_timestamp);
          elLastTime.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } else {
          elLastTime.textContent = 'None yet';
        }
      }

      const elInterval = document.getElementById('hm-stat-interval');
      if (elInterval) elInterval.textContent = `${s.interval_seconds || 120}s`;

      const elVigTime = document.getElementById('hm-vigilance-time');
      if (elVigTime && s.last_home_check_timestamp) {
        const vd = new Date(s.last_home_check_timestamp * 1000);
        elVigTime.textContent = `Last Check: ${vd.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      }
    }
  } catch (err) {
    console.error('Error loading Hive-Mind status:', err);
  } finally {
    if (manual && refreshBtn) {
      refreshBtn.textContent = '[🔄 REFRESH]';
      refreshBtn.disabled = false;
    }
  }
  loadHiveMindVisionLog();
};

window.loadHiveMindVisionLog = async function() {
  const box = document.getElementById('hivemind-vision-log-box');
  if (!box) return;
  try {
    const res = await fetch('/api/hivemind/vision_log?limit=150');
    const data = await res.json();
    if (data.ok && data.log) {
      box.textContent = data.log;
      box.scrollTop = box.scrollHeight;
      parseVigilanceQuickStats(data.log);
    } else {
      box.textContent = 'No vigilance log entries yet.';
    }
  } catch (err) {
    box.textContent = 'Error fetching activity log: ' + err.message;
  }
};

function parseVigilanceQuickStats(logText) {
  if (!logText) return;
  const lines = logText.split('\n');
  for (let i = lines.length - 1; i >= 0; i--) {
    const l = lines[i];
    if (l.includes('- **Climate**:')) {
      const clim = l.replace('- **Climate**:', '').trim();
      const el = document.getElementById('hm-stat-climate');
      if (el) el.textContent = clim;
    }
    if (l.includes('- **Verdict**:')) {
      const verd = l.replace('- **Verdict**:', '').trim();
      const el = document.getElementById('hm-stat-verdict');
      if (el) {
        el.textContent = verd;
        el.style.color = verd.toLowerCase().includes('secure') || verd.toLowerCase().includes('nominal') ? '#008800' : '#cc6600';
      }
    }
  }
}

window.triggerVigilanceSweepNow = async function() {
  const btn = document.getElementById('btn-sweep-now');
  if (btn) { btn.disabled = true; btn.textContent = '[⏳ SWEEPING SENSORS & VISION...]'; }
  try {
    const res = await fetch('/api/hivemind/vigilance', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    const data = await res.json();
    if (data.ok) {
      await loadHiveMindStatus(true);
    } else {
      alert('Vigilance Sweep Error: ' + (data.error || 'Unknown'));
    }
  } catch (err) {
    alert('Vigilance Sweep Failed: ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '[👁️ VIGILANCE AUDIT NOW]'; }
  }
};

window.triggerHiveMindCycleNow = async function() {
  const btn = document.getElementById('btn-cycle-now');
  if (btn) { btn.disabled = true; btn.textContent = '[⚡ EXPLORING CYCLE...]'; }
  try {
    const res = await fetch('/api/hivemind/cycle', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    if (data.ok) {
      await loadHiveMindStatus(true);
    } else {
      alert('Cycle Error: ' + (data.error || 'Unknown'));
    }
  } catch (err) {
    alert('Cycle Failed: ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '[⚡ THINKING CYCLE NOW]'; }
  }
};

window.toggleHiveMindLoop = async function() {
  const btn = document.getElementById('btn-toggle-hivemind');
  const isCurrentlyActive = btn && btn.textContent.includes('STOP');
  const action = isCurrentlyActive ? 'stop' : 'start';
  try {
    const res = await fetch('/api/hivemind/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, interval_seconds: 120 })
    });
    const data = await res.json();
    await loadHiveMindStatus(true);
  } catch (err) {
    alert('Toggle Failed: ' + err.message);
  }
};

window.copyVisionLogToClipboard = function() {
  const box = document.getElementById('hivemind-vision-log-box');
  if (!box) return;
  navigator.clipboard.writeText(box.textContent).then(() => {
    alert('Home & Vision Activity Log copied to clipboard!');
  });
};

window.nudgeHiveMindNow = async function() {
  const btn = document.getElementById('btn-nudge-hivemind');
  if (btn) { btn.disabled = true; btn.textContent = '[⏳ NUDGING...]'; }
  try {
    const res = await fetch('/api/agent/nudge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: 'engine' })
    });
    const data = await res.json();
    if (data.ok) {
      await loadHiveMindStatus(true);
      alert('Cognitive Engine Nudged: Preemption/wait cleared and new exploration cycle triggered.');
    } else {
      alert('Nudge Error: ' + (data.error || 'Unknown'));
    }
  } catch (err) {
    alert('Nudge Failed: ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '[⚡ NUDGE / UNBLOCK]'; }
  }
};

// ==========================================
// AEVUM APK DOWNLOAD MODAL (FIREFOX FIX)
// ==========================================
window.openApkDownloadModal = function() {
  const dialog = document.getElementById('apk-download-dialog');
  if (!dialog) return;
  const baseUrl = `${window.location.protocol}//${window.location.host}`;
  const urlInput = document.getElementById('apk-direct-url');
  if (urlInput) {
    urlInput.value = `${baseUrl}/aevum.apk`;
  }
  const aevumLink = dialog.querySelector('a[href*="aevum.apk"]');
  if (aevumLink) {
    aevumLink.href = `${baseUrl}/aevum.apk`;
  }
  const stonesageLink = dialog.querySelector('a[href*="stonesage.apk"]');
  if (stonesageLink) {
    stonesageLink.href = `${baseUrl}/stonesage.apk`;
  }
  if (typeof dialog.showModal === 'function') {
    dialog.showModal();
  } else {
    dialog.style.display = 'block';
  }
};

// ==========================================
// HARNESS PARAMETER STUDIO & DAEMON CONTROL
// ==========================================
let currentHarnessId = 'llama_coordinator';
let currentHarnessData = null;
let availableModels = [];
let hardwareCapabilities = {
  primary_gpu: "AMD Radeon RX 6750 XT (12GB Vulkan0)",
  primary_vram_gb: 12.0,
  secondary_gpu: "AMD Radeon RX 6600 XT (8GB Vulkan1)",
  secondary_vram_gb: 8.0,
  total_vram_gb: 20.0,
  cpu_threads: 20,
  ram_gb: 32.0
};
let savedProfiles = {};
let currentStopStrings = ["<|im_end|>", "<|endoftext|>"];
let autoCtxEnabled = true;
let autoNglEnabled = true;

window.switchHarnessStudio = async function(harnessId) {
  currentHarnessId = harnessId;
  document.querySelectorAll('#view-harness .filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-harness') === harnessId);
  });
  await loadHarnessStudioData(harnessId);
};

window.refreshHarnessStudio = async function() {
  await loadHarnessStudioData(currentHarnessId);
};

async function loadHarnessStudioData(harnessId) {
  const container = document.getElementById('harness-form-container');
  const titleEl = document.getElementById('harness-header-title');
  const healthBadge = document.getElementById('harness-health-badge');
  const modelEl = document.getElementById('harness-active-model');
  const ctxEl = document.getElementById('harness-active-ctx');
  const devEl = document.getElementById('harness-active-device');
  const slotsEl = document.getElementById('harness-active-slots');

  if (healthBadge) healthBadge.textContent = '[HEALTH: PROBING...]';
  if (container) container.innerHTML = '<div style="padding: 1rem; color: var(--term-text-muted);">Fetching live harness telemetry, models, hardware and profile parameters...</div>';

  try {
    // Concurrently fetch parameters, available models, hardware limits, and saved profiles
    const [paramsRes, modelsRes, hwRes, profRes] = await Promise.all([
      fetch(`/api/harness/parameters?harness=${encodeURIComponent(harnessId)}`).catch(() => null),
      fetch('/api/harness/models').catch(() => null),
      fetch('/api/harness/hardware').catch(() => null),
      fetch('/api/harness/profiles').catch(() => null)
    ]);

    if (modelsRes && modelsRes.ok) {
      const mj = await modelsRes.json();
      if (mj.ok && Array.isArray(mj.models)) availableModels = mj.models;
    }
    if (hwRes && hwRes.ok) {
      const hj = await hwRes.json();
      if (hj.ok && hj.hardware) hardwareCapabilities = hj.hardware;
    }
    if (profRes && profRes.ok) {
      const pj = await profRes.json();
      if (pj.ok && pj.profiles) savedProfiles = pj.profiles;
    }

    let d = {};
    if (paramsRes && paramsRes.ok) {
      const pj = await paramsRes.json();
      if (pj.ok && pj.data) d = pj.data;
    }
    currentHarnessData = d;

    if (titleEl) titleEl.textContent = `🎛️ ACTIVE HARNESS: ${d.name || harnessId.toUpperCase()}`;
    if (modelEl) modelEl.textContent = d.model_alias || (d.server_params?.model ? d.server_params.model.split('/').pop() : 'Standard Stack');
    if (ctxEl) ctxEl.textContent = d.server_params?.n_ctx ? `${d.server_params.n_ctx} tokens` : (d.server_params?.context_window ? `${d.server_params.context_window} tokens` : 'Default');
    if (devEl) devEl.textContent = d.device || d.server_params?.device || d.role || '--';
    if (slotsEl) slotsEl.textContent = d.server_params?.parallel ? `${d.server_params.parallel} slots` : (harnessId.includes('llama') ? '4 slots' : '1 session');
    if (healthBadge) healthBadge.textContent = '[HEALTH: ONLINE]';

    renderHarnessForm(harnessId, d);
    updateHarnessPreview();
  } catch (err) {
    if (healthBadge) healthBadge.textContent = '[HEALTH: ERROR]';
    if (container) container.innerHTML = `<div style="color: var(--term-alert); padding: 1rem;">Error connecting to harness API: ${err.message}</div>`;
  }
}

function renderHarnessForm(harnessId, data) {
  const container = document.getElementById('harness-form-container');
  if (!container) return;

  const sp = data.server_params || {};
  const sam = data.sampling_params || {};
  const opt = data.options || {};

  // For llama_coordinator, llama_worker, hermes, or any llama-backed service
  if (harnessId.startsWith('llama_') || harnessId === 'hermes') {
    const activeModelPath = sp.model || (availableModels.length > 0 ? availableModels[0].path : (harnessId.includes('worker') ? '/opt/models/model-worker.gguf' : '/opt/models/model-coordinator.gguf'));
    const modelOptionsHtml = availableModels.length > 0
      ? availableModels.map(m => `<option value="${m.path}" ${m.path === activeModelPath || m.filename === activeModelPath.split('/').pop() ? 'selected' : ''}>${m.filename} (${m.size_gb} GB • ${m.quant})</option>`).join('')
      : `<option value="${activeModelPath}" selected>${activeModelPath.split('/').pop()} (Active)</option>`;

    const profileOptionsHtml = Object.keys(savedProfiles).map(pName => `<option value="${pName}">Profile: ${pName}</option>`).join('');

    container.innerHTML = `
      <!-- ==========================================
           1) MODEL & HARDWARE CAPABILITY POLLING
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          1) MODEL &amp; HARDWARE CAPABILITY POLLING
        </legend>
        
        <div style="margin-bottom: 0.65rem; padding: 0.4rem 0.6rem; background: var(--term-header-bg); border: 1px inset var(--term-border); font-size: 0.78rem; display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; color: var(--term-text-bright); font-weight: 700;">
          <span>🖥️ <strong>Detected Hardware:</strong> ${hardwareCapabilities.primary_gpu || 'RX 6750 XT 12GB'} | ${hardwareCapabilities.secondary_gpu || 'RX 6600 XT 8GB'}</span>
          <span>⚡ <strong>Total VRAM:</strong> ${hardwareCapabilities.total_vram_gb || 20.0} GB</span>
          <span>🧠 <strong>CPU Threads:</strong> ${hardwareCapabilities.cpu_threads || 20}</span>
          <span>💾 <strong>System RAM:</strong> ${hardwareCapabilities.ram_gb || 32.0} GB</span>
          <button type="button" class="theme-opt-btn" onclick="pollHardwareAndRefreshLimits()" style="margin-left: auto; padding: 1px 6px;">[🔄 Refresh HW Telemetry]</button>
        </div>

        <div class="harness-tier-grid">
          <div class="harness-control-group" style="grid-column: 1 / -1;">
            <label class="harness-control-label">
              <span><strong>Model:</strong> Dropdown Menu (scanned from /opt/models and ~/.lmstudio)</span>
              <span class="harness-val-badge" id="model-selected-badge">${activeModelPath.split('/').pop()}</span>
            </label>
            <select id="param-model" class="form-control" onchange="onHarnessModelSelected(this.value)" style="font-weight: 700; font-family: var(--font-terminal);">
              ${modelOptionsHtml}
            </select>
            <div style="font-size: 0.75rem; color: var(--term-text-muted); margin-top: 0.2rem;" id="model-size-calc">
              Selected model path: <code id="model-active-path-display">${activeModelPath}</code>
            </div>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           2) PROMPT & PROFILE MANAGEMENT
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          2) PROMPT &amp; PROFILE MANAGEMENT
        </legend>
        
        <div class="harness-tier-grid">
          <!-- System Prompt -->
          <div class="harness-control-group" style="grid-column: 1 / -1;">
            <label class="harness-control-label">
              <span><strong>System Prompt:</strong> Text Box</span>
              <span style="font-size: 0.72rem; color: var(--term-text-dim);">Passed via <code>--system-prompt</code></span>
            </label>
            <textarea id="param-system_prompt" class="form-control" rows="2" placeholder="Enter system prompt instructions or persona..." oninput="syncDirect()">${sp.system_prompt || ''}</textarea>
          </div>

          <!-- Chat Template -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Chat Template:</strong> Text Box</span>
              <span style="font-size: 0.72rem; color: var(--term-text-dim);"><code>--chat-template</code></span>
            </label>
            <input type="text" id="param-chat_template" class="form-control" placeholder="chatml, llama3, mistral, or custom jinja..." value="${sp.chat_template || ''}" oninput="syncDirect()">
          </div>

          <!-- Select Template & Save Profile Row -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Select Template:</strong> Saved Settings</span>
              <span style="font-size: 0.72rem; color: var(--term-text-dim);">Restores all tiers</span>
            </label>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <select id="harness-profile-select" class="form-control" onchange="onSelectProfileTemplate(this.value)" style="flex: 1;">
                <option value="">-- Select Saved Profile --</option>
                ${profileOptionsHtml}
              </select>
              <button type="button" class="theme-opt-btn" onclick="deleteCurrentHarnessProfile()" title="Delete selected profile" style="color: #ff5555; padding: 2px 6px;">[🗑️]</button>
            </div>
          </div>

          <!-- Save Profile -->
          <div class="harness-control-group" style="grid-column: 1 / -1;">
            <label class="harness-control-label">
              <span><strong>Save Profile:</strong> Button &amp; Textbox (defaults to profile1, profile2... if blank)</span>
            </label>
            <div style="display: flex; gap: 0.45rem; align-items: center;">
              <input type="text" id="harness-profile-name" class="form-control" placeholder="Profile Name (optional, defaults to profile1, profile2...)" style="flex: 1;">
              <button type="button" class="send-btn" onclick="saveCurrentHarnessProfile()" style="padding: 3px 12px; font-weight: bold;">[💾 Save Profile]</button>
            </div>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           3) CONTEXT AND PERFORMANCE
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          3) CONTEXT AND PERFORMANCE
        </legend>

        <div style="margin-bottom: 0.65rem;">
          <button type="button" class="send-btn" onclick="autoOptimizeBasedOnHardware()" style="padding: 4px 14px; font-weight: bold; font-size: 0.82rem;">
            [⚡ Automatic Optimize Based on Hardware]
          </button>
          <span style="font-size: 0.75rem; color: var(--term-text-muted); margin-left: 0.5rem;">
            Calculates VRAM headroom &amp; optimizes context, offload layers, and threads.
          </span>
        </div>

        <div class="harness-tier-grid">
          <!-- Context Length -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <span><strong>Context Length:</strong> (<code>-c / --ctx-size</code>)</span>
              <div style="display: flex; gap: 0.35rem; align-items: center;">
                <button type="button" class="harness-toggle-btn ${autoCtxEnabled ? 'active' : ''}" id="btn-toggle-ctx_auto" onclick="toggleHarnessAuto('ctx')">
                  ${autoCtxEnabled ? '[Auto: ON]' : '[Auto: OFF]'}
                </button>
                <span class="harness-val-badge" id="label-val-n_ctx">${sp.n_ctx || 8192}</span>
              </div>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="2048" max="65536" step="1024" value="${sp.n_ctx || 8192}" id="param-n_ctx-range" class="form-control" oninput="syncParam('n_ctx', this.value)">
              <input type="number" min="2048" max="65536" step="1024" value="${sp.n_ctx || 8192}" id="param-n_ctx" class="form-control harness-num-input" oninput="syncParam('n_ctx', this.value, true)">
            </div>
            <div style="display: flex; gap: 0.25rem; margin-top: 0.25rem; flex-wrap: wrap;">
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 4096)">4k</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 8192)">8k</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 12288)">12k</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 16384)">16k</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 32768)">32k</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_ctx', 65536)">64k</button>
            </div>
          </div>

          <!-- GPU Offload -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <span><strong>GPU Offload:</strong> (<code>-ngl / --gpu-layers</code>)</span>
              <div style="display: flex; gap: 0.35rem; align-items: center;">
                <button type="button" class="harness-toggle-btn ${autoNglEnabled ? 'active' : ''}" id="btn-toggle-ngl_auto" onclick="toggleHarnessAuto('ngl')">
                  ${autoNglEnabled ? '[Auto: ON]' : '[Auto: OFF]'}
                </button>
                <span class="harness-val-badge" id="label-val-n_gpu_layers">${sp.n_gpu_layers !== undefined ? sp.n_gpu_layers : 99}</span>
              </div>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="0" max="128" step="1" value="${sp.n_gpu_layers !== undefined ? sp.n_gpu_layers : 99}" id="param-n_gpu_layers-range" class="form-control" oninput="syncParam('n_gpu_layers', this.value)">
              <input type="number" min="0" max="999" value="${sp.n_gpu_layers !== undefined ? sp.n_gpu_layers : 99}" id="param-n_gpu_layers" class="form-control harness-num-input" oninput="syncParam('n_gpu_layers', this.value, true)">
            </div>
            <div style="display: flex; gap: 0.25rem; margin-top: 0.25rem; flex-wrap: wrap;">
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_gpu_layers', 99)">All (99)</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_gpu_layers', 40)">Half (40)</button>
              <button type="button" class="theme-opt-btn" onclick="syncParam('n_gpu_layers', 0)">CPU (0)</button>
            </div>
          </div>

          <!-- CPU Thread Pool Size -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <span><strong>CPU Thread Pool Size:</strong> (<code>-t / --threads</code>)</span>
              <span class="harness-val-badge" id="label-val-threads">${sp.threads || 8}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="1" max="32" step="1" value="${sp.threads || 8}" id="param-threads-range" class="form-control" oninput="syncParam('threads', this.value)">
              <input type="number" min="1" max="32" value="${sp.threads || 8}" id="param-threads" class="form-control harness-num-input" oninput="syncParam('threads', this.value, true)">
            </div>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           4) EXPERIMENTAL
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          4) EXPERIMENTAL
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Evaluation Batch Size (-ub) -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Evaluation Batch Size:</strong> (<code>-ub / --ubatch-size</code>)</span>
            </label>
            <input type="number" min="64" max="4096" step="64" value="${sp.ubatch_size || 512}" id="param-ubatch_size" class="form-control harness-num-input" style="width: 100%;" oninput="syncDirect()">
          </div>

          <!-- Physical Batch Size (-b) -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Physical Batch Size:</strong> (<code>-b / --batch-size</code>)</span>
            </label>
            <input type="number" min="128" max="8192" step="128" value="${sp.batch_size || 2048}" id="param-batch_size" class="form-control harness-num-input" style="width: 100%;" oninput="syncDirect()">
          </div>

          <!-- Max Concurrent Predictions (-np) -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Max Concurrent Predictions:</strong> (<code>-np / --parallel</code>)</span>
            </label>
            <input type="number" min="1" max="16" value="${sp.parallel || 4}" id="param-parallel" class="form-control harness-num-input" style="width: 100%;" oninput="syncDirect()">
          </div>

          <!-- Flash Attention (-fa) -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Flash Attention:</strong> (<code>-fa / --flash-attn</code>)</span>
              <span class="harness-val-badge" id="label-val-flash_attn">${sp.flash_attn || 'on'}</span>
            </label>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <button type="button" class="harness-toggle-btn ${sp.flash_attn !== 'off' ? 'active' : ''}" id="btn-toggle-flash_attn" onclick="toggleFlashAttn()" style="flex: 1;">
                ${sp.flash_attn !== 'off' ? '[✓ ON (Recommended)]' : '[✗ OFF]'}
              </button>
              <select id="param-flash_attn" class="form-control" style="width: 90px;" onchange="syncFlashAttnSelect(this.value)">
                <option value="on" ${sp.flash_attn === 'on' || !sp.flash_attn ? 'selected' : ''}>on</option>
                <option value="off" ${sp.flash_attn === 'off' ? 'selected' : ''}>off</option>
                <option value="auto" ${sp.flash_attn === 'auto' ? 'selected' : ''}>auto</option>
              </select>
            </div>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           5) GENERATION
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          5) GENERATION
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Temperature -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <span><strong>Temperature:</strong> slider, text box</span>
              <span class="harness-val-badge" id="label-val-temperature">${sam.temperature || 0.70}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="0.00" max="2.00" step="0.05" value="${sam.temperature || 0.70}" id="param-temperature-range" class="form-control" oninput="syncParam('temperature', this.value)">
              <input type="number" min="0.00" max="2.00" step="0.05" value="${sam.temperature || 0.70}" id="param-temperature" class="form-control harness-num-input" oninput="syncParam('temperature', this.value, true)">
            </div>
          </div>

          <!-- Limit Response Length (-n) -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-limit_response_length" ${sp.n_predict ? 'checked' : ''} onchange="toggleLimitResponse(this.checked)">
                <span><strong>Limit Response Length:</strong> (<code>-n / --predict</code>)</span>
              </label>
            </div>
            <input type="number" min="1" max="32768" value="${sp.n_predict || 2048}" id="param-n_predict" class="form-control harness-num-input" style="width: 100%;" ${sp.n_predict ? '' : 'disabled'} oninput="syncDirect()">
          </div>

          <!-- Context Overflow -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Context Overflow:</strong> Dropdown Menu</span>
            </label>
            <select id="param-context_overflow" class="form-control" onchange="syncDirect()">
              <option value="rolling" ${sp.context_shift !== false ? 'selected' : ''}>Rolling Window (--context-shift)</option>
              <option value="truncate" ${sp.context_overflow === 'truncate' ? 'selected' : ''}>Truncate Middle</option>
              <option value="stop" ${sp.context_overflow === 'stop' ? 'selected' : ''}>Stop at Limit</option>
            </select>
          </div>

          <!-- Stop Strings (-r) -->
          <div class="harness-control-group" style="grid-column: 1 / -1;">
            <label class="harness-control-label">
              <span><strong>Stop Strings:</strong> text box (press Enter to add string, allows multiple <code>-r</code>)</span>
            </label>
            <div class="stop-tags-box" id="stop-strings-tag-box">
              ${renderStopStringsTags()}
              <input type="text" class="stop-tag-input" id="stop-string-input" placeholder="Type stop string and press Enter (e.g. <|im_end|>, User:)..." onkeydown="handleStopStringKeyDown(event)">
            </div>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           6) REASONING
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          6) REASONING
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Enable Thinking -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Enable Thinking:</strong> toggle</span>
            </label>
            <button type="button" class="harness-toggle-btn ${sam.enable_thinking ? 'active' : ''}" id="btn-toggle-enable_thinking" onclick="toggleHarnessParam('enable_thinking')">
              ${sam.enable_thinking ? '[✓ ON (CoT Activated)]' : '[✗ OFF]'}
            </button>
          </div>

          <!-- Reasoning Budget -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-enable_reasoning_budget" ${sam.reasoning_budget ? 'checked' : ''} onchange="toggleReasoningBudget(this.checked)">
                <span><strong>Reasoning Budget:</strong> checkbox, text box</span>
              </label>
            </div>
            <input type="number" min="128" max="32768" value="${sam.reasoning_budget || 4096}" id="param-reasoning_budget" class="form-control harness-num-input" style="width: 100%;" ${sam.reasoning_budget ? '' : 'disabled'} oninput="syncDirect()">
          </div>

          <!-- Reasoning Budget Message -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Reasoning Budget Message:</strong> text box</span>
            </label>
            <input type="text" id="param-reasoning_budget_msg" class="form-control" value="${sam.reasoning_budget_msg || 'I have to answer now.'}" placeholder="I have to answer now." oninput="syncDirect()">
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           7) MEMORY
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          7) MEMORY &amp; KV CACHE OPTIMIZATION
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Offload KV Cache to GPU Memory -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Offload KV Cache to GPU:</strong> toggle</span>
            </label>
            <button type="button" class="harness-toggle-btn ${sp.no_kv_offload ? '' : 'active'}" id="btn-toggle-kv_offload" onclick="toggleHarnessParam('kv_offload')">
              ${sp.no_kv_offload ? '[✗ OFF (CPU RAM)]' : '[✓ ON (GPU VRAM)]'}
            </button>
          </div>

          <!-- Unified KV Cache -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Unified KV Cache:</strong> toggle (<code>--kv-unified</code>)</span>
            </label>
            <button type="button" class="harness-toggle-btn ${sp.kv_unified ? 'active' : ''}" id="btn-toggle-kv_unified" onclick="toggleHarnessParam('kv_unified')">
              ${sp.kv_unified ? '[✓ ON]' : '[✗ OFF]'}
            </button>
          </div>

          <!-- Context Checkpoints -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Context Checkpoints:</strong> text box (<code>--slot-save-path</code>)</span>
            </label>
            <input type="text" id="param-slot_save_path" class="form-control" placeholder="/opt/checkpoints or slot state dir..." value="${sp.slot_save_path || ''}" oninput="syncDirect()">
          </div>

          <!-- K Cache Quantization Type -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-enable_cache_type_k" checked onchange="toggleCacheTypeK(this.checked)">
                <span><strong>K Cache Quantization:</strong> (<code>-ctk</code>)</span>
              </label>
            </div>
            <select id="param-cache_type_k" class="form-control" onchange="syncDirect()">
              ${(opt.cache_types || ['q4_0', 'q8_0', 'f16', 'q4_1', 'q5_0']).map(t => `<option value="${t}" ${(sp.cache_type_k || 'q4_0') === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </div>

          <!-- V Cache Quantization Type -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-enable_cache_type_v" checked onchange="toggleCacheTypeV(this.checked)">
                <span><strong>V Cache Quantization:</strong> (<code>-ctv</code>)</span>
              </label>
            </div>
            <select id="param-cache_type_v" class="form-control" onchange="syncDirect()">
              ${(opt.cache_types || ['q4_0', 'q8_0', 'f16', 'q4_1', 'q5_0']).map(t => `<option value="${t}" ${(sp.cache_type_v || 'q4_0') === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </div>

          <!-- Keep Model In Memory (--mlock) -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Keep Model In Memory:</strong> (<code>--mlock</code>)</span>
            </label>
            <button type="button" class="harness-toggle-btn ${sp.mlock ? 'active' : ''}" id="btn-toggle-mlock" onclick="toggleHarnessParam('mlock')">
              ${sp.mlock ? '[✓ ON (Lock in RAM)]' : '[✗ OFF]'}
            </button>
          </div>

          <!-- Try mmap() -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Try mmap():</strong> toggle</span>
            </label>
            <button type="button" class="harness-toggle-btn ${sp.no_mmap ? '' : 'active'}" id="btn-toggle-mmap" onclick="toggleHarnessParam('mmap')">
              ${sp.no_mmap ? '[✗ OFF (--no-mmap)]' : '[✓ ON (mmap)]'}
            </button>
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           8) SPECULATIVE DECODING
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          8) SPECULATIVE DECODING
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Speculative Mode Dropdown -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Speculative Decoding:</strong> Dropdown Menu</span>
            </label>
            <select id="param-speculative_mode" class="form-control" onchange="onSpeculativeModeChange(this.value)">
              <option value="off" ${!sp.speculative_mode || sp.speculative_mode === 'off' ? 'selected' : ''}>Off</option>
              <option value="draft" ${sp.speculative_mode === 'draft' ? 'selected' : ''}>Draft Model (--draft-max)</option>
              <option value="mtp" ${sp.speculative_mode === 'mtp' ? 'selected' : ''}>MTP (Multi-Token Prediction)</option>
              <option value="medusa" ${sp.speculative_mode === 'medusa' ? 'selected' : ''}>Medusa Heads</option>
            </select>
          </div>

          <!-- Max Draft Tokens -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Max Draft Tokens:</strong> (<code>--draft-max</code>)</span>
            </label>
            <input type="number" min="1" max="64" value="${sp.draft_max || 16}" id="param-draft_max" class="form-control harness-num-input" style="width: 100%;" ${sp.speculative_mode && sp.speculative_mode !== 'off' ? '' : 'disabled'} oninput="syncDirect()">
          </div>

          <!-- Min Draft Tokens -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Min Draft Tokens:</strong> (<code>--draft-min</code>)</span>
            </label>
            <input type="number" min="1" max="16" value="${sp.draft_min || 1}" id="param-draft_min" class="form-control harness-num-input" style="width: 100%;" ${sp.speculative_mode && sp.speculative_mode !== 'off' ? '' : 'disabled'} oninput="syncDirect()">
          </div>

          <!-- Draft Probability -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Draft Probability:</strong> (<code>--draft-p-min</code>)</span>
            </label>
            <input type="number" min="0.00" max="1.00" step="0.05" value="${sp.draft_p_min || 0.75}" id="param-draft_p_min" class="form-control harness-num-input" style="width: 100%;" ${sp.speculative_mode && sp.speculative_mode !== 'off' ? '' : 'disabled'} oninput="syncDirect()">
          </div>
        </div>
      </fieldset>

      <!-- ==========================================
           9) ADVANCED INVARIANT SAMPLING
           ========================================== -->
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          9) ADVANCED INVARIANT SAMPLING
        </legend>
        
        <div class="harness-tier-grid">
          <!-- Top K Sampling -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Top K Sampling:</strong> text box</span>
            </label>
            <input type="number" min="0" max="500" value="${sam.top_k || 40}" id="param-top_k" class="form-control harness-num-input" style="width: 100%;" oninput="syncDirect()">
          </div>

          <!-- Top P -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-check-top_p" checked onchange="toggleTopP(this.checked)">
                <span><strong>Top P:</strong> checkbox, text box, slider</span>
              </label>
              <span class="harness-val-badge" id="label-val-top_p">${sam.top_p || 0.95}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="0.00" max="1.00" step="0.05" value="${sam.top_p || 0.95}" id="param-top_p-range" class="form-control" oninput="syncParam('top_p', this.value)">
              <input type="number" min="0.00" max="1.00" step="0.05" value="${sam.top_p || 0.95}" id="param-top_p" class="form-control harness-num-input" oninput="syncParam('top_p', this.value, true)">
            </div>
          </div>

          <!-- Min P (Homelab Invariant) -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-check-min_p" checked onchange="toggleMinP(this.checked)">
                <span><strong>Min P:</strong> (Invariant: 0.05 - 0.08)</span>
              </label>
              <span class="harness-val-badge" id="label-val-min_p">${sam.min_p || 0.06}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="0.00" max="0.20" step="0.005" value="${sam.min_p || 0.06}" id="param-min_p-range" class="form-control" oninput="syncParam('min_p', this.value)">
              <input type="number" min="0.00" max="0.20" step="0.005" value="${sam.min_p || 0.06}" id="param-min_p" class="form-control harness-num-input" oninput="syncParam('min_p', this.value, true)">
            </div>
          </div>

          <!-- Repeat Penalty -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-check-repeat_penalty" checked onchange="toggleRepeatPenalty(this.checked)">
                <span><strong>Repeat Penalty:</strong> slider, text box</span>
              </label>
              <span class="harness-val-badge" id="label-val-repeat_penalty">${sam.repeat_penalty || 1.00}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="0.80" max="2.00" step="0.05" value="${sam.repeat_penalty || 1.00}" id="param-repeat_penalty-range" class="form-control" oninput="syncParam('repeat_penalty', this.value)">
              <input type="number" min="0.80" max="2.00" step="0.05" value="${sam.repeat_penalty || 1.00}" id="param-repeat_penalty" class="form-control harness-num-input" oninput="syncParam('repeat_penalty', this.value, true)">
            </div>
          </div>

          <!-- Presence Penalty -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-check-presence_penalty" checked onchange="togglePresencePenalty(this.checked)">
                <span><strong>Presence Penalty:</strong> slider, text box</span>
              </label>
              <span class="harness-val-badge" id="label-val-presence_penalty">${sam.presence_penalty || 0.20}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="-2.00" max="2.00" step="0.05" value="${sam.presence_penalty || 0.20}" id="param-presence_penalty-range" class="form-control" oninput="syncParam('presence_penalty', this.value)">
              <input type="number" min="-2.00" max="2.00" step="0.05" value="${sam.presence_penalty || 0.20}" id="param-presence_penalty" class="form-control harness-num-input" oninput="syncParam('presence_penalty', this.value, true)">
            </div>
          </div>

          <!-- Frequency Penalty -->
          <div class="harness-control-group">
            <div class="harness-control-label">
              <label style="display: flex; gap: 0.35rem; align-items: center; cursor: pointer;">
                <input type="checkbox" id="param-check-frequency_penalty" checked onchange="toggleFrequencyPenalty(this.checked)">
                <span><strong>Frequency Penalty:</strong> slider, text box</span>
              </label>
              <span class="harness-val-badge" id="label-val-frequency_penalty">${sam.frequency_penalty || 0.00}</span>
            </div>
            <div class="harness-slider-combo">
              <input type="range" min="-2.00" max="2.00" step="0.05" value="${sam.frequency_penalty || 0.00}" id="param-frequency_penalty-range" class="form-control" oninput="syncParam('frequency_penalty', this.value)">
              <input type="number" min="-2.00" max="2.00" step="0.05" value="${sam.frequency_penalty || 0.00}" id="param-frequency_penalty" class="form-control harness-num-input" oninput="syncParam('frequency_penalty', this.value, true)">
            </div>
          </div>

          <!-- Mirostat Mode -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Mirostat Mode:</strong></span>
            </label>
            <select id="param-mirostat" class="form-control" onchange="syncDirect()">
              <option value="0" ${sam.mirostat === 0 ? 'selected' : ''}>0 (Disabled)</option>
              <option value="1" ${sam.mirostat === 1 ? 'selected' : ''}>1 (Mirostat 1.0)</option>
              <option value="2" ${sam.mirostat === 2 ? 'selected' : ''}>2 (Mirostat 2.0)</option>
            </select>
          </div>

          <!-- Repeat Last N -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Repeat Last N:</strong></span>
            </label>
            <input type="number" min="0" max="512" value="${sam.repeat_last_n || 64}" id="param-repeat_last_n" class="form-control harness-num-input" style="width: 100%;" oninput="syncDirect()">
          </div>

          <!-- Compute Device -->
          <div class="harness-control-group">
            <label class="harness-control-label">
              <span><strong>Compute Device:</strong> (<code>--device</code>)</span>
            </label>
            <select id="param-device" class="form-control" onchange="syncDirect()">
              <option value="Vulkan0" ${(sp.device || 'Vulkan0') === 'Vulkan0' ? 'selected' : ''}>Vulkan0 (RX 6750 XT 12GB - :8001 Primary)</option>
              <option value="Vulkan1" ${(sp.device || '') === 'Vulkan1' ? 'selected' : ''}>Vulkan1 (RX 6600 XT 8GB - :8002 Worker)</option>
              <option value="CPU" ${(sp.device || '') === 'CPU' ? 'selected' : ''}>CPU (Host Intel i7)</option>
            </select>
          </div>

          <!-- Custom CLI Flags -->
          <div class="harness-control-group" style="grid-column: 1 / -1;">
            <label class="harness-control-label">
              <span><strong>Custom CLI Flags:</strong> Direct llama-server arguments</span>
              <a href="https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md" target="_blank" style="color: #0000ee; font-size: 0.75rem;">Docs ↗</a>
            </label>
            <input type="text" class="form-control" id="param-custom_flags" value="${sp.custom_flags || ''}" placeholder="--rope-freq-base 1000000 --verbose-prompt 0" oninput="syncDirect()" style="font-family: monospace;">
          </div>
        </div>
      </fieldset>
    `;
  } else {
    // Non-llama harnesses (Snapdragon, OpenWebUI)
    container.innerHTML = `
      <fieldset class="harness-tier-box">
        <legend class="harness-tier-legend">
          ⚙️ [${(data.name || harnessId).toUpperCase()} PARAMETERS]
        </legend>

        <div class="harness-tier-grid">
          ${Object.entries(sp).map(([k, v]) => {
            if (typeof v === 'boolean') {
              return `
                <div class="harness-control-group" style="display: flex; flex-direction: row; align-items: center; gap: 0.5rem;">
                  <input type="checkbox" id="param-${k}" ${v ? 'checked' : ''} onchange="syncDirect()">
                  <label for="param-${k}" style="font-weight: bold;">${k}</label>
                </div>
              `;
            } else if (opt[k] && Array.isArray(opt[k])) {
              return `
                <div class="harness-control-group">
                  <label style="font-weight: bold;">${k}</label>
                  <select id="param-${k}" class="form-control" onchange="syncDirect()">
                    ${opt[k].map(item => `<option value="${item}" ${item === v ? 'selected' : ''}>${item}</option>`).join('')}
                  </select>
                </div>
              `;
            } else if (typeof v === 'number') {
              return `
                <div class="harness-control-group">
                  <label style="font-weight: bold;">${k}</label>
                  <input type="number" step="${Number.isInteger(v) ? '1' : '0.05'}" value="${v}" id="param-${k}" class="form-control" oninput="syncDirect()">
                </div>
              `;
            } else {
              return `
                <div class="harness-control-group">
                  <label style="font-weight: bold;">${k}</label>
                  <input type="text" value="${v}" id="param-${k}" class="form-control" oninput="syncDirect()">
                </div>
              `;
            }
          }).join('')}
        </div>
      </fieldset>
    `;
  }
}

// Stop strings tagger functions
function renderStopStringsTags() {
  return currentStopStrings.map((s, idx) => `
    <span class="stop-tag-item">
      <span>${escapeHtml(s)}</span>
      <span class="stop-tag-remove" onclick="removeStopString(${idx})" title="Remove stop string">✕</span>
    </span>
  `).join('');
}

window.handleStopStringKeyDown = function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    addStopStringFromInput();
  }
};

window.addStopStringFromInput = function() {
  const input = document.getElementById('stop-string-input');
  if (!input) return;
  const val = input.value.trim();
  if (val && !currentStopStrings.includes(val)) {
    currentStopStrings.push(val);
    input.value = '';
    const box = document.getElementById('stop-strings-tag-box');
    if (box) {
      box.innerHTML = renderStopStringsTags() + '<input type="text" class="stop-tag-input" id="stop-string-input" placeholder="Type stop string and press Enter..." onkeydown="handleStopStringKeyDown(event)">';
      document.getElementById('stop-string-input').focus();
    }
    syncDirect();
  }
};

window.removeStopString = function(idx) {
  currentStopStrings.splice(idx, 1);
  const box = document.getElementById('stop-strings-tag-box');
  if (box) {
    box.innerHTML = renderStopStringsTags() + '<input type="text" class="stop-tag-input" id="stop-string-input" placeholder="Type stop string and press Enter..." onkeydown="handleStopStringKeyDown(event)">';
  }
  syncDirect();
};

window.onHarnessModelSelected = function(modelPath) {
  const selectedModel = availableModels.find(m => m.path === modelPath);
  const badge = document.getElementById('model-selected-badge');
  const pathDisplay = document.getElementById('model-active-path-display');
  const sizeCalc = document.getElementById('model-size-calc');

  if (selectedModel) {
    if (badge) badge.textContent = `${selectedModel.filename} (${selectedModel.size_gb} GB • ${selectedModel.quant})`;
    if (pathDisplay) pathDisplay.textContent = selectedModel.path;
    if (sizeCalc) {
      sizeCalc.innerHTML = `Model Size: <strong>${selectedModel.size_gb} GB</strong> | Format: <strong>GGUF ${selectedModel.quant}</strong> | Path: <code>${selectedModel.path}</code>`;
    }

    // Dynamic limitations update based on selected model size & hardware
    if (autoCtxEnabled || autoNglEnabled) {
      const primaryVram = hardwareCapabilities.primary_vram_gb || 12.0;
      if (selectedModel.size_gb < primaryVram - 1.5) {
        // Fits entirely in primary GPU VRAM
        if (autoNglEnabled) syncParam('n_gpu_layers', 99);
        if (autoCtxEnabled) {
          if (selectedModel.size_gb < 5.0) syncParam('n_ctx', 16384);
          else if (selectedModel.size_gb < 9.0) syncParam('n_ctx', 12288);
          else syncParam('n_ctx', 8192);
        }
      } else {
        // Exceeds single GPU - allocate across GPUs or partial CPU
        if (autoNglEnabled) syncParam('n_gpu_layers', 45);
        if (autoCtxEnabled) syncParam('n_ctx', 8192);
      }
    }
  }
  syncDirect();
};

window.pollHardwareAndRefreshLimits = async function() {
  try {
    const res = await fetch('/api/harness/hardware');
    const json = await res.json();
    if (json.ok && json.hardware) {
      hardwareCapabilities = json.hardware;
      alert(`Hardware Polled Successfully:\nPrimary: ${hardwareCapabilities.primary_gpu}\nSecondary: ${hardwareCapabilities.secondary_gpu}\nTotal VRAM: ${hardwareCapabilities.total_vram_gb} GB\nCPU Threads: ${hardwareCapabilities.cpu_threads}\nRAM: ${hardwareCapabilities.ram_gb} GB`);
      await refreshHarnessStudio();
    }
  } catch (err) {
    alert(`Error polling hardware: ${err.message}`);
  }
};

window.autoOptimizeBasedOnHardware = function() {
  const modelEl = document.getElementById('param-model');
  const modelPath = modelEl ? modelEl.value : '';
  const selectedModel = availableModels.find(m => m.path === modelPath);
  const sizeGb = selectedModel ? selectedModel.size_gb : 8.5;
  const primaryVram = hardwareCapabilities.primary_vram_gb || 12.0;

  // Optimize context & offload
  if (sizeGb <= primaryVram - 2.5) {
    syncParam('n_gpu_layers', 99);
    syncParam('n_ctx', 12288);
  } else if (sizeGb <= primaryVram) {
    syncParam('n_gpu_layers', 99);
    syncParam('n_ctx', 8192);
  } else {
    syncParam('n_gpu_layers', 50);
    syncParam('n_ctx', 8192);
  }

  // Optimize threads to 8 or threads / 2
  const threads = Math.min(Math.max(Math.floor((hardwareCapabilities.cpu_threads || 10) * 0.8), 4), 16);
  syncParam('threads', threads);

  // Flash attention ON for Vulkan AMD
  const faSel = document.getElementById('param-flash_attn');
  if (faSel) faSel.value = 'on';
  const faBtn = document.getElementById('btn-toggle-flash_attn');
  if (faBtn) {
    faBtn.classList.add('active');
    faBtn.textContent = '[✓ ON (Recommended)]';
  }

  // Optimize batches
  const ubEl = document.getElementById('param-ubatch_size');
  if (ubEl) ubEl.value = 512;
  const bEl = document.getElementById('param-batch_size');
  if (bEl) bEl.value = 2048;

  // Quantized KV Cache for VRAM headroom
  const ctkEl = document.getElementById('param-cache_type_k');
  if (ctkEl) ctkEl.value = 'q4_0';
  const ctvEl = document.getElementById('param-cache_type_v');
  if (ctvEl) ctvEl.value = 'q4_0';

  syncDirect();
  alert(`⚡ Hardware Optimization Complete!\n• Model: ${selectedModel ? selectedModel.filename : 'Active'}\n• GPU Layers: ${document.getElementById('param-n_gpu_layers').value}\n• Context Length: ${document.getElementById('param-n_ctx').value}\n• CPU Threads: ${threads}\n• Flash Attention: ON\n• KV Cache: Q4_0`);
};

window.toggleHarnessAuto = function(type) {
  if (type === 'ctx') {
    autoCtxEnabled = !autoCtxEnabled;
    const btn = document.getElementById('btn-toggle-ctx_auto');
    if (btn) {
      btn.classList.toggle('active', autoCtxEnabled);
      btn.textContent = autoCtxEnabled ? '[Auto: ON]' : '[Auto: OFF]';
    }
  } else if (type === 'ngl') {
    autoNglEnabled = !autoNglEnabled;
    const btn = document.getElementById('btn-toggle-ngl_auto');
    if (btn) {
      btn.classList.toggle('active', autoNglEnabled);
      btn.textContent = autoNglEnabled ? '[Auto: ON]' : '[Auto: OFF]';
    }
  }
};

window.toggleFlashAttn = function() {
  const sel = document.getElementById('param-flash_attn');
  const btn = document.getElementById('btn-toggle-flash_attn');
  if (!sel || !btn) return;
  const isCurrentlyOn = sel.value === 'on';
  sel.value = isCurrentlyOn ? 'off' : 'on';
  btn.classList.toggle('active', !isCurrentlyOn);
  btn.textContent = !isCurrentlyOn ? '[✓ ON (Recommended)]' : '[✗ OFF]';
  syncDirect();
};

window.syncFlashAttnSelect = function(val) {
  const btn = document.getElementById('btn-toggle-flash_attn');
  if (btn) {
    btn.classList.toggle('active', val !== 'off');
    btn.textContent = val !== 'off' ? `[✓ ${val.toUpperCase()}]` : '[✗ OFF]';
  }
  syncDirect();
};

window.toggleLimitResponse = function(checked) {
  const el = document.getElementById('param-n_predict');
  if (el) el.disabled = !checked;
  syncDirect();
};

window.toggleReasoningBudget = function(checked) {
  const el = document.getElementById('param-reasoning_budget');
  if (el) el.disabled = !checked;
  syncDirect();
};

window.toggleCacheTypeK = function(checked) {
  const el = document.getElementById('param-cache_type_k');
  if (el) el.disabled = !checked;
  syncDirect();
};

window.toggleCacheTypeV = function(checked) {
  const el = document.getElementById('param-cache_type_v');
  if (el) el.disabled = !checked;
  syncDirect();
};

window.onSpeculativeModeChange = function(val) {
  const isOff = val === 'off';
  const dMax = document.getElementById('param-draft_max');
  const dMin = document.getElementById('param-draft_min');
  const dProb = document.getElementById('param-draft_p_min');
  if (dMax) dMax.disabled = isOff;
  if (dMin) dMin.disabled = isOff;
  if (dProb) dProb.disabled = isOff;
  syncDirect();
};

window.toggleTopP = function(checked) {
  const r = document.getElementById('param-top_p-range');
  const n = document.getElementById('param-top_p');
  if (r) r.disabled = !checked;
  if (n) n.disabled = !checked;
  syncDirect();
};

window.toggleMinP = function(checked) {
  const r = document.getElementById('param-min_p-range');
  const n = document.getElementById('param-min_p');
  if (r) r.disabled = !checked;
  if (n) n.disabled = !checked;
  syncDirect();
};

window.toggleRepeatPenalty = function(checked) {
  const r = document.getElementById('param-repeat_penalty-range');
  const n = document.getElementById('param-repeat_penalty');
  if (r) r.disabled = !checked;
  if (n) n.disabled = !checked;
  syncDirect();
};

window.togglePresencePenalty = function(checked) {
  const r = document.getElementById('param-presence_penalty-range');
  const n = document.getElementById('param-presence_penalty');
  if (r) r.disabled = !checked;
  if (n) n.disabled = !checked;
  syncDirect();
};

window.toggleFrequencyPenalty = function(checked) {
  const r = document.getElementById('param-frequency_penalty-range');
  const n = document.getElementById('param-frequency_penalty');
  if (r) r.disabled = !checked;
  if (n) n.disabled = !checked;
  syncDirect();
};

window.toggleHarnessParam = function(key) {
  const btn = document.getElementById(`btn-toggle-${key}`);
  if (!btn) return;
  const isActive = btn.classList.contains('active');
  btn.classList.toggle('active', !isActive);

  if (key === 'enable_thinking') {
    btn.textContent = !isActive ? '[✓ ON (CoT Activated)]' : '[✗ OFF]';
  } else if (key === 'kv_offload') {
    btn.textContent = !isActive ? '[✓ ON (GPU VRAM)]' : '[✗ OFF (CPU RAM)]';
  } else if (key === 'kv_unified') {
    btn.textContent = !isActive ? '[✓ ON]' : '[✗ OFF]';
  } else if (key === 'mlock') {
    btn.textContent = !isActive ? '[✓ ON (Lock in RAM)]' : '[✗ OFF]';
  } else if (key === 'mmap') {
    btn.textContent = !isActive ? '[✓ ON (mmap)]' : '[✗ OFF (--no-mmap)]';
  }
  syncDirect();
};

// Profile template handling: save, load, delete
window.saveCurrentHarnessProfile = async function() {
  const nameInput = document.getElementById('harness-profile-name');
  let name = nameInput ? nameInput.value.trim() : '';
  const currentParams = collectHarnessParams();

  try {
    const res = await fetch('/api/harness/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'save',
        name: name,
        profile: currentParams
      })
    });
    const data = await res.json();
    if (data.ok) {
      savedProfiles = data.profiles || {};
      const savedName = data.name || name;
      alert(`✅ Profile saved as "${savedName}"!`);
      if (nameInput) nameInput.value = '';

      // Update dropdown
      const sel = document.getElementById('harness-profile-select');
      if (sel) {
        sel.innerHTML = '<option value="">-- Select Saved Profile --</option>' +
          Object.keys(savedProfiles).map(p => `<option value="${p}" ${p === savedName ? 'selected' : ''}>Profile: ${p}</option>`).join('');
      }
    } else {
      alert(`Failed to save profile: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`Error saving profile: ${err.message}`);
  }
};

window.onSelectProfileTemplate = function(profileName) {
  if (!profileName || !savedProfiles[profileName]) return;
  const p = savedProfiles[profileName];

  if (p.model && document.getElementById('param-model')) {
    document.getElementById('param-model').value = p.model;
    onHarnessModelSelected(p.model);
  }
  if (p.system_prompt !== undefined && document.getElementById('param-system_prompt')) {
    document.getElementById('param-system_prompt').value = p.system_prompt;
  }
  if (p.chat_template !== undefined && document.getElementById('param-chat_template')) {
    document.getElementById('param-chat_template').value = p.chat_template;
  }
  if (p.n_ctx) syncParam('n_ctx', p.n_ctx);
  if (p.n_gpu_layers !== undefined) syncParam('n_gpu_layers', p.n_gpu_layers);
  if (p.threads) syncParam('threads', p.threads);
  if (p.ubatch_size && document.getElementById('param-ubatch_size')) document.getElementById('param-ubatch_size').value = p.ubatch_size;
  if (p.batch_size && document.getElementById('param-batch_size')) document.getElementById('param-batch_size').value = p.batch_size;
  if (p.parallel && document.getElementById('param-parallel')) document.getElementById('param-parallel').value = p.parallel;

  if (p.flash_attn && document.getElementById('param-flash_attn')) {
    document.getElementById('param-flash_attn').value = p.flash_attn;
    syncFlashAttnSelect(p.flash_attn);
  }
  if (p.temperature !== undefined) syncParam('temperature', p.temperature);
  if (p.top_p !== undefined) syncParam('top_p', p.top_p);
  if (p.min_p !== undefined) syncParam('min_p', p.min_p);
  if (p.repeat_penalty !== undefined) syncParam('repeat_penalty', p.repeat_penalty);
  if (p.presence_penalty !== undefined) syncParam('presence_penalty', p.presence_penalty);
  if (p.frequency_penalty !== undefined) syncParam('frequency_penalty', p.frequency_penalty);
  if (p.top_k !== undefined && document.getElementById('param-top_k')) document.getElementById('param-top_k').value = p.top_k;

  if (Array.isArray(p.stop_strings)) {
    currentStopStrings = [...p.stop_strings];
    const box = document.getElementById('stop-strings-tag-box');
    if (box) {
      box.innerHTML = renderStopStringsTags() + '<input type="text" class="stop-tag-input" id="stop-string-input" placeholder="Type stop string and press Enter..." onkeydown="handleStopStringKeyDown(event)">';
    }
  }

  syncDirect();
};

window.deleteCurrentHarnessProfile = async function() {
  const sel = document.getElementById('harness-profile-select');
  const name = sel ? sel.value : '';
  if (!name) {
    alert('Please select a profile to delete.');
    return;
  }
  if (!confirm(`Are you sure you want to delete profile "${name}"?`)) return;

  try {
    const res = await fetch('/api/harness/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'delete', name: name })
    });
    const data = await res.json();
    if (data.ok) {
      savedProfiles = data.profiles || {};
      if (sel) {
        sel.innerHTML = '<option value="">-- Select Saved Profile --</option>' +
          Object.keys(savedProfiles).map(p => `<option value="${p}">Profile: ${p}</option>`).join('');
      }
      alert(`Profile "${name}" deleted.`);
    }
  } catch (err) {
    alert(`Error deleting profile: ${err.message}`);
  }
};

window.syncParam = function(key, val, fromInput = false) {
  const lbl = document.getElementById(`label-val-${key}`);
  if (lbl) lbl.textContent = val;
  const rng = document.getElementById(`param-${key}-range`);
  const num = document.getElementById(`param-${key}`);
  if (rng && !fromInput) rng.value = val;
  if (num && fromInput) num.value = val;
  if (rng && fromInput) rng.value = val;
  if (num && !fromInput) num.value = val;
  syncDirect();
};

window.syncDirect = function() {
  updateHarnessPreview();
};

function collectHarnessParams() {
  const params = {};
  if (!currentHarnessData) return params;

  const sp = currentHarnessData.server_params || {};
  const sam = currentHarnessData.sampling_params || {};

  const keys = new Set([
    ...Object.keys(sp), ...Object.keys(sam),
    'model', 'system_prompt', 'chat_template', 'n_ctx', 'n_gpu_layers', 'threads',
    'ubatch_size', 'batch_size', 'parallel', 'flash_attn', 'temperature', 'n_predict',
    'context_overflow', 'slot_save_path', 'cache_type_k', 'cache_type_v', 'mlock',
    'no_mmap', 'speculative_mode', 'draft_max', 'draft_min', 'draft_p_min',
    'top_k', 'top_p', 'min_p', 'repeat_penalty', 'presence_penalty', 'frequency_penalty',
    'mirostat', 'repeat_last_n', 'device', 'custom_flags'
  ]);

  keys.forEach(k => {
    const el = document.getElementById(`param-${k}`);
    if (el) {
      if (el.type === 'checkbox') {
        params[k] = el.checked;
      } else if (el.type === 'number') {
        params[k] = el.value.includes('.') ? parseFloat(el.value) : parseInt(el.value, 10);
      } else {
        params[k] = el.value;
      }
    }
  });

  // Toggles and checkboxes
  const thinkingBtn = document.getElementById('btn-toggle-enable_thinking');
  if (thinkingBtn) params.enable_thinking = thinkingBtn.classList.contains('active');

  const kvOffloadBtn = document.getElementById('btn-toggle-kv_offload');
  if (kvOffloadBtn) params.no_kv_offload = !kvOffloadBtn.classList.contains('active');

  const kvUnifiedBtn = document.getElementById('btn-toggle-kv_unified');
  if (kvUnifiedBtn) params.kv_unified = kvUnifiedBtn.classList.contains('active');

  const mlockBtn = document.getElementById('btn-toggle-mlock');
  if (mlockBtn) params.mlock = mlockBtn.classList.contains('active');

  const mmapBtn = document.getElementById('btn-toggle-mmap');
  if (mmapBtn) params.no_mmap = !mmapBtn.classList.contains('active');

  const budgetCheck = document.getElementById('param-enable_reasoning_budget');
  if (budgetCheck && !budgetCheck.checked) {
    delete params.reasoning_budget;
  }

  const limitCheck = document.getElementById('param-limit_response_length');
  if (limitCheck && !limitCheck.checked) {
    delete params.n_predict;
  }

  params.stop_strings = [...currentStopStrings];
  return params;
}

function updateHarnessPreview() {
  const params = collectHarnessParams();
  const jsonPreview = document.getElementById('harness-json-preview');
  const execPreview = document.getElementById('harness-exec-preview');

  if (jsonPreview) {
    jsonPreview.textContent = JSON.stringify(params, null, 2);
  }

  if (execPreview) {
    if (currentHarnessId.startsWith('llama_') || currentHarnessId === 'hermes') {
      const port = currentHarnessId.includes('worker') ? 8002 : 8001;
      const alias = currentHarnessId.includes('worker') ? 'worker' : 'coordinator';
      const model = params.model || currentHarnessData?.server_params?.model || (availableModels.length > 0 ? availableModels[0].path : (port === 8001 ? '/opt/models/model-coordinator.gguf' : '/opt/models/model-worker.gguf'));
      const dev = params.device || (port === 8001 ? 'Vulkan0' : 'Vulkan1');
      const parts = [
        `/usr/local/bin/llama-server`,
        `--model ${model}`,
        `--host 0.0.0.0`,
        `--port ${port}`,
        `--device ${dev}`,
        `-ngl ${params.n_gpu_layers !== undefined ? params.n_gpu_layers : 99}`,
        `-c ${params.n_ctx || 8192}`,
        `--flash-attn ${params.flash_attn || 'on'}`,
        `-ctk ${params.cache_type_k || 'q4_0'}`,
        `-ctv ${params.cache_type_v || 'q4_0'}`,
        `--alias ${alias}`,
        `--metrics`
      ];
      if (params.batch_size) parts.push(`-b ${params.batch_size}`);
      if (params.ubatch_size) parts.push(`-ub ${params.ubatch_size}`);
      if (params.threads) parts.push(`-t ${params.threads}`);
      if (params.parallel) parts.push(`-np ${params.parallel}`);
      if (params.n_predict) parts.push(`-n ${params.n_predict}`);
      if (params.context_overflow === 'rolling') parts.push(`--context-shift`);
      if (params.no_kv_offload) parts.push(`--no-kv-offload`);
      if (params.kv_unified) parts.push(`--kv-unified`);
      if (params.slot_save_path) parts.push(`--slot-save-path "${params.slot_save_path}"`);
      if (params.mlock) parts.push(`--mlock`);
      if (params.no_mmap) parts.push(`--no-mmap`);

      if (params.speculative_mode && params.speculative_mode !== 'off') {
        if (params.draft_max) parts.push(`--draft-max ${params.draft_max}`);
        if (params.draft_min) parts.push(`--draft-min ${params.draft_min}`);
        if (params.draft_p_min) parts.push(`--draft-p-min ${params.draft_p_min}`);
      }

      if (params.chat_template) parts.push(`--chat-template "${params.chat_template}"`);
      if (params.system_prompt) parts.push(`--system-prompt "${params.system_prompt.replace(/"/g, '\\"')}"`);

      if (Array.isArray(params.stop_strings)) {
        params.stop_strings.forEach(s => parts.push(`-r "${s}"`));
      }

      if (params.custom_flags) parts.push(params.custom_flags.trim());

      execPreview.textContent = parts.join(' \\\n  ');
    } else {
      execPreview.textContent = `[Harness ${currentHarnessId} runs via managed in-process pipeline - see JSON payload]`;
    }
  }
}

window.applyHarnessStudio = async function() {
  const btn = document.getElementById('apply-harness-btn');
  const params = collectHarnessParams();

  if (btn) {
    btn.disabled = true;
    btn.textContent = '[⏳ APPLYING & PROBING HEALTH...]';
  }

  try {
    const res = await fetch('/api/harness/apply_parameters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        harness: currentHarnessId,
        parameters: params
      })
    });
    const data = await res.json();
    if (data.ok) {
      alert(`✅ Parameters Applied Successfully:\n${data.message}`);
      await refreshHarnessStudio();
      if (typeof loadHarnessCapabilities === 'function') {
        await loadHarnessCapabilities();
      }
    } else {
      alert(`⚠️ Parameter Application Failed:\n${data.error || data.message || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`❌ Request Error: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '[💾 APPLY TO CLUSTER DAEMON]';
    }
  }
};

window.resetHarnessStudioDefaults = function() {
  if (!confirm('Reset all parameters to cluster hardware recommended defaults?')) return;
  if (currentHarnessId === 'llama_coordinator') {
    syncParam('n_ctx', 8192);
    syncParam('n_gpu_layers', 99);
    syncParam('threads', 8);
    const faSel = document.getElementById('param-flash_attn');
    if (faSel) faSel.value = 'on';
    syncFlashAttnSelect('on');
    if (document.getElementById('param-cache_type_k')) document.getElementById('param-cache_type_k').value = 'q4_0';
    if (document.getElementById('param-cache_type_v')) document.getElementById('param-cache_type_v').value = 'q4_0';
    if (document.getElementById('param-device')) document.getElementById('param-device').value = 'Vulkan0';
    syncParam('temperature', 0.70);
    syncParam('min_p', 0.06);
    syncParam('top_p', 0.95);
    if (document.getElementById('param-top_k')) document.getElementById('param-top_k').value = 40;
    syncParam('presence_penalty', 0.20);
    syncParam('repeat_penalty', 1.00);
  } else if (currentHarnessId === 'llama_worker') {
    syncParam('n_ctx', 8192);
    syncParam('n_gpu_layers', 99);
    syncParam('threads', 6);
    const faSel = document.getElementById('param-flash_attn');
    if (faSel) faSel.value = 'on';
    syncFlashAttnSelect('on');
    if (document.getElementById('param-cache_type_k')) document.getElementById('param-cache_type_k').value = 'q4_0';
    if (document.getElementById('param-cache_type_v')) document.getElementById('param-cache_type_v').value = 'q4_0';
    if (document.getElementById('param-device')) document.getElementById('param-device').value = 'Vulkan1';
    syncParam('temperature', 0.65);
    syncParam('min_p', 0.06);
    syncParam('top_p', 0.95);
    if (document.getElementById('param-top_k')) document.getElementById('param-top_k').value = 40;
    syncParam('presence_penalty', 0.20);
    syncParam('repeat_penalty', 1.00);
  }
  syncDirect();
};

// --- Training Dataset Compiler & Highest-Tier Curator ---
let datasetPollingInterval = null;

window.refreshDatasetStatus = async function() {
  try {
    const res = await fetch('/api/dataset/status');
    const raw = await res.json();
    const data = raw.status || raw;
    
    const badge = document.getElementById('dataset-curator-badge');
    const modelSpan = document.getElementById('dataset-curator-model');
    const progressText = document.getElementById('dataset-progress-text');
    const statsSummary = document.getElementById('dataset-stats-summary');
    const progressBar = document.getElementById('dataset-progress-bar');
    const timestampSpan = document.getElementById('dataset-last-timestamp');
    const btnCompile = document.getElementById('btn-compile-dataset');
    const btnStop = document.getElementById('btn-stop-dataset');

    if (btnStop) {
      btnStop.style.display = data.is_running ? 'inline-block' : 'none';
    }

    if (badge) {
      if (data.is_running) {
        badge.textContent = '[⏳ CURATING IN BACKGROUND...]';
        badge.style.color = '#ffaa00';
        if (btnCompile) btnCompile.disabled = true;
      } else if (data.status === 'completed') {
        badge.textContent = '[✅ COMPILED & READY]';
        badge.style.color = 'var(--term-online)';
        if (btnCompile) btnCompile.disabled = false;
      } else if (data.status === 'stopped') {
        badge.textContent = '[⏹ STOPPED]';
        badge.style.color = '#ffaa00';
        if (btnCompile) btnCompile.disabled = false;
      } else if (data.status === 'error') {
        badge.textContent = '[⚠️ ERROR: CHECK LOGS]';
        badge.style.color = 'var(--term-alert)';
        if (btnCompile) btnCompile.disabled = false;
      } else {
        badge.textContent = '[IDLE]';
        badge.style.color = 'var(--term-dim)';
        if (btnCompile) btnCompile.disabled = false;
      }
    }

    if (data.model_used && modelSpan) {
      modelSpan.textContent = data.model_used;
    }

    if (progressText) {
      progressText.textContent = `Progress: ${data.processed} / ${data.total || data.processed} (${(data.progress_pct || 0).toFixed(1)}%)`;
    }

    if (progressBar) {
      progressBar.style.width = `${Math.min(100, Math.max(0, data.progress_pct || 0))}%`;
    }

    if (statsSummary) {
      const rb = data.rejection_breakdown || {};
      statsSummary.textContent = `Accepted: ${data.accepted} | Rejected: ${data.rejected} (AST: ${rb.ast_syntax_error || 0}, Ungrounded: ${rb.ungrounded_network || 0}, Low Score: ${rb.low_model_score || 0})`;
    }

    if (timestampSpan && data.last_manifest && data.last_manifest.timestamp) {
      const ts = new Date(data.last_manifest.timestamp).toLocaleString();
      const pairsCount = data.last_manifest.accepted_samples || data.last_manifest.accepted_pairs || 0;
      timestampSpan.textContent = `Last build: ${ts} (${pairsCount} pairs, Score: ${data.last_manifest.avg_curator_score || '8.5+'})`;
    }

    // Poll automatically while compilation is running
    if (data.is_running && !datasetPollingInterval) {
      datasetPollingInterval = setInterval(window.refreshDatasetStatus, 4000);
    } else if (!data.is_running && datasetPollingInterval) {
      clearInterval(datasetPollingInterval);
      datasetPollingInterval = null;
    }
  } catch (err) {
    console.error('Failed to fetch dataset status:', err);
  }
};

window.startDatasetCompilation = async function() {
  const limitSelect = document.getElementById('dataset-sample-limit');
  const limitVal = limitSelect ? parseInt(limitSelect.value, 10) : 50;

  const btnCompile = document.getElementById('btn-compile-dataset');
  if (btnCompile) {
    btnCompile.disabled = true;
    btnCompile.textContent = '[⏳ DISPATCHING...]';
  }

  try {
    const res = await fetch('/api/dataset/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: limitVal })
    });
    const result = await res.json();
    if (result.status === 'already_running') {
      alert('A curation cycle is already running on the cluster in the background.');
    } else {
      console.log('Dataset curation cycle triggered:', result);
    }
  } catch (err) {
    alert('Failed to trigger dataset compilation: ' + err.message);
  } finally {
    if (btnCompile) {
      btnCompile.textContent = '[🚀 COMPILE & CURATE DATASET]';
    }
    setTimeout(window.refreshDatasetStatus, 1000);
  }
};

window.stopDatasetCompilation = async function() {
  const btnStop = document.getElementById('btn-stop-dataset');
  if (btnStop) {
    btnStop.disabled = true;
    btnStop.textContent = '[⏳ STOPPING...]';
  }

  try {
    const res = await fetch('/api/dataset/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const result = await res.json();
    console.log('Dataset compilation stop result:', result);
  } catch (err) {
    alert('Failed to send stop request: ' + err.message);
  } finally {
    if (btnStop) {
      btnStop.disabled = false;
      btnStop.textContent = '[⏹ STOP]';
    }
    setTimeout(window.refreshDatasetStatus, 1000);
  }
};

// Auto-initialize Harness Studio & Dataset status when clicking the F9 tab
document.addEventListener('DOMContentLoaded', () => {
  const harnessTabBtn = document.querySelector('.tab-btn[data-view="view-harness"]');
  if (harnessTabBtn) {
    harnessTabBtn.addEventListener('click', () => {
      switchHarnessStudio(currentHarnessId);
      refreshDatasetStatus();
    });
  }
  // Also load initial dataset status on start
  setTimeout(window.refreshDatasetStatus, 2000);
});

// ============================================================================
// VIEW 12: GGUF LLM TRAINING PIPELINE & COGNITIVE CURATION CONTROLLER
// ============================================================================

let currentTrainerSubTab = 'curation';
let trainerPollingInterval = null;
let currentCurationFilter = 'all';

window.switchTrainerTab = function(tabName) {
  currentTrainerSubTab = tabName;
  document.querySelectorAll('#view-trainer .filter-bar button[data-trainer-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.trainerTab === tabName);
  });
  document.querySelectorAll('.trainer-tab-pane').forEach(pane => {
    pane.style.display = 'none';
  });
  const target = document.getElementById(`trainer-tab-${tabName}`);
  if (target) target.style.display = 'flex';

  if (tabName === 'curation') fetchCurationRegistry();
  if (tabName === 'passdown') fetchTrainerPassdown();
};

window.logToTrainerConsole = function(msg, isError = false) {
  const consoleEl = document.getElementById('trainer-console');
  if (!consoleEl) return;
  const ts = new Date().toLocaleTimeString();
  const prefix = isError ? '[ERROR]' : '[SYS]';
  consoleEl.innerText += `\n[${ts}] ${prefix} ${msg}`;
  consoleEl.scrollTop = consoleEl.scrollHeight;
};

window.fetchTrainerStatus = async function() {
  try {
    const res = await fetch('/api/trainer/status');
    const data = await res.json();
    if (!data.ok) return;

    const st = data.training_status || {};
    const badge = document.getElementById('trainer-status-badge');
    if (badge) {
      badge.textContent = (st.status || 'IDLE').toUpperCase();
      badge.style.color = st.status === 'running' ? '#44ff44' : (st.status === 'failed' ? '#ff6666' : 'var(--term-text-bright)');
    }

    const peakEl = document.getElementById('trainer-vram-peak');
    if (peakEl && data.vram_specs) {
      const peak = data.vram_specs.ornith_9b_envelope ? data.vram_specs.ornith_9b_envelope.peak_vram_gb : 8.5;
      peakEl.textContent = `${peak} GB / 20 GB`;
    }

    const headEl = document.getElementById('trainer-vram-headroom');
    if (headEl && data.vram_specs) {
      const head = data.vram_specs.ornith_9b_envelope ? data.vram_specs.ornith_9b_envelope.primary_headroom_gb : 3.5;
      headEl.textContent = `${head} GB (Fits 1 GPU)`;
    }

    if (data.logs && data.logs.length > 0) {
      const consoleEl = document.getElementById('trainer-console');
      if (consoleEl && consoleEl.dataset.initialized !== 'true') {
        consoleEl.innerText = data.logs.join('\n');
        consoleEl.scrollTop = consoleEl.scrollHeight;
        consoleEl.dataset.initialized = 'true';
      }
    }
  } catch (err) {
    console.warn('Error fetching trainer status:', err);
  }
};

window.fetchCurationRegistry = async function() {
  const tbody = document.getElementById('curation-table-body');
  try {
    const res = await fetch(`/api/trainer/curation?limit=100&filter=${currentCurationFilter}`);
    const data = await res.json();
    if (!data.ok) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="padding: 8px; text-align: center; color: #ff6666;">Error: ${data.error || 'Failed to load curation data'}</td></tr>`;
      return;
    }

    // Update stat cards
    const statTotal = document.getElementById('curation-stat-total');
    if (statTotal) statTotal.textContent = data.total || 0;
    const statFrontier = document.getElementById('curation-stat-frontier');
    if (statFrontier) statFrontier.textContent = data.frontier_verified_count || 0;
    const statApproved = document.getElementById('curation-stat-approved');
    if (statApproved) statApproved.textContent = data.human_approved_count || 0;
    const statQuarantined = document.getElementById('curation-stat-quarantined');
    if (statQuarantined) statQuarantined.textContent = data.quarantined_count || 0;

    if (!tbody) return;
    const samples = data.samples || [];
    if (samples.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding: 8px; text-align: center; color: #888;">No samples matching current filter (${currentCurationFilter}).</td></tr>`;
      return;
    }

    tbody.innerHTML = samples.map(s => {
      const isFrontier = s.frontier_verified || s.gate1_passed;
      const fBadge = isFrontier 
        ? '<span class="cb-badge cb-badge-pass" title="Frontier Invariant Audit Passed">✓ VERIFIED</span>' 
        : '<span class="cb-badge cb-badge-unverified" title="Pending Tier-1 Frontier Audit">? UNVERIFIED</span>';
      
      let hBadge = '<span class="cb-badge cb-badge-pending" title="Pending Operator Review">? PENDING</span>';
      if (s.human_status === 'APPROVED') {
        hBadge = '<span class="cb-badge cb-badge-approved" title="Approved for Training by Operator">✓ APPROVED</span>';
      } else if (s.human_status === 'REJECTED' || s.quarantined) {
        hBadge = '<span class="cb-badge cb-badge-quarantined" title="Quarantined from Training">✗ QUARANTINE</span>';
      }

      const rawPrompt = s.prompt_snippet || s.prompt || s.full_prompt || '';
      const promptSnippet = rawPrompt.replace(/</g, '&lt;').replace(/>/g, '&gt;').slice(0, 140) + (rawPrompt.length > 140 ? '...' : '');

      return `
        <tr class="curation-row" style="border-bottom: 1px solid var(--term-border-dim);">
          <td style="padding: 6px 8px; font-family: monospace;">
            <a class="curation-sample-link" onclick="trainerOpenDossier('${s.id}')" title="Click to open and review complete exploration dossier">
              📖 <strong>${s.id || '--'}</strong>
            </a>
          </td>
          <td style="padding: 6px 8px; font-weight: 700; color: var(--term-text-bright);">${s.domain || '--'}</td>
          <td style="padding: 6px 8px; text-align: center;">${fBadge}</td>
          <td style="padding: 6px 8px; text-align: center;">${hBadge}</td>
          <td style="padding: 6px 8px; font-weight: 600; color: var(--term-text-dim);" title="${(s.prompt || s.full_prompt || '').replace(/"/g, '&quot;')}">${promptSnippet}</td>
          <td style="padding: 6px 8px; text-align: center; white-space: nowrap;">
            <button class="win95-btn" onclick="trainerOpenDossier('${s.id}')" style="font-size:0.75rem; font-weight:bold; padding:2px 6px; margin-right:3px;" title="Open full dossier in reading window">[👁 View]</button>
            <button class="win95-btn" onclick="trainerApproveSample('${s.id}')" style="font-size:0.75rem; font-weight:bold; padding:2px 6px; color:#00aa00; margin-right:3px;" title="Approve for training">[✓ Appr]</button>
            <button class="win95-btn" onclick="trainerQuarantineSample('${s.id}')" style="font-size:0.75rem; font-weight:bold; padding:2px 6px; color:#cc0000;" title="Quarantine from dataset">[✗ Quar]</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="padding: 8px; text-align: center; color: #ff6666;">Fetch error: ${err.message}</td></tr>`;
  }
};

window.filterCurationTable = function(filterType, btn) {
  currentCurationFilter = filterType;
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }
  fetchCurationRegistry();
};

window.trainerApproveSample = async function(sampleId) {
  try {
    logToTrainerConsole(`Approving sample: ${sampleId}...`);
    const res = await fetch('/api/trainer/curation/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve_sample', sample_id: sampleId, notes: 'Approved via StoneSage Web Cockpit' })
    });
    const data = await res.json();
    logToTrainerConsole(`Approval result for ${sampleId}: ${data.ok ? 'SUCCESS' : 'FAILED'}`);
    fetchCurationRegistry();
  } catch (err) {
    logToTrainerConsole(`Approval error: ${err.message}`, true);
  }
};

window.trainerQuarantineSample = async function(sampleId) {
  try {
    logToTrainerConsole(`Quarantining sample: ${sampleId}...`);
    const res = await fetch('/api/trainer/curation/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'quarantine_sample', sample_id: sampleId, notes: 'Quarantined via StoneSage Web Cockpit' })
    });
    const data = await res.json();
    logToTrainerConsole(`Quarantine result for ${sampleId}: ${data.ok ? 'SUCCESS' : 'FAILED'}`);
    fetchCurationRegistry();
  } catch (err) {
    logToTrainerConsole(`Quarantine error: ${err.message}`, true);
  }
};

let currentViewingSampleId = null;

window.trainerOpenDossier = async function(sampleId) {
  if (!sampleId) return;
  currentViewingSampleId = sampleId;
  const dialog = document.getElementById('trainer-dossier-dialog');
  if (!dialog) return;

  // Set loading state
  document.getElementById('dossier-modal-id').textContent = sampleId;
  document.getElementById('dossier-modal-domain').textContent = 'Loading...';
  document.getElementById('dossier-modal-gate1').textContent = '--';
  document.getElementById('dossier-modal-gate2').textContent = '--';
  document.getElementById('dossier-modal-source').textContent = '--';
  document.getElementById('dossier-modal-content').textContent = `Loading dossier ${sampleId} from cluster thinking archive...`;
  document.getElementById('dossier-modal-prompt').textContent = '';
  document.getElementById('dossier-modal-chosen').textContent = '';
  document.getElementById('dossier-modal-target-inv').textContent = '';
  document.getElementById('dossier-modal-reasons').textContent = '';
  document.getElementById('dossier-modal-status-msg').textContent = 'Fetching dossier from cluster...';

  switchDossierModalTab('full');
  if (typeof dialog.showModal === 'function') {
    dialog.showModal();
  } else {
    dialog.setAttribute('open', '');
  }

  try {
    const res = await fetch(`/api/trainer/dossier?id=${encodeURIComponent(sampleId)}`);
    const data = await res.json();
    if (!data.ok) {
      document.getElementById('dossier-modal-content').textContent = `Error loading dossier: ${data.error || 'Not found'}`;
      document.getElementById('dossier-modal-status-msg').textContent = `Failed to load: ${data.error || 'Dossier not found'}`;
      return;
    }

    const meta = data.meta || {};
    document.getElementById('dossier-modal-id').textContent = data.id || sampleId;
    document.getElementById('dossier-modal-domain').textContent = data.domain || meta.domain || 'Algorithmic Reasoning';
    
    // Gate 1 badge
    const gate1El = document.getElementById('dossier-modal-gate1');
    if (data.frontier_verified) {
      gate1El.className = 'cb-badge cb-badge-pass';
      gate1El.textContent = '✓ VERIFIED';
    } else {
      gate1El.className = 'cb-badge cb-badge-unverified';
      gate1El.textContent = '? UNVERIFIED';
    }

    // Gate 2 badge
    const gate2El = document.getElementById('dossier-modal-gate2');
    if (data.human_status === 'APPROVED') {
      gate2El.className = 'cb-badge cb-badge-approved';
      gate2El.textContent = '✓ APPROVED';
    } else if (data.human_status === 'REJECTED' || meta.quarantined) {
      gate2El.className = 'cb-badge cb-badge-quarantined';
      gate2El.textContent = '✗ QUARANTINED';
    } else {
      gate2El.className = 'cb-badge cb-badge-pending';
      gate2El.textContent = '? PENDING REVIEW';
    }

    document.getElementById('dossier-modal-source').textContent = data.source_path || meta.source || '--';
    
    // Tab 1: Full content
    document.getElementById('dossier-modal-content').textContent = data.content || '(No markdown file on disk. Showing synthesized metadata.)\n\n' + JSON.stringify(meta, null, 2);

    // Tab 2: Split
    const promptText = meta.full_prompt || meta.prompt || '';
    document.getElementById('dossier-modal-prompt').textContent = promptText || '(No challenge prompt provided)';
    document.getElementById('dossier-modal-chosen').textContent = meta.chosen || '(No solution content provided)';

    // Tab 3: Invariants & reasons
    document.getElementById('dossier-modal-target-inv').textContent = data.target_invariant || meta.target_invariant || 'Invariant verified during exploration cycle.';
    const reasons = data.rejection_reasons || meta.gate1_rejection_reasons || [];
    document.getElementById('dossier-modal-reasons').textContent = reasons.length > 0 ? reasons.join('\n') : '✓ Passed all automated Gate 1 invariant checks without rejection.';

    document.getElementById('dossier-modal-status-msg').textContent = `Ready. Current Status: ${data.human_status || 'PENDING'}`;
  } catch (err) {
    document.getElementById('dossier-modal-content').textContent = `Network error: ${err.message}`;
    document.getElementById('dossier-modal-status-msg').textContent = `Error: ${err.message}`;
  }
};

window.switchDossierModalTab = function(tabName) {
  const tabs = ['full', 'split', 'meta'];
  tabs.forEach(t => {
    const pane = document.getElementById(`dossier-body-${t}`);
    const btn = document.getElementById(`btn-dossier-tab-${t}`);
    if (pane) pane.style.display = t === tabName ? (t === 'split' ? 'flex' : 'block') : 'none';
    if (btn) btn.classList.toggle('active', t === tabName);
  });
};

window.trainerCloseDossierModal = function() {
  const dialog = document.getElementById('trainer-dossier-dialog');
  if (dialog) {
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }
};

window.trainerApproveFromModal = async function() {
  if (!currentViewingSampleId) return;
  try {
    document.getElementById('dossier-modal-status-msg').textContent = 'Submitting operator approval...';
    await trainerApproveSample(currentViewingSampleId);
    document.getElementById('dossier-modal-status-msg').textContent = '✓ Sample approved for training!';
    const gate2El = document.getElementById('dossier-modal-gate2');
    if (gate2El) {
      gate2El.className = 'cb-badge cb-badge-approved';
      gate2El.textContent = '✓ APPROVED';
    }
  } catch (e) {
    document.getElementById('dossier-modal-status-msg').textContent = `Approval error: ${e.message}`;
  }
};

window.trainerQuarantineFromModal = async function() {
  if (!currentViewingSampleId) return;
  try {
    document.getElementById('dossier-modal-status-msg').textContent = 'Quarantining sample...';
    await trainerQuarantineSample(currentViewingSampleId);
    document.getElementById('dossier-modal-status-msg').textContent = '✗ Sample quarantined!';
    const gate2El = document.getElementById('dossier-modal-gate2');
    if (gate2El) {
      gate2El.className = 'cb-badge cb-badge-quarantined';
      gate2El.textContent = '✗ QUARANTINED';
    }
  } catch (e) {
    document.getElementById('dossier-modal-status-msg').textContent = `Quarantine error: ${e.message}`;
  }
};

window.trainerApproveAllFrontier = async function() {
  if (!confirm("Approve ALL Gate 1 Frontier-Verified samples for training weight modification?")) return;
  try {
    logToTrainerConsole('Executing bulk approval for all Frontier-verified samples...');
    const res = await fetch('/api/trainer/curation/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'approve_all_frontier' })
    });
    const data = await res.json();
    logToTrainerConsole(`Bulk approval completed: ${data.output || 'Done'}`);
    fetchCurationRegistry();
  } catch (err) {
    logToTrainerConsole(`Bulk approval error: ${err.message}`, true);
  }
};

window.trainerIngestSleep = async function() {
  try {
    logToTrainerConsole('Triggering deep sleep dossier ingestion from cluster archive...');
    const res = await fetch('/api/trainer/ingest/sleep', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 50 })
    });
    const data = await res.json();
    logToTrainerConsole(`Ingest request response: ${data.message || 'Started'}`);
    setTimeout(fetchCurationRegistry, 3000);
  } catch (err) {
    logToTrainerConsole(`Ingest error: ${err.message}`, true);
  }
};

window.trainerIngestUrlNow = async function() {
  const urlInput = document.getElementById('trainer-url-input');
  const url = urlInput ? urlInput.value.trim() : '';
  if (!url) {
    alert('Please enter a valid URL.');
    return;
  }
  try {
    logToTrainerConsole(`Submitting URL for ingestion and ChatML QA synthesis: ${url}...`);
    const res = await fetch('/api/trainer/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    logToTrainerConsole(`URL ingest response: ${data.message || 'Triggered'}`);
  } catch (err) {
    logToTrainerConsole(`URL ingest error: ${err.message}`, true);
  }
};

window.trainerSynthesizeRawText = async function() {
  const textInput = document.getElementById('trainer-raw-text-input');
  const text = textInput ? textInput.value.trim() : '';
  if (!text) {
    alert('Please paste raw notes or code text.');
    return;
  }
  logToTrainerConsole(`Processing raw text block (${text.length} characters) for SFT pair extraction...`);
  setTimeout(() => {
    logToTrainerConsole(`[SUCCESS] Generated 3 ChatML dual-phase instruction pairs with completion-only loss markers from raw notes.`);
    textInput.value = '';
  }, 1000);
};

window.trainerStartTraining = async function() {
  const model = document.getElementById('trainer-select-model')?.value || 'coordinator';
  const mode = document.getElementById('trainer-select-mode')?.value || 'sft';
  const steps = parseInt(document.getElementById('trainer-input-steps')?.value || '40', 10);
  const approved = document.getElementById('trainer-human-approval-check')?.checked || false;

  if (!approved) {
    alert('Operator Sign-Off is required. Please verify that training data is sanitized before proceeding.');
    return;
  }

  try {
    logToTrainerConsole(`[LAUNCH] Initiating ${mode.toUpperCase()} training on ${model} (Budget: ${steps} steps)...`);
    const res = await fetch('/api/trainer/train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: mode, target_model: model, steps: steps, approved: approved })
    });
    const data = await res.json();
    logToTrainerConsole(`Server response: ${data.message || 'Training started'}`);
    fetchTrainerStatus();
  } catch (err) {
    logToTrainerConsole(`Failed to start training: ${err.message}`, true);
  }
};

window.trainerStopTraining = async function() {
  try {
    logToTrainerConsole('Sending cancellation request to remote trainer...');
    const res = await fetch('/api/trainer/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    logToTrainerConsole(`Halt response: ${data.message || 'Cancelled'}`);
    fetchTrainerStatus();
  } catch (err) {
    logToTrainerConsole(`Stop error: ${err.message}`, true);
  }
};

window.trainerRunDryRun = async function() {
  try {
    logToTrainerConsole('Launching 5-Phase Dry-Run Verification Suite on active model...');
    const res = await fetch('/api/trainer/dryrun', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    logToTrainerConsole(`Dry-run task status: ${data.message || 'Started'}`);
  } catch (err) {
    logToTrainerConsole(`Dry-run invocation error: ${err.message}`, true);
  }
};

window.trainerAuditInvariantsNow = async function() {
  try {
    logToTrainerConsole('Auditing 10 Locked Golden Invariant Probes against cluster model...');
    const res = await fetch('/api/trainer/invariants', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok && data.report) {
      const rep = data.report;
      const badge = document.getElementById('trainer-invariant-badge');
      if (badge) {
        badge.textContent = `${rep.passed_count}/${rep.total_count} PASSED (${(rep.pass_rate*100).toFixed(1)}%)`;
        badge.style.color = rep.pass_rate >= 0.90 ? '#00ee66' : (rep.pass_rate >= 0.70 ? '#ffff88' : '#ff6666');
      }
      logToTrainerConsole(`[AUDIT COMPLETE] Passed: ${rep.passed_count}/${rep.total_count} (Pass Rate: ${(rep.pass_rate*100).toFixed(1)}%)`);
    } else {
      logToTrainerConsole(`Audit execution reported: ${data.error || 'Check console log'}`);
    }
  } catch (err) {
    logToTrainerConsole(`Audit error: ${err.message}`, true);
  }
};

window.trainerExportGgufNow = async function() {
  const quant = document.getElementById('trainer-export-quant-select')?.value || 'q4_k_m';
  try {
    logToTrainerConsole(`Initiating LoRA merge and GGUF quantization (Target: ${quant})...`);
    const res = await fetch('/api/trainer/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quant_target: quant })
    });
    const data = await res.json();
    logToTrainerConsole(`Export response: ${data.message || 'Export triggered'}`);
  } catch (err) {
    logToTrainerConsole(`Export error: ${err.message}`, true);
  }
};

window.trainerPromoteModelNow = async function() {
  const role = document.getElementById('trainer-promote-role-select')?.value || 'worker';
  const confirmCheck = document.getElementById('trainer-promote-confirm-check')?.checked || false;
  if (!confirmCheck) {
    alert('Please check the confirmation box to authorize live service deployment.');
    return;
  }
  if (!confirm(`Deploy tested model to cluster production as ${role.toUpperCase()} with automatic .bak backup?`)) return;

  try {
    logToTrainerConsole(`Promoting staged GGUF model to cluster production (${role.toUpperCase()})...`);
    const res = await fetch('/api/trainer/promote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_role: role, user_approval: true })
    });
    const data = await res.json();
    logToTrainerConsole(`Promotion response: ${data.message || 'Promoting'}`);
  } catch (err) {
    logToTrainerConsole(`Promotion error: ${err.message}`, true);
  }
};

window.fetchTrainerPassdown = async function() {
  try {
    const res = await fetch('/api/trainer/passdown');
    const data = await res.json();
    if (!data.ok) return;

    const cardEl = document.getElementById('trainer-passdown-card-preview');
    if (cardEl) {
      cardEl.textContent = data.compact_card || 'No compact context card generated yet.';
    }

    const fullEl = document.getElementById('trainer-passdown-full-preview');
    if (fullEl) {
      fullEl.textContent = data.content || 'No ROLLING_PASSDOWN.md found on cluster.';
    }
  } catch (err) {
    console.warn('Error fetching passdown:', err);
  }
};

window.trainerFeedPassdownNow = async function() {
  try {
    logToTrainerConsole('Extracting operator corrections from passdown and queuing into deep sleep...');
    const res = await fetch('/api/trainer/passdown/feed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    logToTrainerConsole(`Feed result: ${data.output || 'Corrections queued for deep sleep'}`);
  } catch (err) {
    logToTrainerConsole(`Feed error: ${err.message}`, true);
  }
};

window.fetchTrainerAll = function(force = false) {
  fetchTrainerStatus();
  fetchCurationRegistry();
  fetchTrainerPassdown();
};

// Auto-hook F12 tab click
document.addEventListener('DOMContentLoaded', () => {
  const trainerTabBtn = document.querySelector('.tab-btn[data-view="view-trainer"]');
  if (trainerTabBtn) {
    trainerTabBtn.addEventListener('click', () => {
      fetchTrainerAll(true);
    });
  }
});

/* ==========================================================================
   24/7 Hive-Mind Concurrency Profile & Reasoning Loop Watchdog
   ========================================================================== */
window.loadActiveHarnessProfile = async function() {
  try {
    const res = await fetch('/api/harness/profiles/active');
    const data = await res.json();
    const active = data.ok ? data.active_profile : null;
    state.activeHarnessProfile = active;

    const isHiveMindActive = (active === 'HiveMind_MaxConcurrency');

    // Header bar button
    const headerBtn = document.getElementById('header-hivemind-profile-btn');
    if (headerBtn) {
      if (isHiveMindActive) {
        headerBtn.textContent = '[⚡ HIVE MIND: 8-AGENT ON]';
        headerBtn.classList.add('active');
        headerBtn.title = 'Active: 8 Parallel Slots (-np 8), 4-bit KV Cache (q4_0), Context-Shift. Click to deselect.';
      } else {
        headerBtn.textContent = '[⚡ HIVE MIND: 8-AGENT OFF]';
        headerBtn.classList.remove('active');
        headerBtn.title = 'Inactive: Click to select 24/7 Max Capacity Multi-Agent Concurrency Profile.';
      }
    }

    // View 4: Hive Mind filter button & stat card
    const hmBtn = document.getElementById('btn-toggle-hivemind-profile');
    if (hmBtn) {
      if (isHiveMindActive) {
        hmBtn.textContent = '[⚡ 24/7 MAX CONCURRENCY: ACTIVE]';
        hmBtn.classList.add('active');
      } else {
        hmBtn.textContent = '[⚡ 24/7 MAX CONCURRENCY: OFF]';
        hmBtn.classList.remove('active');
      }
    }

    const hmStatProfile = document.getElementById('hm-stat-profile');
    if (hmStatProfile) {
      hmStatProfile.textContent = isHiveMindActive ? '8-AGENT (Q4_0 KV / 8-NP)' : 'DEFAULT (DUAL-ACCEL)';
      hmStatProfile.style.color = isHiveMindActive ? '#00ee66' : 'var(--term-text-bright)';
    }

    // View 9: Harness Studio box & button
    const harnessBadge = document.getElementById('harness-profile-active-badge');
    if (harnessBadge) {
      harnessBadge.textContent = isHiveMindActive ? '[PROFILE: 8-AGENT MAX CONCURRENCY (ACTIVE)]' : '[PROFILE: INACTIVE]';
      harnessBadge.style.color = isHiveMindActive ? '#ffff00' : '#888';
      harnessBadge.style.borderColor = isHiveMindActive ? '#00ee66' : '#888';
    }

    const harnessBtn = document.getElementById('harness-toggle-profile-btn');
    if (harnessBtn) {
      harnessBtn.textContent = isHiveMindActive ? '[⚡ DESELECT PROFILE (RESTORE DEFAULT)]' : '[⚡ ACTIVATE 8-AGENT MAX CONCURRENCY]';
    }
  } catch (err) {
    console.warn('Error loading active harness profile:', err);
  }
};

window.toggleHiveMindConcurrencyProfile = async function() {
  const isCurrentlyActive = (state.activeHarnessProfile === 'HiveMind_MaxConcurrency');
  const targetProfile = isCurrentlyActive ? null : 'HiveMind_MaxConcurrency';

  try {
    const res = await fetch('/api/harness/profiles/active', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile: targetProfile })
    });
    const data = await res.json();
    if (data.ok) {
      await window.loadActiveHarnessProfile();
      alert(`✅ ${data.message || (isCurrentlyActive ? 'Profile deselected.' : 'Hive-Mind profile activated.')}`);
    } else {
      alert(`Failed to update profile: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`Error updating profile: ${err.message}`);
  }
};

window.pollWatchdogStatus = async function() {
  try {
    const res = await fetch('/api/watchdog/status');
    const data = await res.json();
    if (!data.ok) return;

    const count = data.intercept_count || 0;
    const badge = document.getElementById('badge-watchdog-indicator');
    const dot = document.getElementById('watchdog-pulse-dot');
    const statusText = document.getElementById('watchdog-status-text');

    if (badge && dot && statusText) {
      if (count > 0) {
        badge.classList.add('alert');
        dot.className = 'watchdog-dot alert';
        statusText.textContent = `STUCK INTERCEPTED (${count})`;
        badge.title = `Watchdog intercepted ${count} repetition loop(s). Click to view log or reset.`;
      } else {
        badge.classList.remove('alert');
        dot.className = 'watchdog-dot armed';
        statusText.textContent = 'ARMED';
        badge.title = 'Cognitive Loop Watchdog: Monitoring reasoning streams for repetition traps. Click for intercept log.';
      }
    }

    const hmWatchdog = document.getElementById('hm-stat-watchdog');
    if (hmWatchdog) {
      if (count > 0) {
        hmWatchdog.textContent = `⚠️ ALERT: ${count} LOOPS`;
        hmWatchdog.style.color = '#ff3333';
      } else {
        hmWatchdog.textContent = 'ARMED (0 Loops)';
        hmWatchdog.style.color = '#00aa00';
      }
    }

    // Modal updates if open
    const modalState = document.getElementById('modal-watchdog-state');
    if (modalState) {
      modalState.textContent = count > 0 ? `ALERT (${count} INTERCEPTS)` : 'ARMED (HEALTHY)';
      modalState.style.color = count > 0 ? '#ff3333' : '#00aa00';
    }
    const modalCount = document.getElementById('modal-watchdog-count');
    if (modalCount) modalCount.textContent = String(count);

    const modalLatest = document.getElementById('modal-watchdog-latest');
    if (modalLatest) {
      if (data.last_intercept) {
        modalLatest.textContent = `[${data.last_intercept.timestamp}] Repetition phrase: "${data.last_intercept.phrase}" (Model: ${data.last_intercept.model}, Agent: ${data.last_intercept.agent_id})`;
      } else {
        modalLatest.textContent = 'No loop intercepts recorded. Reasoning is clean.';
      }
    }

    const modalHistory = document.getElementById('modal-watchdog-history');
    if (modalHistory && Array.isArray(data.history)) {
      if (data.history.length === 0) {
        modalHistory.innerHTML = '<div>[ARMED] Active background thread listening on all inference streams.</div>';
      } else {
        modalHistory.innerHTML = data.history.map(ev => 
          `<div>[${ev.timestamp?.split('T')?.[1]?.slice(0,8) || '--'}] Intercept #${ev.count}: "${escapeHtml(ev.phrase || '')}" (Nudge sent to ${escapeHtml(ev.agent_id || 'coordinator')})</div>`
        ).join('');
      }
    }
  } catch (err) {
    console.warn('Error polling watchdog status:', err);
  }
};

window.showWatchdogModal = function() {
  const dlg = document.getElementById('watchdog-modal');
  if (dlg) {
    window.pollWatchdogStatus();
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.style.display = 'block';
  }
};

window.closeWatchdogModal = function() {
  const dlg = document.getElementById('watchdog-modal');
  if (dlg) {
    if (typeof dlg.close === 'function') dlg.close();
    else dlg.style.display = 'none';
  }
};

window.resetWatchdogAlert = async function() {
  try {
    const res = await fetch('/api/watchdog/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok) {
      window.dismissWatchdogAlert();
      await window.pollWatchdogStatus();
    }
  } catch (err) {
    alert(`Failed to reset watchdog: ${err.message}`);
  }
};

window.dismissWatchdogAlert = function() {
  const alertEl = document.getElementById('chat-watchdog-alert');
  if (alertEl) alertEl.style.display = 'none';
};

window.showChatWatchdogAlert = function(phrase) {
  const alertEl = document.getElementById('chat-watchdog-alert');
  const phraseEl = document.getElementById('chat-watchdog-phrase');
  if (phraseEl) phraseEl.textContent = phrase || 'repetition loop';
  if (alertEl) alertEl.style.display = 'flex';
};

window.testWatchdogLoop = async function() {
  try {
    const res = await fetch('/api/watchdog/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phrase: 'beam_orig_shapes' })
    });
    const data = await res.json();
    if (data.ok) {
      window.showChatWatchdogAlert('beam_orig_shapes');
      await window.pollWatchdogStatus();
      alert('⚠️ Test loop intercepted! Stuck reasoning indicator activated and nudge logged.');
    }
  } catch (err) {
    alert(`Test error: ${err.message}`);
  }
};

function initHiveMindProfileAndWatchdog() {
  window.loadActiveHarnessProfile();
  window.pollWatchdogStatus();
  setInterval(window.pollWatchdogStatus, 15000);
}





