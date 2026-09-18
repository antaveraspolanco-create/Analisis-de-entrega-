from pathlib import Path
import io
import pandas as pd
import plotly.express as px
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
    """Carga los datasets históricos de la serie temporal y la jerarquía."""
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

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Evolución Macro (IPC vs Salud)",
            "Jerarquía COICOP Salud",
            "Implicaciones PDSS",
            "Tabla IPC Completa",
        ]
    )

# -------------------------------------------------------------
    # TAB 1: Evolución Temporal (Gráfico de Barras)
    # -------------------------------------------------------------
    with tab1:
        st.subheader("Trayectoria IPC General vs. IPC Salud")

        cols_grafico = [
            col
            for col in ["IPC general", "Salud"]
            if col in df_serie.columns
        ]

        if "Fecha" in df_serie.columns and cols_grafico:
            # Opción para agrupar por frecuencia si la serie tiene muchos datos
            frecuencia = st.radio(
                "Frecuencia de visualización:",
                options=["Mensual (Todos los datos)", "Promedio Anual"],
                horizontal=True,
            )

            df_plot = df_serie.copy()

            if frecuencia == "Promedio Anual":
                df_plot["Año"] = df_plot["Fecha"].dt.year
                df_plot = df_plot.groupby("Año")[cols_grafico].mean().reset_index()
                eje_x = "Año"
            else:
                eje_x = "Fecha"

            # Crear gráfico de barras agrupadas
            fig_barras = px.bar(
                df_plot,
                x=eje_x,
                y=cols_grafico,
                barmode="group",
                title="Comparativo IPC General vs IPC Salud",
                color_discrete_sequence=["#2b5c8f", "#00a8e8"],
            )

            fig_barras.update_layout(
                xaxis_title="Periodo",
                yaxis_title="Índice Base",
                legend_title="Indicadores",
                hovermode="x unified",
            )

            st.plotly_chart(fig_barras, use_container_width=True)
        else:
            st.error(
                "⚠️ Columnas requeridas ('Fecha', 'IPC general', 'Salud') no encontradas."
            )

    # -------------------------------------------------------------
    # TAB 2: Jerarquía COICOP (Pie + Treemap / Sunburst)
    # -------------------------------------------------------------
    with tab2:
        st.subheader("Ponderación del Rubro Salud en la Canasta")

        # Definir la lista de niveles jerárquicos COICOP según tu CSV
        path_jerarquia = ["Division", "Grupo", "Clase", "Subclase", "Artículo"]
        path_validos = [col for col in path_jerarquia if col in df_jerarquia.columns]

        # Si no coinciden los nombres exactos de columnas, intenta con nombres comunes en tu dataset
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
        st.info(f"Variación aplicada: **{var_input:.2f}%**")
        st.success(
            f"**Per Cápita Reajustado Recomendado:** RD$ {capita_nueva:,.2f} / afiliado / mes"
        )

    # -------------------------------------------------------------
    # TAB 4: Tabla IPC Completa y Exportación
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

except Exception as e:
    st.error(f"Error al ejecutar el dashboard: {e}")

    streamlit
