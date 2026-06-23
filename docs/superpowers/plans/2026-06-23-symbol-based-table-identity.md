# テーブル内部シンボル方式 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** テーブル・カラムに言語非依存の内部シンボルを導入し、FK 関係をシンボルで定義することで ER 図の関連線の描画を確実にする。

**Architecture:** index.yaml で採番管理、各テーブル TSV にシンボル・論理名・物理名・fk_target 列を追加、ER 図はシンボル + mermaid alias で生成。AI プロンプトをシンボル付きフォーマットに更新し、既存の FK 推定ロジックを廃止する。

**Tech Stack:** Python 3.14+ / FastAPI / Jinja2 / PyYAML（既に依存済み） / mermaid.js

## Global Constraints

- 行長 100 文字以内（Ruff 強制）
- 認知的複雑度 ≤ 10（Ruff C901）
- `print()` 禁止（ログは `logging` を使用）
- テストカバレッジ 80% 以上
- コミットメッセージは Conventional Commits + 日本語
- テストは日本語関数名（`test_テーブルが空なら...` 形式）

---

### Task 1: index.yaml の読み書きとシンボル採番

**Files:**
- Modify: `app/table_service.py` — index.yaml 管理関数を追加
- Test: `tests/unit/test_table_service.py` — index.yaml テスト追加

**Interfaces:**
- Produces:
  - `read_next_table_id() -> int` — index.yaml から次のテーブル ID を読む。ファイルが存在しなければ `1` を返す
  - `save_next_table_id(next_id: int) -> None` — index.yaml に次のテーブル ID を書き込む
  - `allocate_table_symbols(count: int) -> list[str]` — count 個のシンボル（`TABLE_0001` 等）を採番し、index.yaml を更新して返す

- [ ] **Step 1: テスト作成 — index.yaml が存在しない場合に 1 を返す**

```python
def test_indexYAMLが存在しなければ次のテーブルIDは1() -> None:
    # Arrange — 空のデータディレクトリ（conftest が tmp_path を設定済み）

    # Act
    result = table_service.read_next_table_id()

    # Assert
    assert result == 1
```

- [ ] **Step 2: テスト実行 — FAIL を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_indexYAMLが存在しなければ次のテーブルIDは1 -v`
Expected: FAIL — `read_next_table_id` が未定義

- [ ] **Step 3: 実装 — read_next_table_id と save_next_table_id**

`app/table_service.py` の先頭に `import yaml` を追加し、以下を追加:

```python
def read_next_table_id() -> int:
    """index.yaml から次のテーブル ID を読む。ファイルがなければ 1。"""
    path = get_data_dir() / "index.yaml"
    if not path.exists():
        return 1
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("next_table_id", 1)


def save_next_table_id(next_id: int) -> None:
    """index.yaml に次のテーブル ID を書き込む。"""
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "index.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump({"next_table_id": next_id}, f)
```

- [ ] **Step 4: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_indexYAMLが存在しなければ次のテーブルIDは1 -v`
Expected: PASS

- [ ] **Step 5: テスト追加 — save して read のラウンドトリップ**

```python
def test_nextTableIdの保存と読み込み() -> None:
    # Arrange
    table_service.save_next_table_id(5)

    # Act
    result = table_service.read_next_table_id()

    # Assert
    assert result == 5
```

- [ ] **Step 6: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_nextTableIdの保存と読み込み -v`
Expected: PASS

- [ ] **Step 7: テスト追加 — allocate_table_symbols**

```python
def test_テーブルシンボルの採番() -> None:
    # Arrange — 初期状態（next_table_id = 1）

    # Act
    symbols = table_service.allocate_table_symbols(3)

    # Assert
    assert symbols == ["TABLE_0001", "TABLE_0002", "TABLE_0003"]
    assert table_service.read_next_table_id() == 4


def test_テーブルシンボルの連続採番() -> None:
    # Arrange — 既に 2 まで採番済み
    table_service.save_next_table_id(3)

    # Act
    symbols = table_service.allocate_table_symbols(2)

    # Assert
    assert symbols == ["TABLE_0003", "TABLE_0004"]
    assert table_service.read_next_table_id() == 5
```

- [ ] **Step 8: テスト実行 — FAIL を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_テーブルシンボルの採番 tests/unit/test_table_service.py::test_テーブルシンボルの連続採番 -v`
Expected: FAIL — `allocate_table_symbols` が未定義

- [ ] **Step 9: 実装 — allocate_table_symbols**

```python
def allocate_table_symbols(count: int) -> list[str]:
    """count 個のテーブルシンボルを採番し、index.yaml を更新して返す。"""
    start = read_next_table_id()
    symbols = [f"TABLE_{start + i:04d}" for i in range(count)]
    save_next_table_id(start + count)
    return symbols
```

- [ ] **Step 10: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_テーブルシンボルの採番 tests/unit/test_table_service.py::test_テーブルシンボルの連続採番 -v`
Expected: PASS

- [ ] **Step 11: コミット**

```bash
git add app/table_service.py tests/unit/test_table_service.py
git commit -m "feat: index.yaml によるテーブルシンボル採番を追加する"
```

---

### Task 2: TSV ヘッダーとサンプルデータの新フォーマット対応

**Files:**
- Modify: `app/table_service.py:9` — `TSV_HEADERS` 定数更新
- Modify: `tests/conftest.py:6-9` — `SAMPLE_TSV` 更新
- Test: `tests/unit/test_table_service.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `TSV_HEADERS = ["symbol", "logical_name", "physical_name", "type", "nullable", "pk", "unique", "default", "fk_target", "description"]`

- [ ] **Step 1: conftest.py の SAMPLE_TSV を新フォーマットに更新**

```python
SAMPLE_TSV = (
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
)
```

- [ ] **Step 2: TSV_HEADERS を更新**

`app/table_service.py:9` を変更:

```python
TSV_HEADERS = [
    "symbol", "logical_name", "physical_name", "type",
    "nullable", "pk", "unique", "default", "fk_target", "description",
]
```

- [ ] **Step 3: 既存テストを新フォーマットに合わせて修正**

以下のテストのアサーションを更新:

- `test_TSVの書き込みと読み込み`: `rows[0]["column_name"]` → `rows[0]["physical_name"]`、`"id"` のまま
- `test_TSVを生文字列で読み込む`: `"column_name\t"` → `"symbol\t"`、`"id\tUUID"` → `"COLUMN_0001\t"` に変更
- FK 関連テスト（`test_FK関係がER図に含まれる` 等）の TSV リテラルを新フォーマットに更新 — これは Task 4 で対応するため、ここでは skip しない

まず `test_TSVの書き込みと読み込み` を修正:

```python
def test_TSVの書き込みと読み込み(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    rows = table_service.read_tsv("users")

    # Assert
    assert rows[0]["physical_name"] == "id"
    assert rows[0]["type"] == "UUID"
    assert rows[0]["symbol"] == "COLUMN_0001"
```

`test_TSVを生文字列で読み込む` を修正:

```python
def test_TSVを生文字列で読み込む(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    content = table_service.read_tsv_raw("users")

    # Assert
    assert "symbol\t" in content
    assert "COLUMN_0001\t" in content
```

- [ ] **Step 4: テスト実行 — 影響範囲の確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_TSVの書き込みと読み込み tests/unit/test_table_service.py::test_TSVを生文字列で読み込む -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add app/table_service.py tests/conftest.py tests/unit/test_table_service.py
git commit -m "feat: TSV ヘッダーをシンボル付き新フォーマットに更新する"
```

---

### Task 3: index.tsv の新フォーマット対応

**Files:**
- Modify: `app/table_service.py` — `rebuild_index_tables`, `read_index_tables` を更新
- Test: `tests/unit/test_table_service.py`

**Interfaces:**
- Consumes: `allocate_table_symbols(count) -> list[str]` (Task 1)、`read_next_table_id() -> int` (Task 1)
- Produces:
  - `rebuild_index_tables() -> None` — index.tsv を `symbol\tlogical_name\tphysical_name` 形式で再生成
  - `read_index_tables() -> list[dict[str, str]]` — `symbol`, `logical_name`, `physical_name` の辞書リスト
  - `get_table_symbol(physical_name: str) -> str | None` — physical_name からシンボルを逆引き
  - `get_symbol_display_map() -> dict[str, str]` — シンボル→論理名のマップ

- [ ] **Step 1: テスト作成 — 新フォーマットの index.tsv 生成**

```python
def test_インデックス再構築でシンボル付きTSVが生成される(sample_tsv: str) -> None:
    # Arrange — シンボルを採番してテーブルを作成
    symbols = table_service.allocate_table_symbols(1)
    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # Act
    table_service.rebuild_index_tables()

    # Assert
    tables = table_service.read_index_tables()
    assert len(tables) == 1
    assert tables[0]["symbol"] == "TABLE_0001"
    assert tables[0]["logical_name"] == "ユーザー"
    assert tables[0]["physical_name"] == "users"
```

- [ ] **Step 2: テスト実行 — FAIL を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_インデックス再構築でシンボル付きTSVが生成される -v`
Expected: FAIL

- [ ] **Step 3: 実装 — rebuild_index_tables を更新**

index.tsv にシンボル情報を含めるには、物理名→シンボルの対応が必要。これを保持するために index.yaml にマッピングを追加する。

`app/table_service.py` の `save_next_table_id` と `read_next_table_id` を拡張して、`index.yaml` にテーブルマッピングも保持するようにする:

```python
def _read_index_yaml() -> dict:
    """index.yaml を読み込む。ファイルがなければ空辞書。"""
    path = get_data_dir() / "index.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_index_yaml(data: dict) -> None:
    """index.yaml を書き込む。"""
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "index.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)


def read_next_table_id() -> int:
    return _read_index_yaml().get("next_table_id", 1)


def save_next_table_id(next_id: int) -> None:
    data = _read_index_yaml()
    data["next_table_id"] = next_id
    _save_index_yaml(data)


def register_table(symbol: str, physical_name: str) -> None:
    """テーブルのシンボル→物理名の対応を index.yaml に登録する。"""
    data = _read_index_yaml()
    tables = data.setdefault("tables", {})
    tables[symbol] = physical_name
    _save_index_yaml(data)


def unregister_table(physical_name: str) -> None:
    """テーブルの登録を index.yaml から削除する。"""
    data = _read_index_yaml()
    tables = data.get("tables", {})
    to_remove = [s for s, p in tables.items() if p == physical_name]
    for s in to_remove:
        del tables[s]
    _save_index_yaml(data)


def get_table_symbol(physical_name: str) -> str | None:
    """physical_name からシンボルを逆引きする。"""
    tables = _read_index_yaml().get("tables", {})
    for symbol, pname in tables.items():
        if pname == physical_name:
            return symbol
    return None


def get_symbol_display_map() -> dict[str, str]:
    """シンボル→論理名（表示名）のマップを返す。"""
    tables = _read_index_yaml().get("tables", {})
    return {
        symbol: read_table_display_name(pname)
        for symbol, pname in tables.items()
    }
```

`rebuild_index_tables` を更新:

```python
def rebuild_index_tables() -> None:
    """テーブル一覧 (index.tsv) を再生成する。"""
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    names = list_tables()
    lines = ["symbol\tlogical_name\tphysical_name"]
    for name in names:
        symbol = get_table_symbol(name)
        if symbol is None:
            continue
        display_name = read_table_display_name(name)
        lines.append(f"{symbol}\t{display_name}\t{name}")
    (d / f"{_INDEX_STEM}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
```

`read_index_tables` を更新:

```python
def read_index_tables() -> list[dict[str, str]]:
    path = get_data_dir() / f"{_INDEX_STEM}.tsv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [
            {
                "symbol": row["symbol"],
                "logical_name": row["logical_name"],
                "physical_name": row["physical_name"],
            }
            for row in reader
        ]
```

- [ ] **Step 4: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_インデックス再構築でシンボル付きTSVが生成される -v`
Expected: PASS

- [ ] **Step 5: 既存テストを新フォーマットに修正**

以下のテストで `name` → `physical_name`、`display_name` → `logical_name` に更新し、テーブル登録（`register_table`）を追加:

- `test_インデックスからテーブル一覧を読み込む`: `register_table` 呼び出しを追加、辞書キー更新
- `test_テーブル一覧に表示名が含まれる`: 同上
- `test_Markdownなしの表示名はファイル名`: 同上
- `test_インデックス再構築でファイルが生成される`: `register_table` 追加
- `test_テーブルなしでもインデックスファイルが生成される`: 変更不要（テーブルなし）
- `test_テーブル一覧再構築でTSVが生成される`: `register_table` 追加、辞書キー更新

例（`test_インデックスからテーブル一覧を読み込む`）:

```python
def test_インデックスからテーブル一覧を読み込む(sample_tsv: str) -> None:
    # Arrange
    table_service.register_table("TABLE_0001", "orders")
    table_service.register_table("TABLE_0002", "users")
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.read_index_tables()

    # Assert — symbol, logical_name, physical_name を含む辞書のリスト
    assert len(result) == 2
    assert result[0]["physical_name"] == "orders"
    assert result[0]["symbol"] == "TABLE_0001"
    assert result[1]["physical_name"] == "users"
    assert result[1]["symbol"] == "TABLE_0002"
```

- [ ] **Step 6: テスト実行 — 全テスト PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py -v`
Expected: 全テスト PASS（FK 関連テストは Task 4 で更新するため一時的に FAIL 可）

- [ ] **Step 7: コミット**

```bash
git add app/table_service.py tests/unit/test_table_service.py
git commit -m "feat: index.tsv をシンボル付き新フォーマットに対応する"
```

---

### Task 4: ER 図生成のシンボルベース化

**Files:**
- Modify: `app/table_service.py` — `tables_to_er_diagram` 書き換え、`_resolve_fk_target` と `_build_display_name_map` 削除
- Test: `tests/unit/test_table_service.py` — FK 関連テスト全面更新

**Interfaces:**
- Consumes: `get_table_symbol(physical_name) -> str | None` (Task 3)、`get_symbol_display_map() -> dict[str, str]` (Task 3)
- Produces:
  - `tables_to_er_diagram() -> str` — シンボル + mermaid alias 形式の ER 図テキスト

- [ ] **Step 1: テスト作成 — fk_target 列による FK 関係検出**

```python
def test_fk_target列でER図にリレーションが含まれる() -> None:
    # Arrange — products.category_id が TABLE_0001 を参照する
    categories_tsv = (
        "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
        "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t\n"
    )
    products_tsv = (
        "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
        "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t\n"
        "COLUMN_0002\t商品種類\tcategory_id\tUUID\tNO\tNO\tNO\t\tTABLE_0001\t\n"
    )
    table_service.register_table("TABLE_0001", "categories")
    table_service.register_table("TABLE_0002", "products")
    table_service.write_tsv("categories", categories_tsv)
    table_service.write_tsv("products", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — シンボル + alias 形式で出力、リレーション線がある
    assert 'TABLE_0001["' in result
    assert 'TABLE_0002["' in result
    assert "TABLE_0001 ||--o{ TABLE_0002" in result
```

- [ ] **Step 2: テスト実行 — FAIL を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_fk_target列でER図にリレーションが含まれる -v`
Expected: FAIL

- [ ] **Step 3: 実装 — tables_to_er_diagram を書き換え**

`_resolve_fk_target` と `_build_display_name_map` を削除し、`tables_to_er_diagram` を以下に置き換え:

```python
def tables_to_er_diagram() -> str:
    """全テーブルの mermaid erDiagram テキストを生成する。

    TSV の fk_target 列からリレーション線を描く。
    シンボル + mermaid alias 構文で表示名を付与する。
    """
    names = list_tables()
    if not names:
        return ""

    display_map = get_symbol_display_map()
    lines = ["erDiagram"]
    relations: list[str] = []

    for name in names:
        symbol = get_table_symbol(name)
        if symbol is None:
            continue
        try:
            rows = read_tsv(name)
        except FileNotFoundError:
            continue
        for row in rows:
            target = row.get("fk_target", "")
            if not target:
                continue
            nullable = row.get("nullable", "NO").upper() == "YES"
            arrow = "|o--o{" if nullable else "||--o{"
            relations.append(f'    {target} {arrow} {symbol} : ""')

    for name in names:
        symbol = get_table_symbol(name)
        if symbol is None:
            continue
        label = display_map.get(symbol, name)
        lines.append(f'    {symbol}["{label}"]')

    lines.extend(relations)
    return "\n".join(lines)
```

- [ ] **Step 4: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_fk_target列でER図にリレーションが含まれる -v`
Expected: PASS

- [ ] **Step 5: テスト追加 — nullable FK でオプショナル線**

```python
def test_nullableなfk_targetはオプショナル線になる() -> None:
    # Arrange
    categories_tsv = (
        "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
        "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t\n"
    )
    products_tsv = (
        "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
        "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t\n"
        "COLUMN_0002\t商品種類\tcategory_id\tUUID\tYES\tNO\tNO\t\tTABLE_0001\t\n"
    )
    table_service.register_table("TABLE_0001", "categories")
    table_service.register_table("TABLE_0002", "products")
    table_service.write_tsv("categories", categories_tsv)
    table_service.write_tsv("products", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert "|o--o{" in result
```

- [ ] **Step 6: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py::test_nullableなfk_targetはオプショナル線になる -v`
Expected: PASS

- [ ] **Step 7: 旧 FK 推定テストを削除・更新**

以下のテストを **削除**（FK 推定ロジックを廃止するため）:

- `test_FK関係がER図に含まれる`
- `test_nullableなFKはオプショナル線になる`
- `test_参照先テーブルがなければリレーション線なし`
- `test_単数形テーブル名でFK一致`
- `test_descriptionのテーブル参照でFK検出`
- `test_表示名経由のテーブル参照でFK検出`
- `test_descriptionの参照先がなければリレーション線なし`
- `test_idサフィックスがdescription参照より優先`

以下のテストを新フォーマットに **更新**:

- `test_テーブルなしでER図は空文字列` — 変更不要
- `test_単一テーブルのER図`: `register_table` 追加、シンボルのアサーション
- `test_複数テーブルのER図`: 同上

```python
def test_単一テーブルのER図(sample_tsv: str) -> None:
    # Arrange
    table_service.register_table("TABLE_0001", "users")
    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert result.startswith("erDiagram")
    assert 'TABLE_0001["ユーザー"]' in result
```

- [ ] **Step 8: tsv_to_markdown の FK 判定を fk_target 列ベースに変更**

`app/table_service.py` の `tsv_to_markdown` 関数内の FK 判定を変更:

```python
# 変更前
is_fk = _resolve_fk_target(col_name, table_names, description, dn_map) is not None

# 変更後
is_fk = bool(row.get("fk_target", ""))
```

この変更で `table_names`、`dn_map` のセットアップも不要になるので、関数冒頭の `table_names = set(list_tables())` と `dn_map = _build_display_name_map(table_names)` も削除。

また、`tsv_to_markdown` で `col_name` を `row.get("column_name", "")` から取得している箇所を `row.get("logical_name", row.get("physical_name", ""))` に変更し、論理名を優先表示にする:

```python
col_name = row.get("logical_name") or row.get("physical_name", "")
```

FK テストも更新:

```python
def test_FKカラムにfkクラスが付く() -> None:
    # Arrange — fk_target 列でFK判定
    rows = [
        {
            "symbol": "COLUMN_0001",
            "logical_name": "注文者",
            "physical_name": "user_id",
            "type": "UUID",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "fk_target": "TABLE_0001",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — FK カラム名（論理名）が fk クラスの span で囲まれる
    assert '<span class="fk">注文者</span>' in md


def test_非FKカラムにfkクラスは付かない() -> None:
    # Arrange — fk_target が空
    rows = [
        {
            "symbol": "COLUMN_0001",
            "logical_name": "ユーザー名",
            "physical_name": "name",
            "type": "VARCHAR(100)",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "fk_target": "",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — fk クラスは付かない
    assert "fk" not in md
```

- [ ] **Step 9: 残りの tsv_to_markdown テストを新フォーマットに更新**

全テストの行辞書に `symbol`、`logical_name`、`physical_name`、`fk_target` を追加。`column_name` キーを削除して `physical_name` に置き換え。表示名アサーションを `logical_name` ベースに変更。

対象テスト:
- `test_TSVをMarkdownテーブルに変換する`
- `test_必須カラムの型に必須マークが付く`
- `test_PKカラム名が太字になる`
- `test_説明にデフォルトプレフィックスが付かない`

例（`test_TSVをMarkdownテーブルに変換する`）:

```python
def test_TSVをMarkdownテーブルに変換する() -> None:
    # Arrange
    rows = [
        {
            "symbol": "COLUMN_0001",
            "logical_name": "識別子",
            "physical_name": "id",
            "type": "UUID",
            "nullable": "NO",
            "pk": "YES",
            "unique": "YES",
            "default": "",
            "fk_target": "",
            "description": "主キー",
        }
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — 日本語ヘッダー、PK 太字（論理名）、必須は型に * プレフィックス
    assert "| カラム名 |" in md
    assert "| **識別子** |" in md
    assert '| <span class="required">*</span> UUID |' in md
```

- [ ] **Step 10: テスト実行 — 全テスト PASS を確認**

Run: `uv run task test -- tests/unit/test_table_service.py -v`
Expected: 全テスト PASS

- [ ] **Step 11: `_resolve_fk_target` と `_build_display_name_map` を削除**

`app/table_service.py` から以下を削除:
- `_build_display_name_map` 関数（行 424-431）
- `_resolve_fk_target` 関数（行 434-470）

- [ ] **Step 12: テスト実行 + lint — 全チェック PASS を確認**

Run: `uv run task test && uv run task lint`
Expected: 全 PASS

- [ ] **Step 13: コミット**

```bash
git add app/table_service.py tests/unit/test_table_service.py
git commit -m "feat: ER 図生成をシンボルベースに書き換え、FK 推定ロジックを廃止する"
```

---

### Task 5: AI プロンプトとパーサーの更新

**Files:**
- Modify: `prompts/ai_prompts.yaml` — プロンプト全面更新
- Modify: `app/ai_service.py` — パーサー更新、スタブ更新
- Test: `tests/unit/test_ai_service.py` — テスト更新

**Interfaces:**
- Consumes: `allocate_table_symbols(count) -> list[str]` (Task 1)、`read_next_table_id() -> int` (Task 1)
- Produces:
  - `create_table_design(prompt, next_table_id) -> list[tuple[str, str, str, str]]` — `(symbol, physical_name, tsv, md)` のリスト
  - `generate_table_design(prompt, current_tsv, table_symbol) -> str` — 更新された TSV を返す
  - `_parse_multi_table_response(content) -> list[tuple[str, str, str]]` — `[TABLE_XXXX]` セクション形式に対応

- [ ] **Step 1: テスト作成 — 新フォーマットのパーサー**

`tests/unit/test_ai_service.py` のレスポンス定数を更新:

```python
MULTI_TABLE_RESPONSE = (
    "[TABLE_0001]\n"
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
    "\n"
    "[TABLE_0001.md]\n"
    "# ユーザー\n"
    "\n"
    "ユーザー情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[users.tsv]]\n"
    "\n"
    "[TABLE_0002]\n"
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
    "COLUMN_0002\t注文者\tuser_id\tUUID\tNO\tNO\tNO\t\tTABLE_0001\t\n"
    "\n"
    "[TABLE_0002.md]\n"
    "# 注文\n"
    "\n"
    "注文情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[orders.tsv]]\n"
)

SINGLE_TABLE_RESPONSE = (
    "[TABLE_0001]\n"
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
    "\n"
    "[TABLE_0001.md]\n"
    "# ユーザー\n"
    "\n"
    "ユーザー情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[users.tsv]]\n"
)
```

パーサーテストを更新:

```python
class TestParseMultiTableResponse:

    def test_単一テーブルをパースする(self) -> None:
        result = ai_service._parse_multi_table_response(SINGLE_TABLE_RESPONSE)
        assert len(result) == 1
        name, tsv, md = result[0]
        assert name == "TABLE_0001"
        assert "COLUMN_0001\t" in tsv
        assert "![[users.tsv]]" in md

    def test_複数テーブルをパースする(self) -> None:
        result = ai_service._parse_multi_table_response(MULTI_TABLE_RESPONSE)
        assert len(result) == 2
        assert result[0][0] == "TABLE_0001"
        assert result[1][0] == "TABLE_0002"
        assert "TABLE_0001" in result[1][1]  # fk_target
```

- [ ] **Step 2: テスト実行 — FAIL を確認**

Run: `uv run task test -- tests/unit/test_ai_service.py::TestParseMultiTableResponse -v`
Expected: FAIL（パーサーは変更不要 — `[TABLE_0001]` セクションは既存の `_SECTION_RE` でマッチする。テストデータの変更で PASS するはず）

実際には `_SECTION_RE = re.compile(r"^\[([^\]]+)\]$")` は `[TABLE_0001]` にマッチするので、パーサー自体の変更は不要。テストデータの更新のみ。

- [ ] **Step 3: テスト実行 — PASS を確認**

Run: `uv run task test -- tests/unit/test_ai_service.py::TestParseMultiTableResponse -v`
Expected: PASS

- [ ] **Step 4: AI スタブを更新**

`app/ai_service.py` の `_STUB_TSV` と `_STUB_MD` を新フォーマットに:

```python
_STUB_TSV = (
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
)

_STUB_MD = "# スタブ\n\n## 概要\n\nテスト用テーブル。\n\n## テーブル設計\n\n![[stub_table.tsv]]\n"
```

`create_table_design` のテストモードスタブも更新（シンボル付き）:

```python
if os.environ.get("SYSDEN_TEST_MODE") == "1":
    logger.info("AI テーブル作成スキップ (テストモード)")
    return [("TABLE_0001", _STUB_TSV, _STUB_MD)]
```

- [ ] **Step 5: create_table_design のシグネチャ更新**

`create_table_design` に `next_table_id` パラメータを追加し、プロンプトに含める:

```python
def create_table_design(prompt: str, next_table_id: int = 1) -> list[tuple[str, str, str]]:
    """AI にテーブル設計を生成させる。

    Returns:
        (symbol, tsv, md) のリスト。symbol は TABLE_XXXX 形式。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI テーブル作成スキップ (テストモード)")
        symbol = f"TABLE_{next_table_id:04d}"
        return [(symbol, _STUB_TSV, _STUB_MD)]

    config = _load_prompts()["table_create"]
    system_msg = config["system"].format(next_table_id=next_table_id)
    # ... 残りは既存と同じ
```

- [ ] **Step 6: generate_table_design にシンボル情報を追加**

更新モード用に `table_symbol` パラメータを追加:

```python
def generate_table_design(
    prompt: str,
    current_tsv: str | None = None,
    table_symbol: str | None = None,
) -> str:
```

プロンプトにテーブルシンボルを含める。

- [ ] **Step 7: prompts/ai_prompts.yaml を更新**

`table_create` のシステムプロンプトにシンボル仕様を追加:

```yaml
table_create:
  system: |
    あなたはデータベーステーブル設計のアシスタントです。
    ユーザーの依頼に応じて、1 つまたは複数のテーブル定義とテーブル説明を出力してください。

    テーブルシンボルは TABLE_{next_table_id:04d} から開始してください。
    複数テーブルの場合は連番にしてください。

    出力形式（テーブルごとに TSV セクションと markdown セクションを出力）:
    [TABLE_XXXX]
    ヘッダー行（TSV）
    データ行（TSV）

    [TABLE_XXXX.md]
    テーブル説明（markdown）

    TSV ヘッダー（タブ区切り、必須）:
    symbol	logical_name	physical_name	type	nullable	pk	unique	default	fk_target	description

    出力規則:
    - symbol は COLUMN_0001 から連番
    - logical_name は日本語のカラム名（例: 識別子、商品名、作成日時）
    - physical_name は英語スネークケース（例: id、product_name、created_at）
    - nullable, pk, unique は YES または NO
    - default が存在しない場合は空文字（タブのみ）
    - fk_target は参照先テーブルのシンボル（例: TABLE_0001）。FK でない場合は空文字
    - description はカラム名から自明でない補足情報がある場合のみ記載する

    複数テーブルの例:
    [TABLE_0001]
    symbol	logical_name	physical_name	type	nullable	pk	unique	default	fk_target	description
    COLUMN_0001	識別子	id	UUID	NO	YES	YES

    [TABLE_0001.md]
    # ユーザー

    ## 概要

    ユーザー情報を管理するテーブル。

    ## テーブル設計

    ![[users.tsv]]

    [TABLE_0002]
    symbol	logical_name	physical_name	type	nullable	pk	unique	default	fk_target	description
    COLUMN_0001	識別子	id	UUID	NO	YES	YES
    COLUMN_0002	注文者	user_id	UUID	NO	NO	NO		TABLE_0001

    [TABLE_0002.md]
    # 注文

    ## 概要

    注文情報を管理するテーブル。ユーザーと関連する。

    ## テーブル設計

    ![[orders.tsv]]

    markdown セクションの出力規則:
    - [TABLE_XXXX.md] 行で開始する
    - 最初の見出しは「# 日本語テーブル名」（h1）
    - 次に「## 概要」見出しでテーブルの概要説明を記述する
    - 必ず「## テーブル設計」見出しの下に ![[physical_name.tsv]] を埋め込む

  model: gpt-4o
  temperature: 0.2
```

`table_design`（更新用）のシステムプロンプトも同様にシンボル付き TSV フォーマットに更新。

- [ ] **Step 8: 物理設計スタブを新フォーマットに更新**

`app/ai_service.py` の物理設計スタブも TSV ヘッダーを揃える（物理設計 TSV は独自ヘッダーなので `symbol` 等は不要だが、`_STUB_PHYSICAL_TSV` の `column_name` は `physical_name` に対応するためそのまま）。物理設計プロンプトの `user_template` に渡す `logical_tsv` は新フォーマットの TSV がそのまま入るので変更不要。

- [ ] **Step 9: テスト実行 — 全テスト PASS を確認**

Run: `uv run task test -- tests/unit/test_ai_service.py -v`
Expected: 全テスト PASS

- [ ] **Step 10: コミット**

```bash
git add app/ai_service.py prompts/ai_prompts.yaml tests/unit/test_ai_service.py
git commit -m "feat: AI プロンプトとパーサーをシンボル付きフォーマットに対応する"
```

---

### Task 6: API ルーターのシンボルフロー対応

**Files:**
- Modify: `app/routers/api.py` — テーブル作成・更新・削除フロー更新
- Test: `tests/unit/test_api.py`（存在すれば更新、なければ統合テストで確認）

**Interfaces:**
- Consumes: `allocate_table_symbols(count) -> list[str]` (Task 1)、`register_table(symbol, physical_name)` (Task 3)、`unregister_table(physical_name)` (Task 3)、`create_table_design(prompt, next_table_id) -> list[tuple[str, str, str]]` (Task 5)

- [ ] **Step 1: create_table エンドポイントを更新**

`app/routers/api.py` の `create_table` 関数を修正:

```python
@router.post("/tables")
def create_table(
    request: Request,
    prompt: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
) -> Response:
    """AI にテーブル設計を生成させ、ファイルに書き込む。"""
    logger.info("テーブル作成リクエスト: name=%s prompt_length=%d", name, len(prompt))
    next_id = table_service.read_next_table_id()
    if name is None:
        tables = ai_service.create_table_design(prompt, next_table_id=next_id)
    else:
        _check_table_name(name)
        symbol = f"TABLE_{next_id:04d}"
        tsv = ai_service.generate_table_design(prompt, table_symbol=symbol)
        default_md = f"# {name}\n\n## 概要\n\n## テーブル設計\n\n![[{name}.tsv]]\n"
        tables = [(symbol, tsv, default_md)]

    # physical_name を TSV から抽出（markdown の ![[xxx.tsv]] からも取得可能）
    written: list[str] = []
    try:
        for symbol, tbl_tsv, tbl_md in tables:
            # TSV の最初のデータ行から physical_name を使ってファイル名を決定
            # AI の markdown 内の ![[xxx.tsv]] からテーブル名を取得
            import re
            embed_match = re.search(r"!\[\[([A-Za-z0-9_]+)\.tsv\]\]", tbl_md)
            if embed_match:
                tbl_name = embed_match.group(1)
            else:
                tbl_name = symbol.lower()
            _check_table_name(tbl_name)
            if table_service.table_exists(tbl_name):
                raise HTTPException(status_code=409, detail=f"Table '{tbl_name}' already exists")
            table_service.write_tsv(tbl_name, tbl_tsv)
            written.append(tbl_name)
            if tbl_md:
                table_service.write_markdown(tbl_name, tbl_md)
            table_service.register_table(symbol, tbl_name)
    except Exception:
        for written_name in written:
            table_service.delete_table(written_name)
            table_service.unregister_table(written_name)
        raise
    table_service.save_next_table_id(next_id + len(tables))
    table_service.rebuild_index()
    logger.info("テーブル作成完了: tables=%s", [t[0] for t in tables])
    first_name = written[0] if written else ""
    redirect_url = f"/tables/{first_name}" if len(tables) == 1 else "/"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)
```

- [ ] **Step 2: delete_table エンドポイントを更新**

削除時に `unregister_table` を呼ぶ:

```python
@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    _check_table_name(name)
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    table_service.unregister_table(name)
    table_service.rebuild_index()
    logger.info("テーブル削除完了: table=%s", name)
    return {"status": "deleted", "name": name}
```

- [ ] **Step 3: update_table エンドポイントを更新**

テーブルシンボルを AI に渡す:

```python
@router.post("/tables/{name}")
def update_table(name: str, request: Request, prompt: Annotated[str, Form()]) -> Response:
    logger.info("テーブル更新リクエスト: table=%s prompt_length=%d", name, len(prompt))
    _check_table_name(name)
    try:
        current_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    symbol = table_service.get_table_symbol(name)
    tsv = ai_service.generate_table_design(prompt, current_tsv, table_symbol=symbol)
    table_service.write_tsv(name, tsv)
    logger.info("テーブル更新完了: table=%s", name)
    redirect_url = f"/tables/{name}"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)
```

- [ ] **Step 4: html.py のテンプレート変数を更新**

`app/routers/html.py` の `index` 関数で `read_index_tables` が返す辞書キーが変わるので、テンプレートも対応:

index.html で `t.name` → `t.physical_name`、`t.display_name` → `t.logical_name` に変更:

```html
{% for t in tables %}
<tr>
  <td><a href="/tables/{{ t.physical_name }}">{{ t.logical_name }}</a></td>
  <td style="text-align:right;">
    <button hx-delete="/api/tables/{{ t.physical_name }}"
            hx-confirm="{{ t.logical_name }} を削除しますか？"
            ...>削除</button>
  </td>
</tr>
{% endfor %}
```

- [ ] **Step 5: テスト実行 — 全テスト PASS を確認**

Run: `uv run task test && uv run task lint`
Expected: 全 PASS

- [ ] **Step 6: コミット**

```bash
git add app/routers/api.py app/routers/html.py templates/index.html
git commit -m "feat: API ルーターをシンボルフローに対応する"
```

---

### Task 7: 既存データクリアと最終確認

**Files:**
- Delete: `.data/` 配下の既存ファイル（categories.*, products.*, プロダクト.*, index.*, physical_*）
- Create: `.data/index.yaml` — 初期状態

- [ ] **Step 1: 既存データを削除**

```bash
rm -f .data/categories.* .data/products.* .data/プロダクト.* .data/index.* .data/physical_*
```

- [ ] **Step 2: 初期 index.yaml を作成**

```yaml
next_table_id: 1
```

- [ ] **Step 3: 全テスト + lint + 型チェック**

Run: `uv run task test && uv run task lint && uv run task typecheck`
Expected: 全 PASS

- [ ] **Step 4: コミット**

```bash
git add -A .data/
git commit -m "chore: 既存テストデータをクリアし、初期 index.yaml を作成する"
```

- [ ] **Step 5: 開発サーバーで動作確認**

Run: `uv run task dev`

確認項目:
1. トップページ（`/`）が表示される（テーブル一覧は空）
2. テーブル作成ダイアログが開く
3. ER 図エリアが空で表示される
