# 出張旅費精算書アプリ - 合同会社mofu

出張旅費精算を自動化するWebアプリ。フォーム入力＋領収書添付で、PDF生成→Google Drive保存→スプレッドシート記録まで一気通貫で処理します。

## クイックスタート（ローカル）

### Mac ワンクリック起動

`start.command` をダブルクリック。初回は仮想環境作成と依存パッケージインストールが自動実行されます。

### 手動起動

```bash
cd travel-expense-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

http://127.0.0.1:5000 を開いてください。

---

## Render へのデプロイ

### 1. GitHub リポジトリを作成

```bash
cd travel-expense-app
git init
git add .
git commit -m "Initial commit"
gh repo create travel-expense-app --public --source=. --push
```

### 2. Render でデプロイ

1. [Render Dashboard](https://dashboard.render.com/) にログイン
2. **New** → **Web Service**
3. GitHub リポジトリ `travel-expense-app` を接続
4. 設定:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. **Environment Variables** に以下を設定:

| 変数名 | 値 |
|--------|-----|
| `APP_SECRET_KEY` | ランダムな文字列（`python3 -c "import secrets; print(secrets.token_hex(32))"` で生成） |
| `APP_URL` | `https://<your-app-name>.onrender.com`（デプロイ後に確定するURL） |
| `GOOGLE_CLIENT_ID` | Google Cloud Console のクライアントID |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console のクライアントシークレット |
| `PYTHON_VERSION` | `3.11.11` |

6. **Create Web Service** をクリック

> **注意**: デプロイ直後は `APP_URL` が不明なので、Render が発行したURLを確認してから環境変数を更新し、Manual Deploy してください。

### 3. render.yaml を使う場合（Blueprint）

リポジトリに `render.yaml` が含まれているため、Render Dashboard の **Blueprints** からも設定できます。

---

## Google API 設定

Google Drive / Sheets 連携を使う場合に必要です。PDF生成のみなら不要。

### 1. Google Cloud Console でプロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成（例: `mofu-travel-expense`）

### 2. API を有効化

「APIとサービス」→「ライブラリ」で以下を有効化:
- **Google Drive API**
- **Google Sheets API**

### 3. OAuth 同意画面の設定

1. 「APIとサービス」→「OAuth 同意画面」
2. ユーザータイプ: **外部**
3. アプリ名・メールアドレスを入力
4. スコープ: `drive.file`, `spreadsheets`
5. テストユーザーに自分のGmailを追加

### 4. OAuth クライアント ID の作成

1. 「APIとサービス」→「認証情報」→「認証情報を作成」
2. **OAuth クライアント ID** を選択
3. アプリケーションの種類: **ウェブ アプリケーション**
4. **承認済みのリダイレクト URI** に以下を追加:
   - ローカル: `http://127.0.0.1:5000/api/auth/callback`
   - Render: `https://<your-app-name>.onrender.com/api/auth/callback`
5. **クライアントID** と **クライアントシークレット** をメモ

### 5. 環境変数に設定

ローカルの場合は `.env` ファイルを作成:

```bash
cp .env.example .env
# .env を編集して GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET を記入
```

Render の場合は Dashboard の Environment Variables に設定。

### 6. 認証

アプリ画面上部の「Google認証」ボタンをクリックすると Google のログイン画面にリダイレクトされます。許可すると自動的にアプリに戻ります。

---

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `APP_SECRET_KEY` | Render時 | Flask セッション用シークレットキー |
| `APP_URL` | Render時 | アプリの公開URL（OAuthリダイレクトに使用） |
| `GOOGLE_CLIENT_ID` | Google連携時 | OAuth クライアントID |
| `GOOGLE_CLIENT_SECRET` | Google連携時 | OAuth クライアントシークレット |

---

## ディレクトリ構成

```
travel-expense-app/
├── app.py                  # Flask メインアプリ
├── config.py               # 設定定数
├── requirements.txt        # Python 依存パッケージ
├── Procfile                # gunicorn 起動設定
├── render.yaml             # Render Blueprint
├── start.command           # Mac ワンクリック起動
├── services/
│   ├── pdf_generator.py    # ReportLab PDF生成
│   ├── pdf_merger.py       # PyMuPDF PDF結合
│   ├── google_auth.py      # OAuth2 認証（Web Flow）
│   ├── google_drive.py     # Drive アップロード
│   ├── google_sheets.py    # Sheets 記録
│   └── validator.py        # バリデーション
├── static/
│   ├── index.html          # フォーム画面
│   ├── style.css           # スタイル
│   └── app.js              # フロントエンド
├── uploads/                # 一時アップロード
└── output/                 # 生成PDF
```

## 日当規定

| 区分 | 国内 | 海外 |
|------|------|------|
| 代表社員 | 10,000円/日 | 15,000円/日 |
| 従業員 | 5,000円/日 | 10,000円/日 |

## 出張者マスタの編集

`config.py` の `TRAVELERS` リストを編集:

```python
TRAVELERS = [
    {"name": "梶原　明", "role": "representative"},
    {"name": "山田　太郎", "role": "employee"},
]
```
