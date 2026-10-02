"""Current OpenRouter web research; no search-preview dependency or new API key."""
import asyncio
import logging
import os

import requests

logger = logging.getLogger(__name__)


def _research_request(prompt: str) -> str:
    model = os.getenv("OPENROUTER_RESEARCH_MODEL", "google/gemini-2.5-flash")
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": (
                    "Search the web for current evidence before writing your report. "
                    "Cite sources and publication dates. Clearly state missing evidence. "
                    "Do not invent sources or use resolved outcomes as forecasts.\n"
                    + prompt
                ),
            }],
            "tools": [{
                "type": "openrouter:web_search",
                "parameters": {
                    "engine": "exa",
                    "max_results": 3,
                    "max_total_results": 6,
                    "max_uses": 2,
                    "max_characters": 2000,
                },
            }],
            "max_tool_calls": 2,
            "max_tokens": 1800,
            "temperature": 0.1,
        },
        timeout=(10, 180),
    )
    # Never log request headers or credentials.
    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter research HTTP {response.status_code}; "
            "check model availability, key permissions and remaining credits."
        )
    data = response.json()
    if data.get("error"):
        raise RuntimeError("OpenRouter returned a research error; check account activity.")
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no research choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned empty research.")
    sources = []
    for annotation in message.get("annotations") or []:
        citation = annotation.get("url_citation") or {}
        url = citation.get("url")
        if url:
            sources.append(f"- {citation.get('title') or 'Source'}: {url}")
    if not sources:
        raise RuntimeError("Web research returned no source citations; refusing an ungrounded forecast.")
    logger.info("Web research model=%s; cited sources=%d", model, len(sources))
    return content + "\n\nSources verified in API response:\n" + "\n".join(sources)


async def research_with_openrouter(prompt: str) -> str:
    return await asyncio.to_thread(_research_request, prompt)
