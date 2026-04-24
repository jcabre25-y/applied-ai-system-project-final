from __future__ import annotations

import json
import os
from typing import Dict, Tuple
from urllib import error, parse, request

from dotenv import load_dotenv

from logic_utils import build_fallback_sentence, create_blank_activity, evaluate_naming_response

load_dotenv()
LAST_LLM_STATUS = "not_called"


def _safe_confidence(raw_value: object, fallback_value: float) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return float(fallback_value)


def get_last_llm_status() -> str:
    return LAST_LLM_STATUS


def _set_last_llm_status(status: str) -> None:
    global LAST_LLM_STATUS
    LAST_LLM_STATUS = status


def get_unsplash_image(prompt_record: Dict[str, str]) -> Dict[str, str]:
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    query = parse.quote(prompt_record["search_query"])

    if not access_key:
        return {
            "image_url": f"https://source.unsplash.com/featured/900x600/?{query}",
            "credit_name": prompt_record["credit_name"],
            "credit_url": prompt_record["credit_url"],
            "source": "unsplash-source-fallback",
            "image_description": "",
        }

    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape"
    req = request.Request(
        url,
        headers={
            "Authorization": f"Client-ID {access_key}",
            "Accept-Version": "v1",
        },
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return {
            "image_url": f"https://source.unsplash.com/featured/900x600/?{query}",
            "credit_name": prompt_record["credit_name"],
            "credit_url": prompt_record["credit_url"],
            "source": "unsplash-source-fallback",
            "image_description": "",
        }

    description = payload.get("description") or payload.get("alt_description") or ""

    return {
        "image_url": payload["urls"]["regular"],
        "credit_name": payload["user"]["name"],
        "credit_url": payload["links"]["html"],
        "source": "unsplash-api",
        "image_description": description,
    }


def _post_chat_completion(system_prompt: str, user_prompt: str) -> Dict[str, object] | None:
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    if provider in {"auto", "gemini"} and os.getenv("GEMINI_API_KEY"):
        return _post_gemini_completion(system_prompt, user_prompt)

    if provider in {"auto", "openai"}:
        return _post_openai_completion(system_prompt, user_prompt)

    _set_last_llm_status("no_provider_or_key")
    return None


def _post_openai_completion(system_prompt: str, user_prompt: str) -> Dict[str, object] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        _set_last_llm_status("openai_missing_key")
        return None

    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        _set_last_llm_status(f"openai_request_failed:{type(exc).__name__}")
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        _set_last_llm_status("openai_success")
        return parsed
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        _set_last_llm_status(f"openai_parse_failed:{type(exc).__name__}")
        return None


def _post_gemini_completion(system_prompt: str, user_prompt: str) -> Dict[str, object] | None:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        _set_last_llm_status("gemini_missing_key")
        return None

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"{system_prompt}\n\n"
                            "Return valid JSON only.\n\n"
                            f"{user_prompt}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    req = request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        _set_last_llm_status(f"gemini_request_failed:{type(exc).__name__}")
        return None

    try:
        content = payload["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(content)
        _set_last_llm_status("gemini_success")
        return parsed
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        _set_last_llm_status(f"gemini_parse_failed:{type(exc).__name__}")
        return None


def evaluate_with_guardrails(user_response: str, prompt_record: Dict[str, str]) -> Tuple[Dict[str, object], str]:
    deterministic = evaluate_naming_response(user_response, prompt_record)
    system_prompt = (
        "You are a supportive speech-therapy coach. "
        "Return JSON with keys match_status, confidence, feedback, next_step. "
        "Allowed match_status values: correct, close, incorrect."
    )
    user_prompt = (
        f"Target word: {prompt_record['target_word']}\n"
        f"Acceptable answers: {', '.join(prompt_record['acceptable_answers'])}\n"
        f"Concept description: {prompt_record['concept_description']}\n"
        f"Student answer: {user_response}\n"
        "Give encouraging feedback in one or two sentences."
    )
    model_result = _post_chat_completion(system_prompt, user_prompt)

    if not model_result:
        return deterministic, "fallback"

    normalized = {
        "match_status": model_result.get("match_status", deterministic["match_status"]),
        "confidence": _safe_confidence(
            model_result.get("confidence", deterministic["confidence"]),
            float(deterministic["confidence"]),
        ),
        "feedback": str(model_result.get("feedback", deterministic["feedback"])),
        "next_step": str(model_result.get("next_step", deterministic["next_step"])),
    }

    if normalized["match_status"] != deterministic["match_status"]:
        normalized["match_status"] = deterministic["match_status"]
        normalized["feedback"] = (
            f"{normalized['feedback']} "
            "Guardrail note: local validation overrode the model classification."
        ).strip()

    return normalized, "model"


def generate_sentence_activity(prompt_record: Dict[str, str]) -> Tuple[Dict[str, str], str]:
    fallback_sentence = build_fallback_sentence(prompt_record)
    system_prompt = (
        "You create therapy-friendly practice sentences. "
        "Return JSON with keys generated_sentence and blank_answer. "
        "Use the target word exactly once in the sentence."
    )
    user_prompt = (
        f"Target word: {prompt_record['target_word']}\n"
        f"Concept description: {prompt_record['concept_description']}\n"
        "Write one short supportive sentence appropriate for a young learner."
    )
    model_result = _post_chat_completion(system_prompt, user_prompt)

    if not model_result:
        return create_blank_activity(fallback_sentence, prompt_record["target_word"]), "fallback"

    sentence = str(model_result.get("generated_sentence", fallback_sentence))
    activity = create_blank_activity(sentence, prompt_record["target_word"])
    activity["blank_answer"] = prompt_record["target_word"]
    return activity, "model"


def describe_image_prompt(prompt_record: Dict[str, str], image_details: Dict[str, str]) -> Tuple[str, str]:
    existing_description = str(image_details.get("image_description", "")).strip()
    if existing_description:
        return existing_description, "unsplash-metadata"

    fallback_description = (
        f"This image is meant to show a {prompt_record['target_word']}. "
        f"{prompt_record['concept_description']}"
    )
    system_prompt = (
        "You create short image descriptions for a speech-therapy learning app. "
        "Return JSON with one key named image_description. "
        "Keep the description concrete, child-friendly, and under 20 words."
    )
    user_prompt = (
        f"Target word: {prompt_record['target_word']}\n"
        f"Concept description: {prompt_record['concept_description']}\n"
        f"Unsplash search query: {prompt_record['search_query']}\n"
        "Write a short likely description of the fetched image."
    )
    model_result = _post_chat_completion(system_prompt, user_prompt)

    if not model_result:
        return fallback_description, "fallback"

    description = str(model_result.get("image_description", fallback_description)).strip()
    if not description:
        return fallback_description, "fallback"

    return description, "model"
