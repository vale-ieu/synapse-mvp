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

from prompts import PLAN_PROMPT, TUTOR_PROMPT, EXERCISE_PROMPT, EXPLAIN_PROMPT

def _fallback_plan(topic: str, level: str, time_per_day: int, goal_mode: str = "misto") -> dict:
    level_note = {
        "beginner": "spiegazioni semplici con esempi quotidiani",
        "intermediate": "spiegazioni operative con collegamenti tra concetti",
        "advanced": "spiegazioni sintetiche e formali con riferimenti critici",
    }.get(level, "spiegazioni chiare e progressive")

    # lunghezza variabile per obiettivo
    if goal_mode == "esame_universita":
        steps_count = 12
    elif goal_mode == "verifica_liceo":
        steps_count = 9
    else:  # misto bilanciato
        steps_count = 11

    base_steps = [
        {
            "title": "Fondamenti",
            "objective": f"Comprendere le idee chiave di {topic}.",
            "theory_outline": ["Termini essenziali", "Principi di base", "Errori comuni"],
            "theory_explanations": [
                f"Definisci i termini più usati in {topic} con esempi a livello {level}.",
                "Mostra come i principi si collegano tra loro con 1–2 esempi.",
                "Evidenzia gli sbagli tipici e come evitarli."
            ],
            "practice_tasks": ["Riassumi in 5 punti", "Spiegalo a voce in 3 minuti"],
            "suggested_resources": ["Cerca: documentazione ufficiale", "YouTube: introduzione"]
        },
        {"title": "Contesto storico e concettuale", "objective":"Capire perché nasce il tema",
         "theory_outline":["Origine e contesto", "Problemi a cui risponde"],
         "theory_explanations":["Collega l'argomento a eventi/idee del periodo."],
         "practice_tasks":["Timeline di 5 tappe", "Mappa nomi-concetti"],
         "suggested_resources":["Voce enciclopedica affidabile"]},
        {"title": "Concetti cardine 1", "objective":"Approfondire il primo asse concettuale",
         "theory_outline":["Definizione", "Esempio chiave", "Eccezioni/limiti"],
         "theory_explanations":["Spiega con un esempio semplice e uno intermedio."],
         "practice_tasks":["2 esercizi guidati", "Quiz mirato (5 domande)"]},
        {"title": "Concetti cardine 2", "objective":"Secondo asse concettuale",
         "theory_outline":["Definizione", "Relazione con il precedente"],
         "theory_explanations":["Evidenzia analogie/differenze."],
         "practice_tasks":["Confronto in tabella", "Esempio applicato"]},
        {"title": "Esempi guidati", "objective":"Vedere i concetti in azione",
         "theory_outline":["2–3 esempi risolti"],
         "theory_explanations":["Perché ogni passo è necessario"],
         "practice_tasks":["Replica esempi", "Annota dove ti blocchi"]},
        {"title": "Collegamenti trasversali", "objective":"Integrare i concetti",
         "theory_outline":["Schema concettuale", "Cause–effetti"],
         "theory_explanations":["Mostra dipendenze essenziali"],
         "practice_tasks":["Mappa concettuale personale", "1 pagina di sintesi"]},
        {"title": "Pratica strutturata", "objective":"Costruire fluidità",
         "theory_outline":["Schemi ricorrenti", "Euristiche"],
         "theory_explanations":["Quando applicarle"],
         "practice_tasks":["6 esercizi a difficoltà crescente", "Registro degli errori"]},
        {"title": "Mini‑progetto", "objective":"Applicazione end‑to‑end",
         "theory_outline":["Pianifica → Realizza → Riesamina"],
         "theory_explanations":["Piccolo deliverable verificabile"],
         "practice_tasks":["Progetto tascabile", "Riflessione di 150 parole"]},
        {"title": "Ripasso per verifica", "objective":"Preparare una verifica di liceo",
         "theory_outline":["Possibili domande", "Trappole tipiche"],
         "theory_explanations":["Schema di risposta in 4 punti"],
         "practice_tasks":["Simulazione orale 5'", "Schede di ripasso"]},
        {"title": "Approfondimenti (opzionale)", "objective":"Avvio verso livello universitario",
         "theory_outline":["Fonti primarie", "Critiche avanzate"],
         "theory_explanations":["Leggi 1 brano e commentalo"],
         "practice_tasks":["Sintesi critica 200 parole"]},
    ]

    steps = (base_steps[:steps_count] if steps_count <= len(base_steps) else base_steps + [
        {"title": f"Approfondimento extra {i}", "objective":"Estendere e consolidare",
         "theory_outline":["Tema aggiuntivo"],
         "theory_explanations":["Nota avanzata"],
         "practice_tasks":["Esercizio mirato"]}
        for i in range(len(base_steps)+1, steps_count+1)
    ])

    return {
        "overview": (
            f"Panoramica di '{topic}' per livello {level}: {level_note}. "
            f"Modalità: {goal_mode}. Organizzato in sessioni da ~{time_per_day} minuti al giorno con obiettivi chiari."
        ),
        "steps": steps,
        "review_strategy": [
            "Ripasso dilazionato Giorno 2, 4, 7",
            "Trasforma gli errori in flashcard",
            "Spiega ad alta voce alla fine di ogni sessione"
        ],
        "_meta": {"source": "fallback", "lang": "it"}
    }

def generate_plan(topic: str, level: str = "beginner", time_per_day: int = 30, goal_mode: str = "misto") -> dict:
    if DEMO_MODE or client is None:
        return _fallback_plan(topic, level, time_per_day, goal_mode)
    try:
        # chiamata reale (funzionerà quando avrai credito)
        prompt = PLAN_PROMPT.format(topic=topic, level=level, time_per_day=time_per_day, goal_mode=goal_mode)
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
        plan = _fallback_plan(topic, level, time_per_day, goal_mode)
        plan["_error"] = str(e)
        return plan

def tutor_answer(plan_context: dict, question: str) -> str:
    if DEMO_MODE or client is None:
        return (
            f"Modalità demo – nessuna chiamata API.\n"
            f"Domanda: {question}\n"
            f"Suggerimento: passa al prossimo passo del piano, svolgi una micro‑attività, "
            f"e annota la più piccola domanda che ti blocca."
        )
    ctx = json.dumps({k: plan_context.get(k) for k in ("overview", "steps")})
    prompt = TUTOR_PROMPT.format(plan_context=ctx, question=question)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()

def generate_concept_map(plan_json, step_idx=None, textbook_text=None):
    """
    Return a simple dict representing a concept map (nodes & edges).
    Replace with your LLM call; this is a placeholder structure.
    """
    title = plan_json.get("overview","Concetti")
    steps = plan_json.get("steps", [])
    nodes = [{"id": f"s{i}", "label": s.get("title","")} for i,s in enumerate(steps)]
    edges = [{"from": f"s{i}", "to": f"s{i+1}"} for i in range(max(0,len(steps)-1))]
    if step_idx is not None:
        # emphasize selected step
        nodes[step_idx]["label"] = "⭐ " + nodes[step_idx]["label"]
    return {"title": title, "nodes": nodes, "edges": edges}

def propose_exercises_for_step(step):
    """Return a short list of exercises for the given step. Placeholder."""
    base = step.get("practice_tasks") or []
    return base[:3] if base else [
        "Esercizio 1: applica il concetto A a un esempio reale",
        "Esercizio 2: risolvi 3 problemi su B",
        "Esercizio 3: crea un riassunto di 150 parole"
    ]

def generate_exercises_ai(plan_context: dict, step_idx: int, level: str, goal_mode: str) -> dict:
    if DEMO_MODE or client is None:
        step = (plan_context.get("steps") or [{}])[step_idx] if step_idx < len(plan_context.get("steps",[])) else {}
        # Fallback più ricco ma locale
        guided = {
            "title": f"Esercizio guidato: {step.get('title','Concetto')}",
            "steps": [
                "Prepara una scheda con definizioni e un esempio reale",
                "Applica il concetto a un caso scolastico (3 passaggi)",
                "Confronta con un controesempio e spiega la differenza",
                "Scrivi una conclusione di 120–150 parole"
            ]
        }
        quiz = [
            {"q":"Individua l'idea centrale dello step.","opts":["Definizioni isolate","Idea con relazioni","Solo applicazioni","Solo storia"],"a":1,"why":"Serve collegare definizione-relazioni"},
            {"q":"Cosa fare se trovi una contraddizione?","opts":["Ignorarla","Considerarla motore dell'analisi","Scartare il problema","Memorizzare regole"],"a":1,"why":"Analizzare e integrare"},
            {"q":"Quale elemento non fa parte di un esempio ben costruito?","opts":["Contesto","Passi","Verifica","Abbellimenti irrilevanti"],"a":3,"why":"Rilevanza prima di tutto"},
            {"q":"Quanto deve essere lungo un riassunto efficace?","opts":["> 500 parole","120–180 parole","Una parola","Nessun limite"],"a":1,"why":"Sintesi densa"},
            {"q":"Per la verifica è utile…","opts":["Solo leggere","Fare quiz mirati","Saltare esercizi","Rinunciare"],"a":1,"why":"Pratica mirata"},
        ]
        writing = {"prompt": f"Scrivi un saggio breve (120–180 parole) che spieghi '{step.get('title','il concetto')}' con un esempio e un controesempio.", "min":120, "max":180, "rubric":["Definizione corretta","Esempio e controesempio","Chiarezza e lessico", "Collegamenti"]}
        return {"guided": guided, "quiz": quiz, "writing": writing}

    steps = plan_context.get("steps") or []
    step = steps[step_idx] if 0 <= step_idx < len(steps) else {}
    ctx = json.dumps({k: plan_context.get(k) for k in ("overview", "steps")}, ensure_ascii=False)
    prompt = EXERCISE_PROMPT.format(
        plan_context=ctx,
        step_idx=step_idx,
        level=level,
        goal_mode=goal_mode,
        step_title=step.get("title",""),
        step_outline=json.dumps(step.get("theory_outline", []), ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )
    txt = resp.choices[0].message.content
    start, end = txt.find("{"), txt.rfind("}")
    data = json.loads(txt[start:end+1]) if start!=-1 and end!=-1 else json.loads(txt)
    return data

def explain_step_ai(plan_context: dict, step_idx: int, level: str, goal_mode: str) -> str:
    if DEMO_MODE or client is None:
        step = (plan_context.get("steps") or [{}])[step_idx] if step_idx < len(plan_context.get("steps",[])) else {}
        title = step.get("title","Concetto")
        bullets = step.get("theory_outline", [])
        pts = "\n".join([f"- {b}" for b in bullets])
        return (
            f"### {title}\n\n"
            f"Obiettivo: comprendere a fondo il tema e saperlo applicare.\n\n"
            f"Idee chiave:\n{pts}\n\n"
            f"Approfondimenti: definizioni chiare, esempio concreto, mito da sfatare.\n\n"
            f"Mini-check: 1) definisci il concetto 2) fai un esempio 3) indica un limite."
        )

    steps = plan_context.get("steps") or []
    step = steps[step_idx] if 0 <= step_idx < len(steps) else {}
    ctx = json.dumps({k: plan_context.get(k) for k in ("overview", "steps")}, ensure_ascii=False)
    prompt = EXPLAIN_PROMPT.format(
        plan_context=ctx,
        step_idx=step_idx,
        level=level,
        goal_mode=goal_mode,
        step_title=step.get("title",""),
        step_outline=json.dumps(step.get("theory_outline", []), ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()

def generate_plan_from_textbook(topic, target_level, textbook_text):
    """Placeholder: mix topic+level+textbook to produce a plan structure."""
    if not textbook_text:  # fallback
        return generate_plan(topic, target_level, 30)
    # Simple scaffold
    return {
        "overview": f"Piano per '{topic}' (livello {target_level}) basato sul libro caricato.",
        "steps": [
            {"title":"Contenuti fondamentali", "objective":"Capire i concetti base",
             "theory_outline":[f"Cap. 1-2 del testo: {topic}"],
             "practice_tasks":[ "Esercizi di fine capitolo 1", "Quiz su definizioni" ],
             "suggested_resources":[ "Appunti dal libro", "Video introduttivo" ]},
            {"title":"Applicazioni e problemi", "objective":"Applicare le tecniche principali",
             "theory_outline":[ "Cap. 3-4: tecniche e metodi"],
             "practice_tasks":[ "Problemi selezionati cap. 3", "1 progetto breve" ],
             "suggested_resources":[ "Esempi svolti del testo" ]},
        ],
        "review_strategy":[ "Ripasso dopo 2 giorni", "Ripasso dopo 1 settimana" ]
    }
