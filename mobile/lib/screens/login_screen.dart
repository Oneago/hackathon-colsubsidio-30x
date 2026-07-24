import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _cedula = TextEditingController();
  final _password = TextEditingController();

  @override
  void dispose() {
    _cedula.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _ingresar() async {
    final ok = await context.read<AppState>().login(_cedula.text.trim(), _password.text);
    if (!ok && mounted) {
      final msg = context.read<AppState>().error ?? 'No se pudo iniciar sesión';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cargando = context.select<AppState, bool>((s) => s.cargando);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Fondo azul de marca: el logo (isotipo amarillo + texto blanco)
                // no se ve sobre fondo claro. Blanco/amarillo sobre azul cumple WCAG.
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0067B1),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Image.asset('assets/logo.png', height: 72),
                ),
                const SizedBox(height: 16),
                Text('Toma de inventario',
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 4),
                const Text('Ingrese con su cédula y contraseña'),
                const SizedBox(height: 28),
                TextField(
                  controller: _cedula,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Cédula',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Contraseña',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton(
                    // Acento de marca (amarillo Colsubsidio), texto grafito por WCAG.
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFFFD000),
                      foregroundColor: const Color(0xFF343434),
                    ),
                    onPressed: cargando ? null : _ingresar,
                    child: Text(cargando ? 'Ingresando…' : 'Ingresar',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
