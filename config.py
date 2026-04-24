# -*- coding: utf-8 -*-
"""設定定数"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

# アップロード設定
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}

# 会社情報
COMPANY_NAME = "合同会社mofu"

# 出張者マスタ
TRAVELERS = [
    {"name": "梶原　紹良", "role": "representative", "default": True},
    {"name": "梶原　萌花", "role": "representative"},
    {"name": "梶原　章可", "role": "representative"},
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
DRIVE_PARENT_FOLDER_NAME = "合同会社mofu_出張旅費精算"

# Google Sheets設定
SHEETS_NAME = "出張旅費一覧"
SHEETS_HEADERS = [
    "提出日", "出張者", "役職", "出発日", "帰着日", "日数",
    "目的地", "用件", "国内/海外",
    "交通費合計", "宿泊費合計", "日当合計", "総合計",
    "DriveフォルダURL", "備考",
]
