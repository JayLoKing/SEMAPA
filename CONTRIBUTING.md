# Contribuir a SEMAPA

¡Gracias por tu interés en contribuir!

## Flujo de trabajo

1. Crea un branch desde `main`: `git checkout -b feat/nombre-feature`
2. Realiza los cambios siguiendo las convenciones del proyecto.
3. Asegúrate de que pasan los tests: `pytest` (backend) y `npm test` (frontend).
4. Haz commit usando [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` nueva funcionalidad
   - `fix:` corrección de bug
   - `docs:` solo documentación
   - `refactor:` refactor sin cambio funcional
   - `test:` añade o corrige tests
   - `chore:` tareas de mantenimiento
5. Abre un Pull Request hacia `main` describiendo el cambio.

## Estilo de código

- **Python**: PEP 8 + black + ruff
- **TypeScript/JS**: ESLint + Prettier
- **CQL**: nombres en `snake_case`, palabras clave en MAYÚSCULAS
- **Commits**: en inglés, imperativo presente

## Tests obligatorios

- Endpoints nuevos deben tener al menos un test pytest.
- Componentes React críticos deben tener test con Vitest/Testing Library.
- Cambios en cálculo de tarifas → test unitario por cada categoría afectada.

## Variables de entorno

- NUNCA committear `.env` con valores reales.
- Si añades una variable nueva, agrégala también a `.env.example`.

## Reportar bugs

Abre un issue con:
- Descripción del bug
- Pasos para reproducir
- Comportamiento esperado vs. observado
- Logs relevantes
- Entorno (SO, versión de Docker)

## Preguntas

Abre una _discussion_ en el repo.
