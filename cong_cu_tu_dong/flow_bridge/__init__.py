# -*- coding: utf-8 -*-
import sys
import pathlib

_dir = pathlib.Path(__file__).resolve().parent
if str(_dir) not in sys.path:
    sys.path.insert(0, str(_dir))

from flow_music_client import flow_music_client, FlowMusicClient
from google_flow_client import GoogleFlowClient
google_flow_client = GoogleFlowClient()
from session_manager import open_login_session, check_login_status

__all__ = [
    "flow_music_client",
    "FlowMusicClient",
    "google_flow_client",
    "GoogleFlowClient",
    "open_login_session",
    "check_login_status",
]
