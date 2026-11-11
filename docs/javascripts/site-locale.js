/* One preference, ordinary document navigation; URL and fragment stay authoritative. */
(() => {
  "use strict";
  const base = "/quant-backtest-engine/";
  const key = "engine.site.locale.v1";
  function get() {
    try {
      return localStorage.getItem(key) === "zh-CN" ? "zh-CN" : "en";
    } catch {
      return "en";
    }
  }
  function save(value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* Storage is optional. */
    }
  }
  function apply(map) {
    const current = location.pathname.slice(base.length);
    const pair = Object.entries(map.pairs).find(
      ([en, zh]) => current === en || current === zh,
    );
    const currentLocale = pair && current === pair[1] ? "zh-CN" : "en";
    document
      .querySelectorAll("[data-site-locale],a[hreflang]")
      .forEach((link) => {
        const target = link.dataset.siteLocale || link.getAttribute("hreflang");
        if (!["en", "zh-CN"].includes(target)) return;
        link.addEventListener("click", () => save(target));
        if (pair) {
          let hash = decodeURIComponent(location.hash.slice(1));
          const anchors = map.anchors[pair[0]] || {};
          if (currentLocale !== target)
            hash =
              target === "zh-CN"
                ? anchors[hash] || hash
                : Object.entries(anchors).find(([, zh]) => zh === hash)?.[0] ||
                  hash;
          link.href =
            base +
            pair[target === "zh-CN" ? 1 : 0] +
            (hash ? "#" + encodeURIComponent(hash) : "");
        }
      });
    const preference = get();
    document.querySelectorAll("[data-site-nav]").forEach((link) => {
      const route = new URL(link.href).pathname.slice(base.length);
      const p = Object.entries(map.pairs).find(
        ([en, zh]) => route === en || route === zh,
      );
      if (p) link.href = base + p[preference === "zh-CN" ? 1 : 0];
    });
    if (current === "") {
      const link = document.createElement("a");
      link.href = base + (preference === "zh-CN" ? "index.zh-CN/" : "");
      link.textContent =
        preference === "zh-CN" ? "继续阅读中文" : "Continue in English";
      link.dataset.continueLocale = preference;
      document.querySelector("main")?.prepend(link);
    }
  }
  fetch(base + "site/locale-routes.json")
    .then((r) => {
      if (!r.ok) throw Error("locale map unavailable");
      return r.json();
    })
    .then(apply)
    .catch(() => {});
})();
