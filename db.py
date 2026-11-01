"""Capa de datos sobre Supabase (Streamlit Cloud no conserva ficheros locales)."""
import httpx
import streamlit as st
from supabase import create_client


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


@st.cache_resource
def _client():
    url, key = _datos()
    return create_client(url, key)


def _diagnostico(table, err):
    """Pregunta a Supabase directamente y muestra su respuesta real."""
    url, key = _datos()
    try:
        r = httpx.get(f"{url}/rest/v1/{table}?select=*&limit=1",
                      headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=15)
        detalle = f"HTTP {r.status_code}: {r.text[:400]}"
    except Exception as e:  # noqa: BLE001
        detalle = f"No se pudo conectar: {e}"
    st.error(f"Error consultando la tabla '{table}'.\n\n**Respuesta de Supabase:** {detalle}\n\n"
             f"(Clave: empieza por '{key[:8]}…', {len(key)} caracteres)")
    st.stop()


def select(table, order=None, desc=False, **eq):
    try:
        q = _client().table(table).select("*")
        for k, v in eq.items():
            q = q.eq(k, v)
        if order:
            q = q.order(order, desc=desc)
        data = q.execute().data
    except Exception as e:  # noqa: BLE001
        _diagnostico(table, e)
    if not isinstance(data, list):
        st.error(f"Supabase devolvió algo inesperado en '{table}': {str(data)[:300]}")
        st.stop()
    return data


def get(table, id_):
    r = _client().table(table).select("*").eq("id", id_).limit(1).execute().data
    return r[0] if r else None


def insert(table, row):
    return _client().table(table).insert(row).execute().data[0]


def update(table, id_, row):
    _client().table(table).update(row).eq("id", id_).execute()


def delete(table, id_):
    _client().table(table).delete().eq("id", id_).execute()


def siguiente_numero(table, prefijo):
    """Devuelve p. ej. PRE-2026-004 según los ya existentes del año."""
    año = __import__("datetime").date.today().year
    base = f"{prefijo}-{año}-"
    filas = (
        _client().table(table).select("numero").like("numero", base + "%").execute().data
    )
    n = max([int(f["numero"].split("-")[-1]) for f in filas] + [0]) + 1
    return f"{base}{n:03d}"
