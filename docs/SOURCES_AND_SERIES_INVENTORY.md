# Inventario de Fuentes Oficiales y Series del MVP (49 Series Verificadas)

Todas las series del MVP provienen **exclusivamente de organismos oficiales públicos argentinos** (`42 OFFICIAL` + `7 DERIVED` auditadas a partir de series `VERIFIED`). Ningún dato proviene de portales informativos, consultoras, Wikipedia o fuentes privadas.

---

## 1. Organismos oficiales aprobados (`core.official_sources`)

| Código | Organismo | Dominio oficial |
|---|---|---|
| `INDEC` | Instituto Nacional de Estadística y Censos | `indec.gob.ar` |
| `DATOS_ARG` | Datos Argentina — API oficial de Series de Tiempo (INDEC / SSPM / Sec. Trabajo) | `apis.datos.gob.ar` |
| `SSPM_MECON` | Subsecretaría de Programación Macroeconómica — Ministerio de Economía | `infra.datos.gob.ar` |
| `BCRA` | Banco Central de la República Argentina (API Estadísticas v4.0) | `api.bcra.gob.ar` |
| `SEC_TRABAJO` | Secretaría de Trabajo, Empleo y Seguridad Social (SIPA / RIPTE) | `apis.datos.gob.ar` |
| `CEP_SIC` | Secretaría de Industria y Comercio / CEP XXI (SIPA por CLAE2) | `cdn.produccion.gob.ar` |
| `TDH_DERIVED` | Textile Data Hub Argentina (exclusivo para cálculos `DERIVED` auditados) | `internal.textiledatahub.local` |

---

## 2. Inventario verificado de las 49 series del MVP

### A. Actividad y producción (10 OFFICIAL)

| Código | Tipo | Frecuencia | Unidad | Fuente | Cobertura observada | Obs. | Score |
|---|---|---|---|---|---|---:|---:|
| `IPI_TEXTILES` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_FIBRAS_TEXTILES` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_HILADOS_ALGODON` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_TEJIDOS_ACABADO` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_OTROS_TEXTILES` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_PRENDAS_VESTIR` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `IPI_NIVEL_GENERAL_ORIG` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `UCII_TEXTILES` | OFFICIAL | MONTHLY | Porcentaje (%) | `SSPM_MECON` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `UCII_NIVEL_GENERAL` | OFFICIAL | MONTHLY | Porcentaje (%) | `SSPM_MECON` | `2016-01-01..2026-09-01` | 129 | 97.8 |
| `EMAE_INDUSTRIA` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2004-01-01..2026-08-01` | 272 | 92.8 |

### B. Precios y costes (7 OFFICIAL + 1 DERIVED)

| Código | Tipo | Frecuencia | Unidad | Fuente | Cobertura observada | Obs. | Score |
|---|---|---|---|---|---|---:|---:|
| `IPC_PRENDAS_CALZADO` | OFFICIAL | MONTHLY | Índice Dic-2016 = 100 | `DATOS_ARG` | `2016-12-01..2026-10-01` | 119 | 97.8 |
| `IPC_VIVIENDA_ENERGIA` | OFFICIAL | MONTHLY | Índice Dic-2016 = 100 | `DATOS_ARG` | `2016-12-01..2026-10-01` | 119 | 97.8 |
| `IPIM_NIVEL_GENERAL` | OFFICIAL | MONTHLY | Índice Dic-2015 = 100 | `INDEC` | `2015-12-01..2026-10-01` | 130 | 97.7 |
| `IPIM_PRODUCTOS_MANUFACTURADOS` | OFFICIAL | MONTHLY | Índice Dic-2015 = 100 | `INDEC` | `2015-12-01..2026-10-01` | 130 | 97.7 |
| `IPIM_PRODUCTOS_TEXTILES` | OFFICIAL | MONTHLY | Índice Dic-2015 = 100 | `INDEC` | `2015-12-01..2026-10-01` | 130 | 97.7 |
| `IPIM_PRENDAS_VESTIR` | OFFICIAL | MONTHLY | Índice Dic-2015 = 100 | `INDEC` | `2015-12-01..2026-10-01` | 130 | 97.7 |
| `IPIM_ENERGIA_ELECTRICA` | OFFICIAL | MONTHLY | Índice Dic-2015 = 100 | `INDEC` | `2015-12-01..2026-10-01` | 130 | 97.7 |
| `PRECIO_RELATIVO_INDUMENTARIA` | DERIVED | MONTHLY | Índice relativo (Dic-2016 = 100) | `TDH_DERIVED` | `2016-12-01..2026-10-01` | 119 | 97.8 |

### C. Comercio exterior (8 OFFICIAL + 4 DERIVED)

| Código | Tipo | Frecuencia | Unidad | Fuente | Cobertura observada | Obs. | Score |
|---|---|---|---|---|---|---:|---:|
| `IMPO_NCM_52_ALGODON` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_NCM_54_FILAMENTOS_SINT` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_NCM_60_TEJIDOS_PUNTO` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_NCM_61_PRENDAS_PUNTO` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_NCM_62_PRENDAS_PLANO` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_NCM_63_CONFECCIONES_HOGAR` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `EXPO_NCM_51_LANA` | OFFICIAL | MONTHLY | Millones de USD (FOB) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `EXPO_NCM_52_ALGODON` | OFFICIAL | MONTHLY | Millones de USD (FOB) | `SSPM_MECON` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_PRENDAS_TERMINADAS_TOTAL` | DERIVED | MONTHLY | Millones de USD (CIF) | `TDH_DERIVED` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `IMPO_CADENA_TEXTIL_TOTAL` | DERIVED | MONTHLY | Millones de USD (CIF) | `TDH_DERIVED` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `EXPO_CADENA_TEXTIL_TOTAL` | DERIVED | MONTHLY | Millones de USD (FOB) | `TDH_DERIVED` | `1990-01-01..2025-02-01` | 422 | 85.8 |
| `SALDO_COMERCIAL_TEXTIL` | DERIVED | MONTHLY | Millones de USD (FOB - CIF) | `TDH_DERIVED` | `1990-01-01..2025-02-01` | 422 | 85.8 |

### D. Empleo y salarios (9 OFFICIAL + 2 DERIVED)

| Código | Tipo | Frecuencia | Unidad | Fuente | Cobertura observada | Obs. | Score |
|---|---|---|---|---|---|---:|---:|
| `EMPLEO_PRIVADO_TOTAL` | OFFICIAL | MONTHLY | Miles de personas | `SEC_TRABAJO` | `2009-01-01..2026-07-01` | 211 | 92.8 |
| `EMPLEO_PRIVADO_INDUSTRIA` | OFFICIAL | MONTHLY | Miles de personas | `SEC_TRABAJO` | `2009-01-01..2026-07-01` | 211 | 92.8 |
| `EMPLEO_PRIVADO_TEXTIL` | OFFICIAL | MONTHLY | Puestos de trabajo | `CEP_SIC` | `2007-01-01..2023-11-01` | 203 | 85.8 |
| `EMPLEO_PRIVADO_INDUMENTARIA` | OFFICIAL | MONTHLY | Puestos de trabajo | `CEP_SIC` | `2007-01-01..2023-11-01` | 203 | 85.8 |
| `REMUNERACION_INDUSTRIA` | OFFICIAL | MONTHLY | Pesos corrientes (ARS) | `SEC_TRABAJO` | `2004-01-01..2026-06-01` | 270 | 92.8 |
| `REMUNERACION_TEXTIL` | OFFICIAL | MONTHLY | Pesos corrientes (ARS) | `CEP_SIC` | `2007-01-01..2023-11-01` | 203 | 85.8 |
| `REMUNERACION_INDUMENTARIA` | OFFICIAL | MONTHLY | Pesos corrientes (ARS) | `CEP_SIC` | `2007-01-01..2023-11-01` | 203 | 85.8 |
| `RIPTE_NOMINAL` | OFFICIAL | MONTHLY | Pesos corrientes (ARS) | `SEC_TRABAJO` | `2004-01-01..2026-08-01` | 272 | 92.8 |
| `INDICE_SALARIOS_PRIV_REG` | OFFICIAL | MONTHLY | Índice Oct-2016 = 100 | `SEC_TRABAJO` | `2015-10-01..2026-08-01` | 131 | 92.8 |
| `SALARIO_REAL_RIPTE` | DERIVED | MONTHLY | Índice real (Dic-2016 = 100) | `TDH_DERIVED` | `2016-12-01..2026-08-01` | 117 | 92.8 |
| `SALARIO_REAL_INDUSTRIA` | DERIVED | MONTHLY | Índice real (Dic-2016 = 100) | `TDH_DERIVED` | `2016-12-01..2026-06-01` | 115 | 92.8 |

### E. Contexto macroeconómico (8 OFFICIAL — etiquetadas como `VARIABLE DE CONTEXTO`)

| Código | Tipo | Frecuencia | Unidad | Fuente | Cobertura observada | Obs. | Score |
|---|---|---|---|---|---|---:|---:|
| `IPC_NIVEL_GENERAL` | OFFICIAL | MONTHLY | Índice Dic-2016 = 100 | `DATOS_ARG` | `2016-12-01..2026-10-01` | 119 | 97.8 |
| `EMAE_NIVEL_GENERAL_DESEST` | OFFICIAL | MONTHLY | Índice 2004 = 100 | `DATOS_ARG` | `2004-01-01..2026-08-01` | 272 | 92.8 |
| `PIB_PRECIOS_CONSTANTES` | OFFICIAL | QUARTERLY | Millones de ARS constantes (2004) | `DATOS_ARG` | `2004-01-01..2026-04-01` | 90 | 97.8 |
| `TC_MAYORISTA_BCRA` | OFFICIAL | DAILY | ARS / USD | `BCRA` | `2016-01-04..2026-11-20` | 2648 | 94.6 |
| `TASA_BADLAR_PRIVADOS` | OFFICIAL | DAILY | Porcentaje TNA (%) | `BCRA` | `2016-01-04..2026-11-19` | 2647 | 96.8 |
| `PRESTAMOS_SECTOR_PRIVADO` | OFFICIAL | DAILY | Millones de ARS corrientes | `BCRA` | `2016-01-04..2026-11-18` | 2646 | 96.8 |
| `EXPO_TOTALES_ARG` | OFFICIAL | MONTHLY | Millones de USD (FOB) | `DATOS_ARG` | `2004-01-01..2026-09-01` | 273 | 97.8 |
| `IMPO_TOTALES_ARG` | OFFICIAL | MONTHLY | Millones de USD (CIF) | `DATOS_ARG` | `2004-01-01..2026-09-01` | 273 | 97.8 |
