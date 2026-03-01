"""
utils.py - SuperBarato SV
=========================
Iteracion 13b: Fix matching - query sin conectores, todas las palabras
clave deben estar presentes, umbral 75.
"""

import re
from rapidfuzz import fuzz


# =============================================================================
# CONECTORES A OMITIR
# =============================================================================

CONECTORES = {
    "de", "del", "con", "sin", "entre", "a", "al", "el", "la", "los", "las",
    "un", "una", "por", "para", "en", "y", "o", "e", "que", "como",
}


# =============================================================================
# NORMALIZACION
# =============================================================================

def normalizar_texto(texto):
    """Pasa a minusculas, quita acentos, normaliza unidades y caracteres especiales."""
    texto = texto.lower().strip()
    for orig, rep in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","ü":"u"}.items():
        texto = texto.replace(orig, rep)
    texto = re.sub(r"\blbs?\b", "libra", texto)
    texto = re.sub(r"\blibras\b", "libra", texto)
    texto = re.sub(r"\bkgs?\b", "kilo", texto)
    texto = re.sub(r"\bkilos\b", "kilo", texto)
    texto = re.sub(r"\bml\b", "mililitro", texto)
    texto = re.sub(r"\blitros?\b", "litro", texto)
    texto = re.sub(r"\bozs?\b", "onza", texto)
    texto = re.sub(r"\bonzas\b", "onza", texto)
    texto = re.sub(r"\bgramos?\b", "gramo", texto)
    texto = re.sub(r"\bunds?\b", "unidad", texto)
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


# =============================================================================
# EQUIVALENCIAS APROXIMADAS DE UNIDADES
# =============================================================================

EQUIVALENCIAS_UNIDADES = {
    "1 litro": ["1lt", "1000ml", "946ml", "1000 mililitro"],
    "1lt": ["1 litro", "1000ml", "946ml"],
    "1000ml": ["1 litro", "1lt", "946ml"],
    "946ml": ["1 litro", "1lt", "1000ml"],
    "500ml": ["500 mililitro", "0.5 litro", "medio litro"],
    "medio litro": ["500ml", "500 mililitro"],
    "1 libra": ["1lb", "454g", "453g", "454 gramo"],
    "1lb": ["1 libra", "454g", "453g"],
    "5 libra": ["5lb", "2268g", "2268 gramo", "2.27 kilo"],
    "5lb": ["5 libra", "2268g"],
    "2 libra": ["2lb", "907g", "908g"],
    "2lb": ["2 libra", "907g", "908g"],
    "1 kilo": ["1000g", "1000 gramo", "2.2 libra", "1kg"],
    "1kg": ["1 kilo", "1000g"],
    "2 kilo": ["2000g", "2kg"],
    "12 onza": ["12oz", "340g", "355ml"],
    "16 onza": ["16oz", "454g", "473ml"],
}


def _expandir_unidades(texto):
    """Expande abreviaciones de unidades a sus equivalencias para mejor matching."""
    norm = normalizar_texto(texto)
    for patron, equivalentes in EQUIVALENCIAS_UNIDADES.items():
        patron_norm = normalizar_texto(patron)
        if patron_norm in norm:
            return norm + " " + " ".join(normalizar_texto(e) for e in equivalentes)
    return norm


# =============================================================================
# CONVERSIONES
# =============================================================================

CONVERSIONES_A_GRAMOS = {
    "libra": 453.6, "lb": 453.6, "kilo": 1000.0, "kg": 1000.0,
    "onza": 28.35,  "oz": 28.35,  "gramo": 1.0,   "g": 1.0,
    "litro": 1000.0,"l": 1000.0,  "mililitro": 1.0,"ml": 1.0,
}


def extraer_cantidad_y_unidad(texto):
    """Extrae (cantidad_float, unidad_normalizada) de un texto de producto."""
    patron = re.search(
        r"(\d+\.?\d*)\s*(libra|kilo|litro|mililitro|onza|gramo|unidad)",
        normalizar_texto(texto),
    )
    if patron:
        return float(patron.group(1)), patron.group(2)
    return None, None


def convertir_a_gramos(cantidad, unidad):
    """Convierte cantidad+unidad a gramos para comparacion entre productos."""
    if cantidad is None or unidad is None:
        return None
    factor = CONVERSIONES_A_GRAMOS.get(unidad)
    return cantidad * factor if factor else None


# =============================================================================
# EXTRACCION DE PALABRAS CLAVE Y PALABRA LARGA
# =============================================================================

_PALABRAS_UNIDAD = {
    "libra","kilo","litro","mililitro","onza","gramo","unidad",
    "pack","paquete","bolsa","botella","lata","caja",
}


def extraer_palabras_clave(texto_usuario):
    """Extrae las palabras significativas del query del usuario (sin conectores ni unidades).
    Retorna una lista ordenada de mayor a menor longitud (palabra larga primero)."""
    palabras = {p for p in normalizar_texto(texto_usuario).split()
                if not p.isdigit() and len(p) >= 3 and p not in CONECTORES and p not in _PALABRAS_UNIDAD}
    return sorted(palabras, key=len, reverse=True)


def extraer_palabra_larga(texto_usuario):
    """
    Identifica la palabra significativa mas larga del query.
    Ej: 'Leche de almendras' -> 'almendras'
    Ej: 'cafe juan valdez'   -> 'valdez'
    """
    palabras = extraer_palabras_clave(texto_usuario)
    return palabras[0] if palabras else None


def limpiar_query_para_busqueda(texto_usuario):
    """
    Limpia el texto del usuario quitando conectores para enviar a tiendas.
    'leche de almendras' -> 'leche almendras'
    'cafe juan valdez' -> 'cafe juan valdez' (sin conectores que quitar)
    """
    norm = normalizar_texto(texto_usuario)
    palabras = norm.split()
    limpias = [p for p in palabras if p not in CONECTORES or len(p) > 3]
    return " ".join(limpias) if limpias else texto_usuario


# =============================================================================
# MARCAS CONOCIDAS
# =============================================================================

MARCAS_CONOCIDAS = {
    "juan valdez", "nescafe", "colgate", "palmolive", "campero",
    "pilsener", "golden", "supremo", "la constancia", "diana",
    "dona blanca", "naturas", "sabemas", "del monte", "maggi",
    "knorr", "kraft", "nestle", "kelloggs", "lactolac",
    "colcafe", "toscafe", "musun", "lido", "salud",
}


def _detectar_marca(texto):
    """Detecta si el texto del usuario contiene una marca conocida."""
    norm = normalizar_texto(texto)
    for marca in MARCAS_CONOCIDAS:
        if marca in norm:
            return marca
    return None


# =============================================================================
# PALABRAS PROHIBIDAS POR CATEGORIA
# =============================================================================

PALABRAS_PROHIBIDAS = {
    "aceite":  {"sardina","atun","tuna","crema","jabon","shampoo","cabello",
                "johnson","bebe","corporal","masaje","bronceador"},
    "leche":   {"crema","jabon","shampoo","corporal","limpiador","facial",
                "contenedor","babaria","goma","chicle","mascar"},
    "arroz":   {"galleta","cereal","snack","salpor","horchata","vino"},
    "pollo":   {"caldo","cubito","sazon","consomme","sopa"},
    "frijol":  {"salsa","dip"},
    "azucar":  {"cereal","galleta","chocolate"},
    "huevo":   {"shampoo","mascarilla","tratamiento"},
}


def obtener_prohibidas(texto_usuario, categoria=None):
    """Junta las palabras prohibidas que aplican al query y/o la categoria."""
    norm = normalizar_texto(texto_usuario)
    prohibidas = set()
    for clave, malas in PALABRAS_PROHIBIDAS.items():
        if clave in norm:
            prohibidas.update(malas)
    if categoria:
        cat_norm = normalizar_texto(categoria)
        for clave, malas in PALABRAS_PROHIBIDAS.items():
            if clave in cat_norm:
                prohibidas.update(malas)
    return prohibidas


def tiene_palabra_prohibida(nombre, prohibidas):
    """True si el nombre del producto contiene alguna palabra prohibida."""
    if not prohibidas:
        return False
    return any(p in normalizar_texto(nombre) for p in prohibidas)


def contiene_palabras_clave(nombre_producto, palabras_clave):
    """
    Verifica que el nombre del producto contenga TODAS las palabras clave.
    Si tiene 1 palabra clave: debe contenerla.
    Si tiene 2+: debe contener al menos 2, incluyendo siempre la mas larga.
    Retorna (cumple: bool, porcentaje_match: float).
    """
    if not palabras_clave:
        return True, 1.0
    norm = normalizar_texto(nombre_producto)
    # palabras_clave ya viene ordenada de mayor a menor longitud
    presentes = [p for p in palabras_clave if p in norm]
    porcentaje = len(presentes) / len(palabras_clave) if palabras_clave else 0

    if len(palabras_clave) == 1:
        return len(presentes) >= 1, porcentaje

    # 2+ palabras: la mas larga (primera) debe estar presente
    palabra_larga = palabras_clave[0]
    tiene_larga = palabra_larga in norm

    if not tiene_larga:
        return False, porcentaje

    # Con la larga presente, al menos 50% del resto
    if len(palabras_clave) >= 2:
        return len(presentes) >= 2, porcentaje

    return True, porcentaje


# =============================================================================
# KEYWORDS POR CATEGORIA (para filtrado interno)
# =============================================================================

KEYWORDS_CATEGORIA = {
    "bebidas":             {"bebida", "litro", "mililitro", "botella", "lata", "jugo",
                            "refresco", "agua", "cafe", "te", "gaseosa"},
    "granos y cereales":   {"grano", "arroz", "cereal", "avena", "maiz", "trigo",
                            "harina", "libra", "kilo"},
    "lacteos y alternativas": {"leche", "queso", "crema", "yogur", "mantequilla",
                                "lacteo", "litro", "mililitro", "almendra"},
    "aceites y grasas":    {"aceite", "manteca", "margarina", "grasa", "litro", "mililitro"},
    "carnes y pescados":   {"carne", "pollo", "res", "cerdo", "atun", "salmon",
                            "pescado", "libra", "kilo"},
    "snacks":              {"galleta", "snack", "papitas", "cereal", "barra", "chip",
                            "dulce", "chocolat"},
    "limpieza":            {"detergente", "suavizante", "lavaplatos", "desinfectante",
                            "jabon", "limpia", "escoba", "cloro"},
    "otros":               set(),
}


def _filtrar_por_categoria(productos, categoria):
    """
    Filtrado interno por categoria.
    Si el usuario elige una categoria, solo acepta resultados que contengan
    al menos una keyword relacionada con esa categoria.
    """
    if not categoria or _es_categoria_general(categoria):
        return productos

    cat_norm = normalizar_texto(categoria)
    keywords = None
    for cat_key, kws in KEYWORDS_CATEGORIA.items():
        if cat_key in cat_norm or cat_norm in cat_key:
            keywords = kws
            break

    if not keywords:
        return productos

    filtrados = []
    for p in productos:
        nombre_norm = normalizar_texto(p["nombre"])
        if any(kw in nombre_norm for kw in keywords):
            filtrados.append(p)

    return filtrados if filtrados else productos


# =============================================================================
# DETECCION DE CATEGORIA NO ENCAJADA
# =============================================================================

_CATEGORIAS_COMPATIBLES = {
    "cafe": {"bebidas", "cafe", "cafe y te", "te"},
    "te": {"bebidas", "cafe y te", "te"},
    "leche": {"lacteos", "lacteos y alternativas", "leche"},
    "queso": {"lacteos", "lacteos y alternativas"},
    "yogur": {"lacteos", "lacteos y alternativas"},
    "arroz": {"granos", "granos y cereales", "granos y arroz"},
    "frijol": {"frijoles", "frijoles y legumbres", "legumbres"},
    "aceite": {"aceites", "aceites y grasas", "grasas"},
    "pollo": {"carnes", "carnes y pescados"},
    "carne": {"carnes", "carnes y pescados"},
    "atun": {"carnes", "carnes y pescados", "pescados"},
    "agua": {"bebidas"},
    "jugo": {"bebidas"},
    "refresco": {"bebidas"},
    "galleta": {"snacks", "snacks y galletas"},
    "detergente": {"limpieza", "limpieza y hogar"},
    "jabon": {"limpieza", "limpieza y hogar"},
    "almendras": {"lacteos", "lacteos y alternativas"},
}


def _categoria_encaja_con_producto(texto_usuario, categoria):
    """Verifica si la categoria elegida encaja con el producto."""
    if not categoria:
        return True
    cat_norm = normalizar_texto(categoria)
    prod_norm = normalizar_texto(texto_usuario)
    prod_palabras = prod_norm.split()

    for palabra in prod_palabras:
        if palabra in _CATEGORIAS_COMPATIBLES:
            cats_ok = _CATEGORIAS_COMPATIBLES[palabra]
            if any(c in cat_norm for c in cats_ok):
                return True
            return False

    return True


def _es_categoria_general(categoria):
    """True si la categoria es 'Otros', vacia o generica."""
    if not categoria:
        return True
    norm = normalizar_texto(categoria)
    return norm in ("otro", "otros", "general", "sin categoria", "sin subcategoria", "")


# =============================================================================
# SCORING - Verifica TODAS las palabras clave presentes
# =============================================================================

def calcular_score_final(texto_usuario, nombre_producto, cantidad_g=None, categoria=None):
    """
    Score mejorado:
      1. Verifica que TODAS las palabras clave del query esten en el producto.
         Si falta la palabra mas larga: score = 0 (descartado).
         Si faltan otras: penalizacion fuerte.
      2. Base: maximo de fuzzy metrics
      3. +20 bonus si la palabra larga esta presente
      4. Coincidencias aproximadas de unidades
      5. Prohibidas, marca, categoria, cantidad
    Rango: 0-100.
    """
    nu = normalizar_texto(texto_usuario)
    np_ = normalizar_texto(nombre_producto)

    # PASO 1: Verificar palabras clave obligatorias
    palabras_clave = extraer_palabras_clave(texto_usuario)
    cumple, porcentaje = contiene_palabras_clave(nombre_producto, palabras_clave)

    if not cumple:
        # Si no contiene las palabras clave esenciales, score muy bajo
        return max(0, int(porcentaje * 30))

    # Expandir unidades para matching aproximado
    nu_exp = _expandir_unidades(texto_usuario)
    np_exp = _expandir_unidades(nombre_producto)

    # Base: maximo de 3 metricas fuzzy
    tsr = fuzz.token_set_ratio(nu, np_)
    pr = fuzz.partial_ratio(nu, np_)
    token_sort = fuzz.token_sort_ratio(nu, np_)
    tsr_exp = fuzz.token_set_ratio(nu_exp, np_exp)
    pr_exp = fuzz.partial_ratio(nu_exp, np_exp)

    score = max(tsr, pr, token_sort, tsr_exp, pr_exp)

    # Bonus por palabra mas larga
    palabra_larga = extraer_palabra_larga(texto_usuario)
    if palabra_larga and palabra_larga in np_:
        score = min(100, score + 20)

    # Bonus por tener TODAS las palabras clave
    if porcentaje >= 1.0:
        score = min(100, score + 10)

    # Penalizar si hay palabras prohibidas
    if tiene_palabra_prohibida(nombre_producto, obtener_prohibidas(texto_usuario, categoria)):
        score = max(0, score - 50)

    # Categoria
    cat_encaja = _categoria_encaja_con_producto(texto_usuario, categoria)
    if not _es_categoria_general(categoria) and cat_encaja:
        cat_n = normalizar_texto(categoria)
        cat_palabras = cat_n.split()
        coincide_cat = any(p in np_ for p in cat_palabras if len(p) >= 3)
        if coincide_cat:
            score = min(100, score + 12)
        else:
            score = max(0, score - 15)

    # Marca
    marca = _detectar_marca(texto_usuario)
    if marca:
        marca_norm = normalizar_texto(marca)
        marca_palabras = marca_norm.split()
        todas_presentes = all(p in np_ for p in marca_palabras)
        if todas_presentes:
            score = min(100, score + 20)
        else:
            parcial = sum(1 for p in marca_palabras if p in np_) / len(marca_palabras)
            if parcial >= 0.5:
                score = min(100, score + 10)
            else:
                score = max(0, score - 25)

    # Concordancia de cantidad
    if cantidad_g is not None:
        cant_p, un_p = extraer_cantidad_y_unidad(nombre_producto)
        g_p = convertir_a_gramos(cant_p, un_p)
        if g_p is not None:
            ratio = min(cantidad_g, g_p) / max(cantidad_g, g_p)
            if ratio >= 0.8:
                score = min(100, score + 10)
            elif ratio < 0.3:
                score = max(0, score - 15)

    return score


# =============================================================================
# DETECCION DE BUSQUEDA GENERICA
# =============================================================================

def es_busqueda_generica(texto_usuario, candidatos):
    """
    True solo si la busqueda tiene 1 sola palabra clave (ej: "cafe").
    Si el usuario ya dio marca o descripcion (ej: "cafe juan valdez"),
    NO es generico — el usuario ya fue especifico.
    """
    palabras = extraer_palabras_clave(texto_usuario)
    return len(palabras) <= 1


def generar_sugerencia_generica(texto_usuario):
    """
    Genera un mensaje de sugerencia contextual para busquedas genericas.
    Si el termino YA es una marca conocida, sugiere agregar mas detalles.
    Si no es marca, sugiere agregar marca o tipo.
    """
    marca = _detectar_marca(texto_usuario)
    if marca:
        return (
            f"💡 '{texto_usuario}' es muy genérico. "
            f"Prueba añadir más detalles, ej: '{texto_usuario} zucaritas' "
            f"o '{texto_usuario} corn flakes'."
        )
    ejemplo = (f"{texto_usuario} soluble" if "cafe" in texto_usuario.lower()
               else f"{texto_usuario} nescafe")
    return (
        f"💡 '{texto_usuario}' es muy genérico. "
        f"Para mejores resultados prueba algo como: '{ejemplo}'."
    )


# =============================================================================
# CONSTRUCCION DE QUERY (limpia conectores)
# =============================================================================

def construir_query(producto, categoria):
    """
    Construye el query de busqueda limpio (sin conectores).
    'leche de almendras' -> 'leche almendras'
    'cafe juan valdez' -> 'cafe juan valdez'
    """
    query_limpio = limpiar_query_para_busqueda(producto)

    if _es_categoria_general(categoria):
        return query_limpio
    if not _categoria_encaja_con_producto(producto, categoria):
        return query_limpio
    if normalizar_texto(categoria) not in normalizar_texto(producto):
        return f"{query_limpio} {categoria}"
    return query_limpio


# =============================================================================
# CATEGORIAS PRINCIPALES (sin subcategorias visibles)
# =============================================================================

CATEGORIAS_PRINCIPALES = [
    "Bebidas",
    "Granos y Cereales",
    "Lacteos y Alternativas",
    "Aceites y Grasas",
    "Carnes y Pescados",
    "Snacks",
    "Limpieza",
    "Otros",
]

LISTA_CATEGORIAS_PRINCIPALES = ["(sin categoria)"] + CATEGORIAS_PRINCIPALES


# =============================================================================
# TIENDAS
# =============================================================================

TIENDAS = ["selectos", "walmart", "despensa"]
TIENDA_LABELS = {"selectos": "Super Selectos", "walmart": "Walmart", "despensa": "La Despensa"}
TIENDA_COLORS = {"selectos": "#c0392b", "walmart": "#0071ce", "despensa": "#e67e22"}


# =============================================================================
# RECOMENDACION
# =============================================================================

UMBRAL_SIMILITUD = 75


def generar_recomendacion(resultados, selecciones):
    """Genera totales y recomendacion basada en las selecciones actuales (3 tiendas)."""
    totales = {"selectos": 0.0, "walmart": 0.0, "despensa": 0.0}
    items_count = {"selectos": 0, "walmart": 0, "despensa": 0}
    items_sin = 0
    mezcla = []

    for i, r in enumerate(resultados):
        sel = selecciones.get(i, {})
        precios = {}
        for tienda in TIENDAS:
            p = sel.get(tienda, {}).get("precio") if sel.get(tienda) else None
            if p is not None:
                precios[tienda] = p
                totales[tienda] += p
                items_count[tienda] += 1

        if not precios:
            items_sin += 1
            continue

        mejor_tienda = min(precios, key=precios.get)
        mezcla.append({"producto": r["producto_original"], "tienda": TIENDA_LABELS[mejor_tienda]})

    # Total mezcla optima
    total_mezcla = 0.0
    for i in range(len(resultados)):
        sel = selecciones.get(i, {})
        precios = {}
        for tienda in TIENDAS:
            p = sel.get(tienda, {}).get("precio") if sel.get(tienda) else None
            if p is not None:
                precios[tienda] = p
        if precios:
            total_mezcla += min(precios.values())

    return {
        "total_selectos": totales["selectos"],
        "total_walmart": totales["walmart"],
        "total_despensa": totales["despensa"],
        "total_mezcla": total_mezcla,
        "items_selectos": items_count["selectos"],
        "items_walmart": items_count["walmart"],
        "items_despensa": items_count["despensa"],
        "items_sin_datos": items_sin,
        "productos_en_walmart":  [m["producto"] for m in mezcla if m["tienda"] == "Walmart"],
        "productos_en_selectos": [m["producto"] for m in mezcla if m["tienda"] == "Super Selectos"],
        "productos_en_despensa": [m["producto"] for m in mezcla if m["tienda"] == "La Despensa"],
    }


def determinar_mas_barato(sel_s, sel_w, sel_d=None):
    """Devuelve texto indicando cual tienda es mas barata (3 tiendas)."""
    precios = {}
    if sel_s:
        precios["Selectos"] = sel_s["precio"]
    if sel_w:
        precios["Walmart"] = sel_w["precio"]
    if sel_d:
        precios["Despensa"] = sel_d["precio"]

    if not precios:
        return "Sin datos"
    if len(precios) == 1:
        return f"Solo {list(precios.keys())[0]}"

    vals = list(precios.values())
    if all(v == vals[0] for v in vals):
        return "Precio igual"

    return min(precios, key=precios.get)


# Iteracion 14 - 3 tiendas + sugerencia generica inteligente
