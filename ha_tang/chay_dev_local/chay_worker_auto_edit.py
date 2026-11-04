"""Điều phối Auto Edit riêng; phần nặng chạy GitHub, Flow giữ khóa trình duyệt chung."""
import logging
import os
from pathlib import Path
import sys
import time
import uuid
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'), override=True)
sys.path[:0] = [str(root/'sin_content_api'), str(root)]
if os.getenv('REMOTE_COMPUTE_MODE') != 'github':
    raise SystemExit('REMOTE_COMPUTE_MODE_REQUIRED')
os.environ['CONTENT_VIDEO_WORKER_ENABLED'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

from src.database import SessionLocal
from src.modules.media_queue import worker
from src.modules.tac_vu_tu_xa.queue_scope import restrict_dev_queue

worker.AUTO_EDIT_ONLY = True
worker.LEASE_NAME = 'auto-edit-media'
logging.basicConfig(level=logging.INFO)
while True:
    try:
        with SessionLocal() as db:
            restrict_dev_queue(db)
            token = str(uuid.uuid4())
            if worker.acquire_media_lease(db, token):
                worker.process_next_media_job(db, token)
    except Exception:
        logging.exception('Điều phối Auto Edit gặp lỗi; giữ nguyên khóa chống gửi trùng')
    time.sleep(2)
