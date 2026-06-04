/* Minimal self-contained SVG presentation player.
 *
 * Reads window.PP_CONFIG = { count, transition, loop, start } and the
 * data-pp-slide / data-pp-bbox attributes injected by jsexport.build().
 * Shows one slide at a time, frames it via the SVG viewBox so it fills the
 * viewport, and provides keyboard / click navigation with CSS transitions.
 */
(function () {
  "use strict";

  var cfg = window.PP_CONFIG || { count: 0, transition: "none", loop: false, start: 0 };
  var svg = document.documentElement;

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

  function bboxOf(el) {
    var raw = (el.getAttribute("data-pp-bbox") || "0 0 100 100").split(/[ ,]+/);
    return raw.map(parseFloat);
  }

  function show(index) {
    if (index < 0) index = cfg.loop ? slides.length - 1 : 0;
    if (index >= slides.length) index = cfg.loop ? 0 : slides.length - 1;
    current = index;
    var bb = bboxOf(slides[current]);
    svg.setAttribute("viewBox", bb[0] + " " + bb[1] + " " + bb[2] + " " + bb[3]);
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
    updateIndicator();
  }

  function next() { show(current + 1); }
  function prev() { show(current - 1); }

  function onKey(e) {
    switch (e.key) {
      case "ArrowRight": case "PageDown": case " ": case "Enter": next(); break;
      case "ArrowLeft": case "PageUp": case "Backspace": prev(); break;
      case "Home": show(0); break;
      case "End": show(slides.length - 1); break;
      case "f": case "F": toggleFullscreen(); break;
      case "Escape": if (document.fullscreenElement) document.exitFullscreen(); break;
      default: return;
    }
    e.preventDefault();
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (svg.requestFullscreen) svg.requestFullscreen();
  }

  var indicator;
  function updateIndicator() {
    if (!indicator) return;
    indicator.textContent = (current + 1) + " / " + slides.length;
  }

  function buildIndicator() {
    var ns = "http://www.w3.org/2000/svg";
    indicator = document.createElementNS(ns, "text");
    indicator.setAttribute("class", "pp-indicator");
    indicator.setAttribute("x", "4");
    indicator.setAttribute("y", "12");
    svg.appendChild(indicator);
  }

  document.addEventListener("keydown", onKey);
  svg.addEventListener("click", function (e) {
    // Left third = previous, otherwise next.
    if (e.clientX < window.innerWidth / 3) prev(); else next();
  });

  buildIndicator();
  show(current);
})();
