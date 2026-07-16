/**
 * VideoDL Pro – premium frontend shell
 * Theme, command palette, clipboard, progress, toasts
 */

function resolveInitialDark() {
  if (typeof window.__VDL_DARK__ === 'boolean') return window.__VDL_DARK__;
  if (typeof window.__VDL_PREFER_DARK__ === 'function') return window.__VDL_PREFER_DARK__();
  try {
    const t = localStorage.getItem('vdl-theme');
    if (t === 'dark') return true;
    if (t === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return document.documentElement.classList.contains('dark');
  }
}

function applyThemeDark(dark) {
  window.__VDL_DARK__ = !!dark;
  if (typeof window.__VDL_APPLY_THEME__ === 'function') {
    window.__VDL_APPLY_THEME__(!!dark);
  } else {
    document.documentElement.classList.toggle('dark', !!dark);
    document.documentElement.style.backgroundColor = dark ? '#06060a' : '#f4f6fb';
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  }
  const canvas = document.getElementById('theme-canvas');
  if (canvas) canvas.style.backgroundColor = dark ? '#06060a' : '#f4f6fb';
  // Sync meta theme-color for mobile browser chrome
  const meta = document.querySelector('meta[name="theme-color"]:not([media])');
  if (meta) meta.setAttribute('content', dark ? '#06060a' : '#f4f6fb');
}

function appShell() {
  // CRITICAL: dark must be correct on first Alpine evaluation.
  // Starting as false + x-bind:class strips .dark → full white flash.
  const initialDark = resolveInitialDark();

  return {
    dark: initialDark,
    accent: '#6366f1',
    paletteOpen: false,
    paletteQuery: '',
    paletteIndex: 0,
    dropActive: false,
    commands: [],

    init() {
      // Re-assert theme (never trust a stale false)
      this.dark = resolveInitialDark();
      applyThemeDark(this.dark);

      const accent = localStorage.getItem('vdl-accent');
      if (accent) {
        this.accent = accent;
        document.documentElement.style.setProperty('--accent', accent);
      }

      // Keep Alpine state in sync if we change class outside Alpine
      this.$watch('dark', (value) => {
        applyThemeDark(value);
      });

      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('vdl-theme')) {
          this.dark = e.matches;
          applyThemeDark(this.dark);
        }
      });

      this.commands = buildCommands();
      let dragDepth = 0;
      window.addEventListener('dragenter', (e) => {
        if (!e.dataTransfer?.types?.includes('text/uri-list') && !e.dataTransfer?.types?.includes('text/plain')) return;
        dragDepth += 1;
        this.dropActive = true;
      });
      window.addEventListener('dragleave', () => {
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) this.dropActive = false;
      });
      window.addEventListener('dragover', (e) => {
        if (this.dropActive) e.preventDefault();
      });
      window.addEventListener('drop', () => {
        dragDepth = 0;
        this.dropActive = false;
      });
    },

    toggle() {
      this.dark = !this.dark;
      localStorage.setItem('vdl-theme', this.dark ? 'dark' : 'light');
      applyThemeDark(this.dark);
    },

    setAccent(color) {
      this.accent = color;
      document.documentElement.style.setProperty('--accent', color);
      localStorage.setItem('vdl-accent', color);
    },

    get filteredCommands() {
      const q = (this.paletteQuery || '').toLowerCase().trim();
      if (!q) return this.commands;
      return this.commands.filter(
        (c) => c.label.toLowerCase().includes(q) || (c.keywords || '').includes(q)
      );
    },

    openPalette() {
      this.paletteOpen = true;
      this.paletteQuery = '';
      this.paletteIndex = 0;
      this.$nextTick(() => this.$refs.paletteInput?.focus());
    },

    runCommand(cmd) {
      if (!cmd) return;
      this.paletteOpen = false;
      if (cmd.action) cmd.action();
      else if (cmd.href) {
        if (typeof window.softNavigate === 'function') window.softNavigate(cmd.href);
        else window.location.href = cmd.href;
      }
    },

    onKeydown(e) {
      const tag = document.activeElement?.tagName;
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || document.activeElement?.isContentEditable;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (this.paletteOpen) this.paletteOpen = false;
        else this.openPalette();
        return;
      }

      if (e.key === 'Escape' && this.paletteOpen) {
        this.paletteOpen = false;
        return;
      }

      if (!typing && e.key === '/') {
        e.preventDefault();
        const input = document.getElementById('url-input');
        if (input) input.focus();
        else this.openPalette();
      }
    },

    onGlobalDrop(e) {
      this.dropActive = false;
      const text = e.dataTransfer?.getData('text') || e.dataTransfer?.getData('text/uri-list') || '';
      const url = text.trim().split(/\s+/)[0];
      if (url && /^https?:\/\//i.test(url)) {
        const input = document.getElementById('url-input');
        if (input) {
          input.value = url;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          // Alpine model sync
          input.dispatchEvent(new Event('change', { bubbles: true }));
          showToast('Link dropped — analyzing…', 'info');
          // Trigger analyze if home page exposes it
          window.dispatchEvent(new CustomEvent('vdl:drop-url', { detail: { url } }));
        } else {
          const dest = (window.__VDL_NAV__?.home || '/') + '?url=' + encodeURIComponent(url);
          if (typeof window.softNavigate === 'function') window.softNavigate(dest);
          else window.location.href = dest;
        }
      }
    },
  };
}

/**
 * Delayed busy state for buttons — if action finishes fast, user never sees a spinner.
 */
function withBusy(btn, promise, { delay = 180 } = {}) {
  if (!btn) return promise;
  let shown = false;
  const t = setTimeout(() => {
    shown = true;
    btn.classList.add('is-busy');
    btn.disabled = true;
  }, delay);
  return Promise.resolve(promise).finally(() => {
    clearTimeout(t);
    if (shown) {
      btn.classList.remove('is-busy');
      btn.disabled = false;
    }
  });
}

// Backward-compatible alias
function themeApp() {
  return appShell();
}

function buildCommands() {
  const nav = window.__VDL_NAV__ || {};
  const icon = (d) =>
    `<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="${d}"/></svg>`;

  const list = [
    {
      id: 'home',
      label: 'New download',
      href: nav.home || '/',
      hint: 'G H',
      keywords: 'download home paste',
      icon: icon('M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4'),
    },
    {
      id: 'history',
      label: 'History',
      href: nav.history || '/history/',
      keywords: 'history past downloads',
      icon: icon('M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'),
    },
    {
      id: 'api',
      label: 'API docs',
      href: nav.api || '/api/docs/',
      keywords: 'api swagger docs',
      icon: icon('M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4'),
    },
    {
      id: 'theme',
      label: 'Toggle theme',
      keywords: 'dark light mode theme',
      icon: icon('M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z'),
      action: () => {
        const root = document.querySelector('[x-data]');
        // Prefer stored toggle via click on theme button
        document.querySelector('button[aria-label="Light mode"], button[aria-label="Dark mode"]')?.click();
      },
    },
    {
      id: 'focus',
      label: 'Focus URL bar',
      keywords: 'url paste focus search',
      hint: '/',
      icon: icon('M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101'),
      action: () => document.getElementById('url-input')?.focus(),
    },
  ];

  if (nav.dashboard) {
    list.splice(2, 0, {
      id: 'dashboard',
      label: 'Dashboard',
      href: nav.dashboard,
      keywords: 'stats analytics',
      icon: icon('M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'),
    });
  }
  if (nav.files) {
    list.splice(3, 0, {
      id: 'files',
      label: 'File manager',
      href: nav.files,
      keywords: 'files media',
      icon: icon('M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z'),
    });
  }
  if (nav.settings) {
    list.push({
      id: 'settings',
      label: 'Settings',
      href: nav.settings,
      keywords: 'settings preferences api keys',
      icon: icon('M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z'),
    });
  }
  if (nav.login) {
    list.push({
      id: 'login',
      label: 'Sign in',
      href: nav.login,
      keywords: 'login signin',
      icon: icon('M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1'),
    });
  }

  return list;
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.getAttribute('content');
  const cookie = document.cookie
    .split(';')
    .map((c) => c.trim())
    .find((c) => c.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

document.addEventListener('DOMContentLoaded', () => {
  document.body.addEventListener('htmx:configRequest', (e) => {
    e.detail.headers['X-CSRFToken'] = getCsrfToken();
  });

  // Prefill URL from query string
  const params = new URLSearchParams(location.search);
  const qUrl = params.get('url');
  if (qUrl) {
    const input = document.getElementById('url-input');
    if (input) {
      input.value = qUrl;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      window.dispatchEvent(new CustomEvent('vdl:drop-url', { detail: { url: qUrl } }));
    }
  }
});

function showToast(message, type = 'info') {
  const region = document.getElementById('toast-region');
  if (!region) return;
  const el = document.createElement('div');
  const color =
    type === 'error' ? 'bg-rose-500' : type === 'success' ? 'bg-emerald-500' : 'bg-indigo-500';
  el.className =
    'pointer-events-auto glass-strong rounded-2xl px-4 py-3.5 text-sm flex items-start gap-3 animate-slide-up';
  el.innerHTML = `
    <span class="mt-1 h-2 w-2 shrink-0 rounded-full ${color}"></span>
    <p class="flex-1 leading-relaxed"></p>
    <button type="button" class="text-slate-400" aria-label="Dismiss">×</button>`;
  el.querySelector('p').textContent = message;
  el.querySelector('button').onclick = () => el.remove();
  region.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function setMediaBackdrop(url) {
  const wrap = document.getElementById('media-backdrop');
  const img = document.getElementById('media-backdrop-img');
  if (!wrap || !img) return;
  if (url) {
    wrap.style.visibility = 'visible';
    img.onload = () => {
      wrap.classList.add('is-visible');
      wrap.style.opacity = '';
    };
    img.src = url;
    // If cached, onload may not fire
    if (img.complete) {
      wrap.classList.add('is-visible');
      wrap.style.opacity = '';
    }
  } else {
    wrap.classList.remove('is-visible');
    wrap.style.opacity = '0';
    wrap.style.visibility = 'hidden';
    // Defer src clear so dark fade doesn't flash a light image frame
    setTimeout(() => {
      if (!wrap.classList.contains('is-visible')) {
        img.removeAttribute('src');
        img.onload = null;
      }
    }, 320);
  }
}

/**
 * Live download progress — always polls (reliable) and uses WebSocket when available.
 * Normalizes payload so UI always gets progress %, speed string, and sizes.
 */
function connectDownloadProgress(downloadId, handlers = {}) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  let ws;
  let pollTimer;
  let closed = false;
  let lastProgress = -1;

  function normalize(raw) {
    const d = raw && typeof raw === 'object' ? raw : {};
    let progress = Number(d.progress ?? d.percent ?? d.progress_percent ?? 0);
    if (Number.isNaN(progress)) progress = 0;
    progress = Math.max(0, Math.min(100, progress));

    let speed = d.speed;
    if (!speed || speed === '—') {
      if (d.speed_bps != null && d.speed_bps > 0) {
        speed = formatBytes(d.speed_bps) + '/s';
      } else {
        speed = '—';
      }
    }

    return {
      ...d,
      id: d.id || downloadId,
      status: d.status || 'downloading',
      stage: d.stage || d.status || '',
      progress,
      percent: progress,
      progress_percent: Math.round(progress),
      speed,
      speed_bps: d.speed_bps,
      eta: d.eta || '—',
      eta_seconds: d.eta_seconds,
      downloaded: d.downloaded || formatBytes(d.downloaded_bytes) || '—',
      total: d.total || formatBytes(d.total_bytes) || '—',
      downloaded_bytes: d.downloaded_bytes,
      total_bytes: d.total_bytes,
      title: d.title || '',
      error: d.error || '',
    };
  }

  function apply(raw) {
    const data = normalize(raw);
    // Skip no-op tiny updates if identical (except force terminal)
    const terminal = ['completed', 'failed', 'cancelled', 'expired'].includes(data.status);
    if (!terminal && data.progress === lastProgress && data.speed === '—' && !data.stage) {
      return;
    }
    lastProgress = data.progress;

    if (handlers.onProgress) handlers.onProgress(data);
    if (data.status === 'completed' && handlers.onComplete) handlers.onComplete(data);
    if (data.status === 'failed' && handlers.onError) handlers.onError(data);
    return data;
  }

  async function pollOnce() {
    if (closed) return null;
    try {
      const res = await fetch(`/history/${downloadId}/progress/`, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!res.ok) return null;
      return apply(await res.json());
    } catch (_) {
      return null;
    }
  }

  function startPolling() {
    if (pollTimer) return;
    // Aggressive polling while active so % and speed feel live
    pollTimer = setInterval(async () => {
      const data = await pollOnce();
      if (data && ['completed', 'failed', 'cancelled', 'expired'].includes(data.status)) {
        clearInterval(pollTimer);
        pollTimer = null;
        if (ws) {
          try {
            ws.close();
          } catch (_) {
            /* ignore */
          }
        }
      }
    }, 500);
  }

  // Immediate snapshot so bar isn't empty for half a second
  pollOnce();
  startPolling();

  try {
    ws = new WebSocket(`${proto}://${location.host}/ws/downloads/${downloadId}/`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        apply(msg.data || msg);
      } catch (_) {
        /* ignore */
      }
    };
    ws.onerror = () => {
      /* polling already running */
    };
  } catch (_) {
    /* polling covers this */
  }

  return () => {
    closed = true;
    if (ws) {
      try {
        ws.close();
      } catch (_) {
        /* ignore */
      }
    }
    if (pollTimer) clearInterval(pollTimer);
  };
}

async function tryPasteFromClipboard(input) {
  if (!navigator.clipboard || !input) return;
  try {
    const text = await navigator.clipboard.readText();
    if (text && /^https?:\/\//i.test(text.trim()) && !input.value) {
      input.value = text.trim();
      input.dispatchEvent(new Event('input', { bubbles: true }));
      showToast('URL detected from clipboard', 'info');
    }
  } catch (_) {
    /* permission denied */
  }
}

function platformColor(slug) {
  const map = {
    youtube: '#ff0033',
    tiktok: '#25f4ee',
    instagram: '#e1306c',
    twitter: '#1d9bf0',
    facebook: '#1877f2',
    vimeo: '#1ab7ea',
    reddit: '#ff4500',
    twitch: '#9146ff',
    soundcloud: '#ff5500',
    bilibili: '#00a1d6',
  };
  return map[(slug || '').toLowerCase()] || '#6366f1';
}

function formatBytes(n) {
  if (n == null || n < 0) return '—';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = Number(n);
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return i === 0 ? `${v} ${u[i]}` : `${v.toFixed(1)} ${u[i]}`;
}

function formatDuration(sec) {
  if (sec == null || sec < 0) return '—';
  sec = Math.floor(sec);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatViews(n) {
  if (n == null) return '—';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}
