import asyncio
import json
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, JsonValue, TypeAdapter, ValidationError


class ProviderError(Exception):
    """A safe, user-facing provider error; never contains response bodies."""


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen3.8-flash"

    @classmethod
    def from_env(cls) -> "Settings":
        base = os.getenv("ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        url = urlsplit(base)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("ALIYUN_BASE_URL 必须是无凭据、查询参数和片段的 HTTPS 地址。")
        return cls(api_key=os.getenv("ALIYUN_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")), base_url=base, model=os.getenv("ASKLESS_MODEL", "qwen3.8-flash"))


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Message(BaseModel):
    content: str


class Choice(BaseModel):
    message: Message
    finish_reason: str | None = None


class ChatResponse(BaseModel):
    choices: list[Choice] = Field(min_length=1)
    usage: Usage = Field(default_factory=Usage)


@dataclass
class Completion:
    data: dict[str, JsonValue]
    input_tokens: int
    output_tokens: int
    requests: int


class LLMClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    async def json_reply(self, system: str, prompt: str, max_tokens: int) -> Completion:
        if not self.settings.api_key:
            raise ProviderError("阿里云 API 凭据未配置。")
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=45, trust_env=False, transport=self.transport) as client:
            for attempt in range(2):
                try:
                    response = await client.post(
                        self.settings.base_url + "/chat/completions", headers={"Authorization": "Bearer " + self.settings.api_key}, json=payload
                    )
                except httpx.HTTPError:
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    raise ProviderError("阿里云请求超时或网络不可用。") from None
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    await asyncio.sleep(1)
                    continue
                if response.status_code != 200:
                    raise ProviderError(f"阿里云 API 返回 HTTP {response.status_code}；请检查模型权限、额度或配置。")
                return self._decode(response, attempt + 1)
        raise ProviderError("阿里云请求未完成。")

    @staticmethod
    def _decode(response: httpx.Response, requests: int) -> Completion:
        try:
            message = ChatResponse.model_validate(response.json())
            if message.choices[0].finish_reason == "length":
                raise ProviderError("模型输出超过本次长度限额，请重试。")
            data = TypeAdapter(dict[str, JsonValue]).validate_python(json.loads(message.choices[0].message.content))
            return Completion(data, message.usage.prompt_tokens, message.usage.completion_tokens, requests)
        except (ValidationError, ValueError, IndexError):
            raise ProviderError("模型返回了无效的 JSON 结构，请重试。") from None
