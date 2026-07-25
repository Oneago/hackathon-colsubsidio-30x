import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

/// Pantalla de escaneo. Oscurece la cámara fuera de una ventana central y
/// limita la detección a esa ventana (`scanWindow`), para reducir el ruido
/// visual y de reconocimiento como en los escáneres comerciales.
class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> with SingleTickerProviderStateMixin {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  bool _procesado = false;

  late final AnimationController _laser = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _laser.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_procesado) return;
    final codigo = capture.barcodes.isNotEmpty ? capture.barcodes.first.rawValue : null;
    if (codigo == null || codigo.isEmpty) return;
    _procesado = true;
    Navigator.of(context).pop(codigo);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Escanear código'),
        actions: [
          IconButton(
            tooltip: 'Linterna',
            icon: const Icon(Icons.flashlight_on),
            onPressed: () => _controller.toggleTorch(),
          ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          final w = size.width * 0.78;
          final h = w * 0.62;
          final rect = Rect.fromCenter(center: size.center(Offset.zero), width: w, height: h);
          return Stack(
            children: [
              MobileScanner(
                controller: _controller,
                onDetect: _onDetect,
                scanWindow: rect, // detección SOLO dentro del recuadro
              ),
              // Oscurecido + marco + láser (todo pintado sobre la cámara).
              CustomPaint(
                size: size,
                painter: _ScannerOverlay(rect: rect, animation: _laser),
              ),
              Positioned(
                left: 0,
                right: 0,
                bottom: 48,
                child: Text(
                  'Apunte al código dentro del recuadro',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.95),
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    shadows: const [Shadow(color: Colors.black, blurRadius: 4)],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ScannerOverlay extends CustomPainter {
  _ScannerOverlay({required this.rect, required this.animation}) : super(repaint: animation);

  final Rect rect;
  final Animation<double> animation;

  static const _brand = Color(0xFF0067B1); // azul Colsubsidio

  @override
  void paint(Canvas canvas, Size size) {
    final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(16));

    // 1) Scrim: oscurece todo MENOS el recuadro (hueco por diferencia de paths).
    final scrim = Path.combine(
      PathOperation.difference,
      Path()..addRect(Offset.zero & size),
      Path()..addRRect(rrect),
    );
    canvas.drawPath(scrim, Paint()..color = Colors.black.withValues(alpha: 0.62));

    // 2) Borde sutil del recuadro.
    canvas.drawRRect(
      rrect,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.85)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );

    // 3) Esquinas tipo escáner.
    final corner = Paint()
      ..color = _brand
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;
    const len = 26.0;
    final l = rect.left, t = rect.top, r = rect.right, b = rect.bottom;
    // Superior izquierda
    canvas.drawLine(Offset(l, t + len), Offset(l, t), corner);
    canvas.drawLine(Offset(l, t), Offset(l + len, t), corner);
    // Superior derecha
    canvas.drawLine(Offset(r - len, t), Offset(r, t), corner);
    canvas.drawLine(Offset(r, t), Offset(r, t + len), corner);
    // Inferior izquierda
    canvas.drawLine(Offset(l, b - len), Offset(l, b), corner);
    canvas.drawLine(Offset(l, b), Offset(l + len, b), corner);
    // Inferior derecha
    canvas.drawLine(Offset(r - len, b), Offset(r, b), corner);
    canvas.drawLine(Offset(r, b), Offset(r, b - len), corner);

    // 4) Línea láser animada (arriba-abajo).
    final y = rect.top + rect.height * animation.value;
    final laser = Paint()
      ..shader = const LinearGradient(
        colors: [Color(0x00FF3B30), Color(0xFFFF3B30), Color(0x00FF3B30)],
      ).createShader(Rect.fromLTWH(rect.left, y - 1, rect.width, 2))
      ..strokeWidth = 2;
    canvas.drawLine(Offset(rect.left + 6, y), Offset(rect.right - 6, y), laser);
  }

  @override
  bool shouldRepaint(covariant _ScannerOverlay old) =>
      old.rect != rect || old.animation != animation;
}
