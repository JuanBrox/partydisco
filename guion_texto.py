"""Convierte un texto libre con indicaciones en filas de guion (hora, momento, detalle, música)."""
import json
import re

import httpx

_H = r"(\d{1,2})(?:[:.](\d{2})\s*(?:h|hs|hrs|horas)?|\s*(?:h|hs|hrs|horas)\b)"
_LINEA = re.compile(
    r"^\s*(?:[-•*·▪●]\s*)?(?:a\s+las\s+|sobre\s+las\s+)?" + _H
    + r"(?:\s*(?:-|–|—|a|hasta)\s*(?:las\s+)?" + _H + r")?\s*[-–—:)\.]*\s*(.*)$", re.I)
_MUSICA_LINEA = re.compile(r"^\s*(?:[-•*·▪●]\s*)?(m[úu]sica|canci[óo]n(?:es)?|temas?|playlist|estilos?)\s*[:\-]\s*(.+)$", re.I)
_MUSICA_INLINE = re.compile(r"(?:^|[.;]\s+)(m[úu]sica|canci[óo]n(?:es)?|temas?|playlist|estilos?)\s*:\s*(.+)$", re.I)
GENERAL = "Indicaciones generales"


def _hora(h, m):
    h, m = int(h), int(m or 0)
    return f"{h:02d}:{m:02d}" if h <= 23 and m <= 59 else None


def _split_momento(rest):
    rest = rest.strip()
    m = re.match(r"^(.{3,45}?)\s*(?::|\s[-–—]\s|\.\s|;)\s*(.+)$", rest)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    if len(rest) <= 45:
        return rest, ""
    p = rest.split()
    return " ".join(p[:4]), " ".join(p[4:])


def hora_clave(h):
    """Orden cronológico de fiesta: las 00:00–07:59 van después de las 23:59."""
    m = re.search(r"(\d{1,2})[:.](\d{2})", str(h or ""))
    if not m:
        return (99, 0)
    hh = int(m.group(1))
    return (hh + 24 if hh < 8 else hh, int(m.group(2)))


def parse_texto(texto):
    items, generales, actual = [], [], None
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        m = _LINEA.match(linea)
        h1 = _hora(m.group(1), m.group(2)) if m else None
        if m and h1:
            h2 = _hora(m.group(3), m.group(4)) if m.group(3) else None
            momento, detalle = _split_momento(m.group(5))
            musica = ""
            mi = _MUSICA_INLINE.search(detalle)
            if mi:
                musica, detalle = mi.group(2).strip(), detalle[:mi.start()].strip()
            actual = {"hora": f"{h1}–{h2}" if h2 else h1, "momento": momento, "detalle": detalle, "musica": musica}
            items.append(actual)
            continue
        txt = linea.strip().lstrip("-•*·▪● ").strip()
        if actual is None:
            txt = re.sub(r"^indicaciones(?:\s+generales)?\s*:\s*", "", txt, flags=re.I)
            generales.append(txt)
            continue
        mm = _MUSICA_LINEA.match(linea)
        if mm:
            actual["musica"] = (actual["musica"] + "; " if actual["musica"] else "") + mm.group(2).strip()
        else:
            actual["detalle"] = (actual["detalle"] + "\n" if actual["detalle"] else "") + txt
    if generales:
        items.insert(0, {"hora": "", "momento": GENERAL, "detalle": "\n".join(generales), "musica": ""})
    return items


SISTEMA = (
    "Eres un asistente de una empresa de Discomóvil y sonorización de eventos. Recibes un texto libre con las "
    "indicaciones de un evento y lo conviertes en un guion ordenado. Responde SOLO con un array JSON, sin texto "
    "adicional ni bloques de código. Cada elemento: {\"hora\": \"HH:MM\" o \"\", \"momento\": título corto, "
    "\"detalle\": qué ocurre y qué debe hacer el DJ/técnico, \"musica\": canciones, estilos o peticiones}. "
    "Ordena cronológicamente (las horas de madrugada, como 00:30, van después de las de la noche anterior). "
    "No inventes datos que no estén en el texto. Si hay indicaciones generales sin hora (normas, listas de "
    "'no poner', contactos, datos de montaje), ponlas en un primer elemento con hora \"\" y momento "
    "\"Indicaciones generales\". Escribe en español."
)


def organizar_ia(texto, api_key, modelo="claude-sonnet-5-5"):
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=120,
                   headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                   json={"model": modelo, "max_tokens": 4000, "system": SISTEMA,
                         "messages": [{"role": "user", "content": texto}]})
    if r.status_code >= 300:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    out = "".join(b.get("text", "") for b in r.json().get("content", []))
    out = re.sub(r"^```(?:json)?|```$", "", out.strip(), flags=re.M).strip()
    data = json.loads(out)
    return [{k: str(d.get(k) or "") for k in ("hora", "momento", "detalle", "musica")} for d in data if isinstance(d, dict)]
