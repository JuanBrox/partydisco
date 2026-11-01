"""PDFs con diseño corporativo PartyDisco: presupuestos, facturas y guiones."""
import os
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

NAVY = colors.HexColor("#0A1A6E")
LILAC = colors.HexColor("#E0C3FC")
SKY = colors.HexColor("#8EC5FC")
SOFT = colors.HexColor("#F4EFFC")
LOGO = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

ST = {
    "n": ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#222222")),
    "b": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=NAVY),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=NAVY, alignment=2),
    "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#555555"), alignment=2),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=4),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10.5, textColor=colors.HexColor("#555555")),
}


def eur(x):
    return f"{float(x):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def fdate(d):
    if not d:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d[:10])
    return d.strftime("%d/%m/%Y")


def p(txt, style="n"):
    return Paragraph(escape(str(txt or "")).replace("\n", "<br/>"), ST[style])


def totales(lineas, descuento=0, iva=21, retencion=0):
    base = sum(float(l.get("cantidad") or 0) * float(l.get("precio") or 0) for l in lineas)
    desc = base * float(descuento or 0) / 100
    imponible = base - desc
    cuota = imponible * float(iva or 0) / 100
    ret = imponible * float(retencion or 0) / 100
    return {"base": base, "desc": desc, "imponible": imponible, "cuota": cuota, "ret": ret,
            "total": imponible + cuota - ret}


def _footer(empresa):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica", 7.5)
        partes = [empresa.get(k) for k in ("nombre", "nif", "direccion", "telefono", "email") if empresa.get(k)]
        canvas.drawCentredString(A4[0] / 2, 12 * mm, "  ·  ".join(partes))
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Pág. {doc.page}")
        canvas.restoreState()
    return draw


def _header(empresa, titulo, sub):
    if os.path.exists(LOGO):
        logo = Image(LOGO, 28 * mm, 28 * mm)
    else:
        logo = Paragraph(f"<b>{escape(empresa['nombre'])}</b>", ST["b"])
    t = Table([[logo, [Paragraph(escape(titulo), ST["h1"]), Paragraph(escape(sub).replace("\n", "<br/>"), ST["sub"])]]],
              colWidths=[40 * mm, 134 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    band = Table([["", ""]], colWidths=[87 * mm, 87 * mm], rowHeights=[3 * mm])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), LILAC), ("BACKGROUND", (1, 0), (1, 0), SKY)]))
    return [t, Spacer(1, 3), band, Spacer(1, 10)]


def _build(story, empresa, titulo):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=22 * mm, title=titulo, author=empresa["nombre"])
    f = _footer(empresa)
    doc.build(story, onFirstPage=f, onLaterPages=f)
    return buf.getvalue()


def _partes(empresa, cliente):
    rs = empresa.get("razon_social") or empresa["nombre"]
    e = [f"<b>{escape(rs)}</b>"]
    if rs != empresa["nombre"]:
        e.append(f"({escape(empresa['nombre'])})")
    for k, lab in (("nif", "NIF"), ("direccion", ""), ("telefono", "Tel."), ("email", "")):
        if empresa.get(k):
            e.append(f"{lab + ': ' if lab else ''}{escape(empresa[k])}")
    c = ["<b>Cliente</b>"]
    if cliente:
        c.append(escape(cliente.get("nombre") or ""))
        for k, lab in (("nif", "NIF"), ("direccion", ""), ("telefono", "Tel."), ("email", "")):
            if cliente.get(k):
                c.append(f"{lab + ': ' if lab else ''}{escape(cliente[k])}")
    box = Table([[Paragraph("<br/>".join(e), ST["n"]), Paragraph("<br/>".join(c), ST["n"])]],
                colWidths=[87 * mm, 87 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return box


def documento(tipo, numero, empresa, cliente, evento, lineas, descuento, iva, fecha_doc,
              nota_fecha="", condiciones="", pago="", retencion=0, fecha_operacion=None,
              rectifica_a="", notas=""):
    es_factura = tipo.lower().startswith("factura")
    if es_factura:
        sub = f"Fecha de expedición: {fdate(fecha_doc)}"
        if fecha_operacion:
            sub += f"\nFecha de la operación: {fdate(fecha_operacion)}"
        if nota_fecha:
            sub += f"\n{nota_fecha}"
    else:
        sub = f"Fecha: {fdate(fecha_doc)}" + (f"  ·  {nota_fecha}" if nota_fecha else "")
    s = _header(empresa, f"{tipo} {numero}", sub)
    s += [_partes(empresa, cliente), Spacer(1, 8)]
    if rectifica_a:
        s += [Paragraph(f"<b>Esta factura rectifica la factura nº {escape(rectifica_a)}.</b>", ST["n"]), Spacer(1, 6)]
    if evento:
        det = f"<b>Evento:</b> {escape(evento.get('titulo') or '')}"
        if evento.get("fecha"):
            det += f"  ·  {fdate(evento['fecha'])}"
        if evento.get("hora_inicio"):
            det += f"  ·  {escape(evento['hora_inicio'])}" + (f"–{escape(evento['hora_fin'])}" if evento.get("hora_fin") else "")
        if evento.get("lugar"):
            det += f"<br/><b>Lugar:</b> {escape(evento['lugar'])}"
        s += [Paragraph(det, ST["n"]), Spacer(1, 8)]

    rows = [[Paragraph("Concepto", ST["th"]), Paragraph("Cant.", ST["th"]),
             Paragraph("Precio", ST["th"]), Paragraph("Importe", ST["th"])]]
    for l in lineas:
        q, pr = float(l.get("cantidad") or 0), float(l.get("precio") or 0)
        rows.append([p(l.get("concepto")), f"{q:g}", eur(pr), eur(q * pr)])
    t = Table(rows, colWidths=[104 * mm, 16 * mm, 27 * mm, 27 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (1, 1), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LINEBELOW", (0, -1), (-1, -1), 0.8, NAVY),
    ]))
    s += [t, Spacer(1, 8)]

    tt = totales(lineas, descuento, iva, retencion)
    filas = [["Base", eur(tt["base"])]]
    if float(descuento or 0) > 0:
        filas.append([f"Descuento {float(descuento):g}%", eur(-tt["desc"])])
    filas.append(["Base imponible", eur(tt["imponible"])])
    filas.append([f"IVA {float(iva or 0):g}%", eur(tt["cuota"])])
    if float(retencion or 0) > 0:
        filas.append([f"Retención IRPF {float(retencion):g}%", eur(-tt["ret"])])
    filas.append(["TOTAL", eur(tt["total"])])
    tot = Table(filas, colWidths=[45 * mm, 32 * mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("BACKGROUND", (0, -1), (-1, -1), LILAC), ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    s.append(tot)
    if pago:
        s += [Paragraph("Forma de pago", ST["h2"]), p(pago)]
    if notas:
        s += [Paragraph("Observaciones", ST["h2"]), p(notas, "small")]
    if condiciones:
        s += [Paragraph("Condiciones", ST["h2"]), p(condiciones, "small")]
    return _build(s, empresa, f"{tipo} {numero}")


def guion(empresa, evento, cliente, items):
    generales = [i for i in items if not str(i.get("hora") or "").strip()
                 and str(i.get("momento") or "").lower().startswith("indicaciones")]
    items = [i for i in items if i not in generales]
    s = _header(empresa, "Guion del evento", evento.get("titulo") or "")
    info = [f"<b>Fecha:</b> {fdate(evento.get('fecha'))}"]
    if evento.get("hora_inicio"):
        info.append(f"<b>Horario:</b> {escape(evento['hora_inicio'])}" + (f"–{escape(evento['hora_fin'])}" if evento.get("hora_fin") else ""))
    if evento.get("lugar"):
        info.append(f"<b>Lugar:</b> {escape(evento['lugar'])}")
    if cliente:
        info.append(f"<b>Cliente:</b> {escape(cliente.get('nombre') or '')}")
    if evento.get("servicios"):
        info.append(f"<b>Servicios:</b> {escape(', '.join(evento['servicios']))}")
    box = Table([[Paragraph("<br/>".join(info), ST["n"])]], colWidths=[174 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    s += [box, Spacer(1, 10)]
    if generales:
        txt = "<br/>".join(escape(str(g.get("detalle") or "")).replace("\n", "<br/>") for g in generales)
        gb = Table([[Paragraph("<b>Indicaciones generales</b><br/>" + txt, ST["n"])]], colWidths=[174 * mm])
        gb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, SKY), ("LINEBEFORE", (0, 0), (0, -1), 3, NAVY),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        s += [gb, Spacer(1, 10)]
    rows = [[Paragraph(h, ST["th"]) for h in ("Hora", "Momento", "Detalle", "Música / notas")]]
    for it in items:
        rows.append([Paragraph(f"<b>{escape(str(it.get('hora') or ''))}</b>", ST["b"]),
                     Paragraph(f"<b>{escape(str(it.get('momento') or ''))}</b>", ST["n"]),
                     p(it.get("detalle")), p(it.get("musica"))])
    t = Table(rows, colWidths=[24 * mm, 38 * mm, 58 * mm, 54 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LINEBELOW", (0, -1), (-1, -1), 0.8, NAVY),
    ]))
    s.append(t)
    return _build(s, empresa, f"Guion {evento.get('titulo') or ''}")
