# -*- coding: utf-8 -*-
"""Google Drive ファイル管理サービス"""
from __future__ import annotations

from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

import config


def _get_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def _find_or_create_folder(
    service, name: str, parent_id: str | None = None,
) -> str:
    """フォルダを検索し、なければ作成。フォルダIDを返す。"""
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"

    results = service.files().list(
        q=q, spaces="drive", fields="files(id)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id", supportsAllDrives=True).execute()
    return folder["id"]


def _upload_file(
    service, file_path: Path, parent_id: str, mime_type: str | None = None,
) -> str:
    """ファイルをアップロードしてファイルIDを返す。"""
    if mime_type is None:
        ext = file_path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    metadata = {
        "name": file_path.name,
        "parents": [parent_id],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
    f = service.files().create(body=metadata, media_body=media, fields="id", supportsAllDrives=True).execute()
    return f["id"]


def upload_expense_report(
    creds: Credentials,
    form_data: dict,
    report_pdf: Path,
    merged_pdf: Path | None,
    receipt_paths: list[Path],
) -> dict:
    """
    精算書関連ファイルを Google Drive にアップロード。

    指定の共有フォルダに直接PDFを保存する。
    領収書がある場合のみサブフォルダを作成。
    """
    service = _get_service(creds)

    # 指定の共有フォルダに直接アップロード
    parent_id = config.DRIVE_PARENT_FOLDER_ID

    # PDFアップロード
    _upload_file(service, report_pdf, parent_id)

    if merged_pdf and merged_pdf.exists():
        _upload_file(service, merged_pdf, parent_id)

    # 領収書（サブフォルダにまとめる）
    if receipt_paths:
        dep = form_data["departure_date"]
        dep_str = dep.strftime("%Y%m%d") if hasattr(dep, "strftime") else str(dep).replace("-", "")
        name = form_data.get("applicant_name", "").replace("　", "").replace(" ", "")
        receipt_folder_name = f"{dep_str}_{name}_領収書"
        receipt_folder_id = _find_or_create_folder(service, receipt_folder_name, parent_id)
        for rp in receipt_paths:
            if Path(rp).exists():
                _upload_file(service, Path(rp), receipt_folder_id)

    folder_url = f"https://drive.google.com/drive/folders/{parent_id}"
    return {"folderUrl": folder_url, "folderId": parent_id}
