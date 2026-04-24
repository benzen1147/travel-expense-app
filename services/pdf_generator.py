# -*- coding: utf-8 -*-
"""出張旅費精算書 PDF生成サービス（ReportLab CIDフォント使用）"""
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from datetime import date
from pathlib import Path

import config

# CIDフォント登録
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
FONT_G = "HeiseiKakuGo-W5"
FONT_M = "HeiseiMin-W3"


def build_expense_report(output_path: str | Path, data: dict) -> int:
    """
    精算書PDFを生成して合計金額を返す。

    data keys:
        applicant_name: str
        applicant_role: str  ('representative' | 'employee')
        departure_date: date
        return_date: date
        destination: str
        purpose: str
        transport_items: list[dict]   [{'desc': str, 'amount': int}, ...]
        accommodation_items: list[dict]
        is_overseas: bool
        submission_date: date
        itinerary_memo: str (任意)
        high_accommodation_reason: str (任意)
    """
    # --- 計算 ---
    days = (data["return_date"] - data["departure_date"]).days + 1
    region = "overseas" if data.get("is_overseas", False) else "domestic"
    daily_rate = config.DAILY_RATES[region][data["applicant_role"]]
    allowance = days * daily_rate

    transport_total = sum(i["amount"] for i in data.get("transport_items", []))
    accommodation_total = sum(
        i["amount"] for i in data.get("accommodation_items", [])
    )
    grand_total = transport_total + accommodation_total + allowance
    submission_date = data.get("submission_date", date.today())

    # --- ドキュメント ---
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )
    story = []

    # スタイル
    s_title = ParagraphStyle(
        "T", fontName=FONT_G, fontSize=16, leading=24,
        alignment=TA_CENTER, spaceAfter=2 * mm,
    )
    s_sub = ParagraphStyle(
        "S", fontName=FONT_G, fontSize=9, leading=14,
        alignment=TA_CENTER, spaceAfter=1 * mm,
        textColor=colors.HexColor("#555555"),
    )
    s_section = ParagraphStyle(
        "H", fontName=FONT_G, fontSize=10, leading=16, spaceAfter=1 * mm,
    )
    s_note = ParagraphStyle(
        "N", fontName=FONT_M, fontSize=8, leading=13,
        textColor=colors.HexColor("#666666"),
    )
    s_body = ParagraphStyle(
        "B", fontName=FONT_M, fontSize=9, leading=14,
    )

    hdr_bg = colors.HexColor("#EEEEEE")
    grid_c = colors.grey
    base_ts = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_M),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, grid_c),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    # ── タイトル ──
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("出 張 旅 費 精 算 書 兼 報 告 書", s_title))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.black))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(config.COMPANY_NAME, s_sub))
    story.append(Spacer(1, 4 * mm))

    # ── 提出日・申請者 ──
    ht = Table(
        [["提出日", submission_date.strftime("%Y年%m月%d日"),
          "出張者", data["applicant_name"]]],
        colWidths=[25 * mm, 60 * mm, 25 * mm, 60 * mm],
    )
    ht.setStyle(TableStyle(base_ts + [
        ("FONTNAME", (0, 0), (-1, -1), FONT_G),
        ("BACKGROUND", (0, 0), (0, 0), hdr_bg),
        ("BACKGROUND", (2, 0), (2, 0), hdr_bg),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(ht)
    story.append(Spacer(1, 3 * mm))

    # ── 出張概要 ──
    date_str = (
        f"{data['departure_date'].strftime('%Y年%m月%d日')}〜"
        f"{data['return_date'].strftime('%Y年%m月%d日')}（{days}日間）"
    )
    role_label = "代表社員" if data["applicant_role"] == "representative" else "従業員"
    trip_type = "海外" if data.get("is_overseas") else "国内"

    summary_data = [
        ["出張期間", date_str],
        ["目  的  地", data["destination"]],
        ["用　　件", Paragraph(data["purpose"].replace("\n", "<br/>"), s_body)],
        ["役　　職", role_label],
        ["区　　分", f"{trip_type}出張"],
    ]
    st = Table(summary_data, colWidths=[30 * mm, 140 * mm])
    st.setStyle(TableStyle(base_ts + [
        ("FONTNAME", (0, 0), (0, -1), FONT_G),
        ("FONTSIZE", (0, 0), (0, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), hdr_bg),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
    ]))
    story.append(st)
    story.append(Spacer(1, 4 * mm))

    # ── 交通費内訳 ──
    story.append(Paragraph("【交通費内訳】", s_section))
    t_rows = [["No.", "内容", "金額（円）"]]
    for i, item in enumerate(data.get("transport_items", []), 1):
        t_rows.append([str(i), item["desc"], f"{item['amount']:,}"])
    t_rows.append(["", "小計", f"{transport_total:,}"])
    tt = Table(t_rows, colWidths=[12 * mm, 123 * mm, 35 * mm])
    tt.setStyle(TableStyle(base_ts + [
        ("FONTNAME", (0, 0), (-1, 0), FONT_G),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("RIGHTPADDING", (2, 0), (2, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), FONT_G),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F5F5F5")),
    ]))
    story.append(tt)
    story.append(Spacer(1, 3 * mm))

    # ── 宿泊費内訳 ──
    story.append(Paragraph("【宿泊費内訳】", s_section))
    a_rows = [["No.", "内容", "金額（円）"]]
    for i, item in enumerate(data.get("accommodation_items", []), 1):
        a_rows.append([str(i), item["desc"], f"{item['amount']:,}"])
    a_rows.append(["", "小計", f"{accommodation_total:,}"])
    at = Table(a_rows, colWidths=[12 * mm, 123 * mm, 35 * mm])
    at.setStyle(TableStyle(base_ts + [
        ("FONTNAME", (0, 0), (-1, 0), FONT_G),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("RIGHTPADDING", (2, 0), (2, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), FONT_G),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F5F5F5")),
    ]))
    story.append(at)
    story.append(Spacer(1, 3 * mm))

    # ── 日当 ──
    story.append(Paragraph("【日当】", s_section))
    d_rows = [["区分", "日数", "単価（円）", "金額（円）"]]
    d_rows.append([f"{trip_type}・{role_label}", f"{days}日", f"{daily_rate:,}", f"{allowance:,}"])
    dt = Table(d_rows, colWidths=[40 * mm, 30 * mm, 50 * mm, 50 * mm])
    dt.setStyle(TableStyle(base_ts + [
        ("FONTNAME", (0, 0), (-1, 0), FONT_G),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("RIGHTPADDING", (2, 0), (3, -1), 4),
    ]))
    story.append(dt)
    story.append(Spacer(1, 4 * mm))

    # ── 合計 ──
    total_data = [
        ["交通費", f"¥ {transport_total:,}"],
        ["宿泊費", f"¥ {accommodation_total:,}"],
        ["日当", f"¥ {allowance:,}"],
        ["合　計", f"¥ {grand_total:,}"],
    ]
    tot = Table(total_data, colWidths=[135 * mm, 35 * mm])
    tot.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_G),
        ("FONTSIZE", (0, 0), (-1, -2), 10),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, grid_c),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DDEEFF")),
        ("BOX", (0, -1), (-1, -1), 1, colors.HexColor("#336699")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (1, 0), (1, -1), 4),
    ]))
    story.append(tot)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "※ 交通費・宿泊費は実費精算（領収書添付）、日当は規定単価による定額支給",
        s_note,
    ))
    story.append(Spacer(1, 3 * mm))

    # ── 行程メモ（任意）──
    memo = data.get("itinerary_memo", "").strip()
    if memo:
        story.append(Paragraph("【行程メモ】", s_section))
        for line in memo.split("\n"):
            story.append(Paragraph(line, s_body))
        story.append(Spacer(1, 3 * mm))

    # ── 高額宿泊理由（任意）──
    reason = data.get("high_accommodation_reason", "").strip()
    if reason:
        story.append(Paragraph("【高額宿泊理由】", s_section))
        story.append(Paragraph(reason, s_body))
        story.append(Spacer(1, 3 * mm))

    # ── 押印欄 ──
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#AAAAAA"),
    ))
    story.append(Spacer(1, 2 * mm))
    seal_data = [
        ["申請者", "確認者", "承認者（代表社員）"],
        ["\n\n\n\n", "\n\n\n\n", "\n\n\n\n"],
    ]
    seal = Table(seal_data, colWidths=[56 * mm, 56 * mm, 58 * mm])
    seal.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_G),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, grid_c),
        ("TOPPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("ROWHEIGHT", (0, 1), (-1, 1), 18 * mm),
    ]))
    story.append(seal)

    doc.build(story)
    return grand_total
