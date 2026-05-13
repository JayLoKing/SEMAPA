import "react-native-gesture-handler";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";

import LoginScreen from "./src/screens/LoginScreen";
import HomeScreen from "./src/screens/HomeScreen";
import LecturaScreen from "./src/screens/LecturaScreen";
import HistorialScreen from "./src/screens/HistorialScreen";
import { useAuthStore } from "./src/store/auth";

const Stack = createNativeStackNavigator();

export default function App() {
  const token = useAuthStore((s) => s.token);

  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: "#1287B1" },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "700" },
        }}
      >
        {!token ? (
          <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        ) : (
          <>
            <Stack.Screen name="Home" component={HomeScreen} options={{ title: "SEMAPA" }} />
            <Stack.Screen name="Lectura" component={LecturaScreen} options={{ title: "Lectura manual" }} />
            <Stack.Screen name="Historial" component={HistorialScreen} options={{ title: "Historial" }} />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
