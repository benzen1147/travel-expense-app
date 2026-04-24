# -*- coding: utf-8 -*-
"""PDF結合サービス（PyMuPDF使用）

精算書PDFに領収書（画像 or PDF）を結合して1つのPDFにまとめる。
"""
from __future__ import annotations

import fitz  # PyMuPDF
from pathlib import Path


def merge_pdfs(
    report_pdf_path: str | Path,
    receipt_paths: list[str | Path],
    output_path: str | Path,
) -> Path:
    """
    精算書PDF + 領収書ファイル群 → 結合PDFを出力。

    receipt_paths の各ファイルは PDF または画像（PNG/JPG/etc）。
    画像は A4 ページに収まるようリサイズして挿入する。
    """
    output_path = Path(output_path)
    merged = fitz.open(str(report_pdf_path))

    for receipt in receipt_paths:
        receipt = Path(receipt)
        ext = receipt.suffix.lower()

        if ext == ".pdf":
            with fitz.open(str(receipt)) as src:
                merged.insert_pdf(src)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"):
            _insert_image_page(merged, receipt)
        else:
            # サポート外の形式はスキップ
            continue

    merged.save(str(output_path))
    merged.close()
    return output_path


def _insert_image_page(doc: fitz.Document, image_path: Path):
    """画像を A4 ページにフィットさせて挿入する。"""
    a4_width, a4_height = 595.28, 841.89  # A4 in points
    margin = 36  # 0.5 inch margin

    page = doc.new_page(width=a4_width, height=a4_height)
    img = fitz.open(str(image_path))
    if img.page_count == 0:
        img.close()
        return

    # 画像の元サイズ取得
    pix = fitz.Pixmap(str(image_path))
    img_w, img_h = pix.width, pix.height
    pix = None  # メモリ解放

    # マージン内に収まるようスケール
    avail_w = a4_width - 2 * margin
    avail_h = a4_height - 2 * margin
    scale = min(avail_w / img_w, avail_h / img_h, 1.0)

    new_w = img_w * scale
    new_h = img_h * scale
    x0 = margin + (avail_w - new_w) / 2
    y0 = margin + (avail_h - new_h) / 2

    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
    page.insert_image(rect, filename=str(image_path))
    img.close()
