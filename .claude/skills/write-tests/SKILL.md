---
name: write-tests
description: テストコード（unit / integration / E2E）を追加・修正するときの規約
---

# sysden テストスキル

`tests/` 配下のテストコードを追加・修正するときに使う。

## 規約

[docs/coding_rule.md のテスト規約](../../../docs/coding_rule.md#テスト規約)をすべて遵守すること。

主要な規約:

- テスト先行（TDD）で開発する
- テスト関数名は日本語で付ける（`test_<日本語の動作説明>`）
- unittest より pytest を優先（`monkeypatch` / `pytest.fixture`）
- `@pytest.mark.parametrize` を積極的に使う
- ユニットテストは AAA スタイル、統合・E2E テストは Gherkin スタイル
- `caplog` でプロダクトコードのログ出力を検証する

## 作業フェーズ

テストコードの追加・修正は以下の順で行う:

1. **実装フェーズ**: テストを書いて通す（TDD）
2. **リファクタリングフェーズ**: テストが全て通った後に以下を確認する
   - `@pytest.mark.parametrize` を使うべき箇所がないか（同じロジックを複数入力で検証するテスト）
   - テストケースの網羅性は十分か（正常系・異常系・境界値が揃っているか）
   - parametrize に変換した場合、既存テストが壊れないことを確認する
