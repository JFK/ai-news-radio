# AI News Radio - CLAUDE.md

## プロジェクト概要

ニュースを自動収集し、AIでファクトチェック・クリティカル分析・台本生成・音声生成・動画化まで一気通貫で行うWebアプリケーション。生成したメディアはWebUIから再生・ダウンロード可能。
初期対象は熊本のローカルニュースだが、ニュースソースを差し替えることで他地域にも展開可能な汎用設計。

各フェーズにヒューマンチェックポイント（承認ゲート）を設け、ダッシュボードから確認・承認・差し戻しを行う。

**OSS**
Apache 2.0ライセンス

**リポジトリ**
git@github.com:JFK/ai-news-radio.git

## コンテンツ方針

### コンセプト

「ニュースを読むだけじゃない。一緒に考えるラジオ。」

ニュースを鵜呑みにせず、背景・文脈・複数の視点を届ける。専門知識がなくても「なるほど、そういうことか」と腑に落ちる解説を目指す。

### クリティカルシンキング

- **ソースの信頼性評価**: 情報源は誰か？一次情報か？利害関係は？
- **「なぜ今？」の問い**: このニュースが今出てきた背景、タイミングの意味
- **複数視点の提示**: 賛成・反対・中立。立場によって見え方が変わることを明示
- **データの読み方**: 数字のトリック（母数は？比較対象は？）を指摘
- **「わからない」を認める**: 不確実なことは不確実と伝える。断定しない

### わかりやすさ

- **「ひとことで言うと」から始める**: 最初の1文で要点。忙しい人でも10秒で概要がわかる
- **身近な例え・スケール比較**: 「◯◯億円」→「一人あたり◯円」など実感できる表現
- **専門用語はその場で解説**: 「GDP、つまり国の経済の大きさを示す数字ですが〜」
- **「あなたの生活への影響」**: 「この政策が通ると、皆さんの◯◯がこう変わる可能性があります」
- **ストーリーで伝える**: 「なぜこうなったか→今どうなっているか→今後どうなりそうか」

### 台本構成ルール（1ニュースあたり）

1. **導入（10秒）**: 要点を1〜2文で簡潔に。ニュースに合った自然な入り方で
2. **背景解説（30秒）**: なぜ重要か、経緯をストーリーで。専門用語はその場で言い換え
3. **クリティカル分析（30秒）**: 情報源の信頼性、異なる立場からの見方を最低2つ、数字はスケール比較
4. **生活への影響（15秒）**: 「私たちの暮らしにどう関係するか」を具体的に
5. **締め（10秒）**: リスナーへの問いかけ or 考えるヒントで終わる（断定的な結論は避ける）

### 禁止事項

- 情報源不明の断定
- 煽り・恐怖訴求
- 一方的な立場の押し付け
- 専門用語の説明なし使用

## アーキテクチャ

### パイプライン（6ステップ）

```
[1.収集] → ✅ → [2.ファクトチェック] → ✅ → [3.分析] → ✅ → [4.台本生成] → ✅ → [5.音声生成] → ✅ → [6.動画化]
```

各ステップの状態: `pending` → `running` → `needs_approval` → `approved` / `rejected` → (次ステップへ or 差し戻し)

### 各ステップの役割

| # | ステップ | AIモデル使用 | 主な処理 |
|---|---------|-------------|---------|
| 1 | 収集 (collection) | - | Brave Search API、重複排除、直近ニュース絞り込み |
| 2 | ファクトチェック (factcheck) | ✅ (+ web検索) | 事実確認、ソース信頼性スコア、裏取りURL取得 |
| 3 | 分析 (analysis) | ✅ | 背景・文脈分析、複数視点抽出、データ検証、影響評価 |
| 4 | 台本生成 (script) | ✅ | クリティカルシンキング＋わかりやすさを統合した台本 |
| 5 | 音声生成 (voice) | - | VOICEVOX で台本→音声合成 |
| 6 | 動画化 (video) | ✅ (画像生成) | Imagen 4 で背景・サムネイル生成 + FFmpeg で合成→MP4 |

### 技術スタック

- **Backend**: Python 3.12 + FastAPI
- **Frontend**: React (Vite) + TypeScript + Tailwind CSS
- **DB**: PostgreSQL 16 + SQLAlchemy (async) + Alembic
- **キュー**: Celery + Redis
- **AI**: プロバイダー抽象化（Anthropic / OpenAI / Google 対応）
  - デフォルト: Anthropic Claude (claude-sonnet-4-20250514)
  - ステップごとにモデル変更可能
- **音声**: VOICEVOX (ローカルDockerコンテナ、CPU版)
- **動画**: FFmpeg + Google Imagen 4（背景・サムネイル生成、staticフォールバック可）
- **インフラ**: Docker Compose (Ubuntu 22.04+ 推奨)

### AI プロバイダー抽象化

```python
# services/ai_provider.py
class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, model: str, **kwargs) -> AIResponse: ...
    @abstractmethod
    async def web_search(self, query: str, **kwargs) -> SearchResult: ...

# services/providers/anthropic.py
class AnthropicProvider(AIProvider): ...

# services/providers/openai.py
class OpenAIProvider(AIProvider): ...

# services/providers/google.py
class GoogleProvider(AIProvider): ...
```

ステップごとの設定（.env）:
```
PIPELINE_FACTCHECK_PROVIDER=anthropic
PIPELINE_FACTCHECK_MODEL=claude-sonnet-4-20250514
PIPELINE_ANALYSIS_PROVIDER=anthropic
PIPELINE_ANALYSIS_MODEL=claude-sonnet-4-20250514
PIPELINE_SCRIPT_PROVIDER=anthropic
PIPELINE_SCRIPT_MODEL=claude-sonnet-4-20250514
```

### コスト追跡

各APIリクエストのトークン使用量をDBに記録し、ダッシュボードで可視化する。

### ディレクトリ構成

```
ai-news-radio/
├── CLAUDE.md
├── README.md
├── LICENSE                      # MIT
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # DB session
│   │   ├── models/
│   │   │   ├── episode.py       # エピソード (1回の放送)
│   │   │   ├── news_item.py     # 個別ニュース記事
│   │   │   ├── pipeline_step.py # パイプラインステップ状態
│   │   │   └── api_usage.py     # APIコスト追跡
│   │   ├── api/
│   │   │   ├── episodes.py
│   │   │   ├── pipeline.py      # 承認/却下 API
│   │   │   ├── stats.py         # コスト統計 API
│   │   │   └── health.py
│   │   ├── pipeline/
│   │   │   ├── base.py          # BaseStep 抽象クラス
│   │   │   ├── collector.py     # Step 1: ニュース収集
│   │   │   ├── factchecker.py   # Step 2: ファクトチェック
│   │   │   ├── analyzer.py      # Step 3: クリティカル分析
│   │   │   ├── scriptwriter.py  # Step 4: 台本生成
│   │   │   ├── voice.py         # Step 5: 音声生成
│   │   │   └── video.py         # Step 6: 動画化
│   │   ├── services/
│   │   │   ├── ai_provider.py   # プロバイダー抽象基底クラス
│   │   │   ├── providers/
│   │   │   │   ├── anthropic.py # Claude API
│   │   │   │   ├── openai.py    # OpenAI API
│   │   │   │   └── google.py    # Gemini API
│   │   │   ├── voicevox.py      # VOICEVOX API wrapper
│   │   │   └── brave_search.py  # Brave Search API
│   │   └── tasks.py             # Celery tasks
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx     # メインダッシュボード
│   │   │   ├── PipelineView.tsx  # パイプライン可視化（6ステップ）
│   │   │   ├── ApprovalGate.tsx  # 承認/却下UI
│   │   │   ├── NewsItemList.tsx  # ニュース一覧
│   │   │   ├── EpisodeDetail.tsx # エピソード詳細
│   │   │   └── CostDashboard.tsx # コスト統計
│   │   ├── hooks/
│   │   ├── api/
│   │   └── types/
│   └── ...
└── docs/
    ├── setup.md
    └── architecture.md
```

## データモデル

### Episode（エピソード = 1回の放送）
- id, title, status, created_at, published_at
- has_many: NewsItem, PipelineStep

### NewsItem（個別ニュース）
- id, episode_id, title, summary, source_url, source_name
- fact_check_status, fact_check_score (1-5), fact_check_details, reference_urls[]
- analysis_data (JSON): 背景、複数視点、データ検証結果、影響評価
- script_text (このニュースの台本部分)

### PipelineStep（パイプラインステップ）
- id, episode_id, step_name, status
- step_name の値: `collection`, `factcheck`, `analysis`, `script`, `voice`, `video`
- input_data (JSON), output_data (JSON)
- approved_at, rejected_at, rejection_reason
- created_at, started_at, completed_at

### ApiUsage（APIコスト追跡）
- id, episode_id, step_name, provider, model
- input_tokens, output_tokens, cost_usd
- created_at

## 設計原則

1. **各ステップは独立**: 1ステップだけ単体テスト・実行できること
2. **承認ゲートは必須**: どのステップも人間の承認なしに次へ進まない
3. **冪等性**: 同じステップを再実行しても安全であること
4. **ログ重視**: 各ステップのinput/outputをDBに保存し、後から確認可能
5. **設定可能**: ニュースソース、AIモデル、音声設定等は環境変数 or DB設定
6. **プロバイダー非依存**: AIプロバイダーを差し替え可能な抽象化レイヤー
7. **コンテンツ方針の遵守**: クリティカルシンキングとわかりやすさを台本に構造的に組み込む

## ニュース収集

Brave Search API を使用。検索クエリは環境変数 `COLLECTION_QUERIES` で設定可能。

## VOICEVOX 設定

- Docker image: `voicevox/voicevox_engine:cpu-latest`
- GPU版: `voicevox/voicevox_engine:nvidia-latest` (nvidia-container-toolkit必要)
- ポート: 127.0.0.1:50021
- デフォルトキャラ: ずんだもん or 四国めたん（設定可能）
- クレジット表記: 「VOICEVOX:[キャラ名]」（動画・概要欄に必須）
- CPU版パフォーマンス: 5-15秒/文（バッチ処理で実用的）

## サーバー推奨スペック

- OS: Ubuntu 22.04 LTS 以上
- CPU: 4 vCPU
- RAM: 8 GB
- Disk: 80 GB SSD
- GPU: 不要（CPU版VOICEVOX使用）

## コーディング規約

- Python: Ruff (formatter + linter), type hints必須
- TypeScript: ESLint + Prettier
- テスト: pytest (backend), Vitest (frontend)
- コミットメッセージ: Conventional Commits
- ドキュメント: docstring必須（public functions）
