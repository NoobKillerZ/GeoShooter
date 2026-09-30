# -*- coding: utf-8 -*-
"""
jugador.py
==========
Jugador del shooter cenital: movimiento con aceleracion y frenado,
apuntado con raton, disparo, dash con recarga, escudo temporal y
estelas de movimiento.
"""

import math
import random

import pygame

from armas import ArmaJugador, PASO

RADIO = 13

# Sensacion de control
ACELERACION = 2100.0   # px/s^2 al acelerar
FRENADO = 2600.0        # px/s^2 al soltar
IMPULSO_DASH = 3.4     # multiplicador de velocidad durante el dash

COL_CUERPO = (74, 152, 255)
COL_CUERPO_OSC = (46, 104, 200)
COL_CONTORNO = (18, 44, 96)
COL_CABINA = (190, 240, 255)
COL_ALA = (52, 110, 205)
COL_LAMINA = (150, 200, 255)
COL_ESCUDO = (140, 225, 255)
COL_FLAMA = (255, 190, 90)
COL_FLAMA_INT = (255, 245, 210)
COL_BRILLO = (200, 230, 255)

# Silueta plana para las estelas del dash (colorkey + alpha)
_SILUETA = None


def _silueta():
    global _SILUETA
    if _SILUETA is None:
        sup = pygame.Surface((64, 64))
        sup.fill((0, 0, 0))
        puntos = [(24, 32), (14, 22), (8, 26), (8, 38), (14, 42)]
        pygame.draw.polygon(sup, (255, 255, 255), puntos)
        pygame.draw.polygon(sup, (255, 255, 255), [(14, 32), (8, 26), (2, 30), (8, 38)])
        pygame.draw.polygon(sup, (255, 255, 255), [(14, 32), (8, 38), (2, 34), (8, 26)])
        sup.set_colorkey((0, 0, 0))
        _SILUETA = sup
    return _SILUETA


def _oscuro(color, f):
    return tuple(max(0, int(c * (1.0 - f))) for c in color)


def _claro(color, f):
    return tuple(min(255, int(c + (255 - c) * f)) for c in color)


class Jugador:
    def __init__(self, x, y, cartera=None):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.radio = RADIO
        self.angulo = 0.0
        self.velocidad = 270.0
        self.arma = ArmaJugador("pistola")
        self.invul = 0
        self.escudo = 0
        self.velocidad_bonus = 0
        self.estelas = []
        # Camara actual (la inyecta el juego principal para apuntar y dibujar).
        self.cam_x = 0.0
        self.cam_y = 0.0

        # Progresion de la partida: valores neutros hasta que se aplique.
        self.cartera = cartera
        self.dash_max = 1
        self.dash_cargas = 1
        self.dash_cd_max = 46
        self.dash_cd = 0
        self.dash_dur = 0
        self.dash_dir = (0.0, 0.0)
        self.regen = 0.0
        self.critico = 0.0
        self.critico_mult = 2.3
        self.vampiro = 0.0
        self.magnetico = 0.0
        self.segunda_vida = 0
        self.escudo_extra = 0
        self.vida = 100
        self.vida_max = 100
        # Sirve para saber si el dash ha crecido y regalar la carga nueva.
        self._mejora_dash = 0
        self.aplicar_cartera(cartera)

    def aplicar_cartera(self, cartera):
        """Toma las estadisticas de la cartera (nivel + mejoras) y las aplica."""
        if cartera is None:
            return

        vida_previa = self.vida_max
        est = cartera.estadisticas()
        self.cartera = cartera
        self.vida_max = int(est["vida_max"])
        self.velocidad = float(est["velocidad"])
        self.escudo_extra = int(est["escudo_extra"])
        self.dash_max = int(est["dash_cargas"])
        # Comprar o subir IMPULSO REACTIVO te da la carga nueva en el acto, pero
        # cualquier otra mejora no debe rellenar las que ya tenias gastadas.
        mejora_dash = cartera.nivel_mejora("dash")
        if mejora_dash > self._mejora_dash:
            self.dash_cargas = self.dash_max
        self._mejora_dash = mejora_dash
        self.dash_cargas = min(self.dash_cargas, self.dash_max)
        self.dash_cd_max = int(est["dash_cd"])
        self.regen = float(est["regen"])
        self.critico = float(est["critico"])
        self.critico_mult = float(est["critico_mult"])
        self.vampiro = float(est["vampiro"])
        self.magnetico = float(est["magnetico"])
        # La segunda vida se repone cada vez que se compra.
        if cartera.habilidad_activa("segunda"):
            self.segunda_vida = 1
        # La vida sube con la maxima si estaba llena, para que comprar vida no
        # te deje con la barra a medias, pero sin curarte en pleno combate.
        if self.vida >= vida_previa:
            self.vida = self.vida_max
        else:
            self.vida = min(self.vida, self.vida_max)
        if cartera.armas_disponibles():
            self.arma = ArmaJugador(self.arma.tipo, cartera.armas_disponibles())
        self.arma.aplicar_bonos(est["danio"], est["cadencia"], est["municion"], est["recarga"])

    def tirar_dado(self):
        """True si este disparo es critico."""
        return random.random() < self.critico

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.radio),
            int(self.y - self.radio),
            self.radio * 2,
            self.radio * 2,
        )

    def centro(self):
        return (self.x, self.y)

    def apuntar(self, mx, my):
        self.angulo = math.atan2(my - self.y, mx - self.x)

    def puede_dash(self):
        return self.dash_cargas > 0

    def dash_maximo(self):
        return self.dash_max

    def dash_usadas(self):
        return max(0, self.dash_max - self.dash_cargas)

    def intentar_dash(self, dirx, diry):
        if self.dash_cargas <= 0 or (dirx == 0 and diry == 0):
            return False
        m = math.hypot(dirx, diry)
        self.dash_dir = (dirx / m, diry / m)
        self.dash_dur = 12
        self.dash_cargas -= 1
        # La carga gastada empieza ahora su propia recarga: con esto el dash
        # no se puede volver a usar hasta pasar dash_cd_max frames.
        self.dash_cd = 0
        self.invul = max(self.invul, 14)
        # El dash lanza al jugador con velocidad propia.
        self.vx = self.dash_dir[0] * self.velocidad_actual() * 2.1
        self.vy = self.dash_dir[1] * self.velocidad_actual() * 2.1
        self.estelas = []
        return True

    def dash_fraccion(self):
        """0..1 de recarga de la siguiente carga de dash."""
        if self.dash_cargas > 0:
            return 1.0
        return min(1.0, max(0.0, self.dash_cd / max(1, self.dash_cd_max)))

    def recibir_dano(self, cantidad):
        if self.invul > 0:
            return False
        if self.escudo > 0:
            self.escudo = 0
            self.invul = 40
            return True  # absorbido, no quita vida
        self.vida -= cantidad
        self.invul = 48
        if self.vida <= 0 and self.segunda_vida > 0:
            # Segunda vida: revive con la mitad de la vida y se consume.
            self.segunda_vida -= 1
            self.vida = max(1, int(self.vida_max * 0.5))
            self.invul = 150
            return False
        return True

    def curar(self, cantidad):
        if cantidad <= 0:
            return False
        antes = self.vida
        self.vida = min(self.vida_max, self.vida + cantidad)
        return self.vida > antes

    def velocidad_actual(self):
        return self.velocidad + self.velocidad_bonus

    # ------------------------------------------------------------- update
    def actualizar(self, arena, teclas, mouse_pos):
        if self.invul > 0:
            self.invul -= 1
        if self.escudo > 0:
            self.escudo -= 1
        # Las cargas de dash se recuperan de una en una: cada carga gastada
        # necesita su propio dash_cd_max completo antes de volver.
        if self.dash_cargas < self.dash_max:
            self.dash_cd += 1
            if self.dash_cd >= self.dash_cd_max:
                self.dash_cd = 0
                self.dash_cargas += 1

        # Regeneracion: solo fuera de combate, para que no se note como unbeatable.
        if self.regen > 0 and self.vida < self.vida_max and self.dash_dur == 0:
            self.vida = min(self.vida_max, self.vida + self.regen * PASO)

        dirx, diry = 0.0, 0.0
        if teclas[pygame.K_w] or teclas[pygame.K_UP]:
            diry -= 1
        if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
            diry += 1
        if teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
            dirx -= 1
        if teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
            dirx += 1

        if self.dash_dur > 0:
            # Durante el dash manda la direccion del impulso.
            self.dash_dur -= 1
            self.vx = self.dash_dir[0] * self.velocidad_actual() * IMPULSO_DASH
            self.vy = self.dash_dir[1] * self.velocidad_actual() * IMPULSO_DASH
        else:
            velocidad = self.velocidad_actual()
            if dirx or diry:
                m = math.hypot(dirx, diry)
                objetivo_x = dirx / m * velocidad
                objetivo_y = diry / m * velocidad
                # Aceleracion limitada: nada de saltos instantaneos
                dvx = objetivo_x - self.vx
                dvy = objetivo_y - self.vy
                dm = math.hypot(dvx, dvy)
                maximo = ACELERACION * PASO
                if dm > maximo:
                    dvx = dvx / dm * maximo
                    dvy = dvy / dm * maximo
                self.vx += dvx
                self.vy += dvy
            else:
                # Frenado progresivo
                dm = math.hypot(self.vx, self.vy)
                if dm > 0:
                    nuevo = max(0.0, dm - FRENADO * PASO)
                    self.vx *= nuevo / dm
                    self.vy *= nuevo / dm

        self.x, self.y = arena.mover(self.x, self.y, self.vx * PASO, self.vy * PASO, self.radio)
        self.apuntar(mouse_pos[0] + self.cam_x, mouse_pos[1] + self.cam_y)
        self.arma.actualizar()
        self._actualizar_estelas()

    def _actualizar_estelas(self):
        if self.dash_dur > 0:
            self.estelas.append((self.x, self.y, self.angulo))
            if len(self.estelas) > 6:
                self.estelas.pop(0)
        elif self.estelas:
            self.estelas.pop(0)

    # ------------------------------------------------------------- dibujo
    def dibujar(self, pantalla, con_invul=False):
        cx = int(self.x - self.cam_x)
        cy = int(self.y - self.cam_y)
        vw, vh = pantalla.get_width(), pantalla.get_height()
        if cx < -60 or cy < -60 or cx > vw + 60 or cy > vh + 60:
            return

        self._dibujar_estelas(pantalla)

        # Sombra en el suelo
        sombra = pygame.Surface((self.radio * 2 + 6, self.radio), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 70), sombra.get_rect())
        pantalla.blit(sombra, (cx - self.radio - 3, cy + self.radio - 7))

        if con_invul:
            return

        cos_a = math.cos(self.angulo)
        sin_a = math.sin(self.angulo)

        def rot(lx, ly):
            return (cx + lx * cos_a - ly * sin_a, cy + lx * sin_a + ly * cos_a)

        # Propulsor: la llama crece con la velocidad actual
        rapidez = min(1.0, math.hypot(self.vx, self.vy) / max(1.0, self.velocidad_actual()))
        t = pygame.time.get_ticks() / 45.0
        largo = 8 + rapidez * 16 + math.sin(t) * (1.5 + rapidez * 2.5)
        if self.dash_dur > 0:
            largo *= 1.5
        llama = [rot(-12, -5), rot(-12 - largo, 0), rot(-12, 5)]
        pygame.draw.polygon(pantalla, COL_FLAMA, llama)
        pygame.draw.polygon(
            pantalla, COL_FLAMA_INT,
            [rot(-13, -2.4), rot(-12 - largo * 0.6, 0), rot(-13, 2.4)],
        )

        # Alas
        pygame.draw.polygon(pantalla, COL_ALA, [rot(2, -9), rot(-9, -15), rot(-6, -6)])
        pygame.draw.polygon(pantalla, COL_ALA, [rot(2, 9), rot(-9, 15), rot(-6, 6)])
        pygame.draw.polygon(pantalla, COL_LAMINA, [rot(1, -9), rot(-7, -13), rot(-5, -7)])
        pygame.draw.polygon(pantalla, COL_LAMINA, [rot(1, 9), rot(-7, 13), rot(-5, 7)])

        # Casco
        casco = [rot(17, 0), rot(8, -9), rot(-9, -8), rot(-12, 0), rot(-9, 8), rot(8, 9)]
        pygame.draw.polygon(pantalla, COL_CONTORNO, casco, 2)
        pygame.draw.polygon(pantalla, COL_CUERPO, casco)
        # Brillo superior
        brillo = [rot(13, 0), rot(6, -6), rot(-6, -5), rot(-6, -2), rot(6, -2)]
        pygame.draw.polygon(pantalla, COL_CUERPO_OSC, brillo)
        # Sombra inferior del casco
        sombra = [rot(-6, 2), rot(-9, 8), rot(8, 9), rot(6, 4), rot(-4, 4)]
        pygame.draw.polygon(pantalla, _oscuro(COL_CUERPO, 0.35), sombra)
        # Brillo especular
        pygame.draw.polygon(pantalla, _claro(COL_CUERPO, 0.25),
                            [rot(14, -1), rot(9, -6), rot(4, -5), rot(8, -1)])

        # Cabina
        pygame.draw.ellipse(
            pantalla, COL_CABINA,
            pygame.Rect(int(cx - 5 + cos_a * 4), int(cy - 3 + sin_a * 4), 10, 6),
        )
        # Brillo de la cabina
        pygame.draw.ellipse(
            pantalla, (255, 255, 255),
            pygame.Rect(int(cx - 3 + cos_a * 4), int(cy - 2 + sin_a * 4), 4, 2),
        )

        # Cañon
        pygame.draw.circle(pantalla, COL_CONTORNO,
                           (int(cx + cos_a * 18), int(cy + sin_a * 18)), 5)
        pygame.draw.circle(pantalla, (90, 100, 130),
                           (int(cx + cos_a * 18), int(cy + sin_a * 18)), 3)
        # Brillo del cañon
        pygame.draw.circle(pantalla, (200, 220, 255),
                           (int(cx + cos_a * 18 - 1), int(cy + sin_a * 18 - 1)), 1)

        # Escudo
        if self.escudo > 0:
            radio = self.radio + 8 + int(2 * math.sin(pygame.time.get_ticks() / 90))
            pygame.draw.circle(pantalla, COL_ESCUDO, (cx, cy), radio, 2)
            pygame.draw.circle(
                pantalla, (200, 245, 255), (cx, cy), radio, 1,
            )

    def _dibujar_estelas(self, pantalla):
        if not self.estelas:
            return
        total = len(self.estelas)
        for i, (ex, ey, ea) in enumerate(self.estelas):
            img = pygame.transform.rotate(_silueta(), -math.degrees(ea))
            img.set_alpha(int(110 * (i + 1) / total))
            pantalla.blit(
                img,
                (int(ex - self.cam_x - img.get_width() / 2),
                 int(ey - self.cam_y - img.get_height() / 2)),
            )
