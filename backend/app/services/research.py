from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Series
from app.services.search import normalize_text


RESEARCH_TEMPLATES = [
    {
        "keywords": ["importacion", "importaciones", "apertura", "externo", "competencia", "produccion", "local"],
        "topic": "Relación entre importaciones textiles y producción local",
        "primary_code": "IPI_TEXTILES",
        "related_codes": ["IMPO_CADENA_TEXTIL_TOTAL", "IMPO_PRENDAS_TERMINADAS_TOTAL", "TC_MAYORISTA_BCRA", "IPI_NIVEL_GENERAL_ORIG", "EMPLEO_PRIVADO_TEXTIL"],
        "structural_preset_id": "local_vs_imports",
        "exploratory_hypotheses": [
            "¿Aumentaron más las importaciones de insumos intermedios (filamentos NCM 54 / tejidos NCM 60) o las de prendas terminadas (NCM 61+62)?",
            "¿El desempeño de la producción textil acompañó el ciclo de la industria manufacturera general o mostró divergencias específicas?",
            "¿Cómo se comportaron el tipo de cambio mayorista y las importaciones frente a la utilización de capacidad instalada textil?",
        ],
    },
    {
        "keywords": ["pyme", "pymes", "grande", "grandes", "tamano", "tamaño", "micro", "pequena", "mediana", "estructura", "empresarial"],
        "topic": "Estructura empresarial: PyMEs vs grandes empresas en la cadena textil",
        "primary_code": "EMPLEO_PRIVADO_TEXTIL",
        "related_codes": ["EMPLEO_PRIVADO_INDUMENTARIA", "UCII_TEXTILES", "PRESTAMOS_SECTOR_PRIVADO", "TASA_BADLAR_PRIVADOS", "IPI_TEXTILES"],
        "structural_preset_id": "pyme_vs_large",
        "exploratory_hypotheses": [
            "¿Cómo se distribuyen las firmas PyME (Micro, Pequeña, Mediana) frente a grandes empresas a lo largo de los distintos eslabones de la cadena textil?",
            "¿Qué divergencias se observan entre empleo registrado en productos textiles (CLAE 13) y confección de prendas (CLAE 14) durante cambios en tasas y crédito?",
            "¿Qué parte del universo empresarial del sector carece aún de categorización oficial verificable (UNKNOWN)?",
        ],
    },
    {
        "keywords": ["nacional", "nacionales", "extranjera", "extranjeras", "origen", "capital", "multinacional"],
        "topic": "Estructura empresarial: firmas nacionales vs extranjeras",
        "primary_code": "IPI_TEXTILES",
        "related_codes": ["IMPO_PRENDAS_TERMINADAS_TOTAL", "EXPO_CADENA_TEXTIL_TOTAL", "TC_MAYORISTA_BCRA", "SALDO_COMERCIAL_TEXTIL"],
        "structural_preset_id": "national_vs_foreign",
        "exploratory_hypotheses": [
            "¿Se observan distintos modelos productivos (local, mixto o importador) dentro de las firmas de capital nacional frente a las de capital extranjero?",
            "¿Por qué es metodológicamente necesario separar origen societario de tamaño empresarial y de modelo productivo?",
            "¿Cómo evolucionó el saldo comercial textil agregado junto con el tipo de cambio mayorista (sin inferir causalidad directa a nivel de firma)?",
        ],
    },
    {
        "keywords": ["terminado", "terminada", "terminadas", "confeccion", "marca", "retail", "importado", "importada"],
        "topic": "Producción local vs producto terminado importado",
        "primary_code": "IPI_PRENDAS_VESTIR",
        "related_codes": ["IMPO_PRENDAS_TERMINADAS_TOTAL", "IPC_PRENDAS_CALZADO", "PRECIO_RELATIVO_INDUMENTARIA", "EMPLEO_PRIVADO_INDUMENTARIA"],
        "structural_preset_id": "local_vs_imported_finished",
        "exploratory_hypotheses": [
            "¿Cómo evolucionó la producción local de prendas de vestir (IPI) en relación con las importaciones de prendas terminadas (NCM 61+62)?",
            "¿Qué diferencias existen entre el modelo productivo de firmas dedicadas a confección frente a firmas enfocadas en marca o retail?",
            "¿Coincidieron cambios en importaciones de indumentaria terminada con movimientos en el precio relativo de la ropa (sin atribuir causalidad automática)?",
        ],
    },
    {
        "keywords": ["dependencia", "importadora", "insumo", "insumos", "segmento", "eslabon", "cadena", "hilado", "tejido", "fibra"],
        "topic": "Dependencia importadora por segmento de la cadena textil",
        "primary_code": "IMPO_NCM_54_FILAMENTOS_SINT",
        "related_codes": ["IMPO_NCM_60_TEJIDOS_PUNTO", "IMPO_PRENDAS_TERMINADAS_TOTAL", "IPI_TEJIDOS_ACABADO", "IPI_HILADOS_ALGODON", "TC_MAYORISTA_BCRA"],
        "structural_preset_id": "import_dependency_by_segment",
        "exploratory_hypotheses": [
            "¿Cuál es el peso relativo de las importaciones de insumos intermedios (NCM 54 filamentos, NCM 60 tejidos de punto) frente a prendas terminadas (NCM 61+62)?",
            "¿Qué eslabones de la cadena muestran mayor presencia verificada de producción local con insumos importados frente a producción mixta o importación de terminado?",
            "¿Cómo co-evolucionaron las importaciones de insumos intermedios y la producción industrial de tejidos y acabados?",
        ],
    },
    {
        "keywords": ["precio", "precios", "ropa", "inflacion", "indumentaria", "ipc", "mayorista"],
        "topic": "Dinámica de precios de la indumentaria frente a inflación y costos",
        "primary_code": "IPC_PRENDAS_CALZADO",
        "related_codes": ["IPC_NIVEL_GENERAL", "PRECIO_RELATIVO_INDUMENTARIA", "IPIM_PRODUCTOS_TEXTILES", "IPIM_PRENDAS_VESTIR", "SALARIO_REAL_RIPTE"],
        "structural_preset_id": "local_vs_imported_finished",
        "exploratory_hypotheses": [
            "¿En qué períodos el IPC de Prendas de vestir y calzado superó al IPC Nivel General (encarecimiento relativo)?",
            "¿Se observa comovimiento entre los precios mayoristas textiles (IPIM) y el precio final al consumidor?",
            "¿Cómo evolucionó el precio relativo de la ropa respecto del poder adquisitivo salarial (RIPTE real)?",
        ],
    },
    {
        "keywords": ["empleo", "trabajo", "puestos", "salario", "salarios", "sueldo", "remuneracion"],
        "topic": "Empleo formal, salarios y nivel de actividad en el complejo textil",
        "primary_code": "EMPLEO_PRIVADO_TEXTIL",
        "related_codes": ["EMPLEO_PRIVADO_INDUMENTARIA", "EMPLEO_PRIVADO_INDUSTRIA", "IPI_TEXTILES", "IPI_PRENDAS_VESTIR", "SALARIO_REAL_INDUSTRIA"],
        "structural_preset_id": "pyme_vs_large",
        "exploratory_hypotheses": [
            "¿Cómo evolucionó el empleo en fabricación de productos textiles (CLAE 13) frente a confección de prendas (CLAE 14)?",
            "¿El empleo sectorial respondió con rezago a las caídas y recuperaciones de la producción física?",
            "¿Qué diferencias se observan en el salario nominal promedio entre textiles, confección y promedio manufacturero?",
        ],
    },
    {
        "keywords": ["capacidad", "coste", "costo", "energia", "financiamiento", "credito", "tasa"],
        "topic": "Capacidad instalada, costes energéticos y entorno financiero",
        "primary_code": "UCII_TEXTILES",
        "related_codes": ["UCII_NIVEL_GENERAL", "IPI_HILADOS_ALGODON", "IPIM_ENERGIA_ELECTRICA", "TASA_BADLAR_PRIVADOS", "PRESTAMOS_SECTOR_PRIVADO"],
        "structural_preset_id": "pyme_vs_large",
        "exploratory_hypotheses": [
            "¿En cuántos puntos porcentuales difiere el uso de capacidad instalada textil respecto del promedio industrial?",
            "¿Coincidieron períodos de ajustes tarifarios energéticos (IPIM Energía eléctrica) o tasas altas con menor actividad?",
        ],
    },
]


def suggest_research_structure(db: Session, question: str) -> dict[str, Any]:
    norm = normalize_text(question)
    tokens = set(norm.split(" "))

    best_tpl = RESEARCH_TEMPLATES[0]
    best_hits = -1
    for tpl in RESEARCH_TEMPLATES:
        hits = sum(1 for kw in tpl["keywords"] if kw in norm or kw in tokens)
        if hits > best_hits:
            best_hits = hits
            best_tpl = tpl

    needed = [best_tpl["primary_code"]] + best_tpl["related_codes"]
    series_rows = db.scalars(
        select(Series).where(Series.series_code.in_(needed), Series.audit_status == "VERIFIED", Series.active.is_(True))
    ).all()
    by_code = {s.series_code: s for s in series_rows}

    def serialize(s: Series) -> dict[str, Any]:
        return {
            "series_code": s.series_code,
            "series_name": s.series_name,
            "short_name": s.short_name,
            "unit": s.unit,
            "frequency": s.frequency,
            "category": s.category,
            "is_context_variable": s.is_context_variable,
            "series_type": s.series_type,
            "start_date": s.start_date.isoformat() if s.start_date else None,
            "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
        }

    primary = by_code.get(best_tpl["primary_code"])
    related = [serialize(by_code[c]) for c in best_tpl["related_codes"] if c in by_code]

    return {
        "question": question,
        "suggested_topic": best_tpl["topic"],
        "framing_label": "Posible estructura exploratoria de investigación",
        "methodological_caution": (
            "Textile Data Hub no define automáticamente qué variable es 'dependiente' ni 'explicativa' como hecho estadístico. "
            "No interpretar asociaciones entre variables agregadas ni entre dimensiones empresariales como causalidad: "
            "la identificación causal requiere marco teórico, microdatos verificables y diseño econométrico."
        ),
        "primary_variable": serialize(primary) if primary else None,
        "related_variables": related,
        "exploratory_questions": best_tpl["exploratory_hypotheses"],
        "structural_preset_id": best_tpl.get("structural_preset_id"),
    }
