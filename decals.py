"""Marcas persistentes en el suelo: agujeros, quemaduras y salpicaduras.

Que cambia con esto
-------------------
`efectos.GestorParticulas` borra todo a los pocos frames: un impacto se ve
un instante y desaparece. Aqui las marcas se quedan. Se acumulan durante la
partida y se van desvaneciendo solas, asi que el mapa acaba contando lo que
ha pasado en el: donde se ha peleado, que muro ha recibido mas impactos, que
zona ha sido barrida por una explosion.

Por que una lista y no una superficie del tamaño de la arena
------------------------------------------------------------
La alternativa obvio es una superficie del tamano del mapa donde se pinta
y se borra con un alpha. El problema es el desvanecido: `fill` con
`BLEND_RGBA_SUB` sobre una superficie de 1920x1440 cuesta mas de 15 ms, y
hacerlo cada frame es inviable. Hacerlo cada 30 frames sigue siendo un
tiron de 15 ms cada medio segundo, que se ve como un parpadeo.

Con una lista de sprites ageing no hay ninguna pasada de pantalla completa:
se dibuja solo lo que se ve, con un alfa que sale de la edad. El coste es
proporcional a las marcas visibles, no al tamaño del mapa, y la memoria es
la de los sprites, no la de un lienzo gigante.

Los sprites se cachean por (tipo, radio, tinte, tramo de edad), asi que el
aging no regenera nada: solo elige una variante ya hecha.
"""
import math
import random

import pygame

MAX_MARCAS = 150
# Frames que vive una marca. A 60 fps son unos 20 s de rastro.
VIDA_BASE = 1150
# Ultimo cuarto de la vida: aqui es cuando se apaga.
FRACCION_APAGADO = 0.35
TRAMOS_EDAD = 6

# Paleta fija. No se tiñe con el color de quien la deja: un agujero de bala
# es siempre oscuro y una quemadura siempre calida. Ademas, si el tinte
# dependiera del enemigo, la cache de sprites creeria sin limite.
COLOR_AGUJERO = (26, 24, 30)
COLOR_QUEMADURA = (38, 26, 20)
COLOR_CHISPA = (72, 56, 40)
# Tintes de salpicadura: 6 familias de color. Se elige el mas cercano al color
# del enemigo y se guarda cuantizado, para que la cache de sprites tenga un
# numero fijo de variantes en vez de uno por cada color de la partida.
# Van saturados a proposito: un tono apagado hacia gris hacia el medio, y el
# rastro de un enemigo rojo acaba pareciendo una mancha neutra.
TONOS_SALPICADURA = (
    (150, 34, 40), (128, 40, 96), (44, 82, 140),
    (146, 108, 30), (40, 112, 78), (104, 104, 116),
)


def _tono(color):
    """Elige uno de los 6 tonos de salpicadura mas cercano al color dado."""
    mejor = 0
    mejor_d = None
    for i, t in enumerate(TONOS_SALPICADURA):
        d = (abs(t[0] - color[0]) + abs(t[1] - color[1]) + abs(t[2] - color[2]))
        if mejor_d is None or d < mejor_d:
            mejor_d = d
            mejor = i
    return mejor


class Marca:
    """Una marca en el suelo, con su sprite y su edad."""

    __slots__ = ("x", "y", "img", "edad", "vida")

    def __init__(self, x, y, img, vida):
        self.x = x
        self.y = y
        self.img = img
        self.edad = 0
        self.vida = vida

    def actualizar(self):
        self.edad += 1
        return self.edad < self.vida

    def alpha(self):
        """1 mientras la marca es joven, luego baja a 0 al final de su vida."""
        if self.edad < self.vida * (1.0 - FRACCION_APAGADO):
            return 1.0
        restante = 1.0 - (self.edad - self.vida * (1.0 - FRACCION_APAGADO)) / (
            self.vida * FRACCION_APAGADO)
        return max(0.0, min(1.0, restante))


class Marcas:
    """Conjunto de marcas del suelo, acotado y con desvanecido por edad."""

    def __init__(self, maximo=MAX_MARCAS):
        self.maximo = maximo
        self.marcas = []
        self._cache = {}
        self.frame = 0

    def vaciar(self):
        self.marcas = []

    def actualizar(self):
        self.frame += 1
        if not self.marcas:
            return
        self.marcas = [m for m in self.marcas if m.actualizar()]

    # ------------------------------------------------------------- anadir
    def impacto(self, x, y, color=(255, 205, 120)):
        """Agujero de impacto: pequeno, oscuro, con el borde reventado."""
        self._añadir(x, y, "agujero", 4 + random.random() * 2, 0)

    def quemadura(self, x, y, escala=1.0):
        """Quemadura de explosion: mancha blanda y caliente."""
        self._añadir(x, y, "quemadura", 11 + random.random() * 7 * escala, 1)

    def salpicadura(self, x, y, color, escala=1.0):
        """Restos de un enemigo: mancha del color de la criatura."""
        self._añadir(x, y, "salpicadura", 8 + random.random() * 9 * escala,
                     _tono(color))

    def grieta(self, x, y, escala=1.0):
        self._añadir(x, y, "grieta", 16 + random.random() * 14 * escala, 2)

    def _añadir(self, x, y, tipo, radio, tinte):
        # Con el tope lleno se va la mas vieja: es lo que menos se nota.
        if len(self.marcas) >= self.maximo:
            self.marcas.pop(0)
        vida = int(VIDA_BASE * (0.7 + random.random() * 0.6))
        self.marcas.append(Marca(x, y, self._sprite(tipo, radio, tinte, 1.0), vida))

    # ------------------------------------------------------------- dibujar
    def dibujar(self, pantalla, cam_x, cam_y, vw, vh):
        if not self.marcas:
            return
        marco = 40  # margen para los sprites grandes
        for m in self.marcas:
            sx = m.x - cam_x
            sy = m.y - cam_y
            if sx < -marco or sy < -marco or sx > vw + marco or sy > vh + marco:
                continue
            img = self._sprite_variante(m)
            if img is None:
                continue
            pantalla.blit(img, (int(sx - img.get_width() / 2),
                                int(sy - img.get_height() / 2)))

    def _sprite_variante(self, marca):
        """El sprite con el alfa del tramo de edad que le toca."""
        a = marca.alpha()
        if a <= 0.02:
            return None
        if a > 0.995:
            return marca.img
        tramo = max(0, min(TRAMOS_EDAD - 1, int(a * TRAMOS_EDAD)))
        clave = (id(marca.img), tramo)
        img = self._cache.get(clave)
        if img is None:
            img = marca.img.copy()
            img.fill((255, 255, 255, int(255 * (tramo + 1) / TRAMOS_EDAD)),
                     special_flags=pygame.BLEND_RGBA_MULT)
            # La cache se acota con la de los sprites: si no, y como la clave
            # lleva id(), podria crecer sin limite.
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[clave] = img
        return img

    # ------------------------------------------------------------- sprites
    def _sprite(self, tipo, radio, tinte, fuerza):
        """Sprite de la marca, cacheado. Se construye en blanco y se tiñe."""
        radio = max(2, int(radio))
        clave = (tipo, radio, tinte, int(fuerza * 4))
        img = self._cache.get(clave)
        if img is not None:
            return img
        if tipo == "agujero":
            img = self._dibujar_agujero(radio)
        elif tipo == "quemadura":
            img = self._dibujar_quemadura(radio)
        elif tipo == "salpicadura":
            img = self._dibujar_salpicadura(radio)
        else:
            img = self._dibujar_grieta(radio)
        color = self._color_de(tipo, tinte)
        img.fill((color[0], color[1], color[2], 255),
                 special_flags=pygame.BLEND_RGBA_MULT)
        if len(self._cache) > 400:
            self._cache.clear()
        self._cache[clave] = img
        return img

    @staticmethod
    def _color_de(tipo, tinte):
        if tipo == "agujero":
            return COLOR_AGUJERO
        if tipo == "quemadura":
            return COLOR_QUEMADURA
        if tipo == "grieta":
            return COLOR_CHISPA
        return TONOS_SALPICADURA[tinte % len(TONOS_SALPICADURA)]

    # Cada sprite se dibuja en blanco (255) y luego se tiñe multiplicando, para
    # que el color se pueda cambiar sin volver a trazar la forma.
    @staticmethod
    def _dibujar_agujero(radio):
        lado = radio * 4
        sup = pygame.Surface((lado, lado), pygame.SRCALPHA)
        c = lado // 2
        pygame.draw.circle(sup, (90, 90, 90, 150), (c, c), radio, 1)
        pygame.draw.circle(sup, (215, 215, 215, 235), (c, c), radio)
        pygame.draw.circle(sup, (60, 60, 60, 255), (c, c), max(1, radio // 3))
        return sup

    @staticmethod
    def _dibujar_quemadura(radio):
        lado = radio * 2
        sup = pygame.Surface((lado, lado), pygame.SRCALPHA)
        c = radio
        # Se dibuja de fuera hacia dentro con menos alfa: el centro queda mas
        # denso y el borde se disuelve.
        pasos = 7
        for i in range(pasos, 0, -1):
            f = i / pasos
            r = int(radio * f)
            a = int(120 * (1.0 - f) ** 0.8)
            if a <= 2:
                continue
            pygame.draw.circle(sup, (255, 255, 255, a), (c, c), r)
        return sup

    @staticmethod
    def _dibujar_salpicadura(radio):
        lado = radio * 2
        sup = pygame.Surface((lado, lado), pygame.SRCALPHA)
        c = radio
        # Mancha irregular: varios circulos desplazados al azar.
        for _ in range(5):
            dx = random.randint(-radio // 2, radio // 2)
            dy = random.randint(-radio // 2, radio // 2)
            r = random.randint(max(2, radio // 3), max(3, radio * 2 // 3))
            pygame.draw.circle(sup, (255, 255, 255, 130), (c + dx, c + dy), r)
        # Gotas que salen despedidas.
        for _ in range(4):
            a = random.random() * math.tau
            d = radio * random.uniform(0.5, 1.0)
            pygame.draw.circle(sup, (255, 255, 255, 105),
                               (int(c + math.cos(a) * d), int(c + math.sin(a) * d)),
                               max(1, random.randint(1, max(2, radio // 4))))
        return sup

    @staticmethod
    def _dibujar_grieta(radio):
        lado = radio * 2
        sup = pygame.Surface((lado, lado), pygame.SRCALPHA)
        c = radio
        # Lineas radiales cortas desde el centro: parece una fractura.
        for _ in range(7):
            a = random.random() * math.tau
            largo = random.randint(radio // 2, radio)
            pygame.draw.line(sup, (255, 255, 255, 150), (c, c),
                             (int(c + math.cos(a) * largo),
                              int(c + math.sin(a) * largo)),
                             random.choice((1, 1, 2)))
        pygame.draw.circle(sup, (255, 255, 255, 110), (c, c), max(2, radio // 4))
        return sup
