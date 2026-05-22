# Entregable 6 — Guía de Entrevista para Levantamiento de Requerimientos Analíticos

Objetivo: levantar requerimientos de los 3 dashboards (Alcaldía, Gerencia, Contabilidad)
mediante entrevistas a los responsables de decisión de SEMAPA.

---

## A. Alcalde / Concejo Municipal (Nivel Estratégico — ODS / Smart City)

1. ¿Qué indicadores de acceso al agua necesita revisar para reportar a cooperación
   internacional y alinear con los ODS 6, 11, 13 y 3?
2. ¿Qué nivel de granularidad geográfica requiere: ciudad, subalcaldía, distrito o zona?
3. ¿Qué umbral de consumo per cápita (litros/persona/día) considera "crítico" para
   activar políticas públicas? (referencia ONU: 6 niveles, 0→>400 L)
4. ¿Qué eventos climáticos (sequía, ola de calor) deben cruzarse con el consumo y
   generar alertas en el tablero?
5. ¿Con qué frecuencia revisa estos indicadores: diaria, semanal o mensual?
6. ¿Qué decisiones presupuestarias o de inversión dependen directamente del dashboard?
7. ¿Qué zonas vulnerables deben monitorearse prioritariamente por brecha de acceso?
8. ¿Necesita comparativos año contra año o proyecciones de demanda futura?
9. ¿Qué KPI de infraestructura inteligente (sensores activos, cobertura LoRaWAN)
   es relevante para justificar la modernización ante el Concejo?
10. ¿Qué formato de exportación necesita para presentaciones oficiales (PDF, imagen)?

## B. Directorio / Gerencia SEMAPA (Nivel Táctico-Operativo)

1. ¿Qué indicadores operativos necesita revisar a diario para la toma de decisiones?
2. ¿Qué define una "anomalía" accionable: posible fuga, consumo atípico, lectura faltante?
3. ¿Qué umbral de fallas por modelo de medidor dispara una orden de mantenimiento?
4. ¿Necesita ranking de las top-N zonas por demanda para planificar distribución?
5. ¿Qué latencia de ingestión de lecturas es aceptable antes de considerarla un problema?
6. ¿Qué métricas de productividad institucional (lecturas por app móvil, tiempo de
   procesamiento, disponibilidad del sistema) deben mostrarse?
7. ¿Cómo prioriza el envío de cuadrillas de inspección según el tablero?
8. ¿Qué porcentaje de sensores con error es tolerable antes de escalar?
9. ¿Requiere monitoreo en tiempo real o snapshots periódicos?
10. ¿Qué reportes necesita exportar para el directorio mensual?

## C. Departamento Financiero / Contabilidad (Nivel Financiero)

1. ¿Qué KPI financieros necesita revisar diariamente (facturado, recaudado, mora)?
2. ¿Cómo define cartera vencida y a partir de cuántos periodos un contrato es "incobrable"?
3. ¿Qué granularidad necesita para facturación: por distrito, por categoría tarifaria?
4. ¿Qué canal de cobranza (SMS, WhatsApp, email) desea medir en efectividad/conversión?
5. ¿Qué eventos deben generar alertas (caída de recaudación, pico de mora)?
6. ¿Necesita aging de deuda (antigüedad) y ranking de grandes deudores?
7. ¿Qué proyección financiera requiere: 3 meses, escenarios de incremento tarifario?
8. ¿Qué tasa de recuperación objetivo define el éxito de la cobranza preventiva?
9. ¿Necesita comparar presupuesto vs. real?
10. ¿Qué decisiones tarifarias dependen del análisis de elasticidad consumo/precio?

---

### Notas de aplicación
- Entrevistas semiestructuradas, 30–45 min, grabadas con consentimiento.
- Cada respuesta se traduce a un KPI, su fuente de datos (tabla Cassandra) y su
  visualización (card, serie temporal, mapa, ranking).
- Validación cruzada: prototipo navegable revisado con cada stakeholder antes de
  fijar el dashboard final.
