// pymyIO anywidget entry point.
// Loads the vendored d3 bundle + myIOapi engine via <script> tags, then
// re-renders whenever the `config` traitlet changes.

let enginePromise = null;

function injectScript(url, role) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-pymyio="${url}"]`);
    if (existing) {
      if (existing.dataset.loaded === "true") { resolve(); return; }
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error(`Failed to load ${url}`)));
      return;
    }
    const tag = document.createElement("script");
    tag.src = url;
    tag.async = false;
    tag.dataset.pymyio = url;
    tag.dataset.pymyioRole = role;
    tag.addEventListener("load", () => { tag.dataset.loaded = "true"; resolve(); });
    tag.addEventListener("error", () => reject(new Error(`Failed to load ${url}`)));
    document.head.appendChild(tag);
  });
}

async function loadEngine(baseUrl) {
  if (typeof window.myIOchart === "function") {
    window.__pymyioEngineVersion ||= "unknown";
    return Promise.resolve();
  }
  if (enginePromise) return enginePromise;
  enginePromise = (async () => {
    await injectScript(`${baseUrl}lib/d3.min.js`, "d3-core");
    await injectScript(`${baseUrl}lib/d3-hexbin.js`, "d3-hexbin");
    await injectScript(`${baseUrl}lib/d3-sankey.min.js`, "d3-sankey");
    await injectScript(`${baseUrl}myIOapi.js`, "engine");
    window.__pymyioEngineVersion = (window.myIOchart?.version) || "unknown";
  })();
  return enginePromise;
}

function applySize(el, width, height) {
  el.style.width = typeof width === "number" ? `${width}px` : String(width);
  el.style.height = typeof height === "number" ? `${height}px` : String(height);
}

function render({ model, el }) {
  const container = document.createElement("div");
  container.className = "pymyio-chart";
  applySize(container, model.get("width"), model.get("height"));
  el.appendChild(container);

  // Three-tier base-URL resolution. The _base_url traitlet overrides when
  // import.meta.url resolves incorrectly (nbconvert, Colab sandboxed iframe).
  // Otherwise derive from import.meta.url, with "./" as a last resort.
  const override = model.get("_base_url");
  const baseUrl = (typeof override === "string" && override.length > 0)
    ? (override.endsWith("/") ? override : override + "/")
    : ((typeof import.meta !== "undefined" && import.meta.url)
        ? new URL(".", import.meta.url).href
        : "./");

  let chart = null;

  async function draw() {
    try {
      await loadEngine(baseUrl);
    } catch (err) {
      model.set("last_error", { message: String(err), at: new Date().toISOString() });
      model.save_changes();
      return;
    }
    if (typeof window.myIOchart !== "function") {
      model.set("last_error", {
        message: "myIOchart constructor not found on window — engine bundle did not initialize.",
        at: new Date().toISOString(),
      });
      model.save_changes();
      return;
    }
    if (chart) {
      try { chart.destroy(); } catch (_) { /* noop */ }
      while (container.firstChild) container.removeChild(container.firstChild);
      chart = null;
    }
    const config = model.get("config") || {};
    const rect = container.getBoundingClientRect();
    chart = new window.myIOchart({
      element: container,
      config,
      width: rect.width || 600,
      height: rect.height || 400,
    });
    chart.on?.("error", (e) => {
      model.set("last_error", {
        message: e.message,
        layer: e.layer ? e.layer.label : null,
        at: new Date().toISOString(),
      });
      model.save_changes();
    });
    chart.on?.("brushed", (e) => { model.set("brushed", e); model.save_changes(); });
    chart.on?.("annotated", (e) => { model.set("annotated", e); model.save_changes(); });
    chart.on?.("rollover", (e) => { model.set("rollover", e); model.save_changes(); });
  }

  model.on("change:config", draw);
  model.on("change:width change:height", () => {
    applySize(container, model.get("width"), model.get("height"));
    draw();
  });

  draw();

  return () => {
    if (chart) { try { chart.destroy(); } catch (_) {} }
  };
}

export default { render };
