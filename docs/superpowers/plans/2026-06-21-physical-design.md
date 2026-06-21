# 物理設計表示機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 論理設計から AI が物理設計（テーブル定義 + DoA バリデーション仕様）を生成し、独立ページで表示する機能を追加する

**Architecture:** 既存の論理設計パターン（markdown レイアウト + TSV 埋め込み）を踏襲。ファイル名プレフィックス `physical_` で論理/物理を区別。`POST /api/tables/{name}/physical` で AI 生成、`GET /tables/{name}/physical` で表示。

**Tech Stack:** FastAPI, Jinja2, htmx, OpenAI SDK, markdown-it-py

## Global Constraints

- Python 3.14+ / Ruff 行長 100 文字 / 認知的複雑度 ≤ 10
- テスト: `uv run task test`（カバレッジ 80% 以上）
- lint: `uv run task lint` / format: `uv run task format` / typecheck: `uv run task typecheck`
- テスト関数名は日本語（`test_物理設計ページが200を返す`）
- ログは `logging` モジュールを使用（print 禁止）
- テストモード: `SYSDEN_TEST_MODE=1` でスタブ応答を返す

---

### Task 1: table_service に物理設計ファイルの読み書き関数を追加

**Files:**
- Modify: `app/table_service.py`
- Test: `tests/unit/test_table_service.py`

**Interfaces:**
- Consumes: 既存の `get_data_dir()`, `validate_table_name()`
- Produces:
  - `physical_design_exists(name: str) -> bool`
  - `write_physical_tsv(name: str, tsv_content: str) -> None`
  - `write_physical_doa_tsv(name: str, tsv_content: str) -> None`
  - `write_physical_markdown(name: str, content: str) -> None`
  - `read_physical_markdown(name: str) -> str | None`
  - `list_tables()` が `physical_*` を除外するよう修正

- [ ] **Step 1: `list_tables()` が `physical_` プレフィックスを除外するテストを書く**

```python
def test_テーブル一覧がphysicalプレフィックスを除外する(tmp_path: Path) -> None:
    # Given: 論理設計と物理設計の TSV が混在する
    (tmp_path / "users.tsv").write_text("column_name\ttype\n", encoding="utf-8")
    (tmp_path / "physical_users.tsv").write_text("column_name\ttype\n", encoding="utf-8")
    (tmp_path / "physical_users_doa.tsv").write_text("column_name\tpython_type\n", encoding="utf-8")

    # When: テーブル一覧を取得する
    result = table_service.list_tables()

    # Then: physical_ プレフィックスのファイルは含まれない
    assert result == ["users"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/unit/test_table_service.py::test_テーブル一覧がphysicalプレフィックスを除外する -v`
Expected: FAIL（現在は `physical_users` と `physical_users_doa` が含まれる）

- [ ] **Step 3: `list_tables()` を修正する**

`app/table_service.py` の `list_tables()` のリスト内包表記にフィルタを追加:

```python
def list_tables() -> list[str]:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return sorted(
        f.stem
        for f in d.glob("*.tsv")
        if f.stem != _INDEX_STEM and not f.stem.startswith("physical_")
    )
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `uv run pytest tests/unit/test_table_service.py::test_テーブル一覧がphysicalプレフィックスを除外する -v`
Expected: PASS

- [ ] **Step 5: 物理設計の存在判定と読み書き関数のテストを書く**

```python
def test_物理設計の存在判定(tmp_path: Path) -> None:
    # Given: 物理設計ファイルが存在しない
    assert table_service.physical_design_exists("users") is False

    # When: 物理設計 TSV を書き込む
    table_service.write_physical_tsv("users", "column_name\ttype\nid\tuuid\n")

    # Then: 存在判定が True になる
    assert table_service.physical_design_exists("users") is True


def test_物理設計markdownの読み書き(tmp_path: Path) -> None:
    # Given: 物理設計 markdown が存在しない
    assert table_service.read_physical_markdown("users") is None

    # When: 物理設計 markdown を書き込む
    table_service.write_physical_markdown("users", "# テーブル定義\n\n![[physical_users.tsv]]")

    # Then: 読み込みで内容が取得できる
    result = table_service.read_physical_markdown("users")
    assert result is not None
    assert "![[physical_users.tsv]]" in result


def test_物理設計DoA_TSVの書き込み(tmp_path: Path) -> None:
    # Given: データディレクトリが存在する

    # When: DoA TSV を書き込む
    content = "column_name\tpython_type\trequired\nid\tUUID\tYES\n"
    table_service.write_physical_doa_tsv("users", content)

    # Then: ファイルが作成される
    path = tmp_path / "physical_users_doa.tsv"
    assert path.exists()
    assert "UUID" in path.read_text(encoding="utf-8")
```

- [ ] **Step 6: 物理設計の読み書き関数を実装する**

```python
_PHYSICAL_PREFIX = "physical_"


def physical_design_exists(name: str) -> bool:
    return (get_data_dir() / f"{_PHYSICAL_PREFIX}{name}.tsv").exists()


def write_physical_tsv(name: str, tsv_content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")


def write_physical_doa_tsv(name: str, tsv_content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}_doa.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")


def write_physical_markdown(name: str, content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")


def read_physical_markdown(name: str) -> str | None:
    path = get_data_dir() / f"{_PHYSICAL_PREFIX}{name}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 7: 全テストを実行して通過を確認する**

Run: `uv run pytest tests/unit/test_table_service.py -v`
Expected: ALL PASS

- [ ] **Step 8: lint + format + typecheck**

Run: `uv run task lint && uv run task format && uv run task typecheck`

- [ ] **Step 9: コミット**

```bash
git add app/table_service.py tests/unit/test_table_service.py
git commit -m "feat: table_service に物理設計ファイルの読み書き関数を追加する"
```

---

### Task 2: ai_service に物理設計生成関数を追加

**Files:**
- Modify: `app/ai_service.py`
- Modify: `prompts/ai_prompts.yaml`
- Test: `tests/unit/test_ai_service.py`

**Interfaces:**
- Consumes: `get_client()`, `_load_prompts()`, `_parse_multi_table_response()`
- Produces: `generate_physical_design(name: str, logical_md: str, logical_tsv: str, common_rules: str | None = None) -> tuple[str, str, str]`
  - 戻り値: `(physical_md, physical_tsv, physical_doa_tsv)`

- [ ] **Step 1: AI プロンプト定義を追加する**

`prompts/ai_prompts.yaml` に `physical_design` セクションを追加:

```yaml
physical_design:
  system: |
    あなたはデータベース物理設計のアシスタントです。
    論理設計（markdown + TSV）を入力として、以下の3つのセクションを出力してください。

    出力形式:
    [table]
    物理テーブル定義の TSV（ヘッダー + データ行）

    [doa]
    DoA バリデーション仕様の TSV（ヘッダー + データ行）

    [markdown]
    物理設計の markdown（レイアウト定義）

    物理テーブル定義 TSV のヘッダー（タブ区切り、必須）:
    column_name	type	nullable	pk	unique	default	description

    出力規則（物理テーブル定義）:
    - column_name は英語スネークケース
    - type は具体的な SQL 型（uuid, varchar(255), timestamptz, decimal(10,2) など）
    - nullable, pk, unique は YES または NO
    - default は SQL デフォルト値（gen_random_uuid(), now() など）
    - 共通ルールで指定されたカラム（例: created_at, updated_at, disabled_at）を必ず含める

    DoA バリデーション TSV のヘッダー（タブ区切り、必須）:
    column_name	python_type	required	min	max	max_length	description

    出力規則（DoA バリデーション）:
    - column_name は物理テーブル定義と同じカラム名
    - python_type は SQLModel フィールドの Python 型（UUID, str, int, Decimal, date, datetime など）
    - required は YES または NO
    - min, max は数値制約（該当しない場合は空）
    - max_length は文字列長制約（該当しない場合は空）
    - description は Pydantic Field や field_validator で表現する特殊なバリデーションルール（該当しない場合は空）

    markdown の出力規則:
    - 最初の見出しは「# 物理設計」（h1）
    - 「## テーブル定義」見出しの下に ![[physical_{テーブル名}.tsv]] を埋め込む
    - 「## DoA バリデーション」見出しの下に ![[physical_{テーブル名}_doa.tsv]] を埋め込む
    - 必要に応じて補足説明を記載する

  user_template: "テーブル名: {name}\n\n論理設計 markdown:\n{logical_md}\n\n論理設計 TSV:\n{logical_tsv}\n\n共通ルール:\n{common_rules}"

  model: gpt-4o
  temperature: 0.2
```

- [ ] **Step 2: テストモード用スタブとテストを書く**

```python
def test_generate_physical_design_テストモードでスタブを返す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: テストモードが有効
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

    # When: 物理設計を生成する
    md, tsv, doa = ai_service.generate_physical_design(
        name="users",
        logical_md="# ユーザー\n\n## テーブル設計\n\n![[users.tsv]]",
        logical_tsv="column_name\ttype\nid\tUUID\n",
    )

    # Then: スタブが返る
    assert "physical_users.tsv" in md
    assert "column_name\t" in tsv
    assert "column_name\t" in doa
```

- [ ] **Step 3: テストを実行して失敗を確認する**

Run: `uv run pytest tests/unit/test_ai_service.py::test_generate_physical_design_テストモードでスタブを返す -v`
Expected: FAIL（関数が存在しない）

- [ ] **Step 4: `generate_physical_design` を実装する**

```python
_STUB_PHYSICAL_TSV = (
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n"
)

_STUB_PHYSICAL_DOA_TSV = (
    "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\n"
    "id\tUUID\tYES\t\t\t\t\n"
)

_STUB_PHYSICAL_MD = (
    "# 物理設計\n\n## テーブル定義\n\n![[physical_stub_table.tsv]]\n\n"
    "## DoA バリデーション\n\n![[physical_stub_table_doa.tsv]]\n"
)

_PHYSICAL_SECTION_RE = re.compile(r"^\[(table|doa|markdown)\]$")


def _parse_physical_response(content: str) -> tuple[str, str, str]:
    """物理設計レスポンスの [table]/[doa]/[markdown] セクションをパースする。

    Returns:
        (markdown, table_tsv, doa_tsv) のタプル。

    Raises:
        ValueError: 必須セクションが欠けている場合。
    """
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []

    for line in content.splitlines():
        m = _PHYSICAL_SECTION_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(lines).strip() + "\n"
            current = m.group(1)
            lines = []
        elif current is not None:
            lines.append(line)

    if current is not None:
        sections[current] = "\n".join(lines).strip() + "\n"

    missing = {"table", "doa", "markdown"} - sections.keys()
    if missing:
        raise ValueError(f"物理設計のセクションが不足しています: {missing}")

    return sections["markdown"], sections["table"], sections["doa"]


def generate_physical_design(
    name: str,
    logical_md: str,
    logical_tsv: str,
    common_rules: str | None = None,
) -> tuple[str, str, str]:
    """AI に物理設計を生成させる。

    Args:
        name: テーブル名。
        logical_md: 論理設計の markdown。
        logical_tsv: 論理設計の TSV。
        common_rules: 共通ルール（index.md の内容）。

    Returns:
        (physical_md, physical_tsv, physical_doa_tsv) のタプル。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI 物理設計生成スキップ (テストモード)")
        stub_md = _STUB_PHYSICAL_MD.replace("stub_table", name)
        return stub_md, _STUB_PHYSICAL_TSV, _STUB_PHYSICAL_DOA_TSV

    logger.info("AI 物理設計生成開始: table=%s", name)
    config = _load_prompts()["physical_design"]
    user_message = config["user_template"].format(
        name=name,
        logical_md=logical_md,
        logical_tsv=logical_tsv,
        common_rules=common_rules or "なし",
    )

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": config["system"]},
                {"role": "user", "content": user_message},
            ],
            temperature=config["temperature"],
        )
    except Exception:
        logger.exception("AI 物理設計生成失敗: table=%s", name)
        raise
    content = response.choices[0].message.content or ""
    result = _parse_physical_response(content)
    logger.info("AI 物理設計生成完了: table=%s", name)
    return result
```

- [ ] **Step 5: テストを実行して通過を確認する**

Run: `uv run pytest tests/unit/test_ai_service.py::test_generate_physical_design_テストモードでスタブを返す -v`
Expected: PASS

- [ ] **Step 6: `_parse_physical_response` のテストを書いて実行する**

```python
def test_parse_physical_response_正常系() -> None:
    # Given: 3 セクションを含むレスポンス
    content = (
        "[table]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n"
        "\n"
        "[doa]\n"
        "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\n"
        "id\tUUID\tYES\t\t\t\t\n"
        "\n"
        "[markdown]\n"
        "# 物理設計\n\n## テーブル定義\n\n![[physical_users.tsv]]\n"
    )

    # When: パースする
    md, tsv, doa = ai_service._parse_physical_response(content)

    # Then: 各セクションが正しく抽出される
    assert "physical_users.tsv" in md
    assert "uuid" in tsv
    assert "UUID" in doa


def test_parse_physical_response_セクション不足でエラー() -> None:
    # Given: doa セクションが欠けたレスポンス
    content = "[table]\ncolumn_name\ttype\nid\tuuid\n\n[markdown]\n# 物理設計\n"

    # When/Then: ValueError が発生する
    with pytest.raises(ValueError, match="セクションが不足"):
        ai_service._parse_physical_response(content)
```

Run: `uv run pytest tests/unit/test_ai_service.py -k "parse_physical" -v`
Expected: PASS

- [ ] **Step 7: lint + format + typecheck**

Run: `uv run task lint && uv run task format && uv run task typecheck`

- [ ] **Step 8: コミット**

```bash
git add app/ai_service.py prompts/ai_prompts.yaml tests/unit/test_ai_service.py
git commit -m "feat: ai_service に物理設計生成関数を追加する"
```

---

### Task 3: 物理設計生成 API エンドポイントを追加

**Files:**
- Modify: `app/routers/api.py`
- Test: `tests/integration/test_routes.py`

**Interfaces:**
- Consumes: `table_service.validate_table_name()`, `table_service.read_tsv_raw()`, `table_service.read_markdown()`, `table_service.write_physical_tsv()`, `table_service.write_physical_doa_tsv()`, `table_service.write_physical_markdown()`, `ai_service.generate_physical_design()`
- Produces: `POST /api/tables/{name}/physical` — 物理設計を生成して `/tables/{name}/physical` にリダイレクト

- [ ] **Step 1: 統合テストを書く**

```python
def test_物理設計を生成する(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: 論理設計のテーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown(
        "users",
        "# ユーザー\n\n## 概要\n\nユーザー管理。\n\n## テーブル設計\n\n![[users.tsv]]",
    )

    # When: 物理設計生成 API にリクエストを送る
    resp = client.post("/api/tables/users/physical", follow_redirects=False)

    # Then: 物理設計ページにリダイレクトされる
    assert resp.status_code == 303
    assert "/tables/users/physical" in resp.headers["location"]

    # Then: 物理設計ファイルが作成される
    assert table_service.physical_design_exists("users")


def test_論理設計が存在しないテーブルの物理設計生成は404(
    client: TestClient,
    mock_openai: None,
) -> None:
    # Given: テーブルが存在しない

    # When: 物理設計生成 API にリクエストを送る
    resp = client.post("/api/tables/nonexistent/physical")

    # Then: 404 が返る
    assert resp.status_code == 404


def test_物理設計生成でHXリダイレクトを返す(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: テーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # When: HX-Request ヘッダー付きで物理設計を生成する
    resp = client.post(
        "/api/tables/users/physical",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    # Then: 200 + HX-Redirect ヘッダーが返る
    assert resp.status_code == 200
    assert "/tables/users/physical" in resp.headers["HX-Redirect"]
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/integration/test_routes.py::test_物理設計を生成する -v`
Expected: FAIL（エンドポイントが存在しない）

- [ ] **Step 3: API エンドポイントを実装する**

`app/routers/api.py` に追加:

```python
@router.post("/tables/{name}/physical")
def generate_physical(name: str, request: Request) -> Response:
    """論理設計から物理設計を AI に生成させる。"""
    logger.info("物理設計生成リクエスト: table=%s", name)
    _check_table_name(name)
    try:
        logical_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err

    logical_md = table_service.read_markdown(name) or ""

    common_rules: str | None = None
    index_md_path = table_service.get_data_dir() / "index.md"
    if index_md_path.exists():
        common_rules = index_md_path.read_text(encoding="utf-8")

    physical_md, physical_tsv, physical_doa = ai_service.generate_physical_design(
        name=name,
        logical_md=logical_md,
        logical_tsv=logical_tsv,
        common_rules=common_rules,
    )

    table_service.write_physical_tsv(name, physical_tsv)
    table_service.write_physical_doa_tsv(name, physical_doa)
    table_service.write_physical_markdown(name, physical_md)

    logger.info("物理設計生成完了: table=%s", name)
    redirect_url = f"/tables/{name}/physical"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `uv run pytest tests/integration/test_routes.py -k "物理設計" -v`
Expected: ALL PASS

- [ ] **Step 5: lint + format + typecheck**

Run: `uv run task lint && uv run task format && uv run task typecheck`

- [ ] **Step 6: コミット**

```bash
git add app/routers/api.py tests/integration/test_routes.py
git commit -m "feat: 物理設計生成 API エンドポイントを追加する"
```

---

### Task 4: 物理設計ページの HTML テンプレートとルーターを追加

**Files:**
- Create: `templates/physical_detail.html`
- Modify: `app/routers/html.py`
- Modify: `templates/table_detail.html`
- Test: `tests/integration/test_routes.py`

**Interfaces:**
- Consumes: `table_service.physical_design_exists()`, `table_service.read_physical_markdown()`, `table_service.read_table_display_name()`, `table_service.render_markdown_with_embeds()`, `table_service.strip_title_heading()`
- Produces: `GET /tables/{name}/physical` — 物理設計ページを表示

- [ ] **Step 1: 統合テストを書く**

```python
def test_物理設計ページが未生成時に空状態を表示する(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: 論理設計のみ存在し物理設計は未生成
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # When: 物理設計ページにアクセスする
    resp = client.get("/tables/users/physical")

    # Then: 200 が返り生成ボタンが表示される
    assert resp.status_code == 200
    assert "まだ物理設計がありません" in resp.text
    assert "/api/tables/users/physical" in resp.text


def test_物理設計ページが生成済みの内容を表示する(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: 論理設計と物理設計の両方が存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")
    table_service.write_physical_tsv(
        "users",
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n",
    )
    table_service.write_physical_doa_tsv(
        "users",
        "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\n"
        "id\tUUID\tYES\t\t\t\t\n",
    )
    table_service.write_physical_markdown(
        "users",
        "# 物理設計\n\n## テーブル定義\n\n![[physical_users.tsv]]\n\n"
        "## DoA バリデーション\n\n![[physical_users_doa.tsv]]",
    )

    # When: 物理設計ページにアクセスする
    resp = client.get("/tables/users/physical")

    # Then: 200 が返り物理設計の内容が表示される
    assert resp.status_code == 200
    assert "uuid" in resp.text
    assert "UUID" in resp.text
    assert "まだ物理設計がありません" not in resp.text


def test_論理設計が存在しないテーブルの物理設計ページは404(
    client: TestClient,
) -> None:
    # Given: テーブルが存在しない

    # When: 物理設計ページにアクセスする
    resp = client.get("/tables/nonexistent/physical")

    # Then: 404 が返る
    assert resp.status_code == 404
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/integration/test_routes.py::test_物理設計ページが未生成時に空状態を表示する -v`
Expected: FAIL（ルートが存在しない）

- [ ] **Step 3: 物理設計テンプレートを作成する**

`templates/physical_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ display_name }} 物理設計 — sysden{% endblock %}
{% block content %}
<div style="display:flex; align-items:center; gap:0.75rem;">
  <a href="/tables/{{ name }}" aria-label="論理設計に戻る" title="論理設計に戻る" style="display:inline-flex; color:inherit;">
    <img src="/static/icons/arrow-left.svg" alt="" style="width:1.25rem; height:1.25rem;">
  </a>
  <h1 style="margin:0;">{{ display_name }}　<small style="font-weight:normal; font-size:0.6em; color:#888;">物理設計</small></h1>
  {% if has_physical %}
  <form method="post" action="/api/tables/{{ name }}/physical"
        hx-post="/api/tables/{{ name }}/physical"
        hx-disabled-elt="find button"
        style="margin:0;">
    <button type="submit" aria-label="物理設計を再生成" title="物理設計を再生成" style="background:#555; padding:0.3rem 0.45rem; line-height:0;">
      <img src="/static/icons/arrow-path.svg" alt="" style="width:1.1rem; height:1.1rem;">
    </button>
  </form>
  {% endif %}
</div>

{% if has_physical %}
<div id="physical-view" style="margin-top: 1rem;">
  {{ rendered | safe }}
</div>
{% else %}
<div style="margin-top: 2rem; text-align: center;">
  <p>まだ物理設計がありません。</p>
  <form method="post" action="/api/tables/{{ name }}/physical"
        hx-post="/api/tables/{{ name }}/physical"
        hx-disabled-elt="find button">
    <button type="submit">
      <img src="/static/icons/arrow-path.svg" alt="" style="width:1rem; height:1rem; vertical-align:middle;">
      物理設計を生成
    </button>
  </form>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: HTML ルーターにエンドポイントを追加する**

`app/routers/html.py` に追加:

```python
@router.get("/tables/{name}/physical", response_class=HTMLResponse)
def physical_detail(name: str, request: Request) -> HTMLResponse:
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")
    if not table_service.table_exists(name):
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")

    display_name = table_service.read_table_display_name(name)
    has_physical = table_service.physical_design_exists(name)

    rendered = ""
    if has_physical:
        md_content = table_service.read_physical_markdown(name)
        if md_content is not None:
            body = table_service.strip_title_heading(md_content)
            expanded = table_service.render_markdown_with_embeds(body)
            rendered = _md.render(expanded)

    return templates.TemplateResponse(
        request,
        "physical_detail.html",
        {
            "name": name,
            "display_name": display_name,
            "has_physical": has_physical,
            "rendered": rendered,
        },
    )
```

- [ ] **Step 5: 論理設計ページに物理設計へのリンクを追加する**

`templates/table_detail.html` のヘッダー部分にリンクを追加:

```html
<div style="display:flex; align-items:center; gap:0.75rem;">
  <a href="/" aria-label="一覧に戻る" title="一覧に戻る" style="display:inline-flex; color:inherit;">
    <img src="/static/icons/arrow-left.svg" alt="" style="width:1.25rem; height:1.25rem;">
  </a>
  <h1 style="margin:0;">{{ display_name }}</h1>
  <a href="/tables/{{ name }}/physical" aria-label="物理設計" title="物理設計" style="display:inline-flex; color:inherit; margin-left:auto;">
    <img src="/static/icons/server-stack.svg" alt="" style="width:1.25rem; height:1.25rem;">
  </a>
</div>
```

- [ ] **Step 6: server-stack アイコンを追加する**

Heroicons から `server-stack` の outline SVG を `static/icons/server-stack.svg` に保存:

```svg
<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
  <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 0 1-3-3m3 3a3 3 0 1 0 0 6h13.5a3 3 0 1 0 0-6m-16.5-3a3 3 0 0 1 3-3h13.5a3 3 0 0 1 3 3m-19.5 0a4.5 4.5 0 0 1 .9-2.7L5.737 5.1a3.375 3.375 0 0 1 2.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 0 1 .9 2.7m0 0a3 3 0 0 1-3 3m0 3h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Zm-3 6h.008v.008h-.008v-.008Zm0-6h.008v.008h-.008v-.008Z" />
</svg>
```

- [ ] **Step 7: テストを実行して通過を確認する**

Run: `uv run pytest tests/integration/test_routes.py -k "物理設計ページ" -v`
Expected: ALL PASS

- [ ] **Step 8: 論理設計ページに物理設計リンクが表示されるテストを追加・実行する**

```python
def test_論理設計ページに物理設計リンクがある(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: テーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # When: 論理設計ページにアクセスする
    resp = client.get("/tables/users")

    # Then: 物理設計ページへのリンクが存在する
    assert resp.status_code == 200
    assert "/tables/users/physical" in resp.text
```

Run: `uv run pytest tests/integration/test_routes.py::test_論理設計ページに物理設計リンクがある -v`
Expected: PASS

- [ ] **Step 9: 全テストを実行する**

Run: `uv run task test`
Expected: ALL PASS, coverage ≥ 80%

- [ ] **Step 10: lint + format + typecheck**

Run: `uv run task lint && uv run task format && uv run task typecheck`

- [ ] **Step 11: コミット**

```bash
git add templates/physical_detail.html templates/table_detail.html app/routers/html.py static/icons/server-stack.svg
git commit -m "feat: 物理設計ページの表示とナビゲーションを追加する"
```

---

### Task 5: E2E テストを追加

**Files:**
- Create: `tests/e2e/test_physical_design_page.py`

**Interfaces:**
- Consumes: 全タスクの成果物（ページ遷移・ボタン・生成フロー）

- [ ] **Step 1: E2E テストファイルを作成する**

```python
import re

from playwright.sync_api import Page, expect


def test_物理設計ページへの遷移(page: Page) -> None:
    # Given: テーブルが存在する状態でトップページにアクセス
    page.goto("/")
    page.get_by_role("link", name=re.compile(".+")).first.click()

    # When: 物理設計リンクをクリックする
    page.get_by_role("link", name="物理設計").click()

    # Then: 物理設計ページが表示される
    expect(page).to_have_url(re.compile(r"/tables/\w+/physical"))
    expect(page.get_by_text("物理設計")).to_be_visible()


def test_物理設計の未生成状態(page: Page) -> None:
    # Given: テーブルの物理設計ページにアクセス
    page.goto("/")
    page.get_by_role("link", name=re.compile(".+")).first.click()
    page.get_by_role("link", name="物理設計").click()

    # Then: 未生成メッセージと生成ボタンが表示される
    expect(page.get_by_text("まだ物理設計がありません")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("物理設計を生成"))).to_be_visible()


def test_物理設計の生成ボタンで生成される(page: Page) -> None:
    # Given: テーブルの物理設計ページで未生成状態
    page.goto("/")
    page.get_by_role("link", name=re.compile(".+")).first.click()
    page.get_by_role("link", name="物理設計").click()

    # When: 生成ボタンをクリックする
    page.get_by_role("button", name=re.compile("物理設計を生成")).click()

    # Then: 物理設計の内容が表示される（スタブの内容）
    page.wait_for_url(re.compile(r"/tables/\w+/physical"))
    expect(page.get_by_text("まだ物理設計がありません")).not_to_be_visible()


def test_物理設計ページから論理設計に戻れる(page: Page) -> None:
    # Given: 物理設計ページにいる
    page.goto("/")
    page.get_by_role("link", name=re.compile(".+")).first.click()
    page.get_by_role("link", name="物理設計").click()

    # When: 戻るリンクをクリックする
    page.get_by_role("link", name="論理設計に戻る").click()

    # Then: 論理設計ページに遷移する
    expect(page).to_have_url(re.compile(r"/tables/\w+$"))
```

- [ ] **Step 2: E2E テストを実行する**

Run: `uv run pytest tests/e2e/test_physical_design_page.py -v`
Expected: ALL PASS

- [ ] **Step 3: 全テストスイートを実行する**

Run: `uv run task test`
Expected: ALL PASS, coverage ≥ 80%

- [ ] **Step 4: コミット**

```bash
git add tests/e2e/test_physical_design_page.py
git commit -m "test: 物理設計ページの E2E テストを追加する"
```
