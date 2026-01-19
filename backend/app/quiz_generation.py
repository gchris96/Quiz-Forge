import json
import os
import re
import urllib.request
from copy import deepcopy
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_SCRAPE_CHARS = 3500


def ensure_prompt_coverage(prompt: str, quiz_content: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(quiz_content)
    prompt_text = prompt.strip()
    if not prompt_text:
        return normalized

    needle = prompt_text.lower()
    title = str(normalized.get("title", ""))
    questions = normalized.get("questions", [])
    prompts = " ".join(str(question.get("prompt", "")) for question in questions)

    if needle not in title.lower() and needle not in prompts.lower():
        normalized["title"] = f"{prompt_text} Quiz"
    return normalized


def scrape_web_page(url: str) -> str:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "QuizForgeBot/1.0"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read()
    except Exception as exc:
        return f"Unable to fetch {url}: {exc}"

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.stripped_strings)
    return text[:MAX_SCRAPE_CHARS]


def _extract_json(payload: str) -> Dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if not match:
            raise ValueError("quiz response was not valid JSON")
        return json.loads(match.group(0))


def _iter_tool_calls(response) -> List[Dict[str, Any]]:
    calls = []
    output = getattr(response, "output", None) or []
    for item in output:
        output_type = getattr(item, "type", None) or item.get("type")
        if output_type not in {"function_call", "tool_call"}:
            continue
        name = getattr(item, "name", None) or item.get("name")
        arguments = getattr(item, "arguments", None) or item.get("arguments")
        tool_call_id = getattr(item, "id", None) or item.get("id")
        calls.append({"name": name, "arguments": arguments, "id": tool_call_id})
    return calls


def _iter_chat_tool_calls(message) -> List[Dict[str, Any]]:
    tool_calls = getattr(message, "tool_calls", None) or []
    calls = []
    for call in tool_calls:
        function = getattr(call, "function", None) or {}
        calls.append(
            {
                "name": getattr(function, "name", None) or function.get("name"),
                "arguments": getattr(function, "arguments", None)
                or function.get("arguments"),
                "id": getattr(call, "id", None) or call.get("id"),
            }
        )
    return calls


def _run_tool_calls(client: OpenAI, response) -> Optional[str]:
    tool_calls = _iter_tool_calls(response)
    if not tool_calls:
        return None

    tool_outputs = []
    for call in tool_calls:
        if call["name"] != "scrape_web_page":
            continue
        args = json.loads(call["arguments"] or "{}")
        url = args.get("url", "").strip()
        if not url.startswith(("http://", "https://")):
            result = "Invalid URL provided."
        else:
            result = scrape_web_page(url)
        tool_outputs.append(
            {
                "type": "tool_output",
                "tool_call_id": call["id"],
                "output": result,
            }
        )

    if not tool_outputs:
        return None

    followup = client.responses.create(
        model=MODEL_NAME,
        input=tool_outputs,
        previous_response_id=response.id,
    )
    return getattr(followup, "output_text", None) or ""


def _run_chat_tool_calls(
    client: OpenAI, messages: List[Dict[str, Any]], message
) -> Optional[str]:
    tool_calls = _iter_chat_tool_calls(message)
    if not tool_calls:
        return None

    tool_outputs = []
    for call in tool_calls:
        if call["name"] != "scrape_web_page":
            continue
        args = json.loads(call["arguments"] or "{}")
        url = args.get("url", "").strip()
        if not url.startswith(("http://", "https://")):
            result = "Invalid URL provided."
        else:
            result = scrape_web_page(url)
        tool_outputs.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            }
        )

    if not tool_outputs:
        return None

    followup = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages + [message] + tool_outputs,
    )
    return followup.choices[0].message.content or ""


def generate_quiz_content(prompt: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a quiz author. Use web search and the scrape_web_page tool "
        "to ground answers. Respond only with raw JSON (no markdown). "
        "JSON schema: {title: string, questions: [{prompt: string, "
        "options: [{key: 'A'|'B'|'C'|'D', text: string}], "
        "correct_option_key: 'A'|'B'|'C'|'D', explanation: string}]}."
    )
    user_prompt = (
        f"Generate exactly 5 multiple-choice questions about: {prompt}. "
        "Each question must have 4 options with keys A, B, C, D and exactly "
        "one correct_option_key. Keep prompts factual and concise. "
        "Return JSON only."
    )
    function_tool = {
        "type": "function",
        "function": {
            "name": "scrape_web_page",
            "description": "Fetch and summarize visible text from a URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    }
    try:
        if hasattr(client, "responses"):
            response = client.responses.create(
                model=MODEL_NAME,
                tools=[{"type": "web_search"}, function_tool],
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            output_text = getattr(response, "output_text", None) or ""
            tool_output = _run_tool_calls(client, response)
            if tool_output:
                output_text = tool_output
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=[function_tool],
            )
            message = response.choices[0].message
            output_text = message.content or ""
            tool_output = _run_chat_tool_calls(client, messages, message)
            if tool_output:
                output_text = tool_output
    except Exception as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc
    try:
        quiz_content = _extract_json(output_text)
    except Exception as exc:
        raise RuntimeError(f"OpenAI response parse failed: {exc}") from exc
    return ensure_prompt_coverage(prompt, quiz_content)
