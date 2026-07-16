/**
 * Soft navigation — native app feel
 * Instant taps · prefetch · delayed micro-bar · view transitions
 */
(function () {
  const ROOT_ID = "page-root";
  const PREFETCH_TTL = 45_000;
  const SLOW_MS = 140;
  const cache = new Map();

  let navigating = false;
  let barTimer = null;
  let barEl = null;

  function ensureBar() {
    if (barEl) return barEl;
    barEl = document.createElement("div");
    barEl.id = "nav-progress";
    barEl.setAttribute("aria-hidden", "true");
    barEl.innerHTML = '<div class="nav-progress-bar"></div>';
    document.body.appendChild(barEl);
    return barEl;
  }

  function showBarDelayed() {
    clearTimeout(barTimer);
    barTimer = setTimeout(() => {
      ensureBar().classList.add("is-active", "is-loading");
    }, SLOW_MS);
  }

  function hideBar() {
    clearTimeout(barTimer);
    barTimer = null;
    if (!barEl) return;
    barEl.classList.remove("is-loading");
    barEl.classList.add("is-done");
    setTimeout(() => barEl?.classList.remove("is-active", "is-done"), 260);
  }

  function sameOrigin(href) {
    try {
      return new URL(href, location.href).origin === location.origin;
    } catch {
      return false;
    }
  }

  function shouldBoost(a) {
    if (!a || a.tagName !== "A") return false;
    if (a.hasAttribute("download") || a.hasAttribute("data-no-boost")) return false;
    if (a.target && a.target !== "_self") return false;
    const href = a.getAttribute("href") || "";
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("javascript:"))
      return false;
    if (!sameOrigin(a.href)) return false;
    if (/\/file\/?$|\/qr\/?$/i.test(a.pathname || "")) return false;
    if (a.pathname && a.pathname.startsWith("/admin")) return false;
    if (a.pathname && a.pathname.startsWith("/api/")) return false;
    return true;
  }

  function parseDoc(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const root = doc.getElementById(ROOT_ID);
    if (!root) return null;
    return {
      rootHtml: root.outerHTML,
      title: doc.title || document.title,
      t: Date.now(),
    };
  }

  async function fetchPage(url, { useCache = true } = {}) {
    const key = url.split("#")[0];
    if (useCache && cache.has(key)) {
      const hit = cache.get(key);
      if (Date.now() - hit.t < PREFETCH_TTL) return hit;
    }
    const res = await fetch(key, {
      headers: { "X-Soft-Nav": "1", Accept: "text/html" },
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(String(res.status));
    const parsed = parseDoc(await res.text());
    if (!parsed) throw new Error("parse");
    cache.set(key, parsed);
    if (cache.size > 28) cache.delete(cache.keys().next().value);
    return parsed;
  }

  function activateScripts(root) {
    const slot = root.querySelector("#page-scripts");
    if (!slot) return;
    // Move/execute scripts that were inside the page block
    slot.querySelectorAll("script").forEach((old) => {
      const s = document.createElement("script");
      if (old.src) {
        s.src = old.src;
        s.async = false;
      } else {
        s.textContent = old.textContent;
      }
      document.body.appendChild(s);
      // Keep function definitions; remove tag to avoid duplicates growing forever
      // but keep last version on body briefly
      setTimeout(() => s.remove(), 0);
    });
  }

  function reinitAlpine(root) {
    if (!window.Alpine) return;
    try {
      Alpine.initTree(root);
    } catch (_) {
      /* ignore */
    }
  }

  function updateActiveNav(url) {
    let path;
    try {
      path = new URL(url, location.href).pathname;
    } catch {
      return;
    }
    document.querySelectorAll("[data-nav-link]").forEach((el) => {
      let p;
      try {
        p = new URL(el.getAttribute("href") || "", location.href).pathname;
      } catch {
        return;
      }
      const active =
        p === path || (p.length > 1 && path.startsWith(p.replace(/\/$/, "") + "/")) || (p === "/" && path === "/");
      // More precise matching for home
      let isActive = false;
      if (p === "/" || p.endsWith("/downloads/") === false) {
        if (p === "/") isActive = path === "/" || path === "";
        else isActive = path === p || path === p.replace(/\/$/, "") || path.startsWith(p.endsWith("/") ? p : p + "/");
      }
      // Override with data-nav-match if present
      const match = el.getAttribute("data-nav-match");
      if (match === "home") isActive = path === "/" || path === "";
      else if (match === "history") isActive = path.includes("/history");
      else if (match === "dashboard") isActive = path.includes("/dashboard");
      else if (match === "files") isActive = path.includes("/files");
      else if (match === "api") isActive = path.includes("/api/docs") || path.includes("/api/schema");
      else isActive = path === p || path.startsWith(p.replace(/\/?$/, "/"));

      el.classList.toggle("nav-link-active", isActive);
    });
  }

  function isDarkMode() {
    return document.documentElement.classList.contains("dark");
  }

  function lockThemePaint() {
    // Ensure dark class cannot be lost mid-navigation (Alpine shell stays on <html>)
    const dark = isDarkMode();
    document.documentElement.style.backgroundColor = dark ? "#06060a" : "#f4f6fb";
    const canvas = document.getElementById("theme-canvas");
    if (canvas) canvas.style.backgroundColor = dark ? "#06060a" : "#f4f6fb";
    // Hide media blur immediately so light scrim cannot flash
    const mb = document.getElementById("media-backdrop");
    if (mb) {
      mb.classList.remove("is-visible");
      mb.style.visibility = "hidden";
      mb.style.opacity = "0";
    }
  }

  function unlockThemePaint() {
    // Keep inline bg for a frame then leave CSS classes in charge
    requestAnimationFrame(() => {
      // Keep solid bg always — safer than clearing (avoids flash)
      const dark = isDarkMode();
      document.documentElement.style.backgroundColor = dark ? "#06060a" : "#f4f6fb";
    });
  }

  function ensureDarkClass() {
    // Re-assert theme every navigation frame — Alpine must never leave light styles on
    if (window.__VDL_DARK__) {
      document.documentElement.classList.add("dark");
      document.documentElement.style.backgroundColor = "#06060a";
      document.documentElement.style.colorScheme = "dark";
      const canvas = document.getElementById("theme-canvas");
      if (canvas) canvas.style.backgroundColor = "#06060a";
    }
  }

  function doSwap(entry, url) {
    const current = document.getElementById(ROOT_ID);
    if (!current) {
      location.href = url;
      return;
    }
    const wrap = document.createElement("div");
    wrap.innerHTML = entry.rootHtml.trim();
    const next = wrap.firstElementChild;
    if (!next) {
      location.href = url;
      return;
    }

    ensureDarkClass();

    // INSTANT swap — no opacity fade (fades expose light glass / white canvas)
    current.replaceWith(next);

    ensureDarkClass();

    try {
      window.scrollTo({ top: 0, behavior: "instant" });
    } catch {
      window.scrollTo(0, 0);
    }
    document.title = entry.title;
    updateActiveNav(url);

    if (typeof setMediaBackdrop === "function") setMediaBackdrop(null);

    activateScripts(next);
    reinitAlpine(next);

    ensureDarkClass();

    document.dispatchEvent(new CustomEvent("vdl:navigated", { detail: { url } }));
  }

  async function applyPage(entry, url, { push }) {
    lockThemePaint();
    ensureDarkClass();
    doSwap(entry, url);
    ensureDarkClass();
    unlockThemePaint();

    if (push) history.pushState({ soft: true }, entry.title, url);
  }

  async function navigate(url, { push = true, useCache = true } = {}) {
    if (navigating) return;
    const absolute = new URL(url, location.href).href;
    if (push && absolute.split("#")[0] === location.href.split("#")[0]) return;

    navigating = true;
    ensureDarkClass();
    lockThemePaint();
    document.documentElement.classList.add("is-navigating");
    // No top progress bar flash in dark mode (can read as a light streak)
    if (!isDarkMode()) showBarDelayed();
    try {
      const entry = await fetchPage(absolute, { useCache });
      await applyPage(entry, absolute, { push });
    } catch {
      // Preserve theme across hard fallback
      ensureDarkClass();
      location.href = url;
      return;
    } finally {
      navigating = false;
      document.documentElement.classList.remove("is-navigating");
      hideBar();
      ensureDarkClass();
      unlockThemePaint();
    }
  }

  function prefetch(url) {
    if (!sameOrigin(url)) return;
    const key = new URL(url, location.href).href.split("#")[0];
    if (cache.has(key)) return;
    const run = () => fetchPage(key).catch(() => {});
    if ("requestIdleCallback" in window) requestIdleCallback(run, { timeout: 1200 });
    else setTimeout(run, 180);
  }

  document.addEventListener(
    "click",
    (e) => {
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = e.target.closest?.("a");
      if (!shouldBoost(a)) return;
      e.preventDefault();
      a.classList.add("is-pressed");
      setTimeout(() => a.classList.remove("is-pressed"), 160);
      navigate(a.href, { push: true });
    },
    true
  );

  document.addEventListener(
    "pointerenter",
    (e) => {
      const a = e.target.closest?.("a");
      if (shouldBoost(a)) prefetch(a.href);
    },
    true
  );

  document.addEventListener(
    "touchstart",
    (e) => {
      const a = e.target.closest?.("a");
      if (shouldBoost(a)) prefetch(a.href);
    },
    { capture: true, passive: true }
  );

  window.addEventListener("popstate", () => {
    navigate(location.href, { push: false, useCache: true });
  });

  // Instant press feedback
  const PRESS_SEL =
    "button, .btn-primary, .btn-secondary, .btn-ghost, .btn-glass, .chip, .nav-link, a.dropdown-item";
  document.addEventListener(
    "pointerdown",
    (e) => {
      const el = e.target.closest?.(PRESS_SEL);
      if (!el || el.disabled) return;
      el.classList.add("is-pressed");
    },
    true
  );
  const clearPress = () =>
    document.querySelectorAll(".is-pressed").forEach((el) => el.classList.remove("is-pressed"));
  document.addEventListener("pointerup", clearPress, true);
  document.addEventListener("pointercancel", clearPress, true);
  document.addEventListener("pointerleave", (e) => {
    if (e.target instanceof Element) e.target.closest?.(PRESS_SEL)?.classList.remove("is-pressed");
  }, true);

  // Soft GET forms (history filters)
  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.hasAttribute("data-no-boost")) return;
      if ((form.method || "get").toLowerCase() !== "get") return;
      e.preventDefault();
      const action = form.getAttribute("action") || location.pathname;
      const qs = new URLSearchParams(new FormData(form)).toString();
      navigate(qs ? `${action}?${qs}` : action, { push: true, useCache: false });
    },
    true
  );

  window.softNavigate = (url) => navigate(url, { push: true });
  window.softPrefetch = prefetch;

  if (!history.state?.soft) {
    history.replaceState({ soft: true }, document.title, location.href);
  }

  // Prefetch primary nav targets after first paint
  window.addEventListener("load", () => {
    document.querySelectorAll("[data-nav-link]").forEach((a) => {
      const href = a.getAttribute("href");
      if (href) prefetch(href);
    });
  });
})();
