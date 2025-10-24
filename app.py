import os
import json
import streamlit as st
from ai import generate_plan, tutor_answer
from db import (
    upsert_user, save_plan, list_plans,
    get_progress_map, set_progress,
    update_plan_topic, delete_plan,
)

st.set_page_config(page_title="Synapse MVP", page_icon="🧠", layout="wide")

# ---------------- Banner DEMO MODE ----------------
if os.getenv("DEMO_MODE", "false").lower() == "true":
    st.warning(
        "⚠️ DEMO MODE attivo: nessuna chiamata OpenAI. "
        "Imposta DEMO_MODE=false e configura OPENAI_API_KEY per usare l'AI."
    )

# ---------------- Titolo ----------------
st.markdown("<h1 style='color:#7B61FF'>Synapse — Learn smarter.</h1>", unsafe_allow_html=True)

# ---------------- CSS per expander colorati ----------------
st.markdown("""
<style>
.step-todo  [data-testid="stExpander"] summary,
.step-todo  [data-testid="stExpander"] div[role="button"],
.step-doing [data-testid="stExpander"] summary,
.step-doing [data-testid="stExpander"] div[role="button"],
.step-done  [data-testid="stExpander"] summary,
.step-done  [data-testid="stExpander"] div[role="button"] {
  border-radius: 10px !important;
  border: 1px solid transparent !important;
  font-weight: 700 !important;
  transition: background .15s ease, border-color .15s ease;
}
.step-todo  [data-testid="stExpander"] summary,
.step-todo  [data-testid="stExpander"] div[role="button"] {
  background: rgba(185, 28, 28, 0.20) !important;
  border-color: rgba(185, 28, 28, 0.45) !important;
  color: #fff !important;
}
.step-doing [data-testid="stExpander"] summary,
.step-doing [data-testid="stExpander"] div[role="button"] {
  background: rgba(245, 158, 11, 0.25) !important;
  border-color: rgba(245, 158, 11, 0.55) !important;
  color: #111 !important;
}
.step-done  [data-testid="stExpander"] summary,
.step-done  [data-testid="stExpander"] div[role="button"] {
  background: rgba(34, 197, 94, 0.25) !important;
  border-color: rgba(34, 197, 94, 0.55) !important;
  color: #111 !important;
}
</style>
""", unsafe_allow_html=True)

# ========================= Helpers =========================
def plan_completion_percent(plan) -> int:
    """Calcola la % completamento per un piano."""
    pj = plan["plan_json"]
    if isinstance(pj, str):
        try:
            pj = json.loads(pj)
        except Exception:
            pj = {}
    steps = pj.get("steps", [])
    if not steps:
        return 0
    pm = get_progress_map(plan["id"])
    done = sum(1 for i in range(len(steps)) if pm.get(i, "to-do") == "done")
    return int((done / len(steps)) * 100)

# =========================================================
# Sidebar: mock sign-in + new plan + lista piani
# =========================================================
with st.sidebar:
    st.subheader("Sign in (mock)")
    email = st.text_input("Email", placeholder="you@example.com", key="sb_email")
    if st.button("Continue", key="sb_continue") and email:
        st.session_state["user"] = upsert_user(email)

    if "user" in st.session_state:
        st.success(f"Signed in as {st.session_state['user']['email']}")

        st.markdown("---")
        # -------- Bottone "New plan" --------
        if "show_generator" not in st.session_state:
            st.session_state.show_generator = False

        if st.button("➕ New plan", use_container_width=True, key="btn_new_plan_sidebar"):
            st.session_state.show_generator = True
            st.rerun()

        # -------- Elenco piani --------
        st.subheader("Your plans")

        plans_sidebar = list_plans(st.session_state["user"]["id"])

        # init stato selezione/modali
        if "selected_plan_id" not in st.session_state:
            st.session_state.selected_plan_id = plans_sidebar[0]["id"] if plans_sidebar else None
        if "rename_target" not in st.session_state:
            st.session_state.rename_target = None
        if "delete_target" not in st.session_state:
            st.session_state.delete_target = None

        if not plans_sidebar:
            st.info("No plans yet. Create one with 'New plan'.")
        else:
            for p in plans_sidebar:
                pct = plan_completion_percent(p)
                c1, c2, c3 = st.columns([7, 1, 1])

                selected = p["id"] == st.session_state.selected_plan_id
                label_icon = "📘" if selected else "📁"
                label = f"{label_icon} {p['topic']} — {pct}%"

                if c1.button(label, key=f"sel_{p['id']}", use_container_width=True):
                    st.session_state.selected_plan_id = p["id"]
                    st.session_state.rename_target = None
                    st.session_state.delete_target = None
                    st.rerun()

                if c2.button("✏️", key=f"ed_{p['id']}"):
                    st.session_state.rename_target = p["id"]
                    st.session_state.delete_target = None

                if c3.button("🗑️", key=f"rm_{p['id']}"):
                    st.session_state.delete_target = p["id"]
                    st.session_state.rename_target = None

            # Expander rename
            if st.session_state.rename_target:
                plan_to_edit = next((x for x in plans_sidebar if x["id"] == st.session_state.rename_target), None)
                if plan_to_edit:
                    with st.expander(f"Rename '{plan_to_edit['topic']}'", expanded=True):
                        nn = st.text_input("New name", value=plan_to_edit["topic"], key="sb_rename_input")
                        cc1, cc2 = st.columns(2)
                        if cc1.button("Save", key="sb_rename_save"):
                            if nn.strip():
                                update_plan_topic(plan_to_edit["id"], nn.strip())
                                st.success("Name updated.")
                                st.session_state.rename_target = None
                                st.rerun()
                            else:
                                st.error("Name cannot be empty.")
                        if cc2.button("Cancel", key="sb_rename_cancel"):
                            st.session_state.rename_target = None

            # Expander delete
            if st.session_state.delete_target:
                plan_to_del = next((x for x in plans_sidebar if x["id"] == st.session_state.delete_target), None)
                if plan_to_del:
                    with st.expander(f"Delete '{plan_to_del['topic']}'", expanded=True):
                        st.warning("This will permanently delete the plan and its progress.")
                        conf = st.text_input("Type DELETE to confirm", key="sb_del_conf")
                        disabled = conf.strip().upper() != "DELETE"
                        dcc1, dcc2 = st.columns(2)
                        if dcc1.button("Confirm delete", type="secondary", disabled=disabled, key="sb_del_ok"):
                            delete_plan(plan_to_del["id"])
                            st.success("Plan deleted.")
                            remain = [x for x in plans_sidebar if x["id"] != plan_to_del["id"]]
                            st.session_state.selected_plan_id = remain[0]["id"] if remain else None
                            st.session_state.delete_target = None
                            st.rerun()
                        if dcc2.button("Cancel", key="sb_del_cancel"):
                            st.session_state.delete_target = None

# Se non loggato, fermati qui
if "user" not in st.session_state:
    st.info("Sign in (left) to manage or create your plans.")
    st.stop()

user = st.session_state["user"]

# =========================================================
# Corpo centrale: mostra generatore solo se richiesto
# =========================================================
if st.session_state.get("show_generator", False):
    st.write("### Generate your learning plan")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        topic = st.text_input("What do you want to learn?", placeholder="e.g., Thermodynamics basics")
    with col2:
        level = st.selectbox("Level", ["beginner", "intermediate", "advanced"])
    with col3:
        time_per_day = st.number_input("Minutes/day", 15, 180, 30, 5)

    goals = st.text_area("Your goal (optional)", placeholder="Exam, project, career...")

    cgen, ccancel = st.columns([2, 1])
    if cgen.button("Generate & Save", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("Please enter a topic.")
        else:
            with st.spinner("Preparing your plan..."):
                plan = generate_plan(topic, level, time_per_day)
                saved = save_plan(user["id"], topic, level, goals, plan)
                st.session_state["selected_plan_id"] = saved["id"]
            st.session_state.show_generator = False
            st.success("Plan saved.")
            st.rerun()

    if ccancel.button("Cancel"):
        st.session_state.show_generator = False
        st.rerun()

    st.stop()

# =========================================================
# Mostra dettagli del piano selezionato
# =========================================================
plans = list_plans(user["id"])
current_plan = None
if plans and st.session_state.get("selected_plan_id"):
    current_plan = next((x for x in plans if x["id"] == st.session_state["selected_plan_id"]), None)

if not current_plan:
    st.info("Select or create a plan (left) to view details.")
    st.stop()

st.divider()
st.subheader(f"Plan: {current_plan['topic']}  ·  Level: {current_plan['level']}")

plan_json = current_plan["plan_json"]
if isinstance(plan_json, str):
    try:
        plan_json = json.loads(plan_json)
    except Exception:
        plan_json = {}

st.caption(plan_json.get("overview", ""))

# ---------------- Progress summary ----------------
progress_map = get_progress_map(current_plan["id"])
steps = plan_json.get("steps", [])

total_steps = len(steps)
done_count  = sum(1 for i in range(total_steps) if progress_map.get(i, "to-do") == "done")
doing_count = sum(1 for i in range(total_steps) if progress_map.get(i, "to-do") == "doing")
todo_count  = total_steps - done_count - doing_count
completion  = (done_count / total_steps) if total_steps else 0.0

c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
c1.metric("🔴 To-do",   todo_count)
c2.metric("🟡 Doing",   doing_count)
c3.metric("🟢 Done",    done_count)
with c4:
    st.write("**Completamento**")
    st.progress(completion, text=f"{int(completion*100)}%")

# ---------------- Steps render ----------------
EMOJI = {"todo": "🔴", "doing": "🟡", "done": "🟢"}

for i, step in enumerate(steps):
    cur = progress_map.get(i, "todo")
    badge = EMOJI.get(cur, "🔴")
    title = f"{badge} Step {i+1}: {step.get('title','')}"

    st.markdown(f'<div class="step-{cur}">', unsafe_allow_html=True)

    with st.expander(title, expanded=(i == 0)):
        st.markdown("**Objective**: " + step.get("objective", ""))
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

        status = st.selectbox(
            "Status",
            ["to-do", "doing", "done"],
            index=["todo", "doing", "done"].index(cur),
            key=f"st_{i}"
        )
        if st.button("Save status", key=f"sv_{i}"):
            set_progress(current_plan["id"], i, status)
            st.success("Saved")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Review strategy (se presente) ----------------
if plan_json.get("review_strategy"):
    st.markdown("**Review strategy**")
    for b in plan_json["review_strategy"]:
        st.markdown(f"- {b}")

# ---------------- Tutor chat ----------------
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
