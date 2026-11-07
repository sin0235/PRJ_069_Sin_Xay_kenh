/* Bộ điều khiển máy quay thuần thời gian dùng chung cho cảnh sơ đồ và HyperFrames. */
(function (root) {
  "use strict";
  if (root.__bahaCamera) return;
  var AUTO = {
    CHART_TARGET: "DOLLY_RACK", CHART_GROWTH: "PARALLAX_PASS", COMPARE_DOCS: "ORBIT_ARC", PROCESS_RAIL: "PARALLAX_PASS",
    COST_SLICE: "CRANE_DIVE", CASH_FLOW: "ORBIT_ARC", STACK_HEIGHT: "CRANE_DIVE", DOC_LAYERS: "DOLLY_RACK",
    END_CARD: "DOLLY_RACK", OPEN_NUMBER: "DOLLY_RACK", OPEN_DRAIN: "CRANE_DIVE", OPEN_QUESTION: "ORBIT_ARC",
    OPEN_HOOK: "WHIP_PAN_SETTLE", FUNNEL: "CRANE_DIVE", TIMELINE: "PARALLAX_PASS", BEFORE_AFTER: "DOLLY_ZOOM",
    DONUT_SHARE: "ORBIT_ARC", GAUGE: "DOLLY_RACK", CHECKLIST: "DOLLY_RACK", HUB_SPOKE: "ORBIT_ARC",
    MATRIX_2X2: "PARALLAX_PASS", RANK_BARS: "PARALLAX_PASS", KPI_CARDS: "DOLLY_RACK", ASSIGN_CARDS: "PARALLAX_PASS",
    WAIT_CLOCK: "CRANE_DIVE", RADAR_SCAN: "ORBIT_ARC", RACE_LANES: "PARALLAX_PASS", TABLE_AUDIT: "DOLLY_RACK",
    ALERT_STACK: "CRANE_DIVE", PYRAMID_LEVELS: "CRANE_DIVE", VERSUS_LIST: "ORBIT_ARC", DOC_SEARCH: "DOLLY_RACK"
  };
  var MOVES = {
    DOLLY_ORBIT: { x: -.006, y: .002, push: 12, yaw: 3, yaw2: 1.2, pitch: .8, pitch2: -.4, trackX: .006, trackY: .004, zoom: 0, zoom2: 0, settleZ: 3 },
    TRACK_RACK: { x: -.01, y: 0, push: 8, yaw: -2, yaw2: 2, pitch: .3, pitch2: .2, trackX: .016, trackY: .003, zoom: 0, zoom2: 0, settleZ: 2 },
    CRANE_PUSH: { x: 0, y: .008, push: 14, yaw: 0, yaw2: .7, pitch: -2, pitch2: -.8, trackX: .004, trackY: .014, zoom: 0, zoom2: 0, settleZ: 3 },
    ARC_REVEAL: { x: .01, y: -.002, push: 8, yaw: -3, yaw2: 3, pitch: .5, pitch2: -.5, trackX: .014, trackY: .003, zoom: 0, zoom2: 0, settleZ: -3 },
    STATIC: { x: 0, y: 0, push: 0, yaw: 0, yaw2: 0, pitch: 0, pitch2: 0, trackX: 0, trackY: 0, zoom: 0, zoom2: 0, settleZ: 0 }
  };
  var frame = function (x, y, z, pitch, yaw, roll, scale, perspective, back, front, blur) {
    var focus = typeof blur === "number" ? { back: blur, middle: Math.min(1.5, blur * .375) } : (blur || {});
    return { x: x, y: y, z: z, pitch: pitch, yaw: yaw, roll: roll, scale: scale, perspective: perspective,
      planes: { back: { z: back, blur_px: focus.back || 0 }, middle: { z: 0, blur_px: focus.middle || 0 }, front: { z: front, blur_px: focus.front || 0 } } };
  };
  var PROFILES = {
    ORBIT_ARC: [frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0), frame(-18, 8, 22, 0, 0, 0, 1.01, 1900, -60, 25), frame(-48, 20, 100, 0, 0, 0, 1.04, 1600, -240, 130), frame(24, 0, 20, 0, 0, 0, 1.01, 1900, -35, 15)],
    CRANE_DIVE: [frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0), frame(0, -55, 28, -2, 0, 0, 1.01, 2000, -55, 30), frame(8, 92, 150, 7, 2, -.4, 1.06, 1400, -230, 150), frame(0, 12, 24, 0, 0, 0, 1.01, 1900, -40, 18)],
    PARALLAX_PASS: [frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0), frame(-64, 0, 48, 0, 0, 0, 1.02, 2000, -110, 60), frame(76, 6, 120, 0, 0, 0, 1.04, 1500, -300, 160), frame(10, 0, 28, 0, 0, 0, 1.01, 1850, -45, 22)],
    WHIP_PAN_SETTLE: [frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0), frame(-16, 0, 18, 0, -2, -.2, 1.01, 1900, -25, 12), frame(94, 4, 72, 1, 8, 1.6, 1.04, 1600, -140, 85, 4), frame(-8, 0, 16, 0, 0, 0, 1.01, 1900, -20, 10)],
    DOLLY_RACK: [
      frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0, { back: 1.4, middle: .7 }),
      frame(0, 4, 55, 0, 0, 0, 1.02, 2000, -80, 45, { back: 2.6, middle: 1.2 }),
      frame(-26, 8, 150, 1, -2, .2, 1.06, 1400, -220, 145, { back: 1.2, front: 2.2 }),
      frame(8, 0, 24, 0, 0, 0, 1.01, 1900, -35, 18, { back: .6, front: 1.2 })
    ],
    DOLLY_ZOOM: [
      frame(0, 0, 0, 0, 0, 0, 1, 1800, 0, 0),
      frame(-4, 2, -42, 0, -1, 0, 1.02, 2100, -55, 28),
      frame(8, 0, -90, 0, 0, 0, 1.062, 1450, -240, 145),
      frame(0, 0, -30, 0, 0, 0, 1.016, 2000, -40, 18)
    ]
  };
  var clamp = function (n, lo, hi) { return Math.max(lo, Math.min(hi, n)); };
  var ease = function (n) { n = clamp(n, 0, 1); return n * n * (3 - 2 * n); };
  function focusAt(focus, t, duration, x, y, width, height) {
    var points = focus && Array.isArray(focus.points) ? focus.points : [];
    if (!points.length) return { x: x, y: y };
    var frames = [{ x: x, y: y, at: 0 }];
    points.filter(function (p) {
      return p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)) && Number.isFinite(Number(p.at));
    }).map(function (p) {
      return { x: clamp(Number(p.x), 0, width), y: clamp(Number(p.y), 0, height), at: clamp(Number(p.at), 0, duration) };
    }).sort(function (a, b) { return a.at - b.at; }).forEach(function (point) {
      var previous = frames[frames.length - 1];
      if (point.at <= previous.at + .001) frames[frames.length - 1] = point;
      else frames.push(point);
    });
    if (frames.length < 2) return { x: frames[0].x, y: frames[0].y };
    var last = frames.length - 1, phase = 0;
    while (phase < last - 1 && t > frames[phase + 1].at) phase++;
    var previous = frames[Math.max(0, phase - 1)], a = frames[phase], b = frames[phase + 1], next = frames[Math.min(last, phase + 2)];
    var span = Math.max(.001, b.at - a.at), u = clamp((t - a.at) / span, 0, 1);
    function component(key) {
      var m0 = phase === 0 ? 0 : (b[key] - previous[key]) * span / Math.max(.001, b.at - previous.at);
      var m1 = phase === last - 1 ? 0 : (next[key] - a[key]) * span / Math.max(.001, next.at - a.at);
      var u2 = u * u, u3 = u2 * u;
      return (2 * u3 - 3 * u2 + 1) * a[key] + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * b[key] + (u3 - u2) * m1;
    }
    return { x: clamp(component("x"), 0, width), y: clamp(component("y"), 0, height) };
  }
  function resolve(kind, requested) { return requested && requested !== "AUTO" ? requested : (AUTO[kind] || "DOLLY_ORBIT"); }
  function isLayered(kind, requested) { return !!PROFILES[resolve(kind, requested)]; }
  function safePlanes() {
    return { back: { z: 0, blur_px: 0 }, middle: { z: 0, blur_px: 0 }, front: { z: 0, blur_px: 0 } };
  }
  function legacyPose(kind, requested, t, d, focus, x0, y0, w, h) {
    var mode = resolve(kind, requested), p = MOVES[mode] || MOVES.DOLLY_ORBIT;
    var phase = clamp(Math.floor(t / d * 3), 0, 2);
    if (mode === "STATIC") return { origin: x0 + "px " + y0 + "px", transform: "translate3d(0px,0px,0px) rotateX(0deg) rotateY(0deg) rotateZ(0deg) scale(1)", perspective: 1900, phase_index: 0, planes: safePlanes() };
    var from = clamp(focus && Number.isFinite(Number(focus.from)) ? Number(focus.from) : d * .35, 0, d);
    var to = clamp(focus && Number.isFinite(Number(focus.to)) ? Number(focus.to) : from + .7, from, d);
    var start = Math.max(0, from - .9), pivot = Math.min(d, Math.max(start + .25, from)), finish = Math.min(d, Math.max(pivot + .25, to));
    var approach = ease((t - start) / Math.max(.25, pivot - start));
    var track = ease((t - pivot) / Math.max(.25, finish - pivot));
    var settle = ease((t - finish) / Math.max(.25, d - finish));
    var x = p.x * w * approach + (w / 2 - x0) * p.trackX * track;
    var y = p.y * h * approach + (h / 2 - y0) * p.trackY * track;
    var z = p.push * approach + p.push * .3 * track + p.settleZ * settle;
    var pitch = p.pitch * approach + p.pitch2 * track, yaw = p.yaw * approach + p.yaw2 * track;
    var scale = 1 + p.zoom * approach + p.zoom2 * track;
    return { origin: x0.toFixed(2) + "px " + y0.toFixed(2) + "px",
      transform: "translate3d(" + x.toFixed(2) + "px," + y.toFixed(2) + "px," + z.toFixed(2) + "px) rotateX(" + pitch.toFixed(2) + "deg) rotateY(" + yaw.toFixed(2) + "deg) rotateZ(0deg) scale(" + scale.toFixed(4) + ")",
      perspective: 1900, phase_index: phase, planes: safePlanes() };
  }
  function interpolate(frames, marks, phase, time) {
    var a = frames[phase], b = frames[phase + 1], previous = frames[Math.max(0, phase - 1)], next = frames[Math.min(3, phase + 2)];
    var start = marks[phase], end = marks[phase + 1], duration = end - start, u = clamp((time - start) / duration, 0, 1);
    function component(p, a, b, n) {
      var m0 = phase === 0 ? 0 : (b - p) * duration / (end - marks[phase - 1]);
      var m1 = phase === 2 ? 0 : (n - a) * duration / (marks[phase + 2] - start);
      var u2 = u * u, u3 = u2 * u;
      return (2 * u3 - 3 * u2 + 1) * a + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * b + (u3 - u2) * m1;
    }
    var out = {};
    ["x", "y", "z", "pitch", "yaw", "roll", "scale", "perspective"].forEach(function (key) {
      out[key] = component(previous[key], a[key], b[key], next[key]);
    });
    out.planes = {};
    ["back", "middle", "front"].forEach(function (key) {
      out.planes[key] = {};
      ["z", "blur_px"].forEach(function (field) {
        out.planes[key][field] = component(previous.planes[key][field], a.planes[key][field], b.planes[key][field], next.planes[key][field]);
      });
    });
    return out;
  }
  function transform(kind, requested, time, duration, focus, width, height) {
    var w = Number(width) || 1920, h = Number(height) || 1080, d = Math.max(.5, Number(duration) || 1);
    var t = clamp(Number(time) || 0, 0, d), mode = resolve(kind, requested);
    var baseX = clamp(focus && Number.isFinite(Number(focus.x)) ? Number(focus.x) : w / 2, 0, w);
    var baseY = clamp(focus && Number.isFinite(Number(focus.y)) ? Number(focus.y) : h / 2, 0, h);
    var target = focusAt(focus, t, d, baseX, baseY, w, h), x0 = target.x, y0 = target.y;
    var currentFocus = focus && typeof focus === "object" ? Object.assign({}, focus, { x: x0, y: y0 }) : { x: x0, y: y0 };
    if (!PROFILES[mode]) return legacyPose(kind, mode, t, d, currentFocus, x0, y0, w, h);
    var from = clamp(focus && Number.isFinite(Number(focus.from)) ? Number(focus.from) : d * .35, 0, d);
    var to = clamp(focus && Number.isFinite(Number(focus.to)) ? Number(focus.to) : from + .7, from, d);
    var first = clamp(from / d, .12, .32), second = clamp(to / d, first + .2, .86), marks = [0, first, second, 1];
    var phase = t <= d * marks[1] ? 0 : (t <= d * marks[2] ? 1 : 2), frames = PROFILES[mode], lo = marks[phase], hi = marks[phase + 1];
    var pose = interpolate(frames, marks, phase, t / d);
    pose.x = clamp(pose.x + (w / 2 - x0) * .02, -w * .1, w * .1);
    pose.y = clamp(pose.y + (h / 2 - y0) * .02, -h * .1, h * .1);
    pose.z = clamp(pose.z, -220, 220);
    if (mode === "PARALLAX_PASS" || kind === "VERSUS_LIST") {
      // Giữ chữ trong mặt phẳng; chiều sâu vẫn đến từ lớp parallax.
      pose.pitch = pose.yaw = pose.roll = 0;
    }
    pose.scale = clamp(pose.scale, 1, kind === "VERSUS_LIST" ? 1.015 : 1.07); pose.perspective = clamp(pose.perspective, 1200, 2200);
    if (kind === "VERSUS_LIST") {
      var minX = 60.1 - (x0 + (120 - x0) * pose.scale), maxX = 959.9 - (x0 + (960 - x0) * pose.scale);
      pose.x = clamp(pose.x, h > w ? Math.max(-20, minX) : -36, h > w ? Math.min(0, maxX) : 0);
      pose.y = clamp(pose.y, -15, 15);
      pose.z = 0;
    }
    ["back", "middle", "front"].forEach(function (key) {
      pose.planes[key].z = kind === "VERSUS_LIST" ? 0 : key === "back" ? clamp(pose.planes[key].z, -300, 0) : key === "front" ? clamp(pose.planes[key].z, 0, 160) : 0;
      pose.planes[key].blur_px = clamp(pose.planes[key].blur_px, 0, key === "middle" ? 1.5 : 4);
    });
    return { origin: x0.toFixed(2) + "px " + y0.toFixed(2) + "px",
      transform: "translate3d(" + pose.x.toFixed(2) + "px," + pose.y.toFixed(2) + "px," + pose.z.toFixed(2) + "px) rotateX(" + pose.pitch.toFixed(2) + "deg) rotateY(" + pose.yaw.toFixed(2) + "deg) rotateZ(" + pose.roll.toFixed(2) + "deg) scale(" + pose.scale.toFixed(4) + ")",
      perspective: pose.perspective, phase_index: phase, planes: pose.planes };
  }
  root.__bahaCamera = { transform: transform, isLayered: isLayered };
})(window);
