import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import '../config.dart';
import '../models.dart';

/// Descarga y reproduce los audios TTS pre-generados para uso OFFLINE en bodega.
class AudioService {
  final AudioPlayer _player = AudioPlayer();

  Future<Directory> _audioDir() async {
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory('${base.path}/audios');
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    return dir;
  }

  /// Descarga los .mp3 del listado que aún no estén en disco y fija su ruta local.
  Future<void> descargarAudios(List<MovilItem> items) async {
    final dir = await _audioDir();
    for (final item in items) {
      final url = item.audioUrl;
      if (url == null) continue;
      final nombre = url.split('/').last;
      final file = File('${dir.path}/$nombre');
      if (!await file.exists()) {
        try {
          final res = await http.get(Uri.parse('${AppConfig.apiBaseUrl}$url'));
          if (res.statusCode == 200) {
            await file.writeAsBytes(res.bodyBytes);
          }
        } catch (_) {
          // sin conexión: se omite; el ítem podrá contarse sin audio
        }
      }
      if (await file.exists()) {
        item.audioLocalPath = file.path;
      }
    }
  }

  /// Reproduce el audio local pre-generado (no consume la cuota de ElevenLabs).
  Future<void> reproducirLocal(String path) async {
    await _player.stop();
    await _player.play(DeviceFileSource(path));
  }

  Future<void> dispose() async {
    await _player.dispose();
  }
}
