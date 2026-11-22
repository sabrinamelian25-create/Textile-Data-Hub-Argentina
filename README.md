# Textile Data Hub Argentina (MVP)

Plataforma académica de datos económicos oficiales verificados orientada a estudiantes universitarios de Economía y Finanzas para investigar el complejo textil e indumentaria argentino.

> **Principio rector:** Reducir el coste de encontrar, comprender, auditar, comparar y descargar series oficiales dispersas (INDEC, BCRA, Secretaría de Trabajo / SIPA, CEP XXI / Sec. de Industria y Comercio, SSPM Datos Argentina) **sin producir conclusiones automáticas ni reemplazar el razonamiento económico del estudiante**.

---

## Arquitectura del sistema

```text
FUENTES OFICIALES (INDEC, BCRA, Sec. Trabajo/SIPA, CEP XXI, SSPM Datos Argentina)
  ↓
CONECTORES MODULARES (discover → download → validate → parse → normalize)
  ↓
RAW (raw.raw_extractions + snapshots inmutables con SHA-256)
  ↓
STAGING (staging.staged_observations)
  ↓
DATA AUDITOR (Procedencia · Integridad · Estructura · Estadística · Revisiones · Quality Score)
  ↓
CORE PostgreSQL (core.series · core.observations formato LONG con historial de revisiones)
  ↓
API REST FastAPI + OpenAPI (/docs)
  ↓
FRONTEND Next.js + TypeScript + Tailwind CSS + ECharts
```

---

## Módulos funcionales implementados

1. **Buscador inteligente (`/`)**: Tolerante a tildes, mayúsculas, singular/plural y sinónimos académicos (`"precio de la ropa"`, `"producción textil"`, `"importaciones de prendas"`, `"algodón"`, `"salarios textiles"`), explicando el motivo de coincidencia.
2. **Explorador sectorial (`/explorar`)**: Organizado en 5 dimensiones:
   - *Actividad y producción* (IPI manufacturero y aperturas textiles/prendas, UCII, EMAE industria)
   - *Precios y costes* (IPC prendas, IPIM textil/prendas/manufacturas/energía eléctrica, Precio relativo derivado)
   - *Comercio exterior* (Importaciones CIF y Exportaciones FOB NCM Capítulos 50–63, agregados de cadena y saldo comercial)
   - *Empleo y salarios* (SIPA agregado e industria, CEP XXI CLAE 13 y CLAE 14, RIPTE nominal y salarios reales deflactados por IPC)
   - *Contexto macroeconómico* (identificadas explícitamente como `VARIABLE DE CONTEXTO`)
3. **Página de indicador (`/indicador/[series_code]`)**: Lectura rápida (Nivel 1), gráfico interactivo único con `1A | 3A | 5A | 10A | MÁX | PERSONALIZADO` y `NIVEL | VAR % MENSUAL | VAR % INTERANUAL | BASE 100`, explicaciones académicas (Nivel 2), glosario contextual `[i]`, ficha metodológica avanzada colapsable, modal de trazabilidad en 9 pasos y descarga lista para Excel/Python/R/Stata.
4. **Comparador (`/comparar`)**: Cruce de 2 a 4 series con alineación opcional de series diarias a mensuales, alertas metodológicas automáticas (unidades, frecuencias, estacionalidad, nominal vs. real, cobertura) y recordatorio explícito de **Correlación ≠ Causalidad**.
5. **Modo Research (`/research`)**: Recorrido guiado desde una pregunta económica hacia una *posible estructura exploratoria de investigación*, visualización comparativa y exportación reproducible con fragmentos listos para `pandas` y `R`.
6. **Cadena productiva NCM 50–63 (`/cadena-textil`)**: Mapeo oficial de los 14 capítulos textiles a lo largo de los 5 eslabones productivos (`trade_product_mapping`).
7. **Estructura de la industria (`/estructura-industria` — Módulo Experimental)**: Análisis de la estructura empresarial modelando cuatro dimensiones estrictamente independientes (**Tamaño**, **Origen**, **Modelo productivo** y **Posición en la cadena** multi-posición) con tablas `core.companies`, `core.company_chain_positions` y `core.company_classification_history`, auditor automático de evidencia oficial (`CompanyClassificationAuditor`), filtros combinables, exportación CSV/JSON e integración directa con **Modo Research** sin inferir causalidad.
8. **Data Auditor (`/data-auditor`)**: Panel de transparencia y control con contadores `VERIFIED / WARNING / PENDING / REJECTED`, puntaje diagnóstico `Data Quality Score (0–100)`, historial de corridas y ejecución manual de conectores.

---

## Cómo ejecutar el proyecto

### Opción A: Ejecución nativa en Windows (sin Docker Desktop)

Los scripts incluidos utilizan PostgreSQL 16 portable y Node.js 24 LTS ubicados en `.tools/` más el entorno virtual `backend/.venv`.

```powershell
# 1. Iniciar PostgreSQL 16 en puerto 5432
powershell -ExecutionPolicy Bypass -File .\scripts\start_db.ps1

# 2. Aplicar migraciones, poblar catálogo y ejecutar ingesta oficial completa
powershell -ExecutionPolicy Bypass -File .\scripts\ingest_all.ps1

# 3. Levantar API FastAPI (:8000) y Frontend Next.js (:3000)
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

Abrir en el navegador:
- **Aplicación web:** `http://localhost:3000`
- **Documentación OpenAPI:** `http://localhost:8000/docs`

### Opción B: Con Docker Compose

```bash
docker compose up --build -d
# Ejecutar ingesta inicial dentro del contenedor backend
docker compose exec backend python -m app.cli ingest --all
```

---

## Pruebas automatizadas (`pytest`)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -v
```

Incluye tests unitarios e integración para Data Auditor (procedencia, duplicados, gaps, outliers, historial de revisiones, preservación ante fallos), transformaciones estadísticas, conectores (incluyendo parser del `.xls` oficial del INDEC), API REST y exportaciones CSV/ZIP/XLSX/JSON.

---

## Documentación técnica adicional

- [Inventario de fuentes oficiales y 49 series del MVP](docs/SOURCES_AND_SERIES_INVENTORY.md)
- [Metodología del Data Auditor y Quality Score](docs/DATA_AUDITOR_METHODOLOGY.md)
- [Metodología del Módulo Experimental de Estructura Empresarial](docs/INDUSTRY_STRUCTURE_METHODOLOGY.md)
- [Limitaciones conocidas, rezagos oficiales y hoja de ruta](docs/LIMITATIONS_AND_ROADMAP.md)
