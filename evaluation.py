from llm_client import evaluate_with_guardrails, generate_sentence_activity, get_last_llm_status
from logic_utils import evaluate_blank_response
from prompt_data import PROMPTS


CASES = [
    ("apple", "apple", "apple", "exact match"),
    ("ball", "sports ball", "ball", "synonym accepted"),
    ("chair", "table", "chair", "incorrect naming"),
]


def find_prompt(prompt_id: str):
    for prompt in PROMPTS:
        if prompt["id"] == prompt_id:
            return prompt
    raise ValueError(f"Unknown prompt id: {prompt_id}")


def run_evaluation():
    passed = 0
    results = []

    for prompt_id, naming_response, blank_response, label in CASES:
        prompt = find_prompt(prompt_id)
        naming_feedback, naming_source = evaluate_with_guardrails(naming_response, prompt)
        activity, sentence_source = generate_sentence_activity(prompt)
        blank_feedback = evaluate_blank_response(blank_response, activity["blank_answer"])
        case_passed = naming_feedback["match_status"] in {"correct", "close"} if label != "incorrect naming" else naming_feedback["match_status"] == "incorrect"
        if label != "incorrect naming":
            case_passed = case_passed and blank_feedback["match_status"] == "correct"

        if case_passed:
            passed += 1

        results.append(
            {
                "label": label,
                "prompt": prompt["target_word"],
                "naming_status": naming_feedback["match_status"],
                "blank_status": blank_feedback["match_status"],
                "naming_source": naming_source,
                "sentence_source": sentence_source,
                "llm_status": get_last_llm_status(),
                "passed": case_passed,
            }
        )

    print(f"Evaluation summary: {passed}/{len(CASES)} cases passed")
    for result in results:
        print(
            f"- {result['label']}: naming={result['naming_status']} "
            f"blank={result['blank_status']} "
            f"sources=({result['naming_source']}, {result['sentence_source']}) "
            f"llm_status={result['llm_status']} "
            f"passed={result['passed']}"
        )


if __name__ == "__main__":
    run_evaluation()
