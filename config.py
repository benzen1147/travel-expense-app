# -*- coding: utf-8 -*-
"""設定定数"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Render等の本番環境では /tmp を使う（エフェメラルだが書き込み可能）
_on_render = bool(os.environ.get("RENDER"))
_storage_base = Path("/tmp") if _on_render else BASE_DIR
UPLOAD_DIR = _storage_base / "uploads"
OUTPUT_DIR = _storage_base / "output"

# アップロード設定
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}

# 会社情報
COMPANY_NAME = "合同会社mofu"

# 出張者マスタ
TRAVELERS = [
    {"name": "梶原紹良", "role": "employee", "default": True},
    {"name": "梶原萌花", "role": "representative"},
    {"name": "梶原章可", "role": "employee"},
]

# 日当単価
DAILY_RATES = {
    "domestic": {
        "representative": 10000,
        "employee": 5000,
    },
    "overseas": {
        "representative": 15000,
        "employee": 10000,
    },
}

# 高額宿泊の閾値（1泊あたり）
HIGH_ACCOMMODATION_THRESHOLD = 30000

# Flask
SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-change-me")

# アプリURL（OAuthリダイレクト用）
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:5000")

# Google API設定（Web Application Flow）
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_TOKEN_FILE = str(BASE_DIR / "token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Google Drive設定
DRIVE_PARENT_FOLDER_ID = os.environ.get(
    "GOOGLE_DRIVE_FOLDER_ID", "1Xq7H_jCqEdIBQNVEZ8jqPQIwTKYxSIdZ",
)

# Google Sheets設定
SHEETS_SPREADSHEET_ID = os.environ.get(
    "GOOGLE_SHEETS_ID", "1fBiCEcSPU0w0c7dzrhTd3UHewnwvkpGBEaNthbpXnKw",
)
SHEETS_NAME = "【mofu】出張旅費一覧"
SHEETS_HEADERS = [
    "提出日", "出張者", "役職", "出発日", "帰着日", "日数",
    "目的地", "用件", "国内/海外",
    "交通費合計", "宿泊費合計", "日当合計", "総合計",
    "DriveフォルダURL", "備考",
]
