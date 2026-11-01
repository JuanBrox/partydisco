"""Capa de datos sobre Supabase usando su API REST directamente (sin la librería supabase)."""
import datetime

import httpx
import streamlit as st


def _datos():
    faltan = [k for k in ("SUPABASE_URL", "SUPABASE_KEY") if k not in st.secrets]
    if faltan:
        st.error(f"Faltan en Secrets: {', '.join(faltan)} (deben ir antes de [empresa]).")
        st.stop()
    url = st.secrets["SUPABASE_URL"].strip().strip('"').rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip().strip('"')
    if not (url.startswith("https://") and url.endswith(".supabase.co")):
        st.error(f"SUPABASE_URL no parece una Project URL válida: {url}")
        st.stop()
    return url, key


def _req(method, table, params=None, json=None, prefer=None):
    url, key = _datos()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        r = httpx.request(method, f"{url}/rest/v1/{table}", params=params, json=json,
                          headers=headers, timeout=20)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo conectar con Supabase: {e}")
        st.stop()
    if r.status_code >= 300:
        st.error(f"Supabase respondió HTTP {r.status_code} en '{table}': {r.text[:400]}")
        st.stop()
    return r.json() if r.text else []


def select(table, order=None, desc=False, **eq):
    params = {"select": "*"}
    for k, v in eq.items():
        params[k] = f"eq.{v}"
    if order:
        params["order"] = f"{order}.{'desc' if desc else 'asc'}"
    return _req("GET", table, params)


def get(table, id_):
    r = _req("GET", table, {"select": "*", "id": f"eq.{id_}", "limit": 1})
    return r[0] if r else None


def insert(table, row):
    return _req("POST", table, json=row, prefer="return=representation")[0]


def update(table, id_, row):
    _req("PATCH", table, {"id": f"eq.{id_}"}, json=row)


def delete(table, id_):
    _req("DELETE", table, {"id": f"eq.{id_}"})


def siguiente_numero(table, prefijo):
    """Devuelve p. ej. PRE-2026-004 según los ya existentes del año."""
    base = f"{prefijo}-{datetime.date.today().year}-"
    filas = _req("GET", table, {"select": "numero", "numero": f"like.{base}*"})
    n = max([int(f["numero"].split("-")[-1]) for f in filas] + [0]) + 1
    return f"{base}{n:03d}"
