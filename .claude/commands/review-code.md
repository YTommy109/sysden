# /review-code — プロダクトコードレビュー

`app/`・`templates/`・`static/` 配下の変更差分を [docs/coding_rule.md](../docs/coding_rule.md) の規約に照らしてレビューする。

## 手順

1. 変更差分を取得する:
   ```bash
   git diff --name-only | grep -E '^(app|templates|static)/'
   git diff -- app/ templates/ static/
   ```

2. 以下の観点で各ファイルをチェックし、違反があれば報告する:

### Python コード（`app/`）
- [Python コーディング規約](../docs/coding_rule.md#python-コーディング規約): 型アノテーション、`X | None` 構文、`raise ... from`
- [Python 3.14 モダン構文](../docs/coding_rule.md#python-314-モダン構文の積極活用): match-case、f-string、walrus 演算子など
- [docstring・コメント規約](../docs/coding_rule.md#docstringコメント規約): 公開関数に Google スタイル docstring があるか
- [ロギング規約](../docs/coding_rule.md#ロギング規約): `logger = logging.getLogger(__name__)`、操作・識別子・結果が 1 行にまとまっているか
- [エラーハンドリング規約](../docs/coding_rule.md#エラーハンドリング規約): 例外の型でステータスコードを決定しているか、文字列マッチ禁止
- [AI 連携規約](../docs/coding_rule.md#ai-連携規約): プロンプト外部化、テストモード対応、ロールバック

### テンプレート（`templates/`）
- [静的アセット分離ルール](../docs/coding_rule.md#静的アセット分離ルール): インライン `<script>` / `<style>` / `<svg>` 禁止
- [UI インタラクション規約](../docs/coding_rule.md#ui-インタラクション規約): クラス付け替え等は hyperscript で
- [テンプレートレスポンス](../docs/coding_rule.md#テンプレートレスポンス): `TemplateResponse(request, ...)` 形式

## 出力フォーマット

違反ごとに以下を報告する:

- **ファイル**: パスと行番号
- **規約**: 違反した規約名
- **問題**: 何が問題か
- **修正案**: 具体的な修正コード

違反がなければ「✅ レビュー完了: 問題なし」と報告する。
