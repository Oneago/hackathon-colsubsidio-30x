import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../models.dart';
import '../services/formato_cantidad.dart';
import '../services/parseo_cantidad.dart';

enum _Fase { confirmar, dictar, manual }

class ConteoScreen extends StatefulWidget {
  final MovilItem item;
  final String metodo; // 'escaneo' | 'busqueda'

  const ConteoScreen({super.key, required this.item, required this.metodo});

  @override
  State<ConteoScreen> createState() => _ConteoScreenState();
}

class _ConteoScreenState extends State<ConteoScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  final TextEditingController _manualCtrl = TextEditingController();

  _Fase _fase = _Fase.confirmar;
  bool _grabando = false;
  bool _transcribiendo = false;
  bool _guardando = false;
  String _textoReconocido = '';
  double? _cantidad;
  int _intentos = 0;
  Timer? _autoStopTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _reproducirAudio());
  }

  @override
  void dispose() {
    _autoStopTimer?.cancel();
    _recorder.dispose();
    _manualCtrl.dispose();
    super.dispose();
  }

  void _reproducirAudio() {
    final path = widget.item.audioLocalPath;
    if (path != null) {
      context.read<AppState>().audio.reproducirLocal(path);
    }
  }

  // El dictado depende de la API/ElevenLabs: sin red no tiene sentido grabar.
  Future<void> _grabar() async {
    final appState = context.read<AppState>();
    if (!appState.online) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Sin conexión: el dictado por voz no está disponible')),
      );
      return;
    }
    if (!await _recorder.hasPermission()) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Se necesita permiso de micrófono para dictar')),
        );
      }
      return;
    }

    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/dictado_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc), path: path);
    setState(() {
      _grabando = true;
      _textoReconocido = '';
      _cantidad = null;
    });
    // Corte de seguridad: evita grabaciones colgadas y gasto de créditos de más.
    _autoStopTimer = Timer(const Duration(seconds: 15), _detenerYEnviar);
  }

  Future<void> _detenerYEnviar() async {
    _autoStopTimer?.cancel();
    if (!_grabando) return;
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() {
      _grabando = false;
      _transcribiendo = path != null;
    });
    if (path == null) return;

    try {
      final texto = await context.read<AppState>().transcribirDictado(File(path));
      if (!mounted) return;
      final n = parseCantidad(texto);
      setState(() {
        _transcribiendo = false;
        _textoReconocido = texto;
        if (n != null) {
          _cantidad = n;
        } else {
          _cantidad = null;
          _intentos += 1;
          if (_intentos >= 3) _fase = _Fase.manual; // fallback automático
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _transcribiendo = false;
        _cantidad = null;
        _intentos += 1;
        if (_intentos >= 3) _fase = _Fase.manual;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No se pudo transcribir el audio')),
      );
    }
  }

  Future<void> _guardar(num cantidad, String entrada) async {
    setState(() => _guardando = true);
    try {
      await context.read<AppState>().registrarConteo(
            widget.item,
            cantidad: cantidad,
            metodo: widget.metodo,
            entrada: entrada,
          );
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _guardando = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } catch (_) {
      if (mounted) {
        setState(() => _guardando = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No se pudo enviar el conteo')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conteo')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: switch (_fase) {
          _Fase.confirmar => _vistaConfirmar(),
          _Fase.dictar => _vistaDictar(),
          _Fase.manual => _vistaManual(),
        },
      ),
    );
  }

  Widget _vistaConfirmar() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Texto grande y de alto contraste (uso de campo).
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            widget.item.fraseConfirmacion,
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white),
          ),
        ),
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: widget.item.audioLocalPath != null ? _reproducirAudio : null,
          icon: const Icon(Icons.volume_up),
          label: const Text('Reproducir audio', style: TextStyle(fontSize: 18)),
        ),
        const Spacer(),
        SizedBox(
          height: 56,
          child: FilledButton(
            onPressed: () => setState(() => _fase = _Fase.dictar),
            child: const Text('Confirmar para continuar', style: TextStyle(fontSize: 20)),
          ),
        ),
      ],
    );
  }

  Widget _estadoDictado(bool online) {
    final color = online ? Colors.green.shade700 : Colors.orange.shade800;
    final texto = online
        ? 'Reconocimiento de voz por ElevenLabs'
        : 'Sin conexión — dictado no disponible, use el teclado e ingrese el valor con cuidado';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Row(
        children: [
          Icon(online ? Icons.graphic_eq : Icons.wifi_off, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(texto, style: TextStyle(color: color, fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }

  Widget _vistaDictar() {
    final online = context.watch<AppState>().online;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _estadoDictado(online),
        const SizedBox(height: 12),
        Text(widget.item.descripcion, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Text('Diga la cantidad en ${widget.item.unidadTexto}',
            style: const TextStyle(fontSize: 16, color: Colors.black54)),
        const SizedBox(height: 24),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              Text(
                _cantidad != null
                    ? formatearCantidad(_cantidad!)
                    : (_transcribiendo
                        ? 'Transcribiendo…'
                        : (_textoReconocido.isEmpty ? '—' : _textoReconocido)),
                style: const TextStyle(fontSize: 40, fontWeight: FontWeight.bold),
              ),
              if (_intentos > 0 && _cantidad == null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text('No se entendió. Intento $_intentos de 3',
                      style: const TextStyle(color: Colors.redAccent)),
                ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.tonalIcon(
          onPressed: !online || _transcribiendo
              ? null
              : (_grabando ? _detenerYEnviar : _grabar),
          icon: Icon(_grabando ? Icons.stop_circle : Icons.mic_none),
          label: Text(
            _grabando ? 'Detener y enviar' : (_transcribiendo ? 'Transcribiendo…' : 'Dictar cantidad'),
            style: const TextStyle(fontSize: 18),
          ),
        ),
        TextButton(
          onPressed: () => setState(() => _fase = _Fase.manual),
          child: const Text('Ingresar manualmente'),
        ),
        const Spacer(),
        SizedBox(
          height: 56,
          child: FilledButton(
            onPressed: (_cantidad != null && !_guardando) ? () => _guardar(_cantidad!, 'voz') : null,
            child: Text(_guardando ? 'Enviando…' : 'Confirmar cantidad',
                style: const TextStyle(fontSize: 20)),
          ),
        ),
      ],
    );
  }

  Widget _vistaManual() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(widget.item.descripcion, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Text('Ingrese la cantidad en ${widget.item.unidadTexto}',
            style: const TextStyle(fontSize: 16, color: Colors.black54)),
        const SizedBox(height: 24),
        TextField(
          controller: _manualCtrl,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          autofocus: true,
          style: const TextStyle(fontSize: 32),
          textAlign: TextAlign.center,
          decoration: const InputDecoration(border: OutlineInputBorder()),
        ),
        const Spacer(),
        SizedBox(
          height: 56,
          child: FilledButton(
            onPressed: _guardando
                ? null
                : () {
                    final n = double.tryParse(_manualCtrl.text.replaceAll(',', '.'));
                    if (n == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Ingrese un número válido')),
                      );
                      return;
                    }
                    _guardar(n, 'manual');
                  },
            child: Text(_guardando ? 'Enviando…' : 'Guardar conteo',
                style: const TextStyle(fontSize: 20)),
          ),
        ),
      ],
    );
  }
}
