# -*- coding: utf-8 -*-
"""入力バリデーション"""

from datetime import date
import config


def validate_submission(data: dict) -> list[str]:
    """
    フォームデータのバリデーション。
    エラーメッセージのリストを返す（空ならOK）。
    """
    errors = []

    # 必須フィールド
    if not data.get("applicant_name", "").strip():
        errors.append("出張者名を入力してください。")

    if data.get("applicant_role") not in ("representative", "employee"):
        errors.append("役職を選択してください。")

    dep = data.get("departure_date")
    ret = data.get("return_date")

    if not dep:
        errors.append("出発日を入力してください。")
    if not ret:
        errors.append("帰着日を入力してください。")

    if dep and ret:
        if isinstance(dep, str):
            try:
                dep = date.fromisoformat(dep)
            except ValueError:
                errors.append("出発日の形式が不正です。")
                dep = None
        if isinstance(ret, str):
            try:
                ret = date.fromisoformat(ret)
            except ValueError:
                errors.append("帰着日の形式が不正です。")
                ret = None

        if dep and ret and ret < dep:
            errors.append("帰着日は出発日以降にしてください。")

    if not data.get("destination", "").strip():
        errors.append("目的地を入力してください。")

    if not data.get("purpose", "").strip():
        errors.append("用件を入力してください。")

    # 交通費内訳
    transport = data.get("transport_items", [])
    for i, item in enumerate(transport, 1):
        if not item.get("desc", "").strip():
            errors.append(f"交通費 {i}行目: 内容を入力してください。")
        amt = item.get("amount")
        if amt is None or (isinstance(amt, (int, float)) and amt < 0):
            errors.append(f"交通費 {i}行目: 金額が不正です。")

    # 宿泊費内訳
    accommodation = data.get("accommodation_items", [])
    has_high = False
    for i, item in enumerate(accommodation, 1):
        if not item.get("desc", "").strip():
            errors.append(f"宿泊費 {i}行目: 内容を入力してください。")
        amt = item.get("amount")
        if amt is None or (isinstance(amt, (int, float)) and amt < 0):
            errors.append(f"宿泊費 {i}行目: 金額が不正です。")
        elif isinstance(amt, (int, float)) and amt > config.HIGH_ACCOMMODATION_THRESHOLD:
            has_high = True

    # 高額宿泊理由
    if has_high and not data.get("high_accommodation_reason", "").strip():
        errors.append(
            f"1泊{config.HIGH_ACCOMMODATION_THRESHOLD:,}円を超える宿泊があるため、"
            "高額宿泊理由を入力してください。"
        )

    return errors
