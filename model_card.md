# Model Card: Speech Therapy Image Coach

## System Purpose

Speech Therapy Image Coach is a small educational support app that helps users practice identifying common objects and reinforce vocabulary with short sentence activities. It is designed as a classroom portfolio project, not as a substitute for licensed speech-language therapy.

## Base Project

The base project was `ai110-module1show-gameglitchinvestigator-starter`, a Streamlit number guessing game that focused on debugging AI-generated code problems. I reused the Streamlit structure, session state approach, and testing mindset from that project.

## Model And AI Behavior

- Optional model API for supportive response wording and sentence generation
- Deterministic local validation for correctness checks
- Deterministic fallback when the model or Unsplash API is unavailable
- Guardrail logic that can override malformed or conflicting model classifications

## Reliability Summary

- The app includes unit tests for answer matching, sentence blank generation, difficulty progression, and score updates.
- `evaluation.py` provides a small reliability harness with predefined prompt-response cases.
- The app records model or fallback sources in the debug log so it is easier to explain how a result was produced.

## Limitations And Biases

- The project uses typed text instead of real voice input, so it does not evaluate pronunciation, pacing, or articulation.
- The curated prompts are small and may not reflect the full range of objects, dialects, or cultural contexts a learner may encounter.
- Model-generated feedback may still sound repetitive or overly generic even with guardrails.

## Potential Misuse And Mitigation

- This app should not be used to diagnose speech disorders or replace professional clinical guidance.
- It could be misused if someone treats model confidence as a medical judgment, so the app positions confidence as system confidence only.
- Deterministic validation and visible debug logging help reduce silent errors, but they do not remove all risk.

## Testing Reflection

What surprised me most was how important fallback behavior became for reliability. Even when the AI feature is optional, the project needs to keep running in a predictable way so the demo and evaluation do not collapse when an API call fails.

## Collaboration With AI

One helpful AI suggestion was to structure the system as a multi-step workflow instead of a single model call. That made the app easier to explain and test. One flawed AI tendency was pushing broad feature ideas too quickly, which I had to narrow down so the final project stayed feasible inside the existing Streamlit setup.
