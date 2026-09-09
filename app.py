# app del scorecard. correr con: streamlit run app.py
# necesita scorecard_model.pkl al lado (sale del notebook)

import hashlib
import pickle
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from fpdf import FPDF

# el fpdf nuevo no acepta ln=True
try:
    from fpdf.enums import XPos, YPos
    _NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
except:
    _NL = {"ln": True}

PROYECTO = "PROYECTO DE CIENCIA DE DATOS APLICADA"
SISTEMA = "Prototipo de scoring crediticio en entorno de experimentacion"
AUTOR = "Giuliano D'Angelo"
VERSION_MODELO = "Scorecard v1.0 - experimental"
ESCALA_MIN, ESCALA_MAX = 300, 850

DISCLAIMER = (
    "Prototipo con fines de demostracion tecnica. El modelo fue entrenado sobre "
    "un conjunto de datos publico de prestamos personales; los legajos que se "
    "cargan son hipoteticos. La aplicacion no pertenece a ninguna entidad "
    "financiera, no resuelve solicitudes reales y no constituye asesoramiento "
    "crediticio."
)

st.set_page_config(
    page_title="Motor de Scoring crediticio - Prototipo",
    layout="wide",
    initial_sidebar_state="expanded",
)

ETIQUETAS = {
    "person_age": "Edad del solicitante",
    "person_income": "Ingreso anual declarado",
    "person_home_ownership": "Regimen de vivienda",
    "person_emp_length": "Antiguedad laboral",
    "loan_intent": "Destino del prestamo",
    "loan_grade": "Grado interno de la operacion",
    "loan_amnt": "Monto solicitado",
    "loan_int_rate": "Tasa de interes nominal",
    "loan_percent_income": "Relacion monto / ingreso",
    "cb_person_default_on_file": "Antecedente de incumplimiento",
    "cb_person_cred_hist_length": "Extension del historial crediticio",
}

VIVIENDA = {
    "RENT": "Alquiler",
    "OWN": "Propietario",
    "MORTGAGE": "Hipotecada",
    "OTHER": "Otro",
}

DESTINO = {
    "PERSONAL": "Consumo personal",
    "EDUCATION": "Educacion",
    "MEDICAL": "Salud",
    "VENTURE": "Emprendimiento",
    "HOMEIMPROVEMENT": "Refaccion de vivienda",
    "DEBTCONSOLIDATION": "Consolidacion de deudas",
}

## la mayor parte de la UI estetica la cree con ayuda de Claude para no escribir mil lineas de codigo
## css. todo inline porque streamlit no toma un .css aparte sin joder con config

ESTILOS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap');

:root{
  --tinta:#101720; --navy:#16233A; --gris:#657084; --linea:#DFE3EA;
  --panel:#FFFFFF; --fondo:#F1F3F6;
  --sans:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  --serif:'IBM Plex Serif',Georgia,'Times New Roman',serif;
  --mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;
}

/* ---- base ------------------------------------------------------------- */
.stApp{background:var(--fondo);color:var(--tinta);font-family:var(--sans);}
html,body,[class*="css"]{font-family:var(--sans);}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"]{display:none;}
#MainMenu,footer{visibility:hidden;}
.block-container{padding:3.2rem 2.4rem 4rem;max-width:1240px;}
hr{border:none;border-top:1px solid var(--linea);margin:1.1rem 0;}

/* ---- animaciones ------------------------------------------------------ */
@keyframes surgir{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes velar{from{opacity:0;}to{opacity:1;}}
@keyframes trazo{from{width:0;}to{width:100%;}}
@keyframes crecer{to{width:var(--w);}}
.an{animation:surgir .55s cubic-bezier(.2,.7,.3,1) both;}

/* ---- cabecera institucional ------------------------------------------- */
.cab{border-bottom:2px solid var(--navy);padding-bottom:.85rem;margin-bottom:.2rem;
     display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:1rem;}
.cab .marca{font-family:var(--serif);font-size:1.62rem;font-weight:600;letter-spacing:-.015em;
     color:var(--navy);line-height:1.15;}
.cab .sub{font-size:.70rem;letter-spacing:.20em;text-transform:uppercase;color:var(--gris);
     font-weight:600;margin-top:.35rem;}
.cab .folio{text-align:right;font-family:var(--mono);font-size:.72rem;color:var(--gris);
     line-height:1.7;}
.cab .folio b{color:var(--tinta);font-weight:500;}

/* ---- titulos de seccion ----------------------------------------------- */
.sec{display:flex;align-items:baseline;gap:.7rem;margin:.1rem 0 1.05rem;}
.sec .n{font-family:var(--mono);font-size:.68rem;color:#fff;background:var(--navy);
     padding:.16rem .42rem;letter-spacing:.06em;}
.sec h3{font-family:var(--serif);font-size:1.02rem;font-weight:600;color:var(--tinta);margin:0;}
.sec p{font-size:.74rem;color:var(--gris);margin:0;}
.rot{font-size:.66rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gris);
     font-weight:600;margin:.2rem 0 .55rem;}

/* ---- paneles ----------------------------------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--panel);border:1px solid var(--linea);border-radius:2px;
  box-shadow:0 1px 2px rgba(16,24,40,.05);}
[data-testid="stVerticalBlockBorderWrapper"] > div{padding:.15rem;}

/* ---- controles de formulario ------------------------------------------- */
[data-testid="stWidgetLabel"] p{font-size:.685rem;text-transform:uppercase;
  letter-spacing:.10em;color:var(--gris);font-weight:600;}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{
  border-radius:2px !important;background:#FCFCFD !important;border-color:var(--linea) !important;}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within{
  border-color:var(--navy) !important;box-shadow:0 0 0 2px rgba(22,35,58,.08) !important;}
input,[data-baseweb="select"]{font-family:var(--mono) !important;font-size:.86rem !important;
  font-variant-numeric:tabular-nums;color:var(--tinta) !important;}
[data-testid="stNumberInput"] button{border-radius:0 !important;border-color:var(--linea) !important;}

/* ---- botones ------------------------------------------------------------ */
.stButton>button{width:100%;background:var(--navy);color:#fff;border:1px solid var(--navy);
  border-radius:2px;font-family:var(--sans);font-size:.72rem;font-weight:600;
  letter-spacing:.16em;text-transform:uppercase;padding:.92rem 1rem;
  transition:transform .25s cubic-bezier(.2,.7,.3,1),box-shadow .25s,background .25s;}
.stButton>button:hover{background:#0D1727;transform:translateY(-1px);
  box-shadow:0 8px 20px rgba(16,29,48,.20);color:#fff;}
.stButton>button:active{transform:translateY(0);}
.stButton>button:focus:not(:active){color:#fff;border-color:var(--navy);}
.stDownloadButton>button{width:100%;background:transparent;color:var(--navy);
  border:1px solid var(--navy);border-radius:2px;font-size:.70rem;font-weight:600;
  letter-spacing:.14em;text-transform:uppercase;padding:.78rem 1rem;transition:all .25s;}
.stDownloadButton>button:hover{background:var(--navy);color:#fff;}

/* ---- dictamen ----------------------------------------------------------- */
.dict{border-left:3px solid var(--navy);padding:.15rem 0 .15rem 1.05rem;margin:.1rem 0 1.1rem;}
.dict .lb{font-size:.66rem;letter-spacing:.19em;text-transform:uppercase;color:var(--gris);
  font-weight:600;}
.dict .vl{font-family:var(--serif);font-size:2.0rem;font-weight:600;letter-spacing:-.02em;
  line-height:1.2;margin-top:.15rem;}
.dict .gl{font-size:.845rem;line-height:1.62;color:#3A4453;margin-top:.55rem;max-width:52ch;}

/* ---- indicadores -------------------------------------------------------- */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--linea);
  border-bottom:1px solid var(--linea);}
.kpi{padding:.85rem 1rem;border-right:1px solid var(--linea);}
.kpi:last-child{border-right:none;}
.kpi .k{font-size:.63rem;letter-spacing:.13em;text-transform:uppercase;color:var(--gris);
  font-weight:600;}
.kpi .v{font-family:var(--mono);font-size:1.20rem;font-weight:500;color:var(--tinta);
  margin-top:.28rem;font-variant-numeric:tabular-nums;}
.kpi .u{font-size:.68rem;color:var(--gris);margin-top:.16rem;}

/* ---- tabla de factores -------------------------------------------------- */
.fac{width:100%;border-collapse:collapse;font-size:.80rem;}
.fac th{font-size:.63rem;letter-spacing:.13em;text-transform:uppercase;color:var(--gris);
  font-weight:600;text-align:left;padding:.5rem .7rem;border-bottom:1px solid var(--navy);}
.fac th.r,.fac td.r{text-align:right;}
.fac td{padding:.62rem .7rem;border-bottom:1px solid var(--linea);vertical-align:middle;}
.fac td.nm{color:var(--tinta);font-weight:500;}
.fac td.bn{font-family:var(--mono);font-size:.735rem;color:var(--gris);}
.fac td.pt{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--tinta);}
.fbar{position:relative;height:5px;background:#EDEFF3;width:150px;}
.fbar span{position:absolute;left:0;top:0;height:100%;width:0;
  animation:crecer .95s cubic-bezier(.2,.7,.3,1) forwards;}
.fac tr:hover td{background:#FAFBFC;}

/* ---- avisos -------------------------------------------------------------- */
.aviso{border:1px solid var(--linea);border-left:3px solid #8A5A12;background:#FDFBF6;
  padding:.7rem .95rem;font-size:.79rem;color:#4A4231;line-height:1.55;margin:.2rem 0 .9rem;}
.nota{font-size:.72rem;color:var(--gris);line-height:1.6;}

/* ---- banda de naturaleza experimental ---------------------------------- */
.demo{display:flex;align-items:baseline;gap:.75rem;flex-wrap:wrap;
  border:1px solid #E3D8C0;border-left:3px solid #8A5A12;background:#FDFBF6;
  padding:.6rem .9rem;margin-bottom:1.1rem;}
.demo .tag{font-size:.60rem;letter-spacing:.16em;text-transform:uppercase;
  font-weight:700;color:#8A5A12;white-space:nowrap;}
.demo .txt{font-size:.755rem;line-height:1.55;color:#5A5340;max-width:96ch;}
.pie{border-top:1px solid var(--linea);margin-top:2.6rem;padding-top:.9rem;
  font-size:.685rem;color:#8A93A2;line-height:1.65;letter-spacing:.01em;}

/* ---- barra lateral ------------------------------------------------------- */
[data-testid="stSidebar"]{background:var(--navy);border-right:1px solid var(--navy);}
[data-testid="stSidebar"] *{color:#C9D2E0;}
.sb-t{font-family:var(--serif);font-size:1.18rem;font-weight:600;color:#FFFFFF !important;
  letter-spacing:-.01em;line-height:1.25;
  border-bottom:1px solid rgba(255,255,255,.16);padding-bottom:.7rem;margin-bottom:1rem;}
.sb-r{display:flex;justify-content:space-between;gap:.6rem;padding:.34rem 0;
  border-bottom:1px solid rgba(255,255,255,.07);font-size:.735rem;}
.sb-r .k{color:#8E9CB4 !important;letter-spacing:.03em;}
.sb-r .v{font-family:var(--mono);color:#FFFFFF !important;font-variant-numeric:tabular-nums;}
.sb-h{font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:#7C8AA3 !important;
  font-weight:600;margin:1.5rem 0 .55rem;}
.sb-n{font-size:.70rem;color:#8E9CB4 !important;line-height:1.62;}
</style>
"""


# si la maquina esta en modo oscuro y el config.toml no tiene base="light",
# los widgets salen negros sobre el fondo claro. esto lo pisa todo a mano.

BLINDAJE = """
<style>
:root,.stApp{color-scheme:light;}

/* --- superficies generales ------------------------------------------------ */
[data-testid="stAppViewContainer"],[data-testid="stMain"],section.main{
  background:#F1F3F6 !important;}
[data-testid="stHeader"]{background:#F1F3F6 !important;}
[data-testid="stDecoration"]{display:none !important;}
[data-testid="stMarkdownContainer"]{color:#101720;}

/* --- campos de texto y numericos ------------------------------------------ */
[data-baseweb="input"],[data-baseweb="base-input"],
[data-testid="stNumberInputContainer"],[data-testid="stTextInputRootElement"]{
  background:#FCFCFD !important;border-color:#DFE3EA !important;}
.stApp input,.stApp textarea{
  background:#FCFCFD !important;color:#101720 !important;
  -webkit-text-fill-color:#101720 !important;caret-color:#16233A;}
.stApp input::placeholder{color:#98A1B0 !important;-webkit-text-fill-color:#98A1B0 !important;}
.stApp input:disabled{-webkit-text-fill-color:#98A1B0 !important;}

/* --- pasos +/- del number_input ------------------------------------------- */
[data-testid="stNumberInputStepUp"],[data-testid="stNumberInputStepDown"]{
  background:#F3F5F8 !important;color:#16233A !important;border-color:#DFE3EA !important;}
[data-testid="stNumberInputStepUp"]:hover,[data-testid="stNumberInputStepDown"]:hover{
  background:#E8ECF2 !important;color:#0D1727 !important;}
[data-testid="stNumberInputStepUp"] svg,[data-testid="stNumberInputStepDown"] svg{
  fill:#16233A !important;}

/* --- selectores: control cerrado ------------------------------------------ */
[data-baseweb="select"]>div{background:#FCFCFD !important;border-color:#DFE3EA !important;}
[data-baseweb="select"] div,[data-baseweb="select"] span{color:#101720 !important;}
[data-baseweb="select"] svg{fill:#657084 !important;}

/* el foco de streamlit usa primaryColor, que por defecto es ese rojo #FF4B4B */
[data-baseweb="select"]>div:focus-within,[data-baseweb="select"]>div[aria-expanded="true"],
[data-baseweb="input"]:focus-within,[data-baseweb="base-input"]:focus-within,
[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within{
  border-color:#16233A !important;
  box-shadow:0 0 0 2px rgba(22,35,58,.10) !important;
  outline:none !important;}

/* el menu del selectbox se monta afuera de .stApp. no se cual de todos estos
   divs pinta el fondo, si saco alguno se rompe, asi que van todos */
[data-baseweb="popover"],[data-baseweb="popover"]>div,
[data-baseweb="popover"] div,[data-baseweb="popover"] ul,
[data-baseweb="menu"],[data-baseweb="menu"]>div,[data-baseweb="menu"] div,
[data-baseweb="menu"] ul,[role="listbox"]{
  background-color:#FFFFFF !important;background-image:none !important;color:#101720 !important;}

[data-baseweb="popover"] [data-baseweb="menu"],[data-baseweb="popover"] [role="listbox"]{
  border:1px solid #DFE3EA !important;border-radius:2px !important;
  box-shadow:0 10px 28px rgba(16,24,40,.14) !important;padding:2px 0 !important;}

[data-baseweb="popover"] li,[data-baseweb="menu"] li,[role="option"]{
  background-color:transparent !important;color:#101720 !important;
  font-family:'IBM Plex Mono',ui-monospace,monospace !important;
  font-size:.82rem !important;padding:.5rem .75rem !important;border-radius:0 !important;}

[role="option"]:hover,[data-baseweb="menu"] li:hover,
[role="option"][aria-selected="true"],[data-baseweb="menu"] li[aria-selected="true"]{
  background-color:#EEF1F5 !important;color:#101720 !important;
  box-shadow:inset 2px 0 0 #16233A !important;}

/* barra de desplazamiento del menu */
[data-baseweb="menu"] ul::-webkit-scrollbar,[role="listbox"]::-webkit-scrollbar{width:8px;}
[data-baseweb="menu"] ul::-webkit-scrollbar-track,[role="listbox"]::-webkit-scrollbar-track{
  background:#F1F3F6 !important;}
[data-baseweb="menu"] ul::-webkit-scrollbar-thumb,[role="listbox"]::-webkit-scrollbar-thumb{
  background:#C3CAD5 !important;border-radius:0;}

/* la barra lateral si va oscura, es a proposito */
[data-testid="stSidebar"],[data-testid="stSidebarContent"]{background:#16233A !important;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]{color:#C9D2E0 !important;}
[data-testid="stSidebar"] input{background:#1E2C45 !important;color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;}

/* --- paneles y avisos ------------------------------------------------------ */
[data-testid="stVerticalBlockBorderWrapper"]{background:#FFFFFF !important;}
[data-testid="stAlert"]{background:#FDFBF6 !important;color:#4A4231 !important;
  border:1px solid #DFE3EA !important;border-radius:2px !important;}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"]{color:#4A4231 !important;}

/* ojo: el header de streamlit es fixed, si le saco el alto se come la primera
   linea. van los tres testid porque cambian segun la version */
.block-container,[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"]{
  padding-top:3.2rem !important;padding-bottom:4rem !important;
  padding-left:2.4rem !important;padding-right:2.4rem !important;
  max-width:1240px !important;}
/* saque el boton de colapso (ver abajo) y esta franja quedo vacia ocupando
   lugar, asi que la aplasto */
[data-testid="stSidebarHeader"]{
  height:0 !important;min-height:0 !important;padding:0 !important;
  margin:0 !important;overflow:hidden !important;}
[data-testid="stSidebarUserContent"]{padding-top:1.5rem !important;}
[data-testid="stSidebarContent"]>div:first-child{padding-top:0 !important;}
[data-testid="stSidebar"] .sb-t{margin-top:0;}

@media (max-width:900px){
  .block-container,[data-testid="stMainBlockContainer"],
  [data-testid="stAppViewBlockContainer"]{
    padding-left:1.2rem !important;padding-right:1.2rem !important;
    padding-top:2.4rem !important;}
}

/* la barra va siempre abierta. antes peleaba con el boton de expandir y se
   rompia en cada update de streamlit, asi que lo escondo y listo */
[data-testid="stSidebar"],[data-testid="stSidebar"][aria-expanded="false"]{
  display:block !important;visibility:visible !important;opacity:1 !important;
  transform:none !important;margin-left:0 !important;left:0 !important;
  min-width:252px !important;width:252px !important;max-width:252px !important;
  transition:none !important;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"],
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{
  visibility:visible !important;opacity:1 !important;}

[data-testid="stSidebarCollapseButton"],[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarHeader"] button{display:none !important;}

/* en celular vuelve el comportamiento nativo: se superpone al contenido, asi
   que ahi si tiene que poder cerrarse */
@media (max-width:900px){
  [data-testid="stSidebar"]{min-width:0 !important;width:auto !important;
    max-width:100% !important;}
  [data-testid="stSidebarCollapseButton"],[data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"],[data-testid="stExpandSidebarButton"]{
    display:flex !important;}
}

/* el color del boton no agarra si no lo repito en los hijos, el label queda
   gris. raro esto pero anda */
.stButton>button,[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"]{
  background:#16233A !important;border:1px solid #16233A !important;
  border-radius:2px !important;}
.stButton>button,.stButton>button *,
.stButton>button p,.stButton>button div,.stButton>button span,
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondary"] *{
  color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;}
.stButton>button:hover,[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover{
  background:#0D1727 !important;border-color:#0D1727 !important;}
.stButton>button:focus,.stButton>button:focus-visible,
.stButton>button:active{border-color:#0D1727 !important;
  box-shadow:0 0 0 2px rgba(22,35,58,.18) !important;outline:none !important;}

/* Boton de descarga: variante de contorno, texto navy que invierte al pasar. */
.stDownloadButton>button,[data-testid="stBaseButton-secondaryFormSubmit"]{
  background:transparent !important;border:1px solid #16233A !important;
  border-radius:2px !important;}
.stDownloadButton>button,.stDownloadButton>button *,
.stDownloadButton>button p,.stDownloadButton>button div,.stDownloadButton>button span{
  color:#16233A !important;-webkit-text-fill-color:#16233A !important;}
.stDownloadButton>button:hover{background:#16233A !important;}
.stDownloadButton>button:hover,.stDownloadButton>button:hover *{
  color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;}

/* el iframe del medidor no tiene que heredar el fondo oscuro */
iframe[title="streamlit_component_v1"],[data-testid="stIFrame"]{
  background:#FFFFFF !important;color-scheme:light;}
</style>
"""


RUTA_MODELO = Path(__file__).resolve().parent / "models" / "scorecard_model.pkl"


# cache_resource, con cache_data no anda porque el scorecard no se serializa
@st.cache_resource(show_spinner=False)
def cargar_modelo():
    with open(RUTA_MODELO, "rb") as f:
        return pickle.load(f)


if not RUTA_MODELO.exists():
    st.markdown(ESTILOS, unsafe_allow_html=True)
    st.error(
        f"No se encontro el archivo del modelo en la ruta esperada: {RUTA_MODELO}. "
        "El motor de decision no puede inicializarse."
    )
    st.stop()

artefactos = cargar_modelo()
scorecard = artefactos["scorecard"]
CORTE_APROBACION = int(artefactos["cutoff_aprobacion"])
CORTE_REVISION = int(artefactos["cutoff_revision"])


def miles(valor, decimales=0):
    # formato AR. lo del @ es un hack para no depender de locale
    try:
        txt = f"{float(valor):,.{decimales}f}"
    except:
        return str(valor)
    return txt.replace(",", "@").replace(".", ",").replace("@", ".")


# def cuota(capital, tna, meses):
#     return (capital * (1 + tna / 100)) / meses   <- estaba mal, no era frances


def cuota_francesa(capital, tna, meses):
    i = tna / 100.0 / 12.0
    if meses <= 0:
        return 0.0
    if i <= 0:
        return capital / meses
    return capital * i / (1 - (1 + i) ** (-meses))


DICTAMENES = {
    "APROBADO": {
        "color": "#15603C",
        "glosa": (
            "El puntaje supera el corte de aprobacion definido para este ejercicio. "
            "En un entorno productivo, el legajo se derivaria a otorgamiento bajo "
            "condiciones estandar de tasa y plazo."
        ),
    },
    "REVISION MANUAL": {
        "color": "#8A5A12",
        "glosa": (
            "El puntaje se ubica en la franja de indeterminacion del ejercicio. "
            "En un entorno productivo, el legajo se derivaria a analisis manual con "
            "verificacion documental de ingresos o constitucion de garantia adicional."
        ),
    },
    "RECHAZADO": {
        "color": "#8E2226",
        "glosa": (
            "El riesgo estimado excede el umbral definido para este ejercicio. En un "
            "entorno productivo, el legajo se derivaria a rechazo o a una "
            "reformulacion de las condiciones solicitadas."
        ),
    },
}


def color_dictamen(dictamen):
    return DICTAMENES[dictamen]["color"]


def resolver_dictamen(score):
    if score >= CORTE_APROBACION:
        return "APROBADO"
    if score >= CORTE_REVISION:
        return "REVISION MANUAL"
    return "RECHAZADO"


##### el gauge. lo hice con ayuda de claude porque con svg porque el de plotly no me gustaba

PLANTILLA_MEDIDOR = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#FFFFFF;font-family:'IBM Plex Sans',sans-serif;overflow:hidden;}
.mrc{padding:2px 6px 0;}
svg{display:block;margin:0 auto;}
#num{font-family:'IBM Plex Mono',monospace;font-size:46px;font-weight:500;fill:#101720;
     letter-spacing:-.01em;}
#cap{font-family:'IBM Plex Sans',sans-serif;font-size:8.4px;font-weight:600;fill:#657084;
     letter-spacing:2.1px;}
.esc{margin:2px 10px 0;}
.tira{position:relative;height:7px;display:flex;background:#EDEFF3;}
.tira i{display:block;height:100%;}
.mk{position:absolute;top:-6px;left:0;transition:left 1.45s cubic-bezier(.22,.68,.24,1);
    transform:translateX(-50%);}
.mk .pin{width:1px;height:19px;background:#101720;margin:0 auto;}
.mk .cab{width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;
    border-top:5px solid #101720;margin:0 auto;}
.ejes{display:flex;justify-content:space-between;margin-top:6px;font-family:'IBM Plex Mono',monospace;
    font-size:9.2px;color:#8A93A2;}
.leyendas{display:flex;margin-top:9px;border-top:1px solid #E6E9EE;padding-top:7px;}
.leyendas div{font-size:8.2px;letter-spacing:1.5px;text-transform:uppercase;color:#8A93A2;
    font-weight:600;text-align:center;}
</style>

<div class="mrc">
  <svg viewBox="0 0 300 158" width="100%" height="164" preserveAspectRatio="xMidYMid meet">
    <path d="M30,140 A120,120 0 0 1 270,140" fill="none" stroke="#E9ECF1" stroke-width="8"/>
    <path id="arco" d="M30,140 A120,120 0 0 1 270,140" fill="none" stroke="__COLOR__"
          stroke-width="8" stroke-dasharray="377" stroke-dashoffset="377"/>
    <text id="num" x="150" y="122" text-anchor="middle">300</text>
    <text id="cap" x="150" y="140" text-anchor="middle">PUNTAJE DE COMPORTAMIENTO</text>
  </svg>

  <div class="esc">
    <div class="tira">
      <i style="width:__W1__%;background:#C9A5A6"></i>
      <i style="width:__W2__%;background:#D9C398"></i>
      <i style="width:__W3__%;background:#A2BFAD"></i>
      <div class="mk" id="mk"><div class="cab"></div><div class="pin"></div></div>
    </div>
    <div class="ejes"><span>300</span><span>__CR__</span><span>__CA__</span><span>850</span></div>
    <div class="leyendas">
      <div style="width:__W1__%">Rechazo</div>
      <div style="width:__W2__%">Revision</div>
      <div style="width:__W3__%">Aprobacion</div>
    </div>
  </div>
</div>

<script>
(function(){
  var S=__SCORE__, F=__FRAC__, P=__POS__, L=377, D=1450;
  var arco=document.getElementById('arco'), num=document.getElementById('num'),
      mk=document.getElementById('mk');
  requestAnimationFrame(function(){
    arco.style.transition='stroke-dashoffset 1.45s cubic-bezier(.22,.68,.24,1)';
    arco.style.strokeDashoffset = L*(1-F);
    mk.style.left = P+'%';
  });
  var t0=null;
  function paso(t){
    if(t0===null) t0=t;
    var p=Math.min(1,(t-t0)/D), e=1-Math.pow(1-p,3);
    num.textContent = Math.round(300+(S-300)*e);
    if(p<1) requestAnimationFrame(paso);
  }
  requestAnimationFrame(paso);
})();
</script>
"""


def render_medidor(score, dictamen):
    frac = max(0.0, min(1.0, (score - ESCALA_MIN) / (ESCALA_MAX - ESCALA_MIN)))
    total = ESCALA_MAX - ESCALA_MIN
    w1 = (CORTE_REVISION - ESCALA_MIN) / total * 100
    w2 = (CORTE_APROBACION - CORTE_REVISION) / total * 100
    w3 = 100 - w1 - w2

    html = (
        PLANTILLA_MEDIDOR.replace("__COLOR__", color_dictamen(dictamen))
        .replace("__SCORE__", str(score))
        .replace("__FRAC__", f"{frac:.5f}")
        .replace("__POS__", f"{frac * 100:.3f}")
        .replace("__W1__", f"{w1:.3f}")
        .replace("__W2__", f"{w2:.3f}")
        .replace("__W3__", f"{w3:.3f}")
        .replace("__CR__", str(CORTE_REVISION))
        .replace("__CA__", str(CORTE_APROBACION))
    )
    components.html(html, height=268, scrolling=False)


@st.cache_data(show_spinner=False)
def tabla_detallada():
    # el style detailed no esta en todas las versiones de optbinning
    try:
        tabla = scorecard.table(style="detailed").copy()
        if "Points" not in tabla.columns:
            return None
        return tabla
    except Exception:
        return None


def descomponer(df_eval):
    # aprovechamiento = que parte de los puntos posibles de esa variable se
    # lleva el tramo que le toco. 0 el peor tramo, 1 el mejor.
    tabla = tabla_detallada()
    if tabla is None:
        return None
    try:
        indices = scorecard.binning_process_.transform(df_eval, metric="indices")
    except Exception:
        return None

    rows = []
    for variable in indices.columns:
        try:
            bin_id = int(indices[variable].iloc[0])
        except (TypeError, ValueError):
            continue

        sub = tabla[tabla["Variable"] == variable]
        actual = sub[sub["Bin id"] == bin_id]
        if actual.empty:
            continue

        # sin Special ni Missing, me rompian el maximo
        base = sub[~sub["Bin"].astype(str).isin(["Special", "Missing"])]
        if base.empty:
            base = sub

        puntos = float(actual["Points"].iloc[0])
        p_min, p_max = float(base["Points"].min()), float(base["Points"].max())
        rango = p_max - p_min
        aprov = 0.5 if rango <= 0 else max(0.0, min(1.0, (puntos - p_min) / rango))

        rows.append(
            {
                "variable": variable,
                "etiqueta": ETIQUETAS.get(variable, variable),
                "tramo": str(actual["Bin"].iloc[0]),
                "puntos": puntos,
                "maximo": p_max,
                "brecha": p_max - puntos,
                "aprovechamiento": aprov,
            }
        )

    return sorted(rows, key=lambda f: f["aprovechamiento"]) or None


def color_aporte(aprov):
    if aprov >= 0.6:
        return "#4E8C6A"
    if aprov >= 0.35:
        return "#C79A4B"
    return "#B8666A"


## PDF
# fpdf con las fuentes core es latin-1 y explota con las comillas raras

_REEMPLAZOS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", " ": " ",  # el ultimo es un nbsp
}


def _s(texto):
    salida = str(texto)
    for origen, destino in _REEMPLAZOS.items():
        salida = salida.replace(origen, destino)
    return salida.encode("latin-1", "replace").decode("latin-1")


def _marca_agua(pdf):
    try:
        with pdf.rotation(45, x=105, y=150):
            pdf.set_font("Helvetica", "B", 46)
            pdf.set_text_color(237, 240, 245)
            pdf.set_xy(15, 140)
            pdf.cell(180, 20, _s("EJERCICIO DE DEMOSTRACION"), align="C")
    except Exception:
        pass  # rotation() no existe en fpdf2 viejo; sin sello, pero sale el pdf


class Informe(FPDF):
    folio = ""

    def header(self):
        # el sello va primero, si no tapa el texto
        x0, y0 = self.get_x(), self.get_y()
        _marca_agua(self)
        self.set_xy(x0, y0)

        self.set_font("Helvetica", "B", 8)
        self.set_text_color(101, 112, 132)
        self.cell(120, 5, _s(PROYECTO), align="L")
        self.cell(70, 5, _s(f"Caso de prueba {self.folio}"), align="R", **_NL)
        self.set_draw_color(22, 35, 58)
        self.set_line_width(0.6)
        self.line(10, self.get_y() + 1, 200, self.get_y() + 1)
        self.set_line_width(0.2)
        self.line(10, self.get_y() + 2.1, 200, self.get_y() + 2.1)
        self.ln(8)

    def footer(self):
        self.set_y(-16)
        self.set_draw_color(223, 227, 234)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(150, 158, 172)
        self.cell(
            150,
            4,
            _s(
                "Documento de demostracion sin validez comercial ni contractual. "
                f"Generado por un prototipo experimental ({VERSION_MODELO})."
            ),
            align="L",
        )
        self.cell(40, 4, _s(f"Pagina {self.page_no()}"), align="R")

    def titulo_seccion(self, numero, texto):
        self.ln(3)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(22, 35, 58)
        self.cell(0, 6, _s(f"{numero}.  {texto.upper()}"), **_NL)
        self.set_draw_color(223, 227, 234)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2.6)

    def fila(self, izquierda, derecha, sombra=False):
        if sombra:
            self.set_fill_color(248, 249, 251)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(75, 85, 100)
        self.cell(95, 6.4, _s("  " + izquierda), border="B", fill=sombra)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(16, 23, 32)
        self.cell(95, 6.4, _s("  " + derecha), border="B", fill=sombra, **_NL)


def generar_informe(folio, momento, datos, operacion, score, dictamen,
                    pd_estimada, factores):
    pdf = Informe()
    pdf.folio = folio
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    # portada
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(16, 23, 32)
    pdf.cell(0, 8, _s("Informe de evaluacion crediticia"), **_NL)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(101, 112, 132)
    pdf.cell(
        0, 5,
        _s(f"Generado el {momento}  |  {VERSION_MODELO}  |  Escala 300-850  |  {AUTOR}"),
        **_NL,
    )

    # recuadro de aviso, pegado abajo del titulo
    pdf.ln(1.5)
    y_av = pdf.get_y()
    pdf.set_fill_color(253, 251, 246)
    pdf.rect(10, y_av, 190, 13, style="F")
    pdf.set_fill_color(138, 90, 18)
    pdf.rect(10, y_av, 1.4, 13, style="F")
    pdf.set_xy(14, y_av + 1.6)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(138, 90, 18)
    pdf.cell(0, 3.4, _s("EJERCICIO DE DEMOSTRACION - SIN VALIDEZ COMERCIAL"), **_NL)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 7.4)
    pdf.set_text_color(90, 83, 64)
    pdf.multi_cell(182, 3.2, _s(DISCLAIMER))
    pdf.set_y(y_av + 15)

    pdf.titulo_seccion("I", "Dictamen")

    y0 = pdf.get_y()
    pdf.set_fill_color(247, 248, 250)
    pdf.rect(10, y0, 190, 24, style="F")
    rgb = tuple(int(color_dictamen(dictamen).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    pdf.set_fill_color(*rgb)
    pdf.rect(10, y0, 1.6, 24, style="F")

    pdf.set_xy(15, y0 + 3.5)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(101, 112, 132)
    pdf.cell(60, 4, _s("PUNTAJE OBTENIDO"))
    pdf.cell(60, 4, _s("RESOLUCION"))
    pdf.cell(60, 4, _s("PROBABILIDAD DE INCUMPLIMIENTO"), **_NL)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(16, 23, 32)
    pdf.cell(60, 9, _s(f"{score}"))
    pdf.set_text_color(*rgb)
    pdf.cell(60, 9, _s(dictamen))
    pdf.set_text_color(16, 23, 32)
    pdf.cell(60, 9, _s(f"{pd_estimada * 100:.2f}%" if pd_estimada is not None else "n/d"), **_NL)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(101, 112, 132)
    pdf.cell(
        0,
        4,
        _s(
            f"Cortes definidos para el ejercicio - aprobacion: {CORTE_APROBACION}   "
            f"revision: {CORTE_REVISION}"
        ),
        **_NL,
    )

    # la misma barra 300-850 del medidor, pero dibujada con rects
    pdf.set_y(y0 + 28)
    ancho, x0, y1 = 190.0, 10.0, pdf.get_y()
    tramo = ESCALA_MAX - ESCALA_MIN
    a1 = (CORTE_REVISION - ESCALA_MIN) / tramo * ancho
    a2 = (CORTE_APROBACION - CORTE_REVISION) / tramo * ancho
    pdf.set_fill_color(201, 165, 166); pdf.rect(x0, y1, a1, 2.2, style="F")
    pdf.set_fill_color(217, 195, 152); pdf.rect(x0 + a1, y1, a2, 2.2, style="F")
    pdf.set_fill_color(162, 191, 173); pdf.rect(x0 + a1 + a2, y1, ancho - a1 - a2, 2.2, style="F")
    px = x0 + max(0.0, min(1.0, (score - ESCALA_MIN) / tramo)) * ancho
    pdf.set_fill_color(16, 23, 32); pdf.rect(px - 0.5, y1 - 2.2, 1.0, 6.6, style="F")
    pdf.set_y(y1 + 6)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(150, 158, 172)
    pdf.cell(63, 4, _s("300"), align="L")
    pdf.cell(64, 4, _s(f"{CORTE_REVISION}          {CORTE_APROBACION}"), align="C")
    pdf.cell(63, 4, _s("850"), align="R", **_NL)

    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(58, 68, 83)
    pdf.multi_cell(190, 4.8, _s("Fundamento: " + DICTAMENES[dictamen]["glosa"]))

    pdf.titulo_seccion("II", "Antecedentes del solicitante")
    for i, (clave, valor) in enumerate(datos.items()):
        pdf.fila(ETIQUETAS.get(clave, clave), valor, sombra=(i % 2 == 0))

    pdf.titulo_seccion("III", "Condiciones de la operacion")
    for i, (clave, valor) in enumerate(operacion.items()):
        pdf.fila(clave, valor, sombra=(i % 2 == 0))

    if factores:
        pdf.titulo_seccion("IV", "Descomposicion del puntaje por variable")
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(101, 112, 132)
        pdf.set_fill_color(240, 242, 246)
        pdf.cell(78, 6, _s("  VARIABLE"), border="B", fill=True)
        pdf.cell(60, 6, _s("  TRAMO ASIGNADO"), border="B", fill=True)
        pdf.cell(26, 6, _s("PUNTOS  "), border="B", fill=True, align="R")
        pdf.cell(26, 6, _s("APROVECH.  "), border="B", fill=True, align="R", **_NL)

        for i, f in enumerate(factores):
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(16, 23, 32)
            sombra = i % 2 == 0
            if sombra:
                pdf.set_fill_color(250, 251, 252)
            pdf.cell(78, 6, _s("  " + f["etiqueta"]), border="B", fill=sombra)
            pdf.set_font("Helvetica", "", 7.2)
            pdf.set_text_color(101, 112, 132)
            tramo_txt = f["tramo"][:34] + ("..." if len(f["tramo"]) > 34 else "")
            pdf.cell(60, 6, _s("  " + tramo_txt), border="B", fill=sombra)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(16, 23, 32)
            pdf.cell(26, 6, _s(f"{f['puntos']:.1f}  "), border="B", fill=sombra, align="R")
            pdf.cell(
                26, 6, _s(f"{f['aprovechamiento'] * 100:.0f}%  "),
                border="B", fill=sombra, align="R", **_NL,
            )

        adversos = [f for f in factores if f["aprovechamiento"] < 0.5][:3]
        if adversos:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(22, 35, 58)
            pdf.cell(0, 5, _s("Principales factores adversos del legajo"), **_NL)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(58, 68, 83)
            for n, f in enumerate(adversos, start=1):
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(
                    190, 4.6,
                    _s(
                        f"{n}. {f['etiqueta']}: el tramo asignado cede {f['brecha']:.1f} "
                        f"puntos respecto del maximo alcanzable en esa variable."
                    ),
                    **_NL,
                )

    pdf.titulo_seccion("V", "Naturaleza del ejercicio y limitaciones")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(101, 112, 132)
    pdf.multi_cell(
        190,
        4.4,
        _s(
            "Este informe es la salida de un prototipo construido con fines de demostracion "
            "tecnica y no proviene de ninguna entidad financiera. El puntaje expresa el riesgo "
            "relativo de incumplimiento estimado por un modelo entrenado sobre un conjunto de "
            "datos publico de prestamos personales, y los puntos de corte fueron fijados por el "
            "autor para ilustrar la mecanica de un motor de decision, no por una politica de "
            "riesgo vigente. El legajo evaluado es hipotetico. En consecuencia, el documento no "
            "constituye una decision de otorgamiento, una calificacion crediticia ni "
            "asesoramiento financiero, y no debe emplearse para evaluar personas reales.\n\n"
            "El desempeño del modelo sobre datos historicos no garantiza su comportamiento "
            "sobre poblaciones distintas de aquella con la que fue entrenado. Un despliegue "
            "productivo exigiria validacion sobre muestra fuera de tiempo, analisis de "
            "estabilidad poblacional, revision de sesgos y gobierno del modelo."
        ),
    )
    return bytes(pdf.output())


# ---------- app ----------

st.markdown(ESTILOS + BLINDAJE, unsafe_allow_html=True)

# un folio por sesion, asi el pdf y la pantalla dicen lo mismo
if "folio" not in st.session_state:
    st.session_state.folio = f"DEMO-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"

momento = datetime.now().strftime("%d/%m/%Y %H:%M")

# barra lateral: ficha tecnica del modelo
with st.sidebar:
    st.markdown('<div class="sb-t">Ficha tecnica del modelo</div>', unsafe_allow_html=True)

    ficha = [
        ("Version", VERSION_MODELO),
        ("Metodologia", "WoE + Logistica"),
        ("Discretizacion", "OptBinning"),
        ("Escala", f"{ESCALA_MIN} - {ESCALA_MAX}"),
    ]
    # los pkl viejos no traen las metricas
    gini, ks = artefactos.get("gini"), artefactos.get("ks")
    if gini is not None:
        ficha.append(("Indice de Gini", f"{float(gini):.3f}"))
    if ks is not None:
        ficha.append(("Estadistico KS", f"{float(ks):.1f}%"))

    for clave, valor in ficha:
        st.markdown(
            f'<div class="sb-r"><span class="k">{clave}</span>'
            f'<span class="v">{valor}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sb-h">Umbrales del ejercicio</div>', unsafe_allow_html=True)
    politica = [
        ("Aprobacion", f"&ge; {CORTE_APROBACION}"),
        ("Revision manual", f"{CORTE_REVISION} - {CORTE_APROBACION - 1}"),
        ("Rechazo", f"&lt; {CORTE_REVISION}"),
    ]
    for clave, valor in politica:
        st.markdown(
            f'<div class="sb-r"><span class="k">{clave}</span>'
            f'<span class="v">{valor}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sb-h">Naturaleza del proyecto</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sb-n">Prototipo de demostracion tecnica, sin vinculo con '
        "entidad financiera alguna. Los puntos de corte fueron fijados por el autor "
        "para este ejercicio y no responden a una politica de riesgo vigente. Los "
        "legajos cargados son hipoteticos y ningun dictamen tiene efecto real.</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sb-h">Autoria</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sb-n"><span style="color:#FFFFFF">{AUTOR}</span><br>'
        "Modelo entrenado sobre un conjunto de datos publico de prestamos "
        "personales. Construccion del scorecard con OptBinning y regresion "
        "logistica sobre WoE.</div>",
        unsafe_allow_html=True,
    )

# cabecera
st.markdown(
    f"""
    <div class="demo an">
      <span class="tag">Proyecto de portfolio</span>
      <span class="txt">{DISCLAIMER}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="cab an">
      <div>
        <div class="marca">Motor de Scoring crediticio - PROTOTIPO</div>
        <div class="sub">{PROYECTO} &nbsp;&middot;&nbsp; {SISTEMA}</div>
      </div>
      <div class="folio">
        Caso de prueba <b>{st.session_state.folio}</b><br>
        Fecha de evaluacion <b>{momento}</b>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# formulario de carga
st.markdown(
    """
    <div class="sec an">
      <span class="n">01</span>
      <div>
        <h3>Carga del legajo</h3>
        <p>Complete los atributos del solicitante y las condiciones de la operacion solicitada.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.write("")
    c1, c2, c3 = st.columns(3, gap="large")

    with c1:
        st.markdown('<div class="rot">A &nbsp;&middot;&nbsp; Perfil del solicitante</div>',
                    unsafe_allow_html=True)
        person_age = st.number_input("Edad", min_value=18, max_value=100, value=28, step=1)
        person_income = st.number_input(
            "Ingreso anual declarado", min_value=1_000, max_value=2_000_000,
            value=50_000, step=1_000,
        )
        person_home_ownership = st.selectbox(
            "Regimen de vivienda", list(VIVIENDA), format_func=lambda v: VIVIENDA[v],
        )
        person_emp_length = st.number_input(
            "Antiguedad laboral (años)", min_value=0.0, max_value=60.0, value=4.0, step=0.5,
        )

    with c2:
        st.markdown('<div class="rot">B &nbsp;&middot;&nbsp; Condiciones de la operacion</div>',
                    unsafe_allow_html=True)
        loan_intent = st.selectbox(
            "Destino del prestamo", list(DESTINO), format_func=lambda v: DESTINO[v],
        )
        # TODO: sacar las grades del binning en vez de tenerlas a mano aca
        loan_grade = st.selectbox(
            "Grado interno", ["A", "B", "C", "D", "E", "F", "G"],
        )
        loan_amnt = st.number_input(
            "Monto solicitado", min_value=500, max_value=50_000, value=8_000, step=500,
        )
        loan_int_rate = st.number_input(
            "Tasa nominal anual (%)", min_value=5.0, max_value=30.0, value=11.2, step=0.1,
        )

    with c3:
        st.markdown('<div class="rot">C &nbsp;&middot;&nbsp; Antecedentes crediticios</div>',
                    unsafe_allow_html=True)
        cb_person_default_on_file = st.selectbox(
            "Incumplimiento previo registrado", ["N", "Y"],
            format_func=lambda v: "No registra" if v == "N" else "Registra antecedente",
        )
        cb_person_cred_hist_length = st.number_input(
            "Extension del historial (años)", min_value=0, max_value=50, value=5, step=1,
        )
        plazo = st.number_input(
            "Plazo de amortizacion (meses)", min_value=6, max_value=120, value=36, step=6,
        )
        st.markdown(
            '<div class="nota">El plazo se utiliza unicamente para estimar la cuota; '
            "no interviene en el calculo del puntaje.</div>",
            unsafe_allow_html=True,
        )

    st.write("")

# el unico que entra al modelo es loan_percent_income, el resto es para mostrar
loan_percent_income = round(loan_amnt / person_income, 2) if person_income > 0 else 0.0
cuota = cuota_francesa(loan_amnt, loan_int_rate, int(plazo))
ingreso_mensual = person_income / 12 if person_income > 0 else 0.0
carga = cuota / ingreso_mensual if ingreso_mensual > 0 else 0.0

st.write("")
st.markdown(
    f"""
    <div class="kpis an">
      <div class="kpi"><div class="k">Relacion monto / ingreso</div>
        <div class="v">{loan_percent_income * 100:.1f}%</div>
        <div class="u">variable del modelo</div></div>
      <div class="kpi"><div class="k">Cuota estimada</div>
        <div class="v">{f"{cuota:,.0f}".replace(",", ".")}</div>
        <div class="u">sistema frances a {int(plazo)} meses</div></div>
      <div class="kpi"><div class="k">Carga sobre ingreso mensual</div>
        <div class="v">{carga * 100:.1f}%</div>
        <div class="u">cuota / ingreso mensual</div></div>
      <div class="kpi"><div class="k">Costo financiero total</div>
        <div class="v">{f"{cuota * int(plazo) - loan_amnt:,.0f}".replace(",", ".")}</div>
        <div class="u">intereses del periodo</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if carga > 0.35:
    st.markdown(
        f'<div class="aviso an">La cuota estimada compromete el '
        f"{carga * 100:.1f}% del ingreso mensual declarado, por encima del umbral "
        "prudencial del 35% fijado por la politica de originacion.</div>",
        unsafe_allow_html=True,
    )

# las keys tienen que llamarse igual que en el entrenamiento o revienta
data_cliente = {
    "person_age": person_age,
    "person_income": person_income,
    "person_home_ownership": person_home_ownership,
    "person_emp_length": person_emp_length,
    "loan_intent": loan_intent,
    "loan_grade": loan_grade,
    "loan_amnt": loan_amnt,
    "loan_int_rate": loan_int_rate,
    "loan_percent_income": loan_percent_income,
    "cb_person_default_on_file": cb_person_default_on_file,
    "cb_person_cred_hist_length": cb_person_cred_hist_length,
}

# para darme cuenta si tocaron algo despues de correr el motor
huella = hashlib.md5((str(data_cliente) + str(plazo)).encode("utf-8")).hexdigest()

st.write("")
if st.button("Ejecutar evaluacion de riesgo", type="primary"):
    df_eval = pd.DataFrame([data_cliente])
    # st.write(df_eval)
    score = int(round(float(scorecard.score(df_eval)[0])))
    score = max(ESCALA_MIN, min(ESCALA_MAX, score))
    print("score:", score)

    try:
        probabilidad = float(scorecard.predict_proba(df_eval)[0][1])
    except:
        probabilidad = None

    st.session_state.resultado = {
        "score": score,
        "dictamen": resolver_dictamen(score),
        "pd": probabilidad,
        "factores": descomponer(df_eval),
        "datos": dict(data_cliente),
        "plazo": int(plazo),
        "cuota": cuota,
        "carga": carga,
        "momento": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "huella": huella,
    }

# resultados
resultado = st.session_state.get("resultado")

if resultado:
    score = resultado["score"]
    dictamen = resultado["dictamen"]

    st.write("")
    st.markdown(
        """
        <div class="sec an">
          <span class="n">02</span>
          <div>
            <h3>Resolucion del motor</h3>
            <p>Puntuacion, dictamen y descomposicion de los factores que explican el resultado.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if resultado["huella"] != huella:
        st.markdown(
            '<div class="aviso an">Los parametros del legajo fueron modificados con '
            "posterioridad a esta evaluacion. El dictamen que se muestra corresponde a "
            "la corrida anterior; vuelva a ejecutar el motor para actualizarlo.</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.write("")
        izq, der = st.columns([1, 1.28], gap="large")

        with izq:
            render_medidor(score, dictamen)

        with der:
            st.write("")
            st.markdown(
                f"""
                <div class="dict an" style="border-left-color:{color_dictamen(dictamen)}">
                  <div class="lb">Resolucion</div>
                  <div class="vl" style="color:{color_dictamen(dictamen)}">{dictamen}</div>
                  <div class="gl">{DICTAMENES[dictamen]["glosa"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            pd_txt = (
                f"{resultado['pd'] * 100:.2f}%" if resultado["pd"] is not None else "n/d"
            )
            distancia = score - CORTE_APROBACION
            distancia_txt = f"{distancia:+d}"

            st.markdown(
                f"""
                <div class="kpis an" style="border-top:1px solid var(--linea)">
                  <div class="kpi"><div class="k">Prob. de incumplimiento</div>
                    <div class="v">{pd_txt}</div>
                    <div class="u">horizonte del modelo</div></div>
                  <div class="kpi"><div class="k">Distancia al corte</div>
                    <div class="v">{distancia_txt}</div>
                    <div class="u">puntos vs. {CORTE_APROBACION}</div></div>
                  <div class="kpi"><div class="k">Cuota estimada</div>
                    <div class="v">{miles(resultado["cuota"], 0)}</div>
                    <div class="u">a {resultado["plazo"]} meses</div></div>
                  <div class="kpi"><div class="k">Carga / ingreso</div>
                    <div class="v">{resultado["carga"] * 100:.1f}%</div>
                    <div class="u">umbral 35%</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.write("")

    # descomposicion del puntaje
    factores = resultado["factores"]

    st.write("")
    with st.container(border=True):
        st.write("")
        cA, cB = st.columns([1.75, 1], gap="large")

        with cA:
            st.markdown('<div class="rot">Aporte de cada variable al puntaje</div>',
                        unsafe_allow_html=True)

            if factores:
                filas_html = []
                for f in factores:
                    ancho = max(2.0, f["aprovechamiento"] * 100)
                    tramo = f["tramo"]
                    if len(tramo) > 30:
                        tramo = tramo[:29] + "…"
                    filas_html.append(
                        f"<tr>"
                        f'<td class="nm">{f["etiqueta"]}</td>'
                        f'<td class="bn">{tramo}</td>'
                        f'<td class="pt r">{f["puntos"]:.1f}</td>'
                        f'<td><div class="fbar"><span style="--w:{ancho:.1f}%;'
                        f'background:{color_aporte(f["aprovechamiento"])}"></span></div></td>'
                        f'<td class="pt r">{f["aprovechamiento"] * 100:.0f}%</td>'
                        f"</tr>"
                    )

                st.markdown(
                    '<table class="fac an"><thead><tr>'
                    "<th>Variable</th><th>Tramo asignado</th><th class='r'>Puntos</th>"
                    "<th>Aprovechamiento</th><th class='r'>&nbsp;</th>"
                    "</tr></thead><tbody>" + "".join(filas_html) + "</tbody></table>",
                    unsafe_allow_html=True,
                )

                aporte_total = sum(f["puntos"] for f in factores)
                base = score - aporte_total
                st.markdown(
                    f'<div class="nota" style="margin-top:.7rem">'
                    f"Suma de aportes {aporte_total:.1f} + puntaje base {base:.1f} = "
                    f"<b>{score}</b> puntos. El aprovechamiento indica que proporcion "
                    "de los puntos disponibles en cada variable captura el tramo "
                    "asignado al solicitante.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="nota">La descomposicion por variable no esta disponible '
                    "para este artefacto de modelo.</div>",
                    unsafe_allow_html=True,
                )

        with cB:
            st.markdown('<div class="rot">Factores adversos</div>', unsafe_allow_html=True)

            if factores:
                adversos = [f for f in factores if f["aprovechamiento"] < 0.5][:3]
                if adversos:
                    for n, f in enumerate(adversos, start=1):
                        st.markdown(
                            f'<div class="an" style="border-left:2px solid '
                            f'#B8666A;padding:.15rem 0 .15rem .8rem;margin-bottom:.9rem">'
                            f'<div style="font-size:.63rem;letter-spacing:.13em;'
                            f'text-transform:uppercase;color:var(--gris);font-weight:600">'
                            f"Motivo {n:02d}</div>"
                            f'<div style="font-size:.85rem;font-weight:500;margin-top:.15rem">'
                            f'{f["etiqueta"]}</div>'
                            f'<div class="nota" style="margin-top:.2rem">Cede '
                            f'{f["brecha"]:.1f} puntos respecto del maximo de la variable.'
                            f"</div></div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div class="nota">El legajo no presenta variables con '
                        "aprovechamiento inferior al 50% de los puntos disponibles.</div>",
                        unsafe_allow_html=True,
                    )

            st.write("")
            st.markdown('<div class="rot">Constancia</div>', unsafe_allow_html=True)

            operacion_pdf = {
                "Plazo de amortizacion": f"{resultado['plazo']} meses",
                "Cuota estimada": miles(resultado["cuota"], 2),
                "Carga sobre ingreso mensual": f"{resultado['carga'] * 100:.1f}%",
                "Corte de aprobacion del ejercicio": str(CORTE_APROBACION),
                "Corte de revision del ejercicio": str(CORTE_REVISION),
            }

            datos_pdf = {
                k: (
                    VIVIENDA.get(v, v) if k == "person_home_ownership"
                    else DESTINO.get(v, v) if k == "loan_intent"
                    else ("No registra" if v == "N" else "Registra antecedente")
                    if k == "cb_person_default_on_file"
                    else miles(v, 2) if isinstance(v, float)
                    else miles(v) if isinstance(v, int)
                    else v
                )
                for k, v in resultado["datos"].items()
            }

            # esto se rearma en cada rerun, revisar despues
            try:
                pdf_bytes = generar_informe(
                    st.session_state.folio,
                    resultado["momento"],
                    datos_pdf,
                    operacion_pdf,
                    score,
                    dictamen,
                    resultado["pd"],
                    factores,
                )
                st.download_button(
                    label="Descargar informe de demostracion",
                    data=pdf_bytes,
                    file_name=f"Informe_{st.session_state.folio}.pdf",
                    mime="application/pdf",
                )
            except Exception as exc:
                st.markdown(
                    f'<div class="nota">No fue posible generar el informe: {exc}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<div class="nota" style="margin-top:.6rem">Folio '
                f"{st.session_state.folio} &middot; {resultado['momento']}</div>",
                unsafe_allow_html=True,
            )
        st.write("")

# pie
st.markdown(
    f"""
    <div class="pie">
      {PROYECTO} &nbsp;&middot;&nbsp; {SISTEMA} &nbsp;&middot;&nbsp; {VERSION_MODELO}
      &nbsp;&middot;&nbsp; {AUTOR}<br>
      {DISCLAIMER} El puntaje es una estimacion estadistica del riesgo relativo de
      incumplimiento sobre datos historicos, util para ilustrar la mecanica de un
      scorecard; no debe emplearse para evaluar personas reales.
    </div>
    """,
    unsafe_allow_html=True,
)
