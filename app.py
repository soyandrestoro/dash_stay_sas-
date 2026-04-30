import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

st.set_page_config(
    page_title="Dashboard Energético",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Constantes ───────────────────────────────────────────────────────────────

MESES_COLS = ['Octubre', 'Noviembre', 'Diciembre', 'Enero', 'Febrero', 'Marzo', 'Abril']
MESES_KEYS = ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04']
MESES_TARIFA = {
    '2025-10': 'octubre 1, 2025',
    '2025-11': 'noviembre 1, 2025',
    '2025-12': 'diciembre 1, 2025',
    '2026-01': 'enero 1, 2026',
    '2026-02': 'febrero 1, 2026',
    '2026-03': 'marzo 1, 2026',
    '2026-04': 'abril 1, 2026',
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def limpiar_col(c):
    # UTF-8 BOM leído como latin1 produce los 3 chars ï»¿ (ï»¿)
    return c.replace('ï»¿', '').replace('﻿', '').strip()

def limpiar_dinero(v):
    if pd.isna(v):
        return 0.0
    if isinstance(v, str):
        return float(v.replace('$', '').replace(',', '').strip())
    return float(v)

def limpiar_num(v):
    if pd.isna(v):
        return 0.0
    if isinstance(v, str):
        return float(v.replace(',', '').strip())
    return float(v)

# ── Carga de datos ────────────────────────────────────────────────────────────

ARCHIVOS_CSV = [
    'Nivel de tensión y propiedad de activos 1 or.csv',
    'Nivel de tensión y propiedad de activos 1 usuario.csv',
    'Nivel de tensión y propiedad de activos 2 usuario .csv',
    'Tarifas nivel de tension 1 or.csv',
    'Tarifas nivel de tension 1 usuario.csv',
    'Tarifas nivel de tension 2 usuario.csv',
]

def mtimes_csv():
    return tuple(os.path.getmtime(f) for f in ARCHIVOS_CSV)

@st.cache_data
def cargar_datos(mtimes):
    # Tarifas
    cfg_tarifas = [
        ('nivel_1_operador', 'Tarifas nivel de tension 1 or.csv'),
        ('nivel_1_user',     'Tarifas nivel de tension 1 usuario.csv'),
        ('nivel_2_operator', 'Tarifas nivel de tension 2 usuario.csv'),
    ]
    tarifas = {}
    for nivel, fname in cfg_tarifas:
        # Tarifas: Latin-1 con BOM — limpiar_col elimina ï»¿
        t = pd.read_csv(fname, sep=';', encoding='latin1')
        t.columns = [limpiar_col(c) for c in t.columns]
        t['Mes'] = t['Mes'].str.strip()
        tarifas[nivel] = {
            row['Mes']: (float(row['Tarifa EPM']), float(row['Tarifa BIA']))
            for _, row in t.iterrows()
        }

    # Consumos
    cfg_consumos = [
        ('Nivel de tensión y propiedad de activos 1 or.csv',       'nivel_1_operador', 'Nivel 1 - Operador'),
        ('Nivel de tensión y propiedad de activos 1 usuario.csv',  'nivel_1_user',     'Nivel 1 - Usuario'),
        ('Nivel de tensión y propiedad de activos 2 usuario .csv', 'nivel_2_operator', 'Nivel 2 - Usuario'),
    ]

    registros = []
    for fname, nivel_key, nivel_label in cfg_consumos:
        # Consumos: UTF-8 con BOM — utf-8-sig lo elimina automáticamente
        df = pd.read_csv(fname, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
        df.columns = [c.strip() for c in df.columns]

        id_col = (
            'Número de cuenta'      if 'Número de cuenta'      in df.columns else
            'Dirección de frontera' if 'Dirección de frontera'  in df.columns else
            'Ciudad'                if 'Ciudad'                 in df.columns else
            None
        )

        for _, row in df.iterrows():
            cuenta    = str(row[id_col]) if id_col else nivel_label
            direccion = str(row['Dirección de frontera']) if 'Dirección de frontera' in df.columns else (
                        str(row['Ciudad']) if 'Ciudad' in df.columns else '—')
            costo_eq  = limpiar_dinero(row.get('Costo equipos', 0))
            renting   = limpiar_dinero(row.get('Total Renting', 0))

            for mes_col, mes_key in zip(MESES_COLS, MESES_KEYS):
                col = next((c for c in df.columns if c == mes_col), None)
                if col is None:
                    continue
                consumo = limpiar_num(row[col])
                if consumo <= 0:
                    continue

                t = tarifas[nivel_key].get(MESES_TARIFA[mes_key])
                if t is None:
                    continue
                tarifa_epm, tarifa_bia = t

                costo_epm    = consumo * tarifa_epm
                costo_bia    = consumo * tarifa_bia
                ahorro_bruto = costo_epm - costo_bia
                ahorro_neto  = ahorro_bruto - renting

                registros.append({
                    'cuenta':          cuenta,
                    'direccion':       direccion,
                    'nivel':           nivel_label,
                    'mes':             mes_key,
                    'consumo':         consumo,
                    'tarifa_epm':      tarifa_epm,
                    'tarifa_bia':      tarifa_bia,
                    'costo_epm':       costo_epm,
                    'costo_bia':       costo_bia,
                    'ahorro_bruto':    ahorro_bruto,
                    'costo_equipos':   costo_eq,
                    'renting_mensual': renting,
                    'ahorro_neto':     ahorro_neto,
                })

    return pd.DataFrame(registros)

df = cargar_datos(mtimes_csv())

# ── Encabezado ────────────────────────────────────────────────────────────────

st.title("⚡ Dashboard Energético")
st.markdown("**Análisis de Consumo, Ahorro y Costos** | EPM vs BIA | Oct 2025 – Abr 2026")
st.markdown("---")

# ── Búsqueda y filtros ────────────────────────────────────────────────────────

# Inicializar estado de seguimiento de nivel
if 'ultimo_nivel' not in st.session_state:
    st.session_state.ultimo_nivel = ""

def reiniciar_filtros():
    for key in ('busqueda_widget', 'nivel_widget', 'sede_widget', 'mes_widget'):
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.ultimo_nivel = ""

col_titulo, col_btn = st.columns([6, 1])
with col_titulo:
    st.markdown("### Filtros")
with col_btn:
    st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
    st.button("✕ Limpiar", on_click=reiniciar_filtros, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

busqueda = st.text_input("🔍 Buscar por número de cuenta o dirección",
                         placeholder="Ej: 12975372", key="busqueda_widget")

c1, c2, c3 = st.columns(3)

with c1:
    nivel = st.selectbox("Nivel de Tensión",
                         [""] + sorted(df['nivel'].unique().tolist()),
                         index=0, key="nivel_widget")

# Si el nivel cambió, borrar el widget de sede para que vuelva a índice 0
if nivel != st.session_state.ultimo_nivel:
    st.session_state.ultimo_nivel = nivel
    if 'sede_widget' in st.session_state:
        del st.session_state['sede_widget']

# Calcular opciones de sede según el nivel activo
pool = df if not nivel else df[df['nivel'] == nivel]
cuentas_disp = [""] + sorted(pool['cuenta'].astype(str).unique().tolist())

with c2:
    sede = st.selectbox("Sede / Cuenta", cuentas_disp, index=0, key="sede_widget")

with c3:
    mes = st.selectbox("Mes", [""] + sorted(df['mes'].unique().tolist()),
                       index=0, key="mes_widget")

# Aplicar filtros
filtrado = df.copy()
if busqueda:
    mask = (filtrado['cuenta'].astype(str).str.contains(busqueda, case=False) |
            filtrado['direccion'].astype(str).str.contains(busqueda, case=False))
    filtrado = filtrado[mask]
if nivel:
    filtrado = filtrado[filtrado['nivel'] == nivel]
if sede:
    filtrado = filtrado[filtrado['cuenta'].astype(str) == sede]
if mes:
    filtrado = filtrado[filtrado['mes'] == mes]

# Banner de estado
st.markdown("---")
partes = []
if busqueda: partes.append(f"**Búsqueda:** {busqueda}")
if nivel:    partes.append(f"**Nivel:** {nivel}")
if sede:     partes.append(f"**Sede:** {sede}")
if mes:      partes.append(f"**Mes:** {mes}")
prefijo = "Filtros activos: " + " • ".join(partes) if partes else "Mostrando todos los datos"
st.info(f"{prefijo} • **{len(filtrado)} registros**")

# ── Tarjetas ──────────────────────────────────────────────────────────────────

total_consumo  = filtrado['consumo'].sum()
total_epm      = filtrado['costo_epm'].sum()
total_bia      = filtrado['costo_bia'].sum()
total_renting  = filtrado['renting_mensual'].sum()
total_bia_rent = total_bia + total_renting
ahorro_real    = total_epm - total_bia_rent   # positivo = ahorra, negativo = más caro con BIA

n_sedes  = filtrado['cuenta'].nunique()
contexto = sede if sede else (nivel if nivel else "Todas las sedes")

st.markdown("### Resumen")
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Consumo",
    f"{total_consumo:,.0f} kWh",
    help="Energía consumida en el período seleccionado"
)
c2.metric(
    "Valor con EPM",
    f"${total_epm:,.0f}",
    help="Costo total pagando tarifa EPM"
)
c3.metric(
    "Valor con BIA",
    f"${total_bia:,.0f}",
    help="Costo de energía pagando tarifa BIA (sin renting)"
)
c4.metric(
    "BIA + Renting",
    f"${total_bia_rent:,.0f}",
    delta=f"-${total_renting:,.0f} renting",
    delta_color="off",
    help="Costo total BIA incluyendo renting mensual de equipos"
)

ahorro_tarifa = total_epm - total_bia   # ahorro solo en tarifa, sin renting

if ahorro_tarifa > 0:
    delta_txt   = f"${ahorro_tarifa:,.0f} sin renting"
    delta_color = "normal"                # verde
else:
    delta_txt   = "Sin ahorro en tarifa"
    delta_color = "off"                   # gris, nunca rojo

c5.metric(
    "Ahorro vs EPM",
    f"${ahorro_real:,.0f}",
    delta=delta_txt,
    delta_color=delta_color,
    help="Valor principal: EPM − (BIA + Renting). Abajo: ahorro solo en tarifa de energía sin incluir renting"
)

# ── Gráficos ──────────────────────────────────────────────────────────────────

if len(filtrado) > 0:
    st.markdown("---")
    st.markdown("### Visualizaciones")

    # ── Tarifas EPM vs BIA (arriba, ancho completo) ───────────────────────────

    st.markdown("### Comportamiento de Tarifas ($/kWh)")

    tarifas_mes = (
        filtrado
        .groupby(['mes', 'nivel'], as_index=False)
        .agg(tarifa_epm=('tarifa_epm', 'first'), tarifa_bia=('tarifa_bia', 'first'))
        .sort_values(['nivel', 'mes'])
    )

    COLORES_EPM = {
        'Nivel 1 - Operador': '#ef4444',
        'Nivel 1 - Usuario':  '#f97316',
        'Nivel 2 - Usuario':  '#f59e0b',
    }
    COLORES_BIA = {
        'Nivel 1 - Operador': '#3b82f6',
        'Nivel 1 - Usuario':  '#10b981',
        'Nivel 2 - Usuario':  '#a855f7',
    }

    fig_tarifas = go.Figure()
    for niv in sorted(tarifas_mes['nivel'].unique()):
        sub = tarifas_mes[tarifas_mes['nivel'] == niv]
        fig_tarifas.add_trace(go.Scatter(
            x=sub['mes'], y=sub['tarifa_epm'],
            mode='lines+markers',
            name=f'EPM – {niv}',
            line=dict(color=COLORES_EPM.get(niv, '#ef4444'), width=2, dash='solid'),
            marker=dict(size=8),
        ))
        fig_tarifas.add_trace(go.Scatter(
            x=sub['mes'], y=sub['tarifa_bia'],
            mode='lines+markers',
            name=f'BIA – {niv}',
            line=dict(color=COLORES_BIA.get(niv, '#10b981'), width=2, dash='dot'),
            marker=dict(size=8, symbol='diamond'),
        ))

    fig_tarifas.update_layout(
        xaxis_title="Mes",
        yaxis_title="Tarifa ($/kWh)",
        hovermode='x unified',
        template='plotly_dark',
        height=420,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    st.plotly_chart(fig_tarifas, use_container_width=True)

    por_mes = (
        filtrado
        .groupby('mes', as_index=False)
        .agg(
            ahorro_bruto=('ahorro_bruto', 'sum'),
            renting_mensual=('renting_mensual', 'sum'),
            ahorro_neto=('ahorro_neto', 'sum'),
            costo_epm=('costo_epm', 'sum'),
            costo_bia=('costo_bia', 'sum'),
            consumo=('consumo', 'sum'),
        )
        .sort_values('mes')
    )

    # ── 1. Waterfall mensual ──────────────────────────────────────────────────
    meses_wf  = list(por_mes['mes']) + ['Total']
    valores_wf = list(por_mes['ahorro_neto'])
    medidas_wf = ['relative'] * len(por_mes) + ['total']
    textos_wf  = [f"${v:,.0f}" for v in por_mes['ahorro_neto']] + [f"${sum(por_mes['ahorro_neto']):,.0f}"]

    fig_wf = go.Figure(go.Waterfall(
        orientation='v',
        measure=medidas_wf,
        x=meses_wf,
        y=valores_wf + [0],
        text=textos_wf,
        textposition='outside',
        textfont=dict(size=11),
        connector=dict(line=dict(color='#475569', width=1)),
        increasing=dict(marker=dict(color='#10b981')),
        decreasing=dict(marker=dict(color='#94a3b8')),
        totals=dict(marker=dict(color='#3b82f6')),
    ))
    fig_wf.update_layout(
        title='Flujo de Ahorro Neto Mensual (Ahorro tarifa − Renting)',
        xaxis_title='Mes', yaxis_title='Monto ($)',
        template='plotly_dark', height=420,
        showlegend=False,
    )
    st.plotly_chart(fig_wf, use_container_width=True)

    # ── 2. Scatter Consumo vs Ahorro por sede  +  3. Ranking de sedes ────────
    por_sede = (
        filtrado
        .groupby('cuenta', as_index=False)
        .agg(
            consumo    =('consumo',    'sum'),
            ahorro_neto=('ahorro_neto','sum'),
            nivel      =('nivel',      'first'),
        )
    )

    c1, c2 = st.columns(2)

    with c1:
        colores_scatter = ['#10b981' if v > 0 else '#94a3b8' for v in por_sede['ahorro_neto']]
        fig_sc = go.Figure(go.Scatter(
            x=por_sede['consumo'],
            y=por_sede['ahorro_neto'],
            mode='markers',
            marker=dict(size=10, color=colores_scatter, line=dict(width=1, color='#1e293b')),
            text=por_sede['cuenta'].astype(str) + '<br>' + por_sede['nivel'],
            hovertemplate='<b>%{text}</b><br>Consumo: %{x:,.0f} kWh<br>Ahorro neto: $%{y:,.0f}<extra></extra>',
        ))
        fig_sc.add_hline(y=0, line=dict(color='#475569', dash='dash', width=1))
        fig_sc.update_layout(
            title='Consumo vs Ahorro Neto por Sede',
            xaxis_title='Consumo total (kWh)',
            yaxis_title='Ahorro neto ($)',
            template='plotly_dark', height=420,
        )
        st.plotly_chart(fig_sc, use_container_width=True)

    with c2:
        ranking = por_sede.sort_values('ahorro_neto', ascending=True)
        col_rank = ['#10b981' if v > 0 else '#94a3b8' for v in ranking['ahorro_neto']]
        fig_rk = go.Figure(go.Bar(
            x=ranking['ahorro_neto'],
            y=ranking['cuenta'].astype(str),
            orientation='h',
            marker_color=col_rank,
            text=[f"${v:,.0f}" for v in ranking['ahorro_neto']],
            textposition='outside',
            textfont=dict(size=10),
        ))
        fig_rk.update_layout(
            title='Ranking de Sedes por Ahorro Neto',
            xaxis_title='Ahorro neto ($)',
            yaxis_title='',
            template='plotly_dark',
            height=max(420, len(ranking) * 22 + 80),
            margin=dict(l=120),
        )
        st.plotly_chart(fig_rk, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure([
            go.Bar(x=por_mes['mes'], y=por_mes['costo_epm'], name='Costo EPM', marker_color='#ef4444'),
            go.Bar(x=por_mes['mes'], y=por_mes['costo_bia'], name='Costo BIA', marker_color='#10b981'),
        ])
        fig.update_layout(title="Costo Comparativo (EPM vs BIA)",
                          xaxis_title="Mes", yaxis_title="Costo ($)",
                          barmode='group', hovermode='x unified',
                          template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        por_mes['acumulado'] = por_mes['ahorro_neto'].cumsum()
        fig = go.Figure([
            go.Scatter(
                x=por_mes['mes'], y=por_mes['acumulado'],
                mode='lines+markers', name='Acumulado Neto',
                line=dict(color='#3b82f6', width=3), fill='tozeroy'
            )
        ])
        fig.update_layout(title="Acumulado Neto por Período",
                          xaxis_title="Mes", yaxis_title="Monto Acumulado ($)",
                          hovermode='x', template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Tabla detallada ───────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### Detalle de Datos")

    tabla = filtrado[[
        'cuenta', 'direccion', 'nivel', 'mes', 'consumo',
        'ahorro_bruto', 'renting_mensual', 'ahorro_neto', 'costo_equipos'
    ]].copy()
    tabla.columns = ['Cuenta', 'Dirección', 'Nivel', 'Mes', 'Consumo (kWh)',
                     'Ahorro ($)', 'Renting ($)', 'Diferencia ($)', 'Equipos ($)']

    tabla['Consumo (kWh)'] = tabla['Consumo (kWh)'].apply(lambda x: f"{x:,.0f}")
    for col in ['Ahorro ($)', 'Renting ($)', 'Diferencia ($)', 'Equipos ($)']:
        tabla[col] = tabla[col].apply(lambda x: f"${x:,.0f}")

    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("📥 Descargar como CSV", tabla.to_csv(index=False),
                       "dashboard_energetico.csv", "text/csv")

else:
    st.warning("No hay registros que coincidan con los filtros seleccionados.")

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("---")
n_cuentas   = df['cuenta'].nunique()
n_registros = len(df)
st.markdown(f"""
<div style='text-align:center;color:#888;font-size:0.9em'>
    Dashboard Energético • Oct 2025 – Abr 2026 • {n_cuentas} Sedes • {n_registros} Registros
</div>
""", unsafe_allow_html=True)
