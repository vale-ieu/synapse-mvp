import os, json
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# DEMO / fallback: niente chiamate API se non vuoi o non puoi usare i crediti
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Importa OpenAI solo se non siamo in demo
client = None
if not DEMO_MODE:
    from openai import OpenAI, OpenAIError
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from prompts import PLAN_PROMPT, TUTOR_PROMPT

def _fallback_plan(topic: str, level: str, time_per_day: int) -> dict:
    return {
        "overview": f"A concise plan to learn {topic} at {level} level in {time_per_day} min/day.",
        "steps": [
            {
                "title": "Foundations",
                "objective": f"Understand the core ideas of {topic}.",
                "theory_outline": ["Key terms", "Core principles", "Typical pitfalls"],
                "practice_tasks": ["Summarize in 5 bullets", "Explain to a friend in 3 minutes"],
                "suggested_resources": ["Search: official docs", "YouTube: crash course"]
            },
            {
                "title": "Guided Examples",
                "objective": "See concepts in action.",
                "theory_outline": ["2–3 worked examples"],
                "practice_tasks": ["Replicate examples", "Note where you get stuck"],
                "suggested_resources": ["Blog walkthroughs", "Tutorial playlist"]
            },
            {
                "title": "Structured Practice",
                "objective": "Build fluency.",
                "theory_outline": ["Patterns & heuristics"],
                "practice_tasks": ["3 short exercises", "Keep a mistake log"],
                "suggested_resources": ["Practice websites", "Short quizzes"]
            },
            {
                "title": "Mini Project",
                "objective": "Apply end-to-end.",
                "theory_outline": ["Plan → Build → Review"],
                "practice_tasks": ["Small project", "150-word reflection"],
                "suggested_resources": ["Starter template", "Checklists"]
            },
            {
                "title": "Review & Next Steps",
                "objective": "Consolidate and extend.",
                "theory_outline": ["What you know / don’t know"],
                "practice_tasks": ["Teach-back in 5 bullets", "Plan next week"],
                "suggested_resources": ["Advanced playlist", "Community/forum"]
            },
        ],
        "review_strategy": [
            "Spaced review on Day 2, 4, 7",
            "Turn mistakes into flashcards",
            "Teach-back after each session"
        ],
        "_meta": {"source": "fallback"}
    }

def generate_plan(topic: str, level: str = "beginner", time_per_day: int = 30) -> dict:
    if DEMO_MODE or client is None:
        return _fallback_plan(topic, level, time_per_day)
    try:
        # chiamata reale (funzionerà quando avrai credito)
        prompt = PLAN_PROMPT.format(topic=topic, level=level, time_per_day=time_per_day)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = resp.choices[0].message.content
        try:
            return json.loads(text)
        except Exception:
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start:end+1]) if start != -1 and end != -1 else {"raw": text}
    except Exception as e:  # include insufficient_quota
        plan = _fallback_plan(topic, level, time_per_day)
        plan["_error"] = str(e)
        return plan

def tutor_answer(plan_context: dict, question: str) -> str:
    if DEMO_MODE or client is None:
        return (
            f"Demo mode — no API call.\n"
            f"Q: {question}\n"
            f"Tip: follow the next step in your plan, do one tiny practice task, "
            f"and write down the smallest sub-question blocking you."
        )
    ctx = json.dumps({k: plan_context.get(k) for k in ("overview", "steps")})
    prompt = TUTOR_PROMPT.format(plan_context=ctx, question=question)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()
