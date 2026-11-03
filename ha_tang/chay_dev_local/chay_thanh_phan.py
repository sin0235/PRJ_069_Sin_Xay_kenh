"""Khởi động native từ cấu hình local; không in giá trị biến bí mật."""
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'), override=True)
sys.path[:0] = [str(ROOT / 'sin_content_api'), str(ROOT)]
os.environ['CONTENT_VIDEO_WORKER_ENABLED'] = '0'
os.environ['DEV_AUTH_BYPASS'] = '0'
os.environ['SYNTHETIC_DATA_ALLOWED'] = 'false'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'


if __name__ == '__main__':
    import uvicorn
    component = sys.argv[1]
    if component == 'api':
        uvicorn.run('src.main:app', host='127.0.0.1', port=8001, workers=1,
                    proxy_headers=True, forwarded_allow_ips='127.0.0.1')
    elif component == 'worker':
        if os.getenv('REMOTE_COMPUTE_MODE') != 'github':
            raise SystemExit('REMOTE_COMPUTE_MODE_REQUIRED')
        if not os.getenv('LOCAL_DEV_JOB_CUTOFF_UTC'):
            raise SystemExit('LOCAL_DEV_JOB_CUTOFF_REQUIRED')
        import threading
        from src.runtime_status import write_worker_heartbeat
        from src.migrations.runner import migration_up
        from src.modules.tao_video_noi_dung.runner import content_video_worker
        migration_up()
        content_video_worker.start()
        stopped = threading.Event()
        def heartbeat():
            while not stopped.is_set():
                if not content_video_worker._thread or not content_video_worker._thread.is_alive():
                    return
                write_worker_heartbeat()
                stopped.wait(5)
        threading.Thread(target=heartbeat, daemon=True).start()
        try:
            uvicorn.run('src.modules.flow_sessions.worker:app', host='127.0.0.1', port=8090, workers=1)
        finally:
            stopped.set()
            content_video_worker.stop()
    else:
        raise SystemExit('COMPONENT_INVALID')
