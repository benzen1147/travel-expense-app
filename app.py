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
    checks["token_exists"] = Path(config.GOOGLE_TOKEN_FILE).exists()
    checks["client_id_set"] = bool(config.GOOGLE_CLIENT_ID)

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
    token_exists = Path(config.GOOGLE_TOKEN_FILE).exists()
    creds_configured = bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)
    return jsonify({
        "authenticated": token_exists,
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
        exchange_code(code)
        # 認証成功後、メイン画面にリダイレクト
        return redirect("/?auth=success")
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
        base_name = f"出張旅費精算書_{dep.strftime('%Y%m%d')}_{dest}"
        report_pdf = config.OUTPUT_DIR / f"{base_name}.pdf"

        grand_total = build_expense_report(str(report_pdf), form_data)

        # 領収書結合PDF
        merged_pdf = None
        if saved_receipts:
            merged_pdf = config.OUTPUT_DIR / f"{base_name}_結合.pdf"
            merge_pdfs(report_pdf, saved_receipts, merged_pdf)

        result = {
            "success": True,
            "grandTotal": grand_total,
            "reportPdf": report_pdf.name,
            "mergedPdf": merged_pdf.name if merged_pdf else None,
        }

        # Google Drive / Sheets 保存（認証済みの場合のみ）
        if Path(config.GOOGLE_TOKEN_FILE).exists():
            try:
                drive_result = _save_to_google(
                    form_data, report_pdf, merged_pdf, saved_receipts,
                )
                result.update(drive_result)
            except Exception as e:
                msg = str(e).strip()
                if not msg:
                    msg = f"{type(e).__name__}: {repr(e)}"
                result["googleError"] = msg

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
    """Google Drive & Sheets に保存。"""
    from services.google_auth import get_credentials
    from services.google_drive import upload_expense_report
    from services.google_sheets import record_expense

    creds = get_credentials()
    if not creds:
        return {}

    # Drive保存
    drive_info = upload_expense_report(
        creds=creds,
        form_data=form_data,
        report_pdf=report_pdf,
        merged_pdf=merged_pdf,
        receipt_paths=receipt_paths,
    )

    # Sheets記録
    sheets_info = record_expense(
        creds=creds,
        form_data=form_data,
        folder_url=drive_info.get("folderUrl", ""),
    )

    return {**drive_info, **sheets_info}


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
