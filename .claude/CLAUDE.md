# sysden

markdown + mermaid で書かれたシステム設計ドキュメントを管理・閲覧する Web アプリ。
ブラウザ上の依頼 UI から AI（Claude Agent SDK）に依頼してドキュメントを生成・更新する。
人向けのテキストエディタは提供しない。

## アーキテクチャ

```
ブラウザ (htmx + _hyperscript + mermaid.js)
  │
  └── FastAPI (uvicorn)
       ├── routers/html.py   — HTML ページ (Jinja2)
       ├── routers/api.py    — JSON API
       ├── routers/events.py — SSE (/events)
       ├── ai_service        — Agent SDK セッション管理・リビジョン生成
       ├── document_service  — ドキュメント CRUD
       ├── event_bus         — asyncio.Queue ベースの SSE 通知
       └── PostgreSQL (SQLAlchemy 2 async + asyncpg)
```

AI 生成は `asyncio.create_task()` で非同期実行し、完了を SSE でブラウザに通知する。

## 技術スタック

- Python 3.14+ / FastAPI + uvicorn（ASGI サーバー）
- SQLModel（SQLAlchemy 2.x async ラッパー）+ asyncpg（PostgreSQL アクセス）
- Anthropic SDK（Claude Agent SDK クライアント）
- markdown-it-py（markdown → HTML 変換）
- sse-starlette（Server-Sent Events）
- Jinja2（HTML テンプレート）
- htmx + htmx-ext-sse + _hyperscript + mermaid.js（フロントエンド）
- uv / taskipy（パッケージ管理・タスクランナー）

## コマンド

```bash
uv run task dev       # FastAPI 開発サーバー起動（ポート 8000）
uv run task test      # テスト + カバレッジ
uv run task lint      # Ruff チェック
uv run task format    # Ruff フォーマット
uv run task typecheck # ty 型チェック
```

## コード品質

- **行長**: 100 文字以内（Ruff 強制）
- **複雑度**: 認知的複雑度 ≤ 10（Ruff C901 強制）
- **import 順序**: Ruff I（isort 互換）で自動整理
- **モダン構文**: Ruff UP（pyupgrade）で最新 Python 構文を強制（`Optional[X]` → `X | None` など）
- **バグ検出**: Ruff B（flake8-bugbear）で一般的なバグパターンを検出
- **簡潔化**: Ruff SIM（flake8-simplify）で不必要に複雑なコードを検出
- **命名規約**: Ruff N（pep8-naming）で PEP 8 準拠の命名を強制
- **print 禁止**: Ruff T20 で `print()` の残留を検出（ログは `logging` を使う）
- **型チェック**: ty（pre-commit フック）
- **テストカバレッジ**: 80% 以上（`fail_under = 80`）

## Python コーディング規約

- 型アノテーションを必ず付ける（引数・戻り値）。`Optional[X]` ではなく `X | None` を使う
- async 関数には `async def` を使う。DB アクセスはすべて await する
- DB セッションは `async with AsyncSession(engine) as session:` パターンで使う（SQLModel の `AsyncSession` を利用）
- `event_bus` は `asyncio.Queue` ベース。全処理がイベントループ内のため `call_soon_threadsafe` は不要
- `except` 節で例外を再送出するときは `raise ... from err` または `raise ... from None` を使う
- 値による分岐は `if-elif` チェーンではなく `match-case` 文を優先する

## docstring・コメント規約

- プロダクトコードの公開関数には Google スタイルの docstring を付ける
- 非公開関数（`_` プレフィックス）や自明なヘルパーは省略可

```python
def generate_table_design(prompt: str, current_tsv: str | None = None) -> str:
    """AI にテーブル設計（TSV）を生成または更新させる。

    Args:
        prompt: ユーザーからの依頼テキスト。
        current_tsv: 既存のカラム定義 TSV。指定時は更新モードで動作する。

    Returns:
        生成されたカラム定義の TSV 文字列。

    Raises:
        ValueError: OPENAI_API_KEY が未設定の場合。
    """
```

## テストコード規約

- **unittest より pytest を優先**: `unittest.mock.patch` / `MagicMock` ではなく
  `monkeypatch` / `pytest.fixture` を使う
- pytest fixture が適したところでは積極的に活用する（テストデータ、モック注入など）
- **ユニットテスト**: AAA（Arrange-Act-Assert）スタイルで空行ブロック分けする

```python
def test_write_and_read_tsv(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    rows = table_service.read_tsv("users")

    # Assert
    assert rows[0]["column_name"] == "id"
```

- **統合テスト・E2E**: Gherkin（Given-When-Then）スタイルで空行ブロック分けする

```python
def test_create_table_via_ai(client: TestClient, mock_openai: None) -> None:
    # Given: AI モックが TSV を返す状態でアプリが起動している

    # When: テーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"name": "users", "prompt": "ユーザーテーブルを作って"},
        follow_redirects=True,
    )

    # Then: 200 が返りテーブル名がレスポンスに含まれる
    assert resp.status_code == 200
    assert "users" in resp.text
```

## エラーハンドリング規約

- ドメイン層・サービス層の失敗は、意味のあるエラー種別（例外クラスまたはエラーコード）で表現する
- HTTP ハンドラは生の `error` 文字列に依存せず、例外の**型**からステータスコードとユーザー向けメッセージを決定する
- 同じ種類の失敗は、ハンドラやレスポンス形式（HTML / JSON）にかかわらず同じメッセージを返す
- `strings.Contains(err.Error(), "...")` 相当の文字列マッチによるエラー判定は禁止

## 静的アセット分離ルール

- `<script>` タグ内にコードを直接書かない。ロジックは `static/js/*.js` に切り出す
- `<style>` タグ内にスタイルを直接書かない。スタイルは `static/css/*.css` に切り出す
- `<svg>` タグをテンプレートに直接書かない。アイコンは `static/icons/*.svg` に切り出す
- テンプレートからは `<script src="/static/js/...">` や `<link rel="stylesheet" href="/static/css/...">` で参照する
- **例外（インラインで書いてよいもの）**: hyperscript の `_="..."` 属性、htmx の `hx-*` 属性

## UI インタラクション規約

- クラス付け替え・表示/非表示・モーダル開閉・タブ切り替えなどの一般的な UI インタラクションは hyperscript 属性で記述する
- ページごとの ad-hoc な JavaScript を増やさない
- JavaScript を書くべきケース: 複数コンポーネント間で状態を共有する複雑な挙動、API 呼び出しなどロジックに集中する処理

## AI 連携規約

- **ANTHROPIC_API_KEY は設定しない**。Agent SDK はサブスクリプション認証で動作する。
  シェルに `ANTHROPIC_API_KEY` が設定されていると SDK がそちらを優先し Max プランの枠外で課金される
- Agent（設計書生成の指示・モデル ID）はアプリ起動時に 1 回だけ作成し、ID を state に保持する
- AI ジョブ 1 件 = Session 1 件。セッション完了後に `agent.message` から markdown を抽出する
- 失敗時は `status=failed` と `error` を記録。リビジョンは作成せず現行ドキュメントは無傷で残す

## テスト規約

- **ユニットテスト**: `tests/unit/` — pytest AAA スタイル、外部依存なし
  - ai_service のテストでは Agent SDK をモックする
- **インテグレーションテスト**: `tests/integration/` — FastAPI `TestClient` + テスト用 PostgreSQL
- **E2E テスト**: `tests/e2e/` — Playwright（下記 E2E 規約を参照）
- SSE エンドポイントのテストは `TestClient` の制限からルート登録確認のみ行う
- `uv run pytest tests/unit -q` は 60 秒以内に完了すること

```python
# SSE ルート登録確認の例
def test_events_route_is_registered():
    from app.main import app
    from fastapi.routing import APIRoute
    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert "/events" in paths
```

## E2E テスト規約

### スコープ・方針

- ルーターが配線済みの画面のみテスト対象とする
- BE 内部仕様の網羅性は不要。FE 部品の網羅性を重視する
- 新しい画面・ルーターを追加したら、対応する E2E テストファイルも追加する

### スタイル

- **Gherkin (Given-When-Then)** コメントで各テストの意図を明示し、空行でブロック分けする
- クラスで論理グループ化: `Test<Page><Category>` (例: `TestIndexPageEmpty`, `TestCreateTableForm`)
- 関数名: `test_<what_is_being_tested>`
- ファイル: `test_<page_name>.py`（ページ単位）、`test_navigation.py`（ページ間遷移フロー）

### AI モック

- `SYSDEN_TEST_MODE=1` 環境変数で `ai_service` をスタブ化する。実際の API は呼ばない
- サーバーは `tests/e2e/conftest.py` の session スコープ fixture でサブプロセス起動する

### データ分離

- 各テスト前に `SYSDEN_DATA` 内の TSV を削除する autouse fixture `clean_data` でテスト間の独立性を保証する
- テスト前提条件は `create_table` fixture（httpx POST）で API 経由で作成する

### FE 部品チェックリスト（各画面で網羅すること）

- 全 UI 要素の存在確認（ボタン、リンク、フォーム、入力欄、見出し）
- 空状態のメッセージ表示 / 非表示
- ボタン・リンクの属性（href, action, hx-* の結果）
- フォーム送信後の遷移先
- HTML バリデーション（required 属性）
- htmx インタラクション（hx-delete + hx-confirm、DOM 更新）
- ナビゲーションバーのリンク
- ページタイトル (`<title>`)

### 実行コマンド

```bash
uv run task e2e           # E2E のみ
uv run pytest tests/e2e -v --headed  # ブラウザ表示ありデバッグ
uv run task test          # 全テスト（unit + integration + e2e）
```

## 開発フロー（テスト先行）

- 新機能追加・仕様変更では、**先にテストを書き、そのテストを通す実装を行う**
- テストがすべてグリーンになった時点でタスク完了とみなす
- **不具合を確認したとき**: 先に落ちる回帰テストを追加してから修正する
- リファクタリングでは先に既存挙動をテストで固定してからコードを変更する
- テストの優先順位:
  1. 代表的なユーザーフローは Playwright E2E
  2. HTML 構造・API のステータスコードは FastAPI `TestClient` 統合テスト
  3. ドメインロジック単体は pytest ユニットテスト

## テンプレートレスポンス

```python
# 正しい（Starlette 1.x 以降）
templates.TemplateResponse(request, "template.html", {"key": "value"})
```

## 応答言語

- **会話**: ユーザーとのやりとりは基本的に**日本語**で行う
- **説明・コメント**: コード外の説明、コミットメッセージも日本語で書く
- **コード**: 変数名・関数名・ファイル名はプロジェクトの既存規約に従う（英語のまま）
- ユーザーが英語で質問した場合は、返答も英語で行う

## コミット規約

Conventional Commits + 日本語:

```
feat: ドキュメントビューア画面を追加する
fix: AI ジョブが完了しても SSE 通知が届かない問題を修正する
chore: CI ワークフローを更新する
```
