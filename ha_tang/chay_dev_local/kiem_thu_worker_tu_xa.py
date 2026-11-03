"""Kiểm thử kết nối Actions với tệp nguồn thật; không chạy model/render trên local."""
import argparse
import json
import os
from pathlib import Path
import sys
import sqlite3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'), override=True)
sys.path[:0] = [str(ROOT / 'sin_content_api'), str(ROOT)]


def main():
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--source', type=Path)
    inputs.add_argument('--diagram', action='store_true')
    args = parser.parse_args()
    from src.modules.tac_vu_tu_xa.client import scope, execute
    token = scope.set({'workspace': os.environ['SIN_WORKSPACE_ID'], 'pipeline': 'AUTO_EDIT'})
    try:
        if args.diagram:
            from src.modules.tao_video_noi_dung.planner import UiScene, PORTRAIT_DIAGRAM_LAYOUTS
            from src.modules.tao_video_noi_dung.render_engines import render_scene
            with sqlite3.connect(os.environ['DATABASE_URL'].removeprefix('sqlite:///')) as db:
                rows = db.execute("SELECT request_payload_json FROM ai_generation_jobs WHERE workspace_id=? AND state='SUCCEEDED' ORDER BY created_at DESC LIMIT 100", (os.environ['SIN_WORKSPACE_ID'],)).fetchall()
            payload = next(json.loads(row[0]) for row in rows if row[0] and json.loads(row[0]).get('operation') == 'render_auto_edit_diagram')
            params = payload['parameters']
            scene = UiScene.model_validate(params['ui_scene'])
            ratio = '9:16' if scene.layout in PORTRAIT_DIAGRAM_LAYOUTS else '16:9'
            alpha = bool(params.get('transparent_background'))
            output = Path(__file__).with_name('runtime') / ('dien_hoa_kiem_thu.mov' if alpha else 'dien_hoa_kiem_thu.mp4')
            result = render_scene(scene, {**params['style_snapshot'], 'render_engine': 'hyperframes', 'aspect_ratio': ratio},
                                  params['duration_seconds'], ratio, output,
                                  narration=params.get('narration', ''), word_times=params.get('narration_word_times'),
                                  transparent_background=alpha)
            print(json.dumps({'remote_diagram': result, 'output_bytes': output.stat().st_size}), flush=True)
        else:
            result = execute('QC', 'decode', {'path': {'remote_input': 0}}, [args.source.resolve(strict=True)])
            print(json.dumps({'remote_decode': result, 'source_bytes': args.source.stat().st_size}), flush=True)
    finally:
        scope.reset(token)


if __name__ == '__main__':
    main()
