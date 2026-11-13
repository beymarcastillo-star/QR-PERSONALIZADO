"""Siluetas (máscaras) para dar forma al QR: gato, perrito, árbol, auto, etc.

Cada silueta se dibuja con Pillow en coordenadas normalizadas (0 a 1). El 255
marca el interior de la figura y el 0 el exterior o los "huecos" (ojos, nariz,
ventanas), que ayudan a reconocer la figura.
"""
import math
from typing import Callable, Dict, Optional

from PIL import Image, ImageDraw

SHAPES: Dict[str, str] = {
    "ninguna": "Sin forma (cuadrado)",
    "gato": "Gato",
    "perro": "Perrito",
    "arbol": "Árbol",
    "auto": "Auto",
    "corazon": "Corazón",
    "estrella": "Estrella",
    "circulo": "Círculo",
}

_SUPERMUESTREO = 4


def _pts(puntos, s):
    return [(x * s, y * s) for x, y in puntos]


def _elipse(d, s, x0, y0, x1, y1, valor=255):
    d.ellipse([x0 * s, y0 * s, x1 * s, y1 * s], fill=valor)


def _gato(d, s):
    _elipse(d, s, 0.10, 0.30, 0.90, 0.95)
    d.polygon(_pts([(0.11, 0.62), (0.12, 0.05), (0.47, 0.36)], s), fill=255)
    d.polygon(_pts([(0.89, 0.62), (0.88, 0.05), (0.53, 0.36)], s), fill=255)
    for cx in (0.33, 0.67):                                   # ojos
        _elipse(d, s, cx - 0.075, 0.52, cx + 0.075, 0.68, 0)
    d.polygon(_pts([(0.445, 0.74), (0.555, 0.74), (0.5, 0.81)], s), fill=0)   # nariz


def _perro(d, s):
    _elipse(d, s, 0.03, 0.16, 0.33, 0.78)                     # orejas caídas
    _elipse(d, s, 0.67, 0.16, 0.97, 0.78)
    _elipse(d, s, 0.22, 0.18, 0.78, 0.94)                     # cabeza
    d.arc([0.22 * s, 0.18 * s, 0.78 * s, 0.94 * s], 100, 260, fill=0, width=int(0.022 * s))
    d.arc([0.22 * s, 0.18 * s, 0.78 * s, 0.94 * s], -80, 80, fill=0, width=int(0.022 * s))
    for cx in (0.40, 0.60):                                   # ojos
        _elipse(d, s, cx - 0.05, 0.44, cx + 0.05, 0.54, 0)
    _elipse(d, s, 0.42, 0.66, 0.58, 0.78, 0)                  # nariz grande


def _arbol(d, s):
    d.polygon(_pts([(0.5, 0.03), (0.78, 0.36), (0.22, 0.36)], s), fill=255)
    d.polygon(_pts([(0.5, 0.20), (0.86, 0.62), (0.14, 0.62)], s), fill=255)
    d.polygon(_pts([(0.5, 0.40), (0.95, 0.87), (0.05, 0.87)], s), fill=255)
    d.rectangle([0.42 * s, 0.84 * s, 0.58 * s, 0.99 * s], fill=255)


def _auto(d, s):
    d.rounded_rectangle([0.03 * s, 0.48 * s, 0.97 * s, 0.78 * s], radius=0.07 * s, fill=255)
    d.polygon(_pts([(0.20, 0.50), (0.32, 0.22), (0.68, 0.22), (0.82, 0.50)], s), fill=255)
    d.polygon(_pts([(0.29, 0.46), (0.36, 0.28), (0.485, 0.28), (0.485, 0.46)], s), fill=0)   # ventanas
    d.polygon(_pts([(0.515, 0.28), (0.64, 0.28), (0.73, 0.46), (0.515, 0.46)], s), fill=0)
    for cx in (0.27, 0.73):                                   # ruedas
        _elipse(d, s, cx - 0.13, 0.66, cx + 0.13, 0.92)
        _elipse(d, s, cx - 0.045, 0.745, cx + 0.045, 0.835, 0)


def _corazon(d, s):
    _elipse(d, s, 0.05, 0.12, 0.52, 0.60)
    _elipse(d, s, 0.48, 0.12, 0.95, 0.60)
    d.polygon(_pts([(0.07, 0.43), (0.93, 0.43), (0.5, 0.96)], s), fill=255)


def _estrella(d, s):
    puntos = []
    for k in range(10):
        radio = 0.50 if k % 2 == 0 else 0.21
        ang = -math.pi / 2 + k * math.pi / 5
        puntos.append((0.5 + radio * math.cos(ang), 0.54 + radio * math.sin(ang)))
    d.polygon(_pts(puntos, s), fill=255)


def _circulo(d, s):
    _elipse(d, s, 0.02, 0.02, 0.98, 0.98)


_DIBUJOS: Dict[str, Callable] = {
    "gato": _gato, "perro": _perro, "arbol": _arbol, "auto": _auto,
    "corazon": _corazon, "estrella": _estrella, "circulo": _circulo,
}


def shape_mask(shape: str, size: int) -> Optional[Image.Image]:
    """Máscara 'L' (size x size) de la silueta, o None si no hay forma."""
    if shape not in _DIBUJOS:
        return None
    s = size * _SUPERMUESTREO
    img = Image.new("L", (s, s), 0)
    _DIBUJOS[shape](ImageDraw.Draw(img), s)
    return img.resize((size, size), Image.LANCZOS)
