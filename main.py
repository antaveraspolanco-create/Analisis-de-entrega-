from pathlib import Path
import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Dashboard IPC Salud & PDSS", layout="wide")
st.title("📊 Tablero de Control: IPC Salud e Indexación PDSS")

# Directivas de rutas locales
BASE_DIR = Path(__file__).resolve().parent

# -------------------------------------------------------------
# KPIs Superiores (Agosto 2026)
# -------------------------------------------------------------
st.subheader("Indicadores de Inflación (Agosto 2026)")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Inflación Mensual", value="0.38%")

with col2:
    st.metric(
        label="Inflación Interanual Salud",
        value="6.45%",
        delta="+1.32 pp vs General",
        delta_color="normal",
    )

with col3:
    st.metric(
        label="Subyacente Interanual",
        value="4.76%",
        help="Excluye alimentos volátiles, combustibles y servicios regulados",
    )

st.divider()


# -------------------------------------------------------------
# Carga y Procesamiento de Datos CSV
# -------------------------------------------------------------
def _leer_csv(ruta: Path) -> pd.DataFrame:
    """Lee CSV probando encodificaciones estándar."""
    for enc in ("utf-8-sig", "latin1", "cp1252"):
        try:
            df = pd.read_csv(ruta, encoding=enc)
            df.columns = df.columns.astype(str).str.strip()
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer el archivo {ruta.name}")


@st.cache_data
def cargar_datos():
    """Carga los datasets históricos de la serie temporal y jerarquía."""
    ruta_serie = BASE_DIR / "IPC República Dominicana (ACDI).csv"
    ruta_jerarquia = BASE_DIR / "DataSet analisis.csv"

    if not ruta_serie.exists() or not ruta_jerarquia.exists():
        return None, None

    df_serie = _leer_csv(ruta_serie)
    df_jerarquia = _leer_csv(ruta_jerarquia)

    if "Fecha" in df_serie.columns:
        df_serie["Fecha"] = pd.to_datetime(df_serie["Fecha"], errors="coerce")

    return df_serie, df_jerarquia


try:
    df_serie, df_jerarquia = cargar_datos()

    if df_serie is None or df_jerarquia is None:
        st.error(
            "⚠️ No se encontraron los archivos CSV requeridos en la carpeta del proyecto."
        )
        st.stop()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Evolución Macro (IPC vs Salud)",
            "Jerarquía COICOP Salud",
            "Implicaciones PDSS",
            "Tabla IPC Completa",
            "IPC República Dominicana Salud",
        ]
    )

    # -------------------------------------------------------------
    # TAB 1: Evolución Temporal
    # -------------------------------------------------------------
    with tab1:
        st.subheader("Trayectoria IPC General vs. IPC Salud")

        cols_grafico = [
            col
            for col in ["IPC general", "Salud"]
            if col in df_serie.columns
        ]

        if "Fecha" in df_serie.columns and cols_grafico:
            frecuencia = st.radio(
                "Frecuencia de visualización:",
                options=["Mensual (Todos los datos)", "Promedio Anual"],
                horizontal=True,
            )

            df_plot = df_serie.copy().sort_values("Fecha")

            if frecuencia == "Mensual (Todos los datos)":
                fig = go.Figure()

                if "IPC general" in cols_grafico:
                    fig.add_trace(
                        go.Bar(
                            x=df_plot["Fecha"],
                            y=df_plot["IPC general"],
                            name="IPC General (Barras)",
                            marker_color="#2b5c8f",
                        )
                    )

                if "Salud" in cols_grafico:
                    fig.add_trace(
                        go.Bar(
                            x=df_plot["Fecha"],
                            y=df_plot["Salud"],
                            name="IPC Salud (Barras)",
                            marker_color="#00a8e8",
                        )
                    )

                df_plot["Promedio_IPC"] = df_plot[cols_grafico].mean(axis=1)
                fig.add_trace(
                    go.Scatter(
                        x=df_plot["Fecha"],
                        y=df_plot["Promedio_IPC"],
                        mode="lines+markers",
                        name="Línea de Promedio Ascendente",
                        line=dict(color="#ff9f1c", width=3, dash="solid"),
                    )
                )

                fig.update_layout(
                    barmode="group",
                    title="Evolución Mensual: Barras IPC General vs Salud con Línea de Promedio",
                    xaxis_title="Fecha",
                    yaxis_title="Índice Base",
                    hovermode="x unified",
                    height=550,
                )

            else:
                df_plot["Año"] = df_plot["Fecha"].dt.year
                df_anual = df_plot.groupby("Año")[cols_grafico].mean(numeric_only=True).reset_index()

                fig = px.bar(
                    df_anual,
                    x="Año",
                    y=cols_grafico,
                    barmode="group",
                    title="Promedio Anual: Comparativo de Barras IPC General vs IPC Salud",
                    color_discrete_sequence=["#2b5c8f", "#00a8e8"],
                )

                fig.update_layout(
                    xaxis_title="Año",
                    yaxis_title="Promedio Índice Base",
                    hovermode="x unified",
                    height=500,
                )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(
                "⚠️ Columnas requeridas ('Fecha', 'IPC general', 'Salud') no encontradas."
            )

    # -------------------------------------------------------------
    # TAB 2: Jerarquía COICOP
    # -------------------------------------------------------------
    with tab2:
        st.subheader("Ponderación del Rubro Salud en la Canasta")

        path_jerarquia = ["Division", "Grupo", "Clase", "Subclase", "Artículo"]
        path_validos = [col for col in path_jerarquia if col in df_jerarquia.columns]

        if not path_validos:
            path_validos = [col for col in ["Nivel", "Codigo_COICOP", "Descripcion"] if col in df_jerarquia.columns]

        tipo_grafico = st.selectbox(
            "Seleccionar Tipo de Gráfico",
            options=[
                "Diagrama Anular (Sunburst)",
                "Mapa de Árbol (Treemap)",
                "Vista de Tabla",
            ],
        )

        val_ponderacion = "Ponderacion" if "Ponderacion" in df_jerarquia.columns else None

        if tipo_grafico == "Diagrama Anular (Sunburst)":
            fig_sun = px.sunburst(
                df_jerarquia,
                path=path_validos,
                values=val_ponderacion,
                title="Estructura Circular COICOP (Salud)",
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_sun.update_layout(margin=dict(t=40, l=0, r=0, b=0), height=650)
            st.plotly_chart(fig_sun, use_container_width=True)

        elif tipo_grafico == "Mapa de Árbol (Treemap)":
            fig_tree = px.treemap(
                df_jerarquia,
                path=path_validos,
                values=val_ponderacion,
                title="Estructura Jerárquica COICOP (Salud)",
            )
            fig_tree.update_traces(textinfo="label+value")
            fig_tree.update_layout(margin=dict(t=40, l=0, r=0, b=0), height=650)
            st.plotly_chart(fig_tree, use_container_width=True)

        else:
            st.dataframe(df_jerarquia, use_container_width=True)

    # -------------------------------------------------------------
    # TAB 3: Simulador PDSS
    # -------------------------------------------------------------
    with tab3:
        st.subheader("Simulador de Reajuste del Cápita Base")

        capita_actual = st.number_input(
            "Per Cápita Base Actual (RD$):", value=1525.40, step=10.0
        )

        col_var = (
            "Salud, variación interanual"
            if "Salud, variación interanual" in df_serie.columns
            else None
        )

        if col_var and not df_serie[col_var].dropna().empty:
            var_interanual = float(df_serie[col_var].dropna().iloc[-1])
        else:
            var_interanual = 6.45

        var_input = st.number_input(
            "Variación Interanual IPC Salud (%):",
            value=var_interanual,
            step=0.1,
        )

        capita_nueva = capita_actual * (1 + (var_input / 100))
        st.info(f"Variación applied: **{var_input:.2f}%**")
        st.success(
            f"**Per Cápita Reajustado Recomendado:** RD$ {capita_nueva:,.2f} / afiliado / mes"
        )

    # -------------------------------------------------------------
    # TAB 4: Tabla IPC Completa
    # -------------------------------------------------------------
    with tab4:
        st.subheader("Serie Temporal Histórica de Precios")

        st.dataframe(df_serie, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_serie.to_excel(
                writer, index=False, sheet_name="IPC_Serie_Historica"
            )

        st.download_button(
            label="📥 Descargar Serie Completa en Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="serie_historica_ipc.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # -------------------------------------------------------------
    # TAB 5: EVOLUCIÓN LINEAL Y COMPARATIVA IPC SALUD
    # -------------------------------------------------------------
    with tab5:
        st.header("📊 Evolución e Indicadores - IPC República Dominicana Salud")

        archivo_salud = BASE_DIR / "ipc_salud.csv"

        if archivo_salud.exists():
            try:
                df_salud_raw = pd.read_csv(archivo_salud, encoding='utf-8')
            except Exception:
                df_salud_raw = pd.read_csv(archivo_salud, encoding='latin1')

            df_salud_clean = df_salud_raw.copy()
            df_salud_clean.columns = (
                df_salud_clean.columns.astype(str)
                .str.replace('"', '')
                .str.strip()
            )

            col_fecha = [c for c in df_salud_clean.columns if "fecha" in c.lower()]
            if col_fecha:
                df_salud_clean[col_fecha[0]] = pd.to_datetime(df_salud_clean[col_fecha[0]], errors="coerce")
                df_salud_clean = df_salud_clean.dropna(subset=[col_fecha[0]]).sort_values(col_fecha[0])

            for col in df_salud_clean.columns:
                if not col_fecha or col != col_fecha[0]:
                    s_num = (
                        df_salud_clean[col]
                        .astype(str)
                        .str.replace(',', '.')
                        .str.strip()
                    )
                    df_salud_clean[col] = pd.to_numeric(s_num, errors='coerce')

            cols_num = [c for c in df_salud_clean.select_dtypes(include=["number"]).columns if df_salud_clean[c].dropna().count() > 0]
            cols_cat = [c for c in df_salud_clean.columns if c not in cols_num]

            if cols_cat and cols_num:
                tipo_visual = st.radio(
                    "Estilo de visualización gráfica:",
                    options=["Línea Suave con Área Sombreada", "Combinado (Barras + Línea)"],
                    horizontal=True
                )

                col_x = st.selectbox("Seleccionar Eje X (Fecha / Categoría):", options=cols_cat, key="sb_cat_salud")
                col_y = st.selectbox("Seleccionar Eje Y (Métrica a Graficar):", options=cols_num, key="sb_num_salud")

                df_grafico = df_salud_clean.dropna(subset=[col_y])

                if not df_grafico.empty:
                    if tipo_visual == "Línea Suave con Área Sombreada":
                        fig_salud = px.line(
                            df_grafico,
                            x=col_x,
                            y=col_y,
                            title=f"📈 Evolución Tendencial de {col_y}",
                            markers=True,
                            template="plotly_white"
                        )
                        fig_salud.update_traces(
                            line_color="#00a8e8",
                            line_width=3,
                            marker=dict(size=6, color="#003459"),
                            fill='tonexty'
                        )
                    else:
                        fig_salud = go.Figure()
                        fig_salud.add_trace(
                            go.Bar(
                                x=df_grafico[col_x],
                                y=df_grafico[col_y],
                                name=f"Magnitud {col_y}",
                                marker_color="#2b5c8f"
                            )
                        )
                        fig_salud.add_trace(
                            go.Scatter(
                                x=df_grafico[col_x],
                                y=df_grafico[col_y],
                                name="Tendencia",
                                mode="lines+markers",
                                line=dict(color="#ff9f1c", width=3)
                            )
                        )
                        fig_salud.update_layout(title=f"📊 Comparativo en Barras y Línea: {col_y}")

                    fig_salud.update_layout(
                        xaxis_title=col_x,
                        yaxis_title=col_y,
                        xaxis=dict(tickangle=-45),
                        hovermode="x unified",
                        height=550
                    )
                    st.plotly_chart(fig_salud, use_container_width=True)
                else:
                    st.warning(f"⚠️ La columna '{col_y}' no contiene datos numéricos válidos.")
            else:
                st.warning("⚠️ No se detectaron columnas numéricas válidas para graficar.")

            st.subheader("Vista previa de la tabla de datos")
            st.dataframe(df_salud_clean, use_container_width=True)
            st.caption(f"Total de registros válidos cargados: {len(df_salud_clean)} filas.")
        else:
            st.error("❌ No se encontró el archivo ipc_salud.csv en la raíz del proyecto.")

except Exception as e:
    st.error(f"Error general en la aplicación: {e}")