from __future__ import annotations

from typing import Protocol


class QueryRewriter(Protocol):
    async def a_rewrite(self, query: str, context) -> str:
        ...


class DeterministicRewriter:
    async def a_rewrite(self, query: str, context) -> str:
        # Lowercase and trim simple stopwords
        return query.strip().lower()


class OpenAIRewriter:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def a_rewrite(self, query: str, context) -> str:
        prompt = f"Rewrite the user query for retrieval: {query}"
        result = self.provider.invoke(messages=[{"role": "user", "content": prompt}])
        return str(result.get("result", query))
