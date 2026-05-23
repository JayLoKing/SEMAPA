import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";

export default function LoginScreen() {
  const [username, setU] = useState("contabilidad");
  const [password, setP] = useState("conta123");
  const login = useAuthStore((s) => s.login);

  async function submit() {
    try {
      const r = await api.post("/auth/login", { username, password });
      await login(r.data.access_token, r.data.rol, r.data.nombre);
    } catch (e: any) {
      // Distinguir red vs auth: si no hay response, fue error de conexión
      if (e.response) {
        const detail = e.response.data?.detail || `HTTP ${e.response.status}`;
        Alert.alert("Login falló", detail);
      } else {
        Alert.alert(
          "Sin conexión al backend",
          `No se pudo conectar a:\n${api.defaults.baseURL}\n\n` +
          `Verifica:\n` +
          `• PC y celular en la misma WiFi\n` +
          `• EXPO_PUBLIC_API_URL apunta a la IP LAN del PC (no 10.0.2.2 ni localhost)\n` +
          `• Docker corriendo (docker compose ps)\n` +
          `• Error: ${e.message}`
        );
      }
    }
  }

  return (
    <View style={styles.c}>
      <Text style={styles.title}>SEMAPA</Text>
      <Text style={styles.subtitle}>Gestión Inteligente de Agua Potable</Text>
      <TextInput style={styles.in} value={username} onChangeText={setU}
                 placeholder="Usuario" autoCapitalize="none" />
      <TextInput style={styles.in} value={password} onChangeText={setP}
                 placeholder="Contraseña" secureTextEntry />
      <TouchableOpacity style={styles.btn} onPress={submit}>
        <Text style={styles.btnText}>Ingresar</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  c: { flex: 1, padding: 24, justifyContent: "center", backgroundColor: "#1287B1" },
  title: { fontSize: 36, fontWeight: "700", color: "#fff", textAlign: "center" },
  subtitle: { color: "#cfeefb", textAlign: "center", marginBottom: 32 },
  in: { backgroundColor: "#fff", padding: 12, borderRadius: 8, marginBottom: 12, fontSize: 16 },
  btn: { backgroundColor: "#0A4F66", padding: 14, borderRadius: 8, marginTop: 8 },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700", textAlign: "center" },
});
