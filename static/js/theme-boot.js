/**
 * Runs as early as possible (blocking, in <head>).
 * Sets dark mode BEFORE Alpine/CSS can paint a light frame.
 */
(function () {
  var KEY = "vdl-theme";
  function preferDark() {
    try {
      var t = localStorage.getItem(KEY);
      if (t === "dark") return true;
      if (t === "light") return false;
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch (e) {
      return false;
    }
  }

  function apply(dark) {
    var root = document.documentElement;
    root.classList.toggle("dark", !!dark);
    root.style.backgroundColor = dark ? "#06060a" : "#f4f6fb";
    root.style.colorScheme = dark ? "dark" : "light";
    // Expose for Alpine / soft-nav (no flash from wrong initial state)
    window.__VDL_DARK__ = !!dark;
  }

  apply(preferDark());

  // If anything (e.g. Alpine class binding) strips .dark, put it back immediately
  try {
    var obs = new MutationObserver(function () {
      if (window.__VDL_DARK__ && !document.documentElement.classList.contains("dark")) {
        document.documentElement.classList.add("dark");
        document.documentElement.style.backgroundColor = "#06060a";
      }
      if (!window.__VDL_DARK__ && document.documentElement.classList.contains("dark")) {
        // Only re-strip if we intentionally want light — avoid fighting toggle mid-click
      }
    });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    window.__VDL_THEME_OBS__ = obs;
  } catch (e) {}

  window.__VDL_APPLY_THEME__ = apply;
  window.__VDL_PREFER_DARK__ = preferDark;
})();
