import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/modules/tao_video_noi_dung"


def test_versus_portrait_keeps_cards_below_tiktok_safe_top_without_decorative_drift():
    script = r'''
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const body = source.split("function sceneVersus(t, p) {")[1].split("\n}\n\n/* DOC_SEARCH:")[0];
const helpers = {
  PORTRAIT: true,
  COL: { bg: "#0B0F17", shadow: "#070A10", ink: "#F2EEE6", teal: "#0562AF", tealD: "#083D70", tealL: "#5FA8FF", navy: "#D9B26A", coral: "#ED1B24", gold: "#FABC11" },
  eo: x => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3),
  seg: (t, a, b) => Math.max(0, Math.min(1, (t - a) / Math.max(1e-6, b - a))),
  eio: x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
  fit: (_text, _width, size) => size,
  esc: text => String(text),
  paperCard: (x, y, w, h) => `<rect x="${x}" y="${y}" width="${w}" height="${h}"/>`
};
const makeScene = vm.runInNewContext(`(function sceneVersus(t, p) {${body}\n})`, helpers);
const p = { t: { left: .2, right: 2, verdict: 4 }, docs: [
  {title:"Thủ công", label:"Cách A", value:"Chậm"}, {title:"Tự động", label:"Cách B", value:"Nhanh"}
], layers:["Nhập từng mục"], values:["Giảm sai sót"], diff_label:"Tự động nhanh hơn" };
process.stdout.write(JSON.stringify([.5, .9, 1.2, 8].map(time => makeScene(time, p))));
'''
    frames = json.loads(subprocess.run(
        ["node", "-e", script, str(MODULE / "diagram_scene.html")],
        check=True,
        capture_output=True,
        text=True,
    ).stdout)
    result = frames[-1]

    assert re.search(r'<rect x="120" y="210" width="840" height="510"', result)
    assert re.search(r'<rect x="120" y="760" width="840" height="510"', result)
    assert "paperDust" not in result
    assert " rotate(" not in result
    entering = re.search(r'transform="translate\(0 ([\d.]+)\) translate\(540 465\)', frames[0])
    assert entering and float(entering.group(1)) > 0
    assert 'class="paperCheck"' in result and "stroke-dashoffset=" in result
    checks = [re.search(r'class="paperCheck"[^>]+stroke-dashoffset="([\d.]+)"', frame).group(1) for frame in frames[1:3]]
    assert float(checks[0]) > float(checks[1])


def test_shared_camera_is_seek_deterministic_with_parallax_flat_and_other_profiles_tilted():
    camera = MODULE / "dieu_khien_may_quay.js"
    script = r'''
const fs = require("fs"), vm = require("vm");
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), context);
const camera = context.window.__bahaCamera;
const out = {};
for (const [width, height] of [[1080,1920],[1920,1080]]) {
  out[width] = {};
  for (const [kind, mode] of [["CHECKLIST", "PARALLAX_PASS"], ["CHECKLIST", "CRANE_DIVE"], ["CHECKLIST", "WHIP_PAN_SETTLE"], ["VERSUS_LIST", "ORBIT_ARC"]]) {
    const sample = t => camera.transform(kind, mode, t, 8,
      {x:width/2,y:height/2,from:1,to:6,points:[]}, width, height).transform;
    out[width][mode] = { middle: sample(3), repeated: sample(5), middleAgain: sample(3) };
  }
}
process.stdout.write(JSON.stringify(out));
'''
    poses = json.loads(subprocess.run(
        ["node", "-e", script, str(camera)], check=True, capture_output=True, text=True
    ).stdout)

    for modes in poses.values():
        for pose in modes.values():
            assert pose["middle"] == pose["middleAgain"]
        parallax = modes["PARALLAX_PASS"]["middle"]
        parallax_rotation = [float(value) for value in re.findall(r"rotate[XYZ]\(([-\d.]+)deg\)", parallax)]
        parallax_scale = float(re.search(r"scale\(([-\d.]+)\)", parallax).group(1))
        assert parallax_rotation == [0, 0, 0]
        assert 1 <= parallax_scale <= 1.04
        versus_rotation = [float(value) for value in re.findall(r"rotate[XYZ]\(([-\d.]+)deg\)", modes["ORBIT_ARC"]["middle"])]
        assert versus_rotation == [0, 0, 0]
        if "ORBIT_ARC" in modes:
            assert float(re.search(r"scale\(([-\d.]+)\)", modes["ORBIT_ARC"]["middle"]).group(1)) <= 1.02
        for mode in ("CRANE_DIVE", "WHIP_PAN_SETTLE"):
            rotations = [float(value) for value in re.findall(r"rotate[XYZ]\(([-\d.]+)deg\)", modes[mode]["middle"])]
            assert any(rotations)


def test_native_checklist_keeps_event_stagger_svg_reveal_and_small_punch():
    from src.modules.tao_video_noi_dung.hf_scenes import NATIVE

    html = NATIVE["CHECKLIST"]("motion", {
        "kind": "CHECKLIST", "title": "Ba bước", "steps": ["Ghi nhận", "Đối chiếu"],
        "camera_motion": "PARALLAX_PASS",
    }, 0, 5, {"c0": .7, "c1": 2.4})

    assert 'gsap.timeline({ paused: true })' in html
    assert "stagger: .07" in html
    assert "function draw(" in html and "strokeDashoffset" in html
    assert "T('c' + i)" in html
    assert "scale: Math.min(k || 1.07, 1.04)" in html


def test_versus_portrait_key_bounds_stay_safe_across_focus_origins_and_all_frames():
    camera = MODULE / "dieu_khien_may_quay.js"
    script = r'''const fs = require("fs"), vm = require("vm");
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), context);
const camera = context.window.__bahaCamera, frames = [];
for (const y of [1380, 960]) for (let i = 0; i <= 240; i++) {
  const pose = camera.transform("VERSUS_LIST", "ORBIT_ARC", i / 30, 8,
    {x: 540, y, from: 0, to: 8, points: []}, 1080, 1920);
  frames.push({y, ...pose});
}
process.stdout.write(JSON.stringify(frames));
'''
    frames = json.loads(subprocess.run(
        ["node", "-e", script, str(camera)], check=True, capture_output=True, text=True
    ).stdout)
    assert len(frames) == 482
    for frame in frames:
        origin_x, origin_y = [float(value.removesuffix("px")) for value in frame["origin"].split()]
        x, y, z = [float(value) for value in re.search(
            r"translate3d\(([-\d.]+)px,([-\d.]+)px,([-\d.]+)px\)", frame["transform"]
        ).groups()]
        scale = float(re.search(r"scale\(([-\d.]+)\)", frame["transform"]).group(1))
        left, right = [origin_x + (edge - origin_x) * scale + x for edge in (120, 960)]
        top, bottom = [origin_y + (edge - origin_y) * scale + y for edge in (215, 1432)]
        assert 60 <= left <= right <= 960
        assert 150 <= top <= bottom <= 1600
        assert z == 0 and all(plane["z"] == 0 for plane in frame["planes"].values())
