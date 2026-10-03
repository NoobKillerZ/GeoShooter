# -*- coding: utf-8 -*-
"""
efectos.py
===========
Efectos visuales del shooter: particulas, ondas expansivas, textos
flotantes, destello de disparo, chispas de impacto, explosiones y aviso
de dano. Todo se dibuja en coordenadas de mundo con desplazamiento de
camara.
"""

import math
import random

import pygame

# Color de fondo de la arena: sirve para desvanecer los anillos.
COL_FONDO = (14, 14, 20)


def _teñir(color, factor):
    """Escala un color hacia el fondo (factor 0 = fondo, 1 = color pleno)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(
        int(COL_FONDO[i] + (color[i] - COL_FONDO[i]) * factor) for i in range(3)
    )


# El tinte se pide miles de veces por frame (una particula por chispa) y el
# resultado solo depende de (color, factor). Con el factor cuantizado a 1/32 los
# colores posibles se reducen a un puñado y la cache acierta casi siempre.
_CACHE_TINTE = {}
_TINTE_PASOS = 32


def _teñir_cache(color, factor):
    """Como _teñir, pero recuerda el resultado.

    Sin esto, dibujar 200 particulas hacia 3 canales y 3 generadores era de los
    costes medidos del frame. Cuantizar el factor da un tope de 32 tintes por
    color base, que es lo que hace que la cache sirva de algo.
    """
    q = int(max(0.0, min(1.0, factor)) * _TINTE_PASOS)
    clave = (color, q)
    tinte = _CACHE_TINTE.get(clave)
    if tinte is None:
        tinte = _teñir(color, q / _TINTE_PASOS)
        if len(_CACHE_TINTE) > 4096:
            _CACHE_TINTE.clear()
        _CACHE_TINTE[clave] = tinte
    return tinte


# ------------------------------------------------------------------ fogonazo
# El fogonazo de antes eran 7 particulas sueltas en un circulo, mas o menos
# iguales entre si. Eso no lee como un disparo: una explosion de chispas
# redondas en todas direcciones es otra cosa. Lo que se quiere es un cono que
# nace en la boca del arma y se abre hacia atras, con lo mas brillante pegado
# al canon.
#
# Se dibuja como un sprite con la forma ya resuelta, por las mismas razones que
# la estela de las balas: rotar con el centro como pivote ampliaba la caja a un
# cuadrado y ademas movia la punta del punto de anclaje.
#
# El angulo va cuantizado a 6 grados. Con el cono pegado al cano, 3 grados de
# error se notan: la punta se separa de la boca del arma.
_FOG_CACHE = {}
_FOG_ANGULO = 6
_FOG_MAX = 300


def cono_fogonazo(largo, ancho, angulo, color=(255, 240, 170)):
    """Sprite del cono de fogonazo, ya teñido y con el angulo cuantizado.

    x = 0 es la punta, pegada a la boca del canon: estrecha y muy brillante.
    x = largo-1 es la boca abierta, hacia atras, ancha y apagada.
    """
    a = int(round(angulo / _FOG_ANGULO)) * _FOG_ANGULO
    clave = (largo, ancho, color, a)
    img = _FOG_CACHE.get(clave)
    if img is not None:
        return img

    img = pygame.Surface((largo, ancho), pygame.SRCALPHA)
    medio = (ancho - 1) / 2.0
    for x in range(largo):
        t = x / float(largo - 1)
        brillo = (1.0 - t) ** 1.4
        semiancho = medio * (1.0 - 0.78 * t)
        for y in range(ancho):
            # De 1 en el eje a 0 en el borde: el perfil transversal del cono.
            f = max(0.0, 1.0 - abs(y - medio) / max(0.5, semiancho))
            v = brillo * f
            if v > 0.01:
                img.set_at((x, y), (min(255, int(255 * v)),
                                    min(255, int(240 * v)),
                                    min(255, int(170 * v)), 255))

    # El color llega despues, para no repetir el perfil por cada variante. Se
    # reescriben los pixeles ya encendidos; los apagados se quedan fuera.
    if color != (255, 240, 170):
        rr = color[0] / 255.0
        gg = color[1] / 255.0
        bb = color[2] / 255.0
        for x in range(largo):
            for y in range(ancho):
                r, g, b, _a = img.get_at((x, y))
                if r:
                    img.set_at((x, y), (min(255, int(r * rr)),
                                        min(255, int(g * gg)),
                                        min(255, int(b * bb)), 255))

    if len(_FOG_CACHE) > _FOG_MAX:
        _FOG_CACHE.clear()
    _FOG_CACHE[clave] = img
    return img


class Particula:
    """ chispa con rozamiento."""

    def __init__(self, x, y, color, velocidad_px=2.0, vida_frames=25, radio=3, rozamiento=0.92):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        self.vida = vida_frames
        self.vida_max = vida_frames
        self.radio = radio
        self.rozamiento = rozamiento

        angulo = random.uniform(0, 2 * math.pi)
        rapidez = random.uniform(0.3, 1.0) * velocidad_px
        self.vx = math.cos(angulo) * rapidez
        self.vy = math.sin(angulo) * rapidez
        self.vivo = True

    def actualizar(self):
        if not self.vivo:
            return
        self.x += self.vx
        self.y += self.vy
        self.vx *= self.rozamiento
        self.vy *= self.rozamiento
        self.vida -= 1
        if self.vida <= 0:
            self.vivo = False

    def dibujar(self, pantalla, cam_x=0, cam_y=0):
        if not self.vivo:
            return
        proporcion = self.vida / self.vida_max
        radio_actual = max(1, int(self.radio * proporcion) + 1)
        color = _teñir_cache(self.color, proporcion)
        pygame.draw.circle(
            pantalla, color, (int(self.x - cam_x), int(self.y - cam_y)), radio_actual
        )


class Anillo:
    """Onda expansiva (explosiones, recogidas, impactos)."""

    def __init__(self, x, y, color, radio_final, vida=18, grosor=3):
        self.x = x
        self.y = y
        self.color = color
        self.radio_final = radio_final
        self.vida = vida
        self.vida_max = vida
        self.grosor = grosor
        self.vivo = True

    def actualizar(self):
        if not self.vivo:
            return
        self.vida -= 1
        if self.vida <= 0:
            self.vivo = False

    def dibujar(self, pantalla, cam_x=0, cam_y=0):
        if not self.vivo:
            return
        t = 1 - self.vida / self.vida_max
        radio = int(self.radio_final * t) + 2
        if radio < 2:
            return
        grosor = max(1, int(self.grosor * (1 - t)) + 1)
        pygame.draw.circle(
            pantalla,
            _teñir_cache(self.color, 1 - t),
            (int(self.x - cam_x), int(self.y - cam_y)),
            radio,
            grosor,
        )


class Texto:
    """Texto que sube y se desvanece (puntos, avisos)."""

    def __init__(self, x, y, texto, color, fuente, vida=48, vy=-1.4):
        self.x = x
        self.y = y
        self.texto = texto
        self.color = color
        self.fuente = fuente
        self.vida = vida
        self.vida_max = vida
        self.vy = vy
        self.vivo = True

    def actualizar(self):
        if not self.vivo:
            return
        self.y += self.vy
        self.vida -= 1
        if self.vida <= 0:
            self.vivo = False

    def dibujar(self, pantalla, cam_x=0, cam_y=0):
        if not self.vivo:
            return
        t = self.vida / self.vida_max
        if t < 0.35:
            # Parpadeo al desaparecer
            if (self.vida // 3) % 2 == 0:
                return
        imagen = self.fuente.render(self.texto, True, _teñir(self.color, min(1.0, t * 1.6)))
        pantalla.blit(imagen, (int(self.x - cam_x), int(self.y - cam_y)))


class GestorParticulas:
    """Coleccion de efectos; se actualizan y dibujan en bloque."""

    def __init__(self, max_particulas=300):
        self.max_particulas = max_particulas
        self.particulas = []
        self.anillos = []
        self.textos = []
        self._fuente_cache = {}
        # Marcas en el suelo. Es None por defecto para que los tests y el resto
        # de codigo que usa GestorParticulas suelto no dependan de el; el juego
        # se lo cuelga en Juego.__init__ y a partir de ahi todo impacto y toda
        # explosion dejan rastro.
        self.marcas = None

    def marcas_(self, gestor):
        """Conecta el gestor de marcas y lo devuelve, para encadenar."""
        self.marcas = gestor
        return gestor

    # ------------------------------------------------------------- internos
    def _fuente(self, tamano):
        fuente = self._fuente_cache.get(tamano)
        if fuente is None:
            fuente = pygame.font.SysFont("consolas", tamano, bold=True)
            self._fuente_cache[tamano] = fuente
        return fuente

    def agregar(self, x, y, color, cantidad=10, velocidad_px=2.0, vida_frames=25,
                radio=3, rozamiento=0.92):
        for _ in range(cantidad):
            if len(self.particulas) >= self.max_particulas:
                self.particulas.pop(0)
            self.particulas.append(
                Particula(
                    x, y, color,
                    velocidad_px=velocidad_px,
                    vida_frames=vida_frames,
                    radio=radio,
                    rozamiento=rozamiento,
                )
            )

    def anillo(self, x, y, color, radio_final, vida=18, grosor=3):
        self.anillos.append(Anillo(x, y, color, radio_final, vida, grosor))

    def texto(self, x, y, texto, color, tamano=18, vida=48, vy=-1.4):
        self.textos.append(Texto(x, y, texto, color, self._fuente(tamano), vida, vy))

    def texto_fuente(self, x, y, texto, fuente, color, vida=48, vy=-1.4):
        """Texto flotante con una fuente ya creada (evita buscarla por tamano)."""
        self.textos.append(Texto(x, y, texto, color, fuente, vida, vy))

    def dibujar_fogonazo(self, pantalla, x, y, angulo, largo=26, ancho=16,
                         color=(255, 240, 170)):
        """Fogonazo en cono pegado a la boca del canon.

        Se dibuja aparte de las particulas porque es una forma orientada, no
        un grupo de chispas: sale del cano y se ensancha hacia atras, con la
        parte mas brillante pegada al arma. Va con BLEND_RGB_ADD para que sume
        luz en vez de tapar el fondo.

        La punta del sprite va en su centro, y el sprite se dibuja desplazado
        media caja hacia delante para que la punta caiga en la boca del canon.
        El mismo truco que usan las estelas de bala, por el mismo motivo:
        rotar con el centro como pivote moveria la punta del punto de anclaje.
        """
        img = cono_fogonazo(largo, ancho, math.degrees(angulo), color)
        ux, uy = math.cos(angulo), math.sin(angulo)
        dx = int(x + ux * img.get_width() * 0.5 - img.get_width() * 0.5)
        dy = int(y + uy * img.get_width() * 0.5 - img.get_height() * 0.5)
        pantalla.blit(img, (dx, dy), special_flags=pygame.BLEND_RGB_ADD)

    # ------------------------------------------------------------- efectos
    def destello_disparo(self, x, y, direccion):
        """Fogonazo: acepta nombre de direccion o angulo en radianes."""
        if isinstance(direccion, str):
            dx, dy = {
                "arriba": (0, -1),
                "abajo": (0, 1),
                "izquierda": (-1, 0),
                "derecha": (1, 0),
            }.get(direccion, (0, 1))
        else:
            dx, dy = math.cos(float(direccion)), math.sin(float(direccion))
        # Fogonazo en la boca del canon
        self.agregar(x + dx * 6, y + dy * 6, (255, 240, 170),
                     cantidad=5, velocidad_px=1.6, vida_frames=8, radio=3)
        # Humo que se queda atras
        self.agregar(x - dx * 8, y - dy * 8, (150, 150, 165),
                     cantidad=2, velocidad_px=0.5, vida_frames=16, radio=4, rozamiento=0.88)

    def impacto(self, x, y, color=(255, 205, 120)):
        self.agregar(x, y, color, cantidad=6, velocidad_px=2.0, vida_frames=14, radio=2)
        self.agregar(x, y, (255, 255, 255), cantidad=2, velocidad_px=1.2, vida_frames=7, radio=2)
        # El agujero se queda: las particulas se van en 14 frames, esto no.
        if self.marcas is not None:
            self.marcas.impacto(x, y, color)

    def explosion(self, x, y, escala=1.0):
        self.agregar(x, y, (255, 130, 60), cantidad=16, velocidad_px=2.6,
                     vida_frames=28, radio=4)
        self.agregar(x, y, (255, 225, 140), cantidad=10, velocidad_px=1.8,
                     vida_frames=20, radio=3)
        self.agregar(x, y, (90, 90, 105), cantidad=6, velocidad_px=0.9,
                     vida_frames=34, radio=5, rozamiento=0.9)
        self.anillo(x, y, (255, 190, 110), int(34 * escala), vida=16, grosor=3)
        self.anillo(x, y, (255, 120, 70), int(20 * escala), vida=11, grosor=2)
        if self.marcas is not None:
            self.marcas.quemadura(x, y, escala)

    def destello_powerup(self, x, y, color):
        self.agregar(x, y, color, cantidad=14, velocidad_px=1.8, vida_frames=22, radio=3)
        self.anillo(x, y, color, 30, vida=16, grosor=2)

    def destello_dano(self, x, y):
        self.agregar(x, y, (235, 70, 70), cantidad=16, velocidad_px=2.2,
                     vida_frames=24, radio=3)
        self.agregar(x, y, (255, 255, 255), cantidad=6, velocidad_px=1.5,
                     vida_frames=14, radio=2)
        self.anillo(x, y, (255, 90, 80), 34, vida=14, grosor=3)

    def escudo_roto(self, x, y):
        self.anillo(x, y, (150, 225, 255), 42, vida=18, grosor=3)
        self.agregar(x, y, (170, 230, 255), cantidad=12, velocidad_px=2.4,
                     vida_frames=20, radio=3)

    def dash(self, x, y, direccion):
        self.agregar(x, y, (120, 190, 255), cantidad=10, velocidad_px=1.4,
                     vida_frames=16, radio=3)

    # ------------------------------------------------------------- ciclo
    def actualizar(self):
        for p in self.particulas:
            p.actualizar()
        self.particulas = [p for p in self.particulas if p.vivo]
        for a in self.anillos:
            a.actualizar()
        self.anillos = [a for a in self.anillos if a.vivo]
        for t in self.textos:
            t.actualizar()
        self.textos = [t for t in self.textos if t.vivo]

    def dibujar(self, pantalla, cam_x=0, cam_y=0):
        for a in self.anillos:
            a.dibujar(pantalla, cam_x, cam_y)
        for p in self.particulas:
            p.dibujar(pantalla, cam_x, cam_y)
        for t in self.textos:
            t.dibujar(pantalla, cam_x, cam_y)

    def vaciar(self):
        self.particulas = []
        self.anillos = []
        self.textos = []
