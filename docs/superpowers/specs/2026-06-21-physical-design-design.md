# 物理設計表示機能

## 概要

論理設計（markdown + TSV）を入力として AI が物理設計を生成し、独立ページで表示する機能。
物理設計は「テーブル定義」と「DoA バリデーション仕様」の2つの TSV で構成される。

## ファイル構成

```
.data/
├── {name}.md                      # 論理設計 markdown（既存）
├── {name}.tsv                     # 論理設計 TSV（既存）
├── physical_{name}.md             # 物理設計 markdown（レイアウト定義）
├── physical_{name}.tsv            # 物理テーブル定義 TSV
├── physical_{name}_doa.tsv        # DoA バリデーション TSV
├── index.tsv / index.mmd          # 既存（変更なし）
├── index.md                       # 共通ルール（任意、存在すれば物理設計生成時に参照）
```

- `list_tables()` のグロブから `physical_*` プレフィックスを除外する
- 物理設計の存在判定: `physical_{name}.tsv` の有無

## TSV カラム構成

### 物理テーブル定義 TSV（論理設計と同じ7列）

| 列名 | 説明 |
|---|---|
| column_name | 物理カラム名（英語スネークケース） |
| type | SQL 型（uuid, varchar(255), timestamptz など） |
| nullable | NO / YES |
| pk | YES / NO |
| unique | YES / NO |
| default | デフォルト値（gen_random_uuid(), now() など） |
| description | 説明 |

### DoA バリデーション TSV

| 列名 | 説明 |
|---|---|
| column_name | 物理カラム名 |
| python_type | Python 型（UUID, str, int, Decimal, date など） |
| required | YES / NO |
| min | 最小値（数値型のみ） |
| max | 最大値（数値型のみ） |
| max_length | 最大文字長（文字列型のみ） |
| description | その他のバリデーションルール（テキスト記述） |

## ルーティング

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/tables/{name}/physical` | 物理設計ページ表示 |
| POST | `/api/tables/{name}/physical` | 物理設計の生成（AI 呼び出し） |

## ページ構成

### URL

`/tables/{name}/physical`

### 論理設計ページからのナビゲーション

テーブル詳細ページ（`/tables/{name}`）のヘッダー付近に物理設計ページへのアイコンリンクを常時表示する。

### 未生成時

- 「まだ物理設計がありません。」メッセージ
- 「物理設計を生成」ボタン（リフレッシュアイコン付き）

### 生成済み

- ヘッダー: 戻りリンク（← 論理設計ページへ）+ テーブル表示名 + 「物理設計」ラベル + 再生成ボタン
- 本体: `physical_{name}.md` をレンダリング
  - markdown 内の `![[physical_{name}.tsv]]` がテーブル定義として展開
  - markdown 内の `![[physical_{name}_doa.tsv]]` が DoA 仕様として展開

## 生成フロー

1. ユーザーが「生成」または「再生成」ボタンを押下
2. `POST /api/tables/{name}/physical` にリクエスト
3. サーバーが以下を読み取り AI に渡す:
   - `{name}.md`（論理設計 markdown）
   - `{name}.tsv`（論理設計 TSV）
   - `index.md`（共通ルール、存在する場合のみ）
4. AI が3ファイルを生成:
   - `physical_{name}.md`
   - `physical_{name}.tsv`
   - `physical_{name}_doa.tsv`
5. ファイル保存
6. `/tables/{name}/physical` にリダイレクト

## テンプレート

新規テンプレート `templates/physical_detail.html` を追加する。

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `app/table_service.py` | `list_tables()` で `physical_*` を除外、物理設計の読み書き関数追加 |
| `app/routers/html.py` | `GET /tables/{name}/physical` エンドポイント追加 |
| `app/routers/api.py` | `POST /api/tables/{name}/physical` エンドポイント追加 |
| `app/ai_service.py` | 物理設計生成用のプロンプト・関数追加 |
| `templates/table_detail.html` | 物理設計ページへのリンク追加 |
| `templates/physical_detail.html` | 新規：物理設計ページテンプレート |
