"""Motor de dibujo del QR personalizado (estilos, siluetas e imagen de referencia).

Regla de oro: el QR debe seguir siendo ESCANEABLE. Por eso:
  - se usa corrección de errores nivel H (tolera hasta ~30 % de daño);
  - los puntos siempre se oscurecen y el fondo siempre se aclara, para que haya
    contraste aunque la imagen de referencia sea oscura o muy colorida;
  - los tres cuadros de las esquinas (los que usa el lector para ubicar el
    código) se dibujan siempre completos y sólidos;
  - la silueta (gato, perrito...) se marca con un fondo tintado y puntos más
    grandes dentro de la figura, sin quitar ningún módulo del código.
"""
import io
from dataclasses import dataclass
from typing import Optional, Tuple

import qrcode
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from qrcode.constants import ERROR_CORRECT_H

from app.services.qr_shapes import SHAPES, shape_mask  # noqa: F401  (SHAPES se reexporta)

STYLES = {
    "cuadrado": "Cuadrados clásicos",
    "puntos": "Puntos redondos",
    "redondeado": "Cuadrados redondeados",
    "diamantes": "Diamantes",
}

PX = 16                  # píxeles por módulo en la imagen final
SS = 2                   # supermuestreo para suavizar bordes
QUIET = 4                # zona de silencio (en módulos)
ESCALA_FUERA = 0.76      # tamaño de los puntos fuera de la silueta
ESCALA_FUERA_PUNTOS = 0.88   # los puntos redondos necesitan ser más grandes para leerse
LUM_MAX_PUNTO = 85       # luminancia máxima de un punto de la imagen (0-255)
LUM_MAX_COLOR = 95       # luminancia máxima del color elegido
LUM_MIN_FONDO = 200      # luminancia mínima del fondo
TINTE_SILUETA = 0.72     # cuánto se aclara el color dentro de la silueta (0 = color puro)
CLARO_FUERA = 0.0        # los puntos fuera de la silueta se aclaran este porcentaje
CONTORNO_SILUETA = False # dibuja un contorno fino de la figura
MAX_DATOS = 800          # caracteres máximos del contenido

COLOR_POR_DEFECTO = "#111827"


@dataclass
class QROptions:
    style: str = "cuadrado"
    shape: str = "ninguna"
    color: str = COLOR_POR_DEFECTO
    ref_image: Optional[bytes] = None
    image_strength: float = 0.55     # cuánto se ve la imagen de fondo (0.15 a 0.9)


# --------------------------------------------------------------- utilidades
def _hex_a_rgb(valor: str) -> Tuple[int, int, int]:
    v = (valor or "").strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (17, 24, 39)


def _luminancia(rgb) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _oscurecer(rgb, max_lum: float):
    lum = _luminancia(rgb)
    if lum <= max_lum:
        return tuple(int(c) for c in rgb)
    f = max_lum / lum
    return tuple(int(c * f) for c in rgb)


def _hacia_blanco(rgb, t: float):
    return tuple(int(c * (1 - t) + 255 * t) for c in rgb)


def cargar_referencia(datos: bytes) -> Image.Image:
    """Abre la imagen de referencia (JPG, PNG, WEBP...) y la deja cuadrada y en RGB."""
    try:
        img = Image.open(io.BytesIO(datos))
        img.load()
    except Exception as exc:
        raise ValueError("El archivo no es una imagen válida.") from exc
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[3])
        img = fondo
    else:
        img = img.convert("RGB")
    return ImageOps.fit(img, (800, 800), Image.LANCZOS)


def _aclarar(img: Image.Image, minimo: int = LUM_MIN_FONDO) -> Image.Image:
    """Mezcla con blanco cada píxel que sea más oscuro que `minimo` (garantiza contraste)."""
    gris = img.convert("L")
    tabla = [0 if v >= minimo else int(255 * (minimo - v) / (255 - v)) for v in range(256)]
    return Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, gris.point(tabla))


def _fondo_area(area: int, opts: QROptions, ref: Optional[Image.Image],
                mascara: Optional[Image.Image], color) -> Image.Image:
    blanco = Image.new("RGB", (area, area), (255, 255, 255))
    if ref is not None:
        base = ref.resize((area, area), Image.LANCZOS)
        visible = max(0.15, min(0.9, opts.image_strength))
        dentro = _aclarar(Image.blend(blanco, base, visible))
        fuera = _aclarar(Image.blend(blanco, base, 0.12)) if mascara is not None else dentro
    else:
        if mascara is None:
            return blanco
        dentro = Image.new("RGB", (area, area), _hacia_blanco(color, TINTE_SILUETA))
        fuera = blanco
    if mascara is None:
        return dentro
    fondo = Image.composite(dentro, fuera, mascara)
    if not CONTORNO_SILUETA:
        return fondo
    # contorno fino de la figura (ayuda a reconocer el gato, el árbol, etc.)
    k = max(3, (area // 70) | 1)
    borde = ImageChops.subtract(mascara.filter(ImageFilter.MaxFilter(k)), mascara.filter(ImageFilter.MinFilter(k)))
    fondo.paste(Image.new("RGB", fondo.size, _hacia_blanco(color, 0.30)), mask=borde)
    return fondo


def _en_ojo(r: int, c: int, n: int) -> bool:
    """¿El módulo cae en uno de los tres cuadros de posición (con su separador)?"""
    return (r < 8 and c < 8) or (r < 8 and c >= n - 8) or (r >= n - 8 and c < 8)


def _modulo(d: ImageDraw.ImageDraw, estilo: str, x0: float, y0: float, px: int,
            escala: float, col) -> None:
    t = px * escala * (0.96 if estilo == "puntos" else 1.0)
    off = (px - t) / 2
    a, b = x0 + off, y0 + off
    e, f = a + t, b + t
    if estilo == "puntos":
        d.ellipse([a, b, e, f], fill=col)
    elif estilo == "redondeado":
        d.rounded_rectangle([a, b, e, f], radius=t * 0.32, fill=col)
    elif estilo == "diamantes":
        cx, cy, h = x0 + px / 2, y0 + px / 2, px * escala * 0.60
        d.polygon([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)], fill=col)
    else:
        d.rectangle([a, b, e, f], fill=col)


def _ojo(d: ImageDraw.ImageDraw, estilo: str, x0: float, y0: float, px: int, col) -> None:
    tam = 7 * px
    # Las esquinas se mantienen casi cuadradas: si se redondean mucho, los lectores
    # dejan de reconocerlas (comprobado con OpenCV).
    radio = tam * 0.08 if estilo == "redondeado" else 0
    d.rounded_rectangle([x0, y0, x0 + tam - 1, y0 + tam - 1], radius=radio, outline=col, width=px)
    d.rounded_rectangle([x0 + 2 * px, y0 + 2 * px, x0 + 5 * px - 1, y0 + 5 * px - 1],
                        radius=radio * 0.45, fill=col)


# ------------------------------------------------------------------ principal
def render_qr(data: str, opts: Optional[QROptions] = None) -> Image.Image:
    opts = opts or QROptions()
    if not data or not data.strip():
        raise ValueError("El contenido del QR está vacío.")
    if len(data) > MAX_DATOS:
        raise ValueError(f"El contenido es demasiado largo (máximo {MAX_DATOS} caracteres).")

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=1, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    matriz = qr.get_matrix()
    n = len(matriz)

    px = PX * SS
    q = QUIET * px
    area = n * px
    total = area + 2 * q

    color = _oscurecer(_hex_a_rgb(opts.color), LUM_MAX_COLOR)
    ref = cargar_referencia(opts.ref_image) if opts.ref_image else None
    mascara = shape_mask(opts.shape, area)
    estilo = opts.style if opts.style in STYLES else "cuadrado"

    lienzo = Image.new("RGB", (total, total), (255, 255, 255))
    lienzo.paste(_fondo_area(area, opts, ref, mascara, color), (q, q))
    d = ImageDraw.Draw(lienzo)
    muestras = ref.resize((n, n), Image.BOX) if ref is not None else None
    fuera = ESCALA_FUERA_PUNTOS if estilo == "puntos" else ESCALA_FUERA

    for r in range(n):
        for c in range(n):
            if not matriz[r][c] or _en_ojo(r, c, n):
                continue
            dentro = True
            if mascara is not None:
                dentro = mascara.getpixel((c * px + px // 2, r * px + px // 2)) > 127
            col = _oscurecer(muestras.getpixel((c, r)), LUM_MAX_PUNTO) if muestras is not None else color
            if not dentro:
                col = _hacia_blanco(col, CLARO_FUERA)
            _modulo(d, estilo, q + c * px, q + r * px, px, 1.0 if dentro else fuera, col)

    for fila, col_ in ((0, 0), (0, n - 7), (n - 7, 0)):
        _ojo(d, estilo, q + col_ * px, q + fila * px, px, color)

    return lienzo.resize((total // SS, total // SS), Image.LANCZOS)


def render_png(data: str, opts: Optional[QROptions] = None) -> bytes:
    buffer = io.BytesIO()
    render_qr(data, opts).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
