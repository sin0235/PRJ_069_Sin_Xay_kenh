"""Kiểm thử kết nối Actions với tệp nguồn thật; không chạy model/render trên local."""
import argparse
import json
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'), override=True)
sys.path[:0] = [str(ROOT / 'sin_content_api'), str(ROOT)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    from src.modules.tac_vu_tu_xa.client import scope, execute
    token = scope.set({'workspace': os.environ['SIN_WORKSPACE_ID'], 'pipeline': 'AUTO_EDIT'})
    try:
        result = execute('QC', 'decode', {'path': {'remote_input': 0}}, [args.source.resolve(strict=True)])
        print(json.dumps({'remote_decode': result, 'source_bytes': args.source.stat().st_size}), flush=True)
    finally:
        scope.reset(token)


if __name__ == '__main__':
    main()
