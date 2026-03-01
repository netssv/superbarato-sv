"""
scrapers.py - SuperBarato SV v0.16
==================================
- Super Selectos: Playwright headless (Blazor site requiere JS rendering)
- Walmart: doble motor VTEX Catalog + Intelligent Search
- La Despensa de Don Juan: doble motor VTEX Catalog + Intelligent Search
- Filtrado por categoria, flag generico, timeout 20s
"""

import re
import requests
from urllib.parse import quote, quote_plus

from utils import (
    calcular_score_final,
    construir_query,
    extraer_cantidad_y_unidad,
    convertir_a_gramos,
    es_busqueda_generica,
    _filtrar_por_categoria,
    normalizar_texto,
    UMBRAL_SIMILITUD,
)

# ─── Headers ─────────────────────────────────────────────────────────────────
HEADERS_JSON = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-SV,es;q=0.9",
}

TIMEOUT = 20
MAX_RESULTADOS = 10
MAX_ALTERNATIVAS = 5

TEXTOS_BANNER = {
    "se te olvida", "olvida algo", "check-out", "checkout",
    "te puede interesar", "tambien te", "recomendado", "publicidad",
    "suscribete", "newsletter", "promocion especial", "exclusivas online",
    "no te lo pierdas",
}


def _es_texto_banner(texto):
    """True si el texto parece ser de un banner o seccion irrelevante."""
    if not texto:
        return True
    t = texto.lower().strip()
    if len(t) < 4:
        return True
    return any(b in t for b in TEXTOS_BANNER)


def _limpiar_url_imagen(url, base="https://www.superselectos.com"):
    """Normaliza una URL de imagen."""
    if not url:
        return None
    url = url.strip()
    if " " in url and "http" in url:
        url = url.split(",")[0].split()[0]
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base + url
    if not url.startswith("http"):
        return None
    if any(x in url.lower() for x in ["placeholder", "blank", "lazy.gif", "data:image", ".svg", "transparent"]):
        return None
    return url


def _normalizar_url_imagen_vtex(url):
    """Normaliza URLs de imagenes VTEX (Walmart / La Despensa)."""
    if not url:
        return None
    url = url.strip()
    # Asegurar HTTPS
    if url.startswith("//"):
        url = "https:" + url
    # Quitar parametros de tamaño para obtener imagen original
    url = re.sub(r'-\d+x\d+\.', '.', url)
    return url


# =============================================================================
# SCRAPING - SUPER SELECTOS (Playwright headless browser)
# =============================================================================

def buscar_selectos(texto_usuario, categoria=None):
    """
    Scraping de Super Selectos con Playwright (headless Chromium).
    El sitio usa Blazor WebAssembly, necesita JS rendering completo.
    """
    import subprocess, shutil
    # Auto-instalar Chromium si no esta disponible (necesario en Streamlit Cloud)
    if not shutil.which("chromium") and not shutil.which("chromium-browser"):
        try:
            subprocess.run(["playwright", "install", "--with-deps", "chromium"],
                           check=True, capture_output=True, timeout=120)
        except Exception:
            pass

    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    query = construir_query(texto_usuario, categoria)
    url_busqueda = f"https://www.superselectos.com/products?keyword={quote_plus(query)}"

    cant_u, un_u = extraer_cantidad_y_unidad(texto_usuario)
    cant_g = convertir_a_gramos(cant_u, un_u)
    productos = []
    vistos = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url_busqueda, wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")

    # ─── Estrategia principal: li.item-producto en ul.listado-productos ────────
    lista_productos = soup.find("ul", class_=re.compile(r"listado.?productos", re.I))
    items = []
    if lista_productos:
        items = lista_productos.find_all("li", class_=re.compile(r"item.?producto", re.I))

    if not items:
        items = soup.find_all("li", class_=re.compile(r"item.?producto", re.I))

    for item in items:
        if len(productos) >= MAX_RESULTADOS:
            break

        # Nombre del producto en h5.prod-nombre > a.clickeable
        h5 = item.find("h5", class_=re.compile(r"prod.?nombre", re.I))
        if not h5:
            continue
        enlace = h5.find("a", class_="clickeable")
        nombre = enlace.get_text(strip=True) if enlace else h5.get_text(strip=True)
        if not nombre or len(nombre) < 5:
            continue
        if _es_texto_banner(nombre):
            continue
        if nombre.lower() in vistos:
            continue
        vistos.add(nombre.lower())

        # URL
        href = ""
        if enlace:
            href = enlace.get("href", "")
        url_prod = href if href.startswith("http") else f"https://www.superselectos.com{href}" if href else url_busqueda

        # ─── Precios: selectores exactos de Super Selectos ─────────────────────
        # Estructura real del HTML (Blazor WebAssembly):
        #   div.precios
        #     div.lside     -> contiene: $17.55 (actual) + $20.71 (lista)
        #     span.antes    -> $20.71 (precio original, tachado)
        #     span.ahorro   -> $3.16 (monto de ahorro, NO es precio)
        # Sin oferta: div.precios solo tiene el precio actual
        info_prod = item.find("div", class_=re.compile(r"info.?prod", re.I)) or item

        precio = None
        precio_lista = None

        # 1) Buscar span.antes = precio lista/original (tachado)
        span_antes = info_prod.find("span", class_="antes")
        if span_antes:
            nums = re.findall(r"\$?([\d]+\.?\d*)", span_antes.get_text())
            if nums:
                precio_lista = float(nums[0])

        # 2) Buscar div.lside = contiene precio actual (+ puede tener lista)
        div_lside = info_prod.find("div", class_="lside")
        if div_lside:
            # Extraer precios del lside, EXCLUYENDO span.antes si esta dentro
            texto_lside = div_lside.get_text(separator=" ", strip=True)
            precios_lside = re.findall(r"\$([\d]+\.?\d*)", texto_lside)
            vals_lside = [float(v) for v in precios_lside if 0.01 <= float(v) <= 5000]

            if vals_lside:
                if precio_lista and len(vals_lside) >= 2:
                    # El precio actual es el que NO es el precio_lista
                    for v in vals_lside:
                        if abs(v - precio_lista) > 0.01:
                            precio = v
                            break
                    if precio is None:
                        precio = vals_lside[0]
                elif len(vals_lside) >= 2:
                    # Sin span.antes: menor es actual, mayor es lista
                    sorted_v = sorted(vals_lside)
                    precio = sorted_v[0]
                    precio_lista = sorted_v[-1] if sorted_v[-1] > sorted_v[0] * 1.01 else None
                else:
                    precio = vals_lside[0]

        # 3) Fallback: div.precios excluyendo span.ahorro
        if precio is None:
            div_precios = info_prod.find("div", class_="precios")
            bloque = div_precios if div_precios else info_prod

            # Remover span.ahorro antes de extraer (es monto de ahorro, no precio)
            for ahorro_tag in bloque.find_all("span", class_="ahorro"):
                ahorro_tag.decompose()

            texto_precios = bloque.get_text(separator=" ", strip=True)
            precios_raw = re.findall(r"\$([\d]+\.?\d*)", texto_precios)
            vals = sorted([float(v) for v in precios_raw if 0.01 <= float(v) <= 5000])

            if not vals:
                continue

            if len(vals) >= 2:
                precio = vals[0]
                precio_lista = vals[-1] if vals[-1] > vals[0] * 1.01 else None
            else:
                precio = vals[0]

        if precio is None:
            continue

        # Validar que precio_lista sea mayor que precio (si existe)
        if precio_lista is not None:
            if precio_lista <= precio * 1.01:
                precio_lista = None  # No es realmente una oferta

        es_oferta = bool(precio_lista and precio_lista > precio * 1.01)

        # Imagen
        img_url = None
        for img_tag in item.find_all("img"):
            for attr in ["src", "data-src", "data-lazy-src"]:
                val = img_tag.get(attr, "")
                if val and ("bitworks" in val or "superselectos" in val):
                    img_url = _limpiar_url_imagen(val)
                    if img_url:
                        break
            if img_url:
                break

        score = calcular_score_final(texto_usuario, nombre, cant_g, categoria)

        productos.append({
            "nombre": nombre,
            "precio": precio,
            "precio_lista": precio_lista,
            "es_oferta": es_oferta,
            "url": url_prod,
            "imagen": img_url,
            "similitud": score,
            "tienda": "Selectos",
        })

    # Filtrado por categoria
    productos = _filtrar_por_categoria(productos, categoria)
    productos.sort(key=lambda x: x["similitud"], reverse=True)
    return productos[:MAX_RESULTADOS]


# =============================================================================
# PARSING VTEX COMUN (reutilizado por Walmart y La Despensa)
# =============================================================================

def _parsear_vtex_productos(datos, texto_usuario, categoria, tienda_label, base_url=""):
    """
    Parsea la respuesta JSON de VTEX (Catalog o Intelligent Search)
    y retorna lista de productos normalizados.
    Funciona para Walmart y La Despensa (misma estructura VTEX).
    """
    if not datos or not isinstance(datos, list):
        return []

    cant_u, un_u = extraer_cantidad_y_unidad(texto_usuario)
    cant_g = convertir_a_gramos(cant_u, un_u)
    productos = []

    for item in datos[:MAX_RESULTADOS]:
        nombre = item.get("productName", "")

        # Link: puede venir como 'link' (catalog) o 'linkText' (intelligent)
        enlace = item.get("link", "")
        if not enlace:
            link_text = item.get("linkText", "")
            enlace = f"{base_url}/{link_text}/p" if link_text else ""

        precio = None
        precio_lista = None
        img_url = None
        items_list = item.get("items", [])

        if items_list:
            first_item = items_list[0]
            sellers = first_item.get("sellers", [])
            if sellers:
                oferta = sellers[0].get("commertialOffer", {})
                precio = oferta.get("Price") or oferta.get("ListPrice")
                precio_lista = oferta.get("ListPrice")
                if precio == 0:
                    precio = precio_lista

            imagenes = first_item.get("images", [])
            if imagenes:
                img_url = _normalizar_url_imagen_vtex(imagenes[0].get("imageUrl"))

        if precio is None or float(precio) <= 0:
            continue

        precio = float(precio)
        precio_lista = float(precio_lista) if precio_lista else None
        es_oferta = bool(precio_lista and precio < precio_lista * 0.99)

        score = calcular_score_final(texto_usuario, nombre, cant_g, categoria)

        productos.append({
            "nombre": nombre,
            "precio": precio,
            "precio_lista": precio_lista,
            "es_oferta": es_oferta,
            "url": enlace,
            "imagen": img_url,
            "similitud": score,
            "tienda": tienda_label,
        })

    productos = _filtrar_por_categoria(productos, categoria)
    productos.sort(key=lambda x: x["similitud"], reverse=True)
    return productos


# =============================================================================
# SCRAPING - WALMART (Motor 1: VTEX Catalog API)
# =============================================================================

def buscar_walmart_vtex(texto_usuario, categoria=None):
    """VTEX Catalog API (responde 206 con datos reales)."""
    query = construir_query(texto_usuario, categoria)
    url = (
        f"https://www.walmart.com.sv/api/catalog_system/pub/products/search/"
        f"{quote(query, safe='')}?_from=0&_to={MAX_RESULTADOS - 1}"
    )

    try:
        resp = requests.get(url, headers=HEADERS_JSON, timeout=TIMEOUT)
        if resp.status_code not in (200, 206):
            return []
        datos = resp.json()
    except (requests.RequestException, ValueError):
        return []

    return _parsear_vtex_productos(datos, texto_usuario, categoria, "Walmart",
                                    base_url="https://www.walmart.com.sv")


# =============================================================================
# SCRAPING - WALMART (Motor 2: Intelligent Search API)
# =============================================================================

def buscar_walmart_intelligent(texto_usuario, categoria=None):
    """VTEX Intelligent Search API con parametro ?query=."""
    query = construir_query(texto_usuario, categoria)
    url = (
        f"https://www.walmart.com.sv/api/io/_v/api/intelligent-search/"
        f"product_search/?query={quote_plus(query)}&page=1&count={MAX_RESULTADOS}&locale=es-SV"
    )

    try:
        resp = requests.get(url, headers=HEADERS_JSON, timeout=TIMEOUT)
        resp.raise_for_status()
        datos = resp.json()
    except (requests.RequestException, ValueError):
        return []

    products = datos.get("products", [])
    return _parsear_vtex_productos(products, texto_usuario, categoria, "Walmart",
                                    base_url="https://www.walmart.com.sv")


# =============================================================================
# SCRAPING - LA DESPENSA DE DON JUAN (Motor 1: VTEX Catalog API)
# =============================================================================

def buscar_despensa_vtex(texto_usuario, categoria=None):
    """La Despensa - VTEX Catalog API."""
    query = construir_query(texto_usuario, categoria)
    url = (
        f"https://www.ladespensadedonjuan.com.sv/api/catalog_system/pub/products/search/"
        f"{quote(query, safe='')}?_from=0&_to={MAX_RESULTADOS - 1}"
    )

    try:
        resp = requests.get(url, headers=HEADERS_JSON, timeout=TIMEOUT)
        if resp.status_code not in (200, 206):
            return []
        datos = resp.json()
    except (requests.RequestException, ValueError):
        return []

    return _parsear_vtex_productos(datos, texto_usuario, categoria, "Despensa",
                                    base_url="https://www.ladespensadedonjuan.com.sv")


# =============================================================================
# SCRAPING - LA DESPENSA DE DON JUAN (Motor 2: Intelligent Search API)
# =============================================================================

def buscar_despensa_intelligent(texto_usuario, categoria=None):
    """La Despensa - VTEX Intelligent Search API."""
    query = construir_query(texto_usuario, categoria)
    url = (
        f"https://www.ladespensadedonjuan.com.sv/api/io/_v/api/intelligent-search/"
        f"product_search/?query={quote_plus(query)}&page=1&count={MAX_RESULTADOS}&locale=es-SV"
    )

    try:
        resp = requests.get(url, headers=HEADERS_JSON, timeout=TIMEOUT)
        resp.raise_for_status()
        datos = resp.json()
    except (requests.RequestException, ValueError):
        return []

    products = datos.get("products", [])
    return _parsear_vtex_productos(products, texto_usuario, categoria, "Despensa",
                                    base_url="https://www.ladespensadedonjuan.com.sv")


# =============================================================================
# COMBINAR RESULTADOS DE DOBLE MOTOR (reutilizable)
# =============================================================================

def _combinar_doble_motor(todos_w1, todos_w2):
    """Combina y deduplica resultados de 2 motores VTEX."""
    vistos = set()
    combinados = []
    for p in sorted(todos_w1 + todos_w2, key=lambda x: x["similitud"], reverse=True):
        nombre_norm = normalizar_texto(p["nombre"])
        if nombre_norm not in vistos:
            vistos.add(nombre_norm)
            combinados.append(p)
        if len(combinados) >= MAX_RESULTADOS:
            break
    return combinados


# =============================================================================
# BUSQUEDA COMBINADA (3 tiendas)
# =============================================================================

def buscar_producto(texto_usuario, categoria=None):
    """
    Busca en 3 tiendas:
    - Super Selectos con Playwright (headless browser)
    - Walmart con doble motor (VTEX Catalog + Intelligent Search)
    - La Despensa de Don Juan con doble motor VTEX
    """
    # ─── Super Selectos ──────────────────────────────────────────────────────
    todos_s = buscar_selectos(texto_usuario, categoria)
    con_s = [p for p in todos_s if p["similitud"] >= UMBRAL_SIMILITUD]
    sin_s = [p for p in todos_s if p["similitud"] < UMBRAL_SIMILITUD]

    # ─── Walmart: doble motor ─────────────────────────────────────────────────
    todos_w1 = buscar_walmart_vtex(texto_usuario, categoria)
    todos_w2 = buscar_walmart_intelligent(texto_usuario, categoria)
    todos_w = _combinar_doble_motor(todos_w1, todos_w2)

    con_w = [p for p in todos_w if p["similitud"] >= UMBRAL_SIMILITUD]
    sin_w = [p for p in todos_w if p["similitud"] < UMBRAL_SIMILITUD]

    # ─── La Despensa: doble motor ─────────────────────────────────────────────
    todos_d1 = buscar_despensa_vtex(texto_usuario, categoria)
    todos_d2 = buscar_despensa_intelligent(texto_usuario, categoria)
    todos_d = _combinar_doble_motor(todos_d1, todos_d2)

    con_d = [p for p in todos_d if p["similitud"] >= UMBRAL_SIMILITUD]
    sin_d = [p for p in todos_d if p["similitud"] < UMBRAL_SIMILITUD]

    # ─── Seleccionar mejores ─────────────────────────────────────────────────
    sel_s = con_s[0] if con_s else None
    sel_w = con_w[0] if con_w else None
    sel_d = con_d[0] if con_d else None

    walmart_no_disponible = (not todos_w1 and not todos_w2)
    despensa_no_disponible = (not todos_d1 and not todos_d2)

    # Mas barato
    precios = {}
    if sel_s:
        precios["selectos"] = sel_s["precio"]
    if sel_w:
        precios["walmart"] = sel_w["precio"]
    if sel_d:
        precios["despensa"] = sel_d["precio"]

    if precios:
        mas_barato = min(precios, key=precios.get)
    else:
        mas_barato = "sin_datos"

    todos_candidatos = todos_s + todos_w + todos_d
    generico = es_busqueda_generica(texto_usuario, todos_candidatos)

    return {
        "producto_original": texto_usuario,
        "categoria": categoria,
        "selectos": sel_s,
        "walmart": sel_w,
        "despensa": sel_d,
        "mas_barato": mas_barato,
        "candidatos_selectos": (con_s + sin_s)[:MAX_ALTERNATIVAS],
        "candidatos_walmart": (con_w + sin_w)[:MAX_ALTERNATIVAS],
        "candidatos_despensa": (con_d + sin_d)[:MAX_ALTERNATIVAS],
        "es_generico": generico,
        "walmart_no_disponible": walmart_no_disponible,
        "despensa_no_disponible": despensa_no_disponible,
    }
