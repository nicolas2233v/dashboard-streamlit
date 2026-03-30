import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Dashboard Etra PRO", layout="wide")

st.title("Dashboard Etra")

FAMILIAS_FOCO_DEFAULT = ["PETFOOD SALADILLO", "VITALCAN", "CAVOX", "BIOVIT"]


# =========================================================
# HELPERS
# =========================================================
def ordenar_meses(lista):
    orden = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
        "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }
    return sorted(lista, key=lambda x: orden.get(str(x), 999))


def safe_div(a, b):
    return a / b if b not in [0, None] and pd.notna(b) else 0


@st.cache_data
def cargar_archivos(files):
    dfs = []

    for file in files:
        df = pd.read_csv(file, sep=";", encoding="latin1")

        rename_map = {
            "Sum(Peso Artículo Comprobante (Kg))": "Kg",
            "Sum(Cantidad de Artículos)": "Unidades",
            "Sum(Precio Total)": "Precio Venta",
        }
        df = df.rename(columns=rename_map)

        # Mes
        if "Mes" not in df.columns:
            name = file.name.lower()
            if "enero" in name or "01" in name:
                df["Mes"] = "Enero"
            elif "febrero" in name or "02" in name:
                df["Mes"] = "Febrero"
            elif "marzo" in name or "03" in name:
                df["Mes"] = "Marzo"
            elif "abril" in name or "04" in name:
                df["Mes"] = "Abril"
            else:
                df["Mes"] = file.name

        # Fecha
        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
        else:
            df["Fecha"] = pd.NaT

        # Asegurar columnas
        columnas_base = [
            "Cliente", "Zona", "Vendedor", "Artículo", "Familia Artículo",
            "Kg", "Unidades", "Precio Venta", "Costo Unitario",
            "Nro Comprobante", "Mes", "Fecha"
        ]
        for c in columnas_base:
            if c not in df.columns:
                df[c] = np.nan

        # Numéricos
        for c in ["Kg", "Unidades", "Precio Venta", "Costo Unitario"]:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", ".", regex=False),
                errors="coerce"
            ).fillna(0)

        # Derivados
        df["Ventas"] = df["Precio Venta"]
        df["Costo Total"] = df["Costo Unitario"] * df["Unidades"]
        df["Margen $"] = df["Ventas"] - df["Costo Total"]
        df["Margen %"] = np.where(df["Ventas"] != 0, df["Margen $"] / df["Ventas"], 0)

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    out = pd.concat(dfs, ignore_index=True)

    # Limpieza texto
    for c in ["Cliente", "Zona", "Vendedor", "Artículo", "Familia Artículo", "Nro Comprobante", "Mes"]:
        if c in out.columns:
            out[c] = out[c].astype(str).str.strip()

    return out


def aplicar_filtros(df):
    st.sidebar.header("Filtros")

    # familias foco
    usar_familias_foco = st.sidebar.checkbox("Solo familias foco", value=False)
    base = df.copy()
    if usar_familias_foco:
        base = base[base["Familia Artículo"].isin(FAMILIAS_FOCO_DEFAULT)]

    # métrica
    metricas = ["Unidades", "Kg", "Ventas", "Costo Total", "Margen $", "Margen %"]
    metrica = st.sidebar.radio("Medir por", metricas)

    # periodo
    meses = ordenar_meses(base["Mes"].dropna().unique().tolist())
    meses_sel = st.sidebar.multiselect("Mes", meses, default=meses)

    f1 = base[base["Mes"].isin(meses_sel)] if meses_sel else base.copy()

    # filtro cascada
    zonas = sorted([z for z in f1["Zona"].dropna().unique().tolist() if z != "nan"])
    zonas_sel = st.sidebar.multiselect("Zona", zonas)
    f2 = f1[f1["Zona"].isin(zonas_sel)] if zonas_sel else f1.copy()

    vendedores = sorted([v for v in f2["Vendedor"].dropna().unique().tolist() if v != "nan"])
    vendedores_sel = st.sidebar.multiselect("Vendedor", vendedores)
    f3 = f2[f2["Vendedor"].isin(vendedores_sel)] if vendedores_sel else f2.copy()

    clientes = sorted([c for c in f3["Cliente"].dropna().unique().tolist() if c != "nan"])
    clientes_sel = st.sidebar.multiselect("Cliente", clientes)
    f4 = f3[f3["Cliente"].isin(clientes_sel)] if clientes_sel else f3.copy()

    familias = sorted([fa for fa in f4["Familia Artículo"].dropna().unique().tolist() if fa != "nan"])
    familias_sel = st.sidebar.multiselect("Familia", familias)
    f5 = f4[f4["Familia Artículo"].isin(familias_sel)] if familias_sel else f4.copy()

    articulos = sorted([a for a in f5["Artículo"].dropna().unique().tolist() if a != "nan"])
    articulos_sel = st.sidebar.multiselect("Artículo", articulos)
    f6 = f5[f5["Artículo"].isin(articulos_sel)] if articulos_sel else f5.copy()

    # filtro fecha si existe
    if f6["Fecha"].notna().any():
        min_f = f6["Fecha"].min().date()
        max_f = f6["Fecha"].max().date()
        fecha_rango = st.sidebar.date_input("Rango de fechas", value=(min_f, max_f))
        if isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
            desde, hasta = fecha_rango
            f6 = f6[(f6["Fecha"].dt.date >= desde) & (f6["Fecha"].dt.date <= hasta)]

    return f6, metrica


def descargar_filtrado(df):
    csv = df.to_csv(index=False, sep=";").encode("latin1", errors="ignore")
    st.download_button(
        "Descargar filtrado CSV",
        data=csv,
        file_name="dashboard_filtrado.csv",
        mime="text/csv"
    )


def mostrar_kpis(df, metrica):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    total_metrica = df[metrica].sum() if metrica != "Margen %" else safe_div(df["Margen $"].sum(), df["Ventas"].sum())
    c1.metric("Total métrica", f"{total_metrica:,.2f}")
    c2.metric("Clientes", f"{df['Cliente'].nunique():,}")
    c3.metric("Artículos", f"{df['Artículo'].nunique():,}")
    c4.metric("Zonas", f"{df['Zona'].nunique():,}")
    c5.metric("Vendedores", f"{df['Vendedor'].nunique():,}")
    c6.metric("Comprobantes", f"{df['Nro Comprobante'].nunique():,}" if "Nro Comprobante" in df.columns else "0")


def comparacion_periodos(df, metrica):
    st.subheader("Comparación entre períodos")

    meses = ordenar_meses(df["Mes"].dropna().unique().tolist())
    if len(meses) < 2:
        st.info("Cargá al menos dos meses para comparar.")
        return None, None

    c1, c2 = st.columns(2)
    periodo_a = c1.selectbox("Período A", meses, index=0, key="periodo_a")
    periodo_b = c2.selectbox("Período B", meses, index=min(1, len(meses)-1), key="periodo_b")

    dfa = df[df["Mes"] == periodo_a]
    dfb = df[df["Mes"] == periodo_b]

    ta = dfa[metrica].sum() if metrica != "Margen %" else safe_div(dfa["Margen $"].sum(), dfa["Ventas"].sum())
    tb = dfb[metrica].sum() if metrica != "Margen %" else safe_div(dfb["Margen $"].sum(), dfb["Ventas"].sum())
    delta = tb - ta
    delta_pct = safe_div(delta * 100, ta)

    st.metric(f"{periodo_b} vs {periodo_a}", f"{tb:,.2f}", f"{delta_pct:,.1f}%")

    fam = df.groupby(["Familia Artículo", "Mes"], dropna=False)[metrica].sum().reset_index()
    fig = px.bar(fam, x="Familia Artículo", y=metrica, color="Mes", barmode="group", title="Familias por mes")
    st.plotly_chart(fig, use_container_width=True, key="chart_familias_comparacion")

    return periodo_a, periodo_b


def tab_resumen(df, metrica):
    st.subheader("Resumen general")

    zona_res = df.groupby("Zona", dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    fig1 = px.bar(zona_res, x="Zona", y=metrica, title="Total por zona")
    st.plotly_chart(fig1, use_container_width=True, key="chart_resumen_zonas")

    ven_res = df.groupby("Vendedor", dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    fig2 = px.bar(ven_res, x="Vendedor", y=metrica, title="Total por vendedor")
    st.plotly_chart(fig2, use_container_width=True, key="chart_resumen_vendedores")

    descargar_filtrado(df)


def tab_zonas(df, metrica, periodo_a, periodo_b):
    st.subheader("Análisis por zona")

    actual = df.groupby("Zona", dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    st.dataframe(actual, use_container_width=True)

    fig = px.bar(actual, x="Zona", y=metrica, title="Ranking zonas")
    st.plotly_chart(fig, use_container_width=True, key="chart_tab_zonas")

    if periodo_a and periodo_b:
        za = df[df["Mes"] == periodo_a].groupby("Zona")[metrica].sum()
        zb = df[df["Mes"] == periodo_b].groupby("Zona")[metrica].sum()
        comp = pd.concat([za, zb], axis=1).fillna(0)
        comp.columns = [periodo_a, periodo_b]
        comp["Var Abs"] = comp[periodo_b] - comp[periodo_a]
        comp["Var %"] = np.where(comp[periodo_a] != 0, comp["Var Abs"] / comp[periodo_a], 0)
        comp = comp.sort_values("Var Abs")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Zonas que más caen")
            st.dataframe(comp.head(15), use_container_width=True)
        with c2:
            st.markdown("### Zonas que más crecen")
            st.dataframe(comp.sort_values("Var Abs", ascending=False).head(15), use_container_width=True)

        # Productos explicativos por zona
        st.markdown("### ¿Qué productos explican la suba o baja por zona?")
        zona_sel = st.selectbox("Elegí una zona", sorted(df["Zona"].dropna().unique().tolist()), key="zona_explicativa")

        dfa_z = df[(df["Mes"] == periodo_a) & (df["Zona"] == zona_sel)]
        dfb_z = df[(df["Mes"] == periodo_b) & (df["Zona"] == zona_sel)]

        pa = dfa_z.groupby(["Artículo", "Familia Artículo"])[metrica].sum()
        pb = dfb_z.groupby(["Artículo", "Familia Artículo"])[metrica].sum()
        expl = pd.concat([pa, pb], axis=1).fillna(0)
        expl.columns = [periodo_a, periodo_b]
        expl["Var Abs"] = expl[periodo_b] - expl[periodo_a]
        expl = expl.reset_index().sort_values("Var Abs")

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### Productos que más cayeron")
            st.dataframe(expl.head(20), use_container_width=True)
        with c4:
            st.markdown("#### Productos que más crecieron")
            st.dataframe(expl.sort_values("Var Abs", ascending=False).head(20), use_container_width=True)


def tab_vendedores(df, metrica, periodo_a, periodo_b):
    st.subheader("Análisis por vendedor")

    ven = df.groupby(["Vendedor", "Zona"], dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    st.dataframe(ven, use_container_width=True)

    fig = px.bar(ven, x="Vendedor", y=metrica, color="Zona", title="Vendedor por zona")
    st.plotly_chart(fig, use_container_width=True, key="chart_vendedores")

    if periodo_a and periodo_b:
        va = df[df["Mes"] == periodo_a].groupby("Vendedor")[metrica].sum()
        vb = df[df["Mes"] == periodo_b].groupby("Vendedor")[metrica].sum()
        comp = pd.concat([va, vb], axis=1).fillna(0)
        comp.columns = [periodo_a, periodo_b]
        comp["Var Abs"] = comp[periodo_b] - comp[periodo_a]
        comp["Var %"] = np.where(comp[periodo_a] != 0, comp["Var Abs"] / comp[periodo_a], 0)
        st.markdown("### Evolución de vendedores")
        st.dataframe(comp.sort_values("Var Abs"), use_container_width=True)


def tab_clientes(df, metrica, periodo_a, periodo_b):
    st.subheader("Clientes")

    ranking = df.groupby(["Cliente", "Zona", "Vendedor"], dropna=False)[metrica].sum().reset_index()
    ranking = ranking.sort_values(by=metrica, ascending=False)
    st.dataframe(ranking, use_container_width=True)

    if periodo_a and periodo_b:
        ca = df[df["Mes"] == periodo_a].groupby("Cliente")[metrica].sum()
        cb = df[df["Mes"] == periodo_b].groupby("Cliente")[metrica].sum()
        comp = pd.concat([ca, cb], axis=1).fillna(0)
        comp.columns = [periodo_a, periodo_b]
        comp["Var Abs"] = comp[periodo_b] - comp[periodo_a]
        comp["Var %"] = np.where(comp[periodo_a] != 0, comp["Var Abs"] / comp[periodo_a], 0)

        fuertes = comp.sort_values(periodo_a, ascending=False).head(50)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Clientes fuertes que más cayeron")
            st.dataframe(fuertes.sort_values("Var Abs").head(20), use_container_width=True)
        with c2:
            st.markdown("### Clientes fuertes que más crecieron")
            st.dataframe(fuertes.sort_values("Var Abs", ascending=False).head(20), use_container_width=True)


def tab_articulos(df, metrica, periodo_a, periodo_b):
    st.subheader("Artículos vendidos")

    buscar = st.text_input("Buscar artículo", key="buscar_articulo")

    art = df.groupby(["Artículo", "Familia Artículo"], dropna=False)[metrica].sum().reset_index()
    art = art.sort_values(by=metrica, ascending=False)

    if buscar:
        art = art[art["Artículo"].str.contains(buscar, case=False, na=False)]

    st.markdown("### Top de artículos")
    st.dataframe(art, use_container_width=True)

    articulos_lista = art["Artículo"].dropna().unique().tolist()
    if not articulos_lista:
        st.info("No hay artículos disponibles con esos filtros.")
        return

    articulo_sel = st.selectbox("Elegí un artículo para profundizar", articulos_lista, key="articulo_drill")

    d = df[df["Artículo"] == articulo_sel].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Clientes que compraron", f"{d['Cliente'].nunique():,}")
    c2.metric("Zonas", f"{d['Zona'].nunique():,}")
    c3.metric("Vendedores", f"{d['Vendedor'].nunique():,}")

    st.markdown("### Clientes que compraron este artículo")
    cli = d.groupby(["Cliente", "Zona", "Vendedor"], dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    st.dataframe(cli, use_container_width=True)

    if not cli.empty:
        clientes_lista = cli["Cliente"].dropna().unique().tolist()
        cliente_sel = st.selectbox("Elegí un cliente de este artículo", clientes_lista, key="cliente_desde_articulo")

        dc = df[df["Cliente"] == cliente_sel].copy()

        st.markdown(f"### Todos los productos comprados por {cliente_sel}")
        prods = dc.groupby(["Artículo", "Familia Artículo"], dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
        st.dataframe(prods, use_container_width=True)

        if dc["Fecha"].notna().any():
            hist = dc.groupby("Fecha")[metrica].sum().reset_index().sort_values("Fecha")
            fig = px.line(hist, x="Fecha", y=metrica, title=f"Histórico de {cliente_sel}")
            st.plotly_chart(fig, use_container_width=True, key="chart_historico_cliente_desde_articulo")

    if periodo_a and periodo_b:
        pa = df[df["Mes"] == periodo_a].groupby("Artículo")[metrica].sum()
        pb = df[df["Mes"] == periodo_b].groupby("Artículo")[metrica].sum()
        comp = pd.concat([pa, pb], axis=1).fillna(0)
        comp.columns = [periodo_a, periodo_b]
        comp["Var Abs"] = comp[periodo_b] - comp[periodo_a]
        comp["Var %"] = np.where(comp[periodo_a] != 0, comp["Var Abs"] / comp[periodo_a], 0)

        c4, c5 = st.columns(2)
        with c4:
            st.markdown("### Artículos que más cayeron")
            st.dataframe(comp.sort_values("Var Abs").head(20), use_container_width=True)
        with c5:
            st.markdown("### Artículos que más crecieron")
            st.dataframe(comp.sort_values("Var Abs", ascending=False).head(20), use_container_width=True)


def tab_historico_cliente(df, metrica):
    st.subheader("Histórico cliente")

    clientes = sorted([c for c in df["Cliente"].dropna().unique().tolist() if c != "nan"])
    if not clientes:
        st.info("No hay clientes.")
        return

    cliente_sel = st.selectbox("Elegí un cliente", clientes, key="historico_cliente_sel")
    d = df[df["Cliente"] == cliente_sel].copy()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Compras registradas", f"{len(d):,}")
    c2.metric("Productos distintos", f"{d['Artículo'].nunique():,}")
    c3.metric("Última fecha", str(d["Fecha"].max().date()) if d["Fecha"].notna().any() else "Sin fecha")
    c4.metric("Total métrica", f"{d[metrica].sum():,.2f}" if metrica != "Margen %" else "N/A")

    cols = [c for c in ["Fecha", "Mes", "Nro Comprobante", "Zona", "Vendedor", "Artículo", "Familia Artículo", "Kg", "Unidades", "Ventas", "Costo Total", "Margen $"] if c in d.columns]
    ordenado = d[cols].sort_values(by="Fecha", ascending=False) if d["Fecha"].notna().any() else d[cols]
    st.dataframe(ordenado, use_container_width=True)

    if d["Fecha"].notna().any():
        hist = d.groupby("Fecha")[metrica].sum().reset_index().sort_values("Fecha")
        fig = px.line(hist, x="Fecha", y=metrica, title=f"Histórico de {cliente_sel}")
        st.plotly_chart(fig, use_container_width=True, key="chart_historico_cliente_tab")
    else:
        hist = d.groupby("Mes")[metrica].sum().reset_index()
        fig = px.bar(hist, x="Mes", y=metrica, title=f"Histórico por mes de {cliente_sel}")
        st.plotly_chart(fig, use_container_width=True, key="chart_historico_cliente_mes")

    prods = d.groupby(["Artículo", "Familia Artículo"], dropna=False)[metrica].sum().reset_index().sort_values(by=metrica, ascending=False)
    st.markdown("### Mix de productos del cliente")
    st.dataframe(prods, use_container_width=True)


def tab_rentabilidad(df):
    st.subheader("Rentabilidad")

    ventas = df["Ventas"].sum()
    costo = df["Costo Total"].sum()
    margen = df["Margen $"].sum()
    margen_pct = safe_div(margen * 100, ventas)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas", f"{ventas:,.2f}")
    c2.metric("Costo Total", f"{costo:,.2f}")
    c3.metric("Margen $", f"{margen:,.2f}")
    c4.metric("Margen %", f"{margen_pct:,.2f}%")

    por_cliente = df.groupby("Cliente", dropna=False)[["Ventas", "Costo Total", "Margen $"]].sum().reset_index()
    por_cliente["Margen %"] = np.where(por_cliente["Ventas"] != 0, por_cliente["Margen $"] / por_cliente["Ventas"], 0)
    st.markdown("### Rentabilidad por cliente")
    st.dataframe(por_cliente.sort_values("Margen $", ascending=False), use_container_width=True)

    por_articulo = df.groupby(["Artículo", "Familia Artículo"], dropna=False)[["Ventas", "Costo Total", "Margen $"]].sum().reset_index()
    por_articulo["Margen %"] = np.where(por_articulo["Ventas"] != 0, por_articulo["Margen $"] / por_articulo["Ventas"], 0)
    st.markdown("### Rentabilidad por artículo")
    st.dataframe(por_articulo.sort_values("Margen $", ascending=False), use_container_width=True)


def tab_alertas(df, metrica, periodo_a, periodo_b):
    st.subheader("Alertas y hallazgos")

    if not periodo_a or not periodo_b:
        st.info("Necesitás dos meses para alertas comparativas.")
        return

    # Familias dependientes de un solo producto
    st.markdown("### Familias con dependencia alta de un solo producto")
    d = df[df["Mes"] == periodo_b].copy()
    fam_prod = d.groupby(["Familia Artículo", "Artículo"], dropna=False)[metrica].sum().reset_index()

    resultados = []
    for familia in fam_prod["Familia Artículo"].dropna().unique():
        temp = fam_prod[fam_prod["Familia Artículo"] == familia].copy()
        total = temp[metrica].sum()
        if total <= 0:
            continue
        top = temp.sort_values(by=metrica, ascending=False).iloc[0]
        share = safe_div(top[metrica], total)
        resultados.append({
            "Familia": familia,
            "Producto dominante": top["Artículo"],
            "Participación": share
        })

    out = pd.DataFrame(resultados)
    if not out.empty:
        st.dataframe(out.sort_values("Participación", ascending=False), use_container_width=True)
        riesgos = out[out["Participación"] >= 0.60]
        if not riesgos.empty:
            st.warning("Hay familias cuyo crecimiento o volumen depende demasiado de un solo producto.")
            st.dataframe(riesgos, use_container_width=True)

    # Clientes perdidos / muy caídos
    st.markdown("### Clientes fuertes en caída")
    ca = df[df["Mes"] == periodo_a].groupby("Cliente")[metrica].sum()
    cb = df[df["Mes"] == periodo_b].groupby("Cliente")[metrica].sum()
    comp = pd.concat([ca, cb], axis=1).fillna(0)
    comp.columns = [periodo_a, periodo_b]
    comp["Var Abs"] = comp[periodo_b] - comp[periodo_a]
    comp["Var %"] = np.where(comp[periodo_a] != 0, comp["Var Abs"] / comp[periodo_a], 0)

    fuertes = comp.sort_values(periodo_a, ascending=False).head(50)
    st.dataframe(fuertes.sort_values("Var Abs").head(20), use_container_width=True)

    # Productos perdidos
    st.markdown("### Productos con mayor caída")
    pa = df[df["Mes"] == periodo_a].groupby("Artículo")[metrica].sum()
    pb = df[df["Mes"] == periodo_b].groupby("Artículo")[metrica].sum()
    prod_comp = pd.concat([pa, pb], axis=1).fillna(0)
    prod_comp.columns = [periodo_a, periodo_b]
    prod_comp["Var Abs"] = prod_comp[periodo_b] - prod_comp[periodo_a]
    st.dataframe(prod_comp.sort_values("Var Abs").head(20), use_container_width=True)


# =========================================================
# MAIN
# =========================================================
files = st.file_uploader("Subí uno o más CSV", type=["csv"], accept_multiple_files=True)

if files:
    df = cargar_archivos(files)

    if df.empty:
        st.warning("No se pudieron cargar datos.")
        st.stop()

    df_f, metrica = aplicar_filtros(df)

    mostrar_kpis(df_f, metrica)
    periodo_a, periodo_b = comparacion_periodos(df_f, metrica)

    tabs = st.tabs([
        "Resumen",
        "Zonas",
        "Vendedores",
        "Clientes",
        "Artículos",
        "Histórico cliente",
        "Rentabilidad",
        "Alertas"
    ])

    with tabs[0]:
        tab_resumen(df_f, metrica)

    with tabs[1]:
        tab_zonas(df_f, metrica, periodo_a, periodo_b)

    with tabs[2]:
        tab_vendedores(df_f, metrica, periodo_a, periodo_b)

    with tabs[3]:
        tab_clientes(df_f, metrica, periodo_a, periodo_b)

    with tabs[4]:
        tab_articulos(df_f, metrica, periodo_a, periodo_b)

    with tabs[5]:
        tab_historico_cliente(df_f, metrica)

    with tabs[6]:
        tab_rentabilidad(df_f)

    with tabs[7]:
        tab_alertas(df_f, metrica, periodo_a, periodo_b)

else:
    st.info("Subí uno o más CSV para empezar.")