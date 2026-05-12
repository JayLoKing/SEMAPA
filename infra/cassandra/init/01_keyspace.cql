-- ============================================================================
-- SEMAPA - Keyspace
-- ============================================================================

CREATE KEYSPACE IF NOT EXISTS semapa
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 2
}
AND durable_writes = true;

-- NOTA PARA PRODUCCIÓN: usar NetworkTopologyStrategy
-- CREATE KEYSPACE semapa WITH replication = {
--     'class': 'NetworkTopologyStrategy',
--     'datacenter1': 3
-- };
