"""
components.py - SuperBarato SV v0.16
=====================================
Iteracion 14: Gestor de productos + badge oferta.
Los selectores de alternativas ahora estan inline en la tabla (app.py).
"""

import streamlit as st
from utils import LISTA_CATEGORIAS_PRINCIPALES, normalizar_texto


# =============================================================================
# BADGE DE OFERTA (verde, solo ahorro real)
# =============================================================================

def badge_oferta(precio, precio_lista):
    """Badge verde con ahorro real, sin porcentaje."""
    if precio_lista and precio_lista > precio * 1.01:
        ahorro = precio_lista - precio
        st.markdown(
            f"<span style='"
            f"background:#27ae60;color:white;font-size:0.75rem;"
            f"font-weight:700;padding:2px 8px;border-radius:12px;"
            f"letter-spacing:0.5px;'>"
            f"&#9733; EN OFERTA! Ahorras ${ahorro:.2f}"
            f"</span>",
            unsafe_allow_html=True,
        )


# =============================================================================
# GESTOR DINAMICO DE PRODUCTOS (solo fields, sin pegar lista)
# =============================================================================

def inicializar_lista_productos():
    """Inicializa en session_state la lista de productos si aun no existe."""
    if "lista_productos" not in st.session_state:
        st.session_state.lista_productos = [
            {"texto": "", "categoria": "(sin categoria)"}
        ]


def agregar_producto():
    """Agrega una fila vacia a la lista de productos."""
    st.session_state.lista_productos.append(
        {"texto": "", "categoria": "(sin categoria)"}
    )


def eliminar_producto(idx):
    """Elimina el producto en la posicion idx."""
    lst = st.session_state.lista_productos
    if len(lst) > 1:
        lst.pop(idx)
    else:
        lst[0] = {"texto": "", "categoria": "(sin categoria)"}


def renderizar_gestor_productos():
    """
    Gestor dinamico touch-friendly de productos.
    Solo fields dinamicos: texto + categoria principal (sin subcategorias).
    Devuelve lista de tuples (texto_producto, categoria_principal).
    """
    inicializar_lista_productos()

    # ─── Filas de productos ───────────────────────────────────────────────────
    lista = st.session_state.lista_productos

    for i, prod in enumerate(lista):
        col_txt, col_cat, col_del = st.columns([3, 2, 0.5])

        with col_txt:
            nuevo_texto = st.text_input(
                label=f"Producto {i+1}",
                value=prod["texto"],
                placeholder="ej: leche de almendras, cafe juan valdez",
                key=f"prod_txt_{i}",
                label_visibility="collapsed",
            )
            lista[i]["texto"] = nuevo_texto

        with col_cat:
            idx_cat = (LISTA_CATEGORIAS_PRINCIPALES.index(prod["categoria"])
                       if prod["categoria"] in LISTA_CATEGORIAS_PRINCIPALES else 0)
            nueva_cat = st.selectbox(
                label="Categoria",
                options=LISTA_CATEGORIAS_PRINCIPALES,
                index=idx_cat,
                key=f"prod_cat_{i}",
                label_visibility="collapsed",
            )
            lista[i]["categoria"] = nueva_cat

        with col_del:
            if st.button("X", key=f"del_{i}", help="Eliminar este producto",
                         use_container_width=True):
                eliminar_producto(i)
                st.rerun()

    # ─── Boton Agregar ────────────────────────────────────────────────────────
    st.markdown("")
    if st.button("+ Agregar producto", use_container_width=False, type="secondary"):
        agregar_producto()
        st.rerun()

    # ─── Construir lista para busqueda ────────────────────────────────────────
    items_busqueda = []
    for prod in lista:
        texto = prod["texto"].strip()
        if not texto:
            continue

        cat = prod["categoria"]
        # Si es "(sin categoria)" o "Otros", busqueda general (None)
        cat_para_busqueda = None
        if cat and cat != "(sin categoria)" and normalizar_texto(cat) != "otros":
            cat_para_busqueda = cat

        items_busqueda.append((texto, cat_para_busqueda))

    return items_busqueda


# Iteracion 14 - selectores de alternativas movidos a tabla inline en app.py
