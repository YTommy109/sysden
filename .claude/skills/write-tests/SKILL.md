---
name: write-tests
description: テストコード（unit / integration / E2E）を追加・修正するときの規約
---

# sysden テストスキル

`tests/` 配下のテストコードを追加・修正するときの規約。

## 開発フロー（テスト先行）

- 新機能追加・仕様変更では、**先にテストを書き、そのテストを通す実装を行う**
- テストがすべてグリーンになった時点でタスク完了とみなす
- **不具合を確認したとき**: 先に落ちる回帰テストを追加してから修正する
- リファクタリングでは先に既存挙動をテストで固定してからコードを変更する
- テストの優先順位:
  1. 代表的なユーザーフローは Playwright E2E
  2. HTML 構造・API のステータスコードは FastAPI `TestClient` 統合テスト
  3. ドメインロジック単体は pytest ユニットテスト

## 作業フェーズ

テストコードの追加・修正は以下の順で行う:

1. **実装フェーズ**: テストを書いて通す（TDD）
2. **リファクタリングフェーズ**: テストが全て通った後に以下を確認する
   - `@pytest.mark.parametrize` を使うべき箇所がないか（同じロジックを複数入力で検証するテスト）
   - テストケースの網羅性は十分か（正常系・異常系・境界値が揃っているか）
   - parametrize に変換した場合、既存テストが壊れないことを確認する

## 共通規約

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

## ユニットテスト（`tests/unit/`）

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

## インテグレーションテスト（`tests/integration/`）

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

## E2E テスト（`tests/e2e/`）

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
