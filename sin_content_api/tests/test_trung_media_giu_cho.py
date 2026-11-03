from types import SimpleNamespace

from src.modules.tao_video_noi_dung.runner import _has_duplicate_shot_media, _hashes_for_duplicate_check


def asset(i, sha):
    return SimpleNamespace(id=f"a{i}", sha256=sha)


def test_identical_placeholder_clips_of_hyperframes_assembly_are_not_duplicates():
    steps = [{"asset_id": "a1", "render_engine": "hyperframes_assembly"}, {"asset_id": "a2", "render_engine": "hyperframes_assembly"},
             {"asset_id": "a3"}, {"asset_id": "a4"}]
    assets = [asset(1, "same"), asset(2, "same"), asset(3, "x"), asset(4, "y")]
    assert not _has_duplicate_shot_media(_hashes_for_duplicate_check(steps, assets))


def test_two_flow_shots_with_the_same_clip_are_still_rejected():
    steps = [{"asset_id": "a1"}, {"asset_id": "a2"}, {"asset_id": "a3", "render_engine": "hyperframes_assembly"}]
    assets = [asset(1, "same"), asset(2, "same"), asset(3, "p")]
    assert _has_duplicate_shot_media(_hashes_for_duplicate_check(steps, assets))
