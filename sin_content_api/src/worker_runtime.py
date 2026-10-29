"""Worker production: tách model/browser/render khỏi tiến trình API."""
import argparse
import os
import threading

from src.runtime_status import heartbeat_path, validate_production_runtime, worker_status, write_worker_heartbeat


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        raise SystemExit(0 if worker_status()["state"] == "READY" else 1)
    validate_production_runtime()
    from src.migrations.runner import migration_up
    from src.modules.tao_video_noi_dung.runner import content_video_worker
    import uvicorn
    migration_up()
    stopped = threading.Event()
    content_video_worker.start()

    def heartbeat():
        while not stopped.is_set():
            if not content_video_worker._thread or not content_video_worker._thread.is_alive():
                return
            write_worker_heartbeat()
            stopped.wait(5)

    thread = threading.Thread(target=heartbeat, name="worker-liveness", daemon=True)
    thread.start()
    try:
        uvicorn.run("src.modules.flow_sessions.worker:app", host="0.0.0.0", port=8090, workers=1)
    finally:
        stopped.set()
        content_video_worker.stop()
        thread.join(timeout=6)
        heartbeat_path().unlink(missing_ok=True)


if __name__ == "__main__":
    main()
