import asyncio
import uuid
from datetime import UTC, datetime
from typing import Literal

from askless.agents import acknowledge, propose
from askless.engine import compile_questions, execute, explore, parse_csv
from askless.llm import Completion, LLMClient, ProviderError
from askless.models import SPECS, DecisionKey, Policy
from askless.session import AgentState, Event, Receipt, Run, new_agents
from askless.store import Conflict, Store


def now() -> str:
    return datetime.now(UTC).isoformat()


def event(run: Run, label: str, detail: str) -> None:
    run.events.append(Event(at=now(), label=label, detail=detail))


def usage(run: Run, completion: Completion | None) -> None:
    if completion:
        run.llm_calls += completion.requests
        run.input_tokens += completion.input_tokens
        run.output_tokens += completion.output_tokens


class Service:
    def __init__(self, store: Store, llm: LLMClient) -> None:
        self.store = store
        self.llm = llm

    def create(self, title: str, csv_text: str, mode: Literal["live", "offline"]) -> Run:
        if not title.strip() or len(title) > 2000:
            raise ValueError("任务描述需包含 1–2,000 个字符。")
        if mode == "live" and not self.llm.settings.api_key:
            raise ValueError("阿里云 API 凭据未配置，请设置 ALIYUN_API_KEY 或选择离线演示。")
        run = Run(
            id=uuid.uuid4().hex,
            title=title.strip(),
            mode=mode,
            model=self.llm.settings.model if mode == "live" else "deterministic",
            created_at=now(),
            dataset=parse_csv(csv_text),
            agents=new_agents(),
        )
        event(run, "任务已接收", "原始 CSV 留在本机；LLM 只接收任务描述、聚合统计和策略合同。")
        self.store.create(run)
        return run

    async def prepare(self, run_id: str) -> None:
        try:
            run = self.store.get(run_id)

            def started(current: Run) -> None:
                for agent in current.agents:
                    agent.status = "thinking"
                event(current, "三个角色开始分析", "每个角色按已注册合同提交问题，待执行证据决定哪些问题需要保留。")

            self.store.update(run_id, started)
            outcomes = await asyncio.gather(*(self._propose(run, agent) for agent in run.agents), return_exceptions=True)
            self._raise_errors(outcomes)

            def exploring(current: Run) -> None:
                current.status = "exploring"
                event(current, "实际运行备选方案", "完整枚举 8 个策略组合，检查结果差异和策略交互。")

            run = self.store.update(run_id, exploring)
            trials = await asyncio.to_thread(explore, run.dataset)
            groups = compile_questions(run.questions, trials, run.dataset.scope)

            def ready(current: Run) -> None:
                current.trials, current.groups, current.status = trials, groups, "ready"
                remaining = sum(g.status == "pending" for g in groups)
                event(current, "问题编译完成", f"{len(current.questions)} 个原始问题 → {remaining} 个需要你决定的选择。等价结论绑定当前数据哈希。")

            self.store.update(run_id, ready)
        except Exception as error:  # noqa: BLE001 -- Background jobs persist a sanitized terminal failure.
            self._fail(run_id, error)

    async def _propose(self, run: Run, agent: AgentState) -> None:
        summary, questions, completion = await propose(self.llm, run, agent)

        def update(current: Run) -> None:
            state = next(a for a in current.agents if a.id == agent.id)
            state.summary, state.status = summary, "waiting_decision"
            current.questions.extend(questions)
            usage(current, completion)
            event(current, agent.name + "已提交", "3 个问题进入同一批数据的决策作用域。")

        self.store.update(run.id, update)

    def answer(self, run_id: str, answers: dict[str, str], revision: int) -> Run:
        def apply(run: Run) -> None:
            if run.status != "ready" or run.revision != revision:
                raise Conflict("运行状态已变化，请刷新后再提交。")
            pending = {g.key for g in run.groups if g.status == "pending"}
            if set(answers) != pending:
                raise ValueError("请仅提交全部待定问题的答案。")
            if any(value not in {o.value for o in SPECS[DecisionKey(key)].options} for key, value in answers.items()):
                raise ValueError("选择不在注册的选项范围内。")
            for group in run.groups:
                if group.key in answers:
                    group.selected, group.status = answers[group.key], "answered"
            policy = Policy.model_validate({g.key: g.selected for g in run.groups})
            run.result = execute(run.dataset, policy)
            run.status = "applying"
            for agent in run.agents:
                agent.status = "resuming"
            event(run, "决定已确认", "答案仅传播到同一数据作用域的相关角色，最终策略重新执行。")

        return self.store.update(run_id, apply)

    async def finish(self, run_id: str) -> None:
        try:
            run = self.store.get(run_id)
            if run.status != "applying" or run.result is None:
                raise ValueError("Run is not ready to finish")
            outcomes = await asyncio.gather(*(self._resume(run, agent) for agent in run.agents), return_exceptions=True)
            self._raise_errors(outcomes)

            def done(current: Run) -> None:
                current.status = "completed"
                event(current, "答案传播与执行完成", "三个角色回执均通过策略一致性检查，真实产物已保存在本机。")

            self.store.update(run_id, done)
        except Exception as error:  # noqa: BLE001 -- Background jobs persist a sanitized terminal failure.
            self._fail(run_id, error)

    async def _resume(self, run: Run, agent: AgentState) -> None:
        if run.result is None:
            raise ValueError("Missing result")
        policy = run.result.policy
        summary, completion = await acknowledge(self.llm, run, agent, policy)
        verification = execute(run.dataset, policy)
        if verification.output_hash != run.result.output_hash:
            raise ValueError("Worker output mismatch")
        receipt = Receipt(
            agent_id=agent.id,
            summary=summary,
            policy=policy,
            output_hash=verification.output_hash,
            consumed_question_ids=[q.id for q in run.questions if q.agent_id == agent.id],
        )

        def save(current: Run) -> None:
            current.receipts.append(receipt)
            next(a for a in current.agents if a.id == agent.id).status = "done"
            usage(current, completion)

        self.store.update(run.id, save)

    @staticmethod
    def _raise_errors(outcomes: list[None | BaseException]) -> None:
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome

    def _fail(self, run_id: str, error: Exception) -> None:
        def failed(run: Run) -> None:
            run.status = "failed"
            run.error = str(error) if isinstance(error, ProviderError) else "执行未完成：内部校验或存储失败。请新建运行；已完成的证据已保留。"
            event(run, "运行停止", run.error)

        self.store.update(run_id, failed)
