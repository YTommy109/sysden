---
name: new-page
description: 新しい画面（ルーター + テンプレート + E2E テスト）を追加する
---

# /new-page — 画面追加

新しい画面を追加するとき、ルーター・テンプレート・E2E テストの 3 点セットを漏れなく作成する。

## 引数

```
/new-page <page_name> — <画面の説明>
```

例: `/new-page settings — アプリ設定画面`

## 手順

### 1. 既存構造の確認

以下を確認して、既存の命名パターンとディレクトリ構成を把握する。

- `app/routers/` 内の既存ルーターファイル
- `templates/` 内の既存テンプレートファイル
- `templates/base.html` のレイアウト構造
- `tests/e2e/` 内の既存テストファイル

### 2. ルーター作成

`app/routers/<page_name>.py` を作成する。

- 既存ルーター（`html.py` など）のパターンに従う
- `templates.TemplateResponse(request, "<page_name>.html", {...})` 形式でレスポンスを返す
- 型アノテーション・docstring は CLAUDE.md の規約に従う

### 3. テンプレート作成

`templates/<page_name>.html` を作成する。

- `{% extends "base.html" %}` でベーステンプレートを継承する
- `{% block title %}` と `{% block content %}` を設定する
- 静的アセット分離ルールに従う（インライン `<script>` / `<style>` 禁止）
- htmx / hyperscript の属性はインラインで OK

### 4. ルーターの登録

`app/main.py` にルーターを `include_router()` で登録する。

### 5. E2E テスト作成

`tests/e2e/test_<page_name>.py` を作成する。

CLAUDE.md の E2E テスト規約に従い、以下を網羅する:

- Gherkin（Given-When-Then）コメントスタイル
- クラスで論理グループ化: `Test<PageName><Category>`
- FE 部品チェックリストの全項目:
  - 全 UI 要素の存在確認（ボタン、リンク、フォーム、入力欄、見出し）
  - 空状態のメッセージ表示 / 非表示
  - ボタン・リンクの属性（href, action, hx-* の結果）
  - フォーム送信後の遷移先
  - HTML バリデーション（required 属性）
  - htmx インタラクション（hx-delete + hx-confirm、DOM 更新）
  - ナビゲーションバーのリンク
  - ページタイトル (`<title>`)

### 6. ナビゲーション更新

`templates/base.html` のナビゲーションバーに新しい画面へのリンクを追加する。
`tests/e2e/test_navigation.py` にページ間遷移のテストを追加する。

### 7. 検証

```bash
uv run task lint
uv run ruff format --check .
uv run task typecheck
uv run task test
```

すべてパスしたら完了。
