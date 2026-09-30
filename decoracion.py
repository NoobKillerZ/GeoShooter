# -*- coding: utf-8 -*-
"""
decoracion.py
=============
Props y ambiente del mapa. Nada de esto colisiona: es lo que hace que la
arena deje de ser una cuadrícula de colores planos.

Todo se genera con la semilla de la arena, así que el mismo mapa sale siempre
igual (las pruebas dependen de eso) y hay que regenerarlo si cambia la
semilla. Se pinta una sola vez en una superficie junto al suelo, y en cada
frame es un blit más.

Piezas:

* ``Prop``          un objeto con forma, capa y comportamiento de parpadeo.
* ``Decoracion``    genera y pinta todo: suelo, grietas, charcos, tuberías,
                    manchas, cables, rejillas, chatarra yDetalles finos.
* Niebla y polvo    capas atmosféricas animadas, que se dibujan por frame
                    porque se mueven (barato: dos surfaces tileadas).
"""

import math
import random

import pygame

# Paleta de decoracion.
COL_GRIETA = (26, 27, 36)
COL_GRIETA_CLARA = (48, 50, 64)
COL_CHARCO = (22, 24, 33)
COL_CHARCO_BRILLO = (58, 74, 92)
COL_TUBERIA = (74, 78, 96)
COL_TUBERIA_TOP = (104, 110, 134)
COL_TUBERIA_SOMBRA = (44, 46, 60)
COL_CHATARRA = (66, 62, 70)
COL_CHATARRA_TOP = (94, 90, 100)
COL_MANCHA = (34, 36, 46)
COL_REJILLA = (50, 53, 68)
COL_CABLE = (30, 32, 42)
COL_BRILLO = (150, 160, 185)
COL_SALIDA = (40, 90, 70)
COL_SALIDA_TOP = (70, 150, 120)

TIPOS_PROP = ("grieta", "charco", "tuberia", "mancha", "rejilla", "chatarra",
              "cable", "polvo", "salida")


class Prop:
    """Un objeto decorativo, ya con su forma resuelta."""

    __slots__ = ("tipo", "x", "y", "ancho", "alto", "rot", "capa", "color",
                 "color2", "radio", "fase", "semilla", "extra")

    def __init__(self, tipo, x, y, ancho=32, alto=32, rot=0.0, capa=0,
                 color=None, color2=None, radio=0, semilla=0, extra=None):
        self.tipo = tipo
        self.x = float(x)
        self.y = float(y)
        self.ancho = ancho
        self.alto = alto
        self.rot = rot
        # Capa: 0 = bajo los muros, 1 = encima del suelo. Sirve para que los
        # charcos queden bajo las unidades y las tuberías no.
        self.capa = capa
        self.color = color
        self.color2 = color2
        self.radio = radio
        self.fase = random.Random(semilla).random() * math.tau
        self.semilla = semilla
        self.extra = extra or {}

    def __repr__(self):
        return "<Prop %s en (%d,%d)>" % (self.tipo, int(self.x), int(self.y))


class Decoracion:
    """Genera, cachea y pinta la decoracion de una arena."""

    def __init__(self, arena):
        self.arena = arena
        self.props = []
        self._bajo_muros = None
        self._sobre_muros = None
        self._arena_ref = None
        self.generar()

    # ------------------------------------------------------------ generar
    def generar(self):
        arena = self.arena
        # Se siembra con la semilla de la arena, no con id(arena): dos arenas
        # con la misma semilla tienen que quedar igual, y id() cambia siempre.
        rng = random.Random(arena.semilla ^ 0x5EED)
        props = []

        # Charcos: en el suelo, oscuros, con reflejo. Frequent en pasillos.
        for _ in range(rng.randint(14, 22)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            r = rng.randint(12, 30)
            props.append(Prop("charco", x, y, r * 2, r * 2, capa=0,
                              radio=r, semilla=rng.random(),
                              extra={"brillo": rng.random() * math.tau}))

        # Grietas: lineas ramificadas por el suelo.
        for _ in range(rng.randint(8, 14)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            largo = rng.randint(50, 150)
            puntos = []
            px, py = x, y
            ang = rng.uniform(0, math.tau)
            for _ in range(rng.randint(3, 6)):
                puntos.append((int(px), int(py)))
                ang += rng.uniform(-0.7, 0.7)
                px += math.cos(ang) * largo / 5
                py += math.sin(ang) * largo / 5
            puntos.append((int(px), int(py)))
            props.append(Prop("grieta", x, y, capa=0, semilla=rng.random(),
                              extra={"puntos": puntos, "grosor": rng.randint(1, 3)}))

        # Rejillas de ventilacion: recuadros con lineas.
        for _ in range(rng.randint(4, 7)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            props.append(Prop("rejilla", x, y, 30, 30, rng.uniform(0, math.pi / 2),
                              capa=0, semilla=rng.random(),
                              extra={"lineas": rng.randint(3, 6)}))

        # Tuberías: tramos rectos con uniones, pegados a los muros.
        self._colocar_tuberias(rng, props)

        # Cables: tendidos curvos que cruzan una sala.
        for _ in range(rng.randint(1, 3)):
            props.append(self._colocar_cable(rng))

        # Chatarra: montoncitos angulares.
        for _ in range(rng.randint(7, 12)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            n = rng.randint(3, 6)
            puntos = []
            for k in range(n):
                a = k * math.tau / n + rng.uniform(-0.3, 0.3)
                d = rng.uniform(4, 13)
                puntos.append((int(math.cos(a) * d), int(math.sin(a) * d)))
            props.append(Prop("chatarra", x, y, capa=1, semilla=rng.random(),
                              extra={"puntos": puntos}))

        # Manchas: decolores limpios, para romper el color uniforme.
        for _ in range(rng.randint(8, 14)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            r = rng.randint(16, 38)
            props.append(Prop("mancha", x, y, r * 2, r * 2, capa=0, radio=r,
                              semilla=rng.random()))

        # Salidas: rarezas que dan color. Luces propias aparte.
        for _ in range(2):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            props.append(Prop("salida", x, y, 24, 24, capa=1, semilla=rng.random()))

        # Motas de polvo: pequeñas, capa alta, se dibujan por frame.
        for _ in range(rng.randint(40, 70)):
            col, fila = self._celda_libre_aleatoria(rng)
            x, y = self._centro(col, fila)
            props.append(Prop("polvo", x, y, capa=1, semilla=rng.random(),
                              extra={"v": rng.uniform(0.2, 0.7),
                                     "r": rng.uniform(0.6, 1.6),
                                     "deriva": rng.uniform(-0.15, 0.15)}))

        self.props = props
        self._bajo_muros = None
        self._sobre_muros = None

    def _celda_libre_aleatoria(self, rng, intentos=40):
        for _ in range(intentos):
            col = rng.randint(1, self.arena.cols - 2)
            fila = rng.randint(1, self.arena.filas - 2)
            if not self.arena.celda_bloqueada(col, fila):
                return col, fila
        return 2, 2

    def _centro(self, col, fila):
        return (col * 32 + 16, fila * 32 + 16)

    def _colocar_tuberias(self, rng, props):
        """Tuberias pegadas a los muros, en tramos."""
        muros = sorted(self.arena.muros)
        rng.shuffle(muros)
        colocados = 0
        for col, fila in muros:
            if colocados >= 6:
                break
            if rng.random() > 0.4:
                continue
            largo = rng.randint(2, 4) * 32
            # Horizontal pegada al borde superior de la celda.
            x = col * 32
            y = fila * 32 + 6
            props.append(Prop("tuberia", x + largo / 2, y, largo, 10,
                              rot=0.0, capa=1, semilla=rng.random(),
                              extra={"eje": "h"}))
            # Union al final.
            props.append(Prop("tuberia", x + largo, y, 14, 14, capa=1,
                              semilla=rng.random(), extra={"eje": "nodo"}))
            colocados += 1

    def _colocar_cable(self, rng):
        col, fila = self._celda_libre_aleatoria(rng)
        x0, y0 = self._centro(col, fila)
        largo = rng.randint(60, 150)
        ang = rng.choice((0, math.pi / 2))
        puntos = [(int(x0), int(y0))]
        x, y = x0, y0
        for _ in range(4):
            x += math.cos(ang) * largo / 4 + rng.uniform(-4, 4)
            y += math.sin(ang) * largo / 4 + rng.uniform(-4, 4)
            puntos.append((int(x), int(y)))
        return Prop("cable", x0, y0, capa=1, semilla=rng.random(),
                    extra={"puntos": puntos})

    # --------------------------------------------------------------- pint
    def _pintar_prop(self, surf, prop, t):
        if prop.tipo == "charco":
            self._pintar_charco(surf, prop)
        elif prop.tipo == "grieta":
            self._pintar_grieta(surf, prop)
        elif prop.tipo == "rejilla":
            self._pintar_rejilla(surf, prop)
        elif prop.tipo == "cable":
            self._pintar_cable(surf, prop)
        elif prop.tipo == "chatarra":
            self._pintar_chatarra(surf, prop)
        elif prop.tipo == "tuberia":
            self._pintar_tuberia(surf, prop)
        elif prop.tipo == "mancha":
            self._pintar_mancha(surf, prop)
        elif prop.tipo == "salida":
            self._pintar_salida(surf, prop, t)

    def _pintar_charco(self, surf, prop):
        r = prop.radio
        if r < 2:
            return
        # Base oscura
        pygame.draw.circle(surf, COL_CHARCO, (int(prop.x), int(prop.y)), r)
        # Borde un poco mas claro: se nota que es liquido.
        pygame.draw.circle(surf, COL_CHARCO_BRILLO, (int(prop.x), int(prop.y)),
                           r, 1)
        # Reflejo: un arco claro en un lado, fijo (no se mueve, es pintura).
        fase = prop.extra.get("brillo", 0.0)
        a0 = int(fase * 360)
        if r > 8:
            caja = pygame.Rect(int(prop.x - r), int(prop.y - r), r * 2, r * 2)
            pygame.draw.arc(surf, COL_CHARCO_BRILLO, caja,
                            math.radians(a0), math.radians(a0 + 70), 2)
        # Brillo especular
        if r > 10:
            pygame.draw.ellipse(surf, (90, 110, 135),
                                (int(prop.x - r * 0.4), int(prop.y - r * 0.5),
                                 int(r * 0.5), int(r * 0.25)))

    def _pintar_grieta(self, surf, prop):
        puntos = prop.extra.get("puntos")
        if not puntos or len(puntos) < 2:
            return
        grosor = prop.extra.get("grosor", 2)
        pygame.draw.lines(surf, COL_GRIETA, False, puntos, grosor + 1)
        pygame.draw.lines(surf, COL_GRIETA_CLARA, False, puntos, 1)

    def _pintar_rejilla(self, surf, prop):
        w, h = 26, 26
        x, y = int(prop.x - w / 2), int(prop.y - h / 2)
        caja = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, COL_REJILLA, caja, 2)
        n = prop.extra.get("lineas", 4)
        for k in range(1, n):
            ly = y + h * k // n
            pygame.draw.line(surf, COL_REJILLA, (x + 2, ly), (x + w - 2, ly), 1)
        # Brillo de la rejilla
        pygame.draw.line(surf, (80, 86, 108), (x + 2, y + 2), (x + w - 2, y + 2), 1)

    def _pintar_tuberia(self, surf, prop):
        eje = prop.extra.get("eje", "h")
        largo = int(prop.ancho)
        grosor = 8
        if eje == "h":
            x0, x1 = int(prop.x - largo / 2), int(prop.x + largo / 2)
            y = int(prop.y)
            pygame.draw.line(surf, COL_TUBERIA_SOMBRA, (x0, y + grosor // 2 + 2),
                             (x1, y + grosor // 2 + 2), grosor)
            pygame.draw.line(surf, COL_TUBERIA, (x0, y), (x1, y), grosor)
            pygame.draw.line(surf, COL_TUBERIA_TOP, (x0, y - grosor // 2 + 1),
                             (x1, y - grosor // 2 + 1), 1)
            # Juntas de union
            for k in range(1, max(1, largo // 64)):
                jx = x0 + largo * k // max(1, largo // 64)
                pygame.draw.line(surf, COL_TUBERIA_SOMBRA, (jx, y - grosor // 2),
                                 (jx, y + grosor // 2), 2)
        else:
            # Nodo: un cuadrado con tornillos.
            pygame.draw.rect(surf, COL_TUBERIA, (int(prop.x - 6), int(prop.y - 6), 12, 12))
            pygame.draw.rect(surf, COL_TUBERIA_TOP, (int(prop.x - 6), int(prop.y - 6), 12, 12), 1)
            for dx, dy in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
                pygame.draw.circle(surf, COL_TUBERIA_SOMBRA,
                                   (int(prop.x + dx), int(prop.y + dy)), 1)

    def _pintar_cable(self, surf, prop):
        puntos = prop.extra.get("puntos")
        if puntos and len(puntos) >= 2:
            pygame.draw.lines(surf, COL_CABLE, False, puntos, 2)
            pygame.draw.lines(surf, (52, 54, 66), False, puntos, 1)

    def _pintar_chatarra(self, surf, prop):
        puntos = prop.extra.get("puntos")
        if not puntos:
            return
        py_points = [(int(prop.x + dx), int(prop.y + dy)) for dx, dy in puntos]
        pygame.draw.polygon(surf, COL_CHATARRA, py_points)
        # Borde superior: da volumen.
        pygame.draw.lines(surf, COL_CHATARRA_TOP, True, py_points, 1)

    def _pintar_mancha(self, surf, prop):
        r = prop.radio
        if r < 3:
            return
        # Varias capas con alfa baja hacen una mancha irregular, sin usar
        # una textura nueva por mancha.
        for k, f in ((0, 1.0), (1, 0.66), (2, 0.4)):
            pygame.draw.circle(surf, COL_MANCHA,
                               (int(prop.x + (prop.semilla - 0.5) * 8 * k),
                                int(prop.y + (0.5 - prop.semilla) * 6 * k)),
                               int(r * f))

    def _pintar_salida(self, surf, prop, t):
        x, y = int(prop.x), int(prop.y)
        pygame.draw.rect(surf, COL_SALIDA, (x - 10, y - 10, 20, 20), 2)
        pygame.draw.rect(surf, COL_SALIDA_TOP, (x - 10, y - 10, 20, 20), 1)
        # Tres rayas que "corren": una se ilumina y va pasando.
        f = int(t * 6) % 3
        for k in range(3):
            if k == f:
                pygame.draw.rect(surf, COL_SALIDA_TOP, (x - 6 + k * 5, y - 6, 3, 12))

    def _blit_camara(self, surf, pantalla, cam_x, cam_y, ancho_visor, alto_visor):
        """Pega la capa respetando la camara, como hace Arena.dibujar().

        La decoracion vive en coordenadas de mundo, asi que sin esto se
        desplazaria respecto al suelo en cuanto la camara se moviera.
        """
        cx, cy = int(math.floor(cam_x)), int(math.floor(cam_y))
        sx, sy = max(0, cx), max(0, cy)
        ex = min(self.arena.ancho, cx + ancho_visor + 8)
        ey = min(self.arena.alto, cy + alto_visor + 8)
        if ex > sx and ey > sy:
            pantalla.blit(surf, (sx - cx, sy - cy), (sx, sy, ex - sx, ey - sy),
                          special_flags=pygame.BLEND_RGBA_ADD)

    def dibujar_bajo_muros(self, pantalla, cam_x, cam_y, ancho_visor, alto_visor):
        """Capa 0: charcos, grietas, manchas y rejillas, bajo las unidades."""
        self._blit_camara(self.superficie_bajo_muros(), pantalla, cam_x, cam_y,
                          ancho_visor, alto_visor)

    # ---------------------------------------------------- cache y dibujado
    def superficie_bajo_muros(self):
        """Capa 0: charcos, grietas, manchas, rejillas (bajo las unidades)."""
        if self._bajo_muros is None:
            surf = pygame.Surface((self.arena.ancho, self.arena.alto), pygame.SRCALPHA)
            for prop in self.props:
                if prop.capa == 0:
                    self._pintar_prop(surf, prop, 0)
            self._bajo_muros = surf
        return self._bajo_muros

    def superficie_sobre_muros(self):
        """Capa 1: tuberias, cables, chatarra (encima del suelo)."""
        if self._sobre_muros is None:
            surf = pygame.Surface((self.arena.ancho, self.arena.alto), pygame.SRCALPHA)
            for prop in self.props:
                if prop.capa == 1 and prop.tipo != "polvo":
                    self._pintar_prop(surf, prop, 0)
            self._sobre_muros = surf
        return self._sobre_muros

    def dibujar(self, pantalla, cam_x, cam_y, t, ancho_visor=None, alto_visor=None):
        """Dibuja la capa alta y las motas de polvo (las animadas)."""
        if ancho_visor is None:
            ancho_visor = pantalla.get_width()
        if alto_visor is None:
            alto_visor = pantalla.get_height()
        self._blit_camara(self.superficie_sobre_muros(), pantalla,
                          cam_x, cam_y, ancho_visor, alto_visor)
        # Polvo: barato, son circulos sueltos que flotan.
        for prop in self.props:
            if prop.tipo != "polvo":
                continue
            px = int(prop.x + math.sin(t * prop.extra["v"] + prop.fase) * 12 - cam_x)
            py = int(prop.y + math.cos(t * prop.extra["v"] * 0.7 + prop.fase) * 8 - cam_y)
            if -4 <= px <= ancho_visor + 4 and -4 <= py <= alto_visor + 4:
                pygame.draw.circle(pantalla, (70, 74, 92),
                                   (px, py), max(1, int(prop.extra["r"])))

    # --------------------------------------------------------------- luces
    def luces_ambiente(self, luces):
        """Registra las luces que aportan los props (salidas, chatarra…)."""
        for prop in self.props:
            if prop.tipo == "salida":
                luz = luces.crear(prop.x, prop.y, 70, COL_SALIDA_TOP,
                                  intensidad=0.7, parpadeo=0.25, caida=2.4)
                prop.extra["luz"] = luz
