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
    for key in ('busqueda_widget', 'nivel_widget', 'sede_widget', 'mes_widget', 'heatmap_sedes_widget', 'detalle_cuentas_widget'):
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
        'Nivel 1 - Operador': '#FFB627',
        'Nivel 1 - Usuario':  '#FFC94D',
        'Nivel 2 - Usuario':  '#FFD980',
    }
    COLORES_BIA = {
        'Nivel 1 - Operador': '#09B4CC',
        'Nivel 1 - Usuario':  '#2ECC71',
        'Nivel 2 - Usuario':  '#7555F3',
    }

    fig_tarifas = go.Figure()
    for niv in sorted(tarifas_mes['nivel'].unique()):
        sub = tarifas_mes[tarifas_mes['nivel'] == niv]
        c_epm = COLORES_EPM.get(niv, '#FFB627')
        c_bia = COLORES_BIA.get(niv, '#09B4CC')
        fig_tarifas.add_trace(go.Scatter(
            x=sub['mes'], y=sub['tarifa_epm'],
            mode='lines+markers',
            name=f'EPM · {niv}',
            line=dict(color=c_epm, width=1.5, shape='spline'),
            marker=dict(size=5, symbol='circle', color=c_epm,
                        line=dict(width=0)),
            hovertemplate='$%{y:.4f}/kWh<extra>EPM · ' + niv + '</extra>',
        ))
        fig_tarifas.add_trace(go.Scatter(
            x=sub['mes'], y=sub['tarifa_bia'],
            mode='lines+markers',
            name=f'BIA · {niv}',
            line=dict(color=c_bia, width=1.5, dash='dot', shape='spline'),
            marker=dict(size=5, symbol='diamond', color=c_bia,
                        line=dict(width=0)),
            hovertemplate='$%{y:.4f}/kWh<extra>BIA · ' + niv + '</extra>',
        ))

    fig_tarifas.update_layout(
        hovermode='x unified',
        template='plotly_dark',
        height=360,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.05,
            xanchor='left', x=0,
            font=dict(size=11),
            bgcolor='rgba(0,0,0,0)', borderwidth=0,
        ),
        xaxis=dict(
            title='', tickfont=dict(size=11),
            showgrid=True, gridcolor='rgba(140,155,176,0.12)', gridwidth=1,
            zeroline=False, showline=False,
        ),
        yaxis=dict(
            title='$/kWh', tickfont=dict(size=11), tickformat='$.3f',
            showgrid=True, gridcolor='rgba(140,155,176,0.12)', gridwidth=1,
            zeroline=False, showline=False,
        ),
        margin=dict(t=10, b=40, l=60, r=20),
        hoverlabel=dict(bgcolor='#101525', bordercolor='#1A2035',
                        font=dict(size=12)),
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
        connector=dict(line=dict(color='#8C9BB0', width=1)),
        increasing=dict(marker=dict(color='#2ECC71')),
        decreasing=dict(marker=dict(color='#8C9BB0')),
        totals=dict(marker=dict(color='#7555F3')),
    ))
    fig_wf.update_layout(
        title='Flujo de Ahorro Neto Mensual (Ahorro tarifa − Renting)',
        xaxis_title='Mes', yaxis_title='Monto ($)',
        template='plotly_dark', height=420,
        showlegend=False,
    )
    st.plotly_chart(fig_wf, use_container_width=True)

    # ── 2. Heatmap Sede × Mes  +  Participación de Sede ─────────────────────
    por_sede = (
        filtrado
        .groupby('cuenta', as_index=False)
        .agg(
            consumo    =('consumo',    'sum'),
            ahorro_neto=('ahorro_neto','sum'),
            nivel      =('nivel',      'first'),
        )
    )

    # Filtro de sedes para el heatmap (depende de filtros principales)
    cuentas_disp_hm = sorted(filtrado['cuenta'].astype(str).unique().tolist())
    sedes_hm = st.multiselect(
        "Sedes en el mapa de calor",
        options=cuentas_disp_hm,
        default=[],
        placeholder="Selecciona una o varias sedes para visualizar…",
        key="heatmap_sedes_widget",
    )

    c1, c2 = st.columns(2)

    with c1:
        if not sedes_hm:
            st.info("Selecciona al menos una sede arriba para ver el mapa de calor.")
        else:
            df_hm = filtrado[filtrado['cuenta'].astype(str).isin(sedes_hm)]
            pivot = df_hm.pivot_table(
                index='cuenta', columns='mes', values='ahorro_neto',
                aggfunc='sum', fill_value=0,
            )
            cols_ord = [m for m in MESES_KEYS if m in pivot.columns]
            pivot = pivot[cols_ord]
            pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]

            fig_hm = go.Figure(go.Heatmap(
                z=pivot.values,
                x=list(pivot.columns),
                y=[str(c) for c in pivot.index],
                colorscale=[[0.0, '#7555F3'], [0.5, '#101525'], [1.0, '#2ECC71']],
                zmid=0,
                hoverongaps=False,
                hovertemplate='<b>Cuenta %{y}</b><br>Mes: %{x}<br>Ahorro neto: $%{z:,.0f}<extra></extra>',
                colorbar=dict(title='Ahorro ($)', tickformat='$,.0f'),
            ))
            fig_hm.update_layout(
                title='Ahorro Neto por Sede y Mes',
                xaxis_title='Mes',
                yaxis_title='',
                template='plotly_dark',
                height=max(300, len(pivot) * 40 + 100),
            )
            st.plotly_chart(fig_hm, use_container_width=True)

    with c2:
        st.markdown("**Participación de Sede**")
        ranking = por_sede.sort_values('ahorro_neto', ascending=False)
        sede_opts = [""] + ranking['cuenta'].astype(str).tolist()
        sede_sel = st.selectbox(
            "Selecciona una sede",
            sede_opts,
            index=0,
            key="ranking_sede_widget",
        )

        if not sede_sel:
            st.info("Selecciona una sede para ver su participación en el resultado global.")
        else:
            det = filtrado[filtrado['cuenta'].astype(str) == sede_sel]
            niv_sede   = det['nivel'].iloc[0] if len(det) else '—'
            s_consumo  = det['consumo'].sum()
            s_ahorro   = det['ahorro_neto'].sum()
            s_epm      = det['costo_epm'].sum()
            s_bia      = det['costo_bia'].sum()
            s_bia_rent = s_bia + det['renting_mensual'].sum()

            g_consumo  = filtrado['consumo'].sum()
            g_ahorro   = filtrado['ahorro_neto'].sum()
            g_epm      = filtrado['costo_epm'].sum()
            g_bia_rent = filtrado['costo_bia'].sum() + filtrado['renting_mensual'].sum()

            def _pct(a, b): return round(a / b * 100, 1) if b else 0.0

            p_consumo  = _pct(s_consumo,  g_consumo)
            p_ahorro   = _pct(s_ahorro,   g_ahorro)
            p_epm      = _pct(s_epm,      g_epm)
            p_bia_rent = _pct(s_bia_rent, g_bia_rent)

            c_ahorro = '#2ECC71' if s_ahorro > 0 else '#8C9BB0'
            st.markdown(
                f"<span style='color:#8C9BB0;font-size:0.82em'>{niv_sede}</span>&nbsp;&nbsp;"
                f"<span style='color:{c_ahorro};font-weight:600'>Ahorro neto: ${s_ahorro:,.0f}</span>",
                unsafe_allow_html=True,
            )

            st.markdown("""
<div style='background:#101525;border-left:3px solid #7555F3;padding:10px 14px;border-radius:4px;margin:10px 0;font-size:0.82em;color:#8C9BB0;line-height:1.6'>
<b style='color:#FFFFFF'>¿Cómo leer este panel?</b><br>
Cada tarjeta muestra el <b style='color:#FFFFFF'>peso porcentual</b> de esta sede dentro del total filtrado, y el valor absoluto debajo.<br><br>
⚡ <b style='color:#09B4CC'>Consumo</b> — fracción de la energía total consumida por esta sede.<br>
💰 <b style='color:#2ECC71'>Ahorro Neto</b> — porción del ahorro (o pérdida) que aporta esta sede.<br>
🔴 <b style='color:#FFB627'>Costo EPM</b> — cuánto representa esta sede del costo total si se pagara con EPM.<br>
🟢 <b style='color:#7555F3'>BIA + Renting</b> — su peso en el costo real con BIA incluyendo el renting mensual.<br><br>
Las barras horizontales muestran visualmente ese porcentaje sobre el 100% del total.
</div>
""", unsafe_allow_html=True)

            ma, mb = st.columns(2)
            ma.metric("⚡ Consumo",     f"{p_consumo:.1f}%",  f"{s_consumo:,.0f} kWh", delta_color="off")
            mb.metric("💰 Ahorro Neto", f"{p_ahorro:.1f}%",   f"${s_ahorro:,.0f}",      delta_color="off")
            mc, md = st.columns(2)
            mc.metric("🔴 Costo EPM",   f"{p_epm:.1f}%",      f"${s_epm:,.0f}",         delta_color="off")
            md.metric("🟢 BIA+Renting", f"{p_bia_rent:.1f}%", f"${s_bia_rent:,.0f}",    delta_color="off")

            st.markdown("")

            labels = ['Consumo', 'Ahorro Neto', 'Costo EPM', 'BIA+Renting']
            vals   = [p_consumo, p_ahorro, p_epm, p_bia_rent]
            colors = ['#09B4CC', c_ahorro, '#FFB627', '#7555F3']

            fig_p = go.Figure()
            fig_p.add_trace(go.Bar(
                x=[100] * 4, y=labels, orientation='h',
                marker_color='rgba(140,155,176,0.1)',
                showlegend=False, hoverinfo='skip',
            ))
            fig_p.add_trace(go.Bar(
                x=vals, y=labels, orientation='h',
                marker_color=colors,
                text=[f"{v:.1f}%" for v in vals],
                textposition='inside',
                textfont=dict(size=12, color='#FFFFFF'),
                showlegend=False,
                hovertemplate='%{y}: %{x:.1f}% del total<extra></extra>',
            ))
            fig_p.update_layout(
                barmode='overlay',
                template='plotly_dark',
                height=240,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(showgrid=False, tickfont=dict(size=11)),
                margin=dict(t=0, b=10, l=100, r=20),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure([
            go.Bar(
                x=por_mes['mes'], y=por_mes['costo_epm'],
                name='EPM', marker_color='#7555F3',
                text=[f"${v:,.0f}" for v in por_mes['costo_epm']],
                textposition='outside', textfont=dict(size=10, color='#8C9BB0'),
                hovertemplate='EPM %{x}: $%{y:,.0f}<extra></extra>',
            ),
            go.Bar(
                x=por_mes['mes'], y=por_mes['costo_bia'],
                name='BIA', marker_color='#09B4CC',
                text=[f"${v:,.0f}" for v in por_mes['costo_bia']],
                textposition='outside', textfont=dict(size=10, color='#8C9BB0'),
                hovertemplate='BIA %{x}: $%{y:,.0f}<extra></extra>',
            ),
        ])
        fig.update_layout(
            title="Costo Comparativo (EPM vs BIA)",
            xaxis_title="", yaxis_title="$",
            barmode='group', hovermode='x unified',
            template='plotly_dark', height=420,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', yanchor='top', y=-0.15, xanchor='center', x=0.5,
                        bgcolor='rgba(0,0,0,0)', borderwidth=0),
            yaxis=dict(showgrid=True, gridcolor='rgba(140,155,176,0.12)', zeroline=False),
            xaxis=dict(showgrid=False),
            margin=dict(t=40, b=60, l=60, r=20),
            uniformtext=dict(mode='hide', minsize=9),
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        por_mes['acumulado'] = por_mes['ahorro_neto'].cumsum()
        fig = go.Figure([
            go.Scatter(
                x=por_mes['mes'], y=por_mes['acumulado'],
                mode='lines+markers', name='Acumulado Neto',
                line=dict(color='#09B4CC', width=3), fill='tozeroy'
            )
        ])
        fig.update_layout(title="Acumulado Neto por Período",
                          xaxis_title="Mes", yaxis_title="Monto Acumulado ($)",
                          hovermode='x', template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Tabla detallada ───────────────────────────────────────────────────────

    FACTOR_COMERCIAL = 1.40
    N_MESES          = 7

    # Una fila por sede dentro del filtrado activo
    eq_filtrado    = filtrado.groupby('cuenta').agg(
        costo_equipos   =('costo_equipos',   'first'),
        renting_mensual =('renting_mensual', 'first'),
    )
    valor_eq_real  = eq_filtrado['costo_equipos'].sum()
    valor_eq_com   = valor_eq_real * FACTOR_COMERCIAL
    rent_real_men  = eq_filtrado['renting_mensual'].sum()
    rent_ref_men   = rent_real_men * FACTOR_COMERCIAL
    bia_men        = rent_ref_men - rent_real_men

    pagado_real    = rent_real_men * N_MESES
    pagado_ref     = rent_ref_men  * N_MESES
    bia_aportado   = bia_men       * N_MESES

    por_pagar_real = valor_eq_real - pagado_real
    por_pagar_ref  = valor_eq_com  - pagado_ref

    st.markdown("---")
    st.markdown("### Detalle de Datos")
    cuentas_tabla_opts = sorted(filtrado['cuenta'].astype(str).unique().tolist())
    st.multiselect(
        "Filtrar tabla por cuenta",
        options=cuentas_tabla_opts,
        default=[],
        placeholder="Todas las cuentas — selecciona para filtrar",
        key="detalle_cuentas_widget",
    )
    cuentas_tabla_sel = st.session_state.get("detalle_cuentas_widget", [])

    # ── Banner BIA ──────────────────────────────────────────────────────────
    st.markdown(f"""
<div style='background:#101525;border-left:4px solid #2ECC71;padding:14px 18px;
            border-radius:6px;margin-bottom:18px'>
  <span style='color:#8C9BB0;font-size:0.85em'>Aporte acumulado de BIA en {N_MESES} meses</span><br>
  <span style='color:#2ECC71;font-size:1.8em;font-weight:700'>${bia_aportado:,.0f}</span>
  <span style='color:#8C9BB0;font-size:0.9em'> financiados por BIA en equipos</span>
</div>
""", unsafe_allow_html=True)

    # ── Comparativo lado a lado ─────────────────────────────────────────────
    st.markdown("#### Financiamiento de Equipos")

    def _header(texto, color):
        st.markdown(
            f"<div style='color:{color};font-weight:600;font-size:0.9em;"
            f"padding-bottom:8px;margin-bottom:4px;border-bottom:1px solid rgba(140,155,176,0.2)'>"
            f"{texto}</div>",
            unsafe_allow_html=True,
        )

    def _ahorro_card(label, valor):
        st.markdown(
            f"<div style='padding:8px 0 8px 0;border-bottom:1px solid rgba(140,155,176,0.1)'>"
            f"<div style='color:#8C9BB0;font-size:0.78em'>{label}</div>"
            f"<div style='color:#2ECC71;font-size:1.15em;font-weight:600'>${valor:,.0f}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    col_sin, col_con, col_ahorro = st.columns(3)

    with col_sin:
        _header("Valor total equipos", "#8C9BB0")
        st.metric("Valor equipos",             f"${valor_eq_com:,.0f}")
        st.metric("Renting mensual",           f"${rent_ref_men:,.0f}")
        st.metric(f"Pagado ({N_MESES} meses)", f"${pagado_ref:,.0f}")
        st.metric("Por pagar",                 f"${por_pagar_ref:,.0f}")

    with col_con:
        _header("Con BIA", "#09B4CC")
        st.metric("Valor equipos",             f"${valor_eq_real:,.0f}")
        st.metric("Renting mensual",           f"${rent_real_men:,.0f}")
        st.metric(f"Pagado ({N_MESES} meses)", f"${pagado_real:,.0f}")
        st.metric("Por pagar",                 f"${por_pagar_real:,.0f}")

    with col_ahorro:
        _header("El cliente ahorra", "#2ECC71")
        _ahorro_card("En valor de equipos",     valor_eq_com - valor_eq_real)
        _ahorro_card("En renting mensual",      bia_men)
        _ahorro_card(f"En {N_MESES} meses",     bia_aportado)
        _ahorro_card("En saldo por pagar",      por_pagar_ref - por_pagar_real)

    st.markdown("")

    base_tabla = (
        filtrado if not cuentas_tabla_sel
        else filtrado[filtrado['cuenta'].astype(str).isin(cuentas_tabla_sel)]
    )

    tabla = base_tabla[[
        'cuenta', 'direccion', 'nivel', 'mes', 'consumo',
        'tarifa_epm', 'tarifa_bia', 'ahorro_bruto',
        'costo_equipos', 'renting_mensual',
    ]].copy()

    tabla['valor_comercial']  = tabla['costo_equipos'] * FACTOR_COMERCIAL
    tabla['renting_ref']      = tabla['renting_mensual'] * FACTOR_COMERCIAL
    tabla['bia_financia']     = tabla['renting_ref'] - tabla['renting_mensual']

    # costo_equipos = valor real (Con BIA) | valor_comercial = precio full
    tabla.columns = [
        'Cuenta', 'Dirección', 'Nivel', 'Mes', 'Consumo (kWh)',
        'Tarifa EPM ($/kWh)', 'Tarifa BIA ($/kWh)', 'Ahorro en Tarifa ($)',
        'Valor Con BIA ($)', 'Renting Con BIA ($)',
        'Valor Total Equipos ($)', 'Renting Mensual ($)', 'El Cliente Ahorra ($)',
    ]

    # Precio full primero, luego Con BIA
    tabla = tabla[[
        'Cuenta', 'Dirección', 'Nivel', 'Mes', 'Consumo (kWh)',
        'Tarifa EPM ($/kWh)', 'Tarifa BIA ($/kWh)', 'Ahorro en Tarifa ($)',
        'Valor Total Equipos ($)', 'Renting Mensual ($)',
        'Valor Con BIA ($)', 'Renting Con BIA ($)', 'El Cliente Ahorra ($)',
    ]]

    tabla['Consumo (kWh)']      = tabla['Consumo (kWh)'].apply(lambda x: f"{x:,.0f}")
    tabla['Tarifa EPM ($/kWh)'] = tabla['Tarifa EPM ($/kWh)'].apply(lambda x: f"${x:.4f}")
    tabla['Tarifa BIA ($/kWh)'] = tabla['Tarifa BIA ($/kWh)'].apply(lambda x: f"${x:.4f}")
    for col in ['Ahorro en Tarifa ($)', 'Valor Total Equipos ($)', 'Renting Mensual ($)',
                'Valor Con BIA ($)', 'Renting Con BIA ($)', 'El Cliente Ahorra ($)']:
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
<div style='text-align:center;color:#8C9BB0;font-size:0.9em'>
    Dashboard Energético • Oct 2025 – Abr 2026 • {n_cuentas} Sedes • {n_registros} Registros
</div>
""", unsafe_allow_html=True)
