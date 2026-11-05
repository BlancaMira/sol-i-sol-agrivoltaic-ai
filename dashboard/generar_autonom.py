"""
generar_autonom.py
Genera SOL_I_SOL_dashboard_autonom.html incrustant dashboard_data.json
dins l'index.html modificat (amb vista pagès i alertes).

Ús:
  1. Posa aquest script a la carpeta dashboard/
  2. Executa:  python generar_autonom.py
  3. S'genera SOL_I_SOL_dashboard_autonom.html al mateix directori
"""

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INDEX_HTML  = SCRIPT_DIR / "index.html"
DATA_JSON   = SCRIPT_DIR / "dashboard_data.json"
OUTPUT_HTML = SCRIPT_DIR / "SOL_I_SOL_dashboard_autonom.html"

def main():
    print("Llegint index.html ...")
    html = INDEX_HTML.read_text(encoding="utf-8")

    print("Llegint dashboard_data.json (pot trigar uns segons) ...")
    data = DATA_JSON.read_bytes()          # bytes per evitar re-encode
    data_str = data.decode("utf-8")

    # Comprova que el JSON és vàlid
    json.loads(data_str)
    print(f"  JSON vàlid · {len(data)/1_048_576:.1f} MB")

    # Substitueix la crida fetch() per dades incrustades directament
    # El boot() original fa:  const response = await fetch("dashboard_data.json");
    #                          payload = await response.json();
    # Ho reemplacem per:      payload = <dades>;
    OLD = '''        const response = await fetch("dashboard_data.json");
        payload = await response.json();'''

    NEW = f'''        // Dades incrustades (mode autònom, sense servidor)
        payload = {data_str};'''

    if OLD not in html:
        # Intenta versió amb cometes simples per si de cas
        OLD2 = OLD.replace('"', "'")
        if OLD2 in html:
            html = html.replace(OLD2, NEW)
        else:
            print("ERROR: No s'ha trobat el patró fetch() a index.html.")
            print("       Comprova que el fitxer és el generat per Claude.")
            return 1
    else:
        html = html.replace(OLD, NEW)

    print("Escrivint fitxer autònom ...")
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    size_mb = OUTPUT_HTML.stat().st_size / 1_048_576
    print(f"  ✓ Generat: {OUTPUT_HTML.name}  ({size_mb:.1f} MB)")
    print("  Obre'l amb doble clic al navegador, sense necessitat de servidor.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
