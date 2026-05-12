-- ============================================================================
-- SEMAPA - Definición de tablas (wide-column store)
-- ============================================================================

USE semapa;

-- ============================================================================
-- CATÁLOGOS
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

CREATE TABLE IF NOT EXISTS zonas (
    distrito_id int,
    zona_id int,
    nombre text,
    gateway_id int,
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
-- PERSONAS Y CLIENTES
-- ============================================================================

CREATE TABLE IF NOT EXISTS personas (
    persona_id uuid PRIMARY KEY,
    tipo text,                      -- 'NATURAL' | 'JURIDICA'
    documento text,                 -- CI o NIT
    nombre text,
    apellidos text,
    razon_social text,
    email text,
    telefono text,
    fecha_registro timestamp
);

-- ============================================================================
-- INFRAESTRUCTURAS (viviendas, edificios, hospitales, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS infraestructuras (
    infraestructura_id uuid PRIMARY KEY,
    persona_id uuid,
    tipo_infra int,                 -- FK a tipos_infraestructura
    distrito_id int,
    zona_id int,
    direccion text,
    latitud double,
    longitud double
);

-- ============================================================================
-- MEDIDORES IoT
-- ============================================================================

CREATE TABLE IF NOT EXISTS medidores (
    medidor_id uuid PRIMARY KEY,
    mac text,                       -- AB:CB:12:13:56
    numero_serie text,              -- SN=254-41269-1411
    numero_contrato bigint,
    infraestructura_id uuid,
    modelo_id int,
    categoria_tarifa text,          -- R1..R4, C, CE, I, P, S
    gateway_id int,
    distrito_id int,
    zona_id int,
    latitud double,
    longitud double,
    fecha_instalacion date,
    estado text                     -- 'ACTIVO' | 'INACTIVO' | 'FUERA_SERVICIO'
);

-- ============================================================================
-- LECTURAS (time-series, tabla grande ~1 GB)
-- Particionado por (medidor_id, anio_mes) → particiones pequeñas y balanceadas
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_por_medidor (
    medidor_id uuid,
    anio_mes int,                   -- 202504, 202505
    fecha_hora timestamp,
    gateway_id int,
    lectura_litros bigint,          -- acumulado
    consumo_litros int,             -- diferencial vs lectura previa
    status int,                     -- 1=OK, 2=Manual, 3..9=errores
    PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC)
  AND compression = {'sstable_compression': 'LZ4Compressor'}
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};

-- Vista denormalizada para consultas del dashboard por zona/día/hora
CREATE TABLE IF NOT EXISTS lecturas_por_zona_dia (
    distrito_id int,
    zona_id int,
    fecha date,
    hora int,                       -- 0..23
    medidor_id uuid,
    consumo_litros int,
    categoria_tarifa text,
    PRIMARY KEY ((distrito_id, zona_id, fecha), hora, medidor_id)
);

-- Vista para cobertura: cuántos medidores reporta cada gateway/zona
CREATE TABLE IF NOT EXISTS cobertura_gateway (
    gateway_id int,
    zona_id int,
    medidor_id uuid,
    ultima_lectura timestamp,
    PRIMARY KEY ((gateway_id), zona_id, medidor_id)
);

-- ============================================================================
-- FACTURACIÓN
-- ============================================================================

CREATE TABLE IF NOT EXISTS facturas (
    numero_contrato bigint,
    periodo text,                   -- '2025-05'
    factura_id uuid,
    medidor_id uuid,
    persona_id uuid,
    consumo_m3 decimal,
    monto_usd decimal,
    monto_bs decimal,
    tipo_cambio decimal,
    categoria_tarifa text,
    desglose text,                  -- JSON con tramos aplicados
    fecha_emision timestamp,
    estado text,                    -- 'PENDIENTE' | 'PAGADA' | 'ANULADA'
    PRIMARY KEY ((numero_contrato), periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);

CREATE TABLE IF NOT EXISTS facturas_por_periodo (
    periodo text,
    distrito_id int,
    numero_contrato bigint,
    monto_usd decimal,
    consumo_m3 decimal,
    categoria_tarifa text,
    PRIMARY KEY ((periodo, distrito_id), numero_contrato)
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

-- ============================================================================
-- AUDITORÍA: lecturas crudas tal como llegan del simulador (para debugging)
-- ============================================================================

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

-- ============================================================================
-- LECTURAS MANUALES (app móvil)
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_manuales (
    medidor_id uuid,
    fecha_hora timestamp,
    usuario text,
    lectura_litros bigint,
    lat double,
    lon double,
    foto_url text,
    PRIMARY KEY ((medidor_id), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC);
