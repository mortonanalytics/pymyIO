// pymyIO anywidget entry point.
// Loads the vendored d3 bundle + myIOapi engine via <script> tags, then
// re-renders whenever the `config` traitlet changes.

let enginePromise = null;

function injectScript(url) {
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
    tag.addEventListener("load", () => { tag.dataset.loaded = "true"; resolve(); });
    tag.addEventListener("error", () => reject(new Error(`Failed to load ${url}`)));
    document.head.appendChild(tag);
  });
}

async function loadEngine(baseUrl) {
  if (enginePromise) return enginePromise;
  enginePromise = (async () => {
    await injectScript(`${baseUrl}lib/d3.min.js`);
    await injectScript(`${baseUrl}lib/d3-hexbin.js`);
    await injectScript(`${baseUrl}lib/d3-sankey.min.js`);
    await injectScript(`${baseUrl}myIOapi.js`);
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

  // The vendored myIOapi.js script lives next to this widget.js, so derive
  // the base URL from import.meta.url when available, else fall back to "./".
  const baseUrl = (typeof import.meta !== "undefined" && import.meta.url)
    ? new URL(".", import.meta.url).href
    : "./";

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
