import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../models.dart';
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
  final SpeechToText _speech = SpeechToText();
  final TextEditingController _manualCtrl = TextEditingController();

  _Fase _fase = _Fase.confirmar;
  bool _speechDisponible = false;
  bool _escuchando = false;
  bool _guardando = false;
  String _textoReconocido = '';
  double? _cantidad;
  int _intentos = 0;

  @override
  void initState() {
    super.initState();
    _initSpeech();
    WidgetsBinding.instance.addPostFrameCallback((_) => _reproducirAudio());
  }

  @override
  void dispose() {
    _speech.cancel();
    _manualCtrl.dispose();
    super.dispose();
  }

  void _reproducirAudio() {
    final path = widget.item.audioLocalPath;
    if (path != null) {
      context.read<AppState>().audio.reproducirLocal(path);
    }
  }

  Future<void> _initSpeech() async {
    await Permission.microphone.request();
    final ok = await _speech.initialize();
    if (mounted) setState(() => _speechDisponible = ok);
  }

  Future<void> _escuchar() async {
    if (!_speechDisponible) {
      setState(() => _fase = _Fase.manual);
      return;
    }
    setState(() {
      _escuchando = true;
      _textoReconocido = '';
      _cantidad = null;
    });
    await _speech.listen(
      onResult: _onResult,
      listenOptions: SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        localeId: 'es_CO', // paquete de idioma es-CO forzado en la tablet
      ),
    );
  }

  void _onResult(SpeechRecognitionResult result) {
    setState(() => _textoReconocido = result.recognizedWords);
    if (!result.finalResult) return;
    final n = parseCantidad(result.recognizedWords);
    setState(() {
      _escuchando = false;
      if (n != null) {
        _cantidad = n;
      } else {
        _cantidad = null;
        _intentos += 1;
        if (_intentos >= 3) _fase = _Fase.manual; // fallback automático
      }
    });
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

  Widget _vistaDictar() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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
                _cantidad != null ? _cantidad!.toString() : (_textoReconocido.isEmpty ? '—' : _textoReconocido),
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
          onPressed: _escuchando ? null : _escuchar,
          icon: Icon(_escuchando ? Icons.mic : Icons.mic_none),
          label: Text(_escuchando ? 'Escuchando…' : 'Dictar cantidad',
              style: const TextStyle(fontSize: 18)),
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
