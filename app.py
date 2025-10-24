import os
import json
from pathlib import Path
import streamlit as st
from ai import generate_plan, tutor_answer
from db import upsert_user, save_plan, list_plans, get_progress_map, set_progress, update_plan_topic, delete_plan

# ========================= PAGE CONFIG =========================
st.set_page_config(page_title="Synapse — Learn smarter.", page_icon="🧠", layout="wide")

# ========================= CSS GLOBALE =========================
st.markdown("""
<style>
[data-testid="stSidebar"] img {
    border-radius: 50%;
}
[data-testid="stSidebar"] {
    padding-top: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ========================= Helpers =========================
def plan_completion_percent(plan) -> int:
    """Calcola la % di completamento di un piano."""
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
# Sidebar con logo Synapse e login
# =========================================================
APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "static" / "logo.png"  # percorso assoluto sicuro

with st.sidebar:
    # --- logo in alto, piccolo e centrato ---
    st.markdown(
        "<div style='text-align:center; margin-top:-25px; margin-bottom:-5px;'>",
        unsafe_allow_html=True
    )
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=55)
    else:
        st.warning("Logo non trovato in /static/logo.png")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- titolo login ---
    st.markdown("<h2 style='text-align:center; margin-top:-5px;'>Sign in</h2>", unsafe_allow_html=True)

    # --- form login ---
    email = st.text_input("Email", placeholder="you@example.com", key="sb_email")
    if st.button("Continue", key="sb_continue") and email:
        st.session_state["user"] = upsert_user(email)

    if "user" in st.session_state:
        st.success(f"Signed in as {st.session_state['user']['email']}")

        st.markdown("---")
        # -------- Bottone "New plan" --------
        st.session_state.setdefault("show_generator", False)
        if st.button("➕ New plan", use_container_width=True, key="btn_new_plan_sidebar"):
            st.session_state.show_generator = True
            st.rerun()

        # -------- Elenco piani --------
        st.subheader("Your plans")

        plans_sidebar = list_plans(st.session_state["user"]["id"])

        # init stato selezione/modali
        st.session_state.setdefault("selected_plan_id", plans_sidebar[0]["id"] if plans_sidebar else None)
        st.session_state.setdefault("rename_target", None)          # id del piano che è in modalità edit
        st.session_state.setdefault("rename_value", "")             # valore provvisorio del nome
        st.session_state.setdefault("delete_target", None)
        st.session_state.setdefault("show_delete_modal", False)

        if not plans_sidebar:
            st.info("No plans yet. Create one with 'New plan'.")
        else:
            for p in plans_sidebar:
                pct = plan_completion_percent(p)
                # riga a 3 colonne; se in edit, la prima col diventa un text_input inline
                c1, c2, c3 = st.columns([7, 1, 1])
                selected = p["id"] == st.session_state.selected_plan_id
                icon = "📘" if selected else "📁"

                if st.session_state.rename_target == p["id"]:
                    # --- modalità RINOMINA INLINE ---
                    st.session_state.rename_value = st.session_state.rename_value or p["topic"]
                    new_name = c1.text_input("", value=st.session_state.rename_value, key=f"edit_name_{p['id']}")
                    st.session_state.rename_value = new_name
                    save_col, cancel_col = c2, c3
                    if save_col.button("✅", key=f"save_{p['id']}"):
                        nn = (st.session_state.rename_value or "").strip()
                        if nn:
                            update_plan_topic(p["id"], nn)
                            st.session_state.rename_target = None
                            st.session_state.rename_value = ""
                            st.rerun()
                        else:
                            st.error("Name cannot be empty.")
                    if cancel_col.button("✖️", key=f"cancel_{p['id']}"):
                        st.session_state.rename_target = None
                        st.session_state.rename_value = ""
                        st.rerun()
                else:
                    # --- visualizzazione normale ---
                    label = f"{icon} {p['topic']} — {pct}%"
                    if c1.button(label, key=f"sel_{p['id']}", use_container_width=True):
                        st.session_state.selected_plan_id = p["id"]
                        st.rerun()
                    if c2.button("✏️", key=f"ed_{p['id']}"):
                        st.session_state.rename_target = p["id"]
                        st.session_state.rename_value = p["topic"]
                        st.rerun()
                    if c3.button("🗑️", key=f"rm_{p['id']}"):
                        st.session_state.delete_target = p["id"]
                        st.session_state.show_delete_modal = True
                        st.rerun()

# Se non loggato, fermati qui
if "user" not in st.session_state:
    st.info("Sign in (left) to manage or create your plans.")
    st.stop()

user = st.session_state["user"]

# =========================================================
# POPUP di conferma eliminazione (usa st.dialog come decoratore;
# fallback inline se la tua versione non lo supporta)
# =========================================================
if st.session_state.get("show_delete_modal") and st.session_state.get("delete_target"):
    all_plans = list_plans(user["id"])
    plan_to_del = next((x for x in all_plans if x["id"] == st.session_state["delete_target"]), None)
    plan_name = plan_to_del["topic"] if plan_to_del else "this plan"

    if hasattr(st, "dialog"):
        @st.dialog("Confirm deletion")   # <-- decoratore, non context manager
        def _confirm_delete_dialog():
            st.error(f"Delete '{plan_name}'? This action is permanent.")
            col_ok, col_cancel = st.columns(2)
            if col_ok.button("OK, delete", type="primary", key="dialog_del_ok"):
                delete_plan(st.session_state["delete_target"])
                remaining = [x for x in all_plans if x["id"] != st.session_state["delete_target"]]
                st.session_state.selected_plan_id = remaining[0]["id"] if remaining else None
                st.session_state.delete_target = None
                st.session_state.show_delete_modal = False
                st.rerun()
            if col_cancel.button("Cancel", key="dialog_del_cancel"):
                st.session_state.delete_target = None
                st.session_state.show_delete_modal = False
                st.rerun()

        _confirm_delete_dialog()  # mostra la dialog

    else:
        # Fallback compatibile: piccolo box in pagina
        st.warning(f"Delete '{plan_name}'? This action is permanent.")
        col_ok, col_cancel = st.columns(2)
        if col_ok.button("OK, delete", type="primary", key="fallback_del_ok"):
            delete_plan(st.session_state["delete_target"])
            remaining = [x for x in all_plans if x["id"] != st.session_state["delete_target"]]
            st.session_state.selected_plan_id = remaining[0]["id"] if remaining else None
            st.session_state.delete_target = None
            st.session_state.show_delete_modal = False
            st.rerun()
        if col_cancel.button("Cancel", key="fallback_del_cancel"):
            st.session_state.delete_target = None
            st.session_state.show_delete_modal = False
            st.rerun()


# =========================================================
# Corpo centrale: generatore solo se richiesto
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
