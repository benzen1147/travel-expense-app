# -*- coding: utf-8 -*-
"""Flask メインアプリケーション"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory

import config
from services.pdf_generator import build_expense_report
from services.pdf_merger import merge_pdfs
from services.validator import validate_submission

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.secret_key = config.SECRET_KEY

# ディレクトリ確保
config.UPLOAD_DIR.mkdir(exist_ok=True)
config.OUTPUT_DIR.mkdir(exist_ok=True)


# ──────────────────────────────
# エラーハンドラ（HTMLではなくJSONで返す）
# ──────────────────────────────
@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "errors": ["ファイルサイズが大きすぎます（上限50MB）。"]}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "errors": [f"サーバー内部エラー: {e}"]}), 500


# ──────────────────────────────
# SPA
# ──────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ──────────────────────────────
# ヘルスチェック（PDF生成テスト）
# ──────────────────────────────
@app.route("/api/health")
def health():
    """Render上での動作確認用。"""
    import traceback
    checks = {}
    # 1. ディレクトリ
    checks["output_dir"] = str(config.OUTPUT_DIR)
    checks["output_writable"] = os.access(str(config.OUTPUT_DIR), os.W_OK)
    checks["upload_dir_exists"] = config.UPLOAD_DIR.exists()

    # 2. PDF生成テスト
    try:
        from services.pdf_generator import build_expense_report
        test_path = config.OUTPUT_DIR / "_health_test.pdf"
        build_expense_report(str(test_path), {
            "applicant_name": "テスト",
            "applicant_role": "employee",
            "departure_date": date(2026, 1, 1),
            "return_date": date(2026, 1, 2),
            "destination": "テスト",
            "purpose": "テスト",
            "transport_items": [],
            "accommodation_items": [],
            "is_overseas": False,
            "submission_date": date(2026, 1, 1),
        })
        checks["pdf_generation"] = "OK"
        if test_path.exists():
            test_path.unlink()
    except Exception as e:
        checks["pdf_generation"] = f"ERROR: {type(e).__name__}: {e}"
        checks["pdf_traceback"] = traceback.format_exc()

    # 3. Google認証状態
    from services.google_auth import is_authenticated
    checks["authenticated"] = is_authenticated()
    checks["token_file_exists"] = Path(config.GOOGLE_TOKEN_FILE).exists()
    checks["token_env_set"] = bool(os.environ.get("GOOGLE_TOKEN_JSON", "").strip())
    checks["client_id_set"] = bool(config.GOOGLE_CLIENT_ID)

    # 4. Google API テスト
    try:
        from services.google_auth import get_credentials
        creds = get_credentials()
        if creds:
            from googleapiclient.discovery import build
            # Drive
            drive = build("drive", "v3", credentials=creds)
            about = drive.about().get(fields="user(displayName,emailAddress)").execute()
            checks["drive_api"] = f"OK: {about['user']}"
            # Sheets
            sheets = build("sheets", "v4", credentials=creds)
            sheets.spreadsheets().create(
                body={"properties": {"title": "__health_test__"}},
                fields="spreadsheetId",
            ).execute()
            checks["sheets_api"] = "OK"
        else:
            checks["drive_api"] = "SKIP"
            checks["sheets_api"] = "SKIP"
    except Exception as e:
        import traceback
        checks[f"{type(e).__name__}"] = f"{e}"
        checks["api_traceback"] = traceback.format_exc()[-500:]

    return jsonify(checks)


# ──────────────────────────────
# 設定取得
# ──────────────────────────────
@app.route("/api/config")
def get_config():
    return jsonify({
        "travelers": config.TRAVELERS,
        "dailyRates": config.DAILY_RATES,
        "highAccommodationThreshold": config.HIGH_ACCOMMODATION_THRESHOLD,
    })


# ──────────────────────────────
# Google認証（Web Application Flow）
# ──────────────────────────────
@app.route("/api/auth/status")
def auth_status():
    from services.google_auth import get_credentials, is_authenticated
    creds_configured = bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)
    # トークンが存在するだけでなく、実際に有効かチェック
    token_exists = is_authenticated()
    creds_valid = get_credentials() is not None if token_exists else False
    return jsonify({
        "authenticated": creds_valid,
        "tokenExists": token_exists,
        "credentialsConfigured": creds_configured,
    })


@app.route("/api/auth/start", methods=["POST"])
def auth_start():
    """認証URLを返す。フロントエンドがそのURLにリダイレクトする。"""
    try:
        from services.google_auth import get_auth_url
        auth_url = get_auth_url()
        return jsonify({"success": True, "authUrl": auth_url})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/callback")
def auth_callback():
    """Google OAuth コールバック。認可コードを受け取りトークンを保存。"""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return f"認証がキャンセルされました: {error}", 400

    if not code:
        return "認可コードがありません。", 400

    try:
        from services.google_auth import exchange_code
        creds, token_json = exchange_code(code)

        # Render等のエフェメラル環境向け：
        # 常にトークンJSONを表示して環境変数への設定を促す
        return (
            "<html><body style='font-family:sans-serif;max-width:700px;margin:40px auto;'>"
            "<h2>Google認証成功</h2>"
            "<p>以下のトークンJSONを Render の環境変数 <code>GOOGLE_TOKEN_JSON</code> に設定（上書き）してください。</p>"
            "<p>設定後、Manual Deploy すれば永続的に認証が維持されます。</p>"
            f"<textarea style='width:100%;height:200px;font-size:12px'>{token_json}</textarea>"
            "<br><br><a href='/'>アプリに戻る（今回のセッションは認証済み）</a>"
            "</body></html>"
        )
    except Exception as e:
        return f"認証エラー: {e}", 500


# ──────────────────────────────
# メイン処理: 精算書提出
# ──────────────────────────────
@app.route("/api/submit", methods=["POST"])
def submit():
    try:
        # フォームデータ解析
        form_json = request.form.get("data")
        if not form_json:
            return jsonify({"success": False, "errors": ["データが送信されていません。"]}), 400

        form_data = json.loads(form_json)

        # 日付文字列→date変換
        for key in ("departure_date", "return_date", "submission_date"):
            if form_data.get(key):
                form_data[key] = date.fromisoformat(form_data[key])

        # 金額・泊数を int に変換
        for items_key in ("transport_items", "accommodation_items"):
            for item in form_data.get(items_key, []):
                item["amount"] = int(item.get("amount", 0))
                if "nights" in item:
                    item["nights"] = int(item.get("nights", 1) or 1)

        # バリデーション
        errors = validate_submission(form_data)
        if errors:
            return jsonify({"success": False, "errors": errors}), 400

        # ファイル受け取り
        receipt_files = request.files.getlist("receipts")
        upload_id = uuid.uuid4().hex[:8]
        upload_dir = config.UPLOAD_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_receipts = []
        for f in receipt_files:
            if f.filename:
                ext = Path(f.filename).suffix.lower()
                if ext.lstrip(".") in config.ALLOWED_EXTENSIONS:
                    safe_name = f"{len(saved_receipts):03d}{ext}"
                    save_path = upload_dir / safe_name
                    f.save(str(save_path))
                    saved_receipts.append(save_path)

        # PDF生成
        dep = form_data["departure_date"]
        dest = form_data["destination"].replace("/", "_").replace(" ", "_")
        applicant = form_data["applicant_name"].replace("　", "").replace(" ", "")
        base_name = f"{dep.strftime('%Y%m%d')}_{applicant}_出張旅費精算書兼報告書_{dest}"
        report_pdf = config.OUTPUT_DIR / f"{base_name}.pdf"

        grand_total = build_expense_report(str(report_pdf), form_data)

        # 領収書結合PDF
        merged_pdf = None
        if saved_receipts:
            merged_pdf = config.OUTPUT_DIR / f"{base_name}_領収書付き.pdf"
            merge_pdfs(report_pdf, saved_receipts, merged_pdf)

        result = {
            "success": True,
            "grandTotal": grand_total,
            "reportPdf": report_pdf.name,
            "mergedPdf": merged_pdf.name if merged_pdf else None,
        }

        # Google Drive / Sheets 保存（認証済みの場合のみ）
        from services.google_auth import is_authenticated
        if is_authenticated():
            drive_result = _save_to_google(
                form_data, report_pdf, merged_pdf, saved_receipts,
            )
            result.update(drive_result)

        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"success": False, "errors": ["JSONの解析に失敗しました。"]}), 400
    except Exception as e:
        return jsonify({"success": False, "errors": [f"サーバーエラー: {str(e)}"]}), 500


def _save_to_google(
    form_data: dict,
    report_pdf: Path,
    merged_pdf: Path | None,
    receipt_paths: list[Path],
) -> dict:
    """Google Drive & Sheets に保存。それぞれ独立して実行。"""
    from services.google_auth import get_credentials
    from services.google_drive import upload_expense_report
    from services.google_sheets import record_expense

    creds = get_credentials()
    if not creds:
        return {}

    result = {}
    errors = []

    def _err_msg(label: str, e: Exception) -> str:
        msg = str(e).strip()
        if not msg:
            msg = type(e).__name__
        if hasattr(e, "resp") and hasattr(e, "content"):
            msg = f"{msg} (HTTP {e.resp.status})"
        return f"{label}: {msg}"

    # Drive保存
    try:
        drive_info = upload_expense_report(
            creds=creds,
            form_data=form_data,
            report_pdf=report_pdf,
            merged_pdf=merged_pdf,
            receipt_paths=receipt_paths,
        )
        result.update(drive_info)
    except Exception as e:
        errors.append(_err_msg("Drive", e))

    # Sheets記録
    try:
        sheets_info = record_expense(
            creds=creds,
            form_data=form_data,
            folder_url=result.get("folderUrl", ""),
        )
        result.update(sheets_info)
    except Exception as e:
        errors.append(_err_msg("Sheets", e))

    if errors:
        result["googleError"] = " / ".join(errors)

    return result


# ──────────────────────────────
# PDFダウンロード
# ──────────────────────────────
@app.route("/api/download/<filename>")
def download(filename):
    # ディレクトリトラバーサル防止
    safe = Path(filename).name
    file_path = config.OUTPUT_DIR / safe
    if not file_path.exists():
        return jsonify({"error": "ファイルが見つかりません。"}), 404
    return send_from_directory(
        str(config.OUTPUT_DIR), safe, as_attachment=True,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
