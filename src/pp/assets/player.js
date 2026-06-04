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
  var step = 0;  // build step within the current slide

  function bboxOf(el) {
    var raw = (el.getAttribute("data-pp-bbox") || "0 0 100 100").split(/[ ,]+/);
    return raw.map(parseFloat);
  }

  function buildEls(slide) {
    return Array.prototype.slice.call(
      slide.querySelectorAll("[data-pp-effect-order]"));
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
            // Re-trigger the CSS animation.
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

  function show(index, atStep, animateStep) {
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
    step = atStep == null ? 0 : atStep;
    applyBuild(slides[current], step, animateStep == null ? -1 : animateStep);
    updateIndicator(bb);
  }

  function next() {
    if (step < maxStep(slides[current])) {
      step += 1;
      applyBuild(slides[current], step, step);
      updateIndicator(bboxOf(slides[current]));
    } else {
      show(current + 1, 0);
    }
  }

  function prev() {
    if (step > 0) {
      step -= 1;
      applyBuild(slides[current], step, -1);
      updateIndicator(bboxOf(slides[current]));
    } else {
      var target = current > 0 ? current - 1 : (cfg.loop ? slides.length - 1 : 0);
      // Enter the previous slide fully built.
      show(target, maxStep(slides[target]));
    }
  }

  function onKey(e) {
    switch (e.key) {
      case "ArrowRight": case "PageDown": case " ": case "Enter": next(); break;
      case "ArrowLeft": case "PageUp": case "Backspace": prev(); break;
      case "Home": show(0, 0); break;
      case "End": show(slides.length - 1, maxStep(slides[slides.length - 1])); break;
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
  function updateIndicator(bb) {
    if (!indicator) return;
    indicator.textContent = (current + 1) + " / " + slides.length;
    // The viewBox is the current slide's absolute page box, so anchor the
    // indicator to that box's origin instead of the document origin.
    if (bb) {
      indicator.setAttribute("x", (bb[0] + 0.01 * bb[2]).toString());
      indicator.setAttribute("y", (bb[1] + 0.03 * bb[3]).toString());
      var fs = Math.max(8, 0.018 * bb[3]);
      indicator.setAttribute("font-size", fs.toString());
    }
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
