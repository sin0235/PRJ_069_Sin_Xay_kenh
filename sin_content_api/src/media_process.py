"""Giới hạn thời gian các tiến trình xử lý media."""
import subprocess
from pathlib import Path


def run_media_command(*args, **kwargs):
    kwargs.setdefault("timeout", 600)
    if args and isinstance(args[0], (list, tuple)) and args[0] and Path(args[0][0]).name.lower() in {"ffmpeg", "ffmpeg.exe"}:
        command = list(args[0])
        if "-filter_threads" not in command:
            command[1:1] = ["-filter_threads", "2"]
        if "-filter_complex_threads" not in command:
            command[1:1] = ["-filter_complex_threads", "2"]
        if "-threads" not in command:
            command[-1:-1] = ["-threads", "2"]
        args = (command, *args[1:])
    return subprocess.run(*args, **kwargs)
