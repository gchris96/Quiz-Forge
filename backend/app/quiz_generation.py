# Quiz generation via OpenAI with optional web scraping.
import json
import os
import re
import urllib.request
from copy import deepcopy
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.env import load_environment

load_environment()

MAX_SCRAPE_CHARS = 3500
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20240620"

# Ensure the prompt text appears in the quiz title or question prompts.
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

# Fetch a URL and return the cleaned, visible text for grounding.
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

# Parse JSON from a raw model response, with regex fallback.
def _extract_json(payload: str) -> Dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if not match:
            raise ValueError("quiz response was not valid JSON")
        return json.loads(match.group(0))

# Extract tool call records from a responses API output list.
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

# Extract tool call records from a chat completion message.
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

# Execute scrape tool calls for responses API and return follow-up output.
def _run_tool_calls(client, response, model_name: str) -> Optional[str]:
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
        model=model_name,
        input=tool_outputs,
        previous_response_id=response.id,
    )
    return getattr(followup, "output_text", None) or ""

# Execute scrape tool calls for chat completions and return follow-up output.
def _run_chat_tool_calls(
    client, messages: List[Dict[str, Any]], message, model_name: str
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
        model=model_name,
        messages=messages + [message] + tool_outputs,
    )
    return followup.choices[0].message.content or ""

# Resolve which AI provider to use.
def get_ai_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "claude"}:
        raise RuntimeError("AI_PROVIDER must be 'openai' or 'claude'")
    return provider

# Resolve the env var name for the selected provider's API key.
def get_ai_api_key_env_var(provider: str) -> str:
    if provider == "claude":
        return "CLAUDE_API_KEY"
    return "OPENAI_API_KEY"

# Fetch the API key for the selected provider.
def get_ai_api_key(provider: str) -> Optional[str]:
    return os.getenv(get_ai_api_key_env_var(provider))

# Resolve the model name for the selected provider.
def get_ai_model_name(provider: str) -> str:
    if provider == "claude":
        return os.getenv("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

# Generate quiz content with the configured provider and validate JSON output.
def generate_quiz_content(prompt: str) -> Dict[str, Any]:
    provider = get_ai_provider()
    api_key = get_ai_api_key(provider)
    if not api_key:
        raise RuntimeError(f"{get_ai_api_key_env_var(provider)} is not configured")

    model_name = get_ai_model_name(provider)
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
    try:
        if provider == "claude":
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=1500,
            )
            output_text = ""
            for block in response.content:
                if isinstance(block, dict):
                    output_text += block.get("text", "")
                else:
                    output_text += getattr(block, "text", "")
        else:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
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
            if hasattr(client, "responses"):
                response = client.responses.create(
                    model=model_name,
                    tools=[{"type": "web_search"}, function_tool],
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                output_text = getattr(response, "output_text", None) or ""
                tool_output = _run_tool_calls(client, response, model_name)
                if tool_output:
                    output_text = tool_output
            else:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=[function_tool],
                )
                message = response.choices[0].message
                output_text = message.content or ""
                tool_output = _run_chat_tool_calls(
                    client, messages, message, model_name
                )
                if tool_output:
                    output_text = tool_output
    except Exception as exc:
        raise RuntimeError(f"{provider} request failed: {exc}") from exc
    try:
        quiz_content = _extract_json(output_text)
    except Exception as exc:
        raise RuntimeError(f"OpenAI response parse failed: {exc}") from exc
    return ensure_prompt_coverage(prompt, quiz_content)
