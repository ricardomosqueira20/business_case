# ops_app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# -------------------------
# CARGA DE DATOS DESDE GOOGLE SHEETS (usando st.secrets["gcp"])
# -------------------------

@st.cache_data(ttl=0)
def cargar_datos():
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.readonly"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp"], scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open("PRUEBA DATA OPS -  Analysis")
    sheet = spreadsheet.worksheet("PRUEBA DATA OPS")
    data = sheet.get_all_records()

    df = pd.DataFrame(data)
    df['Fecha'] = pd.to_datetime(df['Fecha'], format="%d/%m/%Y")
    return df

# -------------------------
# CLASIFICACIÓN DE LEADS
# -------------------------

def clasificar_lead(row):
    if row['Estatus'] == "Completado" and row['Motivo_Rechazo'] == "N/A":
        return "Exitoso"
    elif row['Estatus'] == "En progreso" and row['Motivo_Rechazo'] == "N/A":
        return "En progreso"
    else:
        return "Rechazado"

# -------------------------
# MÓDULO 1: LEADS DIARIOS POR ESTATUS
# -------------------------

def mostrar_modulo_leads_diarios(df):
    st.header("📊 Evolución diaria de Leads por Estatus")

    df['lead_status'] = df.apply(clasificar_lead, axis=1)
    df['Mes'] = df['Fecha'].dt.strftime('%B %Y')

    meses_disponibles = sorted(df['Mes'].unique())
    mes_seleccionado = st.selectbox("Selecciona el mes a visualizar:", meses_disponibles)

    df_mes = df[df['Mes'] == mes_seleccionado]

    total_exitosos = df_mes[df_mes['lead_status'] == 'Exitoso']['Leads_Obtenidos'].sum()
    total_rechazados = df_mes[df_mes['lead_status'] == 'Rechazado']['Leads_Obtenidos'].sum()

    col1, col2 = st.columns(2)
    col1.metric("✅ Leads exitosos acumulados", f"{total_exitosos:,}")
    col2.metric("❌ Leads rechazados acumulados", f"{total_rechazados:,}")

    leads_diarios = df_mes.groupby(['Fecha', 'lead_status'])['Leads_Obtenidos'].sum().reset_index()

    fig = px.line(
        leads_diarios,
        x='Fecha',
        y='Leads_Obtenidos',
        color='lead_status',
        title=f'Leads diarios por estatus - {mes_seleccionado}',
        labels={'Leads_Obtenidos': 'Total de Leads', 'lead_status': 'Estatus del Lead'}
    )
    st.plotly_chart(fig)

# -------------------------
# MÓDULO 2: CPA y ROI por Canal + Producto
# -------------------------

import plotly.graph_objects as go

def graficar_metrica_canal_producto(df, columna_metric, nombre_metric, objetivo, key_suffix):
    st.subheader(f"📈 {nombre_metric} diario por Canal + Producto")

    df['Canal_Producto'] = df['Canal'] + " | " + df['Producto']
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Filtro por producto con clave única para evitar conflicto de widgets
    opciones = sorted(df['Producto'].unique())
    productos_seleccionados = st.multiselect(
        "Selecciona productos a mostrar",
        opciones,
        default=opciones,
        key=f"{columna_metric}_{key_suffix}"
    )

    df_filtrado = df[df['Producto'].isin(productos_seleccionados)]

    # Promedio por Canal + Producto
    df_cat = df_filtrado.groupby(['Fecha', 'Canal_Producto'])[columna_metric].mean().reset_index()

    # Promedio general
    df_gen = df_filtrado.groupby('Fecha')[columna_metric].mean().reset_index()
    df_gen.rename(columns={columna_metric: "Promedio General"}, inplace=True)

    # Inicializar figura
    fig = go.Figure()

    # Barras: promedio general diario
    fig.add_trace(go.Bar(
        x=df_gen["Fecha"],
        y=df_gen["Promedio General"],
        name="Promedio General",
        marker_color="lightgray",
        opacity=0.6
    ))

    # Líneas: Canal + Producto
    for cp in df_cat["Canal_Producto"].unique():
        df_cp = df_cat[df_cat["Canal_Producto"] == cp]
        fig.add_trace(go.Scatter(
            x=df_cp["Fecha"],
            y=df_cp[columna_metric],
            mode="lines+markers",
            name=cp
        ))

    # Línea horizontal de objetivo
    fig.add_trace(go.Scatter(
        x=df_gen["Fecha"],
        y=[objetivo] * len(df_gen),
        mode="lines",
        name=f"Objetivo {nombre_metric}",
        line=dict(color="red", dash="dash")
    ))

    fig.update_layout(
        title=f"{nombre_metric} diario por Canal + Producto",
        xaxis_title="Fecha",
        yaxis_title=nombre_metric,
        barmode="overlay",
        template="plotly_white",
        height=450
    )

    st.plotly_chart(fig, use_container_width=True)

def mostrar_modulo_cpa_roi(df):
    st.header("📊 CPA, ROI y CTR diario por Canal + Producto")
    graficar_metrica_canal_producto(df, 'CPA', 'CPA', objetivo=120, key_suffix="cpa")
    graficar_metrica_canal_producto(df, 'ROI', 'ROI', objetivo=1.5, key_suffix="roi")
    graficar_metrica_canal_producto(df, 'CTR', 'CTR', objetivo=0.12, key_suffix="ctr")


# -------------------------
# APP STREAMLIT
# -------------------------

def main():
    st.set_page_config(page_title="Rocket Dashboard", layout="wide")
    st.title("🚀 Ops performance | Business Case")

    try:
        df = cargar_datos()
        mostrar_modulo_leads_diarios(df)
        mostrar_modulo_cpa_roi(df)
    except Exception as e:
        st.error("❌ Error al cargar los datos. Verifica los nombres del archivo/hoja o los permisos del service account.")
        st.exception(e)

if __name__ == "__main__":
    main()




