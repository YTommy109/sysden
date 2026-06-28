# 常設チャットエリア設計

<!-- constrained-by ./2026-06-26-toon-migration-design.md -->

## 概要

現在の「新規作成ダイアログ」「更新フォーム」を廃止し、画面右側に常設のチャットエリアを設ける。ユーザーは LLM と複数ターンの会話を通じてテーブル設計の作成・更新を行う。

### 要件

- **複数ターン会話**: LLM が過去のやり取りを覚えて対話を重ねる
- **グローバルに 1 つ**: 全ページで共通のチャットエリア
- **ストリーミング表示**: トークン単位で逐次表示
- **即時反映**: AI の応答に TOON が含まれればテーブルとして保存・反映
- **サーバー側永続化**: ブラウザを閉じても履歴が残る
- **単一会話（リセット可）**: 複数会話の管理はしない
- **開閉可能**: トグルボタンでチャットエリアを表示/非表示

## アーキテクチャ

### 通信方式: WebSocket

チャットのメッセージ送受信とストリーミング応答に WebSocket を使用する。FastAPI のネイティブ WebSocket サポートを利用。

選定理由:
- ストリーミング応答が自然に実装できる
- サーバー → クライアントのプッシュ通知が容易
- SSE は単方向のため htmx-ext-sse でのトークン単位追記に制約がある
- REST ポーリングではストリーミング不可

### AI 呼び出し: 二段構え方式

全テーブルの full TOON を毎回コンテキストに載せるとトークンが爆発するため、二段構えで必要なテーブルだけをロードする。

```
ユーザーメッセージ
    │
    ▼ Stage 1: 関連テーブル特定
    LLM ← prompt + index.toon（サマリー一覧）
    LLM → 必要なテーブル名リスト or 「テーブル操作なし」
    │
    ├─ テーブル操作なしの場合 → Stage 2 へ（コンテキストなし）
    │
    ▼ テーブル読み込み
    必要テーブルの full TOON をファイルから読み込み
    │
    ▼ Stage 2: 設計生成（ストリーミング）
    LLM ← 会話履歴 + full TOON + ルール
    LLM → ストリーミング応答
```

Stage 1 のコストは小さく（index サマリーと短い依頼文のみ）、得られる精度向上は大きい。

## レイアウト

```
┌─────────────────────────────────────────────────────┐
│ nav: sysden                            [💬 トグル]   │
├──────────────────────────────┬──────────────────────┤
│                              │ チャット       [🔄]   │
│  {% block content %}         │──────────────────────│
│  （一覧 or 詳細）            │ メッセージ一覧       │
│                              │ (自動スクロール)     │
│                              │──────────────────────│
│                              │ [textarea]    [送信] │
└──────────────────────────────┴──────────────────────┘
```

- 左側: 現在の `{% block content %}` がそのまま入る
- 右側: 常設チャットエリア（`base.html` に組み込み、全ページ共通）
- ナビゲーションバーにトグルボタンを配置
- チャット閉じ時はメインコンテンツが全幅を使用
- チャットエリアは固定幅（360px）

### 廃止する UI

- `index.html` の `<dialog id="create-dialog">` と「テーブル追加」ボタン
- `table_detail.html` の「AI に更新を依頼」フォーム

## データモデル

### 会話データ

`.data/chat/conversation.json` に保存:

```json
{
  "id": "conv_20260628_001",
  "created_at": "2026-06-28T10:00:00Z",
  "messages": [
    {
      "role": "user",
      "content": "ユーザーテーブルを作って",
      "timestamp": "2026-06-28T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "ユーザーテーブルを作成しました。...",
      "timestamp": "2026-06-28T10:00:05Z",
      "actions": [
        {"type": "create_table", "table_name": "TABLE_0001"}
      ]
    }
  ]
}
```

- `messages` は OpenAI API の `messages` パラメータにマッピング可能な構造
- `actions` は AI 応答に伴って実行されたアクション（テーブル作成/更新）を記録
- リセット時は `conversation.json` をクリアして新しい `id` を採番

## バックエンド設計

### 新規モジュール

#### `app/chat_service.py`

会話管理と AI 連携を担当:

- `load_conversation() -> Conversation`: JSON ファイルから会話を読み込む
- `save_conversation(conversation)`: JSON ファイルに会話を保存する
- `add_user_message(content) -> Message`: ユーザーメッセージを追加する
- `identify_relevant_tables(prompt, index) -> list[str]`: Stage 1 — 関連テーブルを特定する
- `generate_response(conversation, context) -> AsyncGenerator[str]`: Stage 2 — OpenAI Streaming API でトークンを yield する
- `extract_and_apply_actions(response) -> list[Action]`: 応答テキストから TOON を検出し、テーブルを保存する
- `reset_conversation() -> Conversation`: 会話をクリアする

#### `app/routers/chat.py`

WebSocket エンドポイント:

- `GET /api/chat/history`: 既存の会話履歴を返す（ページ読み込み時）
- `WebSocket /ws/chat`: メッセージの送受信

### WebSocket プロトコル

クライアント → サーバー:

```json
{"type": "message", "content": "ユーザーテーブルを作って"}
{"type": "reset"}
```

サーバー → クライアント:

```json
{"type": "stream", "content": "ユ"}
{"type": "stream", "content": "ー"}
{"type": "stream_end", "content": "（全文）", "actions": [{"type": "create_table", "table_name": "TABLE_0001"}]}
{"type": "content_updated", "target": "table_list"}
{"type": "history", "messages": [...]}
{"type": "error", "message": "エラーメッセージ"}
```

### AI プロンプト設計

#### Stage 1: 関連テーブル特定

```yaml
chat_identify:
  system: |
    ユーザーの依頼と既存テーブル一覧を見て、この依頼を処理するために
    詳細設計が必要なテーブル名をJSON配列で返してください。
    テーブル操作を伴わない質問・雑談の場合は空配列を返してください。
    出力はJSON配列のみ（例: ["TABLE_0001", "TABLE_0003"] or []）
  model: gpt-4o
  temperature: 0
```

#### Stage 2: 設計生成（統合プロンプト）

現在の `core_create` / `core_update` を統合:

```yaml
chat:
  system: |
    あなたはデータベーステーブル設計のアシスタントです。
    ユーザーとの会話を通じて、テーブル設計の作成・更新を行います。

    対応できる操作:
    1. 新規テーブル作成: ユーザーの依頼からTOON形式のコア設計を生成
    2. 既存テーブル更新: 指定テーブルのコア設計を変更依頼に基づき更新
    3. 設計の説明・相談: テーブル設計に関する質問への回答

    テーブルを作成・更新する場合:
    - 必ず TOON フォーマットで出力すること（meta + columns）
    - 応答にTOONブロックが含まれる場合、システムが自動的にテーブルとして保存する
    - 会話的な説明も添えてよい（TOONブロックの前後に自然言語を書ける）

    TOON 出力フォーマット:
        meta:
          logical_name: 日本語テーブル名
          physical_name: 英語スネークケース
          description: テーブルの説明
        columns[N]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
          COLUMN_0001,...

        出力規則:
        - symbol は COLUMN_0001 から連番で付与する
        - 既存カラムの symbol は変更しない
        - type は具体的な SQL 型（uuid, varchar(255), integer, timestamptz など）
        - nullable, pk, unique は YES または NO
        - fk_target は参照先テーブルのシンボルを使用する
        - 同一リクエスト内の新規テーブルを参照する場合は NEW_1, NEW_2 等のプレースホルダを使用する
        - 共通ルールで指定されたカラムを必ず含めること
        - [N] はデータ行数と一致させること
        - 複数テーブルを出力する場合、テーブル間は空行で区切る
        - コードブロック記号は不要
  model: gpt-4o
  temperature: 0.2
```

### 既存コードへの影響

- `ai_service.py`: `create_table_design()` / `update_table_design()` は残す（直接 API からも呼べるように）
- `routers/api.py`: `POST /api/tables` / `POST /api/tables/{name}` は残す（API 互換性）
- `index.html`: `<dialog>` を削除
- `table_detail.html`: 更新依頼フォームを削除
- `base.html`: チャットエリアとトグルボタンを追加

## フロントエンド設計

### チャット UI

`base.html` にチャットエリアを組み込む。`_chat.html` パーシャルとして分離も可。

### JavaScript: `static/js/chat.js`

htmx ではなくバニラ JS で WebSocket を管理:

- **WebSocket 接続管理**: 自動再接続（指数バックオフ）
- **メッセージ送信**: textarea の内容を JSON で送信、Ctrl+Enter で送信
- **ストリーミング受信**: `stream` イベントで DOM にテキストを追記、`stream_end` で確定
- **左側コンテンツ更新**: `content_updated` 受信時に `htmx.ajax()` で再取得
- **トグル**: チャットエリアの表示/非表示切り替え、状態を `localStorage` に保存

### 左側コンテンツの更新フロー

1. AI がテーブルを作成/更新 → サーバーが `{"type": "content_updated"}` を送信
2. JS が現在のページ URL に応じて適切な htmx リクエストを発行:
   - 一覧ページ: `htmx.ajax('GET', '/', {target: '#main-content'})`
   - 詳細ページ: `htmx.ajax('GET', '/tables/{name}', {target: '#main-content'})`

## テスト戦略

### ユニットテスト

- `chat_service.py`: 会話の読み書き、メッセージ追加、リセット、Stage 1 テーブル特定、Stage 2 応答パース、TOON 検出・アクション実行
- `routers/chat.py`: WebSocket エンドポイントのテスト（Starlette `TestClient` の WebSocket サポート）

### E2E テスト

- チャットエリアの開閉トグル
- メッセージ送信 → ストリーミング応答表示
- テーブル作成後の左側コンテンツ自動更新
- 会話リセット
- ページ遷移後のチャット履歴維持

### テストモード

`SYSDEN_TEST_MODE=1` でストリーミングを模擬（スタブ TOON を逐次返す）。

## ファイル構成（変更・追加）

```
app/
  chat_service.py          ← 新規: 会話管理 + AI 二段構え
  routers/
    chat.py                ← 新規: WebSocket + 履歴 API
    api.py                 ← 変更なし（API 互換性維持）
    html.py                ← 変更なし
templates/
  base.html                ← 変更: チャットエリア追加
  _chat.html               ← 新規: チャット UI パーシャル
  index.html               ← 変更: ダイアログ削除
  table_detail.html         ← 変更: 更新フォーム削除
static/
  js/chat.js               ← 新規: WebSocket + チャット UI
  css/style.css            ← 変更: チャットエリアのスタイル追加
prompts/
  ai_prompts.yaml          ← 変更: chat / chat_identify 追加
.data/
  chat/
    conversation.json      ← 新規: 会話データ（実行時生成）
```
