from app.catalog.series_catalog_part1 import CATEGORY_DEFINITIONS, SERIES_CATALOG_PART1
from app.catalog.series_catalog_part2 import SERIES_CATALOG_PART2

SERIES_CATALOG = SERIES_CATALOG_PART1 + SERIES_CATALOG_PART2
SERIES_BY_CODE = {s["series_code"]: s for s in SERIES_CATALOG}
CATEGORY_BY_CODE = {c["code"]: c for c in CATEGORY_DEFINITIONS}

# All 14 NCM Section XI (Chapters 50-63) official SSPM CSV columns for exact total chain computation
NCM_IMPO_COLUMNS_50_63 = [
    ("50", "m_seda"),
    ("51", "m_lana_pelo_fino_ordinario_hilados_tejidos_crin"),
    ("52", "m_algodon"),
    ("53", "m_demas_fibras_temtiles_vegetales_hilados_papel"),
    ("54", "m_filamentos_sinteticos_artificiales"),
    ("55", "m_fibras_sinteticas_artificiales_discontinuas"),
    ("56", "m_guata_fieltro_telas_sin_tejer_hilados_especiales"),
    ("57", "m_alfombras_demas_revestimientos_suelo_materia_temtil"),
    ("58", "m_tejidos_especiales_superficies_textiles"),
    ("59", "m_telas_impregnadas_recubiertas_revestidas"),
    ("60", "m_tejido_punto"),
    ("61", "m_prendas_complementos_accesorios_vestir_punto"),
    ("62", "m_prendas_complementos_accesorios_vestir_emcepto_punto"),
    ("63", "m_demas_articulos_textiles_confeccionados"),
]

NCM_EXPO_COLUMNS_50_63 = [
    ("50", "x_seda"),
    ("51", "x_lana_pelo_fino_ordinario_hilados_tejidos_crin"),
    ("52", "x_algodon"),
    ("53", "x_demas_fibras_textiles_vegetales_hilados"),
    ("54", "x_filamentos_sinteticos_artificiales"),
    ("55", "x_fibras_sinteticas_artificiales_discontinuas"),
    ("56", "x_guata_fieltro_telas_sin_tejer_hilados_especiales_cordeles"),
    ("57", "x_alfombras_demas_revestimientos_suelo_materia_textil"),
    ("58", "x_tejidos_especiales_superficies_textiles_mechon_insertado"),
    ("59", "x_telas_impregnadas_recubiertas_revestidas"),
    ("60", "x_tejido_punto"),
    ("61", "x_prendas_complementos_accesorios_vestir_punto"),
    ("62", "x_prendas_complementos_accesorios_vestir_excepto_punto"),
    ("63", "x_demas_articulos_textiles_confeccionados"),
]
