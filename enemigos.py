# -*- coding: utf-8 -*-
"""
enemigos.py
===========
Enemigos del shooter cenital con IA y silueta propias por tipo.

Enemigos:
  corredor  - triangulo rapido que va directo al jugador
  tirador   - rombo que mantiene distancia y dispara
  tanque    - hexagono lento, mucha vida, empuja al jugador
  explosivo - esfera que corre y detona al acercarse
  acorazado - tanque con placa frontal: hay que flanquearlo
  mortero   - se aleja y bombardea donde cree que estas
  dron      - orbita rapido y dispara en rafagas de 3
  sabueso   - avisa y embiste en linea recta pegando mucho
  acechador - parpadea hasta la espalda del jugador
  divisorio - al morir se parte en tres germenes
  germen    - cria del divisorio: rapida y fragil

Jefes: cada uno rota 3 ataques distintos y al bajar del 50% de vida entra en
fase 2 (mas proyectiles por ataque y menos pausa entre ellos).
  jefe           SENTINELA  - abanico, espiral giratoria y pulso radial
  jefe_bastion   BASTION    - mortero, descargas dirigidas y embestida
  jefe_matriarca MATRIARCA  - invoca cria, abanicos cruzados y mordisco
  jefe_prisma    PRISMA     - haces laser giratorios, balas curvas y salto
"""

import math
import random

import pygame

from armas import Proyectil, PASO

TAU = math.tau

TIPOS = {
    "corredor": {
        "vida": 26, "vel": 190, "radio": 12, "color": (232, 74, 74), "puntos": 10,
        "danio_contacto": 10,
    },
    "tirador": {
        "vida": 42, "vel": 105, "radio": 13, "color": (246, 168, 66), "puntos": 18,
        "cadencia": 68, "distancia": 260, "danio_contacto": 10,
    },
    "tanque": {
        "vida": 120, "vel": 74, "radio": 20, "color": (162, 96, 226), "puntos": 32,
        "empuja": 150, "danio_contacto": 18,
    },
    "explosivo": {
        "vida": 20, "vel": 170, "radio": 12, "color": (250, 224, 84), "puntos": 20,
        "radio_boom": 92, "danio_boom": 26, "danio_contacto": 0,
    },
    "acorazado": {
        "vida": 165, "vel": 64, "radio": 21, "color": (96, 132, 210), "puntos": 44,
        "empuja": 195, "danio_contacto": 20,
        # Solo aguanta el frente: hay que rodearlo o pegarle por detras.
        "escudo_frontal": 0.18, "arco_escudo": 1.15,
    },
    "mortero": {
        "vida": 54, "vel": 72, "radio": 14, "color": (110, 200, 190), "puntos": 30,
        "distancia": 330, "danio_contacto": 8,
        "cadencia": 190, "bombardeo": 3, "radio_boom": 76, "danio_boom": 30,
        "aviso_boom": 78, "adelanto": 0.55,
    },
    "dron": {
        "vida": 30, "vel": 158, "radio": 11, "color": (120, 235, 255), "puntos": 22,
        "distancia": 190, "danio_contacto": 8,
        "cadencia": 150, "rafaga": 3, "paso_rafaga": 9,
    },
    "sabueso": {
        "vida": 50, "vel": 122, "radio": 13, "color": (255, 126, 60), "puntos": 28,
        "danio_contacto": 12, "danio_embestida": 30,
        "distancia": 240, "aviso_carga": 42, "frames_carga": 46, "enfriamiento": 300,
    },
    "acechador": {
        "vida": 40, "vel": 168, "radio": 12, "color": (176, 112, 255), "puntos": 26,
        "danio_contacto": 16,
        "distancia_parpadeo": 150, "cadencia_parpadeo": 210, "parpadeo": 26,
    },
    "divisorio": {
        "vida": 76, "vel": 88, "radio": 17, "color": (126, 226, 128), "puntos": 34,
        "danio_contacto": 10, "crias": ("germen", "germen", "germen"),
    },
    "germen": {
        "vida": 14, "vel": 214, "radio": 8, "color": (168, 245, 150), "puntos": 4,
        "danio_contacto": 6,
    },
    # ------------------------------------------------------------------ jefes
    "jefe": {
        "es_jefe": True, "nombre": "SENTINELA",
        "vida": 900, "vel": 84, "radio": 36, "color": (232, 64, 200), "puntos": 400,
        "empuja": 165, "danio_contacto": 24,
        "ataques": ("abanico", "espiral", "pulso"),
    },
    "jefe_bastion": {
        "es_jefe": True, "nombre": "BASTION",
        "vida": 1150, "vel": 62, "radio": 40, "color": (255, 132, 60), "puntos": 520,
        "empuja": 190, "danio_contacto": 28,
        "ataques": ("mortero", "descarga", "embestida"),
    },
    "jefe_matriarca": {
        "es_jefe": True, "nombre": "MATRIARCA",
        "vida": 1000, "vel": 96, "radio": 34, "color": (120, 235, 140), "puntos": 480,
        "danio_contacto": 22,
        "ataques": ("invocar", "abanicos", "mordisco"),
    },
    "jefe_prisma": {
        "es_jefe": True, "nombre": "PRISMA",
        "vida": 860, "vel": 78, "radio": 32, "color": (120, 220, 255), "puntos": 560,
        "danio_contacto": 20,
        "ataques": ("haces", "curva", "salto"),
    },
}

ORDEN_JEFES = ("jefe", "jefe_bastion", "jefe_matriarca", "jefe_prisma")

# Los jefes se turnan cada 3 oleadas: el 3 el primero, el 6 el segundo, ...
CADA_CUANTAS_JEFES = 3

# Las unidades grandes colisionan con un radio menor al visual para que quepan
# por los huecos y no se queden encajadas en las esquinas. El tope de 13.5 px
# es lo que cabe con holgura en un pasillo de una celda (32 px).
FACTOR_COLISION = {"tanque": 0.72, "acorazado": 0.70, "divisorio": 0.80,
                   "jefe": 0.62, "jefe_bastion": 0.60, "jefe_matriarca": 0.62,
                   "jefe_prisma": 0.62}
RADIO_COLISION_MAX = 13.5

# Suavizado del giro (rad/s aproximados)
GIRO = 9.0

# Rotacion de ataques de los jefes. Cada ataque lleva su propia recarga: uno no
# se repite hasta que han jugado los demas, que es lo que evita que un jefe se
# sienta monotono.
ATAQUES_JEFE = {
    "abanico": {"pausa": 120, "aviso": 26, "cadencia": 150},
    "espiral": {"pausa": 215, "aviso": 34, "cadencia": 320},
    "pulso": {"pausa": 185, "aviso": 40, "cadencia": 300},
    "mortero": {"pausa": 250, "aviso": 22, "cadencia": 330},
    "descarga": {"pausa": 135, "aviso": 24, "cadencia": 210},
    "embestida": {"pausa": 260, "aviso": 44, "cadencia": 360},
    "invocar": {"pausa": 300, "aviso": 30, "cadencia": 420},
    "abanicos": {"pausa": 165, "aviso": 28, "cadencia": 260},
    "mordisco": {"pausa": 240, "aviso": 36, "cadencia": 330},
    "haces": {"pausa": 245, "aviso": 52, "cadencia": 340},
    "curva": {"pausa": 150, "aviso": 30, "cadencia": 240},
    "salto": {"pausa": 230, "aviso": 34, "cadencia": 320},
}


class Aviso:
    """Zona de peligro telegrafiada: avisa antes de pegar.

    "zona" es un circulo en el suelo que explota al terminar los frames.
    "rayo" es una linea que gira sobre su origen y hace dano continuo mientras
    dure. Se dibujan bajo las unidades para que se lean de un vistazo.
    """

    ANCHO_RAYO = 13.0
    INTERVALO_RAYO = 24

    def __init__(self, x, y, radio, frames, color, dano, tipo="zona",
                 angulo=0.0, giro=0.0, largo=0.0):
        self.x = float(x)
        self.y = float(y)
        self.radio = float(radio)
        self.tipo = tipo
        self.frames = int(frames)
        self.frames_ini = max(1, int(frames))
        self.color = color
        self.dano = dano
        self.angulo = angulo
        self.giro = giro
        self.largo = float(largo)
        # Largo ya recortado por muros, cacheado desde el ultimo actualizar.
        # Lo usa el dibujo para que el haz no atraviese las paredes.
        self.largo_dibujable = self.largo
        self.exploto = False
        self._cd = 0

    def actualizar(self, arena, jugador, particulas):
        """Avanza un frame. Devuelve la lista de dano hecho al jugador."""
        danos = []
        if self.tipo == "zona":
            self.frames -= 1
            if self.frames <= 0 and not self.exploto:
                self.exploto = True
                particulas.explosion(self.x, self.y, 1.5)
                d = math.hypot(jugador.x - self.x, jugador.y - self.y)
                if d < self.radio + jugador.radio * 0.5:
                    danos.append(self.dano)
        else:
            self.angulo += self.giro
            self.frames -= 1
            largo = self._largo_libre(arena)
            self.largo_dibujable = largo
            if self._toca(jugador, largo):
                if self._cd <= 0:
                    danos.append(self.dano)
                    self._cd = self.INTERVALO_RAYO
                else:
                    self._cd -= 1
            else:
                self._cd = 0
        return danos

    def vivo(self):
        return not self.exploto and self.frames > 0

    def _largo_libre(self, arena):
        """Recorta el rayo en el primer muro: no atraviesa las paredes."""
        pasos = 14
        for i in range(1, pasos + 1):
            d = self.largo * i / pasos
            if not arena.punto_libre(self.x + math.cos(self.angulo) * d,
                                     self.y + math.sin(self.angulo) * d):
                return max(24.0, self.largo * (i - 1) / pasos)
        return self.largo

    def _toca(self, jugador, largo):
        dx = jugador.x - self.x
        dy = jugador.y - self.y
        cos_a, sin_a = math.cos(self.angulo), math.sin(self.angulo)
        perpend = abs(-dx * sin_a + dy * cos_a)
        a_lo_largo = dx * cos_a + dy * sin_a
        return (perpend < self.ANCHO_RAYO + jugador.radio
                and -jugador.radio < a_lo_largo < largo + jugador.radio)

    def dibujar(self, pantalla, cam_x, cam_y):
        px, py = int(self.x - cam_x), int(self.y - cam_y)
        if self.tipo == "zona":
            r = int(self.radio)
            if r < 2:
                return
            avance = 1.0 - max(0.0, min(1.0, self.frames / self.frames_ini))
            lado = r * 2
            capa = pygame.Surface((lado, lado), pygame.SRCALPHA)
            centro = capa.get_rect().center
            alpha = int(40 + 120 * avance)
            pygame.draw.circle(capa, (*self.color, alpha), centro, r)
            pygame.draw.circle(capa, (*self.color, min(255, alpha + 90)), centro, r, 3)
            pantalla.blit(capa, (px - r, py - r))
            # Anillo que se cierra: cuenta atras.
            cuenta = int(r * (1.0 - avance)) + 3
            if cuenta > 3:
                pygame.draw.circle(pantalla, (255, 255, 255), (px, py), cuenta, 2)
            k = int(r * 0.22) + 4
            pygame.draw.line(pantalla, self.color, (px - k, py), (px + k, py), 2)
            pygame.draw.line(pantalla, self.color, (px, py - k), (px, py + k), 2)
        else:
            if self.largo < 8:
                return
            # Se dibuja con el mismo largo recortado que usa la colision, o
            # el haz pareceria atravessar el muro.
            largo = self.largo_dibujable
            cos_a, sin_a = math.cos(self.angulo), math.sin(self.angulo)
            x1, y1 = int(px + cos_a * largo), int(py + sin_a * largo)
            avance = 1.0 - max(0.0, min(1.0, self.frames / self.frames_ini))
            ancho = max(2, int(self.ANCHO_RAYO * (0.45 + 0.55 * avance)))
            pygame.draw.line(pantalla, self.color, (px, py), (x1, y1), ancho + 8)
            pygame.draw.line(pantalla, (255, 255, 255), (px, py), (x1, y1),
                             max(1, ancho - 4))
            pygame.draw.circle(pantalla, self.color, (px, py), ancho)
            pygame.draw.circle(pantalla, (255, 255, 255), (px, py), max(2, ancho // 2))
            t = pygame.time.get_ticks() / 1000.0
            for k in range(1, 4):
                d = largo * k / 4.0
                mxp = int(px + cos_a * d)
                myp = int(py + sin_a * d)
                pygame.draw.circle(pantalla, (255, 255, 255), (mxp, myp),
                                   3 + int(2 * abs(math.sin(t * 6 + k))))


class Fragmento:
    """Trozo de enemigo que sale despedido al morir.

    Cada trozo es un poligono rigido con su propia velocidad y su propio giro.
    No usa el sistema de particulas porque este no se mueve en linea recta:
    un trozo que sale disparado y luego frena no lee como un trozo.
    """

    __slots__ = ("x", "y", "vx", "vy", "giro", "angulo", "puntos", "color",
                 "borde", "edad", "vida", "escala")

    def __init__(self, x, y, puntos, color, borde, vx, vy, vida, escala=1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.giro = random.uniform(-0.28, 0.28)
        self.angulo = 0.0
        self.puntos = puntos
        self.color = color
        self.borde = borde
        self.edad = 0
        self.vida = vida
        self.escala = escala

    def actualizar(self):
        self.edad += 1
        if self.edad >= self.vida:
            return False
        self.x += self.vx
        self.y += self.vy
        self.angulo += self.giro
        # Frena como un proyectil, no como un roce de particula: el rozamiento
        # bajo hace que el trozo derape, que es lo que da peso.
        self.vx *= 0.94
        self.vy *= 0.94
        return True

    def dibujar(self, pantalla, cam_x, cam_y):
        # Se encoge al final en vez de desvanecerse: al encogerse el ultimo
        # frame se ve como que el trozo se desintegra, no como que se apaga.
        f = 1.0 - (self.edad / self.vida) ** 4.0
        if f <= 0.05:
            return
        ca, sa = math.cos(self.angulo), math.sin(self.angulo)
        puntos = []
        for lx, ly in self.puntos:
            x = lx * f
            y = ly * f
            puntos.append((int(self.x - cam_x + x * ca - y * sa),
                           int(self.y - cam_y + x * sa + y * ca)))
        if len(puntos) < 3:
            return
        pygame.draw.polygon(pantalla, self.color, puntos)
        if f > 0.45:
            pygame.draw.polygon(pantalla, self.borde, puntos, 1)


class Enemigo:
    def __init__(self, x, y, tipo, escala=1.0):
        cfg = TIPOS[tipo]
        self.tipo = tipo
        self.cfg = cfg
        self.x = float(x)
        self.y = float(y)
        self.radio = cfg["radio"] * escala
        self.radio_colision = min(self.radio * FACTOR_COLISION.get(tipo, 1.0),
                                  RADIO_COLISION_MAX)
        self.vida_max = int(cfg["vida"] * escala)
        self.vida = self.vida_max
        self.vel = cfg["vel"] * (0.92 + 0.08 * escala)
        self.vel_base = self.vel
        self.color = cfg["color"]
        self.vivo = True
        self.cooldown = random.randint(18, 60)
        self.fase = random.uniform(0, TAU)
        self.lateral = random.choice((-1, 1))
        self.frames_atascado = 0
        self.frames_dentro = 0
        self.angulo = 0.0
        self.dirx, self.diry = 0.0, 0.0
        self.flash = 0
        # Squash: frames que le quedan deformado tras un impacto, y con que
        # fuerza. Al recibir dano se llenan los dos; se van vaciando solos.
        self.squash = 0
        self.squash_fuerza = 0.0
        self.impulso_x = 0.0
        self.impulso_y = 0.0
        self.dano_contacto = cfg.get("danio_contacto", 10)
        self.es_jefe = bool(cfg.get("es_jefe", False))
        # Estado que usa cada IA a su manera (todos en cero por defecto).
        self.carga = 0            # frames de embestida en curso
        self.carga_pendiente = 0  # frames de aviso antes de embestir
        self.frames_carga = 0     # duracion de la embestida
        self.charge_aviso_total = 0  # aviso completo, para el anillo de cuenta atras
        self.multiplicador_carga = 1.0
        self.dano_embestida = 0
        self.parpadeo = 0         # frames de teletransporte del acechador
        self.racha = 0            # disparos de la rafaga del dron
        self.escudo_golpes = 0    # frames de escudo debilitado tras un golpe
        self.marcas_ataque = 0    # frames que lleva anunciando un ataque
        # Contexto del ultimo frame, para las acciones diferidas (aterrizajes,
        # explosiones encadenadas) que aun necesitan avisar o invocar.
        self.ctx_actual = None
        if self.es_jefe:
            self.nombre = cfg.get("nombre", "JEFE")
            self.fase_jefe = 1
            self.rotacion = list(cfg["ataques"])
            self.siguiente_ataque = 0
            self.cd_ataque = 90
            self.cd_propio = {nombre: 0 for nombre in self.rotacion}
            self.preparacion = 0
            self.ataque_en_curso = None
            self.acciones = []    # [(frames, funcion)] para ataques encadenados

    @property
    def puntos(self):
        return self.cfg["puntos"]

    # ------------------------------------------------------------------ dano
    def recibir_dano(self, cantidad, angulo=None):
        if self.escudo_golpes > 0:
            self.escudo_golpes -= 1
            cantidad *= 0.6
        # El acorazado aguanta el frente: el dano entra casi entero por detras.
        frontal = self.cfg.get("escudo_frontal")
        if frontal is not None and angulo is not None:
            arco = self.cfg.get("arco_escudo", 1.15)
            # Impacto frontal = el proyectil viene en contra de su apuntado.
            diferencia = (angulo - self.angulo + math.pi) % TAU - math.pi
            if abs(diferencia) > math.pi - arco:
                cantidad *= frontal
        self.vida -= cantidad
        self.flash = 7
        # Frames que le quedan de deformacion por squash. Un jefe pesa mas y
        # se deforma menos: el mismo % en un radio de 60 px se lee como un
        # glitch, no como un impacto.
        self.squash = 7 if not self.es_jefe else 4
        self.squash_fuerza = 0.18 if not self.es_jefe else 0.10
        if angulo is not None:
            # Empujon hacia atras: los impactos se sienten.
            fuerza = 70 if not self.es_jefe else 22
            self.impulso_x -= math.cos(angulo) * fuerza
            self.impulso_y -= math.sin(angulo) * fuerza
        if self.vida <= 0:
            self.vida = 0
            self.vivo = False
            return True
        return False

    def _embestir(self, frames_aviso, frames_carga, multiplicador, dano):
        """Prepara una embestida: avisa, y luego sale disparado."""
        self.carga_pendiente = frames_aviso
        self.charge_aviso_total = frames_aviso
        self.frames_carga = frames_carga
        self.multiplicador_carga = multiplicador
        self.dano_embestida = dano

    def _al_terminar_carga(self):
        """La embestida se acaba: vuelve a su velocidad y dano normales."""
        self.vel = self.vel_base
        self.dano_contacto = self.cfg.get("danio_contacto", 10)
        self.carga = 0
        self.carga_pendiente = 0
        self.charge_aviso_total = 0

    # ------------------------------------------------------------------ IA
    def actualizar(self, arena, jugador, proyectiles, particulas, campo=None, ctx=None):
        if not self.vivo:
            return
        cfg = self.cfg
        # Se guarda para las acciones diferidas de esta vuelta.
        self.ctx_actual = ctx
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.flash > 0:
            self.flash -= 1
        if self.squash > 0:
            self.squash -= 1
        if self.escudo_golpes > 0:
            self.escudo_golpes -= 1
        if self.parpadeo > 0:
            self.parpadeo -= 1
        if self.marcas_ataque > 0 and not (self.es_jefe and self.ataque_en_curso):
            self.marcas_ataque -= 1
        # Ciclo de la embestida: aviso -> carrera -> fin.
        if self.carga_pendiente > 0:
            self.carga_pendiente -= 1
            if self.carga_pendiente == 0:
                self.carga = self.frames_carga
                self.vel = self.vel_base * self.multiplicador_carga
                self.dano_contacto = self.dano_embestida
        if self.carga > 0:
            self.carga -= 1
            if self.carga == 0:
                if self.tipo == "jefe_bastion":
                    # El bastion no se va sin dejar huella: onda al frenar.
                    particulas.explosion(self.x, self.y, 2.0)
                    proyectiles.append(
                        Proyectil(self.x, self.y, random.uniform(0, TAU), 300, 12, 9,
                                  (255, 150, 90), hostil=True, forma="onda",
                                  largo_estela=8, dano_jugador=18, alcance=44)
                    )
                self._al_terminar_carga()

        dx = jugador.x - self.x
        dy = jugador.y - self.y
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist

        # Mirar siempre al jugador (giro suave)
        objetivo_angulo = math.atan2(dy, dx)
        diferencia = (objetivo_angulo - self.angulo + math.pi) % TAU - math.pi
        self.angulo += max(-GIRO * PASO, min(GIRO * PASO, diferencia))

        # Ruta: el campo de flujo permite rodear muros en vez de encajarse.
        dirx, diry = ux, uy
        if campo:
            fx, fy = arena.direccion_campo(campo, self.x, self.y)
            if fx or fy:
                dirx, diry = fx, fy

        vx = vy = 0.0
        empuje = 0.0

        if self.tipo == "corredor":
            wob = math.sin(self.fase) * 0.28
            self.fase += 0.14
            vx = dirx + (-diry) * wob
            vy = diry + dirx * wob

        elif self.tipo == "tirador":
            objetivo = cfg["distancia"]
            if dist > objetivo + 45:
                vx, vy = dirx, diry
            elif dist < objetivo - 45:
                vx, vy = -dirx, -diry
            else:
                vx, vy = -diry * self.lateral, dirx * self.lateral
            if self.cooldown <= 0 and arena.linea_libre(self.x, self.y, jugador.x, jugador.y):
                a = math.atan2(dy, dx)
                proyectiles.append(
                    Proyectil(self.x, self.y, a, 340, 12, 5, (250, 170, 90),
                              hostil=True, forma="bala", largo_estela=4)
                )
                particulas.destello_disparo(self.x, self.y, a)
                self.cooldown = cfg["cadencia"]

        elif self.tipo == "tanque":
            if dist > 90:
                vx, vy = dirx, diry
            else:
                # Contacto: embiste en linea recta pero roza en arco, para
                # quedarse pegado como una pared que solo empuja.
                roce = 0.55 + 0.25 * math.sin(self.fase * 0.06)
                self.fase += 0.05
                vx = ux * roce - uy * self.lateral * 0.75
                vy = uy * roce + ux * self.lateral * 0.75
            empuje = cfg.get("empuja", 0)

        elif self.tipo == "explosivo":
            vx, vy = dirx, diry

        elif self.tipo == "acorazado":
            # Placa frontal: avanza de frente, sin esquivar, con el escudo
            # puesto. Rodearlo es la unica forma de pegarle fuerte.
            if dist > 100:
                vx, vy = dirx, diry
            else:
                roce = 0.40 + 0.20 * math.sin(self.fase * 0.05)
                self.fase += 0.05
                vx = ux * roce - uy * self.lateral * 0.5
                vy = uy * roce + ux * self.lateral * 0.5
            empuje = cfg.get("empuja", 0)

        elif self.tipo == "mortero":
            # Se keeps lejos y bombardea donde cree que vas a estar.
            objetivo = cfg["distancia"]
            if dist < objetivo - 40:
                vx, vy = -dirx, -diry
            elif dist > objetivo + 60:
                vx, vy = dirx, diry
            else:
                vx, vy = -diry * self.lateral, dirx * self.lateral
            if self.cooldown <= 0:
                self.cooldown = cfg["cadencia"]
                self._bombardear(arena, jugador, ctx)
            empuje = 0

        elif self.tipo == "dron":
            objetivo = cfg["distancia"]
            if dist > objetivo + 40:
                vx, vy = dirx, diry
            elif dist < objetivo - 40:
                vx, vy = -dirx, -diry
            else:
                vx, vy = -diry * self.lateral, dirx * self.lateral
            self.fase += 0.16
            if self.cooldown <= 0:
                # Rafaga de 3 disparos seguidos, luego respira.
                self.racha = 1 if self.racha >= cfg["rafaga"] else self.racha + 1
                self.cooldown = (cfg["paso_rafaga"] if self.racha < cfg["rafaga"]
                                 else cfg["cadencia"])
                a = math.atan2(dy, dx)
                proyectiles.append(
                    Proyectil(self.x, self.y, a, 380, 12, 4, (150, 240, 255),
                              hostil=True, forma="traza", largo_estela=3,
                              dano_jugador=9)
                )
                particulas.destello_disparo(self.x, self.y, a)

        elif self.tipo == "sabueso":
            if self.carga > 0:
                # Embestida: va recta y ya. El aviso previo es lo que la
                # hace honorable.
                vx, vy = math.cos(self.angulo), math.sin(self.angulo)
            elif self.carga_pendiente > 0:
                vx = vy = 0.0  # se queda quieto anunciandose
            elif dist > cfg["distancia"] + 40:
                vx, vy = dirx, diry
            elif dist < cfg["distancia"] - 60:
                vx, vy = -dirx, -diry
            else:
                vx, vy = -diry * self.lateral, dirx * self.lateral
            if (self.cooldown <= 0 and self.carga == 0 and self.carga_pendiente == 0
                    and arena.linea_libre(self.x, self.y, jugador.x, jugador.y)):
                self.cooldown = cfg["enfriamiento"]
                self._embestir(cfg["aviso_carga"], cfg["frames_carga"], 4.2,
                               cfg["danio_embestida"])
                self.marcas_ataque = cfg["aviso_carga"]
            empuje = 0

        elif self.tipo == "acechador":
            if self.parpadeo > 0:
                vx = vy = 0.0
                if self.parpadeo == 1:
                    self._aparecer(arena, jugador, particulas)
            else:
                vx, vy = dirx, diry
                if self.cooldown <= 0:
                    self.cooldown = cfg["cadencia_parpadeo"]
                    if (dist > cfg["distancia_parpadeo"]
                            or not arena.linea_libre(self.x, self.y, jugador.x, jugador.y)):
                        self.parpadeo = cfg["parpadeo"]
                        vx = vy = 0.0
                        particulas.anillo(self.x, self.y, self.color, self.radio * 2,
                                          vida=14)

        elif self.tipo == "divisorio":
            if dist > 110:
                vx, vy = dirx, diry
            else:
                roce = 0.5 * self.lateral
                vx = ux * 0.5 - uy * roce
                vy = uy * 0.5 + ux * roce
                self.fase += 0.06

        elif self.tipo == "germen":
            wob = math.sin(self.fase * 1.6) * 0.4
            self.fase += 0.24
            vx = dirx + (-diry) * wob
            vy = diry + dirx * wob

        else:  # jefes
            vx, vy, empuje = self._ia_jefe(arena, jugador, proyectiles, particulas,
                                           ctx, dist, ux, uy)

        # Suavizar la direccion para que las giros no sean secos
        f = min(1.0, 9.0 * PASO)
        self.dirx += (vx - self.dirx) * f
        self.diry += (vy - self.diry) * f

        # Movimiento con deslizamiento por paredes.
        antes_x, antes_y = self.x, self.y
        paso_x = self.dirx * self.vel * PASO
        paso_y = self.diry * self.vel * PASO
        dentro = arena.celda_bloqueada(*arena.celda_de(self.x, self.y))
        if dentro:
            # Empujado dentro de un muro: sale flotando hasta una celda libre.
            self.frames_dentro += 1
            self.x += paso_x
            self.y += paso_y
            if self.frames_dentro > 20:
                # Red de seguridad: al centro de la celda libre mas cercana.
                self.x, self.y = arena.centrar(self.x, self.y, self.radio_colision)
                self.frames_dentro = 0
            self.frames_atascado = 0
        else:
            self.frames_dentro = 0
            self.x, self.y = arena.mover(
                self.x, self.y, paso_x, paso_y, self.radio_colision
            )
            movido = abs(self.x - antes_x) + abs(self.y - antes_y)

            # Escape de atasco: lleva rato sin avanzar, prueba en perpendicular
            # y, si aun asi no sale, se recentra en su celda. El radio nunca
            # se reduce: colisionarlo con menos radio dejaba unidades metidas
            # dentro de los muros.
            if (paso_x or paso_y) and movido < 0.2:
                self.frames_atascado += 1
                if self.frames_atascado == 10:
                    self.lateral = -self.lateral
                    self.x, self.y = arena.mover(
                        self.x, self.y, -paso_y, paso_x, self.radio_colision
                    )
                elif self.frames_atascado >= 40:
                    self.x, self.y = arena.centrar(self.x, self.y, self.radio_colision)
                    self.frames_atascado = 0
                    self.lateral = random.choice((-1, 1))
            else:
                self.frames_atascado = 0

        # Empujon por impactos recibidos
        if self.impulso_x or self.impulso_y:
            self.x, self.y = arena.mover(
                self.x, self.y,
                self.impulso_x * PASO, self.impulso_y * PASO,
                self.radio_colision,
            )
            self.impulso_x *= 0.86
            self.impulso_y *= 0.86
            if abs(self.impulso_x) < 0.5 and abs(self.impulso_y) < 0.5:
                self.impulso_x = self.impulso_y = 0.0

        # Empuje fisico (tanques y jefes): pasa por la colision para no meter
        # al jugador dentro de un muro.
        if empuje and dist < self.radio + jugador.radio + 6:
            jugador.x, jugador.y = arena.mover(
                jugador.x, jugador.y, ux * empuje * PASO, uy * empuje * PASO,
                jugador.radio,
            )

        # El explosivo detona al acercarse.
        if self.tipo == "explosivo" and dist < cfg["radio_boom"] * 0.55:
            self.explodir(jugador, particulas)

    # -------------------------------------------------------- enemigos nuevos
    def _bombardear(self, arena, jugador, ctx):
        """El mortero marca tres zonas y las detona a la vez."""
        cfg = self.cfg
        if ctx is None:
            return
        # Prediccion: por delante de donde va el jugador ahora mismo.
        pj = cfg["adelanto"]
        px = jugador.x + jugador.vx * pj
        py = jugador.y + jugador.vy * pj
        base = math.atan2(py - self.y, px - self.x)
        for k in range(cfg["bombardeo"]):
            a = base + (k - (cfg["bombardeo"] - 1) / 2) * 0.45
            d = 210 + 34 * k
            bx = self.x + math.cos(a) * d
            by = self.y + math.sin(a) * d
            if not arena.circulo_libre(bx, by, 6):
                bx, by = px, py
            ctx.avisar(bx, by, cfg["radio_boom"], cfg["aviso_boom"],
                       (255, 120, 90), cfg["danio_boom"])

    def _aparecer(self, arena, jugador, particulas):
        """El acechador se materializa pegado al jugador, en un punto libre."""
        angulo = random.uniform(0, TAU)
        for _ in range(8):
            d = self.radio + jugador.radio + 14
            nx = jugador.x + math.cos(angulo) * d
            ny = jugador.y + math.sin(angulo) * d
            if arena.circulo_libre(nx, ny, self.radio_colision):
                self.x, self.y = nx, ny
                break
            angulo += TAU / 8
        else:
            return
        self.angulo = math.atan2(jugador.y - self.y, jugador.x - self.x)
        self.impulso_x = self.impulso_y = 0.0
        particulas.anillo(self.x, self.y, (255, 220, 255), self.radio * 2.4, vida=18)

    def explodir(self, jugador, particulas):
        cfg = self.cfg
        particulas.explosion(self.x, self.y, 1.4)
        d = math.hypot(jugador.x - self.x, jugador.y - self.y)
        if d < cfg["radio_boom"]:
            jugador.recibir_dano(cfg["danio_boom"])
        self.vivo = False
        self.vida = 0

    # ------------------------------------------------------------------ jefes
    def _ia_jefe(self, arena, jugador, proyectiles, particulas, ctx,
                 dist, ux, uy):
        """Rotacion de ataques y fases. El movimiento es propio de cada jefe."""
        cfg = self.cfg
        vx = vy = 0.0
        empuje = cfg.get("empuja", 0)

        # Cambio de fase al bajar del 50%: mas presion y menos respiro.
        if self.fase_jefe == 1 and self.vida <= self.vida_max * 0.5:
            self.fase_jefe = 2
            self.cd_ataque = 20
            for nombre in self.cd_propio:
                self.cd_propio[nombre] = 0
            particulas.anillo(self.x, self.y, self.color, self.radio * 6, vida=40)
            particulas.explosion(self.x, self.y, 1.6)

        # Acciones encadenadas de los ataques largos (espirales, etc).
        if self.acciones:
            pendientes = []
            for frames, funcion in self.acciones:
                frames -= 1
                if frames <= 0:
                    funcion()
                else:
                    pendientes.append((frames, funcion))
            self.acciones = pendientes

        # Aviso del ataque en curso: al terminarse, se ejecuta.
        if self.preparacion > 0:
            self.preparacion -= 1
            if self.preparacion == 0:
                self._ejecutar_ataque(arena, jugador, proyectiles, particulas, ctx)
                self.marcas_ataque = 0
                self.ataque_en_curso = None

        # Elegir el siguiente ataque cuando toca.
        if self.preparacion == 0 and self.ataque_en_curso is None:
            if self.cd_ataque > 0:
                self.cd_ataque -= 1
            # La recarga de cada ataque baja siempre. Sin esto, la rotacion
            # se quedaria con los tres en recarga y el jefe se volveria inerte.
            for nombre in self.cd_propio:
                if self.cd_propio[nombre] > 0:
                    self.cd_propio[nombre] -= 1
            if self.cd_ataque == 0:
                self._elegir_ataque()

        # Movimiento especifico de cada jefe. Las cargas mandan sobre todo lo
        # demas: si esta embistiendo, va recta; si esta avisando, se planta.
        if self.carga > 0:
            vx, vy = math.cos(self.angulo), math.sin(self.angulo)
        elif self.carga_pendiente > 0:
            vx = vy = 0.0
        elif self.tipo == "jefe":
            if dist > 210:
                vx, vy = ux, uy
            else:
                vx, vy = -uy * self.lateral, ux * self.lateral
        elif self.tipo == "jefe_bastion":
            # Pesado y lento: se planta y solo gira. La embestida es aparte.
            if dist > 300:
                vx, vy = ux, uy
            elif dist < 200:
                vx, vy = -ux, -uy
            else:
                vx, vy = -uy * self.lateral, ux * self.lateral
        elif self.tipo == "jefe_matriarca":
            # Huye del jugador y llama a sus crias. No quiere cuerpo a cuerpo.
            if dist < 260:
                vx, vy = -ux, -uy
            elif dist > 340:
                vx, vy = ux, uy
            else:
                vx, vy = -uy * self.lateral, ux * self.lateral
        else:  # jefe_prisma
            objetivo = 230
            if dist > objetivo + 60:
                vx, vy = ux, uy
            elif dist < objetivo - 60:
                vx, vy = -ux, -uy
            else:
                vx, vy = -uy * self.lateral, ux * self.lateral
        return vx, vy, empuje

    def _elegir_ataque(self):
        """Siguiente ataque de la rotacion que tenga la recarga lista."""
        for _ in range(len(self.rotacion)):
            nombre = self.rotacion[self.siguiente_ataque % len(self.rotacion)]
            self.siguiente_ataque += 1
            if self.cd_propio.get(nombre, 0) > 0:
                continue
            cfg = ATAQUES_JEFE[nombre]
            rapido = 0.72 if self.fase_jefe == 2 else 1.0
            self.cd_ataque = int(cfg["pausa"] * rapido)
            self.cd_propio[nombre] = int(cfg["cadencia"] * (0.75 if self.fase_jefe == 2 else 1.0))
            self.ataque_en_curso = nombre
            self.preparacion = cfg["aviso"]
            # El aviso se ve: aro blanco mientras se prepara el ataque.
            self.marcas_ataque = cfg["aviso"]
            return
        # Todos ocupados: se reintenta en un momento.
        self.cd_ataque = 30

    def _ejecutar_ataque(self, arena, jugador, proyectiles, particulas, ctx):
        metodo = getattr(self, "_atq_" + self.ataque_en_curso, None)
        if metodo is not None:
            metodo(arena, jugador, proyectiles, particulas, ctx)

    def _cuantas(self, base, extra):
        """Cuantas balas por ataque: mas si esta en fase 2."""
        return base + (extra if self.fase_jefe == 2 else 0)

    def _balas(self, proyectiles, particulas, angulo, cantidad, separacion,
               velocidad, color, radio, dano_jugador, forma="orbita", gira=0.0,
               alcance=None):
        for k in range(cantidad):
            a = angulo + (k - (cantidad - 1) / 2) * separacion
            proyectiles.append(
                Proyectil(self.x, self.y, a, velocidad, 12, radio, color,
                          hostil=True, forma=forma, largo_estela=6,
                          dano_jugador=dano_jugador, gira=gira, alcance=alcance)
            )
        particulas.destello_disparo(self.x, self.y, angulo)

    def _anillo(self, proyectiles, particulas, cantidad, velocidad, color,
                radio, dano_jugador, forma="orbita", gira=0.0):
        for k in range(cantidad):
            a = self.fase + k * TAU / cantidad
            proyectiles.append(
                Proyectil(self.x, self.y, a, velocidad, 12, radio, color,
                          hostil=True, forma=forma, largo_estela=6,
                          dano_jugador=dano_jugador, gira=gira)
            )
        particulas.destello_disparo(self.x, self.y, self.angulo)

    # --- SENTINELA ----------------------------------------------------------
    def _atq_abanico(self, arena, jugador, proyectiles, particulas, ctx):
        self._balas(proyectiles, particulas, self.angulo, self._cuantas(7, 3),
                    0.20, 320, (240, 110, 220), 6, 12)

    def _atq_espiral(self, arena, jugador, proyectiles, particulas, ctx):
        """Brazos que giran sobre si mismos: hay que buscar el hueco."""
        brazos = 4 + (1 if self.fase_jefe == 2 else 0)
        for k in range(brazos):
            self.acciones.append(
                (k * 7, lambda k=k, b=brazos: self._pulsito_espira(proyectiles,
                                                                  particulas, k, b))
            )
            proyectiles.append(
                Proyectil(self.x, self.y, k * TAU / brazos, 210, 12, 5,
                          (255, 140, 245), hostil=True, forma="espiral",
                          largo_estela=7, dano_jugador=11,
                          gira=0.055 * (1 if k % 2 == 0 else -1), alcance=150)
            )

    def _pulsito_espira(self, proyectiles, particulas, k, brazos):
        self._anillo(proyectiles, particulas, 2, 175, (200, 110, 255), 4, 9,
                     forma="espiral", gira=0.05 * (1 if k % 2 == 0 else -1))

    def _atq_pulso(self, arena, jugador, proyectiles, particulas, ctx):
        """Aro denso en todas direcciones: solo esquivable alejandote."""
        n = self._cuantas(16, 6)
        self._anillo(proyectiles, particulas, n, 250, (250, 90, 210), 5, 13)
        if self.fase_jefe == 2:
            # Segunda oleada girada: deja menos huecos por donde pasar.
            mitad = max(2, n // 2)
            for k in range(mitad):
                a = self.fase + (k + 0.5) * TAU / mitad
                proyectiles.append(
                    Proyectil(self.x, self.y, a, 190, 12, 4, (255, 150, 235),
                              hostil=True, forma="orbita", largo_estela=5,
                              dano_jugador=9)
                )

    # --- BASTION ------------------------------------------------------------
    def _atq_mortero(self, arena, jugador, proyectiles, particulas, ctx):
        """Bombardeo en area: avisa tres puntos y estalla todo a la vez."""
        if ctx is None:
            self._balas(proyectiles, particulas, self.angulo, 3, 0.30, 300,
                        (255, 150, 80), 7, 14)
            return
        n = self._cuantas(3, 2)
        for k in range(n):
            a = self.angulo + (k - (n - 1) / 2) * 0.55
            d = 240 + 60 * k
            bx, by = self.x + math.cos(a) * d, self.y + math.sin(a) * d
            if not arena.circulo_libre(bx, by, 8):
                bx, by = jugador.x, jugador.y
            ctx.avisar(bx, by, 78, 74, (255, 130, 70), 30)

    def _atq_descarga(self, arena, jugador, proyectiles, particulas, ctx):
        """Disparos rapidos al jugador, con dispersion pequena."""
        for _ in range(self._cuantas(3, 2)):
            proyectiles.append(
                Proyectil(self.x, self.y, self.angulo + random.uniform(-0.09, 0.09),
                          520, 12, 6, (255, 200, 120), hostil=True, forma="rayo",
                          largo_estela=9, dano_jugador=15)
            )
        particulas.destello_disparo(self.x, self.y, self.angulo)

    def _atq_embestida(self, arena, jugador, proyectiles, particulas, ctx):
        """Arranca hacia el jugador. Al frenar, sacude el sitio."""
        self._embestir(30, 40, 4.4, 34)
        # El aviso de la carga lo dibuja el marco comun de jefe, asi que no
        # hace falta tocar marcas_ataque (que ademas se limpia al ejecutar).

    # --- MATRIARCA ----------------------------------------------------------
    def _atq_invocar(self, arena, jugador, proyectiles, particulas, ctx):
        if ctx is None:
            return
        # Cuenta cualquier minion, no solo los que ella llama: un divisorio
        # invocado vale por tres germenes al partirse, asi que contar solo
        # germen y corredor dejaba que la sala se llenase de cria.
        vivos = sum(1 for e in ctx.enemigos if e.vivo and not e.es_jefe)
        if vivos >= 8:
            return  # ya hay suficiente jaleo
        tipos = ("germen", "germen", "corredor", "divisorio")
        for k in range(3):
            a = k * TAU / 3 + self.fase
            d = self.radio + 36
            nx, ny = self.x + math.cos(a) * d, self.y + math.sin(a) * d
            if arena.circulo_libre(nx, ny, 6):
                ctx.invocar(tipos[(vivos + k) % len(tipos)], nx, ny)
        particulas.anillo(self.x, self.y, (150, 255, 170), self.radio * 3, vida=26)

    def _atq_abanicos(self, arena, jugador, proyectiles, particulas, ctx):
        """Dos abanicos cruzados que giran en sentidos opuestos."""
        n = self._cuantas(5, 2)
        self._balas(proyectiles, particulas, self.angulo, n, 0.26, 300,
                    (150, 255, 180), 5, 11)
        self._balas(proyectiles, particulas, self.angulo + math.pi / 2, n, 0.26,
                    300, (90, 210, 140), 5, 11)

    def _atq_mordisco(self, arena, jugador, proyectiles, particulas, ctx):
        """Se lanza encima y suelta un aro al llegar."""
        self._embestir(26, 34, 4.0, 26)
        # Al aterrizar deja un aro: el mordisco avisa al suelo tambien.
        self.acciones.append((self.frames_carga, self._aterrizaje))

    def _aterrizaje(self):
        """Zona de dano en el punto donde cae la matriarca."""
        if self.ctx_actual is not None:
            self.ctx_actual.avisar(self.x, self.y, 82, 26, (150, 255, 170), 22)
        self.vel = self.vel_base
        self.dano_contacto = self.cfg.get("danio_contacto", 10)
        self.carga = 0
        self.carga_pendiente = 0
        self.charge_aviso_total = 0

    # --- PRISMA -------------------------------------------------------------
    def _atq_haces(self, arena, jugador, proyectiles, particulas, ctx):
        """Dos haces que barren la sala girando. Se ven venir."""
        if ctx is None:
            return
        base = math.atan2(jugador.y - self.y, jugador.x - self.x)
        for k in range(2):
            ctx.avisar(self.x, self.y, 0, 320, (150, 240, 255), 13,
                       tipo="rayo", angulo=base + k * math.pi / 2,
                       giro=0.012 * (1 if k == 0 else -1), largo=300)

    def _atq_curva(self, arena, jugador, proyectiles, particulas, ctx):
        """Balas que giran sobre si mismas y acaban volviendo a por ti."""
        n = self._cuantas(10, 4)
        for k in range(n):
            a = self.angulo + (k - (n - 1) / 2) * 0.34
            proyectiles.append(
                Proyectil(self.x, self.y, a, 250, 12, 5, (170, 250, 255),
                          hostil=True, forma="espiral", largo_estela=6,
                          dano_jugador=12, gira=-0.045, alcance=170)
            )
        particulas.destello_disparo(self.x, self.y, self.angulo)

    def _atq_salto(self, arena, jugador, proyectiles, particulas, ctx):
        """Se teletransporta junto al jugador dejando una onda donde estaba."""
        proyectiles.append(
            Proyectil(self.x, self.y, random.uniform(0, TAU), 260, 12, 9,
                      (200, 250, 255), hostil=True, forma="onda", largo_estela=8,
                      dano_jugador=16, alcance=40)
        )
        particulas.anillo(self.x, self.y, (170, 245, 255), 60, vida=26)
        self.fase += 0.7
        nuevo = self._buscar_lugar_junto(arena, jugador)
        if nuevo is not None:
            particulas.anillo(nuevo[0], nuevo[1], (255, 255, 255), 46, vida=22)
            self.x, self.y = nuevo
            self.impulso_x = self.impulso_y = 0.0

    def _buscar_lugar_junto(self, arena, jugador):
        base = math.atan2(self.y - jugador.y, self.x - jugador.x)
        for k in range(10):
            a = base + (k - 5) * 0.22
            d = self.radio + jugador.radio + 120
            nx = jugador.x + math.cos(a) * d
            ny = jugador.y + math.sin(a) * d
            if arena.circulo_libre(nx, ny, self.radio_colision):
                return nx, ny
        return None

    # ---------------------------------------------------------------- dibujo
    def dibujar(self, pantalla, cam_x, cam_y):
        px = int(self.x - cam_x)
        py = int(self.y - cam_y)
        vw, vh = pantalla.get_width(), pantalla.get_height()
        if px < -80 or py < -80 or px > vw + 80 or py > vh + 80:
            return
        r = int(self.radio)
        blanco = self.flash > 0
        cuerpo = (255, 240, 240) if blanco else self.color
        borde = (255, 255, 255) if blanco else _oscuro(self.color, 0.45)
        brillo = (255, 255, 255) if blanco else _claro(self.color, 0.45)
        t = pygame.time.get_ticks() / 1000.0

        # Sombra
        sombra = pygame.Surface((r * 2, max(4, r)), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 75), sombra.get_rect())
        pantalla.blit(sombra, (px - r, py + r - 6))

        metodo = getattr(self, "_dib_" + self.tipo, None)
        if metodo is None:
            metodo = self._dibujar_jefe

        # Squash: tras recibir un impacto el enemigo se deforma un poco y
        # vuelve a su forma. Los 12 metodos _dib_ dibujan circulos con pygame
        # y el radio de un circulo no admite escala por eje, asi que en vez de
        # reescribir los 55 draw.circle se dibuja el enemigo a una superficie
        # suelta y se blitea ya escalada.
        #
        # Se usa pygame.transform.scale y no smoothscale porque la diferencia
        # se ve solo en los bordes y no compensa: 1.22 ms frente a 2.01 ms con
        # los 28 enemigos reaccionando a la vez.
        if self.squash > 0 and self.squash_fuerza > 0.0:
            d = min(1.0, self.squash / 7.0) * self.squash_fuerza
            sx = 1.0 + d
            sy = 1.0 - d * 0.78
            # Margen holgado: el jefe dibuja anillos a r*1.45 y el corredor
            # una aleta a r*1.25. Sin esto esas partes se cortarian.
            box = int(r * 3.2) + 4
            sup = pygame.Surface((box * 2, box * 2), pygame.SRCALPHA)
            metodo(sup, box, box, r, cuerpo, borde, brillo, t)
            w = max(1, int(box * 2 * sx))
            h = max(1, int(box * 2 * sy))
            pantalla.blit(pygame.transform.scale(sup, (w, h)),
                          (px - w // 2, py - h // 2))
        else:
            metodo(pantalla, px, py, r, cuerpo, borde, brillo, t)

        # Barra de vida (los jefes la llevan en el HUD, no encima)
        if self.vida < self.vida_max and not self.es_jefe:
            w = r * 2
            by = py - r - 10
            pygame.draw.rect(pantalla, (18, 18, 24), (px - w // 2 - 1, by - 1, w + 2, 7),
                             border_radius=3)
            frac = max(0.0, self.vida / self.vida_max)
            color = (250, 90, 90) if frac > 0.35 else (250, 190, 80)
            pygame.draw.rect(pantalla, color, (px - w // 2, by, int(w * frac), 5),
                             border_radius=2)

    def _dib_corredor(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Flecha apuntando al jugador
        self._poligono(pantalla, px, py, [
            (r + 2, 0), (-r * 0.6, -r * 0.85), (-r * 0.15, 0), (-r * 0.6, r * 0.85)
        ], cuerpo, borde)
        self._poligono(pantalla, px, py, [
            (r * 0.45, 0), (-r * 0.1, -r * 0.32), (-r * 0.1, r * 0.32)
        ], brillo)
        # Aleta trasera
        self._poligono(pantalla, px, py, [
            (-r * 0.5, 0), (-r * 1.25, -r * 0.5), (-r * 1.05, 0), (-r * 1.25, r * 0.5)
        ], _oscuro(cuerpo, 0.25), borde)
        # Brillo especular
        self._poligono(pantalla, px, py, [
            (r * 0.7, -r * 0.2), (r * 0.2, -r * 0.5), (-r * 0.2, -r * 0.4)
        ], _claro(cuerpo, 0.3))

    def _dib_tirador(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Rombo con canon y mira
        self._rombo(pantalla, px, py, r, cuerpo, borde)
        self._poligono(pantalla, px, py, [
            (r + 9, 0), (r * 0.2, -r * 0.22), (r * 0.2, r * 0.22)
        ], _oscuro(cuerpo, 0.35), borde)
        pygame.draw.circle(pantalla, brillo, (px, py), max(2, r // 4))
        pygame.draw.circle(pantalla, (255, 255, 255), (px, py), max(1, r // 6))
        # Brillo del rombo
        self._poligono(pantalla, px, py, [
            (0, -r * 0.5), (r * 0.4, 0), (0, r * 0.1), (-r * 0.3, -r * 0.1)
        ], _claro(cuerpo, 0.25))

    def _dib_tanque(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        puntos = [(math.cos(a) * r, math.sin(a) * r)
                  for a in (0, math.pi / 3, 2 * math.pi / 3, math.pi,
                            4 * math.pi / 3, 5 * math.pi / 3)]
        self._poligono(pantalla, px, py, puntos, cuerpo, borde, 3)
        interior = [(x * 0.55, y * 0.55) for x, y in puntos]
        self._poligono(pantalla, px, py, interior, _oscuro(cuerpo, 0.2), brillo, 1)
        for signo in (-1, 1):
            self._poligono(pantalla, px, py, [
                (r * 0.35, signo * r * 0.35), (-r * 0.15, signo * r * 0.8),
                (r * -0.6, signo * r * 0.45),
            ], _oscuro(cuerpo, 0.3), borde, 1)
        pygame.draw.circle(pantalla, brillo, (px, py), max(2, r // 5))
        # Brillo superior del hexagono
        self._poligono(pantalla, px, py, [
            (0, -r * 0.7), (r * 0.5, -r * 0.35), (0, -r * 0.2), (-r * 0.4, -r * 0.3)
        ], _claro(cuerpo, 0.3))

    def _dib_acorazado(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        self._dib_tanque(pantalla, px, py, r, cuerpo, borde, brillo, t)
        # Placa frontal: solo aguanta ese arco, y se ve shining.
        self._arco_escudo(pantalla, px, py, r * 1.35,
                          self.cfg.get("arco_escudo", 1.15), t)

    def _dib_explosivo(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Esfera con pulso de aviso
        pulso = r + int(4 + 3 * math.sin(self.fase * 0.35 + t * 6))
        pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.45), (px, py), pulso, 2)
        pygame.draw.circle(pantalla, cuerpo, (px, py), r)
        pygame.draw.circle(pantalla, brillo, (px, py), int(r * 0.55))
        pygame.draw.circle(pantalla, (255, 90, 60),
                           (px, py - r - 3), 2 + int(1.5 * abs(math.sin(t * 9))))
        # Brillo especular
        pygame.draw.circle(pantalla, _claro(cuerpo, 0.4),
                           (int(px - r * 0.3), int(py - r * 0.3)), max(2, r // 5))

    def _dib_mortero(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Base fija con tubo largo orientado al objetivo.
        pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.3), (px, py), r, 3)
        pygame.draw.circle(pantalla, cuerpo, (px, py), int(r * 0.8))
        self._poligono(pantalla, px, py, [
            (r * 1.9, 0), (r * 0.3, -r * 0.38), (r * 0.3, r * 0.38)
        ], _oscuro(cuerpo, 0.2), borde, 2)
        pygame.draw.circle(pantalla, brillo, (px, py), max(2, r // 4))
        # Se avisa antes de bombardear: aro rojo aprieta mientras carga.
        if self.cooldown > self.cfg["cadencia"] - 40:
            pygame.draw.circle(pantalla, (255, 120, 90), (px, py), r + 6, 2)

    def _dib_dron(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Carcasa con tres saturaciones girando
        pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.4), (px, py), r)
        pygame.draw.circle(pantalla, cuerpo, (px, py), r, 2)
        for k in range(3):
            a = t * 4.0 + k * TAU / 3
            sx = int(px + math.cos(a) * r * 1.25)
            sy = int(py + math.sin(a) * r * 1.25)
            pygame.draw.circle(pantalla, brillo, (sx, sy), 3)
        pygame.draw.circle(pantalla, (255, 255, 255), (px, py), max(2, r // 3))
        # Brillo del dron
        pygame.draw.circle(pantalla, _claro(cuerpo, 0.35),
                           (int(px - r * 0.25), int(py - r * 0.25)), max(2, r // 4))

    def _dib_sabueso(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        dib = cuerpo
        if self.carga_pendiente > 0:
            # Cargando: parpadea en rojo y echa chispas por delante.
            dib = (255, 150, 90) if (self.carga_pendiente // 4) % 2 else (255, 90, 60)
        self._poligono(pantalla, px, py, [
            (r * 1.4, 0), (-r * 0.5, -r * 0.9), (-r * 0.9, 0), (-r * 0.5, r * 0.9)
        ], dib, borde, 2)
        for k in range(3):
            d = r * (1.6 + k * 0.55)
            ax = int(px + math.cos(self.angulo) * d)
            ay = int(py + math.sin(self.angulo) * d)
            pygame.draw.circle(pantalla, (255, 210, 120), (ax, ay), max(2, 5 - k))
        pygame.draw.circle(pantalla, (30, 20, 16), (px, py), int(r * 0.5))
        pygame.draw.circle(pantalla, (255, 240, 200), (px, py), max(1, int(r * 0.28)))
        if self.carga_pendiente > 0:
            # Anillo que aprieta: cuenta atras de la embestida.
            frac = 1.0 - self.carga_pendiente / max(1, self.cfg["aviso_carga"])
            pygame.draw.circle(pantalla, (255, 80, 60), (px, py), r + 8, 2)
            pygame.draw.circle(pantalla, (255, 220, 160), (px, py),
                               int(r + 8 + 18 * frac), 1)

    def _dib_acechador(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Se difumina mientras se teletransporta.
        alfa = 70 if self.parpadeo > 0 else 255
        lado = int(r * 3)
        capa = pygame.Surface((lado, lado), pygame.SRCALPHA)
        cc = r * 1.5
        hexagono = [(cc + math.cos(a) * r, cc + math.sin(a) * r)
                    for a in (0, math.pi / 3, 2 * math.pi / 3, math.pi,
                              4 * math.pi / 3, 5 * math.pi / 3)]
        pygame.draw.polygon(capa, (*cuerpo, alfa), hexagono)
        pygame.draw.polygon(capa, (*borde, alfa), hexagono, 2)
        pygame.draw.circle(capa, (*brillo, alfa), (int(cc), int(cc)), max(2, r // 3))
        pantalla.blit(capa, (px - int(cc), py - int(cc)))

    def _dib_divisorio(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        # Capsula con costura: se ve por donde se va a partir.
        self._rombo(pantalla, px, py, r, cuerpo, borde)
        for signo in (-1, 1):
            pygame.draw.line(pantalla, _oscuro(cuerpo, 0.5),
                             (int(px - r * 0.2), int(py + signo * r)),
                             (int(px + r * 0.2), int(py + signo * r)), 2)
        pygame.draw.circle(pantalla, (150, 255, 160), (px, py), max(2, r // 3))
        for k in range(3):
            a = t * 1.6 + k * TAU / 3
            sx = int(px + math.cos(a) * r * 0.62)
            sy = int(py + math.sin(a) * r * 0.62)
            pygame.draw.circle(pantalla, (220, 255, 210), (sx, sy), 2)

    def _dib_germen(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        pygame.draw.circle(pantalla, cuerpo, (px, py), r)
        pygame.draw.circle(pantalla, (235, 255, 225), (px, py), max(1, r - 3), 1)
        ax = int(px + math.cos(self.angulo) * r * 1.3)
        ay = int(py + math.sin(self.angulo) * r * 1.3)
        pygame.draw.line(pantalla, cuerpo, (px, py), (ax, ay), 2)

    def _dibujar_jefe(self, pantalla, px, py, r, cuerpo, borde, brillo, t):
        if self.tipo == "jefe":
            # Anillos giratorios + nucleo con ojo
            pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.55), (px, py), int(r * 1.28), 3)
            pygame.draw.circle(pantalla, cuerpo, (px, py), int(r * 1.05))
            pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.3), (px, py), int(r * 1.05), 2)
            for i in range(8):
                a = t * 0.8 + i * TAU / 8
                self._poligono(pantalla, px, py, [
                    (math.cos(a) * r * 1.45, math.sin(a) * r * 1.45),
                    (math.cos(a + 0.28) * r * 1.1, math.sin(a + 0.28) * r * 1.1),
                    (math.cos(a - 0.28) * r * 1.1, math.sin(a - 0.28) * r * 1.1),
                ], brillo, borde, 1)
            pygame.draw.circle(pantalla, (60, 20, 60), (px, py), int(r * 0.55))
            ojo = int(r * 0.3)
            ex = px + int(math.cos(self.angulo) * ojo * 0.8)
            ey = py + int(math.sin(self.angulo) * ojo * 0.8)
            pygame.draw.circle(pantalla, (255, 245, 255), (ex, ey), ojo)
            pygame.draw.circle(pantalla, cuerpo, (ex, ey), max(1, int(ojo * 0.55)))

        elif self.tipo == "jefe_bastion":
            # Bloque pesado con placas de blindaje y boca de mortero.
            pygame.draw.rect(pantalla, _oscuro(cuerpo, 0.4),
                             (px - r, py - r, r * 2, r * 2), border_radius=int(r * 0.2))
            pygame.draw.rect(pantalla, cuerpo,
                             (int(px - r * 0.85), int(py - r * 0.85),
                              int(r * 1.7), int(r * 1.7)),
                             border_radius=int(r * 0.18), width=3)
            for a, b in (((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
                pygame.draw.line(pantalla, _oscuro(cuerpo, 0.25),
                                 (px + a[0] * r * 0.6, py + a[1] * r * 0.6),
                                 (px + b[0] * r * 0.6, py + b[1] * r * 0.6), 4)
            mx = px + math.cos(self.angulo) * r * 0.9
            my = py + math.sin(self.angulo) * r * 0.9
            pygame.draw.circle(pantalla, (40, 24, 14), (int(mx), int(my)), int(r * 0.3))
            pygame.draw.circle(pantalla, (255, 220, 150), (int(mx), int(my)),
                               max(1, int(r * 0.16)))

        elif self.tipo == "jefe_matriarca":
            # Caparazon con celdas latiendo y patas articuladas.
            pygame.draw.circle(pantalla, _oscuro(cuerpo, 0.5), (px, py), int(r * 1.1), 3)
            for i in range(7):
                a = t * 0.6 + i * TAU / 7
                ex = px + math.cos(a) * r * 1.5
                ey = py + math.sin(a) * r * 1.5
                pygame.draw.line(pantalla, _oscuro(cuerpo, 0.3), (px, py), (ex, ey), 5)
                pygame.draw.line(pantalla, cuerpo,
                                 (px + math.cos(a + 0.5) * r * 0.6,
                                  py + math.sin(a + 0.5) * r * 0.6), (ex, ey), 3)
                pygame.draw.circle(pantalla, brillo, (int(ex), int(ey)), 4)
            pygame.draw.circle(pantalla, cuerpo, (px, py), int(r * 0.95))
            for i in range(3):
                a = self.angulo + (i - 1) * 0.5
                ox = px + int(math.cos(a) * r * 0.55)
                oy = py + int(math.sin(a) * r * 0.55)
                pygame.draw.circle(pantalla, (25, 50, 30), (ox, oy), max(2, int(r * 0.16)))
                pygame.draw.circle(pantalla, (220, 255, 200), (ox, oy),
                                   max(1, int(r * 0.08)))
            pygame.draw.circle(pantalla, (30, 80, 40), (px, py), int(r * 0.3))

        else:  # jefe_prisma
            # Nucleo de cristal con caras girando.
            pygame.draw.circle(pantalla, (20, 40, 60), (px, py), int(r * 1.15), 3)
            for k in range(3):
                a = t * 1.1 + k * TAU / 3
                p1 = (math.cos(a) * r * 0.9, math.sin(a) * r * 0.9)
                p2 = (math.cos(a + TAU / 3) * r * 0.9, math.sin(a + TAU / 3) * r * 0.9)
                p3 = (math.cos(a + TAU / 6) * r * 0.45, math.sin(a + TAU / 6) * r * 0.45)
                self._poligono(pantalla, px, py, [p1, p2, p3],
                               _oscuro(cuerpo, 0.2), brillo, 2)
            pygame.draw.circle(pantalla, (235, 250, 255), (px, py), max(2, int(r * 0.22)))
            for k in range(2):
                a = -t * 0.8 + k * math.pi
                ex = px + int(math.cos(a) * r * 1.4)
                ey = py + int(math.sin(a) * r * 1.4)
                pygame.draw.circle(pantalla, (255, 255, 255), (ex, ey), 4)

        # Marco comun de jefe: aura de fase 2 y telegrafia del ataque.
        if self.fase_jefe == 2:
            pygame.draw.circle(pantalla, (255, 60, 60),
                               (px, py), int(r * 1.3 + 3 * math.sin(t * 5)), 2)
        if self.marcas_ataque > 0:
            radio = int(r * 1.15 + 14 * math.sin(t * 18) ** 2)
            pygame.draw.circle(pantalla, (255, 240, 200), (px, py), radio, 2)
        if self.carga_pendiente > 0:
            # Carga del jefe: anillo rojo que aprieta y flecha de direccion,
            # para que se vea de donde viene el pisadon.
            frac = 1.0 - self.carga_pendiente / max(1, self.charge_aviso_total or 1)
            pygame.draw.circle(pantalla, (255, 70, 50), (px, py), int(r * 1.3), 3)
            pygame.draw.circle(pantalla, (255, 235, 190),
                               (px, py), int(r * 1.3 + 26 * frac), 2)
            punta = (int(px + math.cos(self.angulo) * (r * 1.9 + 22 * frac)),
                     int(py + math.sin(self.angulo) * (r * 1.9 + 22 * frac)))
            pygame.draw.circle(pantalla, (255, 120, 70), punta, max(3, int(r * 0.22)))

    def _arco_escudo(self, pantalla, px, py, largo, arco, t):
        """Placa curva del acorazado: protege solo ese arco frontal."""
        puntos = []
        pasos = 9
        for i in range(pasos + 1):
            a = self.angulo - arco / 2 + arco * i / pasos
            puntos.append((int(px + math.cos(a) * largo), int(py + math.sin(a) * largo)))
        color = (200, 230, 255) if (t * 3) % 1 < 0.6 else (150, 200, 255)
        pygame.draw.lines(pantalla, color, False, puntos, 6)
        pygame.draw.lines(pantalla, (255, 255, 255), False, puntos, 2)

    # --------------------------------------------------------- auxiliares
    def _poligono(self, pantalla, px, py, puntos, relleno, borde=None, grosor=2):
        cos_a = math.cos(self.angulo)
        sin_a = math.sin(self.angulo)
        mundo = [
            (px + lx * cos_a - ly * sin_a, py + lx * sin_a + ly * cos_a)
            for lx, ly in puntos
        ]
        if relleno is not None:
            pygame.draw.polygon(pantalla, relleno, mundo)
        if borde is not None and grosor:
            pygame.draw.polygon(pantalla, borde, mundo, grosor)

    def _rombo(self, pantalla, px, py, r, relleno, borde):
        self._poligono(pantalla, px, py, [(r, 0), (0, r), (-r, 0), (0, -r)],
                       relleno, borde)

    # ------------------------------------------------------ fragmentacion
    def explodes_en(self, cantidad=None):
        """Devuelve los `Fragmento` en los que se rompe este enemigo.

        Los trozos salen de la misma silueta que se dibuja, recortada en
        sectores: al arrancar en pedazos de la forma real, el conjunto se lee
        como "se ha roto esto" y no como "han salido unos triangulos".
        """
        r = self.radio
        if cantidad is None:
            # Un jefe se rompe en mas trozos: es mas grande y su muerte tiene
            # que pesar mas que la de un corredor.
            cantidad = 14 if self.es_jefe else max(4, min(9, int(r * 0.7)))
        cuerpo = self.color
        borde = _oscuro(self.color, 0.45)
        fragmentos = []
        # Los trozos se reparten en sectores alrededor del centro. Cada sector
        # lleva su parte de la silueta, mas un borde hacia fuera para que el
        # trozo tenga volumen y no sea una rebanada plana.
        for k in range(cantidad):
            a0 = k * TAU / cantidad
            a1 = (k + 1) * TAU / cantidad
            am = (a0 + a1) * 0.5
            # Se estrecha un poco el sector para que los trozos no se solapen.
            hueco = (a1 - a0) * 0.12
            p0 = a0 + hueco
            p1 = a1 - hueco
            # Vértices: centro, borde del sector y un punto medio fuera, que es
            # lo que hace que el trozo tenga una cara convexa.
            r_ext = r * random.uniform(0.75, 1.15)
            puntos = [
                (0.0, 0.0),
                (math.cos(p0) * r_ext, math.sin(p0) * r_ext),
                (math.cos(am) * r_ext * 1.12, math.sin(am) * r_ext * 1.12),
                (math.cos(p1) * r_ext, math.sin(p1) * r_ext),
            ]
            # El primer vértice se separa un poco del centro: si no, todos los
            # trozos se tocan en un punto y parecen una rueda.
            puntos[0] = (math.cos(am) * r * 0.18, math.sin(am) * r * 0.18)
            # Velocidad: hacia fuera del centro, con dispersion. La dispersion
            # es lo que evita que salgan en linea recta como un abanico.
            vel = random.uniform(1.6, 4.4)
            desvio = random.uniform(-0.5, 0.5)
            va = am + desvio
            fragmentos.append(Fragmento(
                self.x, self.y, puntos, cuerpo, borde,
                math.cos(va) * vel, math.sin(va) * vel,
                vida=random.randint(26, 46),
                escala=r / 12.0,
            ))
        return fragmentos


def _claro(color, f):
    return tuple(min(255, int(c + (255 - c) * f)) for c in color[:3])


def _oscuro(color, f):
    return tuple(max(0, int(c * (1 - f))) for c in color[:3])


def jefe_para_oleada(oleada):
    """Que jefe toca en esta oleada, o None si no toca."""
    if oleada <= 0 or oleada % CADA_CUANTAS_JEFES != 0:
        return None
    return ORDEN_JEFES[(oleada // CADA_CUANTAS_JEFES - 1) % len(ORDEN_JEFES)]


def escala_jefe(oleada):
    """Los jefes se endurecen: el primero es mas facil que el cuarto."""
    n = oleada // CADA_CUANTAS_JEFES
    return 1.0 + max(0, n - 1) * 0.14
