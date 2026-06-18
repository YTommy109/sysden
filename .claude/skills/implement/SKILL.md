# sysden 実装スキル

sysden に新機能を追加または既存コードを変更するときの制約。

## Anthropic Agent SDK の使い方

**ANTHROPIC_API_KEY を環境変数に設定しない**。SDK はサブスクリプション認証で動作する。
設定されていると Max プランの枠外で API 課金が発生する。

Agent はアプリ起動時に 1 回だけ作成し、ID を state に保持する:

```python
# app/ai_service.py（起動時に 1 回）
agent_id: str = client.beta.agents.create(
    model="claude-opus-4-8",
    system="...",  # 設計書の書式規約・mermaid 使用方針
).id
```

AI ジョブ 1 件 = Session 1 件:

```python
session = client.beta.agents.sessions.create(agent_id=agent_id)
# events.send で依頼文を送信し、agent.message から markdown を抽出する
```

## 非同期 DB アクセス

SQLModel（SQLAlchemy 2.x async ラッパー）を使う。モデル定義と DB テーブルを 1 クラスで管理する:

```python
from sqlmodel import SQLModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

class Document(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    ...
```

セッションは必ず `async with` で管理する:

```python
async with AsyncSession(engine) as session:
    result = await session.exec(select(Document).where(Document.id == doc_id))
    doc = result.one_or_none()
```

`session.execute()` ではなく `session.exec()` を使う（SQLModel の推奨 API）。

## EventBus の使い方

`event_bus` は `asyncio.Queue` ベース。全処理がイベントループ内のため `call_soon_threadsafe` は不要:

```python
await event_bus.publish(f"job_finished:{job_id}")
```

watchdog 等のスレッドから呼ぶ場合のみ `loop.call_soon_threadsafe` を使う（本アプリでは不要）。

## AI ジョブの非同期実行

ジョブは `asyncio.create_task()` で実行する。Celery 等の外部キューは使わない:

```python
asyncio.create_task(run_ai_job(job_id))
```

## SSE フロントエンド（htmx-ext-sse）

SSE の受信と DOM 更新は `htmx-ext-sse` 拡張で行う。
htmx 本体の後に拡張スクリプトを読み込み、`hx-ext="sse"` を使う:

```html
<!-- 拡張読み込み -->
<script src="..." defer></script>  <!-- htmx 本体 -->
<script src="..." defer></script>  <!-- htmx-ext-sse -->

<!-- SSE 接続と自動 swap -->
<div hx-ext="sse" sse-connect="/events">
  <div sse-swap="document_updated:{{doc_id}}" hx-target="#preview" hx-get="/documents/{{doc_id}}/preview">
  </div>
</div>
```

イベント名は `job_finished:{job_id}` / `job_failed:{job_id}` / `document_updated:{document_id}` の 3 種。
サーバー側（sse-starlette）のイベント名と必ず一致させる。

## SSE テスト

`TestClient` は SSE 無限ストリームをハングさせるため、SSE エンドポイントのテストは
ルート登録確認のみ行う:

```python
def test_events_route_is_registered():
    from app.main import app
    from fastapi.routing import APIRoute
    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert "/events" in paths
```

## テンプレートレスポンス

Starlette 1.x 以降の API を使う:

```python
# 正しい
templates.TemplateResponse(request, "template.html", {"key": "value"})

# 古い書き方（非推奨）
templates.TemplateResponse("template.html", {"request": request, "key": "value"})
```

## ロールバック実装

ロールバックは `documents.current_revision_id` の付け替えのみ。履歴（revisions）は不変:

```python
doc.current_revision_id = target_revision_id
await session.commit()
```

過去リビジョンを削除したり新たなリビジョンを作成したりしない。
