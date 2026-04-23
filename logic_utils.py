from __future__ import annotations

import random
import re
from typing import Dict, List, Tuple

from prompt_data import PROMPTS

DIFFICULTY_ORDER = ["Easy", "Normal", "Hard"]


def normalize_text(value: str) -> str:
    if value is None:
        return ""

    cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    return " ".join(cleaned.split())


def parse_text_input(raw: str, empty_message: str) -> Tuple[bool, str, str | None]:
    cleaned = normalize_text(raw)
    if not cleaned:
        return False, "", empty_message
    return True, cleaned, None


def get_prompts_for_difficulty(difficulty: str) -> List[Dict[str, str]]:
    prompts = [prompt for prompt in PROMPTS if prompt["difficulty"] == difficulty]
    return prompts or PROMPTS[:]


def choose_prompt(difficulty: str, used_prompt_ids: List[str]) -> Dict[str, str]:
    prompts = get_prompts_for_difficulty(difficulty)
    available = [prompt for prompt in prompts if prompt["id"] not in used_prompt_ids]
    choices = available or prompts
    return random.choice(choices)


def response_matches_target(response: str, acceptable_answers: List[str]) -> bool:
    normalized = normalize_text(response)
    accepted = {normalize_text(answer) for answer in acceptable_answers}
    return normalized in accepted


def evaluate_naming_response(user_response: str, prompt: Dict[str, str]) -> Dict[str, str | float]:
    normalized = normalize_text(user_response)
    target = prompt["target_word"]

    if response_matches_target(normalized, prompt["acceptable_answers"]):
        return {
            "match_status": "correct",
            "confidence": 0.96,
            "feedback": f"Nice work. You correctly identified the {target}.",
            "next_step": "advance",
        }

    if normalized and any(normalized in normalize_text(answer) or normalize_text(answer) in normalized for answer in prompt["acceptable_answers"]):
        return {
            "match_status": "close",
            "confidence": 0.62,
            "feedback": f"That is close. Think about the exact therapy word: {target}.",
            "next_step": "show_hint",
        }

    return {
        "match_status": "incorrect",
        "confidence": 0.22,
        "feedback": f"Not quite yet. Try again and use the image plus the hint if needed.",
        "next_step": "retry",
    }


def build_fallback_sentence(prompt: Dict[str, str]) -> str:
    target = prompt["target_word"]
    templates = {
        "apple": "I eat an apple for a healthy snack.",
        "ball": "The child kicked the ball across the yard.",
        "chair": "Please sit in the chair by the table.",
        "umbrella": "She opened the umbrella when it started to rain.",
        "bicycle": "He rides his bicycle to the park after school.",
        "stethoscope": "The doctor used a stethoscope during the checkup.",
    }
    return templates.get(target, f"I can say the word {target} in a clear sentence.")


def create_blank_activity(sentence: str, target_word: str) -> Dict[str, str]:
    pattern = re.compile(rf"\b{re.escape(target_word)}\b", flags=re.IGNORECASE)
    blanked, count = pattern.subn("_____", sentence, count=1)

    if count == 0:
        sentence = f"The picture shows a {target_word}."
        blanked = sentence.replace(target_word, "_____", 1)

    return {
        "generated_sentence": sentence,
        "blank_sentence": blanked,
        "blank_answer": target_word,
    }


def evaluate_blank_response(user_response: str, blank_answer: str) -> Dict[str, str | float]:
    normalized = normalize_text(user_response)
    expected = normalize_text(blank_answer)

    if not normalized:
        return {
            "match_status": "incorrect",
            "confidence": 0.0,
            "feedback": "Type a word to complete the sentence.",
            "next_step": "retry",
        }

    if normalized == expected:
        return {
            "match_status": "correct",
            "confidence": 0.93,
            "feedback": "Great job. You filled in the practice sentence correctly.",
            "next_step": "advance",
        }

    return {
        "match_status": "incorrect",
        "confidence": 0.18,
        "feedback": f"That word does not fit the practice sentence. Try the target word '{blank_answer}'.",
        "next_step": "retry",
    }


def update_score(current_score: int, naming_result: str, blank_result: str | None = None) -> int:
    score = current_score
    if naming_result == "correct":
        score += 15
    elif naming_result == "close":
        score += 5

    if blank_result == "correct":
        score += 10

    return score


def choose_next_difficulty(current_difficulty: str, naming_result: str, blank_result: str | None) -> str:
    index = DIFFICULTY_ORDER.index(current_difficulty)

    if naming_result == "correct" and blank_result == "correct":
        return DIFFICULTY_ORDER[min(index + 1, len(DIFFICULTY_ORDER) - 1)]

    if naming_result == "incorrect":
        return DIFFICULTY_ORDER[max(index - 1, 0)]

    return current_difficulty


def build_log_entry(prompt: Dict[str, str], naming_feedback: Dict[str, str | float], blank_feedback: Dict[str, str | float] | None) -> Dict[str, str]:
    return {
        "prompt_id": prompt["id"],
        "target_word": prompt["target_word"],
        "naming_result": str(naming_feedback["match_status"]),
        "blank_result": "" if blank_feedback is None else str(blank_feedback["match_status"]),
    }
