import re
import uuid
from typing import Optional

import anthropic
from sqlmodel.ext.asyncio.session import AsyncSession

from app import document_service
from app.database import engine
from app.event_bus import event_bus

client = anthropic.Anthropic()
_agent_id: Optional[str] = None

SYSTEM_PROMPT = """あなたはシステム設計ドキュメントのアシスタントです。
ユーザーの依頼に応じて、markdown + mermaid 形式のシステム設計書を生成または更新します。

出力規則:
- 出力はドキュメント本文のみ。前置き・説明・コードブロック外のコメントは不要
- 先頭は `# タイトル` の見出しで始める
- 図（アーキテクチャ・シーケンス・ER・フロー等）は mermaid フェンスブロックで記述する
- 既存ドキュメントの更新依頼では、変更箇所だけでなくドキュメント全体を返す
"""


async def initialize_agent() -> None:
    global _agent_id
    agent = client.beta.agents.create(
        model="claude-opus-4-8",
        name="sysden-assistant",
        system=SYSTEM_PROMPT,
    )
    _agent_id = agent.id


def _extract_title(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)", markdown, re.MULTILINE)
    return match.group(1).strip() if match else "無題のドキュメント"


def _build_prompt(user_request: str, current_content: Optional[str]) -> str:
    if current_content:
        return f"現在のドキュメント:\n\n{current_content}\n\n---\n\n依頼: {user_request}"
    return user_request


async def run_ai_job(job_id: uuid.UUID) -> None:
    async with AsyncSession(engine) as session:
        job = await document_service.get_ai_job(session, job_id)
        await document_service.update_ai_job_status(session, job_id, "running")

        try:
            prompt = _build_prompt(job.prompt, None)
            if job.document_id:
                rev = await document_service.get_current_revision(session, job.document_id)
                if rev:
                    prompt = _build_prompt(job.prompt, rev.content)

            agent_session = client.beta.agents.sessions.create(agent_id=_agent_id)
            turn = client.beta.agents.sessions.turns.create(
                agent_id=_agent_id,
                session_id=agent_session.id,
                messages=[{"role": "user", "content": prompt}],
            )

            markdown = "\n".join(
                block.text for block in turn.content if hasattr(block, "text")
            )

            if job.document_id:
                await document_service.add_revision(
                    session, job.document_id, markdown, job.id
                )
                await document_service.update_ai_job_status(session, job_id, "succeeded")
                await event_bus.publish(f"job_finished:{job_id}")
                await event_bus.publish(f"document_updated:{job.document_id}")
            else:
                title = _extract_title(markdown)
                doc = await document_service.create_document(
                    session, job.project_id, title
                )
                await document_service.add_revision(session, doc.id, markdown, job.id)
                await document_service.update_ai_job_status(session, job_id, "succeeded")
                await event_bus.publish(f"job_finished:{job_id}")
                await event_bus.publish(f"document_updated:{doc.id}")

        except Exception as exc:
            await document_service.update_ai_job_status(
                session, job_id, "failed", error=str(exc)
            )
            await event_bus.publish(f"job_failed:{job_id}")
