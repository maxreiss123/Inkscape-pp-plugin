/* Initialise embedded content renderers (Mermaid, highlight.js, marked).
 *
 * The renderer libraries are loaded from a CDN by jsexport; this script waits
 * for each global to appear (scripts in SVG can load asynchronously) and then
 * renders the matching foreignObject content. Safe to run with none present.
 */
(function () {
  "use strict";

  function whenReady(test, run, tries) {
    tries = tries == null ? 100 : tries;
    if (test()) { run(); return; }
    if (tries <= 0) return;
    setTimeout(function () { whenReady(test, run, tries - 1); }, 60);
  }

  // Mermaid diagrams.
  if (document.querySelector(".mermaid")) {
    whenReady(function () { return window.mermaid; }, function () {
      try {
        window.mermaid.initialize({ startOnLoad: false });
        if (window.mermaid.run) window.mermaid.run();
        else window.mermaid.init(undefined, document.querySelectorAll(".mermaid"));
      } catch (e) { /* leave source visible on failure */ }
    });
  }

  // Markdown blocks: render the element's text as GitHub-flavoured Markdown.
  var mds = document.querySelectorAll(".pp-md");
  if (mds.length) {
    whenReady(function () { return window.marked; }, function () {
      for (var i = 0; i < mds.length; i++) {
        var el = mds[i];
        var srcText = el.textContent;
        el.innerHTML = window.marked.parse(srcText);
      }
    });
  }

  // Code blocks: syntax highlight.
  if (document.querySelector("pre code")) {
    whenReady(function () { return window.hljs; }, function () {
      var blocks = document.querySelectorAll("pre code");
      for (var i = 0; i < blocks.length; i++) {
        try { window.hljs.highlightElement(blocks[i]); } catch (e) { /* noop */ }
      }
    });
  }
})();
