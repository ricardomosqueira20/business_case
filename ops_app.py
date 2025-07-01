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
# -------------------------
# MÓDULO 2: CPA, ROI y CTR por Canal + Producto
# -------------------------
import plotly.graph_objects as go

def graficar_metrica_canal_producto(df, columna_metric, nombre_metric, objetivo=None):
    st.subheader(f"📈 {nombre_metric} diario por Canal + Producto")

    # Crear columna combinada
    df['Canal_Producto'] = df['Canal'] + " | " + df['Producto']
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Filtro por producto
    opciones = sorted(df['Producto'].unique())
    productos_seleccionados = st.multiselect(
        f"Selecciona productos a mostrar para {nombre_metric}",
        opciones,
        default=opciones,
        key=f"{nombre_metric}_selector"
    )

    df_filtrado = df[df['Producto'].isin(productos_seleccionados)]

    # Promedio por Canal + Producto
    df_cat = df_filtrado.groupby(['Fecha', 'Canal_Producto'])[columna_metric].mean().reset_index()
    df_cat['Tipo'] = "Canal + Producto"

    # Promedio general
    df_gen = df_filtrado.groupby('Fecha')[columna_metric].mean().reset_index()
    df_gen['Canal_Producto'] = "Promedio General"
    df_gen['Tipo'] = "Promedio General"

    # Objetivo
    if objetivo is not None:
        df_obj = df_gen[['Fecha']].copy()
        df_obj[columna_metric] = objetivo
        df_obj['Canal_Producto'] = f"Objetivo ({objetivo})"
        df_obj['Tipo'] = "Objetivo"
        df_plot = pd.concat([df_cat, df_gen, df_obj], ignore_index=True)
    else:
        df_plot = pd.concat([df_cat, df_gen], ignore_index=True)

    # Gráfico combinado
    fig = px.bar(
        df_plot[df_plot['Tipo'] == 'Promedio General'],
        x="Fecha",
        y=columna_metric,
        color="Canal_Producto",
        barmode="group",
        opacity=0.6
    )

    # Añadir barra de objetivo
    if objetivo is not None:
        fig.add_bar(
            x=df_obj['Fecha'],
            y=df_obj[columna_metric],
            name=f"Objetivo ({objetivo})",
            marker_color='red',
            opacity=0.5
        )

    # Añadir líneas para Canal + Producto
    for canal_prod in df_plot[df_plot['Tipo'] == 'Canal + Producto']['Canal_Producto'].unique():
        subset = df_plot[(df_plot['Tipo'] == 'Canal + Producto') & (df_plot['Canal_Producto'] == canal_prod)]
        fig.add_scatter(
            x=subset['Fecha'],
            y=subset[columna_metric],
            mode='lines+markers',
            name=canal_prod
        )

    fig.update_layout(
        title=f"{nombre_metric} diario por Canal + Producto vs Promedio General",
        xaxis_title="Fecha",
        yaxis_title=nombre_metric
    )

    st.plotly_chart(fig, use_container_width=True)

def mostrar_modulo_cpa_roi(df):
    st.header("📊 CPA, ROI y CTR diario por Canal + Producto")

    graficar_metrica_canal_producto(df, 'CPA', 'CPA', objetivo=120)
    graficar_metrica_canal_producto(df, 'ROI', 'ROI', objetivo=1.5)
    graficar_metrica_canal_producto(df, 'CTR', 'CTR', objetivo=0.05)



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




