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
- Alembic（スキーママイグレーション）
- Anthropic SDK（Claude Agent SDK クライアント）
- markdown-it-py（markdown → HTML 変換）
- sse-starlette（Server-Sent Events）
- Jinja2（HTML テンプレート）
- htmx + htmx-ext-sse + _hyperscript + mermaid.js（フロントエンド）
- uv / taskipy（パッケージ管理・タスクランナー）
- Docker Compose（app + postgres）

## コマンド

```bash
uv run task dev       # FastAPI 開発サーバー起動（ポート 8000）
uv run task test      # テスト + カバレッジ
uv run task migrate   # Alembic マイグレーション適用
uv run task lint      # Ruff チェック
uv run task format    # Ruff フォーマット
uv run task typecheck # ty 型チェック
```

## コード品質

- **行長**: 100 文字以内（Ruff 強制）
- **複雑度**: 認知的複雑度 ≤ 10（Ruff C901 強制）
- **import 順序**: Ruff I（isort 互換）で自動整理
- **型チェック**: ty（pre-commit フック）
- **テストカバレッジ**: 80% 以上（`fail_under = 80`）

## Python コーディング規約

- 型アノテーションを必ず付ける（引数・戻り値）
- async 関数には `async def` を使う。DB アクセスはすべて await する
- DB セッションは `async with AsyncSession(engine) as session:` パターンで使う（SQLModel の `AsyncSession` を利用）
- `event_bus` は `asyncio.Queue` ベース。全処理がイベントループ内のため `call_soon_threadsafe` は不要

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
- **e2e**: `tests/e2e/` — Playwright（依頼送信→プレビュー更新、ロールバック、エラーパネル）
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

## テンプレートレスポンス

```python
# 正しい（Starlette 1.x 以降）
templates.TemplateResponse(request, "template.html", {"key": "value"})
```

## コミット規約

Conventional Commits + 日本語:

```
feat: ドキュメントビューア画面を追加する
fix: AI ジョブが完了しても SSE 通知が届かない問題を修正する
chore: alembic 初期マイグレーションを追加する
```
