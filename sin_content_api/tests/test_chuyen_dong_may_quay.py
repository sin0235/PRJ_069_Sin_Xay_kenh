import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from playwright.sync_api import sync_playwright

from src.modules.tao_video_noi_dung.hf_scenes import scaffold
from src.modules.tao_video_noi_dung.planner import DiagramSpec, UiScene
from src.modules.tao_video_noi_dung.ui_sim import _diagram_html, diagram_payload, hyperframes_composition_html


CAMERA_PROFILES_MOI = ("ORBIT_ARC", "CRANE_DIVE", "PARALLAX_PASS", "WHIP_PAN_SETTLE", "DOLLY_RACK", "DOLLY_ZOOM")
POSE_CU = {
    "DOLLY_ORBIT": (
        "translate3d(0.00px,0.00px,0.00px) rotateX(0.00deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-7.28px,4.02px,14.67px) rotateX(0.50deg) rotateY(3.89deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-7.56px,4.08px,18.60px) rotateX(0.40deg) rotateY(4.20deg) rotateZ(0deg) scale(1.0000)",
    ),
    "TRACK_RACK": (
        "translate3d(0.00px,0.00px,0.00px) rotateX(0.00deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-12.93px,0.13px,9.78px) rotateX(0.45deg) rotateY(-0.52deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-13.68px,0.18px,12.40px) rotateX(0.50deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
    ),
    "CRANE_PUSH": (
        "translate3d(0.00px,0.00px,0.00px) rotateX(0.00deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-0.53px,15.98px,17.11px) rotateX(-2.59deg) rotateY(0.52deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(-0.72px,16.20px,21.20px) rotateX(-2.80deg) rotateY(0.70deg) rotateZ(0deg) scale(1.0000)",
    ),
    "ARC_REVEAL": (
        "translate3d(0.00px,0.00px,0.00px) rotateX(0.00deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(8.93px,-3.71px,9.78px) rotateX(0.13deg) rotateY(-0.78deg) rotateZ(0deg) scale(1.0000)",
        "translate3d(8.28px,-3.66px,7.40px) rotateX(0.00deg) rotateY(0.00deg) rotateZ(0deg) scale(1.0000)",
    ),
    "STATIC": (
        "translate3d(0px,0px,0px) rotateX(0deg) rotateY(0deg) rotateZ(0deg) scale(1)",
        "translate3d(0px,0px,0px) rotateX(0deg) rotateY(0deg) rotateZ(0deg) scale(1)",
        "translate3d(0px,0px,0px) rotateX(0deg) rotateY(0deg) rotateZ(0deg) scale(1)",
    ),
}


def test_chuyen_dong_may_quay_co_allowlist_va_khong_doi_du_lieu_cu():
    mac_dinh = DiagramSpec(title="Bảng so sánh")
    assert "camera_motion" not in mac_dinh.model_dump()
    assert DiagramSpec(title="Bảng so sánh", camera_motion="DOLLY_ORBIT").camera_motion == "DOLLY_ORBIT"
    with pytest.raises(ValidationError):
        DiagramSpec(title="Bảng so sánh", camera_motion="ROLL_360")


def test_allowlist_may_quay_bao_gom_sau_ho_so_moi():
    for profile in CAMERA_PROFILES_MOI:
        assert DiagramSpec(title="Sơ đồ", camera_motion=profile).camera_motion == profile


def test_legacy_pose_cac_ho_so_cu_duoc_giu_nguyen_tai_dau_giua_va_cuoi():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Các bước", "steps": ["Bước một", "Bước hai", "Bước ba"],
        "on": {"c0": "Bước một", "c1": "Bước hai", "c2": "Bước ba"},
    }})
    html = _diagram_html(diagram_payload(scene, "Các bước", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        for profile, poses in POSE_CU.items():
            actual = []
            for time in (0, 2.5, 5):
                pose = page.evaluate(
                    "([mode, t]) => window.__bahaCamera.transform('CHECKLIST', mode, t, 5, {x: 720, y: 900, from: 1.5, to: 3}, 1080, 1920)",
                    [profile, time],
                )
                actual.append(pose["transform"])
                assert pose["perspective"] == 1900
                assert all(plane == {"z": 0, "blur_px": 0} for plane in pose["planes"].values())
            assert actual == list(poses), profile
        for time in (0, 2.5, 5):
            poses = page.evaluate("""(t) => {
                const focus = {x: 720, y: 900, from: 1.5, to: 3};
                return ['AUTO', 'DOLLY_RACK'].map(mode =>
                    window.__bahaCamera.transform('CHECKLIST', mode, t, 5, focus, 1080, 1920).transform);
            }""", time)
            assert poses[0] == poses[1]
        browser.close()


def test_new_camera_profiles_phase_and_clamp_have_finite_limited_poses():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Các bước", "steps": ["Bước một", "Bước hai", "Bước ba"],
        "on": {"c0": "Bước một", "c1": "Bước hai", "c2": "Bước ba"},
    }})
    html = _diagram_html(diagram_payload(scene, "Các bước", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        assert page.evaluate("window.__bahaCamera.isLayered('CHECKLIST', 'AUTO')") is True
        assert page.evaluate("window.__bahaCamera.isLayered('CHECKLIST', 'DOLLY_RACK')") is True
        assert page.evaluate("window.__bahaCamera.isLayered('CHECKLIST', 'TRACK_RACK')") is False
        for profile in CAMERA_PROFILES_MOI:
            for duration in (1, 5):
                poses = page.evaluate("""([mode, duration]) => {
                    const focus = {x: 1080, y: 0, from: .35, to: Math.min(duration, .7)};
                    return [-1, 0, .25, .5, .75, 1, 2.5, 5, 6].map(t =>
                        window.__bahaCamera.transform('CHECKLIST', mode, t, duration, focus, 1080, 1920));
                }""", [profile, duration])
                phases = set()
                transforms = set()
                axes = [[] for _ in range(6)]
                for pose in poses:
                    assert pose["perspective"] >= 1200 and pose["perspective"] <= 2200
                    assert 0 <= pose["phase_index"] <= 2
                    phases.add(pose["phase_index"])
                    transforms.add(pose["transform"])
                    match = re.fullmatch(
                        r"translate3d\(([-\d.]+)px,([-\d.]+)px,([-\d.]+)px\) "
                        r"rotateX\(([-\d.]+)deg\) rotateY\(([-\d.]+)deg\) "
                        r"rotateZ\(([-\d.]+)deg\) scale\(([-\d.]+)\)", pose["transform"])
                    assert match, pose["transform"]
                    x, y, z, pitch, yaw, roll, scale = map(float, match.groups())
                    assert abs(x) <= 108 and abs(y) <= 192
                    assert abs(z) <= 220 and abs(pitch) <= 10 and abs(yaw) <= 10 and abs(roll) <= 2
                    assert 1 <= scale <= 1.07
                    for values, value in zip(axes, (x, y, z, pitch, yaw, roll)):
                        values.append(value)
                    assert set(pose["planes"]) == {"back", "middle", "front"}
                    assert -300 <= pose["planes"]["back"]["z"] <= 0
                    assert 0 <= pose["planes"]["front"]["z"] <= 160
                    assert all(0 <= plane["blur_px"] <= 4 for plane in pose["planes"].values())
                    assert all(value == value and abs(value) != float("inf") for value in [pose["perspective"], *[v for plane in pose["planes"].values() for v in plane.values()]])
                assert len(phases) >= 2, profile
                assert len(transforms) >= 2, profile
                assert sum(len(set(values)) > 1 for values in axes) >= 2, profile
        browser.close()


def test_camera_profiles_do_not_stop_at_phase_boundaries():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Các bước", "steps": ["Bước một", "Bước hai", "Bước ba"],
        "on": {"c0": "Bước một", "c1": "Bước hai", "c2": "Bước ba"},
    }})
    html = _diagram_html(diagram_payload(scene, "Các bước", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        movement = page.evaluate("""() => {
            const duration = 5, focus = {x: 540, y: 960, from: 1.6, to: 3}, delta = .025;
            const pose = (mode, time) => {
                const value = window.__bahaCamera.transform('CHECKLIST', mode, time, duration, focus, 1080, 1920);
                return value.transform.match(/translate3d\\(([-\\d.]+)px,([-\\d.]+)px,([-\\d.]+)px\\)/).slice(1).map(Number);
            };
            const distance = (a, b) => Math.hypot(...a.map((v, i) => v - b[i]));
            return ['ORBIT_ARC', 'CRANE_DIVE', 'PARALLAX_PASS', 'WHIP_PAN_SETTLE', 'DOLLY_RACK', 'DOLLY_ZOOM'].map(mode => {
                const first = 1.6, second = 3;
                return [first, second].map(at => distance(pose(mode, at - delta), pose(mode, at + delta)));
            });
        }""")
        assert all(travel > .15 for profile in movement for travel in profile), movement
        browser.close()


def test_dolly_rack_shifts_focus_from_foreground_to_main_layer():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Các bước", "steps": ["Bước một", "Bước hai", "Bước ba"],
        "on": {"c0": "Bước một", "c1": "Bước hai", "c2": "Bước ba"},
    }})
    html = _diagram_html(diagram_payload(scene, "Các bước", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        focus = page.evaluate("""() => [0, 2.7].map(time =>
            window.__bahaCamera.transform('CHECKLIST', 'DOLLY_RACK', time, 5,
                {x: 540, y: 960, from: 1.5, to: 2.75}, 1080, 1920).planes)""")
        assert focus[0]["middle"]["blur_px"] > focus[1]["middle"]["blur_px"] + .5
        assert focus[1]["front"]["blur_px"] > focus[0]["front"]["blur_px"] + 1
        browser.close()


def test_dolly_zoom_holds_content_size_while_depth_planes_expand():
    scene = UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
        "title": "So sánh kết quả",
        "docs": [
            {"title": "Trước", "label": "Đơn", "value": "100"},
            {"title": "Sau", "label": "Đơn", "value": "60"},
        ],
        "diff_label": "Giảm 40",
        "on": {"before": "Trước", "after": "Sau", "delta": "Giảm 40"},
    }})
    html = _diagram_html(diagram_payload(scene, "Trước, sau, giảm 40.", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        factors = page.evaluate("""() => {
            const focus = {x: 540, y: 960, from: 1.5, to: 2.75};
            const pose = (mode, time) => window.__bahaCamera.transform('BEFORE_AFTER', mode, time, 5, focus, 1080, 1920);
            const frameScale = pose => Number(pose.transform.match(/scale\\(([-\\d.]+)\\)/)[1]);
            const rigZ = pose => parseFloat(pose.transform.match(/translate3d\\([^,]+,[^,]+,([^)]+)\\)/)[1]);
            const projection = (pose, plane) => frameScale(pose) * pose.perspective / (pose.perspective - rigZ(pose) - pose.planes[plane].z);
            const start = pose('DOLLY_ZOOM', 0), reveal = pose('DOLLY_ZOOM', 2.75);
            return {
                centerStart: projection(start, 'middle'), centerReveal: projection(reveal, 'middle'),
                backStart: projection(start, 'back'), backReveal: projection(reveal, 'back'),
                frontStart: projection(start, 'front'), frontReveal: projection(reveal, 'front'),
                auto: pose('AUTO', 2.75).transform, explicit: reveal.transform,
            };
        }""")
        assert factors["centerReveal"] == pytest.approx(factors["centerStart"], abs=.01)
        assert factors["backReveal"] < factors["backStart"] * .92
        assert factors["frontReveal"] > factors["frontStart"] * 1.05
        assert factors["auto"] == factors["explicit"]
        browser.close()


def test_camera_rig_cua_canh_chung_tua_xac_dinh_theo_thoi_gian():
    scene = UiScene.model_validate({
        "layout": "BEFORE_AFTER",
        "diagram": {
            "title": "Hiệu quả xử lý",
            "docs": [
                {"title": "Trước", "label": "Thời gian", "value": "100"},
                {"title": "Sau", "label": "Thời gian", "value": "60"},
            ],
            "diff_label": "Giảm 40%",
            "camera_motion": "DOLLY_ORBIT",
            "on": {"before": "Trước 100", "after": "sau 60", "delta": "giảm 40"},
        },
    })
    html = _diagram_html(diagram_payload(scene, "Trước 100, sau 60, giảm 40 phần trăm", 5), "9:16")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        page.evaluate("window.setT(0)")
        dau = page.locator("#rig").evaluate("e => e.style.transform")
        origin_start = page.locator("#rig").evaluate("e => e.style.transformOrigin")
        page.evaluate("window.setT(P.focus.from)")
        focus = page.locator("#rig").evaluate("e => e.style.transformOrigin")
        page.evaluate("window.setT(P.focus.to)")
        settle = page.locator("#rig").evaluate("e => e.style.transformOrigin")
        page.evaluate("window.setT(2)")
        giua = page.locator("#rig").evaluate("e => e.style.transform")
        page.evaluate("window.setT(2)")
        lap_lai = page.locator("#rig").evaluate("e => e.style.transform")
        assert dau != giua
        assert origin_start == "540px 960px"
        assert focus == "530px 570px"
        assert settle == "530px 1224px"
        assert giua == lap_lai
        goc = page.evaluate("window.__bahaCamera.transform('BEFORE_AFTER', 'AUTO', 0, 5, {x: 0, y: 0, from: 0, to: 0}, 1080, 1920)")
        assert goc["origin"] == "0.00px 0.00px"
        page.evaluate("window.setT(4)")
        khung = page.locator("#back rect").nth(1).evaluate("e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; }")
        assert khung[0] >= 0 and khung[1] <= 1080
        browser.close()

    composition = hyperframes_composition_html(scene, "Trước 100, sau 60, giảm 40 phần trăm", 5)
    assert '<div id="rig" data-layout-allow-overflow>' in composition
    assert "__bahaCamera" in composition


def test_three_planes_and_screen_caption_stay_outside_camera_rig():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Các bước", "steps": ["Bước một", "Bước hai", "Bước ba"],
        "stamp": "SẴN SÀNG",
        "camera_motion": "PARALLAX_PASS",
        "on": {"c0": "Bước một", "c1": "Bước hai", "c2": "Bước ba", "stamp": "SẴN SÀNG"},
    }})
    for aspect, width, height in (("16:9", 1920, 1080), ("9:16", 1080, 1920)):
        html = _diagram_html(diagram_payload(scene, "Bước một, bước hai, bước ba. Sẵn sàng.", 5), aspect)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            page.evaluate("document.fonts.ready")
            page.evaluate("window.P.words = [['Bước', 0, 2]]; window.setT(2.5)")
            layers = page.locator("#rig > svg").evaluate_all("els => els.map(e => e.id)")
            assert layers == ["back", "sv", "front"]
            assert page.locator("#cap").evaluate("e => !e.closest('#rig')")
            assert page.locator("#rig").evaluate("e => e.parentElement.id === 'stage'")
            bounds = page.locator("#cap text").evaluate("e => { const b=e.getBBox(); return [b.x,b.y,b.width,b.height]; }")
            assert bounds[0] >= (120 if aspect == "9:16" else 0)
            assert bounds[0] + bounds[2] <= width - (120 if aspect == "9:16" else 0)
            if aspect == "9:16":
                assert bounds[1] >= 150 and bounds[1] + bounds[3] <= height - 320
            focus = page.evaluate("P.focus")
            first = max(.12, min(.32, focus["from"] / 5))
            second = max(first + .2, min(.86, focus["to"] / 5))
            for profile in CAMERA_PROFILES_MOI:
                page.evaluate("mode => { P.camera_motion = mode; }", profile)
                phases = set()
                for time in (0, first * 5, first * 5 + .01, second * 5, second * 5 + .01, 5):
                    page.evaluate("t => window.setT(t)", time)
                    layers = page.evaluate("""t => {
                        const pose = window.__bahaCamera.transform(P.kind, P.camera_motion, t, 5, P.focus, W, H);
                        return ['back', 'middle', 'front'].map(key => {
                            const id = key === 'middle' ? 'sv' : key;
                            const style = getComputedStyle(document.getElementById(id));
                            const blur = style.filter.match(/blur\\(([\\d.]+)px\\)/);
                            return {z: new DOMMatrix(style.transform).m43, blur: blur ? Number(blur[1]) : 0, expected: pose.planes[key]};
                        });
                    }""", time)
                    for layer in layers:
                        assert layer["z"] == pytest.approx(layer["expected"]["z"], abs=.01)
                        assert layer["blur"] == pytest.approx(layer["expected"]["blur_px"], abs=.01)
                    phase, box = page.evaluate("""t => [window.__bahaCamera.transform(
                        P.kind, P.camera_motion, t, 5, P.focus, W, H).phase_index,
                        (() => { const r=document.querySelector('#content > text').getBoundingClientRect(); return [r.left,r.top,r.right,r.bottom]; })()]""", time)
                    phases.add(phase)
                    assert box[0] >= 0 and box[1] >= 0 and box[2] <= width and box[3] <= height, (aspect, profile, time, box)
                assert phases == {0, 1, 2}, (aspect, profile, phases)
                caption = page.locator("#cap text").evaluate("e => { const b=e.getBBox(); return [b.x,b.y,b.width,b.height]; }")
                assert caption[0] >= (120 if aspect == "9:16" else 0)
                assert caption[0] + caption[2] <= width - (120 if aspect == "9:16" else 0)
                if aspect == "9:16":
                    assert caption[1] >= 150 and caption[1] + caption[3] <= height - 320
                page.evaluate("window.setT(7)")
                for label in ("DANH SÁCH", "SẴN SÀNG"):
                    assert page.locator("#sv text").filter(has_text=label).get_attribute("fill") == "#0B0F17"
            browser.close()

        composition = hyperframes_composition_html(scene, "Bước một, bước hai, bước ba. Sẵn sàng.", 5, aspect_ratio=aspect)
        assert '<svg id="back"' in composition and '<svg id="sv"' in composition and '<svg id="front"' in composition
        assert '<svg id="caption"' in composition
        caption_start = composition.index('<svg id="caption"')
        assert composition[caption_start - 6:caption_start] == '</div>'


def test_native_hyperframes_layers_share_camera_pose_at_gsap_seek_time():
    gsap = (Path(__file__).resolve().parents[1] / "engines/vendor/gsap.min.js").read_text(encoding="utf-8")
    samples = (
        ("s01", {"kind": "CHECKLIST", "title": "Ba bước", "camera_motion": "ORBIT_ARC"}),
        ("s02", {"kind": "FUNNEL", "title": "Tỷ lệ chuyển đổi", "camera_motion": "DOLLY_ZOOM"}),
        ("s03", {"kind": "BEFORE_AFTER", "title": "Trước và sau", "camera_motion": "AUTO"}),
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for cid, scene in samples:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            fragment = scaffold(cid, scene, "", "", "", 0, 5, {}).replace("<template>\n", "", 1).rsplit("\n</template>", 1)[0]
            page.set_content(f"<!doctype html><html><head><script>{gsap}</script><script>window.__timelines={{}}</script></head><body>{fragment}</body></html>")
            layers = page.locator(f"#{cid}-rig > .cameraPlane").evaluate_all("els => els.map(e => e.id)")
            assert layers == [f"{cid}-back", f"{cid}-middle", f"{cid}-front"]
            assert page.locator(f"#{cid}-rig").evaluate("e => getComputedStyle(e).transformStyle === 'preserve-3d'")
            for time in (2.5, 2.5, 4.8):
                page.evaluate("([id, t]) => { window.__timelines[id].seek(t, false); }", [cid, time])
                actual, expected, camera_layers = page.evaluate("""([id, t]) => {
                    const rig = document.getElementById(id + '-rig');
                    const expected = window.__bahaCamera.transform(CAMERA_CONFIG.kind, CAMERA_CONFIG.motion, t, D, cameraFocus, 1920, 1080);
                    return [
                        Array.from(new DOMMatrix(rig.style.transform).toFloat64Array()),
                        Array.from(new DOMMatrix(expected.transform).toFloat64Array()),
                        ['back', 'middle', 'front'].map(key => {
                            const element = document.getElementById(id + '-' + key), style = getComputedStyle(element);
                            const blur = style.filter.match(/blur\\(([\\d.]+)px\\)/);
                            return {z: new DOMMatrix(style.transform).m43, blur: blur ? Number(blur[1]) : 0, expected: expected.planes[key]};
                        })
                    ];
                }""", [cid, time])
                assert all(a == pytest.approx(b, abs=1e-9) for a, b in zip(actual, expected))
                for layer in camera_layers:
                    assert layer["z"] == pytest.approx(layer["expected"]["z"], abs=.01)
                    assert layer["blur"] == pytest.approx(layer["expected"]["blur_px"], abs=.01)
            page.close()
        browser.close()


def test_hyperframes_camera_tracks_action_beats_across_layered_scene():
    from src.modules.tao_video_noi_dung.hf_scenes import NATIVE

    scene = {"kind": "CHECKLIST", "camera_motion": "DOLLY_RACK", "steps": ["Bước một", "Bước hai", "Bước ba"]}
    fragment = NATIVE["CHECKLIST"]("follow", scene, 0, 5, {"c0": .5, "c1": 2.2, "c2": 4.0})
    fragment = fragment.replace("<template>\n", "", 1).rsplit("\n</template>", 1)[0]
    gsap = (Path(__file__).resolve().parents[1] / "engines/vendor/gsap.min.js").read_text(encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_content(f"<!doctype html><script>{gsap}</script><script>window.__timelines={{}}</script>{fragment}")

        def focus_at(time):
            return page.evaluate("([time]) => { window.__timelines.follow.seek(time, false); return document.querySelector('#follow-rig').style.transformOrigin; }", [time])

        first, second, last = (focus_at(time) for time in (1.2, 3.0, 4.5))
        assert len({first, second, last}) == 3
        assert focus_at(3.0) == second
        browser.close()


def test_shared_diagram_camera_travels_to_semantic_focus_in_both_aspects():
    scene = UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
        "title": "Kết quả xử lý", "camera_motion": "DOLLY_ZOOM",
        "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                 {"title": "Sau", "label": "Đơn", "value": "60"}],
        "diff_label": "Giảm 40", "on": {"before": "Trước", "after": "Sau", "delta": "Giảm 40"},
    }})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for aspect, width, height in (("9:16", 1080, 1920), ("16:9", 1920, 1080)):
            html = _diagram_html(diagram_payload(scene, "Trước 100, sau 60, giảm 40.", 5), aspect)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            page.evaluate("window.setT(0)")
            start = page.locator("#rig").evaluate("e => e.style.transformOrigin")
            beats = page.evaluate("""() => {
                const times = ['before', 'after', 'delta'].map(key => P.t[key] + .25);
                return times.map(time => {
                    window.setT(time);
                    return document.getElementById('rig').style.transformOrigin;
                });
            }""")
            page.evaluate("window.setT(P.focus.from)")
            focus = page.locator("#rig").evaluate("e => e.style.transformOrigin")
            page.evaluate("window.setT(P.focus.to)")
            settle = page.locator("#rig").evaluate("e => e.style.transformOrigin")
            assert start != focus
            assert focus == beats[0]
            assert settle == beats[-1]
            assert len(set(beats)) == 3
            assert beats == (["530px 570px", "530px 960px", "530px 1224px"]
                             if aspect == "9:16" else ["570px 510px", "1350px 510px", "960px 850px"])
            page.close()
        browser.close()


def test_canh_hyperframes_dung_rig_may_quay_chung():
    html = scaffold(
        "s01",
        {"kind": "CHECKLIST", "title": "Các bước", "camera_motion": "CRANE_PUSH"},
        "",
        "",
        "",
        0,
        5,
        {},
    )
    assert 'id="s01-rig"' in html
    assert "__bahaCamera" in html


def test_shared_diagram_camera_tracks_checklist_beats_in_both_aspects():
    scene = UiScene.model_validate({"layout": "CHECKLIST", "diagram": {
        "title": "Ba bước", "camera_motion": "DOLLY_RACK",
        "steps": ["Liệt kê công đoạn", "Đo thời gian", "Chọn điểm nghẽn"],
        "stamp": "SẴN SÀNG",
        "on": {"c0": "Liệt kê", "c1": "Đo thời gian", "c2": "điểm nghẽn", "stamp": "SẴN SÀNG"},
    }})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for aspect, width, height in (("9:16", 1080, 1920), ("16:9", 1920, 1080)):
            html = _diagram_html(diagram_payload(scene, "Liệt kê công đoạn, đo thời gian, chọn điểm nghẽn, sẵn sàng.", 5), aspect)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            result = page.evaluate("""() => {
                const beats = ['c0', 'c1', 'c2'].map(key => P.t[key] + .2);
                const origins = beats.map(time => {
                    window.setT(time);
                    return document.getElementById('rig').style.transformOrigin;
                });
                return {kind: P.kind, times: P.t, focus: P.focus, points: P.focus.points.length, origins};
            }""")
            assert result["points"] >= 6, result
            assert len(set(result["origins"])) == 3
            page.close()
        browser.close()


def test_shared_diagram_camera_tracks_kpi_cards_in_both_aspects():
    scene = UiScene.model_validate({"layout": "KPI_CARDS", "diagram": {
        "title": "Ba chỉ số", "camera_motion": "DOLLY_RACK",
        "cards": [
            {"title": "Doanh thu", "label": "Tăng 18%", "value": "1,2 tỷ"},
            {"title": "Phản hồi", "label": "Còn 5 phút", "value": "5 phút"},
            {"title": "Khách chốt", "label": "Tăng 34%", "value": "241"},
        ],
        "on": {"k0": "Doanh thu", "k1": "Phản hồi", "k2": "Khách chốt"},
    }})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for aspect, width, height in (("9:16", 1080, 1920), ("16:9", 1920, 1080)):
            html = _diagram_html(diagram_payload(scene, "Doanh thu tăng, phản hồi còn năm phút, khách chốt đơn tăng.", 8), aspect)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            result = page.evaluate("""() => {
                const times = ['k0', 'k1', 'k2'].map(key => P.t[key] + .25);
                const origins = times.map(time => {
                    window.setT(time);
                    return document.getElementById('rig').style.transformOrigin;
                });
                return {kind: P.kind, times: P.t, focus: P.focus, points: P.focus.points.length, origins};
            }""")
            assert result["points"] >= 6, result
            assert len(set(result["origins"])) == 3
            page.close()
        browser.close()


def test_shared_diagram_camera_tracks_versus_beats_in_both_aspects():
    scene = UiScene.model_validate({"layout": "VERSUS_LIST", "diagram": {
        "title": "So sánh hai cách", "camera_motion": "PARALLAX_PASS",
        "docs": [{"title": "Thủ công", "label": "Cách A", "value": "Chậm"},
                 {"title": "Tự động", "label": "Cách B", "value": "Nhanh"}],
        "layers": ["Nhập từng mục", "Kiểm tra thủ công"],
        "values": ["Đồng bộ dữ liệu", "Giảm sai sót"],
        "diff_label": "Tự động nhanh hơn",
        "on": {"left": "Thủ công", "right": "Tự động", "verdict": "nhanh hơn"},
    }})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for aspect, width, height in (("9:16", 1080, 1920), ("16:9", 1920, 1080)):
            html = _diagram_html(diagram_payload(scene, "Thủ công tốn thời gian, tự động giảm sai sót và nhanh hơn.", 8), aspect)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            result = page.evaluate("""() => {
                const times = ['left', 'right', 'verdict'].map(key => P.t[key] + .25);
                const origins = times.map(time => {
                    window.setT(time);
                    return document.getElementById('rig').style.transformOrigin;
                });
                return {kind: P.kind, times: P.t, focus: P.focus, points: P.focus.points.length, origins};
            }""")
            assert result["points"] >= 6, result
            assert len(set(result["origins"])) == 3
            page.close()
        browser.close()
