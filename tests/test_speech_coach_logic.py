from logic_utils import (
    build_fallback_sentence,
    choose_next_difficulty,
    create_blank_activity,
    evaluate_blank_response,
    evaluate_naming_response,
    normalize_text,
    response_matches_target,
    update_score,
)
from prompt_data import PROMPTS
from llm_client import describe_image_prompt


def get_prompt(prompt_id: str):
    for prompt in PROMPTS:
        if prompt["id"] == prompt_id:
            return prompt
    raise ValueError(prompt_id)


def test_normalize_text_strips_case_and_punctuation():
    assert normalize_text(" Apple! ") == "apple"


def test_response_matches_target_accepts_synonym():
    prompt = get_prompt("bicycle")
    assert response_matches_target("bike", prompt["acceptable_answers"]) is True


def test_evaluate_naming_response_marks_exact_match_correct():
    prompt = get_prompt("apple")
    result = evaluate_naming_response("apple", prompt)
    assert result["match_status"] == "correct"


def test_evaluate_naming_response_marks_wrong_answer_incorrect():
    prompt = get_prompt("chair")
    result = evaluate_naming_response("table", prompt)
    assert result["match_status"] == "incorrect"


def test_create_blank_activity_replaces_target_word():
    activity = create_blank_activity("I eat an apple for lunch.", "apple")
    assert "_____" in activity["blank_sentence"]
    assert activity["blank_answer"] == "apple"


def test_create_blank_activity_has_guardrail_when_target_missing():
    activity = create_blank_activity("This sentence forgot the keyword.", "umbrella")
    assert activity["blank_sentence"] == "The picture shows a _____."


def test_evaluate_blank_response_accepts_correct_word():
    result = evaluate_blank_response("apple", "apple")
    assert result["match_status"] == "correct"


def test_update_score_rewards_naming_and_sentence_success():
    assert update_score(0, "correct", "correct") == 25


def test_choose_next_difficulty_advances_on_full_success():
    assert choose_next_difficulty("Easy", "correct", "correct") == "Normal"


def test_choose_next_difficulty_drops_on_failure():
    assert choose_next_difficulty("Normal", "incorrect", None) == "Easy"


def test_build_fallback_sentence_contains_target_word():
    sentence = build_fallback_sentence(get_prompt("stethoscope"))
    assert "stethoscope" in sentence.lower()


def test_describe_image_prompt_prefers_unsplash_metadata():
    prompt = get_prompt("apple")
    description, source = describe_image_prompt(prompt, {"image_description": "A red apple on a table."})
    assert description == "A red apple on a table."
    assert source == "unsplash-metadata"
