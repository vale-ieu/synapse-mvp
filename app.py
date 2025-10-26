import os
import json
from pathlib import Path
from datetime import date
import streamlit as st
from ai import generate_plan, tutor_answer, generate_exercises_ai, explain_step_ai
from db import (
    upsert_user, save_plan, list_plans,
    get_progress_map, set_progress, update_plan_topic, delete_plan, update_plan_json,
    get_ai_cache, set_ai_cache
)

# ========================= PAGE CONFIG =========================
st.set_page_config(page_title="Synapse — Impara facilmente", page_icon="🧠", layout="wide")

# ---------------- Banner DEMO MODE ----------------
if os.getenv("DEMO_MODE", "false").lower() == "true":
    st.warning(
        "⚠️ DEMO MODE attivo: nessuna chiamata OpenAI. "
        "Imposta DEMO_MODE=false e configura OPENAI_API_KEY per usare l'AI."
    )

# ---------------- Titolo ----------------
st.markdown("<h1 style='color:#7B61FF; margin:0 0 .5rem 0;'>Synapse — Impara meglio</h1>", unsafe_allow_html=True)

# ========================= CSS GLOBALE (NO LINEE/SEPARATORI) =========================
st.markdown("""
<style>
/* ====== RESET GLOBALE DI SEPARATORI/LlNEE/SHADOW ====== */
hr, .stDivider { display:none !important; height:0 !important; margin:0 !important; border:0 !important; }
div[data-testid="stMarkdownContainer"] hr { display:none !important; }
[role="separator"]{ display:none !important; }
button:focus, button:focus-visible { outline:none !important; box-shadow:none !important; }
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]{ border:0 !important; margin:0 !important; padding:0 !important; }

/* ====== SIDEBAR ====== */
section[data-testid="stSidebar"]{ padding-top:.2rem !important; }
section[data-testid="stSidebar"] img{ border-radius:50%; }
/* togli borders/shadow/margins/padding dai wrapper */
section[data-testid="stSidebar"] *{ box-shadow:none !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div{
  border-top:0 !important; margin:0 !important; padding-top:0 !important; padding-bottom:0 !important;
}
/* forza ulteriore rimozione di bordi e spazio residuo */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div{
  border-bottom:0 !important; padding:0 !important; margin:0 !important;
}
/* elimina qualunque separator/pseudo-separator in sidebar */
section[data-testid="stSidebar"] [role="separator"],
section[data-testid="stSidebar"] hr,
section[data-testid="stSidebar"] .stDivider,
section[data-testid="stSidebar"] .stMarkdown hr{
  display:none !important; height:0 !important; margin:0 !important; border:0 !important;
}
/* disinnesca qualsiasi ::before/::after generico in sidebar */
section[data-testid="stSidebar"] *::before,
section[data-testid="stSidebar"] *::after{
  content:none !important; display:none !important; border:0 !important; height:0 !important; margin:0 !important; padding:0 !important;
}

/* titoletti sidebar (niente component Heading → zero linee) */
.sidebar-title{ font-weight:700; font-size:1.05rem; margin:.1rem 0 .1rem 0 !important; }
section[data-testid="stSidebar"] .sidebar-title::before,
section[data-testid="stSidebar"] .sidebar-title::after{ content:none !important; display:none !important; }
section[data-testid="stSidebar"] .stButton>button{ margin:0 !important; }
section[data-testid="stSidebar"] p { margin:.25rem 0 !important; }

/* stack della lista piani (toglie gap interni ai figli) */
.plans-stack [data-testid="stVerticalBlock"]{ margin:0 !important; padding:0 !important; }
.plans-stack [data-testid="column"]{ padding-left:0 !important; padding-right:0 !important; }
.plans-stack div[data-testid="stHorizontalBlock"]{ gap:0 !important; }
.plans-stack{ margin-top:2px !important; }
.plans-stack *{ border:0 !important; box-shadow:none !important; }

/* ---- LISTA PIANI: nessuna barra/linea, spacing compatto ---- */
/* rimuove qualunque bordo/linea generata dai wrapper Streamlit */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div,
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:first-child{
  border:0 !important; box-shadow:none !important; background:transparent !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div::before,
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div::after{
  content:none !important; display:none !important;
}

/* riga piano senza bordo e senza overlay viola */
.planbar{
  position:relative;
  background:#262730 !important;
  border:none !important;
  border-radius:10px !important;
  padding:4px 8px !important;
  margin:0 !important;
  overflow:hidden;
}
.planbar.selected{ box-shadow:0 0 0 2px rgba(180,180,190,.22) inset !important; }
section[data-testid="stSidebar"] .planbar::before{ display:none !important; }

/* bottone riga piatto */
.plan-btn [data-testid="baseButton-primary"],
.plan-btn [data-testid="baseButton-secondary"]{
  background:transparent !important; border:none !important;
  justify-content:flex-start !important; padding:.15rem 0 !important;
  min-height:26px !important; margin:0 !important;
}

/* icone inline a destra, senza tondo separato */
.icon-round [data-testid="baseButton-secondary"]{
  width:auto; height:auto; border-radius:6px;
  background:transparent !important; border:none !important; padding:2px 4px !important;
  display:flex; align-items:center; justify-content:center;
}
.icon-round [data-testid="baseButton-secondary"]:hover{ background:rgba(255,255,255,.06) !important; }
</style>
""", unsafe_allow_html=True)

# ========================= Helpers =========================
def plan_completion_percent(plan) -> int:
    """Calcola la % di completamento di un piano."""
    pj = plan.get("plan_json")
    if isinstance(pj, str):
        try:
            pj = json.loads(pj)
        except Exception:
            pj = {}
    steps = (pj or {}).get("steps", [])
    if not steps:
        return 0
    pm = get_progress_map(plan["id"])
    done = sum(1 for i in range(len(steps)) if pm.get(i, "to-do") == "done")
    return int((done / len(steps)) * 100)

# --- meta per step (solo in memoria per ora) ---
st.session_state.setdefault("step_meta", {})  # { plan_id: { step_idx: {due_date:str, notes:str, attachments:list[str]} } }
def get_step_meta(plan_id: int, step_idx: int) -> dict:
    return st.session_state["step_meta"].get(plan_id, {}).get(step_idx, {})
def set_step_meta(plan_id: int, step_idx: int, meta: dict):
    store = st.session_state["step_meta"].setdefault(plan_id, {})
    cur = store.get(step_idx, {})
    cur.update(meta)
    store[step_idx] = cur

# --- helpers “AI” locali (placeholder) ---
def propose_exercises_for_step(step):
    base = step.get("practice_tasks") or []
    if base:
        return [f"Esercizio guidato: {base[0]}", "Quiz 5 domande (MCQ)", "Riassunto in 120 parole"]
    return ["Applica il concetto a un caso reale", "3 problemi progressivi con soluzione", "10 flashcards"]

def generate_concept_map(plan_json, step_idx=None):
    steps = plan_json.get("steps", [])
    nodes = [{"id": f"s{i}", "label": steps[i].get("title","")} for i in range(len(steps))]
    edges = [{"from": f"s{i}", "to": f"s{i+1}"} for i in range(max(0, len(steps)-1))]
    if step_idx is not None and 0 <= step_idx < len(nodes):
        nodes[step_idx]["label"] = "⭐ " + nodes[step_idx]["label"]
    return {"nodes": nodes, "edges": edges}

# --- helper aggiuntivi: spiegazioni, esercizi dettagliati e mappa come immagine ---
def _level_tone(level: str) -> str:
    return {
        "beginner": "con parole semplici e un esempio concreto",
        "intermediate": "mettendo in relazione i concetti",
        "advanced": "in modo sintetico e formale",
    }.get(level, "in modo chiaro e progressivo")

def explain_points(outline, level: str, topic: str):
    if not outline:
        return []
    tone = _level_tone(level)
    outs = []
    for p in outline:
        outs.append(f"{p}: spiegazione {tone} riferita a '{topic}'.")
    return outs

def propose_detailed_exercises(step: dict, level: str, step_idx: int):
    title = step.get("title", "Passo")
    base = step.get("practice_tasks") or []
    guided_title = base[0] if base else f"Applica i concetti di '{title}'"
    return [
        {
            "type": "guided",
            "title": f"Esercizio guidato: {guided_title}",
            "steps": [
                "Definisci l'obiettivo in 1 frase.",
                "Scegli un esempio reale o un caso di studio.",
                "Applica passo‑passo i concetti del passo attuale.",
                "Scrivi un mini‑report (5 punti) su cosa ha funzionato e cosa no."
            ],
        },
        {
            "type": "quiz",
            "title": "Quiz: 5 domande a scelta multipla",
            "questions": [
                {"q": f"Qual è la finalità principale di '{title}'?", "opts": ["Memorizzare definizioni", "Capire concetti chiave", "Saltare alla pratica", "Nessuna delle precedenti"], "a": 1},
                {"q": "Cosa conviene fare quando ti blocchi?", "opts": ["Ignorare il punto", "Tornare ai principi", "Copiare la soluzione", "Chiudere il libro"], "a": 1},
                {"q": "Quale opzione descrive meglio un errore comune?", "opts": ["Spiegare ad alta voce", "Fare un esempio", "Procedere senza capire", "Confrontare approcci"], "a": 2},
                {"q": "Qual è un buon risultato al termine del passo?", "opts": ["Zero domande", "Un riassunto sintetico", "Niente appunti", "Solo link salvati"], "a": 1},
                {"q": "Quanto lungo dovrebbe essere un recap efficace?", "opts": ["> 500 parole", "1–2 frasi", "120 parole circa", "Nessun limite"], "a": 2}
            ],
            "key": f"quiz_{step_idx}"
        },
        {
            "type": "writing",
            "title": "Riassunto in 120 parole",
            "prompt": f"Scrivi un riassunto (100–140 parole) che spieghi il cuore di '{title}' a livello {level}.",
            "min": 100,
            "max": 140,
            "key": f"write_{step_idx}"
        }
    ]

def build_concept_map_image(plan_json, step_idx=None):
    steps = plan_json.get("steps", [])
    nodes = [{"id": f"s{i}", "label": steps[i].get("title","")} for i in range(len(steps))]
    edges = [{"from": f"s{i}", "to": f"s{i+1}"} for i in range(max(0, len(steps)-1))]
    if step_idx is not None and 0 <= step_idx < len(nodes):
        nodes[step_idx]["label"] = "⭐ " + nodes[step_idx]["label"]
    cm = {"nodes": nodes, "edges": edges}
    # genera SVG lineare semplice
    padding, node_w, node_h, gap = 20, 220, 48, 40
    width = padding*2 + max(1,len(nodes)) * (node_w + gap) - gap
    height = padding*2 + node_h
    pos = {n['id']: (padding + i*(node_w+gap), padding) for i,n in enumerate(nodes)}
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
             "<style>.node{fill:#1f1f28;stroke:#6b6b7a;stroke-width:1.2;rx:10;ry:10} .text{fill:#e6e6f0;font-size:14px;font-family:Inter,Segoe UI,Arial} .edge{stroke:#8a8aa5;stroke-width:1.2;marker-end:url(#arrow)}</style>",
             "<defs><marker id='arrow' markerWidth='10' markerHeight='6' refX='9' refY='3' orient='auto' markerUnits='strokeWidth'><path d='M0,0 L10,3 L0,6 z' fill='#8a8aa5'/></marker></defs>"]
    for e in edges:
        x1,y1 = pos[e['from']]
        x2,y2 = pos[e['to']]
        parts.append(f"<line class='edge' x1='{x1+node_w}' y1='{y1+node_h/2}' x2='{x2}' y2='{y2+node_h/2}' />")
    for n in nodes:
        x,y = pos[n['id']]
        label = (n.get('label') or '').replace('&','&amp;')
        parts.append(f"<rect class='node' x='{x}' y='{y}' width='{node_w}' height='{node_h}' />")
        parts.append(f"<text class='text' x='{x+10}' y='{y+28}'>"+label+"</text>")
    parts.append("</svg>")
    return "".join(parts)

def concept_map_png(plan_json, step_idx=None):
    steps = plan_json.get("steps", [])
    nodes = [{"id": f"s{i}", "label": steps[i].get("title","")} for i in range(len(steps))]
    edges = [{"from": f"s{i}", "to": f"s{i+1}"} for i in range(max(0, len(steps)-1))]
    if step_idx is not None and 0 <= step_idx < len(nodes):
        nodes[step_idx]["label"] = "⭐ " + nodes[step_idx]["label"]

    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    padding, node_w, node_h, gap = 20, 260, 64, 28
    cols = 3
    rows = (len(nodes) + cols - 1) // cols if nodes else 1
    width = padding*2 + cols * node_w + (cols-1) * gap
    height = padding*2 + rows * node_h + (rows-1) * gap

    img = Image.new("RGB", (width, height), (24, 24, 32))
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    positions = {}
    for idx, n in enumerate(nodes):
        r = idx // cols
        c = idx % cols
        x = padding + c * (node_w + gap)
        y = padding + r * (node_h + gap)
        positions[n["id"]] = (x, y)

    def round_rect(x, y, w, h, r=10, outline=(107,107,122)):
        dr.rounded_rectangle([x, y, x+w, y+h], radius=r, outline=outline, width=2, fill=(31,31,40))

    for e in edges:
        x1,y1 = positions[e['from']]
        x2,y2 = positions[e['to']]
        cx1, cy1 = x1 + node_w, y1 + node_h/2
        cx2, cy2 = x2, y2 + node_h/2
        dr.line([(cx1, cy1), (cx2, cy2)], fill=(138,138,165), width=2)
        dr.polygon([(cx2-8, cy2-4), (cx2, cy2), (cx2-8, cy2+4)], fill=(138,138,165))

    for n in nodes:
        x,y = positions[n['id']]
        round_rect(x, y, node_w, node_h)
        label = n.get('label') or ''
        dr.text((x+10, y+node_h/2-6), label, font=font, fill=(230,230,240))

    from io import BytesIO
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def concept_map_radial_png(plan_json, topic: str, step_idx: int | None = None):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    steps = plan_json.get("steps", [])
    labels = [s.get("title","") for s in steps]
    if step_idx is not None and 0<=step_idx<len(labels):
        labels[step_idx] = "⭐ " + labels[step_idx]

    w,h = 900, 600
    img = Image.new("RGB", (w,h), (24,24,32))
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    cx, cy = w//2, h//2
    # nodo centrale
    cw, ch = 260, 70
    dr.rounded_rectangle([cx-cw//2, cy-ch//2, cx+cw//2, cy+ch//2], radius=12, fill=(31,31,40), outline=(107,107,122), width=2)
    dr.text((cx-cw//2+10, cy-8), topic, font=font, fill=(230,230,240))

    import math
    r = min(w,h)//2 - 120
    n = max(1, len(labels))
    box_w, box_h = 220, 58
    for i, label in enumerate(labels):
        ang = (2*math.pi*i)/n - math.pi/2
        x = int(cx + r*math.cos(ang)) - box_w//2
        y = int(cy + r*math.sin(ang)) - box_h//2
        dr.line([(cx,cy), (x+box_w//2, y+box_h//2)], fill=(138,138,165), width=2)
        dr.rounded_rectangle([x,y,x+box_w,y+box_h], radius=10, fill=(31,31,40), outline=(107,107,122), width=2)
        dr.text((x+10, y+box_h//2-8), label, font=font, fill=(230,230,240))

    from io import BytesIO
    bio = BytesIO(); img.save(bio, format="PNG"); bio.seek(0)
    return bio

def concept_map_flow_png(plan_json, header: str | None = None):
    """Mappa concettuale gerarchica a blocchi (stile libro scolastico)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    steps = plan_json.get("steps", [])
    labels = [s.get("title","") for s in steps]
    # suddividi in 3-4 fasce
    tiers = []
    if labels:
        tiers.append(labels[:2])
        mid = max(2, len(labels)//3)
        tiers.append(labels[2:2+mid])
        tiers.append(labels[2+mid:])
    else:
        tiers = [["Introduzione"],["Sviluppo"],["Sintesi"]]

    w,h = 1000, 900
    img = Image.new("RGB", (w,h), (255,255,255))
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # colori e stile
    col_box = (255, 247, 235)
    col_border = (210, 150, 90)
    col_head = (236, 170, 70)
    col_text = (40, 40, 40)

    # header
    if header:
        dr.rounded_rectangle([20,20,w-20,70], radius=8, fill=col_head)
        dr.text((30,40), header, fill=(255,255,255), font=font)

    top = 100
    for t, row in enumerate(tiers):
        if not row: continue
        y = top + t*220
        cols = len(row)
        box_w, box_h = 280, 80
        gap = (w - 80 - cols*box_w)//(cols-1) if cols>1 else 0
        xs = [40 + i*(box_w+gap) for i in range(cols)]
        centers = []
        for i, label in enumerate(row):
            x = xs[i]
            dr.rounded_rectangle([x,y,x+box_w,y+box_h], radius=12, fill=col_box, outline=col_border, width=2)
            dr.text((x+10,y+25), label, fill=col_text, font=font)
            centers.append((x+box_w//2, y+box_h))
        # connettori verticali con fascia successiva
        if t < len(tiers)-1 and tiers[t+1]:
            next_y = top + (t+1)*220
            for cx,cy in centers:
                dr.line([(cx, cy), (cx, next_y-20)], fill=col_border, width=2)

    from io import BytesIO
    bio = BytesIO(); img.save(bio, format="PNG"); bio.seek(0)
    return bio

# ========================= SHARE (read-only semplice) =========================
read_only = False
qp = st.query_params
if "share" in qp:
    try:
        st.session_state["selected_plan_id"] = int(qp["share"])
        read_only = True
    except Exception:
        pass

# =========================================================
# Sidebar con logo Synapse e login
# =========================================================
APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "static" / "logo.png"

with st.sidebar:
    st.markdown("<div style='text-align:center; margin-top:-18px; margin-bottom:-2px;'>", unsafe_allow_html=True)
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=46)
    else:
        st.warning("Logo non trovato in /static/logo.png")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<p class='sidebar-title' style='text-align:center;'>Accedi</p>", unsafe_allow_html=True)

    if not read_only:
        email = st.text_input("Email", placeholder="tu@esempio.com", key="sb_email")
        if st.button("Continua", key="sb_continue") and email:
            st.session_state["user"] = upsert_user(email)

    if "user" in st.session_state or read_only:
        if not read_only:
            st.markdown(
                f"<p style='margin:.15rem 0 .25rem 0; opacity:.85;'>Accesso effettuato: {st.session_state['user']['email']}</p>",
                unsafe_allow_html=True
            )

        # New plan (no box/shadow)
        st.session_state.setdefault("show_generator", False)
        if not read_only and st.button("➕ Nuovo piano", use_container_width=True, key="btn_new_plan_sidebar"):
            st.session_state.show_generator = True
            st.rerun()

        # Titolo I tuoi piani (markdown → niente linee)
        st.markdown("<p class='sidebar-title'>I tuoi piani</p>", unsafe_allow_html=True)

        # Elenco piani
        if read_only and "user" not in st.session_state:
            plans_sidebar = []
        else:
            uid = st.session_state["user"]["id"] if "user" in st.session_state else None
            plans_sidebar = list_plans(uid) if uid else []

        if plans_sidebar and "selected_plan_id" not in st.session_state:
            st.session_state["selected_plan_id"] = plans_sidebar[0]["id"]

        st.session_state.setdefault("rename_target", None)
        st.session_state.setdefault("rename_value", "")
        st.session_state.setdefault("delete_target", None)
        st.session_state.setdefault("show_delete_modal", False)

        # === RENDER LISTA PIANI ===
        st.markdown("<div class='plans-stack'>", unsafe_allow_html=True)

        for p in plans_sidebar:
            pct = plan_completion_percent(p)
            selected = (p["id"] == st.session_state.get("selected_plan_id"))
            icon = "📘" if selected else "📁"
            row_class = "planbar selected" if selected else "planbar"

            st.markdown(f"<div class='{row_class}' style='--pct:{pct}%;'>", unsafe_allow_html=True)
            c_left, c_edit, c_del = st.columns([8, 1, 1], gap="small")

            with c_left:
                st.markdown("<div class='plan-btn'>", unsafe_allow_html=True)
                if not read_only and st.session_state["rename_target"] == p["id"]:
                    new_name = st.text_input(
                        label="", value=st.session_state.get("rename_value", p["topic"]),
                        key=f"rename_input_{p['id']}", label_visibility="collapsed"
                    )
                    st.session_state["rename_value"] = new_name
                else:
                    label = f"{icon} {p['topic']} — {pct}%"
                    if st.button(label, key=f"sel_{p['id']}", use_container_width=True):
                        st.session_state["selected_plan_id"] = p["id"]
                        st.session_state["rename_target"] = None
                        st.session_state["delete_target"] = None
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if not read_only and st.session_state["rename_target"] == p["id"]:
                with c_edit:
                    st.markdown("<div class='icon-round'>", unsafe_allow_html=True)
                    if st.button("✅", key=f"save_{p['id']}", type="secondary", help="Save"):
                        nn = (st.session_state.get("rename_value","") or "").strip()
                        if nn:
                            update_plan_topic(p["id"], nn)
                            st.session_state["rename_target"] = None
                            st.session_state["rename_value"] = ""
                            st.rerun()
                        else:
                            st.error("Il nome non può essere vuoto.")
                    st.markdown("</div>", unsafe_allow_html=True)
                with c_del:
                    st.markdown("<div class='icon-round'>", unsafe_allow_html=True)
                    if st.button("✖️", key=f"cancel_{p['id']}", type="secondary", help="Cancel"):
                        st.session_state["rename_target"] = None
                        st.session_state["rename_value"] = ""
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            elif not read_only:
                with c_edit:
                    st.markdown("<div class='icon-round'>", unsafe_allow_html=True)
                    if st.button("✏️", key=f"ed_{p['id']}", type="secondary", help="Rename"):
                        st.session_state["rename_target"] = p["id"]
                        st.session_state["rename_value"] = p["topic"]
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with c_del:
                    st.markdown("<div class='icon-round'>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"rm_{p['id']}", type="secondary", help="Delete"):
                        st.session_state["delete_target"] = p["id"]
                        st.session_state["show_delete_modal"] = True
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)  # chiusura .planbar

        st.markdown("</div>", unsafe_allow_html=True)  # chiusura .plans-stack

# Se non loggato e non in share read-only, fermati qui
if "user" not in st.session_state and not read_only:
    st.info("Accedi (a sinistra) per creare o gestire i tuoi piani.")
    st.stop()

user = st.session_state.get("user")

# =========================================================
# POPUP conferma eliminazione
# =========================================================
if st.session_state.get("show_delete_modal") and st.session_state.get("delete_target") and not read_only:
    all_plans = list_plans(user["id"])
    plan_to_del = next((x for x in all_plans if x["id"] == st.session_state["delete_target"]), None)
    plan_name = plan_to_del["topic"] if plan_to_del else "this plan"

    if hasattr(st, "dialog"):
        @st.dialog("Conferma eliminazione")
        def _confirm_delete_dialog():
            st.error(f"Eliminare '{plan_name}'? L'azione è definitiva.")
            col_ok, col_cancel = st.columns(2)
            if col_ok.button("OK, elimina", type="primary", key="dialog_del_ok"):
                delete_plan(st.session_state["delete_target"])
                remaining = [x for x in all_plans if x["id"] != st.session_state["delete_target"]]
                st.session_state["selected_plan_id"] = remaining[0]["id"] if remaining else None
                st.session_state["delete_target"] = None
                st.session_state["show_delete_modal"] = False
                st.rerun()
            if col_cancel.button("Annulla", key="dialog_del_cancel"):
                st.session_state["delete_target"] = None
                st.session_state["show_delete_modal"] = False
                st.rerun()
        _confirm_delete_dialog()
    else:
        st.warning(f"Eliminare '{plan_name}'? L'azione è definitiva.")
        col_ok, col_cancel = st.columns(2)
        if col_ok.button("OK, elimina", type="primary", key="fallback_del_ok"):
            delete_plan(st.session_state["delete_target"])
            remaining = [x for x in all_plans if x["id"] != st.session_state["delete_target"]]
            st.session_state["selected_plan_id"] = remaining[0]["id"] if remaining else None
            st.session_state["delete_target"] = None
            st.session_state["show_delete_modal"] = False
            st.rerun()
        if col_cancel.button("Annulla", key="fallback_del_cancel"):
            st.session_state["delete_target"] = None
            st.session_state["show_delete_modal"] = False
            st.rerun()

# =========================================================
# Generatore (senza minutes/day) + PDF opzionale
# =========================================================
if st.session_state.get("show_generator", False) and not read_only:
    st.write("### Genera il tuo piano di studio")

    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("Argomento*", placeholder="es. Basi della Termodinamica")
    with col2:
        level = st.selectbox("Livello obiettivo*", ["beginner", "intermediate", "advanced"])  # valori in inglese per compatibilità

    goals = st.text_area("Quale risultato vuoi ottenere? (opzionale)", placeholder="Esame, progetto, voto massimo, ecc.")
    st.markdown("**Opzionale: libro (PDF)** — verrà usato per arricchire il piano")
    textbook = st.file_uploader("Carica PDF", type=["pdf"], accept_multiple_files=False)

    cgen, ccancel = st.columns([2, 1])
    if cgen.button("Genera e salva", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("Inserisci un argomento.")
        else:
            textbook_text = None
            if textbook is not None:
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=textbook.read(), filetype="pdf")
                    parts = [page.get_text() for page in doc]
                    textbook_text = "\n".join(parts)[:20000]
                except Exception as e:
                    st.warning(f"Impossibile leggere il PDF: {e}")

            with st.spinner("Preparo il piano..."):
                plan = generate_plan(topic, level, 30, "misto")
                if textbook_text:
                    try:
                        if "steps" in plan and plan["steps"]:
                            plan["steps"][0].setdefault("suggested_resources", []).append("Textbook (uploaded)")
                    except Exception:
                        pass
                saved = save_plan(user["id"], topic, level, goals, plan)
                st.session_state["selected_plan_id"] = saved["id"]
            st.session_state["show_generator"] = False
            st.success("Piano salvato.")
            st.rerun()

    if ccancel.button("Annulla"):
        st.session_state["show_generator"] = False
        st.rerun()

    st.stop()

# =========================================================
# Mostra dettagli del piano selezionato
# =========================================================
plans = list_plans(st.session_state["user"]["id"]) if "user" in st.session_state else []
current_plan = None
if st.session_state.get("selected_plan_id"):
    for _p in plans:
        if _p["id"] == st.session_state["selected_plan_id"]:
            current_plan = _p
            break

if not current_plan:
    st.info("Seleziona o crea un piano (a sinistra) per vedere i dettagli.")
    st.stop()

# Share (URL semplice)
col_share, _ = st.columns([1,3])
share_url = None
if col_share.button("🔗 Condividi (link pubblico)"):
    share_url = f"?share={current_plan['id']}"
if share_url:
    st.success(f"Link pubblico: {share_url}")

st.divider()
st.subheader(f"Piano: {current_plan['topic']}  ·  Livello: {current_plan['level']}" + ("  ·  Sola lettura" if read_only else ""))

plan_json = current_plan["plan_json"]
if isinstance(plan_json, str):
    try:
        plan_json = json.loads(plan_json)
    except Exception:
        plan_json = {}

# Se il piano ha pochi step, espandilo automaticamente una sola volta
st.session_state.setdefault("_expanded_plans", {})
if not read_only:
    _expanded = st.session_state["_expanded_plans"].get(current_plan["id"], False)
    minimal_steps = len((plan_json or {}).get("steps", []))
    if not _expanded and minimal_steps and minimal_steps < 7:
        with st.spinner("Espando il piano per maggior dettaglio..."):
            new_plan = generate_plan(current_plan["topic"], current_plan.get("level","beginner"), 30, "misto")
            if (new_plan or {}).get("steps") and len(new_plan["steps"]) > minimal_steps:
                update_plan_json(current_plan["id"], new_plan)
                plan_json = new_plan
        st.session_state["_expanded_plans"][current_plan["id"]] = True

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
c1.metric("🔴 Da fare",   todo_count)
c2.metric("🟡 In corso",  doing_count)
c3.metric("🟢 Fatto",     done_count)
with c4:
    st.write("**Completamento**")
    st.progress(completion, text=f"{int(completion*100)}%")

# ---------------- TODAY panel (in base alle due_date) ----------------
today_list, overdue_list = [], []
for idx, s in enumerate(steps):
    m = get_step_meta(current_plan["id"], idx)
    d = m.get("due_date")
    if not d:
        continue
    try:
        dd = date.fromisoformat(d)
        if dd == date.today():
            today_list.append((idx, s))
        elif dd < date.today():
            overdue_list.append((idx, s))
    except Exception:
        pass

if today_list or overdue_list:
    st.write("### Oggi")
    if today_list:
        st.markdown("**Scadenza oggi**")
        for (idx, s) in today_list:
            st.markdown(f"- Step {idx+1}: {s.get('title','')}")
    if overdue_list:
        st.markdown("**In ritardo**")
        for (idx, s) in overdue_list:
            st.markdown(f"- Step {idx+1}: {s.get('title','')}")
    st.divider()

# ---------------- Steps render ----------------
EMOJI = {"to-do": "🔴", "doing": "🟡", "done": "🟢"}

upload_dir = Path("static/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)

for i, step in enumerate(steps):
    cur = progress_map.get(i, "to-do")
    badge = EMOJI.get(cur, "🔴")
    title = f"{badge} Passo {i+1}: {step.get('title','')}"

    with st.expander(title, expanded=(i == 0)):
        st.markdown("**Obiettivo**: " + step.get("objective", ""))

        if step.get("theory_outline"):
            st.markdown("**Teoria (sommario)**")
            for b in step["theory_outline"]:
                st.markdown(f"- {b}")

        # Spiegazione dettagliata (AI) – generazione automatica e cache per piano/passo
        st.session_state.setdefault("ai_explain", {})
        plan_expl = st.session_state["ai_explain"].setdefault(current_plan["id"], {})
        if i not in plan_expl:
            cached = get_ai_cache(current_plan["id"], i, "explain_md")
            if cached is None:
                with st.spinner("Creo spiegazione dettagliata..."):
                    md = explain_step_ai(
                        plan_json,
                        i,
                        current_plan.get("level","beginner"),
                        "misto"
                    )
                set_ai_cache(current_plan["id"], i, "explain_md", md)
                plan_expl[i] = md
            else:
                plan_expl[i] = cached
        st.markdown(plan_expl[i])
        if step.get("practice_tasks"):
            st.markdown("**Pratica**")
            for t in step["practice_tasks"]:
                st.markdown(f"- {t}")
        if step.get("suggested_resources"):
            st.markdown("**Risorse**")
            for r in step["suggested_resources"]:
                st.markdown(f"- {r}")

        # STATUS
        if not read_only:
            status = st.selectbox(
                "Stato",
                ["to-do", "doing", "done"],
                index=["to-do", "doing", "done"].index(cur if cur in ["to-do","doing","done"] else "to-do"),
                key=f"st_{i}"
            )
        else:
            st.write(f"**Stato:** {cur}")
            status = cur

        # META: due_date + notes + attachments
        meta = get_step_meta(current_plan["id"], i)
        colA, colB = st.columns([1,1])

        with colA:
            due_value = date.fromisoformat(meta["due_date"]) if meta.get("due_date") else date.today()
            if not read_only:
                due = st.date_input("Scadenza", value=due_value, key=f"due_{i}")
            else:
                due = due_value
                st.write(f"**Scadenza:** {due}")

        with colB:
            if not read_only:
                note = st.text_area("Post-it (note)", value=meta.get("notes",""), key=f"note_{i}")
            else:
                st.markdown("**Post-it**")
                st.write(meta.get("notes",""))

        saved_files = meta.get("attachments", [])
        if not read_only:
            uploads = st.file_uploader("Allega immagini", type=["png","jpg","jpeg"], accept_multiple_files=True, key=f"up_{i}")
            if uploads:
                for up in uploads:
                    pth = upload_dir / f"{current_plan['id']}_{i}_{up.name}"
                    try:
                        with open(pth, "wb") as f:
                            f.write(up.read())
                        saved_files.append(str(pth))
                    except Exception as e:
                        st.warning(f"Caricamento fallito: {e}")
                saved_files = list(dict.fromkeys(saved_files))

        if saved_files:
            st.caption("Allegati")
            gcols = st.columns(min(4, len(saved_files)))
            for idx, fp in enumerate(saved_files):
                with gcols[idx % len(gcols)]:
                    try:
                        st.image(fp, use_container_width=True)
                    except Exception:
                        st.text(Path(fp).name)

        # Esercizi (AI) – generazione automatica e rendering inline
        st.session_state.setdefault("ai_exercises", {})
        plan_ex = st.session_state["ai_exercises"].setdefault(current_plan["id"], {})
        if i not in plan_ex:
            cached = get_ai_cache(current_plan["id"], i, "exercises_json")
            if cached is None:
                with st.spinner("Creo esercizi con AI..."):
                    data = generate_exercises_ai(
                        plan_json,
                        i,
                        current_plan.get("level","beginner"),
                        "misto"
                    )
                plan_ex[i] = data
                try:
                    set_ai_cache(current_plan["id"], i, "exercises_json", json.dumps(data, ensure_ascii=False))
                except Exception:
                    pass
            else:
                try:
                    plan_ex[i] = json.loads(cached)
                except Exception:
                    plan_ex[i] = {}
        data = plan_ex.get(i)
        if data:
            st.markdown(f"**{data['guided']['title']}**")
            for sidx, stext in enumerate(data['guided']['steps'], start=1):
                st.markdown(f"- Passo {sidx}: {stext}")
            answers = []
            for qi, q in enumerate(data['quiz']):
                sel = st.radio(q["q"], q["opts"], key=f"quiz_{i}_{qi}")
                answers.append(sel)
            if st.button("Verifica risposte", key=f"check_aiquiz_{i}"):
                score = 0
                for qi, q in enumerate(data['quiz']):
                    if answers[qi] == q['opts'][q['a']]: score += 1
                st.success(f"Punteggio: {score}/{len(data['quiz'])}")
            txt = st.text_area(data['writing']['prompt'], key=f"write_{i}", height=140)
            if txt:
                wc = len(txt.split()); st.caption(f"Parole: {wc} (target {data['writing']['min']}–{data['writing']['max']})")

        # Sezione mappa concettuale rimossa su richiesta

        # (spiegazione già mostrata nella sezione principale)

        if not read_only:
            if st.button("Salva passo", key=f"sv_{i}"):
                set_progress(current_plan["id"], i, status)
                set_step_meta(current_plan["id"], i, {
                    "due_date": due.isoformat() if isinstance(due, date) else None,
                    "notes": st.session_state.get(f"note_{i}", meta.get("notes","")),
                    "attachments": saved_files
                })
                st.success("Salvato")
                st.rerun()

# ---------------- Review strategy ----------------
if plan_json.get("review_strategy"):
    st.markdown("**Strategia di ripasso**")
    for b in plan_json["review_strategy"]:
        st.markdown(f"- {b}")

# ---------------- Tutor chat ----------------
st.write("### Chiedi a Synapse (Tutor)")
q = st.text_input("La tua domanda su questo piano")
if st.button("Chiedi"):
    if not q.strip():
        st.error("Scrivi una domanda.")
    else:
        with st.spinner("Elaboro..."):
            answer = tutor_answer(plan_json, q)
        st.info(q)
        st.success(answer)
