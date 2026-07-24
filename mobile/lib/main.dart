import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';
import 'screens/listado_screen.dart';
import 'screens/login_screen.dart';

void main() {
  runApp(const InventarioApp());
}

class InventarioApp extends StatelessWidget {
  const InventarioApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppState(),
      child: MaterialApp(
        title: 'Inventario Colsubsidio',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          // Tokens Colsubsidio: azul de marca (estructura/encabezados).
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF0067B1),
            primary: const Color(0xFF0067B1),
          ),
          scaffoldBackgroundColor: const Color(0xFFF8F9FA),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF0067B1),
            foregroundColor: Colors.white,
          ),
          // Tipografía grande y legible para uso de campo.
          textTheme: const TextTheme(
            bodyLarge: TextStyle(fontSize: 18),
            bodyMedium: TextStyle(fontSize: 16),
          ),
        ),
        home: const RootScreen(),
      ),
    );
  }
}

class RootScreen extends StatelessWidget {
  const RootScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (s.inicializando) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return s.autenticado ? const ListadoScreen() : const LoginScreen();
  }
}
