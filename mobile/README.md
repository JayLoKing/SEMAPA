# SEMAPA Mobile

App React Native (Expo) — captura manual de lecturas con geolocalización.

## Pantallas
- **Login**: contra `POST /api/v1/auth/login`, token en `expo-secure-store`.
- **Home**: permisos de geolocalización, mapa `react-native-maps` con los 5
  medidores del campus Univalle (lat -17.39 / lon -66.15) ordenados por
  distancia haversine al usuario.
- **Lectura**: formulario para enviar `POST /api/v1/lecturas/manual` con la
  MAC del medidor seleccionado + lectura + coordenadas adjuntas.
- **Historial**: pendiente, ver dashboard web.

## Correr en desarrollo

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=http://192.168.1.x/api/v1 npx expo start
# Escanea el QR con Expo Go (Android/iOS).
```

> Android emulator: `EXPO_PUBLIC_API_URL=http://10.0.2.2/api/v1`.
> iOS simulator: `EXPO_PUBLIC_API_URL=http://localhost/api/v1`.

## Build APK

```bash
npm i -g eas-cli
eas login
eas build -p android --profile preview      # produce .apk
```

## Permisos

- `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` (geolocalización)
- `CAMERA` (opcional, foto de la lectura — pendiente)

## Medidores del campus

Coordenadas embebidas en `src/screens/HomeScreen.tsx`:

| ID            | MAC               | Lat/Lon              | Lugar       |
|---------------|-------------------|----------------------|-------------|
| univalle-01   | AA:BB:CC:01:01    | -17.39068, -66.15240 | Pabellón A  |
| univalle-02   | AA:BB:CC:01:02    | -17.39120, -66.15180 | Pabellón B  |
| univalle-03   | AA:BB:CC:01:03    | -17.39010, -66.15300 | Biblioteca  |
| univalle-04   | AA:BB:CC:01:04    | -17.38960, -66.15150 | Comedor     |
| univalle-05   | AA:BB:CC:01:05    | -17.39180, -66.15280 | Auditorio   |

Para que aparezcan en Cassandra, ejecutar este insert post-seed:

```cql
INSERT INTO semapa.medidores
  (medidor_id, mac, numero_serie, numero_contrato, modelo_id, categoria_tarifa,
   gateway_id, distrito_id, zona_id, latitud, longitud, fecha_instalacion, estado)
VALUES (uuid(), 'AA:BB:CC:01:01', 'SN=UVL-00001', 999000001, 1, 'CE', 1, 1, 24,
        -17.39068, -66.15240, '2024-01-01', 'ACTIVO');
-- repetir para 02..05
```
