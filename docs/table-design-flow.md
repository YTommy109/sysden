# テーブル設計 TSV 生成フロー

ユーザーがブラウザからテーブル設計を依頼し、LLM が TSV 形式のカラム定義を生成するまでのシーケンス。

## 概要

sysden のテーブル設計機能は、ユーザーの自然言語プロンプトを OpenAI Chat Completions API に送信し、構造化された TSV（タブ区切り）形式のカラム定義を受け取る。新規作成と既存テーブルの更新で、LLM に送るメッセージの組み立て方が異なる。

## シーケンス図

### 新規テーブル作成

```mermaid
sequenceDiagram
    participant B as ブラウザ
    participant R as FastAPI Router<br>(api.py)
    participant AI as ai_service
    participant LLM as OpenAI API<br>(gpt-4o)
    participant TS as table_service
    participant FS as ファイルシステム<br>(SYSDEN_DATA/)

    B->>R: POST /api/tables<br>{name, prompt}
    R->>TS: table_exists(name)
    TS->>FS: {name}.tsv 存在確認
    FS-->>TS: false
    TS-->>R: false

    R->>AI: generate_table_design(prompt)
    Note over AI: user_message = prompt をそのまま使用

    AI->>LLM: chat.completions.create<br>model: gpt-4o, temperature: 0.2
    Note over AI,LLM: messages:<br>1. system: SYSTEM_PROMPT（TSV 書式規約）<br>2. user: ユーザーの依頼テキスト

    LLM-->>AI: TSV 文字列<br>(ヘッダー + データ行)
    AI-->>R: TSV 文字列

    R->>TS: write_tsv(name, tsv)
    TS->>FS: {name}.tsv 書き込み
    FS-->>TS: OK
    TS-->>R: OK

    R-->>B: 303 Redirect → /tables/{name}
    B->>R: GET /tables/{name}
    R-->>B: テーブル詳細 HTML
```

### 既存テーブル更新

```mermaid
sequenceDiagram
    participant B as ブラウザ
    participant R as FastAPI Router<br>(api.py)
    participant AI as ai_service
    participant LLM as OpenAI API<br>(gpt-4o)
    participant TS as table_service
    participant FS as ファイルシステム<br>(SYSDEN_DATA/)

    B->>R: POST /api/tables/{name}<br>{prompt}
    R->>TS: read_tsv_raw(name)
    TS->>FS: {name}.tsv 読み込み
    FS-->>TS: 現在の TSV 文字列
    TS-->>R: current_tsv

    R->>AI: generate_table_design(prompt, current_tsv)
    Note over AI: user_message を組み立て:<br>「現在のテーブル定義:\n{current_tsv}\n\n依頼: {prompt}」

    AI->>LLM: chat.completions.create<br>model: gpt-4o, temperature: 0.2
    Note over AI,LLM: messages:<br>1. system: SYSTEM_PROMPT（TSV 書式規約）<br>2. user: 現在定義 + 依頼テキスト

    LLM-->>AI: 更新後の TSV 文字列
    AI-->>R: TSV 文字列

    R->>TS: write_tsv(name, tsv)
    TS->>FS: {name}.tsv 上書き
    FS-->>TS: OK
    TS-->>R: OK

    R-->>B: 303 Redirect → /tables/{name}
```

## 各コンポーネントの役割

| コンポーネント | ファイル | 責務 |
|---|---|---|
| **API Router** | `app/routers/api.py` | HTTP リクエスト受付、バリデーション、サービス呼び出し、リダイレクト |
| **ai_service** | `app/ai_service.py` | LLM クライアント管理、プロンプト組み立て、API 呼び出し |
| **table_service** | `app/table_service.py` | TSV ファイルの CRUD、Markdown 変換 |
| **HTML Router** | `app/routers/html.py` | テーブル詳細画面の描画（TSV → Markdown → HTML） |

## LLM 通信の詳細

### システムプロンプト

LLM には「データベーステーブル設計アシスタント」としてのロールと、TSV の出力書式ルールをシステムプロンプトで指定する。プロンプト定義は `prompts/ai_prompts.yaml` で管理されている。

### メッセージ構成

| # | role | 内容 |
|---|---|---|
| 1 | `system` | TSV 書式規約（ヘッダー形式、YES/NO 表記、日本語 description） |
| 2 | `user` | **新規**: ユーザーの依頼テキストそのまま |
|   |        | **更新**: `現在のテーブル定義:\n{TSV}\n\n依頼: {テキスト}` |

### API パラメータ

| パラメータ | 値 | 理由 |
|---|---|---|
| `model` | `gpt-4o` | 構造化出力の精度を優先 |
| `temperature` | `0.2` | TSV 形式の安定性を確保するため低めに設定 |

### テストモード

環境変数 `SYSDEN_TEST_MODE=1` が設定されている場合、LLM API を呼ばずスタブ TSV を返す。E2E テストで使用する。
