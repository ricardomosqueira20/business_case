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

    # Abrir el archivo y hoja de Google Sheets
    spreadsheet = client.open("PRUEBA DATA OPS -  Analysis")  # nombre exacto del archivo
    sheet = spreadsheet.worksheet("PRUEBA DATA OPS")          # nombre exacto de la hoja
    data = sheet.get_all_records()

    # Convertir a DataFrame
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

    # Clasificación de leads
    df['lead_status'] = df.apply(clasificar_lead, axis=1)
    df['Mes'] = df['Fecha'].dt.strftime('%B %Y')

    # Selector de mes
    meses_disponibles = sorted(df['Mes'].unique())
    mes_seleccionado = st.selectbox("Selecciona el mes a visualizar:", meses_disponibles)

    # Filtro por mes
    df_mes = df[df['Mes'] == mes_seleccionado]

    # KPIs acumulados del mes
    total_exitosos = df_mes[df_mes['lead_status'] == 'Exitoso']['Leads_Obtenidos'].sum()
    total_rechazados = df_mes[df_mes['lead_status'] == 'Rechazado']['Leads_Obtenidos'].sum()

    col1, col2 = st.columns(2)
    col1.metric("✅ Leads exitosos acumulados", f"{total_exitosos:,}")
    col2.metric("❌ Leads rechazados acumulados", f"{total_rechazados:,}")


    # Agrupación diaria
    leads_diarios = df_mes.groupby(['Fecha', 'lead_status'])['Leads_Obtenidos'].sum().reset_index()

    # Gráfico interactivo
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

def graficar_metrica_canal_producto(df, columna_metric, nombre_metric):
    st.subheader(f"📈 {nombre_metric} diario por Canal + Producto")

    # Crear columna combinada
    df['Canal_Producto'] = df['Canal'] + " | " + df['Producto']
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Filtro por producto
    opciones = sorted(df['Producto'].unique())
    productos_seleccionados = st.multiselect("Selecciona productos a mostrar", opciones, default=opciones)

    df_filtrado = df[df['Producto'].isin(productos_seleccionados)]

    # Promedio por Canal + Producto
    df_cat = df_filtrado.groupby(['Fecha', 'Canal_Producto'])[columna_metric].mean().reset_index()

    # Promedio general
    df_gen = df_filtrado.groupby('Fecha')[columna_metric].mean().reset_index()
    df_gen['Canal_Producto'] = "Promedio General"

    df_plot = pd.concat([df_cat, df_gen], ignore_index=True)

    # Gráfica
    fig = px.line(
        df_plot,
        x='Fecha',
        y=columna_metric,
        color='Canal_Producto',
        title=f"{nombre_metric} diario por Canal + Producto",
        labels={columna_metric: nombre_metric}
    )

    st.plotly_chart(fig)

def mostrar_modulo_cpa_roi(df):
    st.header("📊 CPA y ROI diario por Canal + Producto")
    graficar_metrica_canal_producto(df, 'CPA', 'CPA')
    graficar_metrica_canal_producto(df, 'ROI', 'ROI')

# -------------------------
# APP STREAMLIT
# -------------------------

def main():
    st.set_page_config(page_title="Rocket Dashboard", layout="wide")
    st.title("🚀 Ops performance | Business Case")

    # Carga de datos
    try:
        df = cargar_datos()
        mostrar_modulo_leads_diarios(df)
        mostrar_modulo_cpa_roi(df)
    except Exception as e:
        st.error("❌ Error al cargar los datos. Verifica los nombres del archivo/hoja o los permisos del service account.")
        st.exception(e)

if __name__ == "__main__":
    main()



