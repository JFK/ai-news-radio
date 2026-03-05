# AI News Radio

ニュースを自動収集し、AIでファクトチェック・クリティカル分析・台本生成・音声生成・動画化・YouTube投稿まで一気通貫で行うWebアプリケーション。

「ニュースを読むだけじゃない。一緒に考えるラジオ。」

## 特徴

- 7ステップのパイプライン（収集 → ファクトチェック → 分析 → 台本 → 音声 → 動画 → 投稿）
- 各ステップにヒューマンチェックポイント（承認ゲート）
- クリティカルシンキングを構造的に組み込んだ台本生成
- AIプロバイダー抽象化（Anthropic / OpenAI / Google 対応）
- VOICEVOX による音声合成
- ダッシュボードからの一元管理

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React (Vite) + TypeScript + Tailwind CSS |
| DB | PostgreSQL 16 + SQLAlchemy (async) + Alembic |
| キュー | Celery + Redis |
| AI | Anthropic Claude / OpenAI / Google Gemini |
| 音声 | VOICEVOX |
| 動画 | FFmpeg |
| インフラ | Docker Compose |

## セットアップ

### 前提条件

- Docker / Docker Compose
- Git

### 手順

```bash
# リポジトリをクローン
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio

# 環境変数を設定
cp .env.example .env
# .env を編集してAPIキーを設定

# 起動
docker compose up -d --build

# マイグレーション実行
docker compose exec backend alembic upgrade head
```

### 動作確認

- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000/api/health
- VOICEVOX: http://localhost:50021/docs

## 開発

```bash
# 全サービスをログ付きで起動
docker compose up

# バックエンドのみ再起動
docker compose restart backend

# テスト実行
docker compose exec backend pytest

# リセット（DBデータも削除）
docker compose down -v
docker compose up -d --build
```

## ライセンス

[Apache License 2.0](LICENSE)
