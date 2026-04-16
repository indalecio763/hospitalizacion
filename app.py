import streamlit as st
import anthropic
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import datetime
import io
import os

st.set_page_config(
    page_title="Ingreso Hospitalización",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
h1, h2, h3 { color: #1e3a5f; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    background-color: #e8f0fe;
    border-radius: 4px 4px 0 0;
    padding: 8px 16px;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background-color: #1e3a5f !important;
    color: white !important;
}
div[data-testid="stExpander"] { border: 1px solid #d0d9e8; border-radius: 6px; margin-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ──────────────────────────────────────────────────────────────────

EPS_LIST = [
    "SELECCIONAR",
    "NUEVA EPS", "SANITAS", "SURA EPS", "COMPENSAR", "COOSALUD",
    "SALUD TOTAL", "FAMISANAR", "MEDIMÁS", "CAJACOPI",
    "COMFENALCO ANTIOQUIA", "COMFENALCO VALLE", "SOS",
    "CAPITAL SALUD", "ALIANSALUD", "MUTUAL SER", "ASMET SALUD",
    "EMDISALUD", "EMSSANAR", "CONVIDA", "FERROCARRILES NACIONALES",
    "POLICÍA NACIONAL", "FUERZAS MILITARES", "MAGISTERIO",
    "PARTICULAR", "OTRO"
]

ANTECEDENTES_PAT = [
    "HIPERTENSIÓN ARTERIAL",
    "DIABETES MELLITUS TIPO 2",
    "DIABETES MELLITUS TIPO 2 INSULINO REQUIRENTE",
    "DIABETES MELLITUS TIPO 1",
    "DISLIPIDEMIA", "HIPOTIROIDISMO", "HIPERTIROIDISMO",
    "EPOC", "ASMA BRONQUIAL",
    "INSUFICIENCIA CARDÍACA CONGESTIVA",
    "CARDIOPATÍA ISQUÉMICA",
    "FIBRILACIÓN AURICULAR",
    "ENFERMEDAD RENAL CRÓNICA",
    "CIRROSIS HEPÁTICA",
    "ENFERMEDAD ARTERIAL PERIFÉRICA",
    "ACCIDENTE CEREBROVASCULAR PREVIO",
    "INFARTO AGUDO DE MIOCARDIO PREVIO",
    "ARTRITIS REUMATOIDE",
    "LUPUS ERITEMATOSO SISTÉMICO",
    "VIH/SIDA", "TUBERCULOSIS",
    "OBESIDAD", "SÍNDROME METABÓLICO",
    "EPILEPSIA", "ENFERMEDAD DE PARKINSON",
    "ENFERMEDAD DE ALZHEIMER", "DEMENCIA SENIL",
    "DEPRESIÓN", "TRASTORNO DE ANSIEDAD",
    "INSUFICIENCIA VENOSA CRÓNICA",
]

SISTEMAS_SINTOMAS = {
    "RESPIRATORIO": ["DISNEA", "TOS", "CIANOSIS", "EXPECTORACIÓN", "HEMOPTISIS", "DOLOR PLEURÍTICO"],
    "MUSCULAR": ["DOLOR MUSCULAR", "LIMITACIÓN A LA MOVILIDAD DE LAS ARTICULACIONES", "OTROS SÍNTOMAS MUSCULARES"],
    "CIRCULATORIO": ["PALPITACIONES", "DOLOR PRECORDIAL", "CRIO-DIAFORESIS", "EDEMAS PERIFÉRICOS"],
    "DIGESTIVO": ["DIARREA", "EPISODIOS EMÉTICOS", "DISFAGIA", "DOLOR ABDOMINAL", "NÁUSEAS"],
    "INMUNOLÓGICO": ["INMUNOSUPRESIÓN"],
    "ENDOCRINOLOGÍA": ["HIPOTIROIDISMO", "DIABETES", "HIPERPARATIROIDISMO"],
    "LINFÁTICO": ["ADENOPATÍAS"],
    "NERVIOSO": ["ALTERACIÓN DEL ESTADO DE LA CONCIENCIA", "ANISOCORIA", "DISARTRIA", "FOCALIZACIÓN NEUROLÓGICA", "DESORIENTACIÓN"],
    "ÓSEO": ["DOLOR ÓSEO", "LIMITACIÓN DE MOVILIDAD ARTICULAR"],
    "REPRODUCTOR": ["ALTERACIONES REPRODUCTORAS"],
    "URINARIO": ["DISURIA", "HEMATURIA", "POLIURIA"],
    "HORMONAL": ["ALTERACIONES HORMONALES"],
    "TEGUMENTARIO": ["LESIONES EN PIEL", "ERITEMA", "PRURITO", "ÚLCERAS CUTÁNEAS"],
}

EXAMEN_OPCIONES = {
    "CABEZA Y CUELLO": {
        "Conjuntivas": ["CONJUNTIVAS TARSALES NORMOCRÓMICAS", "CONJUNTIVAS TARSALES PÁLIDAS", "CONJUNTIVAS ICTÉRICAS"],
        "Mucosa oral": ["MUCOSA ORAL HÚMEDA", "MUCOSA ORAL SECA"],
        "Orofaringe": ["OROFARINGE NORMAL", "OROFARINGE ERITEMATOSA", "OROFARINGE CON EXUDADOS"],
        "Cuello": ["CUELLO SIN ADENOMEGALIAS", "CUELLO CON ADENOMEGALIAS"],
        "Movilidad cervical": ["SIN DOLOR A MOVILIDAD", "CON DOLOR A MOVILIDAD"],
        "Ingurgitación yugular": ["NO INGURGITACIÓN YUGULAR", "CON INGURGITACIÓN YUGULAR"],
    },
    "TÓRAX": {
        "Tirajes": ["NO TIRAJES NI RETRACCIONES", "CON TIRAJES Y RETRACCIONES"],
        "Murmullo vesicular": [
            "MURMULLO VESICULAR CONSERVADO",
            "MURMULLO VESICULAR DISMINUIDO BILATERAL",
            "MURMULLO VESICULAR DISMINUIDO EN BASE DERECHA",
            "MURMULLO VESICULAR DISMINUIDO EN BASE IZQUIERDA",
            "MURMULLO VESICULAR ABOLIDO",
        ],
        "Ruidos agregados": ["SIN RUIDOS AGREGADOS", "SIBILANCIAS ESPIRATORIAS", "CRÉPITOS EN BASES", "RONCUS DIFUSOS"],
        "Ruidos cardíacos": [
            "RUIDOS CARDÍACOS RÍTMICOS SIN SOPLOS",
            "RUIDOS CARDÍACOS ARRÍTMICOS",
            "RUIDOS CARDÍACOS CON SOPLO SISTÓLICO",
            "RUIDOS CARDÍACOS CON SOPLO DIASTÓLICO",
        ],
    },
    "ABDOMEN": {
        "Forma": ["PLANO", "GLOBOSO POR PANÍCULO ADIPOSO", "GLOBOSO", "EXCAVADO"],
        "Consistencia": ["BLANDO, DEPRESIBLE", "TENSO, DOLOROSO A LA PALPACIÓN"],
        "Ruidos intestinales": [
            "RUIDOS INTESTINALES PRESENTES NORMALES EN FRECUENCIA E INTENSIDAD",
            "RUIDOS INTESTINALES DISMINUIDOS",
            "RUIDOS INTESTINALES AUSENTES",
            "RUIDOS INTESTINALES AUMENTADOS EN FRECUENCIA",
        ],
        "Masas": [
            "NO SE PALPAN MASAS NI MEGALIAS",
            "HEPATOMEGALIA PALPABLE",
            "ESPLENOMEGALIA PALPABLE",
            "MASA PALPABLE EN FOSA ILÍACA",
        ],
        "Irritación peritoneal": ["NO SIGNOS DE IRRITACIÓN PERITONEAL", "CON SIGNOS DE IRRITACIÓN PERITONEAL"],
        "Genitourinario": ["GENITOURINARIO: NORMOCONFIGURADO", "GENITOURINARIO: CON ALTERACIONES"],
    },
    "EXTREMIDADES": {
        "Simetría": ["SIMÉTRICAS", "ASIMÉTRICAS"],
        "Edemas": [
            "SIN EDEMAS",
            "EDEMAS EN MMII (+)",
            "EDEMAS EN MMII (++)",
            "EDEMAS EN MMII (+++)",
            "EDEMAS GENERALIZADOS",
        ],
        "Pulsos periféricos": [
            "PULSOS PERIFÉRICOS PRESENTES Y SIMÉTRICOS",
            "PULSOS PERIFÉRICOS LEVEMENTE DISMINUIDOS",
            "PULSOS PERIFÉRICOS AUSENTES EN MMII",
        ],
        "Llenado capilar": ["LLENADO CAPILAR NORMAL (<2 SEG)", "LLENADO CAPILAR PROLONGADO (>2 SEG)"],
        "Lesiones cutáneas": [
            "SIN LESIONES CUTÁNEAS",
            "ÚLCERA NECRÓTICA EN TALÓN IZQUIERDO",
            "ÚLCERA NECRÓTICA EN TALÓN DERECHO",
            "HERIDA QUIRÚRGICA EN CICATRIZACIÓN",
            "ERITEMA LOCALIZADO",
        ],
    },
    "NEUROLÓGICO": {
        "Estado consciencia": ["ALERTA", "SOMNOLIENTO", "ESTUPOROSO", "EN COMA"],
        "Orientación": [
            "ORIENTADO EN TIEMPO Y ESPACIO",
            "DESORIENTADO EN TIEMPO",
            "DESORIENTADO EN TIEMPO Y ESPACIO",
            "DESORIENTADO GLOBALMENTE",
        ],
        "Simetría facial": ["SIMETRÍA FACIAL CONSERVADA", "ASIMETRÍA FACIAL"],
        "Pupilas": [
            "PUPILAS ISOCÓRICAS NORMORREACTIVAS",
            "PUPILAS ANISOCÓRICAS",
            "PUPILAS MIDRIÁTICAS ARREACTIVAS",
            "PUPILAS MIÓTICAS",
        ],
        "Movimientos oculares": ["MOVIMIENTOS OCULARES SIN ALTERACIONES", "MOVIMIENTOS OCULARES CON ALTERACIONES"],
        "Déficit neurológico": [
            "NO DÉFICIT MOTOR O SENSITIVO APARENTE",
            "CON DÉFICIT MOTOR",
            "CON DÉFICIT SENSITIVO",
            "CON DÉFICIT MOTOR Y SENSITIVO",
        ],
        "Rigidez": ["NO RIGIDEZ DE NUCA, NI SIGNOS MENÍNGEOS", "CON RIGIDEZ DE NUCA", "CON SIGNOS MENÍNGEOS POSITIVOS"],
    },
}

DIETAS = ["DIETA NORMAL", "DIETA BLANDA", "DIETA LÍQUIDA", "DIETA HIPOCALÓRICA", "DIETA HIPOSÓDICA", "DIETA DIABÉTICA", "AYUNO"]
ACCESOS = ["TAPÓN VENOSO", "ACCESO VENOSO PERIFÉRICO PERMEABLE", "CATÉTER VENOSO CENTRAL"]
ORDENES_COMUNES = [
    "GLUCOMETRÍA PRECOMIDAS Y A LAS 21:00 HR",
    "CONTROL DE SIGNOS VITALES Y AVISAR CAMBIOS",
    "CUIDADOS POR ENFERMERÍA",
    "BALANCE HÍDRICO ESTRICTO",
    "OXÍGENO SUPLEMENTARIO 2 LT/MIN POR CÁNULA NASAL",
    "MOVILIZACIÓN PROGRESIVA",
    "PROFILAXIS ANTITROMBÓTICA",
    "CURACIONES CADA 24 HORAS",
    "AISLAMIENTO DE CONTACTO",
]
VIA_ADMIN = ["VO", "IV", "SC", "IM", "SUBLINGUAL", "TÓPICO", "INHALADO", "RECTAL"]
FRECUENCIAS = [
    "CADA 4 HORAS", "CADA 6 HORAS", "CADA 8 HORAS",
    "CADA 12 HORAS", "CADA 24 HORAS", "CADA 72 HORAS",
    "UNA VEZ AL DÍA (AM)", "EN LA NOCHE", "PRN",
]

# ── SESSION STATE ──────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "nombre": "",
        "id_paciente": "",
        "sexo": "FEMENINO",
        "edad": 18,
        "eps": "SELECCIONAR",
        "fecha_ingreso": datetime.date.today(),
        "motivo_consulta": "",
        "enfermedad_actual": "",
        "rev_sistemas": {
            s: {sint: "NIEGA" for sint in sints}
            for s, sints in SISTEMAS_SINTOMAS.items()
        },
        "rev_adicional": {s: "" for s in SISTEMAS_SINTOMAS},
        "rev_texto_generado": "",
        "ant_patologicos": [],
        "ant_patologicos_otro": "",
        "ant_farmacologicos_texto": "",
        "ant_quirurgicos": "",
        "ant_alergicos": "",
        "ant_toxicos": "",
        "ant_familiares": "",
        "ta_sist": "",
        "ta_diast": "",
        "fc": "",
        "fr": "",
        "temp": "",
        "spo2": "",
        "glucometria_sv": "",
        "examen": {
            region: {campo: opts[0] for campo, opts in campos.items()}
            for region, campos in EXAMEN_OPCIONES.items()
        },
        "examen_adicional": {r: "" for r in EXAMEN_OPCIONES},
        "examen_ext_especial": "",
        "diagnosticos": [""],
        "analisis": "",
        "plan_dieta": "DIETA NORMAL",
        "plan_acceso": "TAPÓN VENOSO",
        "plan_medicamentos": [{"med": "", "dosis": "", "via": "VO", "freq": "CADA 24 HORAS"}],
        "plan_ordenes": [],
        "plan_solicitudes": "",
        "plan_otro": "",
        "api_key": st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── HELPERS ────────────────────────────────────────────────────────────────────

def calcular_map(sist, diast):
    try:
        return round((int(sist) + 2 * int(diast)) / 3)
    except Exception:
        return ""


def generar_texto_revision():
    lineas = []
    for sistema, sintomas in SISTEMAS_SINTOMAS.items():
        partes = []
        for sintoma in sintomas:
            estado = st.session_state["rev_sistemas"][sistema][sintoma]
            partes.append(f"{'NIEGA' if estado == 'NIEGA' else 'PRESENTA'} {sintoma}")
        adicional = st.session_state["rev_adicional"].get(sistema, "").strip()
        texto = ", ".join(partes)
        if adicional:
            texto += f", {adicional.upper()}"
        lineas.append(f"{sistema}: {texto}")
    return "\n".join(lineas)


def generar_texto_examen():
    bloques = []
    for region, campos in EXAMEN_OPCIONES.items():
        partes = [st.session_state["examen"][region][campo] for campo in campos]
        if region == "EXTREMIDADES":
            especial = st.session_state.get("examen_ext_especial", "").strip()
            if especial:
                partes.append(especial.upper())
        adicional = st.session_state["examen_adicional"].get(region, "").strip()
        if adicional:
            partes.append(adicional.upper())
        bloques.append(f"{region}: {', '.join(partes)}")
    return "\n".join(bloques)


def get_api_key():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return st.session_state.get("api_key", "")


def ia_generar(prompt_texto):
    api_key = get_api_key()
    if not api_key:
        return "CONFIGURA TU API KEY DE ANTHROPIC EN LA BARRA LATERAL."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt_texto}],
        )
        return response.content[0].text.upper()
    except Exception as e:
        return f"ERROR DE API: {str(e)}"


def prompt_enfermedad_actual():
    genero = "FEMENINA" if st.session_state["sexo"] == "FEMENINO" else "MASCULINO"
    edad = st.session_state["edad"]
    ant_pat = list(st.session_state["ant_patologicos"])
    if st.session_state["ant_patologicos_otro"].strip():
        ant_pat.append(st.session_state["ant_patologicos_otro"].strip().upper())
    ant_qx = st.session_state["ant_quirurgicos"].strip()
    motivo = st.session_state["motivo_consulta"].strip()
    return f"""Eres un médico colombiano redactando una historia clínica de ingreso hospitalario.
Redacta la sección ENFERMEDAD ACTUAL para:
- Paciente: {genero}, {edad} años
- Antecedentes patológicos: {', '.join(ant_pat) if ant_pat else 'NO REFIERE'}
- Antecedentes quirúrgicos: {ant_qx if ant_qx else 'NO REFIERE'}
- Motivo de consulta: {motivo}

Instrucciones:
- En mayúsculas, estilo clínico formal colombiano
- Comienza: "PACIENTE {genero} DE {edad} AÑOS DE EDAD CON ANTECEDENTES DE..."
- Describe la cronología de la enfermedad basándote en el motivo de consulta
- No inventes datos específicos (fechas, valores, lugares) que no estén en la información
- Máximo 180 palabras, un párrafo fluido"""


def prompt_analisis():
    genero = "FEMENINA" if st.session_state["sexo"] == "FEMENINO" else "MASCULINO"
    edad = st.session_state["edad"]
    ant_pat = list(st.session_state["ant_patologicos"])
    if st.session_state["ant_patologicos_otro"].strip():
        ant_pat.append(st.session_state["ant_patologicos_otro"].strip().upper())
    diags = [d.strip() for d in st.session_state["diagnosticos"] if d.strip()]
    ta_sist = st.session_state["ta_sist"]
    ta_diast = st.session_state["ta_diast"]
    sv = f"TA {ta_sist}/{ta_diast} mmHg, FC {st.session_state['fc']} lpm, FR {st.session_state['fr']} rpm, Temp {st.session_state['temp']}°C, SpO2 {st.session_state['spo2']}%"
    enf = st.session_state["enfermedad_actual"][:600]
    return f"""Eres un médico colombiano redactando el análisis clínico de un ingreso hospitalario.

Datos:
- Paciente {genero}, {edad} años
- Antecedentes: {', '.join(ant_pat) if ant_pat else 'NO REFIERE'}
- Enfermedad actual (resumen): {enf}
- Signos vitales: {sv}
- Diagnósticos: {'; '.join(diags) if diags else 'NO DEFINIDOS'}

Instrucciones:
- En mayúsculas, estilo clínico formal colombiano
- 2-3 párrafos cortos: (1) integrar situación clínica, (2) hallazgos relevantes al examen, (3) conducta y justificación
- Conciso, sin repetir datos ya conocidos
- Máximo 200 palabras"""


# ── PDF ────────────────────────────────────────────────────────────────────────

def generar_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "T", parent=styles["Normal"],
        fontSize=14, spaceAfter=4, spaceBefore=4,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e3a5f"),
    )
    section_style = ParagraphStyle(
        "S", parent=styles["Normal"],
        fontSize=10, spaceAfter=2, spaceBefore=8,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e3a5f"),
    )
    body_style = ParagraphStyle(
        "B", parent=styles["Normal"],
        fontSize=9, spaceAfter=3, spaceBefore=1,
        fontName="Helvetica", leading=13, alignment=TA_JUSTIFY,
    )
    label_style = ParagraphStyle(
        "L", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
    )

    story = []

    story.append(Paragraph("INGRESO A HOSPITALIZACIÓN — SALA GENERAL", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f"), spaceAfter=8))

    # Patient table
    fecha_str = st.session_state["fecha_ingreso"].strftime("%d/%m/%Y")
    pt_data = [
        [Paragraph("<b>NOMBRE:</b>", label_style), Paragraph(st.session_state["nombre"].upper(), body_style),
         Paragraph("<b>IDENTIFICACIÓN:</b>", label_style), Paragraph(st.session_state["id_paciente"].upper(), body_style)],
        [Paragraph("<b>SEXO:</b>", label_style), Paragraph(st.session_state["sexo"], body_style),
         Paragraph("<b>EDAD:</b>", label_style), Paragraph(f"{st.session_state['edad']} AÑOS", body_style)],
        [Paragraph("<b>EPS:</b>", label_style), Paragraph(st.session_state["eps"], body_style),
         Paragraph("<b>FECHA INGRESO:</b>", label_style), Paragraph(fecha_str, body_style)],
    ]
    pt = Table(pt_data, colWidths=[1.3 * inch, 2.7 * inch, 1.3 * inch, 2.7 * inch])
    pt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8f0fe")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e8f0fe")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pt)
    story.append(Spacer(1, 8))

    def add_section(titulo, contenido):
        story.append(Paragraph(titulo, section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#2c5f8a"), spaceAfter=4))
        if contenido and contenido.strip():
            cleaned = contenido.strip().replace("\n", "<br/>")
            story.append(Paragraph(cleaned, body_style))
        story.append(Spacer(1, 4))

    add_section("MOTIVO DE CONSULTA", st.session_state["motivo_consulta"].upper())
    add_section("ENFERMEDAD ACTUAL", st.session_state["enfermedad_actual"])

    rev = st.session_state["rev_texto_generado"] or generar_texto_revision()
    add_section("REVISIÓN POR SISTEMAS", rev)

    # Antecedentes
    ant_pat = list(st.session_state["ant_patologicos"])
    if st.session_state["ant_patologicos_otro"].strip():
        ant_pat.append(st.session_state["ant_patologicos_otro"].strip().upper())
    ant_bloque = ""
    if ant_pat:
        ant_bloque += f"- PATOLÓGICOS: {', '.join(ant_pat)}\n"
    if st.session_state["ant_farmacologicos_texto"].strip():
        ant_bloque += f"- FARMACOLÓGICOS: {st.session_state['ant_farmacologicos_texto'].upper()}\n"
    if st.session_state["ant_quirurgicos"].strip():
        ant_bloque += f"- QUIRÚRGICOS: {st.session_state['ant_quirurgicos'].upper()}\n"
    if st.session_state["ant_alergicos"].strip():
        ant_bloque += f"- ALÉRGICOS: {st.session_state['ant_alergicos'].upper()}\n"
    if st.session_state["ant_toxicos"].strip():
        ant_bloque += f"- TÓXICOS: {st.session_state['ant_toxicos'].upper()}\n"
    if st.session_state["ant_familiares"].strip():
        ant_bloque += f"- FAMILIARES: {st.session_state['ant_familiares'].upper()}"
    add_section("ANTECEDENTES PERSONALES", ant_bloque)

    # Signos vitales
    sist = st.session_state["ta_sist"]
    diast = st.session_state["ta_diast"]
    map_v = calcular_map(sist, diast)
    map_str = f" ({map_v})" if map_v != "" else ""
    sv_bloque = (
        f"TENSIÓN ARTERIAL: {sist}/{diast}{map_str} MMHG\n"
        f"FRECUENCIA CARDIACA: {st.session_state['fc']} LATIDOS POR MINUTO\n"
        f"FRECUENCIA RESPIRATORIA: {st.session_state['fr']} RESPIRACIONES POR MINUTO\n"
        f"TEMPERATURA: {st.session_state['temp']} °C\n"
        f"SATURACIÓN DE OXÍGENO: {st.session_state['spo2']} % MEDIO AMBIENTE\n"
        f"GLUCOMETRÍA: {st.session_state['glucometria_sv']} MG/DL"
    )
    add_section("EXAMEN FÍSICO — SIGNOS VITALES", sv_bloque)
    add_section("EXAMEN FÍSICO", generar_texto_examen())

    diag_bloque = "\n".join(f"• {d.upper()}" for d in st.session_state["diagnosticos"] if d.strip())
    add_section("DIAGNÓSTICOS", diag_bloque)
    add_section("ANÁLISIS", st.session_state["analisis"])

    # Plan
    plan_bloque = f"ESTANCIA SALA GENERAL\n{st.session_state['plan_dieta']}\n{st.session_state['plan_acceso']}\n"
    meds = [m for m in st.session_state["plan_medicamentos"] if m["med"].strip()]
    if meds:
        plan_bloque += "\nMEDICAMENTOS:\n"
        for m in meds:
            plan_bloque += f"• {m['med'].upper()} {m['dosis'].upper()} {m['via']} {m['freq']}\n"
    if st.session_state["plan_ordenes"]:
        plan_bloque += "\nÓRDENES:\n"
        for o in st.session_state["plan_ordenes"]:
            plan_bloque += f"• {o}\n"
    if st.session_state["plan_solicitudes"].strip():
        plan_bloque += f"\nSE SOLICITA:\n{st.session_state['plan_solicitudes'].upper()}\n"
    if st.session_state["plan_otro"].strip():
        plan_bloque += f"\n{st.session_state['plan_otro'].upper()}"
    add_section("PLAN", plan_bloque)

    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="35%", thickness=0.5, color=colors.black, hAlign="LEFT"))
    story.append(Paragraph("MÉDICO TRATANTE", body_style))
    story.append(Paragraph(f"FECHA: {datetime.date.today().strftime('%d/%m/%Y')}", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ── UI ─────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Configuración")
    if get_api_key():
        st.success("IA lista para usar")
    else:
        api_input = st.text_input(
            "API Key Anthropic",
            value=st.session_state["api_key"],
            type="password",
            help="Requerida para generar texto con IA",
        )
        if api_input != st.session_state["api_key"]:
            st.session_state["api_key"] = api_input
        st.warning("Ingresa tu API Key para usar IA")
    st.divider()
    st.caption("Ingreso Hospitalización v1.0")

st.markdown("""
<div style="background:#1e3a5f;color:white;padding:16px 24px;border-radius:8px;margin-bottom:14px;">
    <h2 style="margin:0;color:white;font-size:20px;">INGRESO A HOSPITALIZACIÓN — SALA GENERAL</h2>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs([
    "👤 Paciente",
    "📋 Consulta & Antecedentes",
    "🔍 Rev. Sistemas",
    "🩺 Examen Físico",
    "🎯 Diagnósticos",
    "📊 Análisis",
    "💊 Plan",
    "📄 PDF",
])

# ── TAB 1: PACIENTE ────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Datos del Paciente")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state["nombre"] = st.text_input("Nombre completo", value=st.session_state["nombre"])
        st.session_state["sexo"] = st.selectbox(
            "Sexo", ["FEMENINO", "MASCULINO"],
            index=0 if st.session_state["sexo"] == "FEMENINO" else 1,
        )
        eps_idx = EPS_LIST.index(st.session_state["eps"]) if st.session_state["eps"] in EPS_LIST else 0
        st.session_state["eps"] = st.selectbox("EPS", EPS_LIST, index=eps_idx)
    with c2:
        st.session_state["id_paciente"] = st.text_input("Número de identificación", value=st.session_state["id_paciente"])
        st.session_state["edad"] = st.number_input("Edad (años)", min_value=0, max_value=120, value=st.session_state["edad"])
        st.session_state["fecha_ingreso"] = st.date_input("Fecha de ingreso", value=st.session_state["fecha_ingreso"])

    if st.session_state["nombre"]:
        st.success(
            f"Paciente: **{st.session_state['nombre'].upper()}** | "
            f"{st.session_state['sexo']} | {st.session_state['edad']} años | {st.session_state['eps']}"
        )

# ── TAB 2: CONSULTA + ANTECEDENTES + ENFERMEDAD ACTUAL ────────────────────────
with tabs[1]:
    # ── MOTIVO DE CONSULTA ──
    st.subheader("Motivo de Consulta")
    st.session_state["motivo_consulta"] = st.text_area(
        "Describe el motivo de consulta",
        value=st.session_state["motivo_consulta"],
        height=80,
        placeholder="Ej: ÚLCERA EN PIE IZQUIERDO CON MAL OLOR, DOLOR Y PICOS FEBRILES",
    )

    st.divider()

    # ── ANTECEDENTES ──
    st.subheader("Antecedentes Personales")

    st.markdown("**Antecedentes Patológicos**")
    st.session_state["ant_patologicos"] = st.multiselect(
        "Selecciona de la lista",
        options=ANTECEDENTES_PAT,
        default=[x for x in st.session_state["ant_patologicos"] if x in ANTECEDENTES_PAT],
    )
    st.session_state["ant_patologicos_otro"] = st.text_input(
        "Otros (escribir)",
        value=st.session_state["ant_patologicos_otro"],
        placeholder="Ej: INSUFICIENCIA VENOSA CRÓNICA, ESCLEROSIS MÚLTIPLE",
    )

    st.markdown("**Antecedentes Farmacológicos**")
    st.session_state["ant_farmacologicos_texto"] = st.text_area(
        "Medicamentos actuales",
        value=st.session_state["ant_farmacologicos_texto"],
        height=75,
        placeholder="Ej: LOSARTAN 50MG, METOPROLOL 50MG, INSULINA GLARGINA 10 UI",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Antecedentes Quirúrgicos**")
        st.session_state["ant_quirurgicos"] = st.text_area(
            "Cirugías previas",
            value=st.session_state["ant_quirurgicos"],
            height=70,
            placeholder="Ej: AMPUTACIÓN SUPRACONDÍLEA DERECHA 14/12/25",
        )
        st.markdown("**Antecedentes Alérgicos**")
        st.session_state["ant_alergicos"] = st.text_input(
            "Alergias",
            value=st.session_state["ant_alergicos"],
            placeholder="Ej: PIPERACILINA TAZOBACTAM, PENICILINA",
        )
    with c2:
        st.markdown("**Antecedentes Tóxicos**")
        st.session_state["ant_toxicos"] = st.text_input(
            "Hábitos tóxicos",
            value=st.session_state["ant_toxicos"],
            placeholder="Ej: EX TABAQUISTA 20 PAQUETES/AÑO",
        )
        st.markdown("**Antecedentes Familiares**")
        st.session_state["ant_familiares"] = st.text_input(
            "Familiares relevantes",
            value=st.session_state["ant_familiares"],
            placeholder="Ej: MADRE CON DM TIPO 2, PADRE CON HTA",
        )

    st.divider()

    # ── ENFERMEDAD ACTUAL ──
    st.subheader("Enfermedad Actual")
    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("Generar con IA", use_container_width=True, key="btn_enf"):
            if not st.session_state["motivo_consulta"].strip():
                st.warning("Primero escribe el motivo de consulta.")
            else:
                with st.spinner("Generando..."):
                    resultado = ia_generar(prompt_enfermedad_actual())
                    st.session_state["enfermedad_actual"] = resultado
                    st.session_state["ta_enf"] = resultado
        st.caption("Usa los datos del paciente, antecedentes y motivo de consulta.")

    st.session_state["enfermedad_actual"] = st.text_area(
        "Enfermedad actual (editable)",
        value=st.session_state["enfermedad_actual"],
        height=220,
        placeholder="Escribe o genera con IA...",
        key="ta_enf",
    )

# ── TAB 3: REVISIÓN POR SISTEMAS ──────────────────────────────────────────────
with tabs[2]:
    st.subheader("Revisión por Sistemas")
    st.caption("Selecciona NIEGA o PRESENTA por síntoma. Luego genera el texto.")

    sistemas_list = list(SISTEMAS_SINTOMAS.items())
    half = (len(sistemas_list) + 1) // 2
    col_l, col_r = st.columns(2)

    for idx, (sistema, sintomas) in enumerate(sistemas_list):
        col = col_l if idx < half else col_r
        with col:
            with st.expander(f"**{sistema}**", expanded=False):
                for sintoma in sintomas:
                    val = st.radio(
                        sintoma,
                        ["NIEGA", "PRESENTA"],
                        index=0 if st.session_state["rev_sistemas"][sistema][sintoma] == "NIEGA" else 1,
                        key=f"rev_{sistema}_{sintoma}",
                        horizontal=True,
                    )
                    st.session_state["rev_sistemas"][sistema][sintoma] = val
                st.session_state["rev_adicional"][sistema] = st.text_input(
                    "Observación adicional",
                    value=st.session_state["rev_adicional"][sistema],
                    key=f"rev_adic_{sistema}",
                    placeholder="Opcional...",
                )

    st.divider()
    if st.button("Generar texto de revisión por sistemas", type="secondary"):
        st.session_state["rev_texto_generado"] = generar_texto_revision()

    if st.session_state["rev_texto_generado"]:
        st.session_state["rev_texto_generado"] = st.text_area(
            "Texto generado (editable)",
            value=st.session_state["rev_texto_generado"],
            height=300,
            key="rev_edit",
        )

# ── TAB 4: EXAMEN FÍSICO ───────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Examen Físico")
    st.markdown("##### Signos Vitales")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.session_state["ta_sist"] = st.text_input("TA Sistólica (mmHg)", value=st.session_state["ta_sist"])
        st.session_state["ta_diast"] = st.text_input("TA Diastólica (mmHg)", value=st.session_state["ta_diast"])
    with c2:
        st.session_state["fc"] = st.text_input("FC (lpm)", value=st.session_state["fc"])
        st.session_state["fr"] = st.text_input("FR (rpm)", value=st.session_state["fr"])
    with c3:
        st.session_state["temp"] = st.text_input("Temperatura (°C)", value=st.session_state["temp"])
        st.session_state["spo2"] = st.text_input("SpO2 (%)", value=st.session_state["spo2"])
    with c4:
        st.session_state["glucometria_sv"] = st.text_input("Glucometría (mg/dL)", value=st.session_state["glucometria_sv"])
        map_v = calcular_map(st.session_state["ta_sist"], st.session_state["ta_diast"])
        if map_v != "":
            st.metric("MAP calculada", f"{map_v} mmHg")

    st.divider()
    st.markdown("##### Examen por Regiones")

    for region, campos in EXAMEN_OPCIONES.items():
        with st.expander(f"**{region}**", expanded=False):
            ncols = min(3, len(campos))
            cols = st.columns(ncols)
            for i, (campo, opciones) in enumerate(campos.items()):
                curr = st.session_state["examen"][region][campo]
                idx = opciones.index(curr) if curr in opciones else 0
                with cols[i % ncols]:
                    val = st.selectbox(campo, options=opciones, index=idx, key=f"exam_{region}_{campo}")
                    st.session_state["examen"][region][campo] = val

            if region == "EXTREMIDADES":
                st.session_state["examen_ext_especial"] = st.text_input(
                    "Hallazgos especiales (amputaciones, etc.)",
                    value=st.session_state["examen_ext_especial"],
                    key="exam_ext_esp",
                    placeholder="Ej: AMPUTACIÓN SUPRACONDÍLEA DERECHA, SENSIBILIDAD Y FUERZA CONSERVADA",
                )

            st.session_state["examen_adicional"][region] = st.text_input(
                "Hallazgos adicionales",
                value=st.session_state["examen_adicional"][region],
                key=f"exam_adic_{region}",
                placeholder="Opcional...",
            )

# ── TAB 5: DIAGNÓSTICOS ────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Diagnósticos")
    st.caption("Agrega todos los diagnósticos del paciente.")

    diags = st.session_state["diagnosticos"]
    to_delete = None

    for i in range(len(diags)):
        c1, c2 = st.columns([11, 1])
        with c1:
            diags[i] = st.text_input(
                f"Diagnóstico {i + 1}",
                value=diags[i],
                key=f"diag_{i}",
                placeholder="Ej: PIE DIABÉTICO GRADO IV SEGÚN WAGNER",
            )
        with c2:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            if len(diags) > 1 and st.button("✕", key=f"del_diag_{i}"):
                to_delete = i

    if to_delete is not None:
        diags.pop(to_delete)
        st.rerun()

    if st.button("+ Agregar diagnóstico"):
        diags.append("")
        st.rerun()

    st.session_state["diagnosticos"] = diags

# ── TAB 6: ANÁLISIS ────────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Análisis Clínico")

    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("Generar con IA", use_container_width=True, key="btn_analisis"):
            with st.spinner("Generando análisis..."):
                resultado = ia_generar(prompt_analisis())
                st.session_state["analisis"] = resultado
                st.session_state["ta_analisis"] = resultado
        st.caption("Integra todos los datos clínicos registrados.")

    st.session_state["analisis"] = st.text_area(
        "Análisis (editable)",
        value=st.session_state["analisis"],
        height=300,
        placeholder="Escribe o genera con IA...",
        key="ta_analisis",
    )

# ── TAB 7: PLAN ────────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("Plan de Manejo")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Estancia, Dieta y Acceso**")
        st.info("ESTANCIA SALA GENERAL")
        dieta_idx = DIETAS.index(st.session_state["plan_dieta"]) if st.session_state["plan_dieta"] in DIETAS else 0
        st.session_state["plan_dieta"] = st.selectbox("Dieta", DIETAS, index=dieta_idx)
        acc_idx = ACCESOS.index(st.session_state["plan_acceso"]) if st.session_state["plan_acceso"] in ACCESOS else 0
        st.session_state["plan_acceso"] = st.selectbox("Acceso vascular", ACCESOS, index=acc_idx)
    with c2:
        st.markdown("**Órdenes de enfermería**")
        st.session_state["plan_ordenes"] = st.multiselect(
            "Selecciona las órdenes",
            options=ORDENES_COMUNES,
            default=[o for o in st.session_state["plan_ordenes"] if o in ORDENES_COMUNES],
        )

    st.divider()
    st.markdown("**Medicamentos**")

    meds = st.session_state["plan_medicamentos"]
    to_del_med = None

    for i in range(len(meds)):
        c1, c2, c3, c4, c5 = st.columns([4, 2, 1.5, 2.5, 0.7])
        with c1:
            meds[i]["med"] = st.text_input("Medicamento", value=meds[i]["med"], key=f"med_n_{i}", placeholder="Ej: ACETAMINOFEN")
        with c2:
            meds[i]["dosis"] = st.text_input("Dosis", value=meds[i]["dosis"], key=f"med_d_{i}", placeholder="Ej: 1 GR")
        with c3:
            via_idx = VIA_ADMIN.index(meds[i]["via"]) if meds[i]["via"] in VIA_ADMIN else 0
            meds[i]["via"] = st.selectbox("Vía", VIA_ADMIN, index=via_idx, key=f"med_v_{i}")
        with c4:
            freq_idx = FRECUENCIAS.index(meds[i]["freq"]) if meds[i]["freq"] in FRECUENCIAS else 0
            meds[i]["freq"] = st.selectbox("Frecuencia", FRECUENCIAS, index=freq_idx, key=f"med_f_{i}")
        with c5:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            if len(meds) > 1 and st.button("✕", key=f"del_med_{i}"):
                to_del_med = i

    if to_del_med is not None:
        meds.pop(to_del_med)
        st.rerun()

    if st.button("+ Agregar medicamento"):
        meds.append({"med": "", "dosis": "", "via": "VO", "freq": "CADA 24 HORAS"})
        st.rerun()

    st.session_state["plan_medicamentos"] = meds

    st.divider()
    st.markdown("**Se solicita / Paraclínicos**")
    st.session_state["plan_solicitudes"] = st.text_area(
        "Exámenes y valoraciones",
        value=st.session_state["plan_solicitudes"],
        height=100,
        placeholder="Ej: HEMOGRAMA, BUN, CREATININA, IONOGRAMA\nDOPPLER ARTERIAL MMII\nVALORACIÓN POR MEDICINA INTERNA",
    )

    st.markdown("**Indicaciones adicionales**")
    st.session_state["plan_otro"] = st.text_area(
        "Otras indicaciones",
        value=st.session_state["plan_otro"],
        height=75,
        placeholder="Cualquier otra indicación del plan...",
    )

# ── TAB 8: PDF ─────────────────────────────────────────────────────────────────
with tabs[7]:
    st.subheader("Generar Documento PDF")

    checks = {
        "Nombre del paciente": bool(st.session_state["nombre"].strip()),
        "ID del paciente": bool(st.session_state["id_paciente"].strip()),
        "EPS seleccionada": st.session_state["eps"] != "SELECCIONAR",
        "Motivo de consulta": bool(st.session_state["motivo_consulta"].strip()),
        "Enfermedad actual": bool(st.session_state["enfermedad_actual"].strip()),
        "Al menos un diagnóstico": any(d.strip() for d in st.session_state["diagnosticos"]),
        "Análisis clínico": bool(st.session_state["analisis"].strip()),
    }

    st.markdown("**Estado del documento:**")
    c1, c2 = st.columns(2)
    items = list(checks.items())
    half = (len(items) + 1) // 2
    for i, (campo, ok) in enumerate(items):
        with (c1 if i < half else c2):
            st.write(f"{'✅' if ok else '⚠️'} {campo}")

    all_ok = all(checks.values())
    if not all_ok:
        st.warning("Algunos campos importantes están incompletos. El PDF se generará igualmente.")

    st.divider()

    if st.button("Generar PDF", type="primary"):
        if not st.session_state["rev_texto_generado"]:
            st.session_state["rev_texto_generado"] = generar_texto_revision()
        with st.spinner("Generando PDF..."):
            pdf_buf = generar_pdf()
            nombre_archivo = (
                f"ingreso_{st.session_state['id_paciente'] or 'paciente'}"
                f"_{datetime.date.today().strftime('%Y%m%d')}.pdf"
            )
            st.download_button(
                label="Descargar PDF",
                data=pdf_buf,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary",
            )
            st.success(f"PDF listo: {nombre_archivo}")
