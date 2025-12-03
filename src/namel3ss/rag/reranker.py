from __future__ import annotations

from typing import List, Protocol

from .models import ScoredItem


class Reranker(Protocol):
    async def a_rerank(self, query: str, candidates: List[ScoredItem], context) -> List[ScoredItem]:
        ...


class DeterministicReranker:
    async def a_rerank(self, query: str, candidates: List[ScoredItem], context) -> List[ScoredItem]:
        keyword = query.split()[0].lower() if query else ""
        reranked = []
        for c in candidates:
            bonus = 0.1 if keyword and keyword in c.item.text.lower() else 0.0
            reranked.append(ScoredItem(item=c.item, score=c.score + bonus, source=c.source))
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked


class OpenAIReranker:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def a_rerank(self, query: str, candidates: List[ScoredItem], context) -> List[ScoredItem]:
        # Simple heuristic: append provider signal, keep deterministic ordering if provider unavailable.
        if not candidates:
            return []
        try:
            prompt = f"Given query '{query}', rank the following documents by relevance:\n"
            for idx, c in enumerate(candidates):
                prompt += f"{idx+1}. {c.item.text[:100]}\n"
            result = self.provider.invoke(messages=[{"role": "user", "content": prompt}])
            text = str(result.get("result", ""))
            # naive parse: pick first mentioned index
            ranked = []
            for idx, c in enumerate(candidates):
                bonus = 0.05 * (len(candidates) - idx)
                if str(idx + 1) in text:
                    bonus += 0.1
                ranked.append(ScoredItem(item=c.item, score=c.score + bonus, source=c.source))
            ranked.sort(key=lambda x: x.score, reverse=True)
            return ranked
        except Exception:
            return candidates
