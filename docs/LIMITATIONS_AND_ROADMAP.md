# Limitaciones conocidas, rezagos oficiales y hoja de ruta

## 1. Limitaciones reales de las fuentes oficiales en el MVP

En cumplimiento estricto de la política de **no inventar, interpolar ni extrapolar datos**, el MVP refleja fielmente las restricciones y rezagos de las fuentes públicas argentinas consultadas al 22/11/2026:

1. **Empleo y salarios por rama CLAE a 2 dígitos (`clae2=13` y `clae2=14`)**:
   - Fuente: CEP XXI / Secretaría de Industria y Comercio (`cdn.produccion.gob.ar`).
   - Limitación observada: los archivos abiertos consolidados por CLAE2 finalizan en **noviembre de 2023** (`2023-11-01`).
   - Impacto: las series `EMPLEO_PRIVADO_TEXTIL`, `EMPLEO_PRIVADO_INDUMENTARIA`, `REMUNERACION_TEXTIL` y `REMUNERACION_INDUMENTARIA` muestran cobertura verificada 2007-01 a 2023-11. Para cobertura hasta 2026 se incluyen además las series SIPA de Industria Manufacturera y Total País (`152.1`, `157.1`, `158.1`).
   - Solución futura: incorporar un conector parser de los boletines SIPA en formato `.xlsx` publicados por la Secretaría de Trabajo (`Boletín de Situación y Evolución del Trabajo Registrado`), si publican apertura a 2 dígitos posterior a 2023.

2. **Comercio exterior desagregado por capítulo NCM (`163.3` y `162.3`)**:
   - Fuente: SSPM / INDEC (`infra.datos.gob.ar`).
   - Limitación observada: las distribuciones CSV a 2 dígitos NCM disponibles en `infra.datos.gob.ar` llegan hasta **febrero de 2025** (`2025-02-01`) y solo reportan valores monetarios (USD CIF/FOB), sin toneladas ni país de origen/destino.
   - Impacto: se documenta el rezago mediante el hallazgo `OFFICIAL_PUBLICATION_LAG` en el Data Auditor y se proveen los totales generales de comercio exterior ICA (`75.3`, `76.3`) actualizados hasta 2026-09 como contexto.
   - Solución futura: integrar consulta/descarga de microdatos aduaneros anuales/mensuales de **ComEX INDEC** (`comex.indec.gov.ar`) para incorporar peso neto (kg), cantidades y apertura bilateral por país de origen/destino.

3. **Erratas ortográficas en encabezados oficiales de SSPM**:
   - El CSV oficial `163.3` utiliza literalmente `m_prendas_complementos_accesorios_vestir_emcepto_punto` y `m_demas_fibras_temtiles_vegetales_hilados_papel`. El conector conserva la trazabilidad literal del `source_series_code` y lo traduce a un código limpio en `core.series`.

4. **IPI Manufacturero por subclase vs. estacionalidad**:
   - El INDEC publica las aperturas textiles (`453.2`) únicamente en serie original (sin ajuste estacional), con cobertura desde enero de 2016 (`2016-01-01`). Para perspectiva larga desde 2004 se complementa con `EMAE_INDUSTRIA`.

5. **Informalidad laboral y talleres no registrados**:
   - Los registros SIPA capturan exclusivamente empleo asalariado formal privado, lo cual subestima la ocupación total en confección de indumentaria (donde históricamente existe trabajo no registrado y cuentapropismo). Se advierte explícitamente en la ficha educativa Nivel 2.
