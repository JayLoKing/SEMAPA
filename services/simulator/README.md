# SEMAPA - Simulator LoRaWAN

Genera archivos `.txt` simulando lecturas de los 120k medidores IoT.

## Formato del archivo
```
MACMedidor,Fecha,Antena,Lectura,Status
AB:CB:12:13:56,2025-05-12 15:30:00,1,001234.67,1
```

## Configuración
- `SIMULATOR_BURST_SIZE=120`
- `SIMULATOR_ERROR_RATE=0.005`
- `SIMULATOR_DUPLICATE_RATE=0.0007`
