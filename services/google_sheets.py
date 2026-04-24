# -*- coding: utf-8 -*-
"""Google Sheets 記録サービス"""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import config


def _get_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds)


def _get_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def _get_spreadsheet_id(creds: Credentials) -> str:
    """
    環境変数で指定されたスプレッドシートIDを使う。
    未設定の場合のみ名前で検索し、なければ新規作成。
    """
    # 環境変数で固定IDが指定されている場合はそれを使う
    if config.SHEETS_SPREADSHEET_ID:
        return config.SHEETS_SPREADSHEET_ID

    drive = _get_drive_service(creds)
    q = (
        f"name='{config.SHEETS_NAME}' "
        "and mimeType='application/vnd.google-apps.spreadsheet' "
        "and trashed=false"
    )
    results = drive.files().list(q=q, spaces="drive", fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # 新規作成
    sheets = _get_service(creds)
    body = {
        "properties": {"title": config.SHEETS_NAME},
        "sheets": [{
            "properties": {"title": "一覧"},
        }],
    }
    ss = sheets.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    ss_id = ss["spreadsheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range="一覧!A1",
        valueInputOption="RAW",
        body={"values": [config.SHEETS_HEADERS]},
    ).execute()

    return ss_id


def record_expense(
    creds: Credentials,
    form_data: dict,
    folder_url: str = "",
) -> dict:
    """
    スプレッドシートに精算データを1行追加。
    """
    ss_id = _get_spreadsheet_id(creds)
    sheets = _get_service(creds)

    dep = form_data["departure_date"]
    ret = form_data["return_date"]
    days = (ret - dep).days + 1 if hasattr(dep, "toordinal") else ""

    region = "overseas" if form_data.get("is_overseas") else "domestic"
    role = form_data.get("applicant_role", "")
    daily_rate = config.DAILY_RATES.get(region, {}).get(role, 0)
    allowance = days * daily_rate if isinstance(days, int) else 0

    transport_total = sum(i.get("amount", 0) for i in form_data.get("transport_items", []))
    accommodation_total = sum(i.get("amount", 0) for i in form_data.get("accommodation_items", []))
    grand_total = transport_total + accommodation_total + allowance

    submission = form_data.get("submission_date", "")
    if hasattr(submission, "strftime"):
        submission = submission.strftime("%Y/%m/%d")

    role_label = "代表社員" if role == "representative" else "従業員"
    trip_type = "海外" if form_data.get("is_overseas") else "国内"

    dep_str = dep.strftime("%Y/%m/%d") if hasattr(dep, "strftime") else str(dep)
    ret_str = ret.strftime("%Y/%m/%d") if hasattr(ret, "strftime") else str(ret)

    # 日付の先頭に ' を付けてテキスト扱いにする（シリアル値変換を防止）
    row = [
        f"'{submission}",
        form_data.get("applicant_name", ""),
        role_label,
        f"'{dep_str}",
        f"'{ret_str}",
        days,
        form_data.get("destination", ""),
        form_data.get("purpose", ""),
        trip_type,
        transport_total,
        accommodation_total,
        allowance,
        grand_total,
        folder_url,
        form_data.get("itinerary_memo", ""),
    ]

    # シート名を動的に取得（最初のシートに追記）
    ss_meta = sheets.spreadsheets().get(
        spreadsheetId=ss_id, fields="sheets.properties(sheetId,title)",
    ).execute()
    first_sheet = ss_meta["sheets"][0]["properties"]
    sheet_name = first_sheet["title"]
    sheet_gid = first_sheet["sheetId"]

    # 追記前に現在の行数を取得（追記される行番号を確定するため）
    existing = sheets.spreadsheets().values().get(
        spreadsheetId=ss_id,
        range=f"'{sheet_name}'!A:A",
    ).execute()
    next_row = len(existing.get("values", [])) + 1  # 1-indexed

    sheets.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range=f"'{sheet_name}'!A{next_row}",
        valueInputOption="USER_ENTERED",
        body={"values": [row]},
    ).execute()

    # 追加した行の書式をリセット（ヘッダー行の装飾・行高を引き���がない）
    row_idx = next_row - 1  # 0-indexed
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={"requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": False},
                            "backgroundColor": {
                                "red": 1.0, "green": 1.0, "blue": 1.0,
                            },
                        },
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                },
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_gid,
                        "dimension": "ROWS",
                        "startIndex": row_idx,
                        "endIndex": row_idx + 1,
                    },
                    "properties": {"pixelSize": 21},
                    "fields": "pixelSize",
                },
            },
        ]},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{ss_id}/edit#gid={sheet_gid}"
    return {"sheetUrl": sheet_url, "spreadsheetId": ss_id}
