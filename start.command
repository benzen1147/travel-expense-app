#!/bin/bash
# ダブルクリックで起動する Mac 用ランチャー
# venv を自動作成し、依存パッケージをインストールして Flask を起動する

cd "$(dirname "$0")"

echo "=== 出張旅費精算書アプリ ==="
echo ""

# Python 3 確認
if ! command -v python3 &> /dev/null; then
    echo "エラー: python3 が見つかりません。Python 3.9 以上をインストールしてください。"
    read -p "Enter を押して終了..."
    exit 1
fi

# venv 作成
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
fi

# activate
source venv/bin/activate

# 依存パッケージインストール
echo "依存パッケージを確認しています..."
pip install -q -r requirements.txt

# ディレクトリ確保
mkdir -p uploads output

# ブラウザ自動起動（1秒後）
(sleep 1 && open "http://127.0.0.1:5000") &

# Flask 起動
echo ""
echo "サーバーを起動しています... http://127.0.0.1:5000"
echo "終了するにはこのウィンドウを閉じるか Ctrl+C を押してください"
echo ""
python3 app.py
