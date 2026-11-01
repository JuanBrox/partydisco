"""Capa de datos sobre Supabase (Streamlit Cloud no conserva ficheros locales)."""
import streamlit as st
from supabase import create_client


@st.cache_resource
def _client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def select(table, order=None, desc=False, **eq):
    q = _client().table(table).select("*")
    for k, v in eq.items():
        q = q.eq(k, v)
    if order:
        q = q.order(order, desc=desc)
    return q.execute().data


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
