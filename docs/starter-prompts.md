# Claude Code プロンプト

## 使い方

1. GitHubリポジトリ `ai-news-radio` を作成してclone
2. CLAUDE.md をリポジトリルートにコピー
3. 以下のプロンプトを Phase ごとに Claude Code に貼って実行
4. 各Phase完了後に `docker compose up -d` で動作確認してから次へ

---

## Phase 1: プロジェクト基盤

```
CLAUDE.md を読んで、プロジェクトの基盤を構築してください。

### やること

1. ディレクトリ構成をCLAUDE.mdに従って作成
2. docker-compose.yml を作成
   - backend (FastAPI, Python 3.12)
   - frontend (React + Vite + TypeScript)
   - db (PostgreSQL 16)
   - redis (Redis 7)
   - celery-worker
   - voicevox (voicevox/voicevox_engine:cpu-latest, ポート50021)
   すべてのコンテナが同一ネットワークで通信できること
3. backend/
   - pyproject.toml (fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, celery[redis], httpx, anthropic, openai, google-generativeai, pydantic-settings, ruff, pytest, pytest-asyncio)
   - Dockerfile (FFmpegもインストールすること)
   - app/config.py (pydantic-settings, .envから読み込み。AIプロバイダー設定をステップごとに持つ)
   - app/database.py (async sessionmaker)
   - app/main.py (FastAPI app, CORSミドルウェア設定)
   - app/models/ に Episode, NewsItem, PipelineStep, ApiUsage のSQLAlchemyモデル
     - PipelineStep.step_name の選択肢: collection, factcheck, analysis, script, voice, video, publish（7ステップ）
     - ApiUsage: episode_id, step_name, provider, model, input_tokens, output_tokens, cost_usd, created_at
   - Alembic初期設定 + 初期マイグレーション
   - app/api/health.py (GET /api/health)
4. frontend/
   - Vite + React + TypeScript + Tailwind CSS のセットアップ
   - Dockerfile
   - src/App.tsx にルーティング（React Router）
   - src/api/client.ts (axios instance, baseURL=/api)
   - 空のページコンポーネント: Dashboard, EpisodeDetail
5. .env.example を作成
   - DB接続情報
   - Redis URL
   - AIプロバイダー設定（ステップごと）:
     PIPELINE_FACTCHECK_PROVIDER=anthropic
     PIPELINE_FACTCHECK_MODEL=claude-sonnet-4-20250514
     PIPELINE_ANALYSIS_PROVIDER=anthropic
     PIPELINE_ANALYSIS_MODEL=claude-sonnet-4-20250514
     PIPELINE_SCRIPT_PROVIDER=anthropic
     PIPELINE_SCRIPT_MODEL=claude-sonnet-4-20250514
   - 各プロバイダーのAPIキー:
     ANTHROPIC_API_KEY=
     OPENAI_API_KEY=
     GOOGLE_API_KEY=
   - VOICEVOX設定
   - YouTube API設定
6. README.md を作成（日本語、セットアップ手順、ライセンス MIT）
7. LICENSE ファイル (MIT)

### 制約
- docker compose up -d で全サービスが起動すること
- http://localhost:3000 でフロントエンド、http://localhost:8000/api/health でバックエンドにアクセスできること
- backend は hot reload 対応 (volume mount + uvicorn --reload)
- frontend も hot reload 対応 (vite dev server)
```

---

## Phase 2: パイプラインエンジン + 承認API + AIプロバイダー抽象化

```
CLAUDE.md を読んだ上で、パイプラインエンジン、承認API、AIプロバイダー抽象化レイヤーを実装してください。

### やること

1. app/services/ai_provider.py
   - AIProvider 抽象基底クラスを定義:
     - abstract method: generate(prompt, model, system=None, **kwargs) -> AIResponse
     - abstract method: web_search(query, **kwargs) -> SearchResult
     - 共通: トークン使用量の追跡（AIResponse に input_tokens, output_tokens を含む）
   - AIResponse データクラス: content, input_tokens, output_tokens, model, provider
   - get_provider(provider_name: str) -> AIProvider ファクトリ関数

2. app/services/providers/anthropic.py
   - AnthropicProvider(AIProvider) を実装
   - Anthropic Python SDK 使用
   - web_search は Claude API の web_search tool を使用
   - リトライ、レートリミット対応

3. app/services/providers/openai.py（スタブ実装）
   - OpenAIProvider(AIProvider) を実装
   - generate は NotImplementedError を raise（Phase 2ではスタブ）
   - 将来の拡張ポイントとしてクラス構造だけ用意

4. app/services/providers/google.py（スタブ実装）
   - GoogleProvider(AIProvider) 同様にスタブ

5. app/pipeline/base.py
   - BaseStep 抽象クラス:
     - abstract method: execute(episode_id, input_data) -> output_data
     - 共通ロジック: ステップ開始/完了のDB更新、エラーハンドリング
     - AIプロバイダー取得: config からステップに対応するプロバイダーとモデルを取得
     - トークン使用量の記録: ApiUsage テーブルに保存
   - PipelineEngine クラス:
     - 7ステップを順番に実行
     - 各ステップ完了後に status を needs_approval に変更して停止
     - 承認されたら次のステップを実行

6. app/tasks.py
   - Celery task: run_pipeline_step(episode_id, step_name)
   - 承認後に次ステップを非同期実行

7. app/api/episodes.py
   - POST /api/episodes - 新規エピソード作成（パイプライン開始）
   - GET /api/episodes - エピソード一覧
   - GET /api/episodes/{id} - エピソード詳細（全ステップ状態含む）

8. app/api/pipeline.py
   - POST /api/episodes/{id}/steps/{step_name}/approve - 承認
   - POST /api/episodes/{id}/steps/{step_name}/reject - 却下（理由付き）
   - POST /api/episodes/{id}/steps/{step_name}/retry - 再実行

9. app/api/stats.py
   - GET /api/stats/cost - コスト統計（月間、エピソード別、ステップ別）

10. 各パイプラインステップの雛形（中身はモック）
    - collector.py: ダミーニュースデータを返す
    - factchecker.py: 入力をそのまま通す
    - analyzer.py: ダミー分析データを返す
    - scriptwriter.py: ダミー台本を返す
    - voice.py: pass
    - video.py: pass
    - publisher.py: pass

11. テスト
    - test_ai_provider.py: AIProvider の抽象インターフェーステスト
    - test_pipeline_engine.py: モックステップでパイプライン実行→承認→次ステップのフロー
    - test_api_episodes.py: APIエンドポイントのテスト

### 制約
- 承認なしに次ステップに進まないことを必ず保証する
- ステップの実行はすべてCeleryタスクとして非同期実行
- input_data, output_data はJSONでDBに保存
- AIプロバイダーは config.py 経由でステップごとに切り替え可能
- 全APIリクエストのトークン使用量を ApiUsage テーブルに記録
```

---

## Phase 3: ダッシュボードUI

```
CLAUDE.md を読んだ上で、フロントエンドのダッシュボードUIを実装してください。

### やること

1. Dashboard.tsx
   - エピソード一覧表示（状態バッジ付き）
   - 「新規エピソード作成」ボタン
   - 各エピソードの現在のパイプライン進捗を横棒で可視化

2. PipelineView.tsx
   - 7ステップを横並びで表示（ステッパーUI）
   - ステップ名: 収集 → チェック → 分析 → 台本 → 音声 → 動画 → 投稿
   - 各ステップの状態を色分け:
     - pending: グレー
     - running: 青（アニメーション）
     - needs_approval: オレンジ（点滅）
     - approved: 緑
     - rejected: 赤
   - 現在のステップの詳細表示

3. ApprovalGate.tsx
   - ステップの出力データをプレビュー表示
   - 「承認」「差し戻し」ボタン
   - 差し戻し時のコメント入力

4. NewsItemList.tsx
   - 収集されたニュースの一覧
   - 各ニュースのソースURL、ファクトチェック状態表示
   - ニュースの選択/除外（台本に含めるか）

5. EpisodeDetail.tsx
   - 上部: PipelineView
   - 中部: 現在のステップの詳細（ApprovalGate or 結果表示）
   - 下部: ニュース一覧

6. CostDashboard.tsx
   - 月間コスト推移グラフ
   - ステップ別・プロバイダー別のコスト内訳
   - エピソードあたりの平均コスト

7. リアルタイム更新
   - ポーリング（5秒間隔）で状態更新

### デザイン方針
- Tailwind CSS ベース、ダークモード
- モバイルでも最低限操作可能なレスポンシブ
- 日本語UI
```

---

## Phase 4: ニュース収集ステップ実装

```
CLAUDE.md を読んだ上で、ニュース収集ステップ (collector.py) を実装してください。

### やること

1. app/services/scraper.py
   - 各ニュースソースからニュースを取得
   - httpx でHTTPリクエスト
   - BeautifulSoup4 でHTML解析
   - 対応ソース:
     - 熊本日日新聞 (kumanichi.com)
     - NHK熊本 (nhk.or.jp/lnews/kumamoto/)
     - 熊本県公式サイト (pref.kumamoto.jp) のお知らせ/新着情報
   - robots.txt確認、リクエスト間隔1秒以上
   - User-Agent を適切に設定
   - 取得データ: タイトル、URL、公開日、カテゴリ（推定）、本文概要

2. app/pipeline/collector.py
   - scraper.py を使って各ソースからニュース収集
   - 重複排除（URLベース）
   - 直近24時間のニュースに絞り込み
   - 収集結果を NewsItem としてDBに保存
   - output_data として収集件数とニュースリストのサマリを返す

3. テスト
   - test_scraper.py: 各スクレイパーの単体テスト（モックHTML使用）
   - test_collector.py: コレクター全体のテスト

### 制約
- サイトの利用規約・robots.txtを尊重する実装
- スクレイピングが失敗しても他ソースの処理は継続
- 取得できなかったソースはログに記録
```

---

## Phase 5: ファクトチェック + クリティカル分析 + 台本生成

```
CLAUDE.md を読んだ上で、ファクトチェック、クリティカル分析、台本生成の3ステップを実装してください。
特に「コンテンツ方針」セクションを熟読し、クリティカルシンキングとわかりやすさを台本に構造的に組み込んでください。

### やること

1. app/pipeline/factchecker.py（Step 2）
   - 各NewsItemに対してAIプロバイダー経由でファクトチェック
   - base.py の get_provider() で設定されたプロバイダー/モデルを使用
   - プロンプト設計:
     - ニュースのタイトル・本文・ソースURLを入力
     - web検索ツール使用を指示
     - 出力（JSON構造化）:
       - source_reliability: ソース信頼性スコア (1-5)
       - fact_check_score: 事実確認スコア (1-5)
       - verified_facts: 確認できた事実のリスト
       - unverified_claims: 未確認の主張のリスト
       - reference_urls: 裏取りに使った公式ソースURL[]
       - notes: 注意事項
   - 結果を NewsItem の fact_check 関連カラムに保存
   - トークン使用量を ApiUsage に記録

2. app/pipeline/analyzer.py（Step 3）★新規ステップ
   - ファクトチェック済みニュース一覧を受け取り、各ニュースを深堀り分析
   - プロンプト設計:
     - 入力: ニュースタイトル、要約、ファクトチェック結果
     - 分析観点:
       a) 背景・文脈: このニュースが出てきた経緯、「なぜ今？」
       b) 複数視点: 最低2つの異なる立場からの見方（賛成/反対/中立など）
       c) データ検証: 数字がある場合、母数・比較対象・スケール感を整理
       d) 生活への影響: 一般市民の日常にどう関係するかの評価
       e) 不確実性: 現時点でわかっていないこと、今後の注目点
     - 出力（JSON構造化）:
       - background: 背景・文脈の説明
       - perspectives: [{stance, explanation}, ...] 複数視点
       - data_check: データの検証結果（該当する場合）
       - life_impact: 生活への影響の説明
       - uncertainties: 不確実な点のリスト
       - newsworthiness_score: ニュース価値スコア (1-5)
   - 結果を NewsItem.analysis_data に保存

3. app/pipeline/scriptwriter.py（Step 4）
   - 分析済みニュース一覧から放送台本を生成
   - プロンプト設計（CLAUDE.md のコンテンツ方針に従うこと）:
     - 入力: ニュース一覧（タイトル、要約、ファクトチェック結果、分析データ）
     - システムプロンプトに以下のルールを明記:

       あなたはAIニュースラジオのパーソナリティです。
       以下のルールに従って台本を作成してください。

       ## 台本構成（1ニュースあたり）
       1. 導入（10秒）: 「ひとことで言うと〜」で要点を伝える
       2. 背景解説（30秒）: なぜ重要か、経緯をストーリーで。専門用語はその場で平易に言い換える
       3. クリティカル分析（30秒）: 情報源の信頼性に言及。異なる立場からの見方を最低2つ提示。数字はスケール比較で実感化。不確実な点は「まだわかっていない」と明示
       4. 生活への影響（15秒）: 「私たちの暮らしにどう関係するか」を具体的に
       5. 締め（10秒）: リスナーへの問いかけ or 考えるヒント。断定的な結論は避ける

       ## 全体構成
       - オープニング挨拶（番組名、日付、ニュースの本数紹介）
       - 各ニュース（上記構成 × ニュース数）
       - ニュース間のつなぎの言葉（自然な接続）
       - エンディング（まとめ、次回予告的な一言）
       - 総尺: 5〜10分程度

       ## 禁止事項
       - 情報源不明の断定
       - 煽り・恐怖訴求
       - 一方的な立場の押し付け
       - 専門用語の説明なし使用

       ## 文体
       - 音声合成用のプレーンテキスト（SSML不要）
       - 句読点を適切に入れ、読みやすさを重視
       - 話し言葉寄り（「〜ですね」「〜なんですが」）

     - 出力: 台本テキスト + YouTube概要欄用のリファレンスリスト

4. YouTube概要欄リファレンスのフォーマット
   ```
   📰 本日のニュースソース

   1. [ニュースタイトル]
      ソース: [メディア名] ([日付]) [URL]
      裏取り: [公式サイト名] [URL]
      ファクトチェック: ✅確認済み / ⚠️一部未確認 / ❌要注意

   (以下繰り返し)

   ⚠️ 本番組はAIによる自動生成コンテンツを含みます。
   正確性には注意を払っていますが、最新情報は各公式サイトをご確認ください。
   音声: VOICEVOX:[キャラ名]
   ```

5. テスト
   - test_factchecker.py: モックAPIレスポンスでのテスト
   - test_analyzer.py: モックAPIレスポンスでのテスト（分析出力の構造検証）
   - test_scriptwriter.py: モックAPIレスポンスでのテスト（台本構成ルール準拠の検証）

### 制約
- 3ステップすべてで ai_provider.py 経由でAIを呼ぶこと（直接SDKを呼ばない）
- 各ステップでトークン使用量を ApiUsage に記録すること
- ファクトチェック結果が低スコア(1-2)のニュースは分析ステップで除外オプション
- 台本は SSML ではなくプレーンテキスト（VOICEVOX用）
- 分析ステップの出力は台本生成ステップの入力として直接使われる構造にすること
```

---

## Phase 6: 音声生成 + 動画化

```
CLAUDE.md を読んだ上で、音声生成と動画化のステップを実装してください。

### やること

1. app/services/voicevox.py
   - VOICEVOX Engine API (http://voicevox:50021) のラッパー
   - テキスト → 音声クエリ → 音声合成 の2ステップ
   - スピーカーID設定可能（デフォルト: ずんだもん or 四国めたん）
   - 長文は適切な長さに分割して合成→結合

2. app/pipeline/voice.py（Step 5）
   - 台本テキストを受け取り音声ファイル(WAV)を生成
   - セクションごとに音声生成（オープニング、各ニュース、エンディング）
   - 無音区間の挿入（ニュース間に1秒）
   - 最終的に1つのWAVファイルに結合
   - 生成した音声ファイルのパスを output_data に保存

3. app/pipeline/video.py（Step 6）
   - FFmpegで音声 + 静止画 → MP4動画を生成
   - 背景画像: シンプルなテンプレート画像（タイトル + 日付表示）
   - 将来的にはニュースごとにテロップ切り替え対応
   - 動画ファイルのパスを output_data に保存

4. 静的アセット
   - media/templates/ に背景テンプレート画像
   - media/bgm/ にBGM用プレースホルダー
   - media/output/ に生成ファイル保存（Docker volume）

5. テスト
   - test_voicevox.py: モックAPIでのテスト
   - test_voice_pipeline.py: 音声結合ロジックのテスト
   - test_video_pipeline.py: FFmpegコマンド生成のテスト

### 制約
- VOICEVOXコンテナが起動していない場合はエラーメッセージを明確に
- 音声・動画ファイルはDocker volumeに保存（コンテナ再起動で消えない）
- FFmpegはbackendコンテナのDockerfileに含まれている（Phase 1で設定済み）
- VOICEVOXのクレジット表記「VOICEVOX:[キャラ名]」を概要欄に含めること
```

---

## Phase 7: YouTube投稿 + 仕上げ

```
CLAUDE.md を読んだ上で、YouTube投稿ステップと全体の仕上げを行ってください。

### やること

1. app/services/youtube.py
   - YouTube Data API v3 ラッパー
   - OAuth2認証フロー（初回のみブラウザ認証）
   - 動画アップロード
   - タイトル、説明文（概要欄）、タグ、カテゴリ設定
   - 公開設定（デフォルト: 限定公開 → 承認後に公開）

2. app/pipeline/publisher.py（Step 7）
   - 動画ファイルをYouTubeにアップロード
   - タイトル: 「AIニュース速報 - YYYY/MM/DD」
   - 説明文: scriptwriter が生成したリファレンスリスト
   - タグ: ニュース, AI, ローカルニュース
   - 限定公開でアップロード → 最終承認後に公開に変更
   - output_data にYouTube URLを保存

3. ダッシュボード拡張
   - 各ステップの出力プレビュー:
     - 収集: ニュース一覧テーブル
     - ファクトチェック: チェック結果 + 信頼度バッジ
     - 分析: 背景・視点・影響のカード表示
     - 台本: テキストプレビュー（編集可能）
     - 音声: ブラウザ内で再生可能なオーディオプレイヤー
     - 動画: ブラウザ内で再生可能なビデオプレイヤー
     - 投稿: YouTube URLリンク
   - 台本の手動編集機能（承認前に修正可能）

4. ドキュメント整備
   - docs/setup.md: 詳細セットアップ手順
   - docs/architecture.md: アーキテクチャ説明
   - docs/youtube-auth.md: YouTube API認証の手順
   - README.md の更新

5. 全体テスト
   - E2Eテスト: エピソード作成→全7ステップ承認→完了のフロー（モック使用）

### 制約
- YouTube API credentials はDockerの外で管理（.envとvolume mount）
- 初回のOAuth認証はブラウザリダイレクトが必要なので手順を明記
- 動画の公開は必ず最終承認ステップを経ること
```
