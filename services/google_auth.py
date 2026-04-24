# -*- coding: utf-8 -*-
"""Google OAuth2 認証管理（Web Application Flow）"""
from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

import config


def _build_client_config() -> dict:
    """環境変数から OAuth クライアント設定を構築。"""
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise ValueError(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET が設定されていません。"
        )
    return {
        "web": {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"{config.APP_URL}/api/auth/callback"],
        }
    }


def get_auth_url() -> str:
    """認証URLを生成して返す。"""
    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=config.GOOGLE_SCOPES,
        redirect_uri=f"{config.APP_URL}/api/auth/callback",
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return auth_url


def exchange_code(code: str) -> Credentials:
    """認可コードをトークンに交換し、保存する。"""
    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=config.GOOGLE_SCOPES,
        redirect_uri=f"{config.APP_URL}/api/auth/callback",
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    # トークン保存
    with open(config.GOOGLE_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    return creds


def get_credentials() -> Credentials | None:
    """
    保存済みトークンからCredentialsを取得。
    期限切れなら自動リフレッシュ。無効なら None を返す。
    """
    token_path = Path(config.GOOGLE_TOKEN_FILE)
    if not token_path.exists():
        return None

    creds = Credentials.from_authorized_user_file(
        str(token_path), config.GOOGLE_SCOPES,
    )

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(config.GOOGLE_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        except Exception:
            return None

    if not creds or not creds.valid:
        return None

    return creds
