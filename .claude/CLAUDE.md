# sysden

テーブル設計ドキュメント（TSV + markdown + mermaid ER 図）を管理・閲覧する Web アプリ。
ブラウザ上の依頼 UI から AI（OpenAI API）に依頼してテーブル定義を生成・更新する。
人向けのテキストエディタは提供しない。

## アーキテクチャ

```
ブラウザ (htmx + _hyperscript + mermaid.js)
  │
  └── FastAPI (uvicorn)
       ├── routers/html.py   — HTML ページ (Jinja2)
       ├── routers/api.py    — JSON API + フォーム受付
       ├── ai_service.py     — OpenAI Chat Completions でテーブル設計を生成
       ├── table_service.py  — テーブル CRUD（TSV/markdown ファイル操作）
       ├── config.py         — データディレクトリ設定
       └── ファイルストレージ（.data/ 配下の TSV + markdown + mermaid）
```

AI 生成は同期的に実行し、レスポンスで結果をリダイレクトする。

## 技術スタック

- Python 3.14+ / FastAPI + uvicorn（ASGI サーバー）
- OpenAI SDK（テーブル設計の AI 生成）
- markdown-it-py（markdown → HTML 変換）
- Jinja2（HTML テンプレート）
- htmx + _hyperscript + mermaid.js（フロントエンド）
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
