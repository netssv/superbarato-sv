"""
app.py - SuperBarato SV v0.16
==============================
3 tiendas: Selectos + Walmart + La Despensa de Don Juan
Tabla comparativa unificada con selectores desplegables inline.
Corre con: streamlit run app.py
"""

import time
import streamlit as st

from utils import (
    generar_recomendacion, determinar_mas_barato,
    generar_sugerencia_generica,
    TIENDA_LABELS, TIENDA_COLORS,
)
from scrapers import buscar_producto
from components import renderizar_gestor_productos

# ─── Configuracion de pagina ─────────────────────────────────────────────────
st.set_page_config(
    page_title="SuperBarato SV",
    page_icon="🛒",
    layout="wide",
)

# ─── Estilos ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stButton > button { min-height: 2.4rem; font-size: 1rem; border-radius: 10px; }
.stSelectbox > div > div { min-height: 2.2rem; }
.stTextInput > div > div > input { min-height: 2.2rem; font-size: 1rem; }
.tabla-header {
    font-weight: 700; font-size: 0.8rem; color: #555;
    border-bottom: 2px solid #ddd; padding-bottom: 6px; margin-bottom: 8px;
}
.oferta-badge {
    background: #27ae60; color: white; font-size: 0.7rem;
    padding: 1px 6px; border-radius: 8px; font-weight: 600;
}
.precio-grande { font-size: 1.2rem; font-weight: 800; color: #1a1a1a; }
.tienda-selectos { color: #c0392b; font-weight: 700; }
.tienda-walmart { color: #0071ce; font-weight: 700; }
.tienda-despensa { color: #e67e22; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# TITULO
# =============================================================================
st.title("SuperBarato SV")
st.caption(
    "Compara precios entre Super Selectos, Walmart y La Despensa de Don Juan. "
    "Agrega tus productos y encuentra donde te sale mas barato."
)
st.divider()


# =============================================================================
# ENTRADA DE PRODUCTOS
# =============================================================================
st.subheader("Tu lista de compras")
items_busqueda = renderizar_gestor_productos()
st.markdown("")
comparar = st.button("Comparar precios", use_container_width=True, type="primary")


# =============================================================================
# SESSION STATE
# =============================================================================
if "resultados" not in st.session_state:
    st.session_state.resultados = []
if "selecciones" not in st.session_state:
    st.session_state.selecciones = {}


# =============================================================================
# BUSQUEDA
# =============================================================================
if comparar:
    items_validos = [(txt, cat) for txt, cat in items_busqueda if txt.strip()]

    if not items_validos:
        st.warning("Agrega al menos un producto antes de comparar.")
    else:
        barra = st.progress(0, text="Buscando productos...")
        resultados = []
        selecciones_init = {}

        for i, (producto, categoria) in enumerate(items_validos):
            barra.progress(
                (i + 1) / len(items_validos),
                text=f"Buscando: {producto} ({i+1}/{len(items_validos)})",
            )
            try:
                resultado = buscar_producto(producto, categoria)
            except Exception:
                resultado = {
                    "producto_original": producto,
                    "categoria": categoria,
                    "selectos": None,
                    "walmart": None,
                    "despensa": None,
                    "mas_barato": "sin_datos",
                    "candidatos_selectos": [],
                    "candidatos_walmart": [],
                    "candidatos_despensa": [],
                    "es_generico": False,
                    "walmart_no_disponible": False,
                    "despensa_no_disponible": False,
                }
            resultados.append(resultado)
            selecciones_init[i] = {
                "selectos": resultado["selectos"],
                "walmart": resultado["walmart"],
                "despensa": resultado["despensa"],
            }
            if i < len(items_validos) - 1:
                time.sleep(0.3)

        barra.empty()
        st.session_state.resultados = resultados
        st.session_state.selecciones = selecciones_init


# =============================================================================
# HELPER: Generar opciones de selectbox para una tienda
# =============================================================================
def _opciones_tienda(candidatos):
    """Genera lista de opciones para selectbox a partir de candidatos."""
    return ["Sin seleccion"] + [
        (f"{c['nombre'][:48]}... - ${c['precio']:.2f}"
         if len(c["nombre"]) > 48 else f"{c['nombre']} - ${c['precio']:.2f}")
        for c in candidatos
    ]


def _indice_actual(candidatos, seleccion_actual):
    """Retorna el indice 1-based del candidato seleccionado."""
    if not seleccion_actual:
        return 0
    for j, c in enumerate(candidatos):
        if (c.get("nombre") == seleccion_actual.get("nombre")
                and c.get("tienda") == seleccion_actual.get("tienda")):
            return j + 1
    return 0


# =============================================================================
# RESULTADOS
# =============================================================================
if st.session_state.resultados:
    resultados = st.session_state.resultados
    selecciones = st.session_state.selecciones

    st.divider()

    # ─── Sugerencias para busquedas genericas ─────────────────────────────────
    for r in resultados:
        if r.get("es_generico"):
            st.info(generar_sugerencia_generica(r["producto_original"]))

    # ─── TABLA COMPARATIVA UNIFICADA con selectores inline ────────────────────
    st.subheader("Tabla comparativa")

    selecciones_nuevas = dict(selecciones)
    cambio = False

    # Encabezados (más compactos con 3 tiendas)
    h_prod, h_ps, h_pw, h_pd, h_mb = st.columns([2, 2.5, 2.5, 2.5, 0.8])
    with h_prod:
        st.markdown("<div class='tabla-header'>📷 Producto</div>", unsafe_allow_html=True)
    with h_ps:
        st.markdown("<div class='tabla-header tienda-selectos'>Super Selectos</div>", unsafe_allow_html=True)
    with h_pw:
        st.markdown("<div class='tabla-header tienda-walmart'>Walmart</div>", unsafe_allow_html=True)
    with h_pd:
        st.markdown("<div class='tabla-header tienda-despensa'>La Despensa</div>", unsafe_allow_html=True)
    with h_mb:
        st.markdown("<div class='tabla-header'>Mejor</div>", unsafe_allow_html=True)

    # Filas de datos con selectores inline
    for i, r in enumerate(resultados):
        sel = selecciones.get(i, {})
        sel_s = sel.get("selectos")
        sel_w = sel.get("walmart")
        sel_d = sel.get("despensa")

        c_prod, c_s, c_w, c_d, c_mb = st.columns([2, 2.5, 2.5, 2.5, 0.8])

        # ── Columna: Producto + imagen ──
        with c_prod:
            st.markdown(f"**{r['producto_original']}**")
            # Mostrar imagen del primer resultado disponible
            img_url = None
            for s in [sel_s, sel_w, sel_d]:
                if s and s.get("imagen"):
                    img_url = s["imagen"]
                    break
            if img_url:
                try:
                    st.image(img_url, width=50)
                except Exception:
                    pass

        # ── Columna: Super Selectos ──
        with c_s:
            cands_s = r.get("candidatos_selectos", [])
            if cands_s:
                opciones = _opciones_tienda(cands_s)
                idx = _indice_actual(cands_s, sel_s)
                elegido = st.selectbox(
                    "Selectos", opciones, index=idx,
                    key=f"tbl_s_{i}", label_visibility="collapsed",
                )
                nuevo_s = None
                if elegido != "Sin seleccion":
                    for j, op in enumerate(opciones[1:]):
                        if op == elegido:
                            nuevo_s = cands_s[j]
                            break
                if nuevo_s != sel_s:
                    selecciones_nuevas[i] = {**selecciones_nuevas.get(i, {}), "selectos": nuevo_s}
                    cambio = True
                # Mostrar precio/oferta del seleccionado
                actual_s = nuevo_s if nuevo_s != sel_s else sel_s
                if actual_s:
                    txt = f"<span class='precio-grande'>${actual_s['precio']:.2f}</span>"
                    if actual_s.get("es_oferta") and actual_s.get("precio_lista"):
                        ahorro = actual_s["precio_lista"] - actual_s["precio"]
                        txt += f"<br><span class='oferta-badge'>★ -{ahorro:.2f}</span>"
                    st.markdown(txt, unsafe_allow_html=True)
            else:
                st.caption("No encontrado")

        # ── Columna: Walmart ──
        with c_w:
            cands_w = r.get("candidatos_walmart", [])
            if cands_w:
                opciones = _opciones_tienda(cands_w)
                idx = _indice_actual(cands_w, sel_w)
                elegido = st.selectbox(
                    "Walmart", opciones, index=idx,
                    key=f"tbl_w_{i}", label_visibility="collapsed",
                )
                nuevo_w = None
                if elegido != "Sin seleccion":
                    for j, op in enumerate(opciones[1:]):
                        if op == elegido:
                            nuevo_w = cands_w[j]
                            break
                if nuevo_w != sel_w:
                    selecciones_nuevas[i] = {**selecciones_nuevas.get(i, {}), "walmart": nuevo_w}
                    cambio = True
                actual_w = nuevo_w if nuevo_w != sel_w else sel_w
                if actual_w:
                    txt = f"<span class='precio-grande'>${actual_w['precio']:.2f}</span>"
                    if actual_w.get("es_oferta") and actual_w.get("precio_lista"):
                        ahorro = actual_w["precio_lista"] - actual_w["precio"]
                        txt += f"<br><span class='oferta-badge'>★ -{ahorro:.2f}</span>"
                    st.markdown(txt, unsafe_allow_html=True)
            elif r.get("walmart_no_disponible"):
                st.caption("No disponible")
            else:
                st.caption("No encontrado")

        # ── Columna: La Despensa ──
        with c_d:
            cands_d = r.get("candidatos_despensa", [])
            if cands_d:
                opciones = _opciones_tienda(cands_d)
                idx = _indice_actual(cands_d, sel_d)
                elegido = st.selectbox(
                    "Despensa", opciones, index=idx,
                    key=f"tbl_d_{i}", label_visibility="collapsed",
                )
                nuevo_d = None
                if elegido != "Sin seleccion":
                    for j, op in enumerate(opciones[1:]):
                        if op == elegido:
                            nuevo_d = cands_d[j]
                            break
                if nuevo_d != sel_d:
                    selecciones_nuevas[i] = {**selecciones_nuevas.get(i, {}), "despensa": nuevo_d}
                    cambio = True
                actual_d = nuevo_d if nuevo_d != sel_d else sel_d
                if actual_d:
                    txt = f"<span class='precio-grande'>${actual_d['precio']:.2f}</span>"
                    if actual_d.get("es_oferta") and actual_d.get("precio_lista"):
                        ahorro = actual_d["precio_lista"] - actual_d["precio"]
                        txt += f"<br><span class='oferta-badge'>★ -{ahorro:.2f}</span>"
                    st.markdown(txt, unsafe_allow_html=True)
            elif r.get("despensa_no_disponible"):
                st.caption("No disponible")
            else:
                st.caption("No encontrado")

        # ── Columna: Mejor ──
        with c_mb:
            sel_actual_s = selecciones_nuevas.get(i, {}).get("selectos") or sel_s
            sel_actual_w = selecciones_nuevas.get(i, {}).get("walmart") or sel_w
            sel_actual_d = selecciones_nuevas.get(i, {}).get("despensa") or sel_d
            mb = determinar_mas_barato(sel_actual_s, sel_actual_w, sel_actual_d)
            if mb == "Selectos":
                st.markdown("<span class='tienda-selectos'>Selectos ✓</span>", unsafe_allow_html=True)
            elif mb == "Walmart":
                st.markdown("<span class='tienda-walmart'>Walmart ✓</span>", unsafe_allow_html=True)
            elif mb == "Despensa":
                st.markdown("<span class='tienda-despensa'>Despensa ✓</span>", unsafe_allow_html=True)
            elif mb == "Precio igual":
                st.caption("Igual")
            else:
                st.caption("–")

        st.divider()

    # Aplicar cambios de seleccion
    if cambio:
        st.session_state.selecciones = selecciones_nuevas
        st.rerun()

    # ─── Metricas ─────────────────────────────────────────────────────────────
    st.divider()
    rec = generar_recomendacion(resultados, selecciones)

    col_s, col_w, col_d, col_m = st.columns(4)
    with col_s:
        st.metric("Total en Selectos", f"${rec['total_selectos']:.2f}",
                  help=f"Basado en {rec['items_selectos']} producto(s)")
    with col_w:
        st.metric("Total en Walmart", f"${rec['total_walmart']:.2f}",
                  help=f"Basado en {rec['items_walmart']} producto(s)")
    with col_d:
        st.metric("Total en Despensa", f"${rec['total_despensa']:.2f}",
                  help=f"Basado en {rec['items_despensa']} producto(s)")
    with col_m:
        st.metric("Total mezcla optima", f"${rec['total_mezcla']:.2f}",
                  help="Comprando cada producto en la tienda mas barata")

    # ─── Recomendacion ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Recomendacion")

    en_wm = rec["productos_en_walmart"]
    en_sl = rec["productos_en_selectos"]
    en_dp = rec["productos_en_despensa"]

    if rec["items_sin_datos"] == len(resultados):
        st.error(
            "No se encontraron coincidencias claras. "
            "Intenta ser mas especifico o elige una categoria."
        )
    else:
        # Determinar si todo va a una sola tienda
        solo_una = sum([bool(en_wm), bool(en_sl), bool(en_dp)])

        if solo_una <= 1:
            if en_sl and not en_wm and not en_dp:
                msg = "Te conviene comprar TODO en Super Selectos."
                st.success(msg)
            elif en_wm and not en_sl and not en_dp:
                msg = "Te conviene comprar TODO en Walmart."
                st.success(msg)
            elif en_dp and not en_sl and not en_wm:
                msg = "Te conviene comprar TODO en La Despensa de Don Juan."
                st.success(msg)
            else:
                st.info("No se encontraron suficientes datos para una recomendacion clara.")
        else:
            txt = "Mezcla recomendada para ahorrar mas:\n\n"
            if en_wm:
                txt += f"- Compra en **Walmart**: {', '.join(en_wm)}\n"
            if en_sl:
                txt += f"- Compra en **Selectos**: {', '.join(en_sl)}\n"
            if en_dp:
                txt += f"- Compra en **La Despensa**: {', '.join(en_dp)}\n"

            ahorro_vs_s = rec["total_selectos"] - rec["total_mezcla"]
            ahorro_vs_w = rec["total_walmart"] - rec["total_mezcla"]
            ahorro_vs_d = rec["total_despensa"] - rec["total_mezcla"]
            txt += (
                f"\nAhorro estimado: ${ahorro_vs_s:.2f} vs Selectos, "
                f"${ahorro_vs_w:.2f} vs Walmart, "
                f"${ahorro_vs_d:.2f} vs La Despensa."
            )
            st.info(txt)

    # ─── Productos sin coincidencia ───────────────────────────────────────────
    no_enc = [
        r["producto_original"]
        for i, r in enumerate(resultados)
        if not selecciones.get(i, {}).get("selectos")
        and not selecciones.get(i, {}).get("walmart")
        and not selecciones.get(i, {}).get("despensa")
    ]
    if no_enc:
        st.warning(
            "Sin coincidencia clara para: "
            + ", ".join(no_enc)
            + ". Intenta ser mas especifico o elige una categoria."
        )


# ─── Pie de pagina ────────────────────────────────────────────────────────────
st.divider()
st.caption("SuperBarato SV v0.16 - Hecho en El Salvador")