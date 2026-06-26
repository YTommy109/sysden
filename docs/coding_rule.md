# sysden コーディング規約

このドキュメントは sysden プロジェクトのコーディング規約を一元管理する。
CLAUDE.md・スキル・コマンドはこのファイルを参照する。

## プロジェクト概要

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
uv run task e2e       # E2E テストのみ
```

## コード品質ツール

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
- `except` 節で例外を再送出するときは `raise ... from err` または `raise ... from None` を使う
- テーブル名は `validate_table_name()` で検証する（`^[a-z][a-z0-9_]{0,63}$`）

### Python 3.14 モダン構文の積極活用

Python 3.14 の新しい文法・機能を積極的に使う。古い書き方より新しい書き方を常に優先する:

- **match-case**: `if-elif` チェーンではなく `match-case` 文を優先する
- **型構文**: `Union[X, Y]` → `X | Y`、`Optional[X]` → `X | None`、`dict[str, int]` など小文字ジェネリクス
- **構造的パターンマッチング**: 辞書・タプル・クラスのデストラクチャリングに `match-case` を活用する
- **例外グループ**: 複数例外の同時処理には `except*` を検討する
- **f-string**: 文字列結合や `format()` ではなく f-string を使う
- **walrus 演算子**: `if (m := re.match(...))` のように代入と条件判定を一行にまとめられる場合は使う
- **TypeAlias / type 文**: 複雑な型には `type` 文でエイリアスを定義する

## docstring・コメント規約

- 公開関数には Google スタイルの docstring を付ける
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

## ロギング規約

- Python 標準の `logging` モジュールを使う（`print()` 禁止は Ruff T20 で強制済み）
- モジュール先頭で `logger = logging.getLogger(__name__)` を定義する
- LLM による調査がしやすいログを書く:
  - **操作・入力・結果を 1 行にまとめる**: 何をしたか・何を受け取ったか・どうなったかが 1 行で読めること
  - **識別子を含める**: テーブル名・リクエスト ID など、ログを grep で絞り込める値を入れる
  - **失敗時は原因と入力値をセットで出す**: エラーメッセージだけでなく、再現に必要なコンテキストを添える

```python
logger = logging.getLogger(__name__)

def generate_table_design(table_name: str, prompt: str) -> str:
    logger.info("AI 生成開始: table=%s prompt_length=%d", table_name, len(prompt))
    try:
        result = _call_openai(prompt)
        logger.info("AI 生成完了: table=%s columns=%d", table_name, len(result.split("\n")))
        return result
    except OpenAIError as err:
        logger.exception("AI 生成失敗: table=%s", table_name)
        raise
```

- ログレベルの使い分け:
  - `DEBUG`: 内部状態の詳細（開発時のみ有用）
  - `INFO`: 正常な処理の開始・完了
  - `WARNING`: 想定内だが注意が必要な状態（フォールバック発動など）
  - `ERROR` / `exception`: 処理失敗（`logger.exception()` でトレースバック付き）

## エラーハンドリング規約

- ドメイン層・サービス層の失敗は、意味のあるエラー種別（例外クラスまたはエラーコード）で表現する
- HTTP ハンドラは生の `error` 文字列に依存せず、例外の**型**からステータスコードとユーザー向けメッセージを決定する
- 同じ種類の失敗は、ハンドラやレスポンス形式（HTML / JSON）にかかわらず同じメッセージを返す
- 文字列マッチによるエラー判定は禁止

## 静的アセット分離ルール

- `<script>` タグ内にコードを直接書かない → `static/js/*.js` に切り出す
- `<style>` タグ内にスタイルを直接書かない → `static/css/*.css` に切り出す
- `<svg>` タグをテンプレートに直接書かない → `static/icons/*.svg` に切り出す
- テンプレートからは `<script src="/static/js/...">` や `<link rel="stylesheet" href="/static/css/...">` で参照
- **例外**: hyperscript `_="..."` 属性、htmx `hx-*` 属性

## UI インタラクション規約

- クラス付け替え・表示/非表示・モーダル開閉・タブ切り替え → hyperscript 属性で記述
- ページごとの ad-hoc な JavaScript を増やさない
- JavaScript を書くべきケース: 複数コンポーネント間で状態を共有する複雑な挙動、API 呼び出しなどロジックに集中する処理

## AI 連携規約

- **OPENAI_API_KEY** 環境変数で OpenAI API に接続する
- プロンプト定義は `prompts/ai_prompts.yaml` に外部化する（コード中にハードコードしない）
- テストでは `SYSDEN_TEST_MODE=1` でスタブ応答を返し、実 API を呼ばない
- 複数テーブル書き込みは途中失敗時にロールバックする（作成済みファイルを削除）

## テンプレートレスポンス

Starlette 1.x 以降の API を使う:

```python
templates.TemplateResponse(request, "template.html", {"key": "value"})
```

## テスト規約

### 開発フロー（テスト先行）

- 新機能追加・仕様変更では、**先にテストを書き、そのテストを通す実装を行う**
- テストがすべてグリーンになった時点でタスク完了とみなす
- **不具合を確認したとき**: 先に落ちる回帰テストを追加してから修正する
- リファクタリングでは先に既存挙動をテストで固定してからコードを変更する
- テストの優先順位:
  1. 代表的なユーザーフローは Playwright E2E
  2. HTML 構造・API のステータスコードは FastAPI `TestClient` 統合テスト
  3. ドメインロジック単体は pytest ユニットテスト

### テスト関数の命名規約

- テスト関数名は**何をテストしているかがわかる簡潔な日本語**で付ける
- 形式: `test_<日本語の動作説明>`（スネークケース・ローマ字ではなく日本語そのまま）
- クラス名は `Test<対象><カテゴリ>` の英語のまま

```python
# ✅ 良い例: 何をテストしているか一目でわかる
def test_テーブル名が空なら422を返す(client: TestClient) -> None: ...
def test_AI生成結果をTSVに保存する(mock_openai: None) -> None: ...
def test_存在しないテーブルの詳細は404(client: TestClient) -> None: ...
def test_マークダウンがHTMLに変換される() -> None: ...

# ❌ 悪い例: 英語で長くなり意図が読みにくい
def test_create_table_with_empty_name_returns_422(): ...
def test_ai_generated_result_is_saved_to_tsv(): ...
```

- parametrize と組み合わせる場合も日本語で:

```python
@pytest.mark.parametrize("name", ["", "123", "A-B", "a" * 65])
def test_不正なテーブル名は422を返す(client: TestClient, name: str) -> None: ...
```

### 共通規約

- **unittest より pytest を優先**: `unittest.mock.patch` / `MagicMock` ではなく `monkeypatch` / `pytest.fixture` を使う
- pytest fixture が適したところでは積極的に活用する（テストデータ、モック注入など）
- **`@pytest.mark.parametrize` を積極的に使う**: 入力パターンが 2 つ以上ある関数テストは parametrize で書く
- `uv run pytest tests/unit -q` は 60 秒以内に完了すること

### parametrize の使い方

同じアサーション構造で入力だけが異なるテストは個別関数にせず parametrize にまとめる:

```python
@pytest.mark.parametrize(
    ("input_type", "expected"),
    [
        ("VARCHAR", "文字列"),
        ("INTEGER", "整数"),
        ("BOOLEAN", "真偽値"),
        ("UNKNOWN", "UNKNOWN"),  # マッチしない場合はそのまま返す
    ],
)
def test_translate_type(input_type: str, expected: str) -> None:
    assert _translate_type(input_type) == expected
```

parametrize を使うべき典型的なケース:
- 複数の有効入力に対して同じ正常結果を期待する
- 複数の無効入力に対して同じエラー（ステータスコード / 例外）を期待する
- 境界値テスト（最小・最大・境界+1）
- 型変換・マッピングのテスト

### テスト時のロギング確認

- プロダクトコードが適切なログを出しているかをテストで検証する
- `caplog` fixture でログ出力をキャプチャし、期待するメッセージが記録されていることを確認する
- 特にエラーパスでは、LLM が調査しやすいログ（操作・入力値・結果がセットで記録されている）が出ることを検証する

```python
def test_AI生成失敗時にテーブル名をログ出力する(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        with pytest.raises(OpenAIError):
            generate_table_design("users", "テスト")

    assert "table=users" in caplog.text
```

### ユニットテスト（`tests/unit/`）

- AAA（Arrange-Act-Assert）スタイルで空行ブロック分けする
- 外部依存なし（ファイル I/O は `tmp_path` fixture で一時ディレクトリに隔離）
- ai_service のテストでは OpenAI SDK をモック（`monkeypatch` + スタブクライアント）する

```python
def test_write_and_read_tsv(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    rows = table_service.read_tsv("users")

    # Assert
    assert rows[0]["column_name"] == "id"
```

### インテグレーションテスト（`tests/integration/`）

- FastAPI `TestClient` + 一時データディレクトリ（`conftest.py` の `tmp_data_dir` fixture）
- Gherkin（Given-When-Then）スタイルで空行ブロック分けする

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

### E2E テスト（`tests/e2e/`）

#### スコープ・方針

- ルーターが配線済みの画面のみテスト対象とする
- BE 内部仕様の網羅性は不要。FE 部品の網羅性を重視する
- 新しい画面・ルーターを追加したら、対応する E2E テストファイルも追加する

#### スタイル

- **Gherkin (Given-When-Then)** コメントで各テストの意図を明示し、空行でブロック分けする
- クラスで論理グループ化: `Test<Page><Category>` (例: `TestIndexPageEmpty`, `TestCreateTableForm`)
- 関数名: `test_<日本語の動作説明>`（[テスト関数の命名規約](#テスト関数の命名規約)参照）
- ファイル: `test_<page_name>.py`（ページ単位）、`test_navigation.py`（ページ間遷移フロー）

#### AI モック

- `SYSDEN_TEST_MODE=1` 環境変数で `ai_service` をスタブ化する。実際の API は呼ばない
- サーバーは `tests/e2e/conftest.py` の session スコープ fixture でサブプロセス起動する

#### データ分離

- 各テスト前に `SYSDEN_DATA` 内の TSV を削除する autouse fixture `clean_data` でテスト間の独立性を保証する
- テスト前提条件は `create_table` fixture（httpx POST）で API 経由で作成する

#### FE 部品チェックリスト（各画面で網羅すること）

- 全 UI 要素の存在確認（ボタン、リンク、フォーム、入力欄、見出し）
- 空状態のメッセージ表示 / 非表示
- ボタン・リンクの属性（href, action, hx-* の結果）
- フォーム送信後の遷移先
- HTML バリデーション（required 属性）
- htmx インタラクション（hx-delete + hx-confirm、DOM 更新）
- ナビゲーションバーのリンク
- ページタイトル (`<title>`)

#### 実行コマンド

```bash
uv run task e2e                          # E2E のみ
uv run pytest tests/e2e -v --headed      # ブラウザ表示ありデバッグ
uv run task test                         # 全テスト（unit + integration + e2e）
```

## 画面追加手順

新しい画面を追加するとき、ルーター・テンプレート・E2E テストの 3 点セットを漏れなく作成する。

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
- 型アノテーション・docstring は本規約に従う

### 3. テンプレート作成

`templates/<page_name>.html` を作成する。

- `{% extends "base.html" %}` でベーステンプレートを継承する
- `{% block title %}` と `{% block content %}` を設定する
- [静的アセット分離ルール](#静的アセット分離ルール)に従う（インライン `<script>` / `<style>` 禁止）
- htmx / hyperscript の属性はインラインで OK

### 4. ルーターの登録

`app/main.py` にルーターを `include_router()` で登録する。

### 5. E2E テスト作成

`tests/e2e/test_<page_name>.py` を作成する。

[E2E テスト規約](#e2e-テストtestse2e)に従い、[FE 部品チェックリスト](#fe-部品チェックリスト各画面で網羅すること)の全項目を網羅する。

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

## 品質チェック手順

以下を順番に実行する:

1. **Ruff lint**: `uv run task lint`
2. **Ruff format check**: `uv run ruff format --check .`
3. **ty 型チェック**: `uv run task typecheck`
4. **ユニット + 統合テスト（カバレッジ付き）**: `uv run task test`

## コミット規約

Conventional Commits + 日本語:

```
<type>: <変更内容を動詞で始める日本語>

[body: 必要な場合のみ]
```

type の選択:
- `feat`: 新機能
- `fix`: バグ修正
- `chore`: ビルド・設定・依存関係・マイグレーション
- `docs`: ドキュメントのみ
- `refactor`: 機能変更なしのコード整理
- `test`: テストの追加・修正

## 応答言語

- **会話**: ユーザーとのやりとりは基本的に**日本語**で行う
- **説明・コメント**: コード外の説明、コミットメッセージも日本語で書く
- **コード**: 変数名・関数名・ファイル名はプロジェクトの既存規約に従う（英語のまま）
- ユーザーが英語で質問した場合は、返答も英語で行う
