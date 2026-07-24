import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../models.dart';
import 'conteo_screen.dart';
import 'scan_screen.dart';

class ListadoScreen extends StatefulWidget {
  const ListadoScreen({super.key});

  @override
  State<ListadoScreen> createState() => _ListadoScreenState();
}

class _ListadoScreenState extends State<ListadoScreen> {
  String _filtro = '';

  Future<void> _abrirConteo(MovilItem item, String metodo) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ConteoScreen(item: item, metodo: metodo)),
    );
    if (mounted) setState(() {}); // refresca marca de "contado"
  }

  Future<void> _escanear() async {
    final codigo = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const ScanScreen()),
    );
    if (codigo == null || !mounted) return;
    final items = context.read<AppState>().listado?.items ?? [];
    final match = items.where((i) => i.codigoBarras == codigo).toList();
    if (match.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ese código no está en tu listado')),
      );
      return;
    }
    await _abrirConteo(match.first, 'escaneo');
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final listado = state.listado;

    return Scaffold(
      appBar: AppBar(
        title: Text(listado?.bodegaNombre ?? 'Mi listado'),
        actions: [
          // Indicador de conectividad.
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Icon(state.online ? Icons.cloud_done : Icons.cloud_off,
                color: state.online ? Colors.white : const Color(0xFFFFD000)),
          ),
          if (state.pendientes > 0)
            IconButton(
              tooltip: 'Sincronizar ${state.pendientes} pendientes',
              onPressed: () => context.read<AppState>().sincronizarManual(),
              icon: Badge(
                label: Text('${state.pendientes}'),
                child: const Icon(Icons.sync),
              ),
            ),
          IconButton(
            onPressed: () => context.read<AppState>().logout(),
            icon: const Icon(Icons.logout),
            tooltip: 'Salir',
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(28),
          child: Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Contados: ${state.contados} / ${state.totalItems}'
              '${state.online ? '' : '  ·  sin conexión'}',
              style: const TextStyle(fontSize: 16),
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        // Acento de marca (amarillo), ícono/texto grafito por contraste (WCAG).
        backgroundColor: const Color(0xFFFFD000),
        foregroundColor: const Color(0xFF343434),
        onPressed: _escanear,
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Escanear'),
      ),
      body: listado == null
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: TextField(
                    decoration: const InputDecoration(
                      prefixIcon: Icon(Icons.search),
                      hintText: 'Buscar ítem…',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (v) => setState(() => _filtro = v.toLowerCase()),
                  ),
                ),
                Expanded(
                  child: ListView(
                    children: listado.items
                        .where((i) =>
                            i.descripcion.toLowerCase().contains(_filtro) ||
                            i.codigoBarras.contains(_filtro))
                        .map((item) => ListTile(
                              title: Text(item.descripcion,
                                  style: const TextStyle(fontSize: 17)),
                              subtitle: Text('${item.codigoBarras} · ${item.unidadTexto}'),
                              trailing: item.contado
                                  ? const Icon(Icons.check_circle, color: Colors.green)
                                  : const Icon(Icons.chevron_right),
                              onTap: () => _abrirConteo(item, 'busqueda'),
                            ))
                        .toList(),
                  ),
                ),
              ],
            ),
    );
  }
}
