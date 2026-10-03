# -*- coding: utf-8 -*-
"""
app_principal.py
================
ARENA - shooter cenital (top-down arena shooter).

Camara que sigue al jugador con suavizado y antecipacion, oleadas cada vez
mas numerosas, congelacion de imagen en los impactos (hitstop), powerups,
cuatro armas, dash, minimapa, HUD y records.
"""

import math
import random
import sys
from datetime import date

import pygame  # type: ignore[import-not-found]

import decoracion
import decals
import efectos
import iconos
import iluminacion
import pantallas
import postproceso
import progresion
import puntajes
import armas as armas_mod
from arena import Arena, TAM_CASILLA
from armas import ARMAS
from enemigos import Enemigo, Aviso, ORDEN_JEFES, jefe_para_oleada, escala_jefe
from jugador import Jugador

# --------------------------------------------------------------- constantes
ANCHO, ALTO = 960, 640
FPS = 60

MENU, JUGANDO, PAUSA, MUERTO, TIENDA, SUBA_NIVEL = 0, 1, 2, 3, 4, 5

COLOR_POWERUP = {
    "vida": (96, 240, 126),
    "escudo": (120, 220, 255),
    "velocidad": (255, 190, 70),
    "arma": (255, 120, 220),
}
SIMBOLO_POWERUP = {"vida": "+", "escudo": "O", "velocidad": ">>", "arma": "*"}
VIDA_POWERUP = 700

# Dano por contacto: ahora lo lleva cada tipo en enemigos.TIPOS
# (self.dano_contacto), porque el sabueso y los jefes lo suben al embestir.

# Fluidez
ESCALA_MINIMAPA = 0.15

COL_PANEL = (16, 17, 24)
COL_PANEL_BORDE = (54, 58, 76)
# Relleno de fondo: lo que se ve fuera de la arena (margen del temblor).
COL_FONDO_EXT = (8, 8, 12)
COL_TEXTO = (226, 232, 244)
COL_TEXTO_SUAVE = (140, 148, 168)
COL_ACENTO = (250, 210, 90)

# Enemigos normales y a partir de que oleada empiezan a salir. Los jefes van
# aparte: uno cada 3 oleadas, rotando entre los cuatro.
COMPOSICION = (
    (1, "corredor"), (2, "tirador"), (2, "tanque"), (3, "explosivo"),
    (4, "acorazado"), (5, "mortero"), (6, "dron"), (7, "sabueso"),
    (8, "acechador"), (9, "divisorio"),
)


def composicion_oleada(oleada):
    """Lista de tipos de enemigos de la oleada, jefe incluido si toca."""
    lista = []
    jefe = jefe_para_oleada(oleada)
    if jefe:
        lista.append(jefe)
    disponibles = [clave for desde, clave in COMPOSICION if oleada >= desde]
    for i in range(4 + oleada * 2):
        # Reparto equitativo con un giro por oleada: en la 5 hay de todo,
        # no solo del ultimo tipo de la tabla.
        lista.append(disponibles[(i + oleada) % len(disponibles)])
    return lista


def multiplicador_combo(combo):
    return 1.0 + min(combo - 1, 8) * 0.2


def direccion_movimiento(teclas):
    dx = float(teclas[pygame.K_d] or teclas[pygame.K_RIGHT]) - float(
        teclas[pygame.K_a] or teclas[pygame.K_LEFT]
    )
    dy = float(teclas[pygame.K_s] or teclas[pygame.K_DOWN]) - float(
        teclas[pygame.K_w] or teclas[pygame.K_UP]
    )
    return dx, dy


class Contexto:
    """Lo que un enemigo necesita del juego para invocar y avisar.

    Se pasa a `Enemigo.actualizar` para que los jefes y el divisorio puedan
    meter unidades y zonas de peligro sin conocer la clase Juego.
    """

    def __init__(self, juego):
        self.juego = juego
        self.enemigos = juego.enemigos
        self.arena = juego.arena
        self.avisos = juego.avisos

    def invocar(self, tipo, x, y):
        escala = 1.0 + max(0, self.juego.oleada - 1) * 0.06
        enemigo = Enemigo(x, y, tipo, escala)
        self.enemigos.append(enemigo)
        return enemigo

    def avisar(self, x, y, radio, frames, color, dano, **kwargs):
        self.avisos.append(Aviso(x, y, radio, frames, color, dano, **kwargs))


class Juego:
    def __init__(self, pantalla, reloj):
        self.pantalla = pantalla
        self.reloj = reloj
        # La cartera la crea reiniciar(): es de esta partida y solo de esta.
        self.cartera = None
        self.particulas = efectos.GestorParticulas(max_particulas=600)
        self.fuente_hud = pygame.font.SysFont("consolas", 20, bold=True)
        self.fuente_ch = pygame.font.SysFont("consolas", 16)
        self.fuente_peq = pygame.font.SysFont("consolas", 14)
        self.fuente_grande = pygame.font.SysFont("consolas", 30, bold=True)
        self._vineta = None
        self._capa_dano = None
        self._capa_oleada = None
        self._dano_flash_pintado = -1
        self._minimapa = None
        self._minimapa_arena = None
        # Cache de textos del HUD: renderizar una fuente es de lo mas caro del
        # frame y casi todo lo que se escribe es el mismo texto cada cuadro
        # ("VIDA", "OLEADA 3", "[T] TIENDA"...). Se cachea por
        # (fuente, texto, color) y solo lo que cambia (numeros, barras) se
        # vuelve a pintar.
        self._cache_texto = {}
        self._cache_texto_orden = []
        # Bloom: buffer emisivo que se difumina y se suma al final del frame.
        # Se crea una sola vez, aqui y no en reiniciar(), para que la cache de
        # texturas de halo sobreviva entre partidas.
        self.bloom = postproceso.Bloom(ANCHO, ALTO)
        # Marcas en el suelo: los impactos y las explosiones dejan rastro. Se
        # cuelga del gestor de particulas, que es por donde pasan todos los
        # impactos y explosiones del juego.
        self.marcas = self.particulas.marcas_(decals.Marcas())
        # Trozos de enemigos al morir. Es una lista propia y no del gestor de
        # particulas porque cada trozo gira sobre si mismo.
        self.fragmentos = []
        self.reiniciar()

    def reiniciar(self):
        self.arena = Arena(semilla=random.randint(1, 10 ** 6))
        # Decoracion y luces se generan con la semilla de la arena, asi que el
        # mapa se ve igual cada vez que sale esa semilla.
        self.decoracion = decoracion.Decoracion(self.arena)
        self.luces = iluminacion.Luces(ANCHO, ALTO)
        self.decoracion.luces_ambiente(self.luces)
        # El gestor de luces es nuevo en cada partida, asi que hay que
        # volver a colgarle el bloom (que si sobrevive).
        self.luces.bloom = self.bloom
        # Luz del jugador: siempre presente, sigue al personaje. Es un tinte
        # calido, no un foco: con intensidad alta se comia el color del mapa.
        self.luz_jugador = self.luces.crear(0, 0, 210, (255, 244, 214),
                                            intensidad=0.30, caida=2.0)
        # Roguelite puro: cada partida arranca con la cartera limpia.
        self.cartera = progresion.Cartera()
        self.jugador = Jugador(*self.arena.punto_spawn((0, 0), 0), cartera=self.cartera)
        self.enemigos = []
        self.proyectiles = []
        self.powerups = []
        # Zonas de peligro telegrafiadas (morteros, bombardeos, laser).
        self.avisos = []
        self.particulas.vaciar()
        # Las marcas son de la partida, no del proceso: una arena nueva empieza
        # sin el rastro de la anterior.
        self.marcas.vaciar()
        self.fragmentos = []
        self.oleada = 0
        self.puntaje = 0
        self.bajas = 0
        self.mejor_combo = 0
        self.combo = 0
        self.combo_t = 0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.shake = 0
        self.hitstop = 0
        self.dano_flash = 0
        self.espera_oleada = 90
        self.mensaje_oleada = 0
        self.habilidades_cd = {clave: 0 for clave in progresion.ORDEN_HABILIDADES}
        self.sobrecarga = 0
        self.campo = {}
        self.campo_celda = None
        self.campo_t = 0
        self._actualizar_campo()

    # ------------------------------------------------- tienda y cartas de nivel
    def comprar(self, pestana, clave):
        """Compra de la tienda en partida. Devuelve True si se aprobo."""
        c = self.cartera
        if pestana == 0:
            ok = c.comprar_mejora(clave)
        elif pestana == 1:
            ok = c.desbloquear_arma(clave)
        else:
            ok = c.desbloquear_habilidad(clave)
        if ok:
            # Los cambios se notan al instante, sin reiniciar la partida.
            self.jugador.aplicar_cartera(c)
            self._aplicar_bonos_arma()
        return ok

    def cartas_nivel(self):
        """Las opciones para la proxima subida de nivel pendiente."""
        return self.cartera.cartas()

    def elegir_carta(self, carta):
        """Aplica la carta elegida y actualiza al jugador."""
        if not self.cartera.elegir_carta(carta):
            return False
        self.jugador.aplicar_cartera(self.cartera)
        self._aplicar_bonos_arma()
        return True

    def _aplicar_bonos_arma(self):
        """Vuelca los multiplicadores de la cartera en el arma, con sobrecarga."""
        if self.cartera is None:
            return
        est = self.cartera.estadisticas()
        danio, cadencia = est["danio"], est["cadencia"]
        if self.sobrecarga > 0:
            danio *= 1.8
            cadencia *= 0.6
        self.jugador.arma.aplicar_bonos(danio, cadencia, est["municion"], est["recarga"])

    def usar_habilidad(self, clave):
        """Activa una habilidad desbloqueada. Devuelve True si se lanzo."""
        if self.cartera is None or not self.cartera.habilidad_activa(clave):
            return False
        if self.habilidades_cd.get(clave, 0) > 0:
            return False
        if clave == "sobrecarga" and self.sobrecarga > 0:
            return False
        cfg = progresion.HABILIDADES[clave]
        jug = self.jugador

        if clave == "nova":
            radio = cfg["radio"]
            for e in self.enemigos:
                if e.vivo and (e.x - jug.x) ** 2 + (e.y - jug.y) ** 2 <= radio * radio:
                    if e.recibir_dano(cfg["danio"], math.atan2(e.y - jug.y, e.x - jug.x)):
                        self._matar_enemigo(e, None, cfg["danio"])
            self.particulas.anillo(jug.x, jug.y, cfg["color"], radio, vida=28, grosor=5)
            self.shake = max(self.shake, 14)
            self.hitstop = max(self.hitstop, 6)
            self.habilidades_cd[clave] = cfg["enfriamiento"]
        elif clave == "tormenta":
            danio = cfg["danio"] * jug.arma.mult_danio
            for i in range(cfg["balas"]):
                a = i * (2 * math.pi / cfg["balas"])
                self.proyectiles.append(
                    armas_mod.Proyectil(
                        jug.x + math.cos(a) * 20, jug.y + math.sin(a) * 20, a,
                        700, danio, 5, cfg["color"], forma="traza", largo_estela=7,
                    )
                )
            self.particulas.anillo(jug.x, jug.y, cfg["color"], 120, vida=22, grosor=3)
            self.luces.destello(jug.x, jug.y, 200, cfg["color"], 0.35, vida=18)
            self.habilidades_cd[clave] = cfg["enfriamiento"]
        elif clave == "sobrecarga":
            self.sobrecarga = cfg["duracion"]
            self.habilidades_cd[clave] = cfg["enfriamiento"]
            self._aplicar_bonos_arma()
            self.luces.destello(jug.x, jug.y, 170, cfg["color"], 0.32, vida=22)
            self.particulas.texto(jug.x, jug.y - 46, "SOBRECARGA", cfg["color"],
                                  tamano=22, vida=60)
        else:
            return False
        return True

    def _actualizar_habilidades(self):
        for clave in list(self.habilidades_cd):
            if self.habilidades_cd[clave] > 0:
                self.habilidades_cd[clave] -= 1
        if self.sobrecarga > 0:
            self.sobrecarga -= 1
            if self.sobrecarga == 0:
                # Al terminar se reponen los multiplicadores de la cartera.
                self._aplicar_bonos_arma()

    # ------------------------------------------------------------- oleadas
    def _actualizar_campo(self):
        """Recalcula el campo de flujo cuando el jugador cambia de celda."""
        if self.campo_t > 0:
            self.campo_t -= 1
            return
        celda = self.arena.celda_de(self.jugador.x, self.jugador.y)
        if celda != self.campo_celda:
            self.campo = self.arena.campo_flujo(self.jugador.x, self.jugador.y)
            self.campo_celda = celda
            self.campo_t = 6

    def iniciar_oleada(self):
        self.oleada += 1
        escala = 1.0 + (self.oleada - 1) * 0.08
        for tipo in composicion_oleada(self.oleada):
            # Los jefes llevan su propia escala para endurecerse por oleadas,
            # sin que les affects la masificacion normal de los enemigos.
            es_jefe = tipo in ORDEN_JEFES
            enemigo = Enemigo(0, 0, tipo,
                              escala=escala_jefe(self.oleada) if es_jefe else escala)
            # Buscar un hueco con holgura para que las unidades grandes quepan.
            x, y = self.arena.punto_spawn(
                self.jugador.centro(), 320, radio=enemigo.radio_colision
            )
            enemigo.x, enemigo.y = x, y
            self.enemigos.append(enemigo)
            # Aviso de aparicion
            self.particulas.anillo(x, y, enemigo.color, 34, vida=18, grosor=2)
        self.mensaje_oleada = 150
        self.espera_oleada = 0

    # --------------------------------------------------------- colisiones
    def _colisiones(self):
        jug = self.jugador

        # Proyectiles propios contra enemigos. Los perforantes atraviesan a
        # varios: se marcan en p.impactados para no repetir dano si rebotan.
        for p in self.proyectiles:
            if not p.vivo or p.hostil:
                continue
            for e in self.enemigos:
                if not e.vivo or id(e) in p.impactados:
                    continue
                if (p.x - e.x) ** 2 + (p.y - e.y) ** 2 > (p.radio + e.radio) ** 2:
                    continue

                p.impactados.add(id(e))
                self.particulas.impacto(p.x, p.y, e.color)
                # Chispa luminosa en el punto de impacto.
                self.luces.destello(p.x, p.y, 46, (255, 236, 190), 0.22, vida=4)
                if e.recibir_dano(p.danio, p.angulo):
                    self._matar_enemigo(e, p.angulo, p.danio)
                else:
                    self.hitstop = max(self.hitstop, 1)

                # El proyectil se consume segun su poder de perforacion.
                if p.perforante < 0:
                    p.danio *= 0.94
                    continue
                if p.perforante <= 0:
                    p.vivo = False
                    break
                p.perforante -= 1
                p.danio *= 0.94
            if not p.vivo:
                break

        # Proyectiles enemigos contra el jugador. Cada ataque duele lo que
        # dice su proyectil, asi que el laser muerde mas que una bala tonta.
        for p in self.proyectiles:
            if not p.vivo or not p.hostil:
                continue
            if (p.x - jug.x) ** 2 + (p.y - jug.y) ** 2 <= (p.radio + jug.radio) ** 2:
                p.vivo = False
                cantidad = p.dano_jugador
                if jug.recibir_dano(cantidad):
                    self._jugador_danado(cantidad)

        # Contacto enemigo-jugador
        for e in self.enemigos:
            if not e.vivo:
                continue
            if (e.x - jug.x) ** 2 + (e.y - jug.y) ** 2 <= (e.radio + jug.radio) ** 2:
                if e.tipo == "explosivo":
                    e.explodir(jug, self.particulas)
                    continue
                # El sabueso y los jefes pegan mas mientras embisten.
                if e.dano_contacto > 0 and jug.recibir_dano(e.dano_contacto):
                    self._jugador_danado(e.dano_contacto)

        # Powerups: con la mejora IMAN son atraidos desde lejos.
        magnetico = jug.magnetico
        for pu in self.powerups:
            if magnetico > 0:
                dx, dy = jug.x - pu["x"], jug.y - pu["y"]
                distancia = math.hypot(dx, dy)
                if 0.1 < distancia < magnetico:
                    paso = min(distancia, 6.0 + magnetico * 0.06)
                    pu["x"] += dx / distancia * paso
                    pu["y"] += dy / distancia * paso
            if (pu["x"] - jug.x) ** 2 + (pu["y"] - jug.y) ** 2 <= (22 + jug.radio) ** 2:
                self._aplicar_powerup(pu)
                pu["vida"] = 0

    def _jugador_danado(self, cantidad):
        self.shake = max(self.shake, 8)
        self.hitstop = max(self.hitstop, 5)
        absorbido = self.jugador.escudo <= 0
        self.dano_flash = 22
        self.particulas.destello_dano(self.jugador.x, self.jugador.y)
        # Destello rojo al recibir dano: deja claro que ha dolido.
        self.luces.destello(self.jugador.x, self.jugador.y, 90,
                            (255, 90, 70), 0.30, vida=9)
        if absorbido:
            self.particulas.texto(
                self.jugador.x, self.jugador.y - 28, "-%d" % cantidad,
                (255, 110, 110), tamano=18,
            )
        else:
            self.particulas.escudo_roto(self.jugador.x, self.jugador.y)
            self.particulas.texto(
                self.jugador.x, self.jugador.y - 28, "ESCUDO",
                (150, 225, 255), tamano=18,
            )

    def _matar_enemigo(self, e, angulo=None, danio=0.0):
        # El divisorio se parte antes de desaparecer.
        crias = e.cfg.get("crias")
        if crias:
            self._partir_divisorio(e, crias)
        escala = 1.6 if e.es_jefe else 1.0
        self.particulas.explosion(e.x, e.y, escala)
        # El enemigo se rompe en trozos que salen despedidos. Van por su cuenta
        # y no por el gestor de particulas porque giran sobre si mismos.
        self.fragmentos.extend(e.explodes_en())
        # Restos del enemigo en el suelo, del color de la criatura. Los jefes
        # dejan mas rastro: mas grande y con grieta alrededor.
        if e.es_jefe:
            self.marcas.salpicadura(e.x, e.y, e.color, escala=2.2)
            self.marcas.grieta(e.x, e.y, escala=1.6)
        else:
            self.marcas.salpicadura(e.x, e.y, e.color)
        # La explosion ilumina de verdad, no solo pintada: un jefe ilumina mas.
        self.luces.destello(e.x, e.y, 110 * escala, e.color,
                            intensidad=0.45 if e.es_jefe else 0.28,
                            vida=14 if e.es_jefe else 7)
        self.shake = max(self.shake, 22 if e.es_jefe else 4)
        self.hitstop = max(self.hitstop, 8 if e.es_jefe else 2)
        self.bajas += 1
        self.combo += 1
        self.combo_t = 110
        self.mejor_combo = max(self.mejor_combo, self.combo)
        puntos = int(e.puntos * multiplicador_combo(self.combo))
        self.puntaje += puntos

        # Monedas y XP por baja, mas vampirismo si esta comprado.
        monedas = progresion.MONEDAS_POR_BAJA.get(e.tipo, 1)
        self.cartera.anadir_monedas(monedas)
        xp = progresion.XP_POR_BAJA.get(e.tipo, 10)
        subidos = self.cartera.anadir_xp(xp)
        if subidos:
            # El nivel da vida y velocidad al instante; el resto se elige
            # luego, en la pantalla de cartas.
            self.jugador.aplicar_cartera(self.cartera)
            self._aplicar_bonos_arma()
            self.particulas.texto(
                e.x, e.y - e.radio - 34, "NIVEL %d" % self.cartera.nivel,
                (150, 220, 255), tamano=26, vida=90,
            )
        jug = self.jugador
        if jug.vampiro > 0 and danio > 0:
            jug.curar(danio * jug.vampiro)

        self.particulas.texto(
            e.x, e.y - e.radio, "+%d" % puntos,
            (255, 220, 120) if self.combo < 5 else (255, 150, 90),
            tamano=20 if not e.es_jefe else 30,
            vida=60,
        )
        self.particulas.texto(
            e.x + 14, e.y - e.radio + 20, "+%d" % monedas,
            (250, 210, 90), tamano=15, vida=55,
        )
        if random.random() < 0.22:
            self.powerups.append(
                {
                    "x": e.x, "y": e.y,
                    "tipo": random.choice(list(COLOR_POWERUP)),
                    "vida": VIDA_POWERUP,
                }
            )

    def _partir_divisorio(self, e, crias):
        """El divisorio suelta su cria al morir, en puntos libres."""
        self.particulas.anillo(e.x, e.y, (170, 255, 170), e.radio * 2.4, vida=20)
        total = len(crias)
        for k, tipo in enumerate(crias):
            a = k * math.tau / total + random.random()
            d = e.radio + 10
            x, y = e.x + math.cos(a) * d, e.y + math.sin(a) * d
            if not self.arena.circulo_libre(x, y, 6):
                # Si el hueco esta ocupado, la cria nace encima: mejor eso que
                # perderla por un muro.
                x, y = e.x, e.y
            self.enemigos.append(Enemigo(x, y, tipo))
            self.particulas.anillo(x, y, (200, 255, 200), 18, vida=14, grosor=2)

    def _aplicar_powerup(self, pu):
        jug = self.jugador
        tipo = pu["tipo"]
        color = COLOR_POWERUP[tipo]
        self.particulas.destello_powerup(pu["x"], pu["y"], color)
        # El powerup ilumina al tomarlo.
        self.luces.destello(pu["x"], pu["y"], 95, color, 0.35, vida=12)
        if tipo == "vida":
            jug.curar(35)
            texto = "+35 VIDA"
        elif tipo == "escudo":
            jug.escudo = 360 + jug.escudo_extra
            texto = "ESCUDO"
        elif tipo == "velocidad":
            jug.velocidad_bonus = 540
            texto = "VELOCIDAD"
        else:
            jug.arma.cambiar_arma(1)
            texto = jug.arma.nombre()
        self.particulas.texto(pu["x"], pu["y"] - 14, texto, color, tamano=18)

    # ------------------------------------------------------------- update
    def actualizar(self, teclas, mouse_pos, mouse_presionado):
        # Congelacion de imagen tras un impacto: da peso a cada golpe.
        if self.hitstop > 0:
            self.hitstop -= 1
            self.particulas.actualizar()
            return

        jug = self.jugador
        jug.cam_x, jug.cam_y = self.cam_x, self.cam_y
        jug.actualizar(self.arena, teclas, mouse_pos)

        # El campo de flujo se recalcula cuando el jugador cambia de celda:
        # sin esto las unidades persiguen en linea recta y se encajan en muros.
        self._actualizar_campo()

        if mouse_presionado:
            critico = jug.tirar_dado()
            for p in jug.arma.disparar(self.arena, jug.x, jug.y, jug.angulo,
                                       critico=critico,
                                       critico_mult=jug.critico_mult) or []:
                self.proyectiles.append(p)
                # El fogonazo en cono lo dibuja la propia bala en sus primeros
                # frames (Proyectil.fogonazo). Aqui solo queda la luz que
                # ilumina la escena alrededor.
                self.luces.destello(p.x, p.y, 70 if critico else 52,
                                    (255, 230, 170) if critico else (255, 214, 150),
                                    0.30 if critico else 0.20,
                                    vida=5 if critico else 3)
                if critico:
                    self.particulas.texto(
                        p.x, p.y - 10, "CRIT", (255, 235, 130), tamano=15, vida=30
                    )

        # Los enemigos reciben un contexto para poder invocar aliados y marcar
        # zonas de peligro (morteros, bombardeos del jefe, laser).
        ctx = Contexto(self)
        for e in self.enemigos:
            e.actualizar(self.arena, jug, self.proyectiles, self.particulas,
                         self.campo, ctx)
        for p in self.proyectiles:
            p.actualizar(self.arena, self.particulas)

        # Zonas de peligro: avisan, luego pegan.
        if self.avisos:
            for aviso in self.avisos:
                for cantidad in aviso.actualizar(self.arena, jug, self.particulas):
                    if jug.recibir_dano(cantidad):
                        self._jugador_danado(cantidad)
            self.avisos = [a for a in self.avisos if a.vivo()]

        self.proyectiles = [p for p in self.proyectiles if p.vivo]
        self.enemigos = [e for e in self.enemigos if e.vivo]

        for pu in self.powerups:
            pu["vida"] -= 1
        self.powerups = [pu for pu in self.powerups if pu["vida"] > 0]

        self._colisiones()
        self.particulas.actualizar()
        # Las marcas envejecen a su ritmo: se van cuando se acaba su vida.
        self.marcas.actualizar()
        # Trozos de enemigos: se quitan los que ya se han desintegrado.
        if self.fragmentos:
            for fr in self.fragmentos:
                fr.actualizar()
            self.fragmentos = [fr for fr in self.fragmentos if fr.edad < fr.vida]
        self._actualizar_habilidades()
        self._actualizar_luces()

        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0:
                self.combo = 0
        if jug.velocidad_bonus > 0:
            jug.velocidad_bonus -= 1

        self._actualizar_camara()
        if self.shake > 0:
            self.shake -= 1
        if self.dano_flash > 0:
            self.dano_flash -= 1
        if self.mensaje_oleada > 0:
            self.mensaje_oleada -= 1

        # Siguiente oleada (con un respiro entre oleadas)
        if not self.enemigos:
            if self.espera_oleada <= 0:
                self.espera_oleada = 90
            self.espera_oleada -= 1
            if self.espera_oleada == 0:
                self.iniciar_oleada()

    def _actualizar_camara(self):
        # Camara rigida centrada en el jugador. Con suavizado o anticipacion
        # el mundo se desplazaba de forma elastica al moverse y las distancias
        # a los enemigos parecian estirarse y comprimirse.
        jug = self.jugador
        self.cam_x = jug.x - ANCHO / 2
        self.cam_y = jug.y - ALTO / 2
        self.cam_x = max(0.0, min(self.arena.ancho - ANCHO, self.cam_x))
        self.cam_y = max(0.0, min(self.arena.alto - ALTO, self.cam_y))

    def _actualizar_luces(self):
        """La luz del jugador le sigue; las demas solo parpadean."""
        self.luces.seguir(self.luz_jugador, self.jugador.x, self.jugador.y)
        self.luces.actualizar()

    # -------------------------------------------------------------- dibujo
    def dibujar(self):
        sac = self.shake
        cx = self.cam_x + (random.randint(-sac, sac) if sac else 0)
        cy = self.cam_y + (random.randint(-sac, sac) if sac else 0)

        # Relleno previo: la zona que la arena no cubre (solo el margen del
        # temblor) no debe conservar lo dibujado en el frame anterior.
        self.pantalla.fill(COL_FONDO_EXT)
        # El buffer de bloom se vacia aqui: a partir de ahora, quien brille
        # pinta su halo y al final del frame se difumina y se suma.
        self.bloom.iniciar()
        self.arena.dibujar(self.pantalla, cx, cy, ANCHO, ALTO)
        # Props bajos: charcos, grietas y manchas del terreno.
        self.decoracion.dibujar_bajo_muros(self.pantalla, cx, cy, ANCHO, ALTO)
        # Marcas de combate: van sobre los props bajos y bajo las unidades, que
        # es donde caen de verdad (un agujero en un muro, una quemadura en el
        # suelo). Antes que los enemigos, para que estos pisen encima.
        self.marcas.dibujar(self.pantalla, cx, cy, ANCHO, ALTO)

        # Powerups
        t = pygame.time.get_ticks() / 220.0
        for pu in self.powerups:
            px, py = int(pu["x"] - cx), int(pu["y"] - cy)
            if px < -30 or py < -30 or px > ANCHO + 30 or py > ALTO + 30:
                continue
            col = COLOR_POWERUP[pu["tipo"]]
            r = 10 + int(2 * math.sin(t))
            pygame.draw.circle(self.pantalla, (18, 18, 26), (px, py), r + 2)
            pygame.draw.circle(self.pantalla, col, (px, py), r)
            pygame.draw.circle(self.pantalla, _claro(col, 0.4), (px, py), r, 2)
            self._simbolo(pu["tipo"], px, py)

        # Zonas de peligro: en el suelo, bajo las unidades, para que se lean
        # como suelo y no como algo flotante.
        for aviso in self.avisos:
            aviso.dibujar(self.pantalla, cx, cy)

        for e in self.enemigos:
            e.dibujar(self.pantalla, cx, cy)

        jug = self.jugador
        # El temblor tambien mueve al jugador; si no, se ve despegado del suelo.
        jug.cam_x, jug.cam_y = cx, cy
        # Parpadea mientras es invulnerable
        jug.dibujar(self.pantalla, jug.invul > 0 and (jug.invul // 4) % 2 == 1)

        for p in self.proyectiles:
            p.dibujar(self.pantalla, cx, cy)
            # Halo de bala: el proyectil ilumina lo que tiene alrededor. Con
            # el radio del proyectil y no con el de la luz, para que un rifle
            # no nuble la pantalla entera.
            self.bloom.marcar(p.x - cx, p.y - cy, p.radio * 3.4, p.color,
                              fuerza=0.5)

        # Trozos de enemigos: van con las particulas, encima de las unidades,
        # porque un enemigo al morir se rompe donde estaba, no por debajo.
        for fr in self.fragmentos:
            fr.dibujar(self.pantalla, cx, cy)

        self.particulas.dibujar(self.pantalla, cx, cy)
        # Props altos: tuberias, cables, chatarra y el polvo que flota.
        self.decoracion.dibujar(self.pantalla, cx, cy, t, ANCHO, ALTO)

        # Iluminacion: se multiplica sobre todo lo del mundo (suelo, props,
        # unidades, particulas) pero antes del HUD, para que los numeros y la
        # barra de vida no se apaguen con la luz. Sin oclusion por muros: con
        # ella la luz se recortaba y parecia que solo se veia un circulo.
        self.luces.componer(self.pantalla, cx, cy)

        # Bloom: difumina los halos acumulados y los suma. Va despues de
        # componer (para que el halo salga de la luz ya compuesta) y antes de
        # la vineta y el HUD, que deben quedarse nitidos.
        self.bloom.aplicar(self.pantalla)

        self._dibujar_vineta()
        self._dibujar_hud()

    def _simbolo(self, tipo, px, py):
        """Icono del powerup en el mundo, con su color."""
        img = iconos.obtener(tipo, 26, COLOR_POWERUP.get(tipo, (255, 255, 255)))
        self.pantalla.blit(
            img, (px - img.get_width() // 2, py - img.get_height() // 2)
        )

    # Tamano de la cache de textos del HUD. Es circular y acotada a proposito:
    # los textos de numeros (vida, puntos, municion) cambian cada cuadro, asi
    # que nunca deben acumular miles de entradas.
    MAX_CACHE_TEXTO = 240

    def _texto(self, texto, fuente, color):
        """render(texto) con memoria: la misma cadena no se repinta dos veces."""
        clave = (id(fuente), texto, color)
        img = self._cache_texto.get(clave)
        if img is not None:
            return img
        img = fuente.render(texto, True, color)
        self._cache_texto[clave] = img
        self._cache_texto_orden.append(clave)
        if len(self._cache_texto_orden) > self.MAX_CACHE_TEXTO:
            # Se descarta lo mas viejo (orden de insercion) para no crecer sin
            # limite durante una partida larga.
            vieja = self._cache_texto_orden.pop(0)
            self._cache_texto.pop(vieja, None)
        return img

    def _blit_texto(self, texto, fuente, color, x, y, alineacion="izq"):
        """Escribe un texto cacheado en pantalla, alineado a izquierda o derecha."""
        img = self._texto(texto, fuente, color)
        if alineacion == "der":
            x -= img.get_width()
        self.pantalla.blit(img, (int(x), int(y)))
        return img

    def _dibujar_vineta(self):
        """Oscurecido en los bordes; en rojo al recibir dano.

        La viñeta base es estatica: se blit una vez. El tinte que hace al rojo
        cuando recibe daño si cambia cada cuadro, pero se pinta una sola vez
        por nivel de intensidad y se reutiliza, asi que el coste se paga 22
        veces en total en vez de 22 por segundo.
        """
        if self._vineta is None:
            self._vineta = self._crear_vineta()
        self.pantalla.blit(self._vineta, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if self.dano_flash > 0:
            if self._capa_dano is None:
                self._capa_dano = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            # Solo se repinta cuando cambia el valor del flash: como baja de
            # 22 a 0, son 22 variantes como mucho en vez de 22 por segundo.
            paso = max(0, min(22, int(self.dano_flash)))
            if paso != self._dano_flash_pintado:
                # Se limpia antes de redibujar: si no, los rects del nivel
                # anterior se quedan y se acumulan.
                self._capa_dano.fill((0, 0, 0, 0))
                f = paso / 22.0
                for i in range(7):
                    a = int(32 * f * (1.0 - i / 7.0))
                    if a <= 0:
                        break
                    inset = i * 16
                    pygame.draw.rect(
                        self._capa_dano, (255, 50, 50, a),
                        pygame.Rect(inset, inset, ANCHO - 2 * inset, ALTO - 2 * inset),
                        14, border_radius=20,
                    )
                self._dano_flash_pintado = paso
            self.pantalla.blit(self._capa_dano, (0, 0))

    def _crear_vineta(self):
        # Se genera pequena y se escala: mucho mas rapido que por pixel.
        # El oscurecido es suave a proposito; con alpha fuerte se comia a los
        # enemigos de las esquinas y parecian difuminados.
        #
        # Va en escala de grises para poder aplicarla con BLEND_RGB_MULT en
        # vez de SRCALPHA. Multiplicar por gris oscurece de forma proporcional
        # (no se satura como haria un resta) y es ~3x mas barato, porque el
        # blit multiplicativo va por canal y el de alpha compone por pixel.
        # Fuerza y exponente calibrados para que el resultado sea
        # indistinguible del SRCALPHA anterior (error medio 0.18/255).
        w, h = 192, 128
        surf = pygame.Surface((w, h))
        cx, cy = w / 2, h / 2
        maximo = math.hypot(cx, cy)
        fuerza, exponente = 0.40, 1.3
        for y in range(h):
            for x in range(w):
                d = math.hypot(x - cx, y - cy) / maximo
                perfil = min(1.0, max(0.0, (d - 0.62) / 0.38)) ** 1.7
                c = int(255 * max(0.0, 1.0 - fuerza * perfil ** exponente))
                surf.set_at((x, y), (c, c, c))
        return pygame.transform.smoothscale(surf, (ANCHO, ALTO))

    def _panel(self, rect, alpha=205, acento=None):
        """Panel con borde y una linea de acento arriba, para que se lea como
        una pieza de interfaz y no como un rectangulo gris."""
        sup = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(sup, (COL_PANEL[0], COL_PANEL[1], COL_PANEL[2], alpha),
                         sup.get_rect(), border_radius=12)
        pygame.draw.rect(sup, COL_PANEL_BORDE, sup.get_rect(), 1, border_radius=12)
        if acento is not None:
            # Linea de acento en el borde superior: marca el panel activo.
            pygame.draw.line(sup, acento, (10, 1), (rect.width - 10, 1), 2)
            pygame.draw.rect(sup, (*acento, 60), sup.get_rect(), border_radius=12)
        self.pantalla.blit(sup, rect.topleft)

    def _barra(self, rect, fraccion, color_fondo, color_relleno):
        pygame.draw.rect(self.pantalla, color_fondo, rect, border_radius=4)
        ancho = int(rect.width * max(0.0, min(1.0, fraccion)))
        if ancho > 0:
            pygame.draw.rect(
                self.pantalla, color_relleno,
                pygame.Rect(rect.x, rect.y, ancho, rect.height), border_radius=4,
            )

    def _dibujar_hud(self):
        jug = self.jugador
        p = self.pantalla
        fuente, fch, fpeq = self.fuente_hud, self.fuente_ch, self.fuente_peq

        # --- Panel de vida (arriba izquierda)
        panel_vida = pygame.Rect(14, 12, 268, 60)
        self._panel(panel_vida, acento=(94, 220, 126))
        self._barra(pygame.Rect(24, 44, 248, 16),
                    jug.vida / jug.vida_max, (44, 30, 34),
                    (94, 220, 126) if jug.vida / jug.vida_max > 0.35 else (235, 84, 84))
        # Segmentos cada 25 puntos
        for i in range(1, 4):
            x = 24 + 248 * i // 4
            pygame.draw.line(p, (14, 16, 22), (x, 44), (x, 60))
        self._blit_texto("VIDA", fch, COL_TEXTO_SUAVE, 24, 22)
        self._blit_texto("%d" % max(0, jug.vida), fch, COL_TEXTO,
                         24 + 248, 22, alineacion="der")
        if jug.escudo > 0:
            self._blit_texto("ESCUDO %ds" % (jug.escudo // 60), fpeq,
                             (140, 225, 255), panel_vida.right - 84, 12)

        # --- Panel de arma (debajo del de vida)
        panel_arma = pygame.Rect(14, 78, 268, 54)
        self._panel(panel_arma, acento=jug.arma.color())
        color_arma = jug.arma.color()
        img_arma = iconos.obtener(jug.arma.tipo, 34, color_arma)
        p.blit(img_arma, img_arma.get_rect(midleft=(22, 96)))
        self._blit_texto(jug.arma.nombre(), fch, COL_TEXTO, 50, 84)
        if jug.arma.sin_municion():
            self._blit_texto("INF", fpeq, COL_ACENTO, 238, 92)
        else:
            self._blit_texto("%d" % jug.arma.municion, fuente, COL_TEXTO, 224, 82)
            self._blit_texto("/%d" % jug.arma.municion_max, fpeq,
                             COL_TEXTO_SUAVE, 256, 92)
        if jug.arma.recargando > 0:
            self._barra(pygame.Rect(24, 118, 248, 6), jug.arma.progreso_recarga(),
                        (50, 40, 30), (255, 190, 90))
        elif not jug.arma.sin_municion():
            self._barra(pygame.Rect(24, 118, 248, 6),
                        jug.arma.municion / max(1, jug.arma.municion_max),
                        (36, 38, 50), color_arma)

        self._dibujar_tira_armas()
        self._dibujar_habilidades()

        # --- Panel de nivel y XP (debajo del de arma)
        panel_nivel = pygame.Rect(14, 138, 268, 46)
        self._panel(panel_nivel, acento=(110, 200, 255))
        c = self.cartera
        self._blit_texto("NIVEL %d" % c.nivel, fch, (150, 220, 255), 24, 146)
        objetivo = c.xp_para_siguiente()
        if objetivo > 0:
            self._blit_texto("%d / %d" % (c.xp, objetivo), fpeq, COL_TEXTO_SUAVE,
                             panel_nivel.right - 14, 148, alineacion="der")
            self._barra(pygame.Rect(24, 168, 248, 8), c.progreso_xp(), (26, 40, 54), (110, 200, 255))
        else:
            self._blit_texto("MAXIMO", fpeq, (255, 215, 120),
                             panel_nivel.right - 88, 148)
        if c.pendientes > 0:
            self._blit_texto("ELIGE TU MEJORA", fpeq, (255, 230, 140),
                             24, panel_nivel.bottom + 4)
        # Aviso de tienda
        self._blit_texto("[T] TIENDA", fpeq, (250, 210, 90), ANCHO - 150, ALTO - 24)

        # --- Panel de estado (abajo izquierda)
        panel_est = pygame.Rect(14, ALTO - 100, 268, 86)
        self._panel(panel_est, acento=(250, 210, 90))
        self._blit_texto("OLEADA %d" % self.oleada, fch, COL_TEXTO, 26, ALTO - 92)
        self._blit_texto("ENEMIGOS %d" % len(self.enemigos), fpeq,
                         COL_TEXTO_SUAVE, 26, ALTO - 72)
        if self.combo > 1:
            self._blit_texto("x%.1f  COMBO %d" % (multiplicador_combo(self.combo), self.combo),
                             fch, (255, 150, 90), 26, ALTO - 52)
        else:
            self._blit_texto("BAJAS %d" % self.bajas, fpeq, COL_TEXTO_SUAVE,
                             26, ALTO - 52)
        # Monedas de la partida: se ven caer al morir enemigos.
        self._blit_texto("$ %d" % self.cartera.monedas, fpeq, COL_ACENTO,
                         26, ALTO - 32)
        self._blit_texto(str(self.puntaje), fuente, COL_ACENTO,
                         panel_est.right - 14, ALTO - 60, alineacion="der")
        self._blit_texto("PUNTOS", fpeq, COL_TEXTO_SUAVE,
                         panel_est.right - 14, ALTO - 84, alineacion="der")
        self._blit_texto("BAJAS %d" % self.bajas, fpeq, COL_TEXTO_SUAVE,
                         panel_est.right - 14, ALTO - 34, alineacion="der")

        # --- Cargas de dash (abajo centro): una pastilla por carga
        total_cargas = max(1, jug.dash_maximo())
        ancho_pastilla = 46
        separacion = 8
        ancho_total = total_cargas * ancho_pastilla + (total_cargas - 1) * separacion
        x0 = ANCHO // 2 - ancho_total // 2
        for i in range(total_cargas):
            rect = pygame.Rect(x0 + i * (ancho_pastilla + separacion), ALTO - 30,
                               ancho_pastilla, 12)
            if i < jug.dash_cargas:
                self._barra(rect, 1.0, (36, 52, 72), (120, 190, 255))
                pygame.draw.rect(p, (200, 235, 255), rect, 1, border_radius=4)
            elif i == jug.dash_cargas:
                # La carga que se esta recargando
                self._barra(rect, jug.dash_fraccion(), (32, 36, 48), (70, 110, 160))
            else:
                self._barra(rect, 0.0, (32, 36, 48), (32, 36, 48))
        etiqueta_dash = ("DASH LISTO" if jug.puede_dash() else "DASH")
        self._blit_texto(etiqueta_dash, fpeq,
                         (120, 190, 255) if jug.puede_dash() else COL_TEXTO_SUAVE,
                         ANCHO // 2 - 28, ALTO - 46)

        # --- Minimapa (arriba derecha)
        self._dibujar_minimapa()

        # --- Barra del jefe (vale para los cuatro: cada uno con su color)
        jefe = next((e for e in self.enemigos if e.es_jefe), None)
        if jefe is not None:
            w = 460
            x0 = (ANCHO - w) // 2
            rect = pygame.Rect(x0, 22, w, 22)
            pygame.draw.rect(p, (18, 12, 20), rect.inflate(6, 6), border_radius=10)
            self._barra(rect, jefe.vida / jefe.vida_max,
                        _oscuro_50(jefe.color), jefe.color)
            pygame.draw.rect(p, _claro(jefe.color, 0.4), rect, 2, border_radius=8)
            # Brillo en la barra del jefe
            pygame.draw.line(p, (255, 255, 255, 120), (rect.x + 2, rect.y + 2),
                             (rect.right - 2, rect.y + 2), 1)
            nombre = jefe.nombre
            if jefe.fase_jefe == 2:
                # En fase 2 el nombre avisa en rojo: la cosa se pone fea.
                nombre += "  -  FASE 2"
            self._blit_texto(nombre, fpeq, _claro(jefe.color, 0.35), x0, 50)

        # --- Aviso de oleada con desvanecido
        if self.mensaje_oleada > 0:
            restante = self.mensaje_oleada
            alpha = int(255 * min(1.0, min(restante, 150 - restante + 1) / 34.0))
            # La capa oscura se reutiliza en vez de crear una Surface
            # SRCALPHA de 960x640 en cada cuadro. El negro puro con alpha
            # variable no necesita SRCALPHA: basta un fill normal.
            if self._capa_oleada is None:
                self._capa_oleada = pygame.Surface((ANCHO, ALTO))
            capa = self._capa_oleada
            capa.fill((0, 0, 0))
            capa.set_alpha(int(alpha * 0.35))
            p.blit(capa, (0, 0))
            capa.set_alpha(None)
            txt = self._texto("OLEADA %d" % self.oleada, self.fuente_grande, COL_ACENTO)
            txt = txt.copy()
            txt.set_alpha(alpha)
            rect_texto = txt.get_rect(center=(ANCHO // 2, ALTO // 2 - 30))
            p.blit(txt, rect_texto)
            sub = self._texto("PREPARATE", fch, COL_TEXTO_SUAVE).copy()
            sub.set_alpha(alpha)
            p.blit(sub, sub.get_rect(center=(ANCHO // 2, rect_texto.bottom + 12)))

        # --- Ayuda de controles (se apaga a los 12 s)
        if self.oleada == 1 and self.mensaje_oleada > 0:
            ayuda = self._texto(
                "WASD mover   RATON apuntar   CLIC disparar   ESPACIO dash   Q arma   T tienda",
                fpeq, COL_TEXTO_SUAVE)
            p.blit(ayuda, ayuda.get_rect(center=(ANCHO // 2, ALTO - 52)))

    def _dibujar_minimapa(self):
        p = self.pantalla
        if self._minimapa is None or self._minimapa_arena is not self.arena:
            self._minimapa = self._crear_minimapa()
            self._minimapa_arena = self.arena
        mini = self._minimapa
        panel = pygame.Rect(ANCHO - mini.get_width() - 18, 12,
                            mini.get_width() + 8, mini.get_height() + 8)
        self._panel(panel, alpha=190)
        px0, py0 = panel.x + 4, panel.y + 4
        p.blit(mini, (px0, py0))

        esc = ESCALA_MINIMAPA
        # Zonas de peligro: se ven en el minimapa, que es donde se decide
        # hacia donde tirar.
        for aviso in self.avisos:
            if aviso.tipo != "zona":
                continue
            pygame.draw.circle(
                p, aviso.color,
                (px0 + int(aviso.x * esc), py0 + int(aviso.y * esc)),
                max(2, int(aviso.radio * esc)), 1,
            )
        # Enemigos
        for e in self.enemigos:
            ex = px0 + int(e.x * esc)
            ey = py0 + int(e.y * esc)
            if e.es_jefe:
                pygame.draw.circle(p, _claro(e.color, 0.4), (ex, ey), 4)
            else:
                pygame.draw.circle(p, e.color, (ex, ey), 3)
        # Powerups
        for pu in self.powerups:
            pygame.draw.circle(p, COLOR_POWERUP[pu["tipo"]],
                               (px0 + int(pu["x"] * esc), py0 + int(pu["y"] * esc)), 2)
        # Jugador
        jx = px0 + int(self.jugador.x * esc)
        jy = py0 + int(self.jugador.y * esc)
        pygame.draw.circle(p, (120, 190, 255), (jx, jy), 4)
        pygame.draw.circle(p, (235, 245, 255), (jx, jy), 2)
        # Rectangulo del visor
        pygame.draw.rect(
            p, (150, 160, 185),
            pygame.Rect(px0 + int(self.cam_x * esc), py0 + int(self.cam_y * esc),
                        int(ANCHO * esc), int(ALTO * esc)),
            1,
        )

    def _dibujar_tira_armas(self):
        """Tira de armas desbloqueadas con su tecla, arriba a la derecha."""
        arma = self.jugador.arma
        disponibles = arma.disponibles
        if len(disponibles) <= 1:
            return
        p = self.pantalla
        fpeq = self.fuente_peq
        ancho_caja, alto_caja, hueco = 40, 34, 6
        total = len(disponibles) * ancho_caja + (len(disponibles) - 1) * hueco
        x0 = ANCHO - 14 - total
        y0 = 132
        for i, tipo in enumerate(disponibles):
            rect = pygame.Rect(x0 + i * (ancho_caja + hueco), y0, ancho_caja, alto_caja)
            activa = i == arma.indice_actual()
            sup = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(sup, (18, 20, 28, 225 if activa else 150),
                             sup.get_rect(), border_radius=8)
            if activa:
                pygame.draw.rect(sup, ARMAS[tipo]["color"], sup.get_rect(), 2,
                                 border_radius=8)
            p.blit(sup, rect.topleft)
            color = ARMAS[tipo]["color"] if activa else (108, 116, 138)
            img = iconos.obtener(tipo, alto_caja - 8, color)
            p.blit(img, img.get_rect(center=(rect.centerx, rect.centery - 3)))
            p.blit(fpeq.render(str(i + 1), True, COL_TEXTO if activa else COL_TEXTO_SUAVE),
                   fpeq.render(str(i + 1), True, COL_TEXTO).get_rect(
                       midbottom=(rect.centerx, rect.bottom - 1)))

    def _dibujar_habilidades(self):
        """Habilidades desbloqueadas con su tecla y su enfriamiento."""
        if self.cartera is None or not self.cartera.habilidades:
            return
        p = self.pantalla
        fpeq = self.fuente_peq
        lado = 40
        separacion = 8
        lista = self.cartera.habilidades
        total = len(lista) * lado + (len(lista) - 1) * separacion
        x0 = ANCHO // 2 - total // 2
        y0 = 16
        for i, clave in enumerate(lista):
            cfg = progresion.HABILIDADES[clave]
            rect = pygame.Rect(x0 + i * (lado + separacion), y0, lado, lado)
            restante = self.habilidades_cd.get(clave, 0)
            activo = restante <= 0
            sup = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(sup, (18, 20, 28, 225 if activo else 120),
                             sup.get_rect(), border_radius=9)
            pygame.draw.rect(sup, cfg["color"] if activo else (80, 86, 106),
                             sup.get_rect(), 2, border_radius=9)
            p.blit(sup, rect.topleft)
            # Barrido de la barra de enfriamiento, de abajo arriba.
            if restante > 0:
                fraccion = restante / max(1, cfg["enfriamiento"])
                alto_oscuro = int(rect.height * fraccion)
                capa = pygame.Surface((rect.width, alto_oscuro), pygame.SRCALPHA)
                capa.fill((6, 8, 14, 175))
                p.blit(capa, (rect.x, rect.bottom - alto_oscuro))
            img = iconos.obtener(clave, lado - 10,
                                 cfg["color"] if activo else (120, 126, 146))
            p.blit(img, img.get_rect(center=(rect.centerx, rect.centery - 3)))
            if cfg["tecla"]:
                p.blit(fpeq.render(cfg["tecla"], True,
                                   COL_TEXTO if activo else COL_TEXTO_SUAVE),
                       fpeq.render(cfg["tecla"], True, COL_TEXTO).get_rect(
                           midbottom=(rect.centerx, rect.bottom - 2)))
        if self.sobrecarga > 0:
            restantes = self.sobrecarga / 60.0
            p.blit(fpeq.render("SOBRECARGA %.1fs" % restantes, True, (255, 130, 90)),
                   (ANCHO // 2 - 42, y0 + lado + 4))

    def _crear_minimapa(self):
        esc = ESCALA_MINIMAPA
        w = max(1, int(self.arena.ancho * esc))
        h = max(1, int(self.arena.alto * esc))
        surf = pygame.Surface((w, h))
        surf.fill((26, 28, 38))
        lado = max(1, int(TAM_CASILLA * esc))
        for (col, fila) in self.arena.muros:
            surf.fill((84, 88, 110), (int(col * TAM_CASILLA * esc), int(fila * TAM_CASILLA * esc), lado, lado))
        return surf


def _claro(color, f):
    return tuple(min(255, int(c + (255 - c) * f)) for c in color[:3])


def _oscuro_50(color):
    return tuple(max(0, int(c * 0.5)) for c in color[:3])


# ============================================================== bucle raiz
def main():
    pygame.init()
    pygame.display.set_caption("ARENA - shooter cenital")
    # Pantalla completa sin bordes (borderless). Con SCALED el buffer logico
    # sigue siendo ANCHO x ALTO (960x640) y pygame lo escala al tamano del
    # monitor, asi que todo el layout hecho para 960x640 sigue valiendo y el
    # raton se convierte solo a coordenadas logicas.
    pantalla = pygame.display.set_mode((ANCHO, ALTO), pygame.SCALED | pygame.FULLSCREEN)
    reloj = pygame.time.Clock()

    records = puntajes.cargar_puntajes()
    juego = Juego(pantalla, reloj)
    estado = MENU
    ejecutando = True

    while ejecutando:
        if estado == MENU:
            opcion = pantallas.pantalla_inicio(pantalla, reloj, ANCHO, ALTO, records)
            if opcion == 0:
                # Roguelite: cada partida arranca con la cartera a cero.
                juego.reiniciar()
                estado = JUGANDO
            elif opcion == 1:
                pantallas.pantalla_records(pantalla, reloj, ANCHO, ALTO, records)
            else:
                ejecutando = False
            continue

        if estado == PAUSA:
            opcion = pantallas.pantalla_pausa(pantalla, reloj, ANCHO, ALTO)
            estado = JUGANDO if opcion == 0 else MENU
            continue

        # Tienda en partida: pausa el combate y deja comprar con las monedas
        # de la run. Al cerrar, se sigue jugando exactamente igual.
        if estado == TIENDA:
            opcion = pantallas.pantalla_tienda(pantalla, reloj, ANCHO, ALTO, juego)
            estado = JUGANDO if opcion != -1 else MENU
            if opcion == -1:
                ejecutando = False
            continue

        # Subida de nivel: 3 cartas aleatorias, una sola por pantalla.
        if estado == SUBA_NIVEL:
            opcion = pantallas.pantalla_subida(pantalla, reloj, ANCHO, ALTO, juego)
            if opcion == -1:
                estado = MENU
                ejecutando = False
            # Si una baja dio varias subidas, se resuelven seguidas sin dejar
            # pasar un frame de juego entre cartas: el combate sigue congelado.
            elif juego.cartera.pendientes > 0:
                estado = SUBA_NIVEL
            else:
                estado = JUGANDO
            continue

        if estado == MUERTO:
            records = puntajes.cargar_puntajes()
            previo = records[0]["puntaje"] if records else 0
            record = int(juego.puntaje) > previo
            if record:
                records = puntajes.guardar_puntaje(
                    juego.puntaje, juego.oleada, date.today().isoformat()
                )
            opcion = pantallas.pantalla_game_over(
                pantalla, reloj, ANCHO, ALTO,
                puntaje=int(juego.puntaje), oleada=juego.oleada, record=record,
                bajas=juego.bajas, combo=juego.mejor_combo,
                build=juego.cartera.resumen(),
            )
            if opcion == 0:
                juego.reiniciar()
                estado = JUGANDO
            else:
                estado = MENU
            continue

        # --------------------------------------------------------- jugando
        teclas = pygame.key.get_pressed()
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                ejecutando = False
            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    estado = PAUSA
                elif evento.key == pygame.K_t:
                    # La tienda en partida
                    estado = TIENDA
                elif evento.key == pygame.K_SPACE:
                    if juego.jugador.intentar_dash(*direccion_movimiento(teclas)):
                        juego.particulas.dash(
                            juego.jugador.x, juego.jugador.y, juego.jugador.angulo
                        )
                elif evento.key == pygame.K_q:
                    juego.jugador.arma.cambiar_arma(1)
                elif evento.key == pygame.K_e:
                    juego.usar_habilidad("nova")
                elif evento.key == pygame.K_r:
                    juego.usar_habilidad("tormenta")
                elif evento.key == pygame.K_f:
                    juego.usar_habilidad("sobrecarga")
                elif pygame.K_1 <= evento.key <= pygame.K_8:
                    # Seleccion directa de arma por numero.
                    juego.jugador.arma.seleccionar(evento.key - pygame.K_1)
            elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 3:
                if juego.jugador.intentar_dash(*direccion_movimiento(teclas)):
                    juego.particulas.dash(
                        juego.jugador.x, juego.jugador.y, juego.jugador.angulo
                    )
        if not ejecutando:
            break

        mouse_pos = pygame.mouse.get_pos()
        disparo = pygame.mouse.get_pressed()[0] or teclas[pygame.K_j]

        juego.actualizar(teclas, mouse_pos, disparo)
        juego.dibujar()
        pygame.display.flip()
        reloj.tick(FPS)

        if juego.jugador.vida <= 0:
            estado = MUERTO
        elif juego.cartera.pendientes > 0:
            # Las subidas de nivel se eligen una a una: la cola se descuenta
            # en pantalla_subida, asi que aqui solo hay que entrar.
            estado = SUBA_NIVEL

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()

