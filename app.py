import calendar
import urllib.parse
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

import db
import pdfs

st.set_page_config(page_title="Party Management", page_icon="🎧", layout="wide")

EMPRESA = {"nombre": "PartyDisco", "lema": "Musical Emotions", "nif": "", "direccion": "",
           "telefono": "", "email": "", "iban": "", **dict(st.secrets.get("empresa", {}))}

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
}


# ---------- utilidades ----------
def login():
    pw = st.secrets.get("APP_PASSWORD")
    if not pw or st.session_state.get("ok"):
        return
    st.title("🎧 Party Management")
    entrada = st.text_input("Contraseña", type="password")
    if st.button("Entrar") and entrada == pw:
        st.session_state["ok"] = True
        st.rerun()
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
    imp_pend = sum(pdfs.totales(f["lineas"], f["descuento"], f["iva"])["total"] for f in pend)
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
            "Lugar": e["lugar"], "Estado": e["estado"]} for e in futuros]), hide_index=True, use_container_width=True)
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
        st.dataframe(pd.DataFrame(cs)[["nombre", "telefono", "email", "nif"]], hide_index=True, use_container_width=True)
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
                                    "Estado": e["estado"]} for e in evs]), hide_index=True, use_container_width=True)
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
                        disabled=["id"], use_container_width=True, key="ed_serv",
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
            df = st.data_editor(lineas_df(ini), num_rows="dynamic", use_container_width=True, key=f"lin_{eid}",
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
                st.divider()
                pct = st.slider("Facturar % del presupuesto", 10, 100, 100, 10, key=f"pct_{p['id']}")
                if st.button("🧾 Crear factura", key=f"fac_{p['id']}"):
                    if pct == 100:
                        lin, des = p["lineas"], p["descuento"]
                    else:
                        base = pdfs.totales(p["lineas"], p["descuento"], 0)["imponible"] * pct / 100
                        lin = [{"concepto": f"{pct}% del presupuesto {p['numero']} ({ev.get('titulo', '')})",
                                "cantidad": 1, "precio": round(base, 2)}]
                        des = 0
                    num = db.siguiente_numero("facturas", "FAC")
                    db.insert("facturas", {"numero": num, "presupuesto_id": p["id"], "evento_id": p["evento_id"],
                                           "cliente_id": p["cliente_id"], "lineas": lin, "descuento": des, "iva": p["iva"],
                                           "vencimiento": (date.today() + timedelta(days=15)).isoformat()})
                    st.success(f"Factura {num} creada en Facturación")
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
    key = f"guion_{eid}"
    if key not in st.session_state:
        st.session_state[key] = ev.get("guion") or []
    st.caption("Cargar plantilla (sustituye el guion actual):")
    cols = st.columns(len(PLANTILLAS))
    for col, (nombre, filas) in zip(cols, PLANTILLAS.items()):
        if col.button(nombre, key=f"pl_{nombre}_{eid}"):
            st.session_state[key] = [dict(zip(("hora", "momento", "detalle", "musica"), f)) for f in filas]
            st.session_state.pop(f"ed_{eid}", None)
            st.rerun()
    base = pd.DataFrame(st.session_state[key], columns=["hora", "momento", "detalle", "musica"]).fillna("")
    df = st.data_editor(base, num_rows="dynamic", use_container_width=True, key=f"ed_{eid}_{len(base)}",
                        column_config={"hora": "Hora", "momento": "Momento", "detalle": "Detalle", "musica": "Música / notas"})
    items = [r for r in df.fillna("").to_dict("records") if str(r["momento"]).strip() or str(r["hora"]).strip()]
    a, b, c = st.columns(3)
    if a.button("💾 Guardar guion", type="primary"):
        db.update("eventos", eid, {"guion": items})
        st.session_state[key] = items
        st.success("Guion guardado")
    if b.button("↕️ Ordenar por hora"):
        st.session_state[key] = sorted(items, key=lambda r: r["hora"])
        st.rerun()
    c.download_button("📄 PDF corporativo", pdfs.guion(EMPRESA, ev, cl.get(ev["cliente_id"]), items),
                      f"guion_{ev['titulo']}.pdf", "application/pdf")


def pag_facturas():
    banner("Facturación")
    cl, evs = clientes_map(), eventos_map()
    fs = db.select("facturas", order="created_at", desc=True)
    tot = [(f, pdfs.totales(f["lineas"], f["descuento"], f["iva"])["total"]) for f in fs]
    a, b = st.columns(2)
    a.metric("Facturado", pdfs.eur(sum(t for _, t in tot)))
    b.metric("Pendiente de cobro", pdfs.eur(sum(t for f, t in tot if f["estado"] == "Pendiente")))
    for f, t in tot:
        ev, cli = evs.get(f["evento_id"], {}), cl.get(f["cliente_id"], {})
        with st.expander(f"{f['numero']} · {cli.get('nombre', '—')} · {pdfs.eur(t)} · {f['estado']}"):
            c1, c2 = st.columns(2)
            est = c1.selectbox("Estado", ESTADOS_FACT, index=ESTADOS_FACT.index(f["estado"]), key=f"fe_{f['id']}")
            met = c2.text_input("Método de pago", f.get("metodo_pago") or "", key=f"fm_{f['id']}")
            if est != f["estado"] or met != (f.get("metodo_pago") or ""):
                db.update("facturas", f["id"], {"estado": est, "metodo_pago": met})
                st.rerun()
            pago = f"Transferencia a {EMPRESA['iban']}" if EMPRESA.get("iban") else ""
            pdf = pdfs.documento("Factura", f["numero"], EMPRESA, cli, ev, f["lineas"], f["descuento"], f["iva"],
                                 f["fecha"], f"Vencimiento {fmt_fecha(f['vencimiento'])}" if f.get("vencimiento") else "",
                                 pago=pago)
            st.download_button("📄 PDF", pdf, f"{f['numero']}.pdf", "application/pdf", key=f"fpdf_{f['id']}")
            if st.button("🗑️ Eliminar", key=f"fdel_{f['id']}"):
                db.delete("facturas", f["id"])
                st.rerun()


# ---------- navegación ----------
login()
css()
PAGINAS = {"🏠 Panel": pag_panel, "📅 Agenda": pag_agenda, "🎉 Eventos": pag_eventos, "👥 Clientes": pag_clientes,
           "💶 Presupuestos": pag_presupuestos, "📝 Guiones": pag_guiones, "🧾 Facturación": pag_facturas,
           "🎛️ Servicios": pag_servicios}
with st.sidebar:
    try:
        st.image("assets/logo.png", width=140)
    except Exception:
        st.title(EMPRESA["nombre"])
    st.markdown("### Party Management")
    pagina = st.radio("Menú", list(PAGINAS), label_visibility="collapsed")
PAGINAS[pagina]()
