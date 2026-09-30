# -*- coding: utf-8 -*-
"""
iluminacion.py
==============
Luz 2D para el shooter cenital.

La escena se pinta tal cual, se calcula una capa de luz y se multiplica
encima: donde no llega luz se apaga, donde llega se ve normal. Sin mallado ni
nada 3D, solo circulos con caida suave.

Piezas:

* ``Luz``      una fuente (posicion, radio, color, intensidad, parpadeo).
* ``Luces``    el gestor: mantiene las luces, calcula la capa y la compone.
* Oclusion     opcional: una luz no ilumina a traves de las paredes, que es
               lo que hace que la sala se lea como una sala y no como un plano.
* Ambiente     un tono base que se aplica antes de multiplicar, para que las
               zonas sin luz no queden en negro puro.

La capa se construye opaca (fill de ambiente + suma de luces) y se aplica con
un solo blit multiplicativo. Medido en esta maquina con 13 luces: 0.47 ms por
frame, frente a 1.5-2.2 ms de las variantes que reescalaban a media
resolucion. El reescalado salia mas caro que la propia capa, porque en
pygame el blit multiplicativo y el blit alfa a RGB solo van rapidos a
resolucion completa.
"""

import math
import random

import pygame

# La capa se calcula a esta proporcion de la pantalla. 1.0 = a resolucion
# completa, que es lo mas rapido aqui: bajar a 0.5 obligaba a un
# transform.scale de 0.73 ms que no se ahorraba por otro lado.
ESCALA_CAPA = 1.0

# Cuantos anillos y rayos se usan para recortar la luz por muros. 12x4 = 48
# comprobaciones por luz ocluida.
_RAYOS_OCLUSION = 12
_PASOS_OCLUSION = 4


def _gradado_radial(radio, color, caida=2.0):
    """Textura circular con caida suave: opaca en el centro, 0 en el borde.

    Va ya tintada con el color de la luz, porque es lo que se reutiliza: dos
    luces del mismo color y radio comparten textura.
    """
    lado = max(4, int(radio * 2))
    surf = pygame.Surface((lado, lado), pygame.SRCALPHA)
    centro = lado / 2.0
    r, g, b = color
    for y in range(lado):
        dy = y - centro
        for x in range(lado):
            dx = x - centro
            d = math.hypot(dx, dy) / radio
            if d >= 1.0:
                continue
            surf.set_at((x, y), (r, g, b, int(255 * (1.0 - d) ** caida)))
    return surf


class Luz:
    """Una fuente de luz puntual."""

    __slots__ = ("x", "y", "radio", "color", "intensidad", "parpadeo", "fase",
                 "velocidad", "viva", "caida", "_cache_brillo", "vida",
                 "vida_max")

    def __init__(self, x, y, radio, color=(255, 240, 200), intensidad=1.0,
                 parpadeo=0.0, caida=2.0):
        self.x = float(x)
        self.y = float(y)
        self.radio = float(radio)
        self.color = color
        self.intensidad = intensidad
        # Parpadeo en [0, 1]: 0 fijo, 1 parpadea fuerte.
        self.parpadeo = parpadeo
        self.fase = random.random() * math.tau
        self.velocidad = random.uniform(0.02, 0.05)
        self.caida = caida
        self.viva = True
        # None = luz fija. Con un numero = destello que se apaga en esos frames.
        self.vida = None
        self.vida_max = None
        self._cache_brillo = {}

    def actualizar(self):
        if self.parpadeo > 0.0:
            self.fase += self.velocidad
        if self.vida is not None:
            self.vida -= 1
            if self.vida <= 0:
                self.vida = None
                self.viva = False

    def brillo(self):
        """Intensidad de este frame, con el parpadeo y el desvanecido aplicados."""
        base = self.intensidad
        if self.vida is not None and self.vida_max:
            base *= self.vida / self.vida_max
        if self.parpadeo <= 0.0:
            return base
        t = self.fase
        # Dos armónicos: el segundo da el caracter a tubo neón defectuoso.
        v = 0.5 + 0.35 * math.sin(t) + 0.15 * math.sin(t * 2.3 + 1.1)
        return max(0.0, base *
                   (1.0 - self.parpadeo * 0.5 + self.parpadeo * 0.5 * v))

    def sigue(self, x, y, margen=0):
        return math.hypot(self.x - x, self.y - y) <= self.radio + margen


class Luces:
    """Gestor de luces y composicion de la capa de iluminacion."""

    def __init__(self, ancho, alto, ambiente=(238, 240, 250), luz_ambiente=1.0):
        self.ancho = ancho
        self.alto = alto
        # El ambiente es un FACTOR de 0 a 255, no un color absoluto: la capa
        # se multiplica sobre la escena, asi que con ambiente 60 un gris 200 se
        # ve como 200*60/255 = 47. Subirlo ilumina mas lo que no esta bajo
        # ninguna luz, bajar lo oscurece.
        #
        # Va alto a proposito: el juego es un shooter cenital que se tiene que
        # poder leer, y un ambiente bajo dejaba todo fuera del radio de la luz
        # casi negro. Con 238 el mapa se ve practicamente igual que sin luz y
        # las luces solo aportan el tinte calido.
        self.ambiente = ambiente
        self.luz_ambiente = luz_ambiente
        self.luces = []
        self.frame = 0
        self._texturas = {}
        self._capa = None
        # Destellos (fogonazos, impactos): se reciclan desde _libres para no
        # crear un objeto por cada disparo.
        self._destellos = []
        self._libres = []
        # Contadores del ultimo frame, para medir.
        self.dibujadas = 0
        self.descartadas = 0

    # --------------------------------------------------------------- luces
    def crear(self, x, y, radio, color=(255, 240, 200), intensidad=1.0,
              parpadeo=0.0, caida=2.0):
        luz = Luz(x, y, radio, color, intensidad, parpadeo, caida)
        self.luces.append(luz)
        return luz

    def destello(self, x, y, radio, color=(255, 240, 200), intensidad=1.0,
                 vida=8):
        """Luz que aparece y se apaga en ``vida`` frames (pool, sin asignar)."""
        if self._libres:
            luz = self._libres.pop()
        else:
            luz = Luz(x, y, radio, color)
            luz._cache_brillo = {}
        luz.x = float(x)
        luz.y = float(y)
        luz.radio = float(radio)
        luz.color = color
        luz.intensidad = intensidad
        luz.caida = 2.0
        luz.parpadeo = 0.0
        luz.vida = vida
        luz.vida_max = vida
        luz.viva = True
        luz._cache_brillo.clear()
        self._destellos.append(luz)
        return luz

    def seguir(self, luz, x, y):
        """Reubica una luz (la del jugador, la de un enemigo que se mueve)."""
        luz.x = x
        luz.y = y

    def quitar(self, luz):
        try:
            self.luces.remove(luz)
        except ValueError:
            pass

    def limpiar(self):
        self.luces = [l for l in self.luces if l.viva]

    def vaciar(self):
        self.luces = []
        self._destellos = []
        self._libres = []

    # --------------------------------------------------------------- ciclo
    def actualizar(self):
        self.frame += 1
        for luz in self.luces:
            luz.actualizar()
        self.limpiar()
        # Los destellos se apagan solos y vuelven al pool.
        vivos = []
        for luz in self._destellos:
            luz.actualizar()
            if luz.vida is None:
                if len(self._libres) < 32:
                    self._libres.append(luz)
            else:
                vivos.append(luz)
        self._destellos = vivos

    # ------------------------------------------------------------- interno
    def _textura(self, luz):
        clave = (int(luz.radio), round(luz.caida, 2), luz.color)
        tex = self._texturas.get(clave)
        if tex is None:
            tex = _gradado_radial(clave[0], luz.color, luz.caida)
            self._texturas[clave] = tex
        return tex

    def _capa_bruta(self):
        """La capa de luz, opaca y reutilizada entre frames.

        No lleva SRCALPHA a proposito: se rellena con el ambiente y se le
        suman las luces, y asi se evita el blit alfa a RGB de pantalla
        completa, que era de los 0.43 ms mas caros del pipeline.
        """
        ancho = max(1, int(self.ancho * ESCALA_CAPA))
        alto = max(1, int(self.alto * ESCALA_CAPA))
        if self._capa is None or self._capa.get_size() != (ancho, alto):
            self._capa = pygame.Surface((ancho, alto))
        return self._capa

    def _aplicar_brillo(self, luz, tex):
        """Textura al brillo actual, con pocas variantes cacheadas.

        No se clona por luz y frame: el parpadeo es suave, asi que se
        cuantiza el brillo y se reutiliza la variante cercana.
        """
        brillo = luz.brillo()
        if brillo >= 0.995:
            return tex, brillo
        clave = int(brillo * 32)
        img = luz._cache_brillo.get(clave)
        if img is None:
            img = tex.copy()
            # Multiplicar el alfa por el brillo atenua la luz sin reponerla.
            img.fill((255, 255, 255, int(255 * min(1.0, brillo))),
                     special_flags=pygame.BLEND_RGBA_MULT)
            if len(luz._cache_brillo) > 48:
                luz._cache_brillo.clear()
            luz._cache_brillo[clave] = img
        return img, brillo

    def _recortar(self, luz, img, oclusion):
        """Sombrea la parte de la luz que queda tras un muro.

        Se muestrea en radios desde el centro: si el muro esta antes de llegar
        a la luz, ese tramo se apaga. Queda una sombra con borde suave, que es
        lo que da la sensacion de que la luz rebota en el muro.
        """
        r = luz.radio
        lado = img.get_width()
        centro = lado / 2.0
        sombra = pygame.Surface((lado, lado), pygame.SRCALPHA)
        hay_sombra = False
        for k in range(_RAYOS_OCLUSION):
            a = k * math.tau / _RAYOS_OCLUSION
            ca, sa = math.cos(a), math.sin(a)
            for paso in range(1, _PASOS_OCLUSION + 1):
                d = r * paso / _PASOS_OCLUSION
                if oclusion(luz.x, luz.y, luz.x + ca * d, luz.y + sa * d):
                    # A partir de aqui el rayo esta bloqueado: se apaga todo
                    # el tramo exterior.
                    pygame.draw.line(
                        sombra, (0, 0, 0, 190),
                        (int(centro + ca * d), int(centro + sa * d)),
                        (int(centro + ca * r), int(centro + sa * r)),
                        int(max(2, r * ESCALA_CAPA)),
                    )
                    hay_sombra = True
                    break
        if not hay_sombra:
            return img
        img = img.copy()
        img.blit(sombra, (0, 0))
        return img

    # ---------------------------------------------------------- composicion
    def componer(self, pantalla, cam_x, cam_y, oclusion=None):
        """Multiplica la escena ya pintada por la capa de luz.

        ``oclusion`` es un callback ``f(x0, y0, x1, y1) -> bool`` que dice si
        hay muro en el tramo. Si no se pasa, la luz atraviesa los muros.
        """
        capa = self._capa_bruta()
        # El ambiente es el piso de la capa: es lo que se ve donde no llega
        # ninguna luz, y sobre el se suman las luces.
        a = self.ambiente
        k = max(0.0, min(1.0, self.luz_ambiente))
        capa.fill((int(a[0] * k), int(a[1] * k), int(a[2] * k)))
        self.dibujadas = 0
        self.descartadas = 0

        ancho_capa, alto_capa = capa.get_size()
        # Las fijas y los destellos se pintan en la misma pasada.
        for luz in self.luces + self._destellos:
            sx = (luz.x - cam_x) * ESCALA_CAPA
            sy = (luz.y - cam_y) * ESCALA_CAPA
            r = luz.radio * ESCALA_CAPA
            # Descarta lo que no toca pantalla, con margen para el radio.
            if (sx + r < 0 or sy + r < 0 or sx - r > ancho_capa
                    or sy - r > alto_capa):
                self.descartadas += 1
                continue
            if luz.brillo() <= 0.03:
                continue
            tex = self._textura(luz)
            img, brillo = self._aplicar_brillo(luz, tex)
            if oclusion is not None and luz.radio > 90:
                img = self._recortar(luz, img, oclusion)
            if brillo <= 0.03:
                continue
            # El alfa de la textura modula la suma sobre la capa.
            capa.blit(img, (int(sx - r), int(sy - r)),
                      special_flags=pygame.BLEND_RGBA_ADD)
            self.dibujadas += 1

        # Un solo blit multiplicativo sobre la pantalla: la capa ya lleva el
        # ambiente de base, asi que no hace falta ninguna superficie intermedia
        # para componerla. Donde no llega luz se queda en el ambiente, no en
        # negro puro.
        if capa.get_size() == pantalla.get_size():
            pantalla.blit(capa, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        else:
            pantalla.blit(pygame.transform.scale(capa, pantalla.get_size()),
                          (0, 0), special_flags=pygame.BLEND_RGB_MULT)
