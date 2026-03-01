"""
test_precios.py - Test masivo de productos SuperBarato SV
=========================================================
Verifica precios de 8 productos en las 3 tiendas.
Detecta precios sospechosamente bajos (posible descuento mal tomado).
"""

import sys
sys.path.insert(0, ".")

from scrapers import buscar_producto

PRODUCTOS_TEST = [
    "te de manzanilla",
    "azucar morena",
    "cafe soluble",
    "cappuccino",
    "margarina",
    "aceite de oliva",
    "aceite",
    "galletas",
]

def main():
    print("=" * 90)
    print("TEST MASIVO DE PRECIOS - SuperBarato SV v0.16")
    print("=" * 90)

    for producto in PRODUCTOS_TEST:
        print(f"\n{'─' * 90}")
        print(f"🔍 Buscando: {producto}")
        print(f"{'─' * 90}")

        try:
            resultado = buscar_producto(producto)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

        for tienda_key in ["selectos", "walmart", "despensa"]:
            tienda_label = {
                "selectos": "Super Selectos",
                "walmart": "Walmart",
                "despensa": "La Despensa",
            }[tienda_key]

            sel = resultado.get(tienda_key)
            candidatos = resultado.get(f"candidatos_{tienda_key}", [])

            if sel:
                print(f"\n  🏪 {tienda_label}:")
                print(f"     Nombre:       {sel['nombre']}")
                print(f"     Precio:       ${sel['precio']:.2f}")
                if sel.get("precio_lista"):
                    print(f"     Precio lista: ${sel['precio_lista']:.2f}")
                print(f"     Es oferta:    {sel.get('es_oferta', False)}")
                print(f"     Imagen:       {'✅' if sel.get('imagen') else '❌ SIN IMAGEN'}")
                print(f"     Similitud:    {sel.get('similitud', 0)}")

                # Detectar precios sospechosos
                if sel["precio"] < 0.50:
                    print(f"     ⚠️  PRECIO MUY BAJO (${sel['precio']:.2f}) - posible descuento mal tomado!")
            else:
                print(f"\n  🏪 {tienda_label}: No encontrado")
                no_disp = resultado.get(f"{tienda_key}_no_disponible", False)
                if no_disp:
                    print(f"     (API no disponible)")

            # Mostrar alternativas
            if candidatos:
                print(f"     Alternativas ({len(candidatos)}):")
                for j, c in enumerate(candidatos[:3]):
                    flag = ""
                    if c.get("es_oferta") and c.get("precio_lista"):
                        flag = f" (oferta, lista: ${c['precio_lista']:.2f})"
                    print(f"       {j+1}. {c['nombre'][:55]} - ${c['precio']:.2f}{flag}")

        # Comparar precios entre tiendas para detectar anomalias
        precios = {}
        for tk in ["selectos", "walmart", "despensa"]:
            s = resultado.get(tk)
            if s:
                precios[tk] = s["precio"]

        if len(precios) >= 2:
            vals = list(precios.values())
            min_p = min(vals)
            max_p = max(vals)
            if max_p > 0 and min_p < max_p * 0.3:
                print(f"\n  ⚠️  ALERTA: Diferencia de precio muy grande ({min_p:.2f} vs {max_p:.2f})")
                print(f"     Posible precio de descuento mal capturado.")

        print(f"\n  Genérico: {resultado.get('es_generico', False)}")
        print(f"  Más barato: {resultado.get('mas_barato', 'sin_datos')}")

    print(f"\n{'=' * 90}")
    print("TEST COMPLETADO")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
