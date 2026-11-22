# Metodología del Módulo Experimental: Estructura Empresarial de la Industria Textil

## 1. Principio rector: dimensiones estrictamente independientes

En el análisis del complejo textil e indumentaria argentino es frecuente colapsar tamaño empresarial, origen del capital y modelo productivo en una única etiqueta. **Textile Data Hub Argentina prohíbe esa mezcla** y modela cuatro dimensiones ortogonales e independientes:

| Dimensión | Código | Valores canónicos | Cardinalidad | Criterio oficial verificable |
| :--- | :--- | :--- | :--- | :--- |
| **A. Tamaño** | `SIZE` | `MICRO` (Micro), `SMALL` (Pequeña), `MEDIUM` (Mediana), `LARGE` (Grande), `UNKNOWN` (No determinado) | Única vigente | Topes oficiales MiPyME (Ley 24.467, Res. SEPyME 220/2019 y actualizaciones como Res. SIC 1/2026), constancia ARCA/AFIP, balances auditados CNV/IGJ |
| **B. Origen** | `ORIGIN` | `NATIONAL` (Nacional), `FOREIGN` (Extranjera), `UNKNOWN` (No determinado) | Única vigente | Registros societarios oficiales: IGJ (incl. art. 118/123 LGS), Registros Públicos provinciales, Boletín Oficial (Sección Sociedades), notas de control societario en estados contables CNV (AIF) |
| **C. Modelo productivo** | `PRODUCTION_MODEL` | `LOCAL_PRIMARY`, `LOCAL_IMPORTED_INPUTS`, `MIXED`, `MAJORITY_IMPORTED_FINISHED`, `IMPORTED_FINISHED`, `UNKNOWN` | Única vigente | Memorias y estados contables auditados CNV (AIF), Registro Industrial de la Nación (RIN / Sec. Industria y Comercio), habilitaciones industriales y registros aduaneros oficiales (DGA/ARCA) |
| **D. Posición en la cadena** | `CHAIN_POSITION` | `FIBER` (Fibra), `YARN` (Hilado), `FABRIC` (Tejido), `APPAREL` (Confección), `BRAND` (Marca), `RETAIL` (Retail), `INTEGRATED` (Integrada), `UNKNOWN` (No determinado) | Múltiple simultánea | Códigos CLAE principal y secundarios (ARCA/AFIP F.883), Registro Industrial de la Nación, objeto social en Boletín Oficial y memorias auditadas CNV |

> Nota sobre el filtro `PyME`: En la interfaz y API se ofrece `PYME` como atajo de consulta equivalente a `MICRO ∪ SMALL ∪ MEDIUM`, manteniendo almacenada la categoría oficial granular de cada firma.

---

## 2. Modelo de datos (`core`)

1. **`core.companies`**: almacena la entidad empresarial (`company_id`, `legal_name`, `brand_name`, `cuit`) y la proyección vigente verificada de `company_size`, `company_origin`, `production_model` y `classification_status` (`VERIFIED_COMPLETE`, `PARTIALLY_VERIFIED`, `UNKNOWN`).
2. **`core.company_chain_positions`**: relación 1:N que materializa todas las posiciones vigentes verificadas de la Dimensión D para consultas combinadas eficientes (`any` / `all`).
3. **`core.company_classification_history`**: bitácora temporal y auditable de cada dimensión (`company_id`, `dimension`, `classification`, `valid_from`, `valid_to`, `official_source_id`, `source_url`, `evidence`, `audit_status`, `audit_notes`).

---

## 3. Regla estricta de fuentes y `CompanyClassificationAuditor`

- Toda clasificación distinta de `UNKNOWN` requiere:
  1. `official_source_id` aprobado en `core.official_sources` (excluyendo `TDH_DERIVED`).
  2. `source_url` cuyo host pertenezca al `official_domain` aprobado del organismo.
  3. `evidence` con cita documental oficial concreta (mínimo 20 caracteres).
- El auditor **rechaza automáticamente (`audit_status = REJECTED`)** cualquier registro que cite:
  - Noticias o prensa
  - Redes sociales
  - Sitios web comerciales
  - Wikipedia
  - Conocimiento previo del modelo o percepción subjetiva de la marca
- Los registros `REJECTED` quedan auditados en `company_classification_history` con `audit_notes`, pero **nunca se promueven** a `core.companies`. Si no existe evidencia oficial suficiente, la clasificación permanece en `UNKNOWN`.

---

## 4. Integración con Modo Research y prevención de falacias causales

El módulo permite construir preguntas exploratorias combinando las 4 dimensiones o seleccionando ejes predefinidos:

- Producción local vs importaciones
- PyMEs vs grandes empresas
- Firmas nacionales vs extranjeras
- Producción local vs producto terminado importado
- Dependencia importadora por segmento

Todas las vistas y endpoints incorporan una advertencia explícita de **no causalidad** y **falacia ecológica**: la coexistencia entre la estructura empresarial y la trayectoria de series económicas agregadas sirve para formular hipótesis exploratorias, nunca para afirmar causalidad sin identificación econométrica ni microdatos longitudinales.
