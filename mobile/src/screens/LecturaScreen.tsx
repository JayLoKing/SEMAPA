import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ScrollView } from "react-native";
import * as Location from "expo-location";
import { api } from "../api/client";

export default function LecturaScreen({ route, navigation }: any) {
  const medidor = route?.params?.medidor;
  const [lectura, setLectura] = useState("");
  const [busy, setBusy] = useState(false);

  async function enviar() {
    if (!lectura || isNaN(parseInt(lectura))) {
      Alert.alert("Inválido", "Ingrese una lectura numérica");
      return;
    }
    setBusy(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      let lat: number | undefined;
      let lon: number | undefined;
      if (status === "granted") {
        const loc = await Location.getCurrentPositionAsync({});
        lat = loc.coords.latitude;
        lon = loc.coords.longitude;
      }
      await api.post("/lecturas/manual", {
        mac: medidor?.mac,
        lectura_litros: parseInt(lectura, 10),
        lat,
        lon,
      });
      Alert.alert("✅ Registrada", "Lectura guardada en SEMAPA");
      navigation.goBack();
    } catch (e: any) {
      Alert.alert("Error", e.response?.data?.detail || "No se pudo enviar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text style={styles.label}>Medidor:</Text>
      <Text style={styles.value}>{medidor?.label || "—"}</Text>
      <Text style={styles.value}>MAC: {medidor?.mac}</Text>

      <Text style={[styles.label, { marginTop: 24 }]}>Lectura (litros):</Text>
      <TextInput
        style={styles.in}
        keyboardType="number-pad"
        value={lectura}
        onChangeText={setLectura}
        placeholder="Ej: 123456"
      />

      <TouchableOpacity style={styles.btn} disabled={busy} onPress={enviar}>
        <Text style={styles.btnText}>{busy ? "Enviando..." : "Enviar lectura"}</Text>
      </TouchableOpacity>
      <Text style={styles.hint}>La ubicación se adjunta automáticamente si tiene permiso.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: { padding: 24, backgroundColor: "#f8fafc", flexGrow: 1 },
  label: { fontWeight: "600", marginBottom: 4 },
  value: { fontSize: 16 },
  in: { backgroundColor: "#fff", padding: 12, borderRadius: 8, borderColor: "#e2e8f0", borderWidth: 1, fontSize: 18 },
  btn: { backgroundColor: "#1287B1", padding: 14, borderRadius: 8, marginTop: 16 },
  btnText: { color: "#fff", textAlign: "center", fontWeight: "700", fontSize: 16 },
  hint: { color: "#64748b", fontSize: 12, marginTop: 12, textAlign: "center" },
});
