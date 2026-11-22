# Metodología del Data Auditor y Data Quality Score

## 1. Pipeline obligatorio

Ninguna observación puede ser consultada en la interfaz pública sin haber atravesado el pipeline:

```text
OFFICIAL SOURCE → RAW (SHA-256) → DATA AUDITOR → STAGING → CORE → API → WEB APP
```

Solo las series en estado **`VERIFIED`** se exponen en los endpoints públicos de búsqueda, catálogo, comparación y exportación.

---

## 2. Controles implementados por el Data Auditor

### A. Validación de procedencia (`PROVENANCE`)
- El organismo debe existir en `core.official_sources` con `is_approved = TRUE`.
- El host de `raw_extractions.source_url` debe coincidir con `official_sources.official_domain` para series `OFFICIAL`.
- Se exige cadena completa sin eslabones rotos: `raw_id` + `dataset_id` + `source_id` + `source_url` + `source_series_code`.
- Las series `DERIVED` exigen registro explícito en `core.derived_series_lineage` (`formula`, `source_series_ids`, `calculation_version`).

### B. Integridad y estructura (`STRUCTURE` / `INTEGRITY`)
- Detección de extracciones vacías o cambios de columnas/esquema (`SCHEMA_DRIFT` → `REJECTED`).
- Rechazo fila por fila de fechas inválidas o valores no numéricos/nulos sin interpolar ni rellenar con cero.
- Detección de fechas duplicadas dentro de la misma extracción (valores contradictorios → `REJECTED`).
- Detección de discontinuidades temporales (`DATE_GAP`). Si faltan más de 2 períodos consecutivos en series mensuales/trimestrales o >30 días corridos en diarias, la serie pasa a `WARNING` para inspección.

### C. Estadística y revisiones (`STATISTICAL`)
- **Outliers por saltos extremos**: se calcula el *robust z-score* basado en la mediana y el MAD (*Median Absolute Deviation*) de las variaciones porcentuales período a período (`|z| > 6.5` y `|var %| > 35%`). Este criterio es robusto para la alta volatilidad inflacionaria argentina. **Nunca se eliminan outliers automáticamente**: solo se marcan (`is_outlier_flagged = TRUE`) y se documentan en `core.audit_findings`.
- **Historial de revisiones**: antes de publicar, cada observación se compara contra `core.observations` donde `is_current = TRUE`. Si el organismo oficial modificó un dato histórico, el registro anterior pasa a `is_current = FALSE` y se inserta el nuevo valor con `revision_number + 1`.

---

## 3. Data Quality Score (0–100)

El Quality Score es un indicador diagnóstico transparente que **nunca modifica los datos**:

| Dimensión | Puntaje máx. | Criterio |
|---|---:|---|
| Validación de fuente oficial y dominio | 25 | Organismo aprobado, dominio coincidente y cadena completa |
| Completitud de metadata | 20 | Presencia de definiciones Nivel 1 y Nivel 2 completas |
| Completitud temporal | 15 | Proporción de observaciones existentes frente a períodos esperados |
| Consistencia estructural y estadística | 15 | Ausencia de errores estructurales o advertencias de integridad |
| Oportunidad (*Freshness*) | 15 | Cercanía del último dato oficial respecto de la fecha actual según frecuencia |
| Trazabilidad SHA-256 y revisiones | 10 | Archivo raw registrado con hash e historial de revisiones activo |
| **Total** | **100** | |
