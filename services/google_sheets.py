# -*- coding: utf-8 -*-
"""Google Sheets 記録サービス"""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import config


def _get_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds)


def _get_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def _find_or_create_spreadsheet(creds: Credentials) -> str:
    """
    「出張旅費一覧」スプレッドシートを検索し、なければ作成。
    スプレッドシートIDを返す。
    """
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

    # ヘッダー行を設定
    sheets.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range="一覧!A1",
        valueInputOption="RAW",
        body={"values": [config.SHEETS_HEADERS]},
    ).execute()

    # ヘッダー行を太字にする
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={"requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": 0,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {
                            "red": 0.85, "green": 0.92, "blue": 1.0,
                        },
                    },
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            },
        }]},
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
    ss_id = _find_or_create_spreadsheet(creds)
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

    row = [
        str(submission),
        form_data.get("applicant_name", ""),
        role_label,
        dep_str,
        ret_str,
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

    sheets.spreadsheets().values().append(
        spreadsheetId=ss_id,
        range="一覧!A:O",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{ss_id}"
    return {"sheetUrl": sheet_url, "spreadsheetId": ss_id}
