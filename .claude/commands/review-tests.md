# /review-tests — テストコードレビュー

`tests/` 配下の変更差分を [docs/coding_rule.md のテスト規約](../docs/coding_rule.md#テスト規約) に照らしてレビューする。

## 手順

1. 変更差分を取得する:
   ```bash
   git diff --name-only | grep '^tests/'
   git diff -- tests/
   ```

2. 以下の観点で各ファイルをチェックし、違反があれば報告する:

### 命名
- [テスト関数の命名規約](../docs/coding_rule.md#テスト関数の命名規約): `test_<日本語の動作説明>` になっているか
- クラス名: `Test<対象><カテゴリ>` の英語

### 構造
- ユニットテスト: AAA（Arrange-Act-Assert）スタイルで空行ブロック分けされているか
- 統合・E2E テスト: Gherkin（Given-When-Then）コメントで意図が明示されているか
- `unittest.mock.patch` / `MagicMock` を使っていないか（`monkeypatch` / `pytest.fixture` を優先）

### parametrize
- 同じアサーション構造で入力だけ異なるテストが個別関数になっていないか
- `@pytest.mark.parametrize` にまとめるべき箇所がないか

### ロギング検証
- エラーパスで `caplog` を使ったログ出力の検証があるか

### E2E 固有
- [FE 部品チェックリスト](../docs/coding_rule.md#fe-部品チェックリスト各画面で網羅すること)の項目が網羅されているか
- データ分離: `clean_data` fixture でテスト間独立性が保たれているか
- AI モック: `SYSDEN_TEST_MODE=1` を使い実 API を呼んでいないか

## 出力フォーマット

違反ごとに以下を報告する:

- **ファイル**: パスと行番号
- **規約**: 違反した規約名
- **問題**: 何が問題か
- **修正案**: 具体的な修正コード

違反がなければ「✅ レビュー完了: 問題なし」と報告する。
