# Entregable 7 — Estimación Económica y Simulación de Contratación Pública (DS 181)

Propuesta técnico-económica para la plataforma inteligente SEMAPA, bajo lineamientos
inspirados en el **Decreto Supremo N.º 181** (Normas Básicas del Sistema de Administración
de Bienes y Servicios). Principios aplicados: economía, eficiencia, transparencia,
competencia y sostenibilidad.

Moneda: Bolivianos (Bs). Tipo de cambio referencial 1 USD = 6.96 Bs.

---

## 1. Desarrollo del MVP (3 meses)

### 1.1 Recursos Humanos

| Rol | Cant. | Meses | Bs/mes | Subtotal Bs |
|-----|------:|------:|-------:|------------:|
| Arquitecto de software | 1 | 3 | 22 000 | 66 000 |
| Backend developer | 2 | 3 | 15 000 | 90 000 |
| Frontend developer | 1 | 3 | 14 000 | 42 000 |
| Mobile developer | 1 | 3 | 14 000 | 42 000 |
| Data engineer | 1 | 3 | 16 000 | 48 000 |
| DevOps | 1 | 3 | 16 000 | 48 000 |
| QA | 1 | 3 | 12 000 | 36 000 |
| Project Manager | 1 | 3 | 18 000 | 54 000 |
| **Subtotal RRHH** | | | | **426 000** |

### 1.2 Costos Administrativos y Operativos (3 meses)

| Concepto | Subtotal Bs |
|----------|------------:|
| Licencias / herramientas (IDEs, monitoreo, repos) | 12 000 |
| Equipamiento temporal de desarrollo | 25 000 |
| Servicios cloud (ambientes de prueba) | 18 000 |
| Internet y comunicaciones | 6 000 |
| Gestión documental | 4 000 |
| Capacitación / transferencia de conocimiento | 15 000 |
| **Subtotal Admin/Op** | **80 000** |

### 1.3 Costos Financieros e Impositivos

| Concepto | Base / Tasa | Bs |
|----------|-------------|----:|
| Subtotal costos directos (RRHH + Admin) | 426 000 + 80 000 | 506 000 |
| Utilidad esperada del proveedor | 15% | 75 900 |
| Contingencia / margen de riesgo | 5% | 25 300 |
| Subtotal antes de impuestos | | 607 200 |
| IVA | 13% | 78 936 |
| IT (Impuesto a las Transacciones) | 3% | 18 216 |
| Gastos bancarios / financieros | ~0.5% | 3 036 |
| **TOTAL MVP (3 meses)** | | **≈ 707 388 Bs** |

> Nota: el RC-IVA aplica como retención sobre haberes del personal dependiente;
> se gestiona en planilla, no se suma al precio ofertado.

---

## 2. Operación en Producción (2 años)

| Concepto | Bs/mes | 24 meses Bs |
|----------|-------:|------------:|
| Servidores (clúster Cassandra 2 nodos + API) | 9 000 | 216 000 |
| Almacenamiento + backups | 2 500 | 60 000 |
| Monitoreo / observabilidad | 1 500 | 36 000 |
| Soporte + mantenimiento correctivo | 12 000 | 288 000 |
| Mantenimiento evolutivo | 8 000 | 192 000 |
| Dominio + certificados SSL | 300 | 7 200 |
| Mensajería SMS/WhatsApp (Twilio) | 4 000 | 96 000 |
| Email transaccional (Mailtrap/SES) | 600 | 14 400 |
| **Subtotal operación** | | **909 600** |
| Utilidad + impuestos (≈21%) | | 191 016 |
| **TOTAL Operación (2 años)** | | **≈ 1 100 616 Bs** |

**TOTAL PROYECTO (MVP + 2 años):** ≈ **1 808 004 Bs**

---

## 3. Simulación de Subasta — 4 Propuestas Económicas

Bajo DS 181 (modalidad de propuestas con evaluación técnica + económica), se presentan
4 ofertas. Evaluación: 70% técnica / 30% económica. Gana el mayor puntaje ponderado.

| Equipo | Precio total Bs | Plazo MVP | Punt. técnico (0-100) | Punt. económico* | Total ponderado |
|--------|---------------:|----------:|---------------------:|-----------------:|----------------:|
| **A (nuestra)** | 1 808 004 | 3 meses | 92 | 96.1 | **93.2** |
| B | 1 950 000 | 3 meses | 88 | 89.1 | 88.3 |
| C | 1 737 000 | 4 meses | 80 | 100.0 | 86.0 |
| D | 2 100 000 | 3 meses | 90 | 82.7 | 87.8 |

\* Punt. económico = (precio_mínimo / precio_oferta) × 100.

**Adjudicación:** Equipo A (mayor puntaje ponderado 93.2), por equilibrio precio/calidad
y cumplimiento de plazo.

### Derecho a apelación (DS 181)
Los equipos no adjudicados (B, C, D) pueden presentar recurso administrativo dentro del
plazo legal, demostrando: (a) error en la evaluación técnica, (b) mejor relación
costo-beneficio, o (c) incumplimiento de criterios por el adjudicado. La entidad
convocante resuelve la impugnación antes de la firma del contrato.

---

## 4. Criterios de Sostenibilidad
- Arquitectura de microservicios contenedorizada → portabilidad y bajo lock-in.
- Cassandra open-source (sin licencias) → reduce TCO.
- Escalabilidad horizontal: agregar nodos sin rediseño.
- Transferencia de conocimiento incluida → autonomía operativa de SEMAPA.
