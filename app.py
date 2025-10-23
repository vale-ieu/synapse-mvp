import os, json
import streamlit as st
from ai import generate_plan, tutor_answer
from db import upsert_user, save_plan, list_plans, get_progress_map, set_progress

st.set_page_config(page_title="Synapse MVP", page_icon="🧠", layout="wide")
import os
if os.getenv("DEMO_MODE", "false").lower() == "true":
    st.warning("DEMO MODE attivo: nessuna chiamata OpenAI. Attiva Billing e metti DEMO_MODE=false per usare l'AI reale.", icon="⚠️")


# Banner + demo mode notice
st.markdown("<h1 style='color:#7B61FF'>Synapse — Learn smarter.</h1>", unsafe_allow_html=True)
if os.getenv("DEMO_MODE", "false").lower() == "true":
    st.warning("DEMO MODE attivo: i piani sono generati senza chiamare l'API OpenAI. Per sbloccare l'AI reale: attiva Billing su OpenAI e metti DEMO_MODE=false.", icon="⚠️")

# --- Sidebar: mock sign-in ---
with st.sidebar:
    st.subheader("Sign in (mock)")
    email = st.text_input("Email", placeholder="you@example.com")
    if st.button("Continue") and email:
        st.session_state["user"] = upsert_user(email)
    if "user" in st.session_state:
        st.success(f"Signed in as {st.session_state['user']['email']}")

if "user" not in st.session_state:
    st.info("Sign in (left) to generate and save your learning plan.")
    st.stop()

user = st.session_state["user"]

# --- Plan Generator ---
st.write("### Generate your learning plan")
col1, col2, col3 = st.columns([2,1,1])
with col1:
    topic = st.text_input("What do you want to learn?", placeholder="e.g., Thermodynamics basics")
with col2:
    level = st.selectbox("Level", ["beginner","intermediate","advanced"])
with col3:
    time_per_day = st.number_input("Minutes/day", 15, 180, 30, 5)

goals = st.text_area("Your goal (optional)", placeholder="Exam, project, career...")

if st.button("Generate & Save", type="primary", use_container_width=True):
    if not topic.strip():
        st.error("Please enter a topic.")
    else:
        with st.spinner("Preparing your plan..."):
            plan = generate_plan(topic, level, time_per_day)
            saved = save_plan(user["id"], topic, level, goals, plan)
            st.session_state["current_plan"] = saved
        st.success("Plan saved!")

# --- Existing Plans ---
plans = list_plans(user["id"])
st.write("### Your plans")
if not plans:
    st.info("No plans yet. Create your first plan above.")
    st.stop()

def _plan_label(p):
    return f"{p['topic']} — {p['created_at'][:19].replace('T',' ')}"

idx = st.selectbox("Select a plan", options=list(range(len(plans))), format_func=lambda i: _plan_label(plans[i]))
current_plan = plans[idx]

st.divider()
st.subheader(f"Plan: {current_plan['topic']}  ·  Level: {current_plan['level']}")
plan_json = current_plan["plan_json"]
st.caption(plan_json.get("overview",""))

# --- Steps & Progress ---
progress_map = get_progress_map(current_plan["id"])
steps = plan_json.get("steps", [])

for i, step in enumerate(steps):
    with st.expander(f"Step {i+1}: {step.get('title','')}", expanded=(i==0)):
        st.markdown("**Objective**: " + step.get("objective",""))
        if step.get("theory_outline"):
            st.markdown("**Theory**")
            for b in step["theory_outline"]:
                st.markdown(f"- {b}")
        if step.get("practice_tasks"):
            st.markdown("**Practice**")
            for t in step["practice_tasks"]:
                st.markdown(f"- {t}")
        if step.get("suggested_resources"):
            st.markdown("**Resources**")
            for r in step["suggested_resources"]:
                st.markdown(f"- {r}")

        # Progress control
        cur = progress_map.get(i, "todo")
        status = st.selectbox(
            "Status",
            ["todo","doing","done"],
            index=["todo","doing","done"].index(cur),
            key=f"st_{i}"
        )
        if st.button("Save status", key=f"sv_{i}"):
            set_progress(current_plan["id"], i, status)
            st.success("Saved")

# Review strategy
if plan_json.get("review_strategy"):
    st.markdown("**Review strategy**")
    for b in plan_json["review_strategy"]:
        st.markdown(f"- {b}")

# --- Tutor chat (works in demo with a generic advice) ---
st.write("### Ask Synapse (Tutor)")
q = st.text_input("Your question about this plan")
if st.button("Ask"):
    if not q.strip():
        st.error("Please type a question.")
    else:
        with st.spinner("Thinking..."):
            answer = tutor_answer(plan_json, q)
        st.info(q)
        st.success(answer)
