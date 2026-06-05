/* Minimal self-contained SVG presentation player.
 *
 * Reads window.PP_CONFIG = { count, transition, loop, start, notes:[...] } and
 * the data-pp-slide / data-pp-bbox attributes injected by jsexport.build().
 * Shows one slide at a time (framed via the SVG viewBox) with keyboard / click
 * navigation, click-to-build animations, a presenter view (press P) and a
 * single-screen notes overlay (press S).
 */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var XHTML = "http://www.w3.org/1999/xhtml";
  var XLINK = "http://www.w3.org/1999/xlink";

  var cfg = window.PP_CONFIG ||
    { count: 0, transition: "none", loop: false, start: 0, notes: [] };
  var notes = cfg.notes || [];
  var svg = document.documentElement;
  var mode = (location.hash || "").indexOf("pp-presenter") >= 0 ? "presenter" : "audience";

  function svgEl(n) { return document.createElementNS(SVGNS, n); }
  function htmlEl(n) { return document.createElementNS(XHTML, n); }

  function collectSlides() {
    var nodes = svg.querySelectorAll("[data-pp-slide]");
    var slides = Array.prototype.slice.call(nodes);
    slides.sort(function (a, b) {
      return (+a.getAttribute("data-pp-slide")) - (+b.getAttribute("data-pp-slide"));
    });
    return slides;
  }

  var slides = collectSlides();
  var current = Math.max(0, Math.min(cfg.start | 0, slides.length - 1));
  var step = 0;

  function bboxOf(el) {
    return (el.getAttribute("data-pp-bbox") || "0 0 100 100").split(/[ ,]+/).map(parseFloat);
  }
  function buildEls(slide) {
    return Array.prototype.slice.call(slide.querySelectorAll("[data-pp-effect-order]"));
  }
  function maxStep(slide) {
    var m = 0;
    buildEls(slide).forEach(function (el) {
      m = Math.max(m, parseInt(el.getAttribute("data-pp-effect-order"), 10) || 0);
    });
    return m;
  }
  function applyBuild(slide, upto, animateStep) {
    buildEls(slide).forEach(function (el) {
      var o = parseInt(el.getAttribute("data-pp-effect-order"), 10) || 0;
      if (o <= upto) {
        el.style.display = "inline";
        el.setAttribute("class", (el.getAttribute("class") || "")
          .replace(/\bpp-anim-\w+\b/g, "").trim());
        if (o === animateStep && animateStep > 0) {
          var t = el.getAttribute("data-pp-effect-type") || "appear";
          if (t !== "appear") {
            void el.getBoundingClientRect();
            el.setAttribute("class",
              ((el.getAttribute("class") || "") + " pp-anim-" + t).trim());
          }
        }
      } else {
        el.style.display = "none";
      }
    });
  }

  // -- Cross-window sync -----------------------------------------------------
  var chan = ("BroadcastChannel" in window) ? new BroadcastChannel("pp-deck") : null;
  function broadcast() {
    var msg = { index: current, step: step };
    if (chan) { chan.postMessage(msg); }
    else { try { localStorage.setItem("pp-deck", JSON.stringify(msg) + "|" + Date.now()); } catch (e) { /* */ } }
  }
  function applyRemote(d) {
    if (!d) return;
    goto(d.index, d.step, -1, true);
  }
  if (chan) chan.onmessage = function (e) { applyRemote(e.data); };
  window.addEventListener("storage", function (e) {
    if (e.key === "pp-deck" && e.newValue) {
      try { applyRemote(JSON.parse(e.newValue.split("|")[0])); } catch (err) { /* */ }
    }
  });

  // -- Navigation ------------------------------------------------------------
  function goto(index, st, animateStep, fromRemote) {
    if (index < 0) index = cfg.loop ? slides.length - 1 : 0;
    if (index >= slides.length) index = cfg.loop ? 0 : slides.length - 1;
    current = index;
    var mx = maxStep(slides[current]);
    step = Math.max(0, Math.min(st == null ? 0 : st, mx));
    if (mode === "presenter") renderPresenter();
    else renderAudience(animateStep == null ? -1 : animateStep);
    if (!fromRemote) broadcast();
  }
  function next() {
    if (step < maxStep(slides[current])) goto(current, step + 1, step + 1);
    else goto(current + 1, 0, -1);
  }
  function prev() {
    if (step > 0) goto(current, step - 1, -1);
    else goto(current - 1, 1e9, -1);
  }

  // -- Audience rendering ----------------------------------------------------
  var indicator;
  function renderAudience(animateStep) {
    var bb = bboxOf(slides[current]);
    svg.setAttribute("viewBox", bb.join(" "));
    for (var i = 0; i < slides.length; i++) {
      var s = slides[i];
      if (i === current) {
        s.style.display = "inline";
        s.setAttribute("class", "pp-slide pp-current pp-" + (cfg.transition || "none"));
      } else {
        s.style.display = "none";
        s.setAttribute("class", "pp-slide");
      }
    }
    applyBuild(slides[current], step, animateStep);
    if (indicator) {
      indicator.textContent = (current + 1) + " / " + slides.length;
      indicator.setAttribute("x", (bb[0] + 0.01 * bb[2]).toString());
      indicator.setAttribute("y", (bb[1] + 0.03 * bb[3]).toString());
      indicator.setAttribute("font-size", Math.max(8, 0.018 * bb[3]).toString());
    }
    if (overlay) updateOverlay();
  }
  function buildIndicator() {
    indicator = svgEl("text");
    indicator.setAttribute("class", "pp-indicator");
    svg.appendChild(indicator);
  }

  // -- Presenter view --------------------------------------------------------
  var pres = null;
  var startTime = Date.now();
  function fmt(ms) {
    var s = Math.floor(ms / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return (h > 0 ? h + ":" : "") + p(m % 60) + ":" + p(s % 60);
  }
  function previewSvg(index, cls) {
    var holder = htmlEl("div");
    holder.setAttribute("class", cls);
    if (index < 0 || index >= slides.length) {
      holder.textContent = "—";
      return holder;
    }
    var bb = bboxOf(slides[index]);
    var s = svgEl("svg");
    s.setAttribute("viewBox", bb.join(" "));
    s.setAttribute("preserveAspectRatio", "xMidYMid meet");
    s.setAttribute("width", "100%");
    s.setAttribute("height", "100%");
    var u = svgEl("use");
    u.setAttribute("href", "#pp-slide-" + index);
    u.setAttributeNS(XLINK, "href", "#pp-slide-" + index);
    s.appendChild(u);
    holder.appendChild(s);
    return holder;
  }
  function buildPresenter() {
    svg.setAttribute("viewBox", "0 0 1280 720");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    var fo = svgEl("foreignObject");
    fo.setAttribute("x", "0"); fo.setAttribute("y", "0");
    fo.setAttribute("width", "1280"); fo.setAttribute("height", "720");
    var body = htmlEl("body");
    body.setAttribute("class", "pp-presenter");
    body.innerHTML =
      '<div class="pp-pv-top">' +
      '  <div class="pp-pv-cur"><div class="pp-pv-label">Current</div><div class="pp-pv-stage" id="pp-cur"></div></div>' +
      '  <div class="pp-pv-side">' +
      '    <div class="pp-pv-clock"><span id="pp-elapsed">00:00</span><span id="pp-clock"></span></div>' +
      '    <div class="pp-pv-next"><div class="pp-pv-label">Next</div><div class="pp-pv-stage" id="pp-next"></div></div>' +
      '  </div>' +
      '</div>' +
      '<div class="pp-pv-notes"><div class="pp-pv-label">Notes</div><div class="pp-pv-notetext" id="pp-notes"></div></div>' +
      '<div class="pp-pv-foot"><button id="pp-prev">◀ Prev</button>' +
      '<span id="pp-pos"></span><button id="pp-next">Next ▶</button></div>';
    fo.appendChild(body);
    svg.appendChild(fo);
    pres = {
      cur: body.querySelector("#pp-cur"), next: body.querySelector("#pp-next"),
      nextStage: body.querySelector("#pp-next"), notes: body.querySelector("#pp-notes"),
      pos: body.querySelector("#pp-pos"), elapsed: body.querySelector("#pp-elapsed"),
      clock: body.querySelector("#pp-clock"),
    };
    body.querySelector("#pp-prev").addEventListener("click", prev);
    body.querySelector("#pp-next").addEventListener("click", next);
    setInterval(tickClock, 1000);
  }
  function tickClock() {
    if (!pres) return;
    pres.elapsed.textContent = fmt(Date.now() - startTime);
    pres.clock.textContent = new Date().toLocaleTimeString();
  }
  function renderPresenter() {
    if (!pres) return;
    var cur = document.getElementById("pp-cur");
    var nxt = document.getElementById("pp-next");
    cur.innerHTML = ""; nxt.innerHTML = "";
    cur.appendChild(previewSvg(current, "pp-pv-fill"));
    nxt.appendChild(previewSvg(current + 1, "pp-pv-fill"));
    pres.notes.textContent = notes[current] || "(no notes)";
    pres.pos.textContent = (current + 1) + " / " + slides.length +
      (maxStep(slides[current]) ? "  · step " + step : "");
    tickClock();
  }

  // -- Single-screen notes overlay (S) --------------------------------------
  var overlay = null;
  function toggleOverlay() {
    if (overlay) { overlay.parentNode.removeChild(overlay); overlay = null; return; }
    overlay = svgEl("foreignObject");
    var body = htmlEl("body");
    body.setAttribute("class", "pp-overlay");
    body.innerHTML = '<div class="pp-ov-time" id="pp-ov-time"></div>' +
      '<div class="pp-ov-notes" id="pp-ov-notes"></div>';
    overlay.appendChild(body);
    svg.appendChild(overlay);
    updateOverlay();
  }
  function updateOverlay() {
    if (!overlay) return;
    var bb = bboxOf(slides[current]);
    overlay.setAttribute("x", bb[0]); overlay.setAttribute("y", bb[1] + bb[3] * 0.74);
    overlay.setAttribute("width", bb[2]); overlay.setAttribute("height", bb[3] * 0.26);
    var n = document.getElementById("pp-ov-notes");
    var t = document.getElementById("pp-ov-time");
    if (n) n.textContent = notes[current] || "(no notes)";
    if (t) t.textContent = fmt(Date.now() - startTime) + "  ·  " + (current + 1) + "/" + slides.length;
  }

  // -- Input -----------------------------------------------------------------
  function openPresenter() {
    window.open(location.href.split("#")[0] + "#pp-presenter", "pp-presenter",
      "width=1100,height=720");
  }
  function onKey(e) {
    switch (e.key) {
      case "ArrowRight": case "PageDown": case " ": case "Enter": next(); break;
      case "ArrowLeft": case "PageUp": case "Backspace": prev(); break;
      case "Home": goto(0, 0); break;
      case "End": goto(slides.length - 1, 1e9); break;
      case "f": case "F": toggleFullscreen(); break;
      case "p": case "P": if (mode === "audience") openPresenter(); break;
      case "s": case "S": if (mode === "audience") { toggleOverlay(); } break;
      case "Escape": if (document.fullscreenElement) document.exitFullscreen(); break;
      default: return;
    }
    e.preventDefault();
  }
  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (svg.requestFullscreen) svg.requestFullscreen();
  }

  document.addEventListener("keydown", onKey);
  svg.addEventListener("click", function (e) {
    if (e.target && e.target.closest && e.target.closest("button")) return;
    if (e.clientX < window.innerWidth / 3) prev(); else next();
  });

  if (mode === "presenter") {
    buildPresenter();
  } else {
    buildIndicator();
  }
  goto(current, 0, -1, true);
})();
