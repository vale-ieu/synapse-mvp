import os
from supabase import create_client, Client

def _client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    return create_client(url, key)

def upsert_user(email: str):
    supa = _client()
    res = supa.table("users").select("*").eq("email", email).execute()
    if res.data:
        return res.data[0]
    ins = supa.table("users").insert({"email": email}).execute()
    return ins.data[0]

def save_plan(user_id: str, topic: str, level: str, goals: str, plan_json: dict):
    supa = _client()
    ins = supa.table("learning_plans").insert({
        "user_id": user_id,
        "topic": topic,
        "level": level,
        "goals": goals,
        "plan_json": plan_json
    }).execute()
    return ins.data[0]

def list_plans(user_id: str):
    supa = _client()
    res = supa.table("learning_plans")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .execute()
    return res.data

def get_progress_map(plan_id: str):
    supa = _client()
    res = supa.table("progress").select("*").eq("plan_id", plan_id).execute()
    return {row["step_index"]: row["status"] for row in res.data}

def set_progress(plan_id: str, step_index: int, status: str):
    supa = _client()
    # upsert by unique (plan_id, step_index)
    existing = supa.table("progress")\
        .select("*")\
        .eq("plan_id", plan_id)\
        .eq("step_index", step_index)\
        .execute().data
    if existing:
        upd = supa.table("progress")\
            .update({"status": status})\
            .eq("id", existing[0]["id"])\
            .execute()
        return upd.data[0]
    ins = supa.table("progress")\
        .insert({"plan_id": plan_id, "step_index": step_index, "status": status})\
        .execute()
    return ins.data[0]
