# sysden

コーディング規約は [docs/coding_rule.md](../docs/coding_rule.md) に一元管理する。
以下はその要約。

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

## コマンド

```bash
uv run task dev       # FastAPI 開発サーバー起動（ポート 8000）
uv run task test      # テスト + カバレッジ
uv run task lint      # Ruff チェック
uv run task format    # Ruff フォーマット
uv run task typecheck # ty 型チェック
```

## コード品質

詳細は [docs/coding_rule.md のコード品質ツール](../docs/coding_rule.md#コード品質ツール) を参照。

- Ruff: 行長 100、C901 ≤ 10、isort、pyupgrade、bugbear、simplify、naming、print 禁止
- ty 型チェック
- テストカバレッジ 80% 以上

## 応答言語

- **会話・説明・コミットメッセージ**: 日本語
- **コード（変数名・関数名・ファイル名）**: 英語（既存規約に従う）
- ユーザーが英語で質問した場合は英語で返答

## コミット規約

Conventional Commits + 日本語:

```
feat: ドキュメントビューア画面を追加する
fix: AI ジョブが完了しても SSE 通知が届かない問題を修正する
chore: CI ワークフローを更新する
```
