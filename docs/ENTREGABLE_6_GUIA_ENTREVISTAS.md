# Entregable 6 — Guía de Entrevistas para Levantamiento de Requerimientos Analíticos

**Proyecto:** Plataforma SEMAPA — Dashboards Estratégico / Táctico / Financiero
**Objetivo:** Recoger requerimientos reales de cada stakeholder antes de iterar el dashboard. Cada bloque tiene **10 preguntas guía** + 2 follow-ups sugeridos. Tiempo estimado por entrevista: 45–60 min.

---

## A. Entrevista al Alcalde / Concejo Municipal (Dashboard Estratégico — ODS / Smart City)

**Público:** Alcalde, Secretario de Planificación, Secretario de Medio Ambiente, Cooperación Internacional.
**Marco de referencia:** ODS 6 (Agua y saneamiento), ODS 11 (Ciudades sostenibles), ODS 13 (Acción climática), ODS 3 (Salud).

1. ¿Qué indicadores de cobertura del servicio de agua necesita revisar al menos una vez por mes y cuáles diariamente?
2. ¿Cuál es la meta política de cobertura de la actual gestión (% de hogares con agua potable) y en qué horizonte temporal?
3. ¿Qué eventos de consumo o estrés hídrico deben generar una alerta inmediata a su despacho?
4. ¿Cómo le gustaría visualizar las desigualdades de consumo entre distritos: mapa coroplético, ranking, semáforo?
5. ¿Qué decisiones de inversión pública (ampliación de redes, plantas de tratamiento) dependen directamente de los datos del dashboard?
6. ¿Qué nivel de granularidad geográfica necesita: subalcaldía, distrito, zona, manzana?
7. ¿A qué niveles de consumo per cápita (litros/persona/día) considera crítico para emitir comunicados oficiales?
8. ¿Cómo deben relacionarse las métricas de SEMAPA con los reportes de cooperación internacional (ODS, BID, ONU-Habitat)?
9. ¿Qué información debería poder mostrar en una conferencia de prensa sin asistencia técnica?
10. ¿Qué frecuencia de actualización del dashboard considera aceptable: tiempo real, diaria, semanal?

*Follow-ups:* ¿Quién más en su gabinete debería tener acceso? ¿Necesita exportar reportes a PDF/PowerPoint?

---

## B. Entrevista al Directorio / Gerencia SEMAPA (Dashboard Táctico-Operativo)

**Público:** Gerente General, Jefe de Operaciones, Jefe de Mantenimiento, Jefe Comercial.
**Enfoque:** Eficiencia operativa, salud de la red IoT, gestión de anomalías, productividad.

1. ¿Qué indicadores operativos diarios definen si el día fue "normal" o "anormal" en la red?
2. ¿Cuáles son los SLA internos para detectar y atender una posible fuga o consumo atípico?
3. ¿Qué umbrales de error en lecturas IoT consideran tolerables vs. requieren intervención de campo?
4. ¿Qué información necesita el equipo de mantenimiento para priorizar visitas a campo (ranking de zonas, edad de medidores)?
5. ¿Cómo medirían el éxito del despliegue de nuevos medidores: por cobertura, por reducción de fallas, por consumo registrado?
6. ¿Qué reportes mensuales presentan al directorio y qué datos están manualmente recolectando hoy?
7. ¿Qué decisiones comerciales (suspender contratos, otorgar facilidades) requieren validación con datos del dashboard?
8. ¿Cómo desean monitorear la productividad del personal de lectura manual vs. lecturas IoT automatizadas?
9. ¿Qué patrones de consumo horario / estacional ya conocen y desean validar empíricamente?
10. ¿Qué alertas deberían enviarse a su teléfono móvil fuera de horario laboral?

*Follow-ups:* ¿Necesitan integración con sistemas legacy (SCADA, GIS)? ¿Quién es el responsable de validar las alertas?

---

## C. Entrevista al Departamento Financiero / Contabilidad SEMAPA (Dashboard Financiero)

**Público:** Director Financiero, Jefe de Facturación, Jefe de Cobranzas, Auditoría Interna.
**Enfoque:** Facturación, recaudación, morosidad, eficiencia de canales de cobranza.

1. ¿Cuál es el ciclo de facturación actual y cuáles son las fechas críticas (corte, emisión, vencimiento)?
2. ¿Qué KPIs financieros revisan a diario, semanal y mensual?
3. ¿Cómo se define hoy "cartera vencida" y a partir de qué edad de deuda se inician acciones legales?
4. ¿Qué canales de cobranza usan actualmente (ventanilla, banco, pasarela, kiosco) y cuál tiene mejor conversión?
5. ¿Qué información requiere el dashboard para proyectar el flujo de caja a 3 y 6 meses?
6. ¿Qué impacto tendría un incremento tarifario diferenciado por categoría sobre la recaudación esperada?
7. ¿Qué datos necesitan los auditores externos y cómo deberían exponerse desde el dashboard?
8. ¿Cómo miden hoy la efectividad de los preavisos enviados (tasa de apertura, conversión a pago)?
9. ¿Qué alertas tempranas necesitan sobre contratos en riesgo de mora antes del vencimiento?
10. ¿Qué reportes regulatorios deben exportarse automáticamente desde el sistema?

*Follow-ups:* ¿Tienen plan de subsidios por categoría tarifaria? ¿Necesitan trazabilidad de quién emitió cada acción cobranza?

---

## D. Preguntas Transversales (aplicables a los 3 perfiles)

1. ¿Qué dashboards o reportes utiliza actualmente y qué le falta?
2. ¿Cuál es su mayor dolor diario relacionado con disponibilidad de datos?
3. ¿Qué dispositivos usa para consultar información: PC, tablet, móvil?
4. ¿Necesita compartir vistas con terceros (consultores, ciudadanos, otras alcaldías)?
5. ¿Qué nivel de seguridad/autenticación esperan (SSO, MFA, roles)?
6. ¿Qué datos NO deben aparecer nunca en pantalla pública (PII, montos individuales)?
7. ¿Está dispuesto a aceptar latencia de datos a cambio de mayor profundidad analítica?
8. ¿En qué idiomas y unidades (m³, litros, Bs, USD) prefiere ver los reportes?
9. ¿Quién debe poder editar parámetros del sistema (tarifas, umbrales, alertas)?
10. ¿Qué tan crítico es exportar a Excel/PDF/PowerPoint y con qué frecuencia?

---

## Metodología recomendada

- **Formato:** entrevistas 1:1, grabadas con consentimiento, duración 45–60 min.
- **Herramientas:** Miro/FigJam para mapear flujos, planilla de KPIs por entrevista.
- **Salida esperada:**
  - Lista priorizada de KPIs (P0/P1/P2) por rol.
  - Wireframes validados por cada stakeholder.
  - Backlog de iteración del dashboard (sprints de 2 semanas).
- **Validación:** prototipo navegable al cierre de cada sprint con cada rol.

---

## Mapeo de preguntas a KPIs ya implementados en SEMAPA

| Pregunta | KPI / endpoint que la responde |
|---|---|
| Cobertura por distrito (A.1) | `GET /dashboard/alcaldia` → `cobertura_pct`, `poblacion_beneficiaria` |
| Consumo per cápita (A.7) | `GET /consultas/per-capita-residencial` |
| Alertas sobreconsumo (A.3, B.10) | `GET /dashboard/alcaldia` → `alertas_sobreconsumo` |
| Top zonas por consumo (B.4) | `GET /dashboard/gerencia` → `top10_zonas_consumo` |
| Lecturas por app móvil (B.8) | `GET /dashboard/gerencia` → `lecturas_app_movil` |
| Pico horario (B.9) | `GET /dashboard/gerencia` → `pico_horario`, `pico_max_hora` |
| Edad medidores (B.5) | `GET /dashboard/gerencia` → `edad_promedio_medidores_anios` |
| Facturado mensual (C.2) | `GET /dashboard/contabilidad` → `facturado_bs` |
| Aging deuda (C.3) | `GET /dashboard/contabilidad` → `aging_deuda_bs` |
| Efectividad canal (C.8) | `GET /dashboard/contabilidad` → `efectividad_por_canal` |
| Preavisos emitidos (C.8) | `GET /dashboard/contabilidad` → `preavisos_emitidos_30d` |
| Facturación por categoría (C.6) | `GET /dashboard/contabilidad` → `facturado_por_categoria_tarifa` |
| Consumo vs clima (A.4) | `GET /consultas/consumo-vs-clima` |
| Estrés hídrico (A.7) | `GET /dashboard/alcaldia` → `zonas_critico_estres_hidrico` |
