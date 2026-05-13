# SEMAPA - PDF Service

Genera facturas en PDF en dos formatos:
- **Media carta (A5, 148x210mm)** para entrega digital/física
- **Rollo térmico (80mm)** para kioscos

## Endpoints

- `GET /pdf?numero_contrato=&periodo=&formato=rollo|medicarta`
- `POST /pdf/batch` (genera ZIP)
