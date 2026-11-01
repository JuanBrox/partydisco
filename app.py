import calendar
import urllib.parse
from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

import db
import guion_texto
import pdfs

st.set_page_config(page_title="Party Management", page_icon="🎧", layout="wide")

EMPRESA = {"nombre": "PartyDisco", "lema": "Musical Emotions", "nif": "", "direccion": "",
           "telefono": "", "email": "", "iban": "", "razon_social": "", **dict(st.secrets.get("empresa", {}))}

ESTADOS_EVENTO = ["Consulta", "Presupuestado", "Confirmado", "Realizado", "Cancelado"]
ESTADOS_PRESU = ["Borrador", "Enviado", "Aceptado", "Rechazado"]
ESTADOS_FACT = ["Pendiente", "Pagada"]
TIPOS = ["Boda", "Cumpleaños", "Comunión", "Bautizo", "Empresa", "Fiesta privada", "Otro"]
COLOR = {"Consulta": "#c9c9d6", "Presupuestado": "#ffe08a", "Confirmado": "#9be3b0",
         "Realizado": "#8ec5fc", "Cancelado": "#f5a3a3"}
CONDICIONES = ("Para reservar la fecha se abonará una señal. El resto se abonará antes del evento. "
               "Presupuesto sujeto a disponibilidad hasta su aceptación. "
               "Horas adicionales no incluidas se facturarán aparte.")

SERVICIOS_INICIALES = [
    ("Sonorización ceremonia", "Equipo de sonido y micrófonos inalámbricos para la ceremonia", 250),
    ("Sonorización cocktail", "Hilo musical y equipo de sonido para el cocktail", 300),
    ("Sonorización de sala con micrófonos", "Sonido de sala y micrófonos para discursos", 350),
    ("Discomóvil", "Sesión de DJ con equipo de sonido e iluminación", 600),
    ("Iluminación ambiental", "Iluminación decorativa y efectos", 150),
    ("Hora extra", "Hora adicional de servicio", 80),
]

PLANTILLAS = {
    "Boda": [
        ("17:30", "Llegada de invitados", "Música ambiente de bienvenida", ""),
        ("18:00", "Ceremonia", "Entrada de novios, lecturas, anillos, salida", "Canciones de entrada y salida:"),
        ("19:00", "Cocktail", "Hilo musical", "Estilo / playlist:"),
        ("21:00", "Entrada al salón", "Presentación de los novios", "Canción de entrada:"),
        ("21:30", "Banquete", "Música de fondo, discursos con micrófono", ""),
        ("23:30", "Corte de tarta", "Brindis", "Canción:"),
        ("23:45", "Primer baile", "", "Canción:"),
        ("00:00", "Discomóvil", "Sesión de baile", "Estilos, peticiones y lista de no-poner:"),
        ("03:00", "Fin de fiesta", "Última canción", ""),
    ],
    "Cumpleaños": [
        ("20:00", "Llegada de invitados", "Música ambiente", ""),
        ("21:00", "Cena", "Música de fondo", ""),
        ("23:00", "Tarta y felicitación", "Cumpleaños feliz", ""),
        ("23:15", "Discomóvil", "Sesión de baile", "Estilos:"),
        ("02:00", "Fin de fiesta", "", ""),
    ],
    "Comunión / Bautizo": [
        ("13:30", "Llegada de invitados", "Música ambiente", ""),
        ("14:00", "Comida", "Música de fondo", ""),
        ("17:00", "Tarta", "", ""),
        ("17:30", "Discomóvil infantil y familiar", "Juegos y baile", "Estilos:"),
        ("20:00", "Fin de fiesta", "", ""),
    ],
    "Empresa": [
        ("19:00", "Hora de inicio", "Apertura del evento. Comprobación final de sonido y micrófonos", ""),
        ("19:15", "Llegada de invitados", "Música ambiente de bienvenida", "Estilo / playlist:"),
        ("19:45", "Welcome drink / cocktail", "Hilo musical de fondo", "Estilo / playlist:"),
        ("21:00", "Cena", "Música de fondo a bajo volumen", ""),
        ("22:00", "Discursos", "Micrófonos inalámbricos para las intervenciones", "Orden de intervenciones:"),
        ("22:30", "Vídeo / presentación / entrega de premios", "Proyección, entrega de galardones y micrófono", "Música de vídeo / entrega:"),
        ("23:00", "Lista de canciones", "Sesión musical según la lista acordada con el cliente", "Canciones, estilos y lista de no-poner:"),
        ("01:00", "Hora de cierre", "Última canción y fin del evento", ""),
    ],
}


# ---------- utilidades ----------
def login():
    pw = st.secrets.get("APP_PASSWORD")
    if not pw or st.session_state.get("ok"):
        return
    st.title("🎧 Party Management")
    with st.form("login"):
        entrada = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Entrar")
    if enviar:
        if entrada == pw:
            st.session_state["ok"] = True
            st.rerun()
        st.error("Contraseña incorrecta")
    st.stop()


def css():
    st.markdown("""
    <style>
    .banner{background:linear-gradient(90deg,#e0c3fc,#8ec5fc);padding:14px 22px;border-radius:14px;margin-bottom:14px}
    .banner h2{margin:0;color:#0a1a6e;letter-spacing:1px}
    .banner span{color:#0a1a6e;font-size:.85rem;letter-spacing:3px}
    table.cal{width:100%;border-collapse:collapse;table-layout:fixed}
    table.cal th{background:#0a1a6e;color:#fff;padding:6px}
    table.cal td{border:1px solid #ddd;height:92px;vertical-align:top;padding:3px;font-size:.78rem}
    table.cal td.off{background:#f6f6fa}
    .ev{border-radius:4px;padding:1px 4px;margin-top:2px;color:#111;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
    </style>""", unsafe_allow_html=True)


def banner(titulo):
    st.markdown(f"<div class='banner'><h2>{escape(titulo)}</h2><span>{escape(EMPRESA['nombre'].upper())} · "
                f"{escape(EMPRESA['lema'].upper())}</span></div>", unsafe_allow_html=True)


def clientes_map():
    return {c["id"]: c for c in db.select("clientes", order="nombre")}


def eventos_map():
    return {e["id"]: e for e in db.select("eventos", order="fecha", desc=True)}


def fmt_fecha(d):
    return pdfs.fdate(d)


def lineas_df(lineas):
    if not lineas:
        return pd.DataFrame({"concepto": pd.Series(dtype=str), "cantidad": pd.Series(dtype=float),
                             "precio": pd.Series(dtype=float)})
    return pd.DataFrame(lineas)[["concepto", "cantidad", "precio"]]


def df_a_lineas(df):
    out = []
    for r in df.to_dict("records"):
        if str(r.get("concepto") or "").strip() and str(r.get("concepto")) != "nan":
            out.append({"concepto": str(r["concepto"]), "cantidad": float(r.get("cantidad") or 0),
                        "precio": float(r.get("precio") or 0)})
    return out


def seed_servicios():
    if not db.select("servicios"):
        for n, d, pr in SERVICIOS_INICIALES:
            db.insert("servicios", {"nombre": n, "descripcion": d, "precio": pr})


# ---------- formulario de evento ----------
def evento_form(key, ev=None):
    ev = ev or {}
    cl = clientes_map()
    if not cl:
        st.info("Primero crea un cliente en la sección Clientes.")
        return
    catalogo = [s["nombre"] for s in db.select("servicios", order="nombre")]
    ids = list(cl.keys())
    with st.form(key):
        c1, c2 = st.columns(2)
        titulo = c1.text_input("Título", ev.get("titulo", ""), placeholder="Boda de Ana y Luis")
        cliente = c2.selectbox("Cliente", ids, index=ids.index(ev["cliente_id"]) if ev.get("cliente_id") in ids else 0,
                               format_func=lambda i: cl[i]["nombre"])
        c3, c4, c5, c6 = st.columns(4)
        tipo = c3.selectbox("Tipo", TIPOS, index=TIPOS.index(ev["tipo"]) if ev.get("tipo") in TIPOS else 0)
        fecha = c4.date_input("Fecha", date.fromisoformat(ev["fecha"]) if ev.get("fecha") else date.today())
        h1 = c5.text_input("Inicio", ev.get("hora_inicio") or "", placeholder="18:00")
        h2 = c6.text_input("Fin", ev.get("hora_fin") or "", placeholder="03:00")
        c7, c8 = st.columns([3, 1])
        lugar = c7.text_input("Lugar", ev.get("lugar") or "")
        invitados = c8.number_input("Invitados", 0, 2000, int(ev.get("invitados") or 0))
        estado = st.selectbox("Estado", ESTADOS_EVENTO,
                              index=ESTADOS_EVENTO.index(ev.get("estado", "Consulta")))
        servicios = st.multiselect("Servicios contratados / a presupuestar", catalogo,
                                   default=[s for s in (ev.get("servicios") or []) if s in catalogo])
        notas = st.text_area("Notas", ev.get("notas") or "")
        ok = st.form_submit_button("Guardar evento", type="primary")
    if ok:
        if not titulo.strip():
            st.error("Pon un título.")
            return
        row = {"titulo": titulo, "cliente_id": cliente, "tipo": tipo, "fecha": fecha.isoformat(),
               "hora_inicio": h1, "hora_fin": h2, "lugar": lugar, "invitados": invitados,
               "estado": estado, "servicios": servicios, "notas": notas}
        choque = [e for e in db.select("eventos", fecha=fecha.isoformat())
                  if e["id"] != ev.get("id") and e["estado"] != "Cancelado"]
        if ev.get("id"):
            db.update("eventos", ev["id"], row)
        else:
            db.insert("eventos", row)
        if choque:
            st.warning("Ojo: ya tienes otro evento ese día → " + ", ".join(e["titulo"] for e in choque))
        st.success("Evento guardado")
        if not choque:
            st.rerun()


# ---------- páginas ----------
def pag_panel():
    banner("Panel")
    evs = db.select("eventos", order="fecha")
    hoy = date.today().isoformat()
    en30 = (date.today() + timedelta(days=30)).isoformat()
    proximos = [e for e in evs if e["fecha"] and hoy <= e["fecha"] <= en30 and e["estado"] != "Cancelado"]
    consultas = [e for e in evs if e["estado"] == "Consulta"]
    presu_env = [p for p in db.select("presupuestos") if p["estado"] == "Enviado"]
    pend = [f for f in db.select("facturas") if f["estado"] == "Pendiente"]
    imp_pend = sum(pdfs.totales(f["lineas"], f["descuento"], f["iva"], f.get("retencion") or 0)["total"] for f in pend)
    a, b, c, d = st.columns(4)
    a.metric("Eventos próx. 30 días", len(proximos))
    b.metric("Consultas sin presupuesto", len(consultas))
    c.metric("Presupuestos esperando respuesta", len(presu_env))
    d.metric("Pendiente de cobro", pdfs.eur(imp_pend))
    cl = clientes_map()
    st.subheader("Próximos eventos")
    futuros = [e for e in evs if e["fecha"] and e["fecha"] >= hoy and e["estado"] != "Cancelado"][:10]
    if futuros:
        st.dataframe(pd.DataFrame([{
            "Fecha": fmt_fecha(e["fecha"]), "Evento": e["titulo"], "Cliente": cl.get(e["cliente_id"], {}).get("nombre", ""),
            "Lugar": e["lugar"], "Estado": e["estado"]} for e in futuros]), hide_index=True, width="stretch")
    else:
        st.caption("No hay eventos próximos.")


def pag_agenda():
    banner("Agenda")
    hoy = date.today()
    c1, c2, _ = st.columns([1, 1, 4])
    año = c1.number_input("Año", 2024, 2040, hoy.year)
    mes = c2.selectbox("Mes", range(1, 13), index=hoy.month - 1,
                       format_func=lambda m:
                       ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
                        "Septiembre", "Octubre", "Noviembre", "Diciembre"][m - 1])
    evs = [e for e in db.select("eventos") if e["fecha"] and e["fecha"][:7] == f"{año}-{mes:02d}"]
    por_dia = {}
    for e in evs:
        por_dia.setdefault(e["fecha"], []).append(e)
    h = "<table class='cal'><tr>" + "".join(f"<th>{d}</th>" for d in "LMXJVSD") + "</tr>"
    for sem in calendar.Calendar(0).monthdayscalendar(año, mes):
        h += "<tr>"
        for d in sem:
            if d == 0:
                h += "<td class='off'></td>"
                continue
            items = "".join(
                f"<div class='ev' style='background:{COLOR[e['estado']]}'>{escape(e.get('hora_inicio') or '')} {escape(e['titulo'])}</div>"
                for e in por_dia.get(date(año, mes, d).isoformat(), []))
            h += f"<td><b>{d}</b>{items}</td>"
        h += "</tr>"
    st.markdown(h + "</table>", unsafe_allow_html=True)
    st.caption("  ".join(f"<span style='background:{c};padding:1px 8px;border-radius:4px'>{k}</span>"
                          for k, c in COLOR.items()), unsafe_allow_html=True)
    with st.expander("➕ Anotar nuevo evento", expanded=not evs):
        evento_form("nuevo_agenda")


def pag_clientes():
    banner("Clientes")
    buscar = st.text_input("Buscar", placeholder="Nombre, teléfono o email")
    cs = [c for c in db.select("clientes", order="nombre")
          if buscar.lower() in (c["nombre"] + (c["telefono"] or "") + (c["email"] or "")).lower()]
    if cs:
        st.dataframe(pd.DataFrame(cs)[["nombre", "telefono", "email", "nif"]], hide_index=True, width="stretch")
    sel = st.selectbox("Editar cliente", [None] + [c["id"] for c in cs],
                       format_func=lambda i: "➕ Nuevo cliente" if i is None else next(c["nombre"] for c in cs if c["id"] == i))
    c = next((x for x in cs if x["id"] == sel), {})
    with st.form(f"cliente_{sel}"):
        nombre = st.text_input("Nombre / razón social", c.get("nombre", ""))
        a, b = st.columns(2)
        tel = a.text_input("Teléfono", c.get("telefono") or "")
        mail = b.text_input("Email", c.get("email") or "")
        nif = a.text_input("NIF/CIF", c.get("nif") or "")
        dire = b.text_input("Dirección", c.get("direccion") or "")
        notas = st.text_area("Notas", c.get("notas") or "")
        ok = st.form_submit_button("Guardar", type="primary")
    if ok and nombre.strip():
        row = {"nombre": nombre, "telefono": tel, "email": mail, "nif": nif, "direccion": dire, "notas": notas}
        db.update("clientes", sel, row) if sel else db.insert("clientes", row)
        st.rerun()
    if sel and st.button("🗑️ Eliminar cliente"):
        db.delete("clientes", sel)
        st.rerun()


def pag_eventos():
    banner("Eventos")
    cl = clientes_map()
    filtro = st.multiselect("Estado", ESTADOS_EVENTO, default=[e for e in ESTADOS_EVENTO if e != "Cancelado"])
    evs = [e for e in db.select("eventos", order="fecha", desc=True) if e["estado"] in filtro]
    if evs:
        st.dataframe(pd.DataFrame([{"Fecha": fmt_fecha(e["fecha"]), "Evento": e["titulo"], "Tipo": e["tipo"],
                                    "Cliente": cl.get(e["cliente_id"], {}).get("nombre", ""), "Lugar": e["lugar"],
                                    "Estado": e["estado"]} for e in evs]), hide_index=True, width="stretch")
    sel = st.selectbox("Editar evento", [None] + [e["id"] for e in evs],
                       format_func=lambda i: "➕ Nuevo evento" if i is None else
                       next(f"{fmt_fecha(e['fecha'])} · {e['titulo']}" for e in evs if e["id"] == i))
    evento_form(f"evento_{sel}", next((e for e in evs if e["id"] == sel), None))
    if sel and st.button("🗑️ Eliminar evento (y sus presupuestos)"):
        db.delete("eventos", sel)
        st.rerun()


def pag_servicios():
    banner("Catálogo de servicios")
    seed_servicios()
    ss = db.select("servicios", order="nombre")
    df = st.data_editor(pd.DataFrame(ss)[["id", "nombre", "descripcion", "precio"]], hide_index=True,
                        disabled=["id"], width="stretch", key="ed_serv",
                        column_config={"precio": st.column_config.NumberColumn("Precio €", format="%.2f")})
    if st.button("Guardar cambios", type="primary"):
        for r in df.to_dict("records"):
            db.update("servicios", int(r["id"]), {"nombre": r["nombre"], "descripcion": r["descripcion"],
                                                  "precio": float(r["precio"] or 0)})
        st.success("Catálogo actualizado")
    with st.form("nuevo_serv", clear_on_submit=True):
        a, b, c = st.columns([2, 3, 1])
        n, d, pr = a.text_input("Nombre"), b.text_input("Descripción"), c.number_input("Precio €", 0.0, step=10.0)
        if st.form_submit_button("➕ Añadir servicio") and n:
            db.insert("servicios", {"nombre": n, "descripcion": d, "precio": pr})
            st.rerun()
    borrar = st.selectbox("Eliminar servicio", [None] + [s["id"] for s in ss],
                          format_func=lambda i: "—" if i is None else next(s["nombre"] for s in ss if s["id"] == i))
    if borrar and st.button("🗑️ Eliminar"):
        db.delete("servicios", borrar)
        st.rerun()


def pag_presupuestos():
    banner("Presupuestos")
    seed_servicios()
    cl, evs = clientes_map(), eventos_map()
    tab_n, tab_l = st.tabs(["Nuevo presupuesto", "Seguimiento"])
    with tab_n:
        if not evs:
            st.info("Crea primero un evento.")
        else:
            eid = st.selectbox("Evento", list(evs), format_func=lambda i: f"{fmt_fecha(evs[i]['fecha'])} · {evs[i]['titulo']}")
            ev = evs[eid]
            cat = {s["nombre"]: s for s in db.select("servicios")}
            ini = [{"concepto": f"{n} — {cat[n]['descripcion']}" if cat[n].get("descripcion") else n,
                    "cantidad": 1.0, "precio": float(cat[n]["precio"] or 0)}
                   for n in (ev.get("servicios") or []) if n in cat]
            st.caption("Edita las líneas libremente (puedes añadir filas). Servicios del evento precargados.")
            df = st.data_editor(lineas_df(ini), num_rows="dynamic", width="stretch", key=f"lin_{eid}",
                                column_config={"precio": st.column_config.NumberColumn("Precio €", format="%.2f"),
                                               "cantidad": st.column_config.NumberColumn("Cant.", min_value=0)})
            a, b, c = st.columns(3)
            desc = a.number_input("Descuento %", 0.0, 100.0, 0.0)
            iva = b.number_input("IVA %", 0.0, 30.0, 21.0)
            val = c.number_input("Validez (días)", 1, 90, 15)
            cond = st.text_area("Condiciones", CONDICIONES)
            lineas = df_a_lineas(df)
            t = pdfs.totales(lineas, desc, iva)
            st.markdown(f"**Base:** {pdfs.eur(t['base'])} · **IVA:** {pdfs.eur(t['cuota'])} · **TOTAL: {pdfs.eur(t['total'])}**")
            if st.button("Crear presupuesto", type="primary", disabled=not lineas):
                num = db.siguiente_numero("presupuestos", "PRE")
                db.insert("presupuestos", {"numero": num, "evento_id": eid, "cliente_id": ev["cliente_id"],
                                           "fecha": date.today().isoformat(), "validez_dias": val, "lineas": lineas,
                                           "descuento": desc, "iva": iva, "condiciones": cond})
                if ev["estado"] == "Consulta":
                    db.update("eventos", eid, {"estado": "Presupuestado"})
                st.success(f"Presupuesto {num} creado. Míralo en Seguimiento.")
    with tab_l:
        for p in db.select("presupuestos", order="created_at", desc=True):
            ev, cli = evs.get(p["evento_id"], {}), cl.get(p["cliente_id"], {})
            tot = pdfs.totales(p["lineas"], p["descuento"], p["iva"])["total"]
            with st.expander(f"{p['numero']} · {ev.get('titulo', '—')} · {pdfs.eur(tot)} · {p['estado']}"):
                nuevo = st.selectbox("Estado", ESTADOS_PRESU, index=ESTADOS_PRESU.index(p["estado"]), key=f"est_{p['id']}")
                if nuevo != p["estado"]:
                    db.update("presupuestos", p["id"], {"estado": nuevo})
                    if nuevo == "Aceptado" and ev:
                        db.update("eventos", ev["id"], {"estado": "Confirmado"})
                    st.rerun()
                vence = (date.fromisoformat(p["fecha"]) + timedelta(days=p["validez_dias"]))
                pdf = pdfs.documento("Presupuesto", p["numero"], EMPRESA, cli, ev, p["lineas"], p["descuento"], p["iva"],
                                     p["fecha"], f"Válido hasta {fmt_fecha(vence)}", p["condiciones"])
                x, y, z = st.columns(3)
                x.download_button("📄 PDF", pdf, f"{p['numero']}.pdf", "application/pdf", key=f"pdf_{p['id']}")
                msg = (f"Hola {cli.get('nombre', '')}, te paso el presupuesto {p['numero']} para {ev.get('titulo', '')} "
                       f"({pdfs.eur(tot)}). Quedo atento. {EMPRESA['nombre']}")
                tel = "".join(ch for ch in (cli.get("telefono") or "") if ch.isdigit())
                if tel:
                    y.link_button("💬 WhatsApp", f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}")
                if cli.get("email"):
                    z.link_button("✉️ Email", f"mailto:{cli['email']}?subject={urllib.parse.quote('Presupuesto ' + p['numero'])}"
                                              f"&body={urllib.parse.quote(msg)}")
                if p["estado"] == "Aceptado":
                    st.caption("Cuando el evento se realice, factúralo desde la sección Facturación.")
                if st.button("🗑️ Eliminar presupuesto", key=f"del_{p['id']}"):
                    db.delete("presupuestos", p["id"])
                    st.rerun()


def pag_guiones():
    banner("Guion del evento")
    cl, evs = clientes_map(), eventos_map()
    if not evs:
        st.info("Crea primero un evento.")
        return
    eid = st.selectbox("Evento", list(evs), format_func=lambda i: f"{fmt_fecha(evs[i]['fecha'])} · {evs[i]['titulo']}")
    ev = evs[eid]
    key, vkey = f"guion_{eid}", f"ver_{eid}"
    if key not in st.session_state:
        st.session_state[key] = ev.get("guion") or []
    st.session_state.setdefault(vkey, 0)
    if st.session_state.get("guion_msg"):
        st.success(st.session_state.pop("guion_msg"))

    with st.expander("📥 Cargar el guion desde un texto", expanded=not st.session_state[key]):
        st.caption("Pega todas las indicaciones del cliente (horas, momentos, canciones, normas…) o sube un .txt. "
                   "Las líneas que empiezan por una hora (18:00, 21h, 00:00 a 03:00) se convierten en momentos; "
                   "lo demás se añade como detalle o como indicaciones generales.")
        archivo = st.file_uploader("Fichero de texto (.txt o .md)", type=["txt", "md"], key=f"up_{eid}")
        texto = st.text_area("Texto con las indicaciones", height=220, key=f"txt_{eid}",
                             placeholder="Indicaciones: no poner reggaeton\n18:00 Llegada de invitados - música ambiente\n"
                                         "18:30 Ceremonia: entrada de novios. Música: Perfect\n00:00 Discomóvil. Estilos: pop, latino, 80s")
        if archivo and not texto.strip():
            raw = archivo.getvalue()
            try:
                texto = raw.decode("utf-8")
            except UnicodeDecodeError:
                texto = raw.decode("latin-1")
        c1, c2 = st.columns(2)
        hay_ia = bool(st.secrets.get("ANTHROPIC_API_KEY"))
        modo = c1.radio("Cómo organizarlo", ["Reglas automáticas"] + (["IA (Claude)"] if hay_ia else []),
                        horizontal=True, key=f"modo_{eid}",
                        help="La IA entiende textos desordenados. Se activa añadiendo ANTHROPIC_API_KEY en los Secrets.")
        accion = c2.radio("Si ya hay un guion", ["Reemplazarlo", "Añadir al final"], horizontal=True, key=f"acc_{eid}")
        if st.button("✨ Organizar texto", type="primary", disabled=not texto.strip(), key=f"org_{eid}"):
            try:
                if modo.startswith("IA"):
                    with st.spinner("Organizando con IA…"):
                        nuevos = guion_texto.organizar_ia(texto, st.secrets["ANTHROPIC_API_KEY"],
                                                          st.secrets.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
                else:
                    nuevos = guion_texto.parse_texto(texto)
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo organizar el texto: {e}")
                nuevos = []
            if nuevos:
                st.session_state[key] = (st.session_state[key] + nuevos) if accion.startswith("Añadir") else nuevos
                st.session_state[vkey] += 1
                st.session_state["guion_msg"] = f"{len(nuevos)} bloques cargados. Revisa la tabla, corrige lo que haga falta y pulsa Guardar."
                st.rerun()
            elif not modo.startswith("IA"):
                st.warning("No he encontrado horas en el texto. Empieza cada línea con la hora (por ejemplo «18:00 Ceremonia») o usa la IA.")

    st.caption("O carga una plantilla (sustituye el guion actual):")
    cols = st.columns(len(PLANTILLAS))
    for col, (nombre, filas) in zip(cols, PLANTILLAS.items()):
        if col.button(nombre, key=f"pl_{nombre}_{eid}"):
            st.session_state[key] = [dict(zip(("hora", "momento", "detalle", "musica"), f)) for f in filas]
            st.session_state[vkey] += 1
            st.rerun()
    base = pd.DataFrame(st.session_state[key], columns=["hora", "momento", "detalle", "musica"]).fillna("").astype(str)
    df = st.data_editor(base, num_rows="dynamic", width="stretch", key=f"ed_{eid}_{st.session_state[vkey]}",
                        column_config={"hora": st.column_config.TextColumn("Hora", default="", width="small"),
                                       "momento": st.column_config.TextColumn("Momento", default=""),
                                       "detalle": st.column_config.TextColumn("Detalle", default="", width="large"),
                                       "musica": st.column_config.TextColumn("Música / notas", default="", width="medium")})
    items = [r for r in df.fillna("").to_dict("records") if str(r["momento"]).strip() or str(r["hora"]).strip() or str(r["detalle"]).strip()]
    a, b, c = st.columns(3)
    if a.button("💾 Guardar guion", type="primary"):
        db.update("eventos", eid, {"guion": items})
        st.session_state[key] = items
        st.success("Guion guardado")
    if b.button("↕️ Ordenar por hora"):
        st.session_state[key] = sorted(items, key=lambda r: (bool(str(r["hora"]).strip()), guion_texto.hora_clave(r["hora"])))
        st.session_state[vkey] += 1
        st.rerun()
    c.download_button("📄 PDF corporativo", pdfs.guion(EMPRESA, ev, cl.get(ev["cliente_id"]), items),
                      f"guion_{ev['titulo']}.pdf", "application/pdf")


def _uid():
    return datetime.now().strftime("%H%M%S%f")


def facturado_base(facturas, pid):
    """Base imponible ya facturada de un presupuesto (las rectificativas restan)."""
    return sum(pdfs.totales(f["lineas"], f["descuento"], 0)["imponible"]
               for f in facturas if f.get("presupuesto_id") == pid)


def emisor_actual():
    return {k: EMPRESA.get(k, "") for k in ("razon_social", "nombre", "nif", "direccion", "telefono", "email", "iban")}


def total_factura(f):
    return pdfs.totales(f["lineas"], f["descuento"], f["iva"], f.get("retencion") or 0)["total"]


def form_factura(draft, facturas):
    cl, evs = clientes_map(), eventos_map()
    uid = draft["uid"]
    pres = db.get("presupuestos", draft["presupuesto_id"]) if draft.get("presupuesto_id") else None
    ev = evs.get(pres["evento_id"], {}) if pres else {}
    cid = pres["cliente_id"] if pres else None
    st.markdown(f"### 🧾 Emitir factura · {'presupuesto ' + pres['numero'] if pres else 'manual'}")

    if not pres:
        cid = st.selectbox("Cliente guardado", [None] + list(cl), key=f"{uid}_cid",
                           format_func=lambda i: "— Introducir los datos a mano —" if i is None else cl[i]["nombre"])
    cli = cl.get(cid, {})

    st.markdown("**Datos de facturación del cliente** — se rellenan con su ficha y puedes cambiarlos solo para esta factura")
    c1, c2 = st.columns(2)
    tipo = c1.radio("Tipo de cliente", ["Particular", "Empresa / autónomo"], horizontal=True, key=f"{uid}_tipo_{cid}")
    nombre = c1.text_input("Nombre y apellidos o razón social", cli.get("nombre", ""), key=f"{uid}_nom_{cid}")
    nif = c2.text_input("NIF / CIF" + (" (obligatorio)" if tipo != "Particular" else ""), cli.get("nif") or "", key=f"{uid}_nif_{cid}")
    email = c2.text_input("Email", cli.get("email") or "", key=f"{uid}_mail_{cid}")
    direccion = st.text_input("Domicilio completo (calle, CP, población, provincia)", cli.get("direccion") or "",
                              key=f"{uid}_dir_{cid}")

    if pres:
        presu_imp = pdfs.totales(pres["lineas"], pres["descuento"], 0)["imponible"]
        ya = facturado_base(facturas, pres["id"])
        pendiente = round(presu_imp - ya, 2)
        pct = st.select_slider("% del presupuesto a facturar ahora", options=list(range(10, 101, 10)),
                               value=draft.get("pct", 100), key=f"{uid}_pct")
        if ya:
            st.info(f"Ya facturado: {pdfs.eur(ya)} (base imponible). Pendiente: {pdfs.eur(pendiente)}.")
        titulo = ev.get("titulo", "")
        if pct == 100 and not ya:
            ini, desc0 = pres["lineas"], pres["descuento"]
        elif pct == 100:
            ini, desc0 = [{"concepto": f"Resto del presupuesto {pres['numero']} — {titulo}", "cantidad": 1.0,
                           "precio": pendiente}], 0
        else:
            ini, desc0 = [{"concepto": f"Anticipo {pct}% del presupuesto {pres['numero']} — {titulo}",
                           "cantidad": 1.0, "precio": round(presu_imp * pct / 100, 2)}], 0
        iva0 = float(pres["iva"])
    else:
        pct, ini, desc0, iva0 = 100, [], 0, 21.0

    st.markdown("**Conceptos**")
    df = st.data_editor(lineas_df(ini), num_rows="dynamic", width="stretch", key=f"{uid}_lin_{pct}_{cid}",
                        column_config={"precio": st.column_config.NumberColumn("Precio €", format="%.2f"),
                                       "cantidad": st.column_config.NumberColumn("Cant.", min_value=0)})
    d1, d2, d3 = st.columns(3)
    f_exp = d1.date_input("Fecha de expedición", date.today(), key=f"{uid}_fe")
    f_op = d2.date_input("Fecha de la operación (evento)",
                         date.fromisoformat(ev["fecha"]) if ev.get("fecha") else date.today(), key=f"{uid}_fo")
    venc = d3.date_input("Vencimiento", date.today() + timedelta(days=15), key=f"{uid}_fv")
    e1, e2, e3 = st.columns(3)
    desc = e1.number_input("Descuento %", 0.0, 100.0, float(desc0), key=f"{uid}_desc_{pct}")
    iva = e2.number_input("IVA %", 0.0, 30.0, iva0, key=f"{uid}_iva")
    ret = e3.number_input("Retención IRPF %", 0.0, 30.0, 0.0, key=f"{uid}_ret",
                          help="Solo si facturas como autónomo a una empresa o profesional y te corresponde. Consúltalo con tu gestor.")
    metodo = st.text_input("Forma de pago", "Transferencia bancaria", key=f"{uid}_met")
    notas = st.text_area("Observaciones (si el IVA es 0%, indica aquí la exención o no sujeción)", key=f"{uid}_notas")

    lineas = df_a_lineas(df)
    t = pdfs.totales(lineas, desc, iva, ret)
    st.markdown(f"**Base imponible:** {pdfs.eur(t['imponible'])} · **IVA:** {pdfs.eur(t['cuota'])}"
                + (f" · **Retención:** -{pdfs.eur(t['ret'])}" if ret else "") + f" · **TOTAL: {pdfs.eur(t['total'])}**")

    b1, b2, _ = st.columns([1, 1, 3])
    if b2.button("Cancelar", key=f"{uid}_can"):
        st.session_state.pop("fact_draft", None)
        st.rerun()
    if b1.button("✅ Emitir factura", type="primary", key=f"{uid}_ok"):
        emisor = emisor_actual()
        err = []
        if not (emisor["razon_social"] or emisor["nombre"]) or not emisor["nif"] or not emisor["direccion"]:
            err.append("Faltan datos del emisor: añade `nif` y `direccion` (y `razon_social`) en la sección [empresa] de los Secrets.")
        if not nombre.strip() or not direccion.strip():
            err.append("El nombre y el domicilio del cliente son obligatorios.")
        if tipo != "Particular" and not nif.strip():
            err.append("Para una empresa o autónomo el NIF/CIF es obligatorio.")
        if not lineas or t["base"] <= 0:
            err.append("Añade al menos un concepto con importe.")
        if float(iva) == 0 and not notas.strip():
            err.append("Con IVA 0% debes indicar el motivo legal en Observaciones.")
        if err:
            for e in err:
                st.error(e)
            return
        num = db.siguiente_numero("facturas", "FAC")
        db.insert("facturas", {
            "numero": num, "presupuesto_id": pres["id"] if pres else None,
            "evento_id": pres["evento_id"] if pres else None, "cliente_id": cid,
            "fecha": f_exp.isoformat(), "fecha_operacion": f_op.isoformat(), "vencimiento": venc.isoformat(),
            "lineas": lineas, "descuento": desc, "iva": iva, "retencion": ret, "estado": "Pendiente",
            "metodo_pago": metodo, "notas": notas, "emisor": emisor,
            "cliente_datos": {"nombre": nombre.strip(), "nif": nif.strip(), "direccion": direccion.strip(),
                              "email": email.strip(), "telefono": cli.get("telefono") or "", "tipo": tipo}})
        if pres and ev.get("estado") == "Confirmado" and pct == 100:
            db.update("eventos", ev["id"], {"estado": "Realizado"})
        st.session_state.pop("fact_draft", None)
        st.session_state["fact_ok"] = num
        st.rerun()


def rectificar(f, motivo):
    num = db.siguiente_numero("facturas", "REC")
    db.insert("facturas", {
        "numero": num, "presupuesto_id": f.get("presupuesto_id"), "evento_id": f.get("evento_id"),
        "cliente_id": f.get("cliente_id"), "fecha": date.today().isoformat(),
        "fecha_operacion": f.get("fecha_operacion"), "lineas": [{**l, "cantidad": -float(l["cantidad"])} for l in f["lineas"]],
        "descuento": f["descuento"], "iva": f["iva"], "retencion": f.get("retencion") or 0, "estado": "Pendiente",
        "metodo_pago": f.get("metodo_pago"), "notas": f"Motivo de la rectificación: {motivo}",
        "emisor": f.get("emisor"), "cliente_datos": f.get("cliente_datos"), "rectifica_a": f["numero"]})
    return num


def pag_facturas():
    banner("Facturación")
    cl, evs = clientes_map(), eventos_map()
    fs = db.select("facturas", order="created_at", desc=True)
    presus = db.select("presupuestos", order="fecha")
    if st.session_state.get("fact_ok"):
        st.success(f"Factura {st.session_state.pop('fact_ok')} emitida. La tienes en la pestaña «Emitidas» para descargarla.")

    pend_fact = []
    for p in presus:
        if p["estado"] != "Aceptado":
            continue
        imp = pdfs.totales(p["lineas"], p["descuento"], 0)["imponible"]
        pend = round(imp - facturado_base(fs, p["id"]), 2)
        ev = evs.get(p["evento_id"], {})
        if pend > 0.01 and ev.get("estado") != "Cancelado":
            pend_fact.append((p, ev, pend))

    a, b, c = st.columns(3)
    a.metric("Facturado", pdfs.eur(sum(total_factura(f) for f in fs)))
    b.metric("Pendiente de cobro", pdfs.eur(sum(total_factura(f) for f in fs if f["estado"] == "Pendiente")))
    c.metric("Pendiente de facturar (con IVA)", pdfs.eur(sum(pend * (1 + float(p["iva"]) / 100) for p, _, pend in pend_fact)))

    if st.session_state.get("fact_draft"):
        form_factura(st.session_state["fact_draft"], fs)
        st.divider()

    t1, t2, t3 = st.tabs(["Para facturar", "Factura manual", "Emitidas"])
    with t1:
        hechos = [x for x in pend_fact if x[1].get("estado") == "Realizado"]
        st.markdown("**Presupuestos aceptados con el evento ya realizado**")
        if not hechos:
            st.caption("No hay nada pendiente de facturar.")
        for p, ev, pend in hechos:
            cli = cl.get(p["cliente_id"], {})
            x, y = st.columns([4, 1])
            x.write(f"**{p['numero']}** · {ev.get('titulo', '')} · {cli.get('nombre', '')} · {fmt_fecha(ev.get('fecha'))} · "
                    f"pendiente {pdfs.eur(pend * (1 + float(p['iva']) / 100))}")
            if y.button("🧾 Facturar", key=f"fp_{p['id']}"):
                st.session_state["fact_draft"] = {"uid": _uid(), "presupuesto_id": p["id"], "pct": 100}
                st.rerun()
        otros = [x for x in pend_fact if x[1].get("estado") != "Realizado"]
        if otros:
            with st.expander(f"Aceptados cuyo evento aún no consta como realizado ({len(otros)})"):
                for p, ev, pend in otros:
                    pasado = bool(ev.get("fecha")) and ev["fecha"] < date.today().isoformat()
                    st.write(f"**{p['numero']}** · {ev.get('titulo', '')} · {fmt_fecha(ev.get('fecha'))}" + (" · ⚠️ fecha ya pasada" if pasado else ""))
                    x, y, _ = st.columns([1, 1, 3])
                    if x.button("✅ Marcar realizado", key=f"rz_{p['id']}"):
                        db.update("eventos", ev["id"], {"estado": "Realizado"})
                        st.rerun()
                    if y.button("💶 Facturar anticipo", key=f"ant_{p['id']}"):
                        st.session_state["fact_draft"] = {"uid": _uid(), "presupuesto_id": p["id"], "pct": 30}
                        st.rerun()
        with st.expander("ℹ️ Qué debe llevar una factura en España y Verifactu"):
            st.markdown(
                "- Número correlativo (y serie), fecha de expedición y fecha de la operación si es distinta.\n"
                "- Nombre o razón social, NIF y domicilio del emisor y del cliente (el NIF del cliente es obligatorio si es empresa o autónomo).\n"
                "- Descripción de los servicios, base imponible, tipo de IVA y cuota, y total.\n"
                "- Con IVA 0%, la mención de la exención o no sujeción.\n"
                "- Las facturas emitidas **no se borran**: si hay un error, se emite una factura rectificativa.\n\n"
                "Esta app genera facturas con ese contenido, pero **no implementa Verifactu** (huella, QR y registro). "
                "Según el BOE, los programas de facturación deben cumplirlo antes del 1/1/2027 (sociedades) o 1/7/2027 (autónomos). "
                "Consúltalo con tu gestor.")
    with t2:
        st.caption("Para facturar algo que no viene de un presupuesto. Puedes elegir un cliente guardado o escribir los datos.")
        if st.button("➕ Nueva factura manual"):
            st.session_state["fact_draft"] = {"uid": _uid(), "presupuesto_id": None}
            st.rerun()
    with t3:
        rectificadas = {f.get("rectifica_a") for f in fs if f.get("rectifica_a")}
        for f in fs:
            ev = evs.get(f.get("evento_id"), {})
            cli = f.get("cliente_datos") or cl.get(f.get("cliente_id"), {})
            marca = " · rectificada" if f["numero"] in rectificadas else ""
            with st.expander(f"{f['numero']} · {cli.get('nombre', '—')} · {pdfs.eur(total_factura(f))} · {f['estado']}{marca}"):
                c1, c2 = st.columns(2)
                est = c1.selectbox("Estado", ESTADOS_FACT, index=ESTADOS_FACT.index(f["estado"]), key=f"fe_{f['id']}")
                met = c2.text_input("Forma de pago", f.get("metodo_pago") or "", key=f"fm_{f['id']}")
                if est != f["estado"] or met != (f.get("metodo_pago") or ""):
                    db.update("facturas", f["id"], {"estado": est, "metodo_pago": met})
                    st.rerun()
                emisor = f.get("emisor") or emisor_actual()
                pago = (f.get("metodo_pago") or "Transferencia bancaria")
                if emisor.get("iban"):
                    pago += f"\nIBAN: {emisor['iban']}"
                if f.get("vencimiento"):
                    pago += f"\nVencimiento: {fmt_fecha(f['vencimiento'])}"
                pdf = pdfs.documento("Factura rectificativa" if f.get("rectifica_a") else "Factura", f["numero"], emisor, cli, ev,
                                     f["lineas"], f["descuento"], f["iva"], f["fecha"], pago=pago,
                                     retencion=f.get("retencion") or 0, fecha_operacion=f.get("fecha_operacion"),
                                     rectifica_a=f.get("rectifica_a") or "", notas=f.get("notas") or "")
                x, y, _ = st.columns([1, 1, 2])
                x.download_button("📄 Descargar PDF", pdf, f"{f['numero']}.pdf", "application/pdf", key=f"fpdf_{f['id']}")
                if cli.get("email"):
                    cuerpo = (f"Hola {cli.get('nombre', '')},\n\nTe adjunto la factura {f['numero']} por importe de "
                              f"{pdfs.eur(total_factura(f))}.\n\nUn saludo,\n{emisor.get('razon_social') or emisor.get('nombre', '')}")
                    y.link_button("✉️ Preparar email", f"mailto:{cli['email']}?subject={urllib.parse.quote('Factura ' + f['numero'])}"
                                                      f"&body={urllib.parse.quote(cuerpo)}")
                    st.caption("Descarga el PDF y adjúntalo al correo (el enlace no puede adjuntarlo solo).")
                if not f.get("rectifica_a") and f["numero"] not in rectificadas:
                    motivo = st.text_input("Motivo para rectificar esta factura", key=f"mot_{f['id']}")
                    if st.button("↩️ Emitir factura rectificativa (anula esta factura)", key=f"rec_{f['id']}"):
                        if motivo.strip():
                            num = rectificar(f, motivo.strip())
                            st.session_state["fact_ok"] = num
                            st.rerun()
                        else:
                            st.error("Indica el motivo de la rectificación.")
                if st.secrets.get("MODO_PRUEBAS") and st.button("🗑️ Borrar (solo modo pruebas)", key=f"fdel_{f['id']}"):
                    db.delete("facturas", f["id"])
                    st.rerun()


# ---------- navegación ----------
login()
css()
PAGINAS = {
    "🏠 Panel": pag_panel,
    "1️⃣ Clientes": pag_clientes,
    "2️⃣ Eventos": pag_eventos,
    "3️⃣ Presupuestos": pag_presupuestos,
    "4️⃣ Guiones": pag_guiones,
    "5️⃣ Facturación": pag_facturas,
    "📅 Agenda": pag_agenda,
    "🎛️ Servicios y tarifas": pag_servicios,
}
with st.sidebar:
    try:
        st.image("assets/logo.png", width=140)
    except Exception:
        st.title(EMPRESA["nombre"])
    st.markdown("### Party Management")
    pagina = st.radio("Menú", list(PAGINAS), label_visibility="collapsed")
PAGINAS[pagina]()
