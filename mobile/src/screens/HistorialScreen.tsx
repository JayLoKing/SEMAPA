import { View, Text, StyleSheet, ScrollView } from "react-native";

export default function HistorialScreen() {
  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text style={styles.title}>Historial</Text>
      <Text style={styles.hint}>
        Las lecturas que envíes desde esta app aparecerán en el dashboard web.
        Para listado detallado consulta `/api/v1/lecturas/manual` con tu rol.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: { padding: 24, backgroundColor: "#f8fafc", flexGrow: 1 },
  title: { fontSize: 20, fontWeight: "700", marginBottom: 12 },
  hint: { color: "#475569" },
});
