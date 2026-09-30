# -*- coding: utf-8 -*-
"""
armas.py
========
Armas y proyectiles del shooter cenital.

Cada arma define cadencia, municion, dispersion, velocidad, dano y forma
del proyectil. La clase ArmaJugador gestiona municion y recarga; la clase
Proyectil se dibuja con estela segun su forma.
"""

import math
import random

import pygame

# El juego corre a 60 FPS; las velocidades se expresan en pixeles por segundo
# y se convierten a desplazamiento por frame con este factor.
PASO = 1.0 / 60.0

ARMAS = {
    "pistola": {
        "nombre": "PISTOLA",
        "icono": "*",
        "cadencia": 11,
        "municion": 40,
        "balas": 1,
        "dispersion": 0.03,
        "velocidad": 780,
        "danio": 24,
        "radio": 4,
        "color": (255, 226, 140),
        "borde": (255, 250, 210),
        "forma": "bala",
        "estela": 5,
        "recarga": 24,
    },
    "escopeta": {
        "nombre": "ESCOPETA",
        "icono": "%",
        "cadencia": 34,
        "municion": 14,
        "balas": 7,
        "dispersion": 0.30,
        "velocidad": 640,
        "danio": 14,
        "radio": 4,
        "color": (255, 160, 84),
        "borde": (255, 220, 170),
        "forma": "perdigon",
        "estela": 3,
        "recarga": 46,
    },
    "rifle": {
        "nombre": "RIFLE",
        "icono": "=",
        "cadencia": 5,
        "municion": 90,
        "balas": 1,
        "dispersion": 0.06,
        "velocidad": 940,
        "danio": 15,
        "radio": 3,
        "color": (130, 255, 165),
        "borde": (230, 255, 235),
        "forma": "traza",
        "estela": 9,
        "recarga": 30,
    },
    "laser": {
        "nombre": "LASER",
        "icono": "-",
        "cadencia": 16,
        "municion": 45,
        "balas": 2,
        "dispersion": 0.0,
        "velocidad": 1180,
        "danio": 34,
        "radio": 3,
        "color": (110, 215, 255),
        "borde": (235, 252, 255),
        "forma": "rayo",
        "estela": 12,
        "recarga": 34,
    },
    "sniper": {
        "nombre": "SNIPER",
        "icono": "#",
        "cadencia": 44,
        "municion": 16,
        "balas": 1,
        "dispersion": 0.0,
        "velocidad": 1600,
        "danio": 96,
        "radio": 4,
        "color": (255, 245, 190),
        "borde": (255, 255, 232),
        "forma": "rayo",
        "estela": 18,
        "recarga": 42,
        "perforante": 3,
    },
    "discos": {
        "nombre": "DISCOS",
        "icono": "O",
        "cadencia": 17,
        "municion": 28,
        "balas": 2,
        "dispersion": 0.15,
        "velocidad": 700,
        "danio": 32,
        "radio": 9,
        "color": (120, 235, 255),
        "borde": (226, 250, 255),
        "forma": "disco",
        "estela": 4,
        "recarga": 34,
        "rebotes": 3,
    },
    "lanzallamas": {
        "nombre": "LANZALLAMAS",
        "icono": "~",
        "cadencia": 2,
        "municion": 0,
        "balas": 3,
        "dispersion": 0.40,
        "velocidad": 430,
        "danio": 10,
        "radio": 7,
        "color": (255, 142, 60),
        "borde": (255, 224, 150),
        "forma": "llama",
        "estela": 3,
        "recarga": 1,
        "sin_municion": True,
        "alcance": 20,
    },
    "railgun": {
        "nombre": "RAILGUN",
        "icono": "=",
        "cadencia": 60,
        "municion": 8,
        "balas": 1,
        "dispersion": 0.0,
        "velocidad": 2200,
        "danio": 155,
        "radio": 5,
        "color": (168, 130, 255),
        "borde": (228, 218, 255),
        "forma": "rayo",
        "estela": 24,
        "recarga": 48,
        "perforante": -1,
    },
}

# Solo las armas propias del jugador se recorren con la tecla Q.
ORDEN_ARMAS = ("pistola", "escopeta", "rifle", "laser",
               "sniper", "discos", "lanzallamas", "railgun")

# Formas de los proyectiles enemigos
FORMAS_HOSTILES = {
    "bala": (250, 170, 90),
    "orbita": (250, 90, 90),
    "rayo": (240, 110, 220),
}


class Proyectil:
    def __init__(self, x, y, angulo, velocidad, danio, radio, color, hostil=False,
                 forma="bala", largo_estela=5, perforante=0, rebotes=0,
                 alcance=None, color_borde=None, dano_jugador=12, gira=0.0):
        self.x = float(x)
        self.y = float(y)
        self.angulo = angulo
        self.velocidad = float(velocidad)
        self.danio = danio
        self.radio = radio
        self.color = color
        self.color_borde = color_borde or color
        self.hostil = hostil
        self.forma = forma
        self.largo_estela = largo_estela
        self.estela = []
        self.vivo = True
        self.vida_frames = alcance if alcance is not None else 130
        # Perforante: enemigos extra que atraviesa (-1 = toda la linea).
        self.perforante = perforante
        # Rebotes que le quedan en los muros.
        self.rebotes = rebotes
        # Ids de los enemigos que ya ha tocado: evita dano repetido al rebotar.
        self.impactados = set()
        # Cuanto hace este proyectil al jugador. Los del jugador lo ignoran.
        self.dano_jugador = dano_jugador
        # Giro del angulo por frame: los proyectiles en espiral no apuntan al
        # jugador, giran sobre si mismos mientras avanzan.
        self.gira = gira

    def actualizar(self, arena, particulas):
        self.angulo += self.gira
        self.estela.append((self.x, self.y))
        if len(self.estela) > self.largo_estela:
            self.estela.pop(0)

        x_prev, y_prev = self.x, self.y
        self.x += math.cos(self.angulo) * self.velocidad * PASO
        self.y += math.sin(self.angulo) * self.velocidad * PASO
        self.vida_frames -= 1
        if not arena.punto_libre(self.x, self.y):
            if self.rebotes > 0 and self._rebotar(arena, x_prev, y_prev):
                particulas.impacto(self.x, self.y, self.color_borde)
            else:
                self.vivo = False
                particulas.impacto(self.x, self.y)
        elif self.vida_frames <= 0:
            self.vivo = False
            if self.forma == "llama":
                particulas.impacto(self.x, self.y, (255, 190, 90))

    def _rebotar(self, arena, x_prev, y_prev):
        """Cambia de direccion para no quedarse enganchado en el muro."""
        self.rebotes -= 1
        candidatos = (-self.angulo, math.pi - self.angulo, self.angulo + math.pi)
        for nuevo in candidatos:
            dx, dy = math.cos(nuevo), math.sin(nuevo)
            nx, ny = x_prev + dx * 7, y_prev + dy * 7
            if arena.punto_libre(nx, ny):
                self.angulo = nuevo
                self.x, self.y = nx, ny
                # El rebote resetea la estela: si no, deja un rastro recto
                # que no corresponde a la nueva trayectoria.
                self.estela = [(nx, ny)]
                return True
        return False

    def dibujar(self, pantalla, cam_x, cam_y):
        x = int(self.x - cam_x)
        y = int(self.y - cam_y)
        vw, vh = pantalla.get_width(), pantalla.get_height()
        if x < -40 or y < -40 or x > vw + 40 or y > vh + 40:
            return

        # Estela
        if len(self.estela) > 1:
            puntos = [(int(px - cam_x), int(py - cam_y)) for px, py in self.estela]
            total = len(puntos)
            for i in range(1, total):
                f = i / total
                col = (int(self.color[0] * f * 0.75),
                       int(self.color[1] * f * 0.75),
                       int(self.color[2] * f * 0.75))
                pygame.draw.line(pantalla, col, puntos[i - 1], puntos[i], 1 + int(f * 2))

        cos_a = math.cos(self.angulo)
        sin_a = math.sin(self.angulo)
        claro = tuple(min(255, int(c * 1.25)) for c in self.color)

        if self.forma == "rayo":
            # Rayo: capsula alargada con nucleo blanco
            largo = self.radio * 4
            x0, y0 = int(x - cos_a * largo), int(y - sin_a * largo)
            x1, y1 = int(x + cos_a * largo), int(y + sin_a * largo)
            pygame.draw.line(pantalla, self.color, (x0, y0), (x1, y1), self.radio * 2)
            pygame.draw.line(pantalla, claro, (x0, y0), (x1, y1), max(1, self.radio - 1))
            pygame.draw.circle(pantalla, (255, 255, 255), (x, y), max(1, self.radio - 1))
        elif self.forma == "traza":
            pygame.draw.circle(pantalla, self.color, (x, y), self.radio)
            pygame.draw.circle(pantalla, claro, (x, y), max(1, self.radio - 1))
        elif self.forma == "disco":
            # Disco: circulo con anillo y marca de giro
            pygame.draw.circle(pantalla, (12, 14, 20), (x, y), self.radio + 2)
            pygame.draw.circle(pantalla, self.color, (x, y), self.radio)
            pygame.draw.circle(pantalla, claro, (x, y), self.radio, 2)
            pygame.draw.line(pantalla, claro, (x, y),
                             (int(x + cos_a * self.radio * 0.7),
                              int(y + sin_a * self.radio * 0.7)), 2)
        elif self.forma == "llama":
            # Llama: bola irregular que se apaga al final de su alcance
            vida = min(1.0, max(0.0, self.vida_frames / 14.0))
            r = max(1, int(self.radio * vida))
            pygame.draw.circle(pantalla, self.color, (x, y), r)
            pygame.draw.circle(pantalla, claro, (x, y), max(1, r - 3))
        elif self.forma == "perdigon":
            pygame.draw.circle(pantalla, self.color, (x, y), self.radio)
        elif self.forma == "espiral":
            # Bala de espiral: huso corto con aletas que se ven girar.
            largo = self.radio * 3.2
            x0, y0 = int(x - cos_a * largo), int(y - sin_a * largo)
            x1, y1 = int(x + cos_a * largo), int(y + sin_a * largo)
            pygame.draw.line(pantalla, self.color, (x0, y0), (x1, y1), self.radio)
            pygame.draw.circle(pantalla, claro, (x, y), max(1, self.radio - 1))
            # Aletas perpendiculares al avance
            for lado in (-1, 1):
                ax = int(x - sin_a * self.radio * 1.5 * lado)
                ay = int(y + cos_a * self.radio * 1.5 * lado)
                pygame.draw.line(pantalla, self.color, (x, y), (ax, ay), 2)
        elif self.forma == "onda":
            # Onda expansiva: aro fino con nucleo brillante.
            pygame.draw.circle(pantalla, (18, 16, 26), (x, y), self.radio + 3)
            pygame.draw.circle(pantalla, self.color, (x, y), self.radio, 3)
            pygame.draw.circle(pantalla, claro, (x, y), max(1, self.radio - 3), 2)
        else:  # bala / orbita
            pygame.draw.circle(pantalla, self.color, (x, y), self.radio)
            pygame.draw.circle(pantalla, claro, (x, y), max(1, self.radio - 1), 1)


class ArmaJugador:
    def __init__(self, tipo="pistola", disponibles=None):
        # Multiplicadores de la build: se fijan a 1 y luego los ajusta
        # aplicar_bonos, para que cambiar de arma no lose nada.
        self.mult_danio = 1.0
        self.mult_cadencia = 1.0
        self.mult_municion = 1.0
        self.mult_recarga = 1.0
        # Solo se recorren las armas desbloqueadas en esta partida.
        self.disponibles = list(disponibles) if disponibles else list(ORDEN_ARMAS)
        if self.disponibles and tipo not in self.disponibles:
            tipo = self.disponibles[0]
        self.municion_max = 0
        self.cooldown = 0
        self.recargando = 0
        self.cambiar(tipo)

    def cambiar(self, tipo):
        if self.disponibles and tipo not in self.disponibles:
            tipo = self.disponibles[0]
        self.tipo = tipo if tipo in ARMAS else "pistola"
        self.config = ARMAS[self.tipo]
        # El maximo nunca se encoge: con mejoras de cargador ya compradas, un
        # arma de menos balas no debe perder el cargador ampliado.
        self.municion_max = max(self.municion_max, self.municion_max_config())
        self.municion = self.municion_max
        self.cooldown = 0
        self.recargando = 0
        self.recarga_total = self.tiempo_recarga_config()

    # ------------------------------------------------- multiplicadores de la build
    def aplicar_bonos(self, danio=1.0, cadencia=1.0, municion=1.0, recarga=1.0):
        """Guarda los multiplicadores que-orcurren de la build del jugador."""
        self.mult_danio = danio
        self.mult_cadencia = cadencia
        self.mult_municion = municion
        self.mult_recarga = recarga
        self.municion_max = self.municion_max_config()
        self.municion = min(self.municion_max, max(self.municion, 0))
        self.recarga_total = self.tiempo_recarga_config()

    def municion_max_config(self):
        return int(self.config["municion"] * getattr(self, "mult_municion", 1.0))

    def tiempo_recarga_config(self):
        return max(1, int(self.config["recarga"] * getattr(self, "mult_recarga", 1.0)))

    def cadencia_actual(self):
        return max(1, int(self.config["cadencia"] * getattr(self, "mult_cadencia", 1.0)))

    def danio_actual(self):
        return self.config["danio"] * getattr(self, "mult_danio", 1.0)

    def nombre(self):
        return self.config["nombre"]

    def color(self):
        return self.config["color"]

    def color_borde(self):
        return self.config.get("borde", self.config["color"])

    def icono(self):
        return self.config.get("icono", "*")

    def sin_municion(self):
        return bool(self.config.get("sin_municion"))

    def cambiar_arma(self, direccion):
        # Rotar entre las cuatro armas disponibles.
        if len(self.disponibles) <= 1:
            return self.tipo
        i = self.disponibles.index(self.tipo)
        nuevo = self.disponibles[(i + direccion) % len(self.disponibles)]
        self.cambiar(nuevo)
        return self.tipo

    def seleccionar(self, indice):
        if 0 <= indice < len(self.disponibles):
            nuevo = self.disponibles[indice]
            if nuevo != self.tipo:
                self.cambiar(nuevo)
                return True
        return False

    def indice_actual(self):
        try:
            return self.disponibles.index(self.tipo)
        except ValueError:
            return 0

    def progreso_recarga(self):
        if self.recargando <= 0:
            return 0.0
        return 1.0 - self.recargando / max(1, self.recarga_total)

    def disparar(self, arena, x, y, angulo, critico=False, critico_mult=2.3):
        if self.cooldown > 0 or self.recargando > 0:
            return None
        if not self.sin_municion() and self.municion <= 0:
            self.recargando = self.tiempo_recarga_config()
            self.recarga_total = self.recargando
            return None

        # Boca del canon; si cae dentro de un muro se dispara desde el centro.
        mx = x + math.cos(angulo) * 18
        my = y + math.sin(angulo) * 18
        if not arena.punto_libre(mx, my):
            mx, my = x, y

        cfg = self.config
        disparos = []
        balas = cfg["balas"]
        dispersion = cfg["dispersion"]
        for i in range(balas):
            if balas == 1:
                extra = random.uniform(-dispersion, dispersion)
            else:
                paso = dispersion * 2 / (balas - 1)
                extra = -dispersion + paso * i + random.uniform(-paso * 0.2, paso * 0.2)
            a = angulo + extra
            danio = self.danio_actual()
            if critico:
                danio *= critico_mult
            disparos.append(
                Proyectil(
                    mx, my, a,
                    cfg["velocidad"],
                    danio,
                    cfg["radio"],
                    cfg["color"],
                    forma=cfg["forma"],
                    largo_estela=cfg["estela"],
                    perforante=cfg.get("perforante", 0),
                    rebotes=cfg.get("rebotes", 0),
                    alcance=cfg.get("alcance"),
                    color_borde=cfg.get("borde"),
                )
            )

        if not self.sin_municion():
            self.municion -= 1
        self.cooldown = self.cadencia_actual()
        if not self.sin_municion() and self.municion <= 0:
            self.recargando = self.tiempo_recarga_config()
            self.recarga_total = self.recargando
        return disparos

    def actualizar(self):
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.recargando > 0:
            self.recargando -= 1
            if self.recargando == 0:
                self.municion = self.municion_max
