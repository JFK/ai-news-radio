[English version is here](README.md)

# AI News Radio

ニュースを自動収集し、AIでファクトチェック・クリティカル分析・台本生成・音声生成・動画化・YouTube投稿まで一気通貫で行うWebアプリケーション。

**「ニュースを読むだけじゃない。一緒に考えるラジオ。」**

ニュースを鵜呑みにせず、背景・文脈・複数の視点を届ける。専門知識がなくても「なるほど、そういうことか」と腑に落ちる解説を目指します。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6.svg)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

## 特徴

- **6ステップパイプライン** — 収集 → ファクトチェック → 分析 → 台本 → 音声 → 動画
- **承認ゲート** — 各ステップにヒューマンチェックポイント。自動で進まない安心設計
- **マルチAIプロバイダー** — Anthropic Claude / OpenAI GPT / Google Gemini を切り替え可能
- **マルチTTSプロバイダー** — VOICEVOX / OpenAI TTS / ElevenLabs / Google Cloud TTS
- **Brave Search 連携** — ニュース収集・ファクトチェック用のWeb検索
- **コスト追跡** — AIプロバイダーのトークン使用量とコストをダッシュボードで可視化
- **Google Drive エクスポート** — 分析結果を NotebookLM 用ソーステキストとしてエクスポート
- **WebUI 設定管理** — ブラウザから全設定を管理（APIキー、プロバイダー、プロンプト等）
- **MCP 連携** — Claude Code 等のAIアシスタントから全操作を実行可能
- **i18n** — 日英対応のフロントエンド

## アーキテクチャ

```
[1.収集] → ✅ → [2.ファクトチェック] → ✅ → [3.分析] → ✅ → [4.台本] → ✅ → [5.音声] → ✅ → [6.動画]
```

各 `✅` はヒューマン承認ゲート。人間が確認・承認するまで次のステップに進みません。

## 動作推奨環境

| リソース | 推奨スペック |
|---------|------------|
| OS | Ubuntu 22.04+ / WSL2 / macOS |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 80 GB SSD |
| Docker | Docker Engine 24+ / Docker Compose v2 |
| Python | 3.12+ |
| **[Claude Code](https://claude.com/claude-code)** | **セットアップ・運用に必須** |

**必要なAPIキー**（AIプロバイダーは最低1つ）:

| サービス | 用途 | 必須 |
|---------|------|------|
| [Brave Search](https://brave.com/search/api/) | ニュース収集・ファクトチェック | Yes |
| [OpenAI](https://platform.openai.com/) | AI (GPT) / TTS | いずれか1つ |
| [Anthropic](https://console.anthropic.com/) | AI (Claude) | いずれか1つ |
| [Google AI](https://aistudio.google.com/) | AI (Gemini) / TTS / Imagen | いずれか1つ |

## クイックスタート

本プロジェクトは **[Claude Code](https://claude.com/claude-code)** でセットアップ・開発・パイプライン操作を行います。

```bash
# 1. クローン
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio

# 2. Claude Code を起動して「セットアップして」と入力
claude
```

Claude Code が自動的に以下を実行します:
- 前提条件のチェック（Docker, Python, ポート）
- Python venv 作成・依存パッケージインストール
- AIプロバイダー選択・APIキー入力 → `.env` 生成
- Docker サービス起動・DBマイグレーション
- MCP サーバー設定（パイプライン操作用）

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React 19 (Vite) + TypeScript + Tailwind CSS |
| Database | PostgreSQL 16 + SQLAlchemy (async) + Alembic |
| Queue | Celery + Redis |
| AI | Anthropic Claude / OpenAI / Google Gemini |
| TTS | VOICEVOX / OpenAI / ElevenLabs / Google Cloud |
| Video | FFmpeg |
| Search | Brave Search API |
| Infra | Docker Compose |

## MCP 連携

AI News Radio は MCP (Model Context Protocol) サーバーを内蔵しており、Claude Code 等のAIアシスタントから直接操作できます。

詳しくは [docs/mcp.md](docs/mcp.md) を参照してください。

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/setup.md](docs/setup.md) | セットアップ詳細ガイド |
| [docs/architecture.md](docs/architecture.md) | アーキテクチャ解説 |
| [docs/mcp.md](docs/mcp.md) | MCP 連携ガイド |
| [CONTRIBUTING.md](CONTRIBUTING.md) | コントリビューションガイド |

## コントリビューション

コントリビューションを歓迎します！[CONTRIBUTING.md](CONTRIBUTING.md) をご確認ください。

## ライセンス

[Apache License 2.0](LICENSE)

## クレジット

- 音声合成: [VOICEVOX](https://voicevox.hiroshiba.jp/)
- ニュース検索: [Brave Search API](https://brave.com/search/api/)
