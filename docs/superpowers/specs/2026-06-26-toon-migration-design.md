# TOON フォーマット移行 + シンボル方式統合

## 概要

テーブル設計データの保存形式を TSV + markdown の複数ファイル構成から TOON（Token-Oriented Object Notation）単一ファイルに移行する。同時にシンボルベースのテーブル/カラム識別を導入し、ER 図の FK 関係を推定ロジックから機械的な生成に置き換える。

AI の役割をコア設計の生成に限定し、論理設計・物理設計・DoA バリデーション仕様は Python コードで導出する。

## 解決する問題

### ER 図のリレーション線が描画されない

`_resolve_fk_target()` がカラム名の `_id` サフィックスや description のテキストマッチで FK 関係を推定しており、不規則な複数形や日本語表記の揺れに対応できない。シンボル方式で `fk_target` に参照先テーブルのシンボルを明記し、機械的に ER 図を生成することで解決する。

### AI が生成する TSV の構造エラー

TSV は位置ベースのフォーマットで、タブ 1 つのずれで全列がシフトする。TOON の `{field1,field2,...}` ヘッダーと `[N]` 行数宣言により、LLM が自己参照できる構造的な出力フォーマットに置き換える。

### ファイル散在と変換コスト

テーブル 1 つにつき最大 5 ファイルが生成され、AI レスポンスのパースも正規表現によるセクション分割で脆い。1 テーブル = 1 `.toon` ファイルに統合し、TOON パーサーでレスポンスを処理する。

## 設計方針

### コア設計 → 論理設計 → 物理設計

```
ユーザーの依頼 → AI → コア設計(.toon)
                          │
                 Python で機械的に導出
                    ┌──────┼──────┐
                論理設計    物理設計   DoA
            （日本語表示） （PostgreSQL） （バリデーション）
```

- **AI の役割**: コア設計（`meta` + `columns` セクション）を TOON フォーマットで生成するのみ
- **論理設計**: コア設計から Python で導出。日本語カラム名、型名の日本語変換
- **物理設計**: コア設計から Python で導出。物理カラム名、SQL 型そのまま
- **DoA**: コア設計から Python で導出。SQL 型 → Python 型マッピング + バリデーションルール推定
- コア設計は画面に表示しない

### 導出結果の保存

論理設計・物理設計・DoA は同じ `.toon` ファイル内にセクションとして保存する。デバッグ用途であり、将来的にオンザフライ生成に移行する可能性がある。

## ファイル構成

```
.data/
├── index.yaml          # 採番カウンター（next_table_id のみ）
├── index.toon          # テーブル一覧 + 共通ルール + ER 図
├── products.toon       # テーブル定義（コア + 論理 + 物理 + DoA）
└── product_types.toon  # 同上
```

### `index.yaml`

```yaml
next_table_id: 3
```

`next_table_id` の採番カウンターのみを管理する。テーブル一覧やマッピングは `index.toon` に移動。

### `index.toon`

```toon
meta:
  description: テーブル設計インデックス

rules:
  - すべてのテーブルはサロゲートキーとして uuidv7 の id カラムを持つ
  - すべてのテーブルは created_at, updated_at, disabled_at を持つ

tables[2]{symbol,name,logical_name,description}:
  TABLE_0001,products,商品マスタ,EC サイトの商品情報を管理する
  TABLE_0002,product_types,商品種類,商品の分類を管理する

er_diagram:
  erDiagram
    TABLE_0002["商品種類"]
    TABLE_0001["商品"]
    TABLE_0002 ||--o{ TABLE_0001 : ""
```

- `tables` セクション: テーブル追加/削除時に自動更新
- `er_diagram` セクション: 全 `.toon` ファイルの `fk_target` から機械的に再生成
- `rules`: AI プロンプトに渡す共通ルール（自由テキスト）

### テーブル `.toon` ファイル

```toon
meta:
  symbol: TABLE_0001
  logical_name: 商品マスタ
  physical_name: products
  description: EC サイトの商品情報を管理するマスタテーブル

columns[4]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,商品ID,product_id,uuid,NO,YES,YES,gen_random_uuid(),,商品を一意に識別する
  COLUMN_0002,商品名,product_name,varchar(100),NO,NO,NO,,,商品の表示名
  COLUMN_0003,単価,unit_price,decimal(10.2),NO,NO,NO,,,税抜価格
  COLUMN_0004,カテゴリID,category_id,integer,NO,NO,NO,,TABLE_0002,カテゴリへの参照

logical[4]{カラム名,型,ユニーク,説明}:
  商品ID,UUID,,商品を一意に識別する
  商品名,文字列(100),,商品の表示名
  単価,固定小数点数(10.2),,税抜価格
  カテゴリID,整数,,カテゴリへの参照

physical[4]{column_name,type,nullable,pk,unique,default,description}:
  product_id,uuid,NO,YES,YES,gen_random_uuid(),商品を一意に識別する
  product_name,varchar(100),NO,NO,NO,,商品の表示名
  unit_price,decimal(10.2),NO,NO,NO,,税抜価格
  category_id,integer,NO,NO,NO,,カテゴリへの参照

doa[4]{column_name,python_type,required,min,max,max_length,description}:
  product_id,UUID,YES,,,,
  product_name,str,YES,,,100,
  unit_price,Decimal,YES,,,,
  category_id,int,YES,,,,
```

- **`columns`**: AI が生成するコア設計。single source of truth
- **`logical`**: コア設計から導出。型名を日本語変換、`logical_name` を使用
- **`physical`**: コア設計から導出。`physical_name` と SQL 型をそのまま使用
- **`doa`**: コア設計から導出。SQL 型 → Python 型マッピング + バリデーションルール推定

## シンボル方式

### テーブルシンボル

- `TABLE_XXXX` 形式（4桁ゼロ埋め）
- `index.yaml` の `next_table_id` で採番管理
- グローバルスコープ（全テーブルでユニーク）

### カラムシンボル

- `COLUMN_XXXX` 形式（4桁ゼロ埋め）
- テーブルスコープ（テーブルが異なれば同じシンボルでよい）
- 各テーブル内で `COLUMN_0001` から連番

### FK 関係

- `fk_target` フィールドに参照先テーブルのシンボル（`TABLE_XXXX`）を記述
- ER 図はシンボルから機械的に生成。推定ロジック `_resolve_fk_target()` は廃止

### プレースホルダ方式

AI にはシンボルを生成させない。処理フロー:

1. AI はカラムシンボルを `COLUMN_0001` から連番で付与（テーブルスコープなので衝突しない）
2. 既存テーブルへの FK は、プロンプトで渡されたシンボル一覧を使用
3. 同一リクエスト内の新規テーブル同士の参照には `NEW_1`, `NEW_2` 等のプレースホルダを使用
4. サーバー側で `next_table_id` からテーブルシンボルを割り当て
5. `fk_target` 内のプレースホルダを割り当て済みシンボルにリマップ

## モジュール構成

### `app/toon_io.py`（新規）

`.toon` ファイルの読み書きを担当する。`toon-python` ライブラリのラッパー。

```python
def read_toon(name: str) -> ToonDocument
def write_toon(name: str, doc: ToonDocument)
def read_index_toon() -> IndexDocument
def write_index_toon(doc: IndexDocument)
```

### `app/table_service.py`（書き換え）

テーブル CRUD と導出ロジックを担当する。

```python
# CRUD
def list_tables() -> list[TableSummary]
def get_table(name: str) -> ToonDocument
def save_table(name: str, doc: ToonDocument)
def delete_table(name: str)

# 導出
def derive_logical(columns: list[Column]) -> list[LogicalRow]
def derive_physical(columns: list[Column]) -> list[PhysicalRow]
def derive_doa(columns: list[Column]) -> list[DoaRow]
def derive_all(doc: ToonDocument) -> ToonDocument

# ER 図
def generate_er_diagram() -> str

# インデックス
def rebuild_index()
```

- `_resolve_fk_target()` は廃止
- 型変換マップ（SQL 型 → 日本語）は `derive_logical` で引き続き使用

### `app/ai_service.py`（書き換え）

AI 呼び出しとレスポンス処理を担当する。

```python
def create_table_design(prompt: str, rules: list[str], existing_tables: list[TableSummary]) -> list[CoreDesign]
def update_table_design(prompt: str, current: ToonDocument, rules: list[str], existing_tables: list[TableSummary]) -> CoreDesign
```

- AI には `rules`（共通ルール）と `existing_tables`（既存テーブルのシンボル一覧）を渡す
- AI は TOON フォーマットでコア設計（`meta` + `columns`）を返す
- レスポンスパースは `toon-python` で処理。正規表現パーサーは廃止

### `app/symbol_service.py`（新規）

シンボル採番とプレースホルダリマップを担当する。

```python
def allocate_table_symbol() -> str
def allocate_column_symbols(count: int) -> list[str]
def remap_placeholders(designs: list[CoreDesign]) -> list[CoreDesign]
```

- `index.yaml` の `next_table_id` を排他的に読み書き
- `remap_placeholders` は `fk_target` 内のプレースホルダも連動して置換

## AI プロンプト設計

### プロンプト構成

現行の3つのプロンプトを2つに再編する。

| プロンプト | 用途 |
|---|---|
| `core_create` | 新規テーブルのコア設計を生成（1つまたは複数） |
| `core_update` | 既存テーブルのコア設計を更新 |

`physical_design` プロンプトは廃止（物理設計は Python で導出するため）。

### AI への入力

- **system プロンプト**: TOON フォーマットの出力規則、カラムヘッダー仕様、シンボルの使い方
- **user メッセージ**: ユーザーの依頼 + 共通ルール + 既存テーブル一覧（シンボル付き）
- 更新モードでは現在のコア設計も含める

### AI レスポンス例（複数テーブル、相互参照）

```toon
meta:
  logical_name: 注文
  physical_name: orders
  description: 注文情報を管理するテーブル

columns[3]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,注文ID,order_id,uuid,NO,YES,YES,gen_random_uuid(),,
  COLUMN_0002,注文者,user_id,uuid,NO,NO,NO,,TABLE_0001,ユーザーへの参照
  COLUMN_0003,配送先,shipping_address_id,uuid,YES,NO,NO,,NEW_2,配送先への参照

meta:
  logical_name: 配送先
  physical_name: shipping_addresses
  description: 配送先住所を管理するテーブル

columns[2]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,配送先ID,shipping_address_id,uuid,NO,YES,YES,gen_random_uuid(),,
  COLUMN_0002,住所,address,varchar(500),NO,NO,NO,,,
```

### サーバー側の処理フロー

1. ユーザーが依頼を送信
2. `index.toon` から `rules` + `tables` を読み込み
3. AI に送信（`rules` + `existing_tables` + `prompt`）
4. AI レスポンスを `toon-python` でパース → `list[CoreDesign]`
5. `symbol_service.allocate_table_symbol()` でテーブルシンボル付与
6. `symbol_service.remap_placeholders()` で `NEW_X` → `TABLE_XXXX` に置換
7. `table_service.derive_all()` で論理/物理/DoA セクションを導出
8. `toon_io.write_toon()` で `.toon` ファイル保存
9. `table_service.rebuild_index()` でインデックス + ER 図更新

## ルーティング

| メソッド | パス | 変更 | 説明 |
|---|---|---|---|
| GET | `/` | 維持 | テーブル一覧 + ER 図 |
| GET | `/tables/{name}` | 変更 | 統合ページ（論理/物理/DoA タブ切り替え） |
| GET | `/tables/{name}/physical` | 廃止 | 統合ページに吸収 |
| POST | `/api/tables` | 変更 | テーブル作成（AI → コア → 導出 → 保存） |
| POST | `/api/tables/{name}` | 変更 | テーブル更新（同上） |
| POST | `/api/tables/{name}/physical` | 廃止 | 物理設計は自動導出 |
| DELETE | `/api/tables/{name}` | 維持 | テーブル削除 |
| POST | `/api/rebuild-index-tables` | 維持 | インデックス再構築 |
| POST | `/api/rebuild-er-diagram` | 維持 | ER 図再生成 |
| GET | `/api/sse/rebuild-index` | 維持 | SSE |
| GET | `/api/sse/rebuild-er` | 維持 | SSE |

## 画面設計

### テーブル一覧ページ（`/`）

データソースを `index.toon` に変更。表示ロジックはほぼ同じ。

### テーブル詳細ページ（`/tables/{name}`）

論理設計・物理設計・DoA を1ページでタブ切り替え表示する。

```
┌─────────────────────────────────────────┐
│ ← 戻る    商品マスタ (TABLE_0001)       │
├─────────────────────────────────────────┤
│  [論理設計]  [物理設計]  [DoA]           │
├─────────────────────────────────────────┤
│                                         │
│  （選択中のタブに応じた表を表示）          │
│                                         │
├─────────────────────────────────────────┤
│  更新依頼: [________________________]   │
│            [送信]                        │
└─────────────────────────────────────────┘
```

- タブ切り替えは `_hyperscript` で実装（サーバーリクエスト不要）
- 3つのタブのデータはページロード時にレンダリング済み
- `physical_detail.html` は廃止

### テンプレート変更

| ファイル | 変更 |
|---|---|
| `base.html` | 変更なし |
| `index.html` | データソースを `index.toon` に変更 |
| `table_detail.html` | 書き換え: タブ切り替え UI に統合 |
| `physical_detail.html` | 廃止 |

## 技術スタック変更

| 項目 | 現行 | 移行後 |
|---|---|---|
| データ形式 | TSV + markdown | TOON（`.toon`） |
| TOON パーサー | — | `toon-python`（PyPI） |
| AI レスポンスパース | 正規表現セクション分割 | `toon-python` |
| FK 推定 | `_resolve_fk_target()`（ヒューリスティック） | `fk_target` シンボル（機械的） |
| 物理設計生成 | AI（`physical_design` プロンプト） | Python 導出 |
| ファイル数/テーブル | 最大 5（TSV×2 + md×2 + DoA TSV） | 1（`.toon`） |

## テスト方針

| モジュール | テスト種別 | 重点 |
|---|---|---|
| `toon_io.py` | unit | 読み書きラウンドトリップ、パース失敗時のエラー |
| `symbol_service.py` | unit | 採番の連番性、プレースホルダリマップの正確性 |
| `table_service.py` | unit + integration | 導出ロジックの変換正確性、ER 図生成、インデックス再構築 |
| `ai_service.py` | unit | TOON レスポンスのパース、テストモードのスタブ更新 |
| `routers/` | integration | エンドポイントの動作確認 |

### 導出ロジックのテスト重点

- 型変換: `uuid` → `UUID`、`varchar(100)` → `文字列(100)`、`decimal(10,2)` → `固定小数点数(10,2)` 等
- 共通カラム: `id`, `created_at`, `updated_at`, `disabled_at` の正しい導出
- FK カラム: `fk_target` ありのカラムの適切な表示
- DoA 型マッピング: SQL 型 → Python 型（`uuid` → `UUID`、`varchar` → `str`、`integer` → `int`）
- DoA バリデーション推定: `varchar(100)` → `max_length=100`

カバレッジ 80% 以上を維持する。

## 既存データの移行

既存の `.data/` 配下ファイル（2テーブル分の TSV + md + index ファイル群）はクリアし、TOON 移行後のコードでサンプルデータを新規生成する。

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `app/toon_io.py` | 新規: TOON ファイル I/O |
| `app/symbol_service.py` | 新規: シンボル採番・リマップ |
| `app/table_service.py` | 書き換え: TOON ベースの CRUD + 導出ロジック |
| `app/ai_service.py` | 書き換え: TOON プロンプト + パース |
| `app/routers/html.py` | 変更: 統合ページ対応、物理設計ルート廃止 |
| `app/routers/api.py` | 変更: TOON ベースの作成/更新フロー、物理設計 API 廃止 |
| `prompts/ai_prompts.yaml` | 書き換え: `core_create` / `core_update` に再編 |
| `templates/table_detail.html` | 書き換え: タブ切り替え UI |
| `templates/index.html` | 変更: データソースを `index.toon` に |
| `templates/physical_detail.html` | 廃止 |
| `pyproject.toml` | 依存追加: `toon-python` |
| `tests/` | 書き換え: TOON 対応 |
| `.data/` | クリア＋再生成 |
