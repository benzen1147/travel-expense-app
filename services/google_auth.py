# -*- coding: utf-8 -*-
"""Google サービスアカウント認証"""
from __future__ import annotations

import json
from pathlib import Path

from google.oauth2.service_account import Credentials

import config

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_credentials() -> Credentials | None:
    """
    サービスアカウントの Credentials を取得。
    環境変数 GOOGLE_SERVICE_ACCOUNT_JSON → ファイルパスの順でフォールバック。
    """
    # 1. 環境変数からJSON文字列を読み込み
    sa_json = config.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            return Credentials.from_service_account_info(info, scopes=_SCOPES)
        except Exception:
            return None

    # 2. ファイルパスからフォールバック
    sa_file = Path(config.GOOGLE_SERVICE_ACCOUNT_FILE)
    if sa_file.exists():
        try:
            return Credentials.from_service_account_file(str(sa_file), scopes=_SCOPES)
        except Exception:
            return None

    return None


def is_authenticated() -> bool:
    """サービスアカウントが設定されているか。"""
    if config.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        return True
    return Path(config.GOOGLE_SERVICE_ACCOUNT_FILE).exists()
