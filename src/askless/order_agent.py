"""One data agent proposes questions; the executor owns every policy meaning."""

import json
from typing import Literal

from pydantic import Field, JsonValue, ValidationError

from askless.llm import Completion, LLMClient, ProviderError
from askless.models import Model
from askless.orders import ORDER_DECISIONS, order_profile
from askless.sdk import AgentQuestion


class OrderQuestion(Model):
    decision_key: Literal["duplicates", "cancelled", "rounding"]
    prompt: str = Field(min_length=1, max_length=500)


class OrderProposal(Model):
    summary: str = Field(min_length=1, max_length=600)
    questions: list[OrderQuestion] = Field(max_length=3)


async def propose_order_questions(client: LLMClient, data: JsonValue) -> tuple[tuple[AgentQuestion, ...], Completion, str]:
    prompt = json.dumps(
        {
            "task": "Prepare an auditable USD order summary. Preserve discarded records and ask about unresolved business choices.",
            "profile": order_profile(data),
            "contracts": [{"key": decision.key, "prompt": decision.prompt, "options": decision.options} for decision in ORDER_DECISIONS],
            "semantics": "Deduplicate by exact order ID in input order, then filter cancellations. Rounding uses decimal ROUND_HALF_UP.",
            "required_output": {"summary": "Brief explanation", "questions": [{"decision_key": "a registered key", "prompt": "one question"}]},
            "instructions": "Ask only questions you consider relevant based on this profile. A subset, including no questions, is valid. Each key at most once. Do not select options or claim you have executed branches.",
        }
    )
    completion = await client.json_reply(
        "You are a data-processing agent. Propose relevant questions within the supplied contracts. Return only JSON.", prompt, 1200
    )
    try:
        draft = OrderProposal.model_validate(completion.data, strict=True)
        if len({question.decision_key for question in draft.questions}) != len(draft.questions):
            raise ValueError("Duplicate contract")
        questions = tuple(
            AgentQuestion(f"orders-{question.decision_key}", "order-agent", question.decision_key, question.prompt) for question in draft.questions
        )
    except (ValidationError, ValueError):
        raise ProviderError("Order agent questions failed contract validation.") from None
    return questions, completion, draft.summary
