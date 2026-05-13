# SEMAPA — Mobile App (React Native + Expo)

App móvil para lectura manual de medidores con geolocalización.

## Funcionalidades

- Login (mismo backend, mismo JWT)
- Geolocalización del dispositivo
- Lista de los 5 medidores más cercanos
- Formulario de lectura manual + foto opcional
- Historial de lecturas

## Stack

- React Native + Expo SDK 50
- expo-location, expo-camera, expo-secure-store
- react-native-maps
- React Navigation v6
- Axios + Zustand

## Desarrollo

```bash
npm install
npm start
```

Escanea el QR con Expo Go (iOS o Android) o abre en emulador.

## Variables de entorno

`EXPO_PUBLIC_API_URL=http://10.0.2.2/api/v1` (emulador Android)  
`EXPO_PUBLIC_API_URL=http://localhost/api/v1` (iOS simulator)

Para dispositivo físico usa la IP de tu máquina en la red local.

## Build APK (Android)

```bash
npm install -g eas-cli
eas build --platform android --profile preview
```

## Pantallas

- `Login`
- `Home` (mapa + medidores cercanos)
- `LecturaManual` (formulario)
- `Historial`

## Medidores del campus

Se poblan 5 medidores en el campus Univalle Cochabamba (≈ -17.39, -66.15).
