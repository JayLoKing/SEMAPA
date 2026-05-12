-- ============================================================================
-- SEMAPA - Índices secundarios
-- Usar con moderación: en Cassandra los índices son costosos.
-- Solo se crean los estrictamente necesarios para el buscador y filtros.
-- ============================================================================

USE semapa;

-- Para búsqueda por documento (CI/NIT)
CREATE INDEX IF NOT EXISTS idx_personas_documento ON personas (documento);

-- Para búsqueda en infraestructuras
CREATE INDEX IF NOT EXISTS idx_infra_persona ON infraestructuras (persona_id);
CREATE INDEX IF NOT EXISTS idx_infra_distrito ON infraestructuras (distrito_id);

-- Para el buscador de medidores
CREATE INDEX IF NOT EXISTS idx_medidor_mac ON medidores (mac);
CREATE INDEX IF NOT EXISTS idx_medidor_contrato ON medidores (numero_contrato);
CREATE INDEX IF NOT EXISTS idx_medidor_serie ON medidores (numero_serie);
CREATE INDEX IF NOT EXISTS idx_medidor_categoria ON medidores (categoria_tarifa);
CREATE INDEX IF NOT EXISTS idx_medidor_distrito ON medidores (distrito_id);
CREATE INDEX IF NOT EXISTS idx_medidor_gateway ON medidores (gateway_id);
CREATE INDEX IF NOT EXISTS idx_medidor_estado ON medidores (estado);

-- Para listar facturas por persona
CREATE INDEX IF NOT EXISTS idx_factura_persona ON facturas (persona_id);
CREATE INDEX IF NOT EXISTS idx_factura_estado ON facturas (estado);
