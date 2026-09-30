# -*- coding: utf-8 -*-
"""
iconos.py
=========
Iconos dibujados por codigo para powerups, mejoras, habilidades y armas.

Antes cada icono era un caracter de texto ("+", "O", ">>"), que se lee mal y
no dice nada de lo que es. Aqui cada icono es una forma vectorial con
sombreado, brillo y contorno, reconocible por lo que representa: una cruz para
la vida, un escudo para el escudo, un rayo para la velocidad.

Todo se cachea por (clave, tamano, color): una partida usa los mismos iconos
cientos de veces y no tiene sentido redibujarlos.
"""

import math

import pygame

# Tamano base al que se dibujan y del que se cachean. Se escala al tamano
# pedido con smoothscale, asi que uno solo basta para todos los tamanos.
_LADO = 96

_cache = {}


def _degradado_radial(lado, color, fuerza=0.55):
    """Superficie cuadrada con un degradado radial del color dado.

    El centro sale claro y el borde oscuro: es lo que da volumen redondo a
    cualquier forma plana.
    """
    surf = pygame.Surface((lado, lado), pygame.SRCALPHA)
    cx = cy = lado / 2.0
    r, g, b = color
    for y in range(lado):
        dy = (y - cy) / (lado / 2.0)
        for x in range(lado):
            dx = (x - cx) / (lado / 2.0)
            d = min(1.0, math.hypot(dx, dy))
            f = 1.0 - fuerza * d
            surf.set_at((x, y), (int(r * f), int(g * f), int(b * f), 255))
    return surf


def _circulo(surf, x, y, radio, color, borde=0, color_borde=None):
    pygame.draw.circle(surf, color, (int(x), int(y)), int(radio))
    if borde > 0:
        pygame.draw.circle(surf, color_borde or (0, 0, 0), (int(x), int(y)),
                           int(radio), int(borde))


def _poligono(surf, puntos, color, borde=0, color_borde=None):
    if len(puntos) >= 3:
        pygame.draw.polygon(surf, color, [(int(x), int(y)) for x, y in puntos])
    if borde > 0 and len(puntos) >= 3:
        pygame.draw.polygon(surf, color_borde or (0, 0, 0),
                            [(int(x), int(y)) for x, y in puntos], int(borde))


def _linea(surf, p0, p1, color, grosor):
    pygame.draw.line(surf, color, (int(p0[0]), int(p0[1])),
                     (int(p1[0]), int(p1[1])), int(grosor))


def _brillo(surf, x, y, rx, ry, alpha=70):
    """Elipse blanca semitrasparente: el brillo de arriba que da volumen."""
    capa = pygame.Surface((int(rx * 2), int(ry * 2)), pygame.SRCALPHA)
    pygame.draw.ellipse(capa, (255, 255, 255, alpha), capa.get_rect())
    surf.blit(capa, (int(x - rx), int(y - ry)))


def _base(lado, color):
    """Fondo circular con degradado y aro: comun a todos los iconos."""
    surf = pygame.Surface((lado, lado), pygame.SRCALPHA)
    c = lado / 2.0
    _circulo(surf, c, c, c - 2, (16, 18, 26))
    _circulo(surf, c, c, c - 2, (0, 0, 0), borde=2, color_borde=(0, 0, 0))
    # Degradado del color, recortado al circulo
    deg = _degradado_radial(lado, color, 0.45)
    mascara = pygame.Surface((lado, lado), pygame.SRCALPHA)
    _circulo(mascara, c, c, c - 3, (255, 255, 255))
    deg.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(deg, (0, 0))
    # Aro exterior con el color
    _circulo(surf, c, c, c - 3, (0, 0, 0), borde=2, color_borde=color)
    return surf


# ------------------------------------------------------------------- iconos
def _vida(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    w = lado * 0.16
    # Cruz con brazos redondeados
    pygame.draw.rect(s, (240, 255, 240), (c - w / 2, c - lado * 0.30, w, lado * 0.60),
                     border_radius=int(w * 0.35))
    pygame.draw.rect(s, (240, 255, 240), (c - lado * 0.30, c - w / 2, lado * 0.60, w),
                     border_radius=int(w * 0.35))
    # Sombra de la cruz
    pygame.draw.rect(s, (0, 0, 0, 90), (c - w / 2 + 2, c - lado * 0.30 + 3, w, lado * 0.60),
                     border_radius=int(w * 0.35))
    _brillo(s, c - w * 0.15, c - lado * 0.16, w * 0.28, lado * 0.10, 90)
    return s


def _escudo(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.30
    # Escudo heraldico
    puntos = [(c, c - r), (c + r * 0.85, c - r * 0.55), (c + r * 0.85, c + r * 0.25),
               (c, c + r), (c - r * 0.85, c + r * 0.25), (c - r * 0.85, c - r * 0.55)]
    _poligono(s, puntos, tuple(min(255, int(x * 0.75)) for x in color), borde=2,
              color_borde=(200, 240, 255))
    _poligono(s, [(c, c - r * 0.72), (c + r * 0.60, c - r * 0.38),
                  (c + r * 0.60, c + r * 0.16), (c, c + r * 0.72),
                  (c - r * 0.60, c + r * 0.16), (c - r * 0.60, c - r * 0.38)],
              color, borde=1, color_borde=(255, 255, 255))
    _brillo(s, c - r * 0.2, c - r * 0.35, r * 0.35, r * 0.18, 80)
    return s


def _velocidad(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.30
    # Rayo
    puntos = [(c + r * 0.25, c - r), (c - r * 0.45, c + r * 0.15), (c - r * 0.05, c + r * 0.15),
               (c - r * 0.25, c + r), (c + r * 0.45, c - r * 0.15), (c + r * 0.05, c - r * 0.15)]
    _poligono(s, puntos, (255, 250, 220), borde=2, color_borde=(255, 255, 255))
    _poligono(s, [(c + r * 0.10, c - r * 0.72), (c - r * 0.28, c + r * 0.05),
                  (c - r * 0.02, c + r * 0.05), (c - r * 0.10, c + r * 0.72),
                  (c + r * 0.28, c - r * 0.05), (c + r * 0.02, c - r * 0.05)],
              color)
    return s


def _arma(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Silueta de pistola
    pygame.draw.rect(s, (40, 42, 52), (c - lado * 0.28, c - lado * 0.14, lado * 0.56, lado * 0.13),
                     border_radius=3)
    pygame.draw.rect(s, (60, 62, 74), (c - lado * 0.28, c - lado * 0.14, lado * 0.56, lado * 0.05),
                     border_radius=3)
    pygame.draw.polygon(s, (40, 42, 52), [(c - lado * 0.24, c - lado * 0.01),
                                           (c - lado * 0.05, c - lado * 0.01),
                                           (c - lado * 0.02, c + lado * 0.22),
                                           (c - lado * 0.20, c + lado * 0.22)])
    _circulo(s, c + lado * 0.20, c - lado * 0.075, lado * 0.035, (255, 255, 255))
    return s


def _dano(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Bala con punta
    pygame.draw.polygon(s, (230, 230, 235), [(c, c - r), (c + r * 0.55, c - r * 0.35),
                                             (c + r * 0.55, c + r * 0.55), (c, c + r * 0.55),
                                             (c - r * 0.55, c + r * 0.55), (c - r * 0.55, c - r * 0.35)],
                        borde=2, color_borde=(255, 255, 255))
    _linea(s, (c, c - r * 0.35), (c, c + r * 0.55), (180, 180, 190), 2)
    _brillo(s, c - r * 0.15, c - r * 0.15, r * 0.2, r * 0.12, 90)
    return s


def _cadencia(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.28
    # Gatillo: arco con palanca
    pygame.draw.arc(s, (235, 235, 240), (c - r, c - r, r * 2, r * 2), 0.3, math.pi - 0.3, 6)
    _linea(s, (c, c - r * 0.85), (c, c + r * 0.5), (235, 235, 240), 6)
    _linea(s, (c, c + r * 0.5), (c + r * 0.5, c + r * 0.5), (235, 235, 240), 6)
    _circulo(s, c, c - r * 0.85, 4, (255, 255, 255))
    return s


def _municion(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Cargador con balas
    pygame.draw.rect(s, (50, 52, 62), (c - lado * 0.16, c - lado * 0.10, lado * 0.32, lado * 0.34),
                     border_radius=3)
    for i in range(3):
        bx = c - lado * 0.10 + i * lado * 0.10
        pygame.draw.rect(s, (220, 200, 120), (bx - 3, c - lado * 0.24, 6, lado * 0.16),
                         border_radius=2)
        pygame.draw.polygon(s, (255, 240, 180), [(bx - 3, c - lado * 0.24), (bx, c - lado * 0.30),
                                                 (bx + 3, c - lado * 0.24)])
    return s


def _recarga(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Flecha circular
    pygame.draw.arc(s, (235, 245, 255), (c - r, c - r, r * 2, r * 2), 0.4, math.pi * 1.5, 7)
    # Punta de la flecha
    a = math.pi * 1.5
    px = c + math.cos(a) * r
    py = c + math.sin(a) * r
    tang = a + math.pi / 2
    _poligono(s, [(px, py), (px + math.cos(tang) * r * 0.45, py + math.sin(tang) * r * 0.45),
                  (px + math.cos(tang + 2.5) * r * 0.35, py + math.sin(tang + 2.5) * r * 0.35)],
              (235, 245, 255))
    return s


def _dash(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Doble flecha
    for signo in (-1, 1):
        x0 = c + signo * r * 0.5
        _poligono(s, [(x0, c - r * 0.6), (x0 + signo * r * 0.55, c),
                      (x0, c + r * 0.6), (x0 - signo * r * 0.25, c)], (240, 245, 255),
                  borde=1, color_borde=(255, 255, 255))
    _linea(s, (c - r * 0.7, c), (c + r * 0.7, c), (200, 210, 230), 3)
    return s


def _regen(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.24
    # Engranaje con cruz
    for i in range(8):
        a = i * math.pi / 4
        x = c + math.cos(a) * r * 0.85
        y = c + math.sin(a) * r * 0.85
        _circulo(s, x, y, r * 0.22, (220, 235, 220))
    _circulo(s, c, c, r * 0.62, (200, 220, 200), borde=2, color_borde=(255, 255, 255))
    _circulo(s, c, c, r * 0.30, (180, 210, 180))
    # Cruz central
    w = r * 0.16
    pygame.draw.rect(s, (240, 255, 240), (c - w / 2, c - r * 0.26, w, r * 0.52), border_radius=2)
    pygame.draw.rect(s, (240, 255, 240), (c - r * 0.26, c - w / 2, r * 0.52, w), border_radius=2)
    return s


def _critico(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.28
    # Diana
    for radio, col in ((r, (235, 235, 240)), (r * 0.66, color), (r * 0.33, (235, 235, 240))):
        _circulo(s, c, c, radio, col)
    _circulo(s, c, c, 3, (255, 255, 255))
    # Marcas de mira
    for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        x0 = c + math.cos(a) * r * 1.15
        y0 = c + math.sin(a) * r * 1.15
        x1 = c + math.cos(a) * r * 1.35
        y1 = c + math.sin(a) * r * 1.35
        _linea(s, (x0, y0), (x1, y1), (235, 235, 240), 2)
    return s


def _vampiro(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Gota con colmillos
    pygame.draw.polygon(s, (220, 60, 80), [(c, c - r), (c + r * 0.7, c + r * 0.3),
                                           (c, c + r * 0.7), (c - r * 0.7, c + r * 0.3)],
                        borde=2, color_borde=(255, 150, 160))
    _poligono(s, [(c - r * 0.35, c - r * 0.1), (c - r * 0.1, c - r * 0.1),
                  (c - r * 0.22, c + r * 0.35)], (245, 240, 240))
    _poligono(s, [(c + r * 0.35, c - r * 0.1), (c + r * 0.1, c - r * 0.1),
                  (c + r * 0.22, c + r * 0.35)], (245, 240, 240))
    _brillo(s, c - r * 0.2, c - r * 0.25, r * 0.18, r * 0.28, 80)
    return s


def _magnetico(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Iman de herradura
    pygame.draw.arc(s, (220, 220, 230), (c - r, c - r, r * 2, r * 2), 0, math.pi, 12)
    _linea(s, (c - r, c), (c - r, c + r * 0.7), (220, 220, 230), 12)
    _linea(s, (c + r, c), (c + r, c + r * 0.7), (220, 220, 230), 12)
    # Polos
    pygame.draw.rect(s, (220, 60, 60), (c - r - 6, c + r * 0.7, 12, 14))
    pygame.draw.rect(s, (60, 120, 220), (c + r - 6, c + r * 0.7, 12, 14))
    return s


def _nova(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Onda expansiva
    for i, radio in enumerate((r * 0.35, r * 0.65, r * 0.95)):
        _circulo(s, c, c, radio, (0, 0, 0), borde=3, color_borde=(255, 220, 150))
    _circulo(s, c, c, r * 0.22, (255, 240, 200))
    _brillo(s, c - r * 0.08, c - r * 0.1, r * 0.12, r * 0.08, 100)
    return s


def _tormenta(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Nube con rayo
    _circulo(s, c - r * 0.4, c - r * 0.1, r * 0.45, (200, 210, 230))
    _circulo(s, c + r * 0.35, c - r * 0.15, r * 0.5, (200, 210, 230))
    _circulo(s, c, c + r * 0.1, r * 0.55, (210, 220, 240))
    _poligono(s, [(c + r * 0.1, c + r * 0.2), (c - r * 0.25, c + r * 0.75),
                  (c + r * 0.05, c + r * 0.75), (c - r * 0.1, c + r * 1.1),
                  (c + r * 0.4, c + r * 0.55), (c + r * 0.1, c + r * 0.55)],
              (255, 240, 120), borde=1, color_borde=(255, 255, 255))
    return s


def _segunda(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Reloj con flecha circular
    _circulo(s, c, c, r, (235, 240, 250), borde=2, color_borde=(255, 255, 255))
    _linea(s, (c, c), (c, c - r * 0.6), (235, 240, 250), 4)
    _linea(s, (c, c), (c + r * 0.45, c + r * 0.2), (235, 240, 250), 4)
    _circulo(s, c, c, 3, (235, 240, 250))
    # Flecha circular de "reintentar"
    pygame.draw.arc(s, color, (c - r * 1.25, c - r * 1.25, r * 2.5, r * 2.5), 0.5, math.pi * 1.4, 3)
    return s


def _sobrecarga(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.26
    # Llama energetica
    puntos = [(c, c - r), (c + r * 0.5, c - r * 0.2), (c + r * 0.3, c + r * 0.3),
               (c + r * 0.6, c + r * 0.5), (c + r * 0.2, c + r * 0.9), (c, c + r * 0.5),
               (c - r * 0.2, c + r * 0.9), (c - r * 0.6, c + r * 0.5), (c - r * 0.3, c + r * 0.3),
               (c - r * 0.5, c - r * 0.2)]
    _poligono(s, puntos, (255, 200, 100), borde=2, color_borde=(255, 240, 200))
    _poligono(s, [(c, c - r * 0.5), (c + r * 0.25, c + r * 0.1), (c, c + r * 0.5),
                  (c - r * 0.25, c + r * 0.1)], (255, 240, 180))
    return s


def _pistola(lado, color):
    return _arma(lado, color)


def _escopeta(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Escopeta: canon doble y culata
    pygame.draw.rect(s, (50, 40, 35), (c - lado * 0.30, c - lado * 0.16, lado * 0.60, lado * 0.10),
                     border_radius=3)
    pygame.draw.rect(s, (50, 40, 35), (c - lado * 0.30, c - lado * 0.04, lado * 0.60, lado * 0.10),
                     border_radius=3)
    pygame.draw.polygon(s, (70, 55, 45), [(c - lado * 0.28, c - lado * 0.02),
                                           (c - lado * 0.05, c - lado * 0.02),
                                           (c - lado * 0.02, c + lado * 0.24),
                                           (c - lado * 0.24, c + lado * 0.24)])
    _linea(s, (c - lado * 0.30, c - lado * 0.11), (c + lado * 0.30, c - lado * 0.11),
           (255, 220, 170), 2)
    return s


def _rifle(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Rifle: canon largo con mira y culata
    pygame.draw.rect(s, (45, 47, 58), (c - lado * 0.34, c - lado * 0.08, lado * 0.68, lado * 0.10),
                     border_radius=2)
    pygame.draw.rect(s, (60, 62, 74), (c - lado * 0.34, c - lado * 0.08, lado * 0.68, lado * 0.04),
                     border_radius=2)
    pygame.draw.rect(s, (35, 37, 46), (c + lado * 0.10, c - lado * 0.16, lado * 0.06, lado * 0.10))
    pygame.draw.polygon(s, (55, 48, 40), [(c - lado * 0.32, c - lado * 0.02),
                                           (c - lado * 0.10, c - lado * 0.02),
                                           (c - lado * 0.06, c + lado * 0.20),
                                           (c - lado * 0.28, c + lado * 0.20)])
    _circulo(s, c + lado * 0.20, c - lado * 0.03, 3, (255, 255, 255))
    return s


def _laser(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Rayo laser
    _linea(s, (c - lado * 0.28, c + lado * 0.10), (c + lado * 0.28, c - lado * 0.10),
           (200, 240, 255), 8)
    _linea(s, (c - lado * 0.28, c + lado * 0.10), (c + lado * 0.28, c - lado * 0.10),
           (255, 255, 255), 3)
    _circulo(s, c - lado * 0.28, c + lado * 0.10, 5, (200, 240, 255))
    _circulo(s, c + lado * 0.28, c - lado * 0.10, 5, (200, 240, 255))
    return s


def _sniper(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Sniper: canon muy largo con mira telescopica
    pygame.draw.rect(s, (40, 42, 52), (c - lado * 0.36, c - lado * 0.06, lado * 0.72, lado * 0.08),
                     border_radius=2)
    pygame.draw.rect(s, (55, 57, 68), (c - lado * 0.36, c - lado * 0.06, lado * 0.72, lado * 0.03),
                     border_radius=2)
    pygame.draw.rect(s, (30, 32, 40), (c - lado * 0.02, c - lado * 0.18, lado * 0.16, lado * 0.10),
                     border_radius=3)
    _circulo(s, c + lado * 0.06, c - lado * 0.13, 4, (255, 255, 255))
    pygame.draw.polygon(s, (50, 45, 38), [(c - lado * 0.34, c - lado * 0.02),
                                           (c - lado * 0.12, c - lado * 0.02),
                                           (c - lado * 0.08, c + lado * 0.18),
                                           (c - lado * 0.30, c + lado * 0.18)])
    return s


def _discos(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.24
    # Disco
    _circulo(s, c, c, r, (200, 230, 240), borde=3, color_borde=(255, 255, 255))
    _circulo(s, c, c, r * 0.6, color)
    _circulo(s, c, c, r * 0.25, (255, 255, 255))
    _brillo(s, c - r * 0.25, c - r * 0.3, r * 0.3, r * 0.15, 90)
    return s


def _lanzallamas(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    r = lado * 0.24
    # Llama
    puntos = [(c, c - r), (c + r * 0.55, c - r * 0.1), (c + r * 0.35, c + r * 0.4),
               (c + r * 0.65, c + r * 0.6), (c + r * 0.25, c + r), (c, c + r * 0.5),
               (c - r * 0.25, c + r), (c - r * 0.65, c + r * 0.6), (c - r * 0.35, c + r * 0.4),
               (c - r * 0.55, c - r * 0.1)]
    _poligono(s, puntos, (255, 150, 60), borde=2, color_borde=(255, 220, 150))
    _poligono(s, [(c, c - r * 0.45), (c + r * 0.28, c + r * 0.15), (c, c + r * 0.5),
                  (c - r * 0.28, c + r * 0.15)], (255, 220, 120))
    _poligono(s, [(c, c - r * 0.15), (c + r * 0.14, c + r * 0.25), (c, c + r * 0.45),
                  (c - r * 0.14, c + r * 0.25)], (255, 245, 200))
    return s


def _railgun(lado, color):
    s = _base(lado, color)
    c = lado / 2.0
    # Railgun: dos rieles paralelos con energia entre ellos
    for signo in (-1, 1):
        y = c + signo * lado * 0.08
        pygame.draw.rect(s, (60, 50, 80), (c - lado * 0.30, y - 4, lado * 0.60, 8),
                         border_radius=3)
    for i in range(4):
        x = c - lado * 0.22 + i * lado * 0.15
        _linea(s, (x, c - lado * 0.08), (x, c + lado * 0.08), (200, 150, 255), 3)
    _linea(s, (c - lado * 0.30, c), (c + lado * 0.30, c), (230, 200, 255), 2)
    return s


_DIBUJOS = {
    "vida": _vida, "escudo": _escudo, "velocidad": _velocidad, "arma": _arma,
    "dano": _dano, "cadencia": _cadencia, "municion": _municion,
    "recarga": _recarga, "dash": _dash, "regen": _regen, "critico": _critico,
    "vampiro": _vampiro, "magnetico": _magnetico,
    "nova": _nova, "tormenta": _tormenta, "segunda": _segunda,
    "sobrecarga": _sobrecarga,
    "pistola": _pistola, "escopeta": _escopeta, "rifle": _rifle, "laser": _laser,
    "sniper": _sniper, "discos": _discos, "lanzallamas": _lanzallamas,
    "railgun": _railgun,
}


def obtener(clave, tamano, color):
    """Icono de la clave, en el tamano y color dados. Cacheado."""
    clave_cache = (clave, tamano, color)
    img = _cache.get(clave_cache)
    if img is not None:
        return img
    dibujo = _DIBUJOS.get(clave)
    if dibujo is None:
        # Clave desconocida: un circulo con el color, para que no se rompa nada.
        img = _base(_LADO, color)
    else:
        img = dibujo(_LADO, color)
    if tamano != _LADO:
        img = pygame.transform.smoothscale(img, (tamano, tamano))
    _cache[clave_cache] = img
    return img


def limpiar_cache():
    _cache.clear()
