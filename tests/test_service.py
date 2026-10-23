import asyncio
import json
from pathlib import Path

import httpx
import pytest

from askless.agents import acknowledge
from askless.llm import LLMClient, ProviderError, Settings
from askless.models import Policy
from askless.service import Service
from askless.session import Run
from askless.store import Conflict, Store

CSV = "email,name\na@example.com,Old\na@example.com,New\ninvalid,Bad\n"


def test_offline_run_applies_decisions_to_actual_worker_outputs(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    service = Service(store, LLMClient(Settings()))
    run = service.create("导入这批联系人", CSV, "offline")
    asyncio.run(service.prepare(run.id))
    ready = store.get(run.id)
    assert ready.status == "ready"
    assert len(ready.questions) == 9
    assert len(ready.trials) == 8
    assert ready.llm_calls == 0
    applying = service.answer(run.id, {"duplicates": "last", "invalid": "quarantine"}, ready.revision)
    asyncio.run(service.finish(applying.id))
    completed = store.get(run.id)
    assert completed.status == "completed"
    result = completed.result
    assert result is not None
    assert result.rows == [{"email": "a@example.com", "name": "New"}]
    assert len(completed.receipts) == 3
    assert all(r.policy.duplicates == "last" for r in completed.receipts)
    assert all(r.output_hash == result.output_hash for r in completed.receipts)
    assert Store(tmp_path / "test.db").get(run.id).status == "completed"


def test_answer_is_atomic_and_rejects_missing_unknown_or_stale_decisions(tmp_path: Path) -> None:
    service = Service(Store(tmp_path / "test.db"), LLMClient(Settings()))
    run = service.create("导入", CSV, "offline")
    asyncio.run(service.prepare(run.id))
    ready = service.store.get(run.id)
    for answers in [{"duplicates": "last"}, {"duplicates": "delete", "invalid": "block"}, {"duplicates": "last", "invalid": "block", "email_case": "lower"}]:
        with pytest.raises(ValueError):
            service.answer(run.id, answers, ready.revision)
    assert service.store.get(run.id).status == "ready"
    service.answer(run.id, {"duplicates": "last", "invalid": "quarantine"}, ready.revision)
    with pytest.raises(Conflict):
        service.answer(run.id, {"duplicates": "first", "invalid": "block"}, ready.revision)


def test_restart_marks_inflight_work_interrupted_but_preserves_ready(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    service = Service(store, LLMClient(Settings()))
    waiting = service.create("导入", CSV, "offline")
    asyncio.run(service.prepare(waiting.id))
    running = service.create("导入", CSV, "offline")
    store.interrupt_inflight()
    assert store.get(waiting.id).status == "ready"
    assert store.get(running.id).status == "interrupted"


def test_provider_errors_are_sanitized_and_never_become_offline_success() -> None:
    secret = "private-credential-sentinel"
    settings = Settings(api_key=secret, base_url="https://example.com/v1", model="test")
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"error": {"message": secret}}))
    client = LLMClient(settings, transport=transport)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(client.json_reply("system", "prompt", 200))
    assert secret not in str(caught.value)
    assert "401" in str(caught.value)


def test_live_mode_requires_credentials(tmp_path: Path) -> None:
    service = Service(Store(tmp_path / "test.db"), LLMClient(Settings()))
    with pytest.raises(ValueError, match="API"):
        service.create("导入", CSV, "live")


def test_answer_enforces_active_capacity_atomically_and_can_resume_later(tmp_path: Path) -> None:
    service = Service(Store(tmp_path / "test.db"), LLMClient(Settings()))
    ready: list[Run] = []
    for _ in range(3):
        run = service.create("导入", CSV, "offline")
        asyncio.run(service.prepare(run.id))
        ready.append(service.store.get(run.id))
    answers = {"duplicates": "last", "invalid": "quarantine"}
    for run in ready[:2]:
        service.answer(run.id, answers, run.revision)
    with pytest.raises(Conflict, match="两次"):
        service.answer(ready[2].id, answers, ready[2].revision)
    unchanged = service.store.get(ready[2].id)
    assert unchanged.status == "ready"
    assert unchanged.revision == ready[2].revision
    asyncio.run(service.finish(ready[0].id))
    assert service.answer(ready[2].id, answers, ready[2].revision).status == "applying"


@pytest.mark.parametrize("ack_policy", [{}, {"duplicates": "first"}])
def test_acknowledgement_must_explicitly_echo_every_policy_field(tmp_path: Path, ack_policy: dict[str, str]) -> None:
    settings = Settings(api_key="test-credential", base_url="https://example.com/v1", model="test")
    response = {"choices": [{"message": {"content": json.dumps({"summary": "ok", "policy": ack_policy})}, "finish_reason": "stop"}]}
    llm = LLMClient(settings, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    service = Service(Store(tmp_path / "test.db"), llm)
    run = service.create("导入", CSV, "live")
    with pytest.raises(ProviderError, match="协议校验"):
        asyncio.run(acknowledge(llm, run, run.agents[0], Policy()))
