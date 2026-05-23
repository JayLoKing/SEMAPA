import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ScrollView, Image } from "react-native";
import * as Location from "expo-location";
import * as ImagePicker from "expo-image-picker";
import { api } from "../api/client";

export default function LecturaScreen({ route, navigation }: any) {
  const medidor = route?.params?.medidor;
  const [lectura, setLectura] = useState("");
  const [foto, setFoto] = useState<string | null>(null);
  const [fotoB64, setFotoB64] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function tomarFoto() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permiso requerido", "Habilite la cámara en ajustes");
      return;
    }
    const r = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.5,
      base64: true,
      allowsEditing: false,
    });
    if (!r.canceled && r.assets?.[0]) {
      setFoto(r.assets[0].uri);
      setFotoB64(r.assets[0].base64 ? `data:image/jpeg;base64,${r.assets[0].base64}` : null);
    }
  }

  async function elegirGaleria() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permiso requerido", "Habilite acceso a galería");
      return;
    }
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.5,
      base64: true,
    });
    if (!r.canceled && r.assets?.[0]) {
      setFoto(r.assets[0].uri);
      setFotoB64(r.assets[0].base64 ? `data:image/jpeg;base64,${r.assets[0].base64}` : null);
    }
  }

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
        lectura_actual: parseInt(lectura, 10),
        lat,
        lon,
        foto_url: fotoB64,
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

      <Text style={[styles.label, { marginTop: 24 }]}>Lectura actual (m³):</Text>
      <TextInput
        style={styles.in}
        keyboardType="number-pad"
        value={lectura}
        onChangeText={setLectura}
        placeholder="Ej: 123456"
      />

      <Text style={[styles.label, { marginTop: 16 }]}>Foto del medidor (opcional):</Text>
      <View style={styles.row}>
        <TouchableOpacity style={[styles.btnAlt, { flex: 1, marginRight: 4 }]} onPress={tomarFoto}>
          <Text style={styles.btnAltText}>📷 Cámara</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btnAlt, { flex: 1, marginLeft: 4 }]} onPress={elegirGaleria}>
          <Text style={styles.btnAltText}>🖼️ Galería</Text>
        </TouchableOpacity>
      </View>
      {foto && (
        <View style={styles.preview}>
          <Image source={{ uri: foto }} style={styles.img} resizeMode="contain" />
          <TouchableOpacity onPress={() => { setFoto(null); setFotoB64(null); }}>
            <Text style={styles.link}>Quitar foto</Text>
          </TouchableOpacity>
        </View>
      )}

      <TouchableOpacity style={styles.btn} disabled={busy} onPress={enviar}>
        <Text style={styles.btnText}>{busy ? "Enviando..." : "Enviar lectura"}</Text>
      </TouchableOpacity>
      <Text style={styles.hint}>GPS y foto se adjuntan si se autorizan.</Text>
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
  btnAlt: { backgroundColor: "#fff", padding: 12, borderRadius: 8, borderColor: "#1287B1", borderWidth: 1 },
  btnAltText: { color: "#1287B1", textAlign: "center", fontWeight: "600" },
  row: { flexDirection: "row", marginTop: 8 },
  preview: { marginTop: 12, alignItems: "center" },
  img: { width: 220, height: 220, borderRadius: 8, borderColor: "#e2e8f0", borderWidth: 1 },
  link: { color: "#dc2626", marginTop: 8 },
  hint: { color: "#64748b", fontSize: 12, marginTop: 12, textAlign: "center" },
});
