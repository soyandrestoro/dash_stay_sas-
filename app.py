import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json

# Configurar página
st.set_page_config(
    page_title="Dashboard Energético",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cargar datos
@st.cache_data
def cargar_datos():
    with open('datos.json', 'r', encoding='utf-8') as f:
        return json.load(f)

datos = cargar_datos()
df = pd.DataFrame(datos['datos_consolidados'])

# Título
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ Dashboard Energético")
    st.markdown("**Análisis de Consumo, Ahorro y Costos** | EPM vs BIA | Oct 2025 - Mar 2026")

# Buscador
st.markdown("---")
col_search = st.columns(1)[0]
with col_search:
    busqueda = st.text_input("🔍 Buscar por número de cuenta", placeholder="Ej: 12975372")

# Filtros
st.markdown("### Filtros")
col1, col2, col3 = st.columns(3)

with col1:
    nivel = st.selectbox(
        "Nivel de Tensión",
        options=[""] + sorted(df['nivel'].unique().tolist()),
        index=0
    )

with col2:
    sedes_disponibles = df['cuenta'].unique().tolist() if not nivel else df[df['nivel'] == nivel]['cuenta'].unique().tolist()
    sede = st.selectbox(
        "Sede",
        options=[""] + sorted(sedes_disponibles),
        index=0
    )

with col3:
    mes = st.selectbox(
        "Mes",
        options=[""] + sorted(df['mes'].unique().tolist()),
        index=0
    )

# Aplicar filtros
filtered = df.copy()

if busqueda:
    filtered = filtered[filtered['cuenta'].astype(str).str.contains(busqueda)]

if nivel:
    filtered = filtered[filtered['nivel'] == nivel]

if sede:
    filtered = filtered[filtered['cuenta'] == sede]

if mes:
    filtered = filtered[filtered['mes'] == mes]

# Mostrar filtros activos
st.markdown("---")
if busqueda or nivel or sede or mes:
    filtros_txt = []
    if busqueda:
        filtros_txt.append(f"**Cuenta:** {busqueda}")
    if nivel:
        filtros_txt.append(f"**Nivel:** {nivel}")
    if sede:
        filtros_txt.append(f"**Sede:** {sede}")
    if mes:
        filtros_txt.append(f"**Mes:** {mes}")
    
    st.info(f"Filtros activos: {' • '.join(filtros_txt)} • **{len(filtered)} registros**")
else:
    st.info(f"Mostrando todos los datos • **{len(filtered)} registros**")

# Métricas
st.markdown("### Métricas")
col1, col2, col3, col4, col5 = st.columns(5)

total_consumo = filtered['consumo'].sum()
total_ahorro = filtered['ahorro_total'].sum()
total_renting = filtered['renting_mensual'].sum()
total_neto = filtered['ahorro_neto'].sum()
promedio_neto = total_neto / len(filtered) if len(filtered) > 0 else 0

with col1:
    st.metric("Consumo Total", f"{total_consumo:,.0f} kWh")

with col2:
    st.metric("Ahorro Total", f"${total_ahorro:,.0f}")

with col3:
    st.metric("Costo Renting", f"${total_renting:,.0f}")

with col4:
    st.metric("Diferencia Neta", f"${total_neto:,.0f}")

with col5:
    st.metric("Promedio/Registro", f"${promedio_neto:,.0f}")

# Gráficos
if len(filtered) > 0:
    st.markdown("---")
    st.markdown("### Visualizaciones")
    
    # Preparar datos por mes
    por_mes = filtered.groupby('mes').agg({
        'ahorro_total': 'sum',
        'renting_mensual': 'sum',
        'ahorro_neto': 'sum',
        'costo_epm': 'sum',
        'costo_bia': 'sum',
        'consumo': 'sum'
    }).reset_index().sort_values('mes')
    
    col1, col2 = st.columns(2)
    
    # Gráfico Ahorro vs Renting
    with col1:
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=por_mes['mes'], y=por_mes['ahorro_total'], name='Ahorro', marker_color='#10b981'))
        fig1.add_trace(go.Bar(x=por_mes['mes'], y=por_mes['renting_mensual'], name='Renting', marker_color='#3b82f6'))
        fig1.update_layout(
            title="Ahorro vs Renting Mensual",
            xaxis_title="Mes",
            yaxis_title="Monto ($)",
            barmode='group',
            hovermode='x unified',
            template='plotly_dark',
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    # Gráfico Diferencia Neta
    with col2:
        colors = ['#10b981' if x > 0 else '#ef4444' for x in por_mes['ahorro_neto']]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=por_mes['mes'], y=por_mes['ahorro_neto'], marker_color=colors, name='Diferencia'))
        fig2.update_layout(
            title="Diferencia Mensual (Ahorro - Renting)",
            xaxis_title="Mes",
            yaxis_title="Monto ($)",
            hovermode='x',
            template='plotly_dark',
            showlegend=False,
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    # Gráfico Costo Comparativo
    with col1:
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=por_mes['mes'], y=por_mes['costo_epm'], name='Costo EPM', marker_color='#ef4444'))
        fig3.add_trace(go.Bar(x=por_mes['mes'], y=por_mes['costo_bia'], name='Costo BIA', marker_color='#10b981'))
        fig3.update_layout(
            title="Costo Comparativo (EPM vs BIA)",
            xaxis_title="Mes",
            yaxis_title="Costo ($)",
            barmode='group',
            hovermode='x unified',
            template='plotly_dark',
            height=400
        )
        st.plotly_chart(fig3, use_container_width=True)
    
    # Gráfico Acumulado
    with col2:
        por_mes['acumulado'] = por_mes['ahorro_neto'].cumsum()
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=por_mes['mes'],
            y=por_mes['acumulado'],
            mode='lines+markers',
            name='Acumulado Neto',
            line=dict(color='#3b82f6', width=3),
            fill='tozeroy'
        ))
        fig4.update_layout(
            title="Acumulado Neto por Período",
            xaxis_title="Mes",
            yaxis_title="Monto Acumulado ($)",
            hovermode='x',
            template='plotly_dark',
            height=400
        )
        st.plotly_chart(fig4, use_container_width=True)
    
    # Tabla detallada
    st.markdown("---")
    st.markdown("### Detalle de Datos")
    
    # Preparar tabla para mostrar
    tabla = filtered[[
        'cuenta', 'direccion', 'nivel', 'mes', 'consumo',
        'ahorro_total', 'renting_mensual', 'ahorro_neto', 'costo_equipos'
    ]].copy()
    
    tabla.columns = ['Cuenta', 'Dirección', 'Nivel', 'Mes', 'Consumo (kWh)', 
                     'Ahorro ($)', 'Renting ($)', 'Diferencia ($)', 'Equipos ($)']
    
    # Formatear números
    for col in ['Consumo (kWh)', 'Ahorro ($)', 'Renting ($)', 'Diferencia ($)', 'Equipos ($)']:
        tabla[col] = tabla[col].apply(lambda x: f"${x:,.0f}" if col != 'Consumo (kWh)' else f"{x:,.0f}")
    
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    
    # Descargar datos
    csv = tabla.to_csv(index=False)
    st.download_button(
        label="📥 Descargar como CSV",
        data=csv,
        file_name="dashboard_energetico.csv",
        mime="text/csv"
    )

else:
    st.warning("No hay registros que coincidan con los filtros seleccionados")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; font-size: 0.9em;'>
    Dashboard Energético • Oct 2025 - Mar 2026 • 46 Sedes • 276 Registros
</div>
""", unsafe_allow_html=True)
