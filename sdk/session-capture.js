// session-capture.js — tiny behavioral telemetry SDK.
//
// Load this from the bank's web frontend and call:
//   AllGreenFraud.init({ sessionId, userId, endpoint });
//
// It batches mousemove/click/keydown/scroll events and POSTs them every 5s.
// Budget: < 8KB gzipped. No external deps.
//
// Phase 1 note: the backend /v1/events/session endpoint currently accepts and
// logs the events but doesn't score them yet. Integration teams can start
// wiring this up safely.

(function () {
  "use strict";

  var DEFAULT_ENDPOINT = "/v1/events/session";
  var BATCH_INTERVAL_MS = 5000;
  var MAX_QUEUE = 500; // drop rather than OOM the tab

  var events = [];
  var sessionId = null;
  var userId = null;
  var endpoint = DEFAULT_ENDPOINT;
  var batchTimer = null;
  var initialized = false;

  function throttle(fn, ms) {
    var last = 0;
    return function () {
      var now = Date.now();
      if (now - last > ms) {
        last = now;
        fn.apply(this, arguments);
      }
    };
  }

  function push(ev) {
    if (events.length >= MAX_QUEUE) return;
    events.push(ev);
  }

  function captureMouseMove(e) {
    push({ type: "mousemove", x: e.clientX, y: e.clientY, ts_ms: Date.now() });
  }
  function captureClick(e) {
    push({ type: "click", x: e.clientX, y: e.clientY, ts_ms: Date.now() });
  }
  function captureKeydown(e) {
    var start = Date.now();
    var handler = function () {
      push({
        type: "keydown",
        key_code: e.keyCode,
        dwell_ms: Date.now() - start,
        ts_ms: start,
      });
      document.removeEventListener("keyup", handler, true);
    };
    document.addEventListener("keyup", handler, true);
  }
  function captureScroll() {
    var h = document.body.scrollHeight || 1;
    push({ type: "scroll", depth: window.scrollY / h, ts_ms: Date.now() });
  }

  function attachListeners() {
    document.addEventListener("mousemove", throttle(captureMouseMove, 100), true);
    document.addEventListener("click", captureClick, true);
    document.addEventListener("keydown", captureKeydown, true);
    document.addEventListener("scroll", throttle(captureScroll, 200), true);
  }

  function flush() {
    if (!events.length) return;
    var batch = events.splice(0, events.length);
    try {
      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, user_id: userId, events: batch }),
        keepalive: true,
      }).catch(function () {
        // Swallow: we don't want SDK failures to break the bank's app.
      });
    } catch (_) {
      // same
    }
  }

  function startBatcher() {
    batchTimer = setInterval(flush, BATCH_INTERVAL_MS);
    // Best-effort flush on unload
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", flush);
  }

  window.AllGreenFraud = {
    init: function (cfg) {
      if (initialized) return;
      if (!cfg || !cfg.sessionId || !cfg.userId) {
        // eslint-disable-next-line no-console
        console.warn("[AllGreenFraud] init called without sessionId/userId");
        return;
      }
      sessionId = cfg.sessionId;
      userId = cfg.userId;
      if (cfg.endpoint) endpoint = cfg.endpoint;
      attachListeners();
      startBatcher();
      initialized = true;
    },
    // Exposed for tests / manual flush
    _flush: flush,
  };
})();
