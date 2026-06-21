# sysden 実装スキル

sysden のプロダクトコード（`app/` 配下）を追加・変更するときの規約。

## Python コーディング規約

- 型アノテーションを必ず付ける（引数・戻り値）。`Optional[X]` ではなく `X | None` を使う
- `except` 節で例外を再送出するときは `raise ... from err` または `raise ... from None` を使う
- テーブル名は `validate_table_name()` で検証する（`^[a-z][a-z0-9_]{0,63}$`）

## Python 3.14 モダン構文の積極活用

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
