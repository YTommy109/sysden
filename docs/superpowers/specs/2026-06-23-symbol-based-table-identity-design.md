# テーブル内部シンボル方式

## 背景

現在の ER 図生成は、カラム名の `_id` サフィックスや description のテキストマッチで FK 関係を「推定」している。
英語の不規則な複数形（category → categories）や日本語表記の揺れに対応できず、関連線が描画されないケースが頻発する。

根本原因は、テーブルやカラムの識別が「言語表現（ファイル名・カラム名）」に依存していること。
設計のコアは人間向けの表現に捉われるべきではない。

## 方針

テーブルとカラムに言語非依存の内部シンボルを導入し、FK 関係をシンボルで定義する。
論理設計名（日本語）・物理設計名（英語）はシンボルからの変換として扱う。

## データモデル

### index.tsv（テーブルレジストリ）

```
symbol	logical_name	physical_name
TABLE_0001	商品種類	categories
TABLE_0002	商品	products
```

- `symbol` — 内部識別子。`TABLE_` + ゼロ埋め 4 桁連番
- `logical_name` — 論理設計での表示名（日本語）
- `physical_name` — 物理設計でのテーブル名（英語スネークケース）。ファイル名にも使用

### index.yaml（採番管理）

```yaml
next_table_id: 3
```

- テーブルシンボルの次の番号を管理する番兵
- テーブル作成後に `next_table_id += 生成テーブル数` で更新
- カラムシンボルはテーブル内で完結するため番兵不要（AI が COLUMN_0001 から採番）

### テーブル TSV（カラム定義）

ファイル名は `physical_name` を使用（例: `categories.tsv`）。

```
symbol	logical_name	physical_name	type	nullable	pk	unique	default	fk_target	description
COLUMN_0001	識別子	id	UUID	NO	YES	YES			
COLUMN_0002	種類名	name	VARCHAR(255)	NO	NO	YES			
```

FK を持つカラムの例:

```
COLUMN_0003	商品種類	category_id	UUID	NO	NO	NO		TABLE_0001	
```

- `symbol` — カラムの内部識別子。`COLUMN_` + ゼロ埋め 4 桁連番（テーブル内で採番）
- `logical_name` — 論理設計での表示名
- `physical_name` — 物理設計でのカラム名
- `fk_target` — 参照先テーブルのシンボル。FK でないカラムは空文字
- 既存の `column_name` 列は `physical_name` に置き換わる

### ER 図（index.mmd）

```
erDiagram
    TABLE_0001["商品種類"]
    TABLE_0002["商品"]
    TABLE_0001 ||--o{ TABLE_0002 : ""
```

- mermaid の `entity["Label"]` 構文でシンボルに表示名を付与
- リレーションは TSV の `fk_target` 列から機械的に生成（推定ロジック不要）
- 表示名は index.tsv の `logical_name` を使用
- 将来的に `physical_name` ビューへの切り替えも可能

## AI 生成フロー

### 新規テーブル作成

1. `index.yaml` から `next_table_id` を読む（例: 3）
2. AI に依頼テキスト + 「テーブルシンボルは TABLE_0003 から開始」を渡す
3. AI が複数テーブル生成の場合は TABLE_0003, TABLE_0004, ... と自動判断
4. AI はシンボル付きで TSV + markdown を返す:
   ```
   [TABLE_0003]
   symbol	logical_name	physical_name	type	nullable	pk	unique	default	fk_target	description
   COLUMN_0001	識別子	id	UUID	NO	YES	YES			
   COLUMN_0002	注文者	user_id	UUID	NO	NO	NO		TABLE_0001	
   ```
5. AI は markdown セクションも返す（従来通り `[TABLE_XXXX.md]` 形式）:
   ```
   [TABLE_0003.md]
   # 注文

   ## 概要

   注文情報を管理するテーブル。

   ## テーブル設計

   ![[orders.tsv]]
   ```
6. サーバーはパース結果のテーブル数を `len(tables)` で算出し、`next_table_id` を更新

### テーブル更新

1. 修正対象テーブルの現在の TSV（シンボル付き）をコンテキストとして AI に渡す
2. AI は既存シンボルを維持しつつ、新規カラムには次の番号を振る
3. 既存テーブルのシンボル一覧は不要 — 修正対象のデータ自体に全情報がある

### 物理設計生成

- 論理設計 TSV をそのまま AI に渡す（シンボル情報含む）
- 物理設計は `physical_name` ベースで SQL 型の具体化・DoA 生成を行う

## 表示レイヤー

### ER 図生成（`tables_to_er_diagram`）

- 現在の FK 推定ロジック（`_resolve_fk_target`）を廃止
- TSV の `fk_target` 列を読むだけで関係を確定
- 表示名は index.tsv の `logical_name` から取得

### テーブル詳細画面（`tsv_to_markdown`）

- 論理設計ビュー: `logical_name` 列をカラム名として表示
- 物理設計ビュー: `physical_name` 列をカラム名として表示
- `symbol` 列はユーザーに見せない（内部管理用）

論理設計ビュー:
```
カラム名 | 型    | ユニーク | 説明
商品名   | 文字列 | ○      |
```

### FK 表示

- FK カラムの判定は `fk_target` 列の有無で決定
- `_resolve_fk_target` 関数は削除

## 既存データの扱い

既存データ（categories, products, プロダクト）はクリアして新形式で作り直す。
マイグレーションスクリプトは作成しない。

## 変更対象ファイル

### 主要な変更

- `app/table_service.py` — TSV_HEADERS 更新、`_resolve_fk_target` 削除、ER 図生成ロジック書き換え、index.yaml 管理、シンボル採番
- `app/ai_service.py` — プロンプト更新（シンボル付き TSV フォーマット）、レスポンスパーサー更新
- `prompts/ai_prompts.yaml` — テーブル作成・更新プロンプトに fk_target 列とシンボル仕様を追加
- `app/routers/api.py` — テーブル作成後のシンボル採番・index.yaml 更新処理

### テンプレート

- `templates/table_detail.html` — 論理名表示に対応
- `templates/index.html` — ER 図のシンボルベース表示（変更不要の可能性あり — mermaid が alias を処理）

### テスト

- `tests/unit/test_table_service.py` — TSV_HEADERS、ER 図生成、FK 判定のテスト更新
- `tests/unit/test_ai_service.py` — パーサーのテスト更新

### データ

- `.data/` — 既存ファイルをクリアし、index.yaml を新規作成
