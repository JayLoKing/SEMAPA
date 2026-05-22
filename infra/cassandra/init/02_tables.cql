-- ============================================================================
-- SEMAPA - Definición de tablas (wide-column store) — MODELO REAL (CSV)
-- Join keys naturales: medidor_iot (MAC), numero_catastro, numero_contrato
-- ============================================================================

USE semapa;

-- ============================================================================
-- CATÁLOGOS (cargados desde data/seeds/*.csv)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sub_alcaldias (
    sub_alcaldia_id int PRIMARY KEY,
    nombre text
);

CREATE TABLE IF NOT EXISTS distritos (
    distrito_id int PRIMARY KEY,
    sub_alcaldia_id int,
    nombre text,
    habitantes int
);

-- zona_id NO es único (una zona aparece en varios distritos) → PK compuesta
CREATE TABLE IF NOT EXISTS zonas (
    distrito_id int,
    zona_id int,
    nombre text,
    gateway_id int,
    habitantes int,
    total_medidores int,
    PRIMARY KEY ((distrito_id), zona_id)
);

CREATE TABLE IF NOT EXISTS gateways (
    gateway_id int PRIMARY KEY,
    nombre text,
    latitud double,
    longitud double
);

CREATE TABLE IF NOT EXISTS modelos_medidor (
    modelo_id int PRIMARY KEY,
    marca text,
    modelo text,
    conectividad text,
    aplicacion text
);

CREATE TABLE IF NOT EXISTS tarifas (
    categoria text PRIMARY KEY,
    alias text,
    fijo_m3 decimal,
    usd_mes decimal,
    r_13_25 decimal,
    r_26_50 decimal,
    r_51_75 decimal,
    r_76_100 decimal,
    r_101_150 decimal,
    r_mas_151 decimal,
    descripcion text
);

CREATE TABLE IF NOT EXISTS errores_iot (
    codigo int PRIMARY KEY,
    descripcion text
);

CREATE TABLE IF NOT EXISTS tipos_infraestructura (
    tipo_id int PRIMARY KEY,
    descripcion text
);

-- ============================================================================
-- INFRAESTRUCTURAS  (data/infraestructuras.csv) — PK numero_catastro
-- ============================================================================

CREATE TABLE IF NOT EXISTS infraestructuras (
    numero_catastro text PRIMARY KEY,
    propietario text,
    ci text,
    direccion text,
    zona text,
    distrito_id int,
    manzano int,
    lote int,
    superficie_terreno int,
    area_construida int,
    uso_suelo text,
    matricula_ddrr text,
    valor_catastral decimal,
    impuesto_anual decimal,
    latitud double,
    longitud double
);

-- ============================================================================
-- MEDIDORES IoT  (data/medidores.csv) — PK mac
-- Denormaliza datos de contrato/infra para drill-down del mapa.
-- ============================================================================

CREATE TABLE IF NOT EXISTS medidores (
    mac text PRIMARY KEY,
    fecha_instalacion date,
    fecha_desinstalacion date,
    estado text,                    -- Operativo|Reacondicionado|Mantenimiento|Dañado|Nuevo
    tipo_medidor_id int,
    -- denormalizado desde contrato/infra:
    numero_contrato text,
    numero_catastro text,
    categoria text,                 -- Residencial|Comercial|...
    subcategoria text,              -- R1..R4, C, CE, I, P, S
    zona text,
    distrito_id int,
    gateway_id int,
    latitud double,
    longitud double
);

-- ============================================================================
-- CONTRATOS  (data/contratos.csv) — PK numero_contrato (CT-00000001)
-- ============================================================================

CREATE TABLE IF NOT EXISTS contratos (
    numero_contrato text PRIMARY KEY,
    numero_catastro text,
    titular_contrato text,
    ci_titular text,
    categoria text,
    subcategoria text,
    medidor_iot text,               -- MAC
    fecha_contrato date,
    estado_contrato text,
    diametro_conexion text,
    tipo_servicio text
);

-- Índice de búsqueda: contrato/catastro por MAC
CREATE TABLE IF NOT EXISTS contrato_por_mac (
    medidor_iot text PRIMARY KEY,
    numero_contrato text,
    numero_catastro text,
    categoria text,
    subcategoria text,
    titular_contrato text,
    ci_titular text
);

-- Búsqueda de contratos por documento (CI)
CREATE TABLE IF NOT EXISTS contratos_por_ci (
    ci_titular text,
    numero_contrato text,
    medidor_iot text,
    PRIMARY KEY ((ci_titular), numero_contrato)
);

-- ============================================================================
-- MAPA: medidores por distrito/zona para drill-down interactivo
-- Click distrito → lista medidores; click medidor → info completa.
-- ============================================================================

CREATE TABLE IF NOT EXISTS medidores_por_zona (
    distrito_id int,
    zona text,
    mac text,
    numero_contrato text,
    titular text,
    categoria text,
    subcategoria text,
    estado text,
    latitud double,
    longitud double,
    PRIMARY KEY ((distrito_id), zona, mac)
);

-- ============================================================================
-- LECTURAS  (data/lecturas.csv)
-- lecturaAnterior/LecturaActual en m³; consumo = actual - anterior.
-- Particionado por (mac) → historial por medidor; clustering por fecha desc.
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_por_medidor (
    mac text,
    periodo text,                   -- '2026-02'
    fecha_hora timestamp,
    lectura_anterior int,
    lectura_actual int,
    consumo_m3 int,
    radiobase int,                  -- gateway_id
    fecha_pago timestamp,           -- null si impago
    status int,                     -- 1=OK, 2=Manual, 3..9=errores
    PRIMARY KEY ((mac), periodo, fecha_hora)
) WITH CLUSTERING ORDER BY (periodo DESC, fecha_hora DESC)
  AND compression = {'sstable_compression': 'LZ4Compressor'}
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};

-- Vista denormalizada para consultas del dashboard por zona/periodo
CREATE TABLE IF NOT EXISTS lecturas_por_zona_periodo (
    distrito_id int,
    zona text,
    periodo text,
    mac text,
    consumo_m3 int,
    subcategoria text,
    PRIMARY KEY ((distrito_id, periodo), zona, mac)
);

-- Auditoría: lecturas crudas del simulador/ingestor
CREATE TABLE IF NOT EXISTS lecturas_raw (
    gateway_id int,
    fecha date,
    ts timestamp,
    mac text,
    payload text,
    procesado boolean,
    error_motivo text,
    PRIMARY KEY ((gateway_id, fecha), ts, mac)
);

-- Lecturas manuales (app móvil)
CREATE TABLE IF NOT EXISTS lecturas_manuales (
    mac text,
    fecha_hora timestamp,
    usuario text,
    lectura_actual int,
    lat double,
    lon double,
    foto_url text,
    PRIMARY KEY ((mac), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC);

-- ============================================================================
-- FACTURACIÓN / PREAVISOS
-- ============================================================================

CREATE TABLE IF NOT EXISTS facturas (
    numero_contrato text,
    periodo text,                   -- '2026-02'
    factura_id uuid,
    mac text,
    consumo_m3 decimal,
    monto_usd decimal,
    monto_bs decimal,
    tipo_cambio decimal,
    categoria_tarifa text,          -- R1..R4, C, CE, I, P, S
    desglose text,                  -- JSON tramos
    fecha_emision timestamp,
    fecha_pago timestamp,
    estado text,                    -- 'PENDIENTE' | 'PAGADA' | 'ANULADA'
    PRIMARY KEY ((numero_contrato), periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);

CREATE TABLE IF NOT EXISTS facturas_por_periodo (
    periodo text,
    distrito_id int,
    numero_contrato text,
    monto_bs decimal,
    monto_usd decimal,
    consumo_m3 decimal,
    categoria_tarifa text,
    estado text,
    PRIMARY KEY ((periodo, distrito_id), numero_contrato)
);

-- ============================================================================
-- TÓTEM AUTOSERVICIO: reclamos/fugas, pagos QR, actualización de contacto
-- ============================================================================

CREATE TABLE IF NOT EXISTS reclamos (
    numero_contrato text,
    reclamo_id timeuuid,
    tipo text,                      -- FUGA | RECLAMO | OTRO
    descripcion text,
    creado_en timestamp,
    estado text,                    -- ABIERTO | CERRADO
    PRIMARY KEY ((numero_contrato), reclamo_id)
) WITH CLUSTERING ORDER BY (reclamo_id DESC);

CREATE TABLE IF NOT EXISTS pagos (
    numero_contrato text,
    periodo text,
    pago_id timeuuid,
    monto_bs decimal,
    metodo text,                    -- QR_SIMULADO
    pagado_en timestamp,
    PRIMARY KEY ((numero_contrato), periodo, pago_id)
) WITH CLUSTERING ORDER BY (periodo DESC, pago_id DESC);

CREATE TABLE IF NOT EXISTS contactos (
    numero_contrato text PRIMARY KEY,
    telefono text,
    email text,
    actualizado_en timestamp
);

-- ============================================================================
-- AUTH (sistema)
-- ============================================================================

CREATE TABLE IF NOT EXISTS usuarios_sistema (
    username text PRIMARY KEY,
    password_hash text,
    rol text,                       -- 'ALCALDIA' | 'GERENCIA' | 'CONTABILIDAD'
    nombre text,
    email text,
    activo boolean,
    fecha_creacion timestamp,
    ultimo_acceso timestamp
);
