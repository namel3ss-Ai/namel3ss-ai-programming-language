"""OpenAI-style chat completions provider."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk, TokenUsage
from . import ChatToolResponse, ModelProvider, ToolCallResult

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class OpenAIProvider(ModelProvider):
    """
    OpenAI-compatible chat provider supporting messages, JSON mode, and streaming.
    The http_client/http_stream parameters allow deterministic mocking in tests.
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream
        self._extra_headers = extra_headers or {}

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self._extra_headers)
        return headers

    def _build_body(self, messages: List[Dict[str, str]], json_mode: bool, **kwargs: Any) -> Dict[str, Any]:
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("OpenAI model name is required")
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        tools_payload = kwargs.get("tools")
        if tools_payload:
            normalized_tools: List[Dict[str, Any]] = []
            for tool in tools_payload:
                if "function" in tool:
                    normalized_tools.append(tool)
                else:
                    normalized_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool.get("name"),
                                "description": tool.get("description"),
                                "parameters": tool.get("parameters"),
                            },
                        }
                    )
            body["tools"] = normalized_tools
        tool_choice = kwargs.get("tool_choice")
        if tool_choice:
            body["tool_choice"] = tool_choice
        # Optional parameters
        for key in ("temperature", "top_p", "max_tokens", "seed", "frequency_penalty", "presence_penalty"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]
        return body

    def _parse_usage(self, payload: Dict[str, Any]) -> TokenUsage | None:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None
        return TokenUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> ModelResponse:
        if not self.api_key and "Authorization" not in self._extra_headers:
            raise Namel3ssError("OpenAI API key missing for provider")
        body = self._build_body(messages, json_mode, **kwargs)
        data = self._http_client(self.base_url, body, self._build_headers())
        content = ""
        finish_reason = None
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                choice = choices[0]
                finish_reason = choice.get("finish_reason")
                content = choice.get("message", {}).get("content", "") or ""
        return ModelResponse(
            provider=self.name,
            model=body["model"],
            messages=messages,
            text=content,
            raw=data,
            usage=self._parse_usage(data) if isinstance(data, dict) else None,
            finish_reason=finish_reason,
        )

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        if not self.api_key and "Authorization" not in self._extra_headers:
            raise Namel3ssError("OpenAI API key missing for provider")
        body = self._build_body(messages, json_mode, **kwargs)
        body["stream"] = True
        for chunk in self._http_stream(self.base_url, body, self._build_headers()):
            delta = ""
            finish_reason = None
            if isinstance(chunk, dict):
                choices = chunk.get("choices") or []
                if choices:
                    choice = choices[0]
                    delta = choice.get("delta", {}).get("content", "") or ""
                    finish_reason = choice.get("finish_reason")
            yield ModelStreamChunk(
                provider=self.name,
                model=body["model"],
                delta=delta,
                raw=chunk,
                finish_reason=finish_reason,
                is_final=finish_reason is not None,
            )

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        json_mode: bool = False,
        **kwargs: Any,
    ) -> ChatToolResponse:
        if not self.api_key and "Authorization" not in self._extra_headers:
            raise Namel3ssError("OpenAI API key missing for provider")
        body = self._build_body(messages, json_mode, tools=tools, tool_choice=tool_choice, **kwargs)
        data = self._http_client(self.base_url, body, self._build_headers())
        tool_calls: List[ToolCallResult] = []
        final_text: str | None = None
        finish_reason: str | None = None
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                choice = choices[0]
                finish_reason = choice.get("finish_reason")
                message = choice.get("message") or {}
                final_text = message.get("content")
                for call in message.get("tool_calls") or []:
                    func = call.get("function") or {}
                    name = func.get("name") or call.get("name") or ""
                    args_payload = func.get("arguments") or call.get("arguments") or {}
                    arguments: Dict[str, Any]
                    if isinstance(args_payload, str):
                        try:
                            arguments = json.loads(args_payload)
                        except json.JSONDecodeError:
                            arguments = {"__raw__": args_payload}
                    elif isinstance(args_payload, dict):
                        arguments = args_payload
                    else:
                        arguments = {}
                    tool_calls.append(ToolCallResult(name=name, arguments=arguments))  # type: ignore[call-arg]
        return ChatToolResponse(
            final_text=final_text,
            tool_calls=tool_calls,
            raw=data,
            finish_reason=finish_reason,
        )

    # Default HTTP client implementations (stdlib)
    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _default_http_stream(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Iterable[Dict[str, Any]]:
        # For simplicity, reuse non-streaming client and wrap as a single chunk.
        yield self._default_http_client(url, body, headers)
