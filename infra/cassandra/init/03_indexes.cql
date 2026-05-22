-- ============================================================================
-- SEMAPA - Índices secundarios (modelo MAC-céntrico)
-- Usar con moderación: en Cassandra los índices son costosos.
-- ============================================================================

USE semapa;

-- Infraestructuras
CREATE INDEX IF NOT EXISTS idx_infra_distrito ON infraestructuras (distrito_id);

-- Medidores (mac es PK → no se indexa). Filtros del dashboard:
CREATE INDEX IF NOT EXISTS idx_medidor_contrato ON medidores (numero_contrato);
CREATE INDEX IF NOT EXISTS idx_medidor_catastro ON medidores (numero_catastro);
CREATE INDEX IF NOT EXISTS idx_medidor_distrito ON medidores (distrito_id);
CREATE INDEX IF NOT EXISTS idx_medidor_gateway ON medidores (gateway_id);
CREATE INDEX IF NOT EXISTS idx_medidor_estado ON medidores (estado);
CREATE INDEX IF NOT EXISTS idx_medidor_subcategoria ON medidores (subcategoria);

-- Contratos: búsqueda por MAC y por catastro
CREATE INDEX IF NOT EXISTS idx_contrato_mac ON contratos (medidor_iot);
CREATE INDEX IF NOT EXISTS idx_contrato_catastro ON contratos (numero_catastro);

-- Facturas: filtro por estado (morosos/pagadas)
CREATE INDEX IF NOT EXISTS idx_factura_estado ON facturas (estado);

-- Lecturas: filtro por status (anomalías) — partición grande, usar con LIMIT
CREATE INDEX IF NOT EXISTS idx_lectura_status ON lecturas_por_medidor (status);
