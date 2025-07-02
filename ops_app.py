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
# MÓDULO 0: ALERTAS POR CANAL
# -------------------------

def mostrar_alertas_por_canal(df):
    st.header("🚨 Alertas de desempeño por Canal (promedio del periodo)")

    objetivos = {
        'CPA': 120,     # valor objetivo máximo
        'ROI': 1.5,     # valor objetivo mínimo
        'CTR': 0.05     # valor objetivo mínimo
    }

    # Agrupar por canal
    resumen = df.groupby('Canal')[['CPA', 'ROI', 'CTR']].mean().reset_index()

    # Clasificación con semáforo
    def clasificar(valor, metrica):
        if metrica == 'CPA':
            return '🟢' if valor <= objetivos['CPA'] else '🔴'
        else:  # ROI y CTR
            return '🟢' if valor >= objetivos[metrica] else '🔴'

    resumen['CPA_Alerta'] = resumen['CPA'].apply(lambda x: clasificar(x, 'CPA'))
    resumen['ROI_Alerta'] = resumen['ROI'].apply(lambda x: clasificar(x, 'ROI'))
    resumen['CTR_Alerta'] = resumen['CTR'].apply(lambda x: clasificar(x, 'CTR'))

    # Reordenar columnas
    resumen = resumen[['Canal', 'CPA', 'CPA_Alerta', 'ROI', 'ROI_Alerta', 'CTR', 'CTR_Alerta']]

    # Renombrar
    resumen.columns = [
        "Canal", "CPA Promedio", "Alerta CPA",
        "ROI Promedio", "Alerta ROI",
        "CTR Promedio", "Alerta CTR"
    ]

    st.dataframe(resumen.style.format({
        "CPA Promedio": "{:,.2f}",
        "ROI Promedio": "{:,.2f}",
        "CTR Promedio": "{:.2%}"
    }))

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

    # Promedio general
    df_gen = df_filtrado.groupby('Fecha')[columna_metric].mean().reset_index()
    df_gen['Canal_Producto'] = "Promedio General"

    # Objetivo
    if objetivo is not None:
        df_obj = df_gen[['Fecha']].copy()
        df_obj[columna_metric] = objetivo
        df_obj['Canal_Producto'] = f"Objetivo ({objetivo})"
    else:
        df_obj = pd.DataFrame()

    # Crear figura
    fig = go.Figure()

    # Barras del promedio general
    fig.add_trace(go.Bar(
        x=df_gen['Fecha'],
        y=df_gen[columna_metric],
        name="Promedio General",
        marker_color='blue',
        opacity=0.6
    ))

    # Barras del objetivo
    if not df_obj.empty:
        fig.add_trace(go.Bar(
            x=df_obj['Fecha'],
            y=df_obj[columna_metric],
            name=f"Objetivo ({objetivo})",
            marker_color='red',
            opacity=0.4
        ))

    # Líneas para cada canal-producto
    for canal_prod in df_cat['Canal_Producto'].unique():
        subset = df_cat[df_cat['Canal_Producto'] == canal_prod]
        fig.add_trace(go.Scatter(
            x=subset['Fecha'],
            y=subset[columna_metric],
            mode='lines+markers',
            name=canal_prod
        ))

    fig.update_layout(
        title=f"{nombre_metric} diario por Canal + Producto vs Promedio General",
        xaxis_title="Fecha",
        yaxis_title=nombre_metric,
        barmode='group'
    )

    st.plotly_chart(fig, use_container_width=True)

def mostrar_modulo_cpa_roi(df):
    st.header("📊 CPA, ROI y CTR diario por Canal + Producto")

    graficar_metrica_canal_producto(df, 'CPA', 'CPA', objetivo=120)
    graficar_metrica_canal_producto(df, 'ROI', 'ROI', objetivo=1.5)
    graficar_metrica_canal_producto(df, 'CTR', 'CTR', objetivo=0.05)

###Modulo 3

def mostrar_modulo_rolling_cpa_roi_por_canal(df):
    st.header("📊 Tendencia Rolling 7D - CPA y ROI por Canal")

    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Filtro de canal
    canales = sorted(df['Canal'].unique())
    canales_seleccionados = st.multiselect(
        "Selecciona canales a mostrar (Rolling 7D)", canales, default=canales, key="rolling_canal_selector"
    )
    df = df[df['Canal'].isin(canales_seleccionados)]

    # Agrupación diaria por Canal
    df_grouped = df.groupby(['Fecha', 'Canal'])[['CPA', 'ROI']].mean().reset_index()
    df_grouped = df_grouped.sort_values(['Canal', 'Fecha'])

    # Rolling 7D
    df_grouped['CPA_rolling_7D'] = df_grouped.groupby('Canal')['CPA'].transform(
        lambda x: x.rolling(window=7, min_periods=1).mean()
    )
    df_grouped['ROI_rolling_7D'] = df_grouped.groupby('Canal')['ROI'].transform(
        lambda x: x.rolling(window=7, min_periods=1).mean()
    )

    # CPA Rolling
    fig_cpa = px.line(
        df_grouped,
        x="Fecha",
        y="CPA_rolling_7D",
        color="Canal",
        title="CPA Rolling 7D por Canal",
        labels={"CPA_rolling_7D": "CPA (7D Promedio)"}
    )
    fig_cpa.add_hline(y=120, line_dash="dash", line_color="red", annotation_text="Objetivo CPA: 120", annotation_position="top left")
    st.plotly_chart(fig_cpa, use_container_width=True)

    # ROI Rolling
    fig_roi = px.line(
        df_grouped,
        x="Fecha",
        y="ROI_rolling_7D",
        color="Canal",
        title="ROI Rolling 7D por Canal",
        labels={"ROI_rolling_7D": "ROI (7D Promedio)"}
    )
    fig_roi.add_hline(y=1.5, line_dash="dash", line_color="green", annotation_text="Objetivo ROI: 1.5", annotation_position="top left")
    st.plotly_chart(fig_roi, use_container_width=True)

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
        mostrar_modulo_rolling_cpa_roi_por_canal(df)
    except Exception as e:
        st.error("❌ Error al cargar los datos. Verifica los nombres del archivo/hoja o los permisos del service account.")
        st.exception(e)

if __name__ == "__main__":
    main()




