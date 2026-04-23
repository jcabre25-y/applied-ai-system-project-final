import streamlit as st

from llm_client import (
    describe_image_prompt,
    evaluate_with_guardrails,
    generate_sentence_activity,
    get_unsplash_image,
)
from logic_utils import (
    build_log_entry,
    choose_next_difficulty,
    choose_prompt,
    evaluate_blank_response,
    parse_text_input,
    update_score,
)

st.set_page_config(page_title="Speech Therapy Image Coach", page_icon="\U0001F5E3\ufe0f", layout="wide")


def reset_round(difficulty: str | None = None):
    selected_difficulty = difficulty or st.session_state.get("difficulty", "Easy")
    prompt = choose_prompt(selected_difficulty, st.session_state.get("used_prompt_ids", []))
    image_details = get_unsplash_image(prompt)
    image_description, description_source = describe_image_prompt(prompt, image_details)
    st.session_state.prompt = prompt
    st.session_state.image_details = image_details
    st.session_state.image_description = image_description
    st.session_state.stage = "naming"
    st.session_state.naming_feedback = None
    st.session_state.blank_activity = None
    st.session_state.blank_feedback = None
    st.session_state.last_sources = {
        "image": image_details["source"],
        "description": description_source,
    }


if "difficulty" not in st.session_state:
    st.session_state.difficulty = "Easy"
if "score" not in st.session_state:
    st.session_state.score = 0
if "completed_rounds" not in st.session_state:
    st.session_state.completed_rounds = 0
if "used_prompt_ids" not in st.session_state:
    st.session_state.used_prompt_ids = []
if "history" not in st.session_state:
    st.session_state.history = []
if "prompt" not in st.session_state:
    reset_round("Easy")

st.title("Speech Therapy Image Coach")
st.caption("Practice naming common objects, then reinforce the word with AI-guided sentence support.")

st.sidebar.header("Session")
difficulty = st.sidebar.selectbox("Starting difficulty", ["Easy", "Normal", "Hard"], index=["Easy", "Normal", "Hard"].index(st.session_state.difficulty))
if difficulty != st.session_state.difficulty:
    st.session_state.difficulty = difficulty
    reset_round(difficulty)

if st.sidebar.button("Start New Round"):
    reset_round(st.session_state.difficulty)
    st.rerun()

st.sidebar.metric("Score", st.session_state.score)
st.sidebar.metric("Completed rounds", st.session_state.completed_rounds)
st.sidebar.caption("Unsplash images are fetched live when available. AI feedback falls back to deterministic rules if an API key is missing.")

prompt = st.session_state.prompt
image_details = st.session_state.image_details
image_description = st.session_state.image_description

left, right = st.columns([1.2, 1])
with left:
    st.subheader("1. Look at the image and name the object")
    try:
        st.image(image_details["image_url"], caption=f"Target concept image from {image_details['credit_name']}", use_container_width=True)
    except Exception:
        st.markdown(f"<div style='font-size: 8rem; text-align: center;'>{prompt['fallback_image']}</div>", unsafe_allow_html=True)
        st.caption("Image fallback is showing because the live image could not load in this environment.")
    st.caption(f"Photo by [{image_details['credit_name']}]({image_details['credit_url']}) on [Unsplash](https://unsplash.com)")
    st.info(f"Therapy hint: {prompt['hint']}")

with right:
    st.subheader("Prompt details")
    st.write(f"Difficulty: **{prompt['difficulty']}**")
    st.write(prompt["concept_description"])
    st.write(f"Image description: {image_description}")
    st.caption(f"Description source: {st.session_state.last_sources.get('description', 'fallback')}")
    st.write("Goal: name the object or concept in the image, then complete a sentence practice activity.")

if st.session_state.stage == "naming":
    with st.form("naming_form", clear_on_submit=True):
        naming_response = st.text_input("What do you see in the picture?")
        naming_submit = st.form_submit_button("Check my answer")

    if naming_submit:
        ok, cleaned, error_message = parse_text_input(naming_response, "Type a word or short phrase to identify the image.")
        if not ok:
            st.error(error_message)
        else:
            naming_feedback, source = evaluate_with_guardrails(cleaned, prompt)
            st.session_state.naming_feedback = naming_feedback
            st.session_state.last_sources["naming"] = source
            st.session_state.score = update_score(st.session_state.score, naming_feedback["match_status"])
            if naming_feedback["match_status"] in {"correct", "close"}:
                activity, sentence_source = generate_sentence_activity(prompt)
                st.session_state.blank_activity = activity
                st.session_state.last_sources["sentence"] = sentence_source
                st.session_state.stage = "sentence"
            st.rerun()

if st.session_state.naming_feedback:
    feedback = st.session_state.naming_feedback
    if feedback["match_status"] == "correct":
        st.success(feedback["feedback"])
    elif feedback["match_status"] == "close":
        st.warning(feedback["feedback"])
    else:
        st.error(feedback["feedback"])
    st.caption(f"Naming confidence: {feedback['confidence']} | source: {st.session_state.last_sources.get('naming', 'fallback')}")

if st.session_state.stage == "sentence" and st.session_state.blank_activity:
    activity = st.session_state.blank_activity
    st.divider()
    st.subheader("2. Fill in the blank")
    st.write("The AI created a short practice sentence from the image context.")
    st.code(activity["blank_sentence"])

    with st.form("blank_form", clear_on_submit=True):
        blank_response = st.text_input("Which word completes the sentence?")
        blank_submit = st.form_submit_button("Submit practice word")

    if blank_submit:
        blank_feedback = evaluate_blank_response(blank_response, activity["blank_answer"])
        st.session_state.blank_feedback = blank_feedback
        st.session_state.score = update_score(
            st.session_state.score,
            "incorrect",
            blank_feedback["match_status"],
        )
        next_difficulty = choose_next_difficulty(
            st.session_state.difficulty,
            st.session_state.naming_feedback["match_status"],
            blank_feedback["match_status"],
        )
        st.session_state.difficulty = next_difficulty
        st.session_state.completed_rounds += 1
        st.session_state.used_prompt_ids.append(prompt["id"])
        st.session_state.history.append(
            build_log_entry(prompt, st.session_state.naming_feedback, blank_feedback)
        )
        st.session_state.stage = "complete"
        st.rerun()

if st.session_state.blank_feedback:
    blank_feedback = st.session_state.blank_feedback
    if blank_feedback["match_status"] == "correct":
        st.success(blank_feedback["feedback"])
    else:
        st.error(blank_feedback["feedback"])

if st.session_state.stage == "complete":
    st.divider()
    st.success(f"Round complete. Your next prompt will start at {st.session_state.difficulty} difficulty.")
    if st.button("Load next prompt"):
        reset_round(st.session_state.difficulty)
        st.rerun()

with st.expander("Reliability and debug log"):
    st.write("Current sources:", st.session_state.get("last_sources", {}))
    st.write("Session history:", st.session_state.history)
    st.write("Current prompt id:", prompt["id"])
    st.write("Target word:", prompt["target_word"])
