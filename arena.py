# -*- coding: utf-8 -*-
"""
arena.py
========
Arena del shooter cenital (vista cenital / top-down).

Genera una arena con muros perimetrales, salas con una sola entrada y
pilares sueltos. El suelo con sus detalles se dibuja una unica vez en
una superficie fuera de pantalla (mucho mas rapido que repintar celda a
celda) y en cada frame solo se hace un blit de la zona visible.

Tambien ofrece consultas de colision por circulo con deslizamiento, un
campo de flujo para que las unidades grandes rodeen los muros, y puntos
de aparicion con holgura segun el tamano de la unidad.
"""

import math
import random
from collections import deque

import pygame

TAM_CASILLA = 32

# Paleta de la arena
COL_FONDO = (13, 13, 19)
COL_SUELO = (38, 40, 52)
COL_SUELO_ALT = (44, 46, 60)
COL_SUELO_LINEA = (32, 34, 45)
COL_MURO = (86, 90, 112)
COL_MURO_TOP = (118, 123, 150)
COL_MURO_SOMBRA = (48, 50, 66)
COL_MURO_LINEA = (52, 55, 72)
COL_BORDE = (30, 30, 42)

# Detalles pintados en el suelo (no colisionan, solo dan profundidad)
COL_MARCA = (58, 60, 76)
COL_PELIGRO = (86, 76, 44)
COL_REJILLA = (52, 54, 70)
COL_PAD = (56, 70, 84)


class Arena:
    def __init__(self, filas=30, cols=44, semilla=None):
        self.filas = filas
        self.cols = cols
        self.ancho = cols * TAM_CASILLA
        self.alto = filas * TAM_CASILLA
        self.rng = random.Random(semilla)
        # Se guarda la semilla para que lo que se genere aparte del mapa
        # (decoracion, luces) salga igual en dos arenas con la misma semilla.
        self.semilla = semilla
        self.muros = set()
        self._generar()
        self.suelo = None
        self._decoraciones = self._preparar_decoraciones()

    # ------------------------------------------------------------ generar
    def _generar(self):
        for col in range(self.cols):
            self.muros.add((col, 0))
            self.muros.add((col, self.filas - 1))
        for fila in range(self.filas):
            self.muros.add((0, fila))
            self.muros.add((self.cols - 1, fila))

        # Salas rectangulares con una entrada (crean cobertura y rutas).
        for _ in range(5):
            w = self.rng.randint(4, 8)
            h = self.rng.randint(3, 6)
            if w + 4 >= self.cols or h + 4 >= self.filas:
                continue
            c0 = self.rng.randint(2, self.cols - w - 3)
            f0 = self.rng.randint(2, self.filas - h - 3)
            self._pintar_sala(c0, f0, w, h)

        # Pilares sueltos.
        for _ in range(10):
            c = self.rng.randint(1, self.cols - 2)
            f = self.rng.randint(1, self.filas - 2)
            self.muros.add((c, f))
            if self.rng.random() < 0.4:
                self.muros.add((c + 1, f))

    def _pintar_sala(self, c0, f0, w, h):
        for c in range(c0, c0 + w):
            self.muros.add((c, f0))
            self.muros.add((c, f0 + h - 1))
        for f in range(f0, f0 + h):
            self.muros.add((c0, f))
            self.muros.add((c0 + w - 1, f))

        # Una sola puerta por sala.
        lado = self.rng.choice(("arriba", "abajo", "izq", "der"))
        if lado == "arriba":
            self.muros.discard((self.rng.randint(c0 + 1, c0 + w - 2), f0))
        elif lado == "abajo":
            self.muros.discard((self.rng.randint(c0 + 1, c0 + w - 2), f0 + h - 1))
        elif lado == "izq":
            self.muros.discard((c0, self.rng.randint(f0 + 1, f0 + h - 2)))
        else:
            self.muros.discard((c0 + w - 1, self.rng.randint(f0 + 1, f0 + h - 2)))

        # Mobiliario interior.
        for _ in range(self.rng.randint(0, 3)):
            c = self.rng.randint(c0 + 1, c0 + w - 2)
            f = self.rng.randint(f0 + 1, f0 + h - 2)
            self.muros.add((c, f))

    def _preparar_decoraciones(self):
        """Detalles de suelo, con semilla estable por celda."""
        detalles = []
        for col, fila in self.celdas_libres():
            r = random.Random((col * 73856093) ^ (fila * 19349663))
            detalles.append((col, fila, r.random(), r.random()))
        return detalles

    # --------------------------------------------------------- consultas
    def celda_bloqueada(self, col, fila):
        if col < 0 or fila < 0 or col >= self.cols or fila >= self.filas:
            return True
        return (col, fila) in self.muros

    def punto_libre(self, px, py):
        return not self.celda_bloqueada(int(px // TAM_CASILLA), int(py // TAM_CASILLA))

    def circulo_libre(self, x, y, radio):
        """Colision exacta circulo contra las celdas bloqueadas cercanas.

        Antes se comprobaban solo 9 puntos sueltos del circulo: eso dejaba
        puntos sin verificar (barreras invisibles) y permitia que las unidades
        se metieran a medias dentro de los muros. Aqui se calcula la distancia
        real del centro al rectangulo de cada celda, asi el resultado es
        continuo y el muro nunca se atraviesa ni se solapa.
        """
        c0 = int(math.floor((x - radio) / TAM_CASILLA))
        c1 = int(math.floor((x + radio) / TAM_CASILLA))
        f0 = int(math.floor((y - radio) / TAM_CASILLA))
        f1 = int(math.floor((y + radio) / TAM_CASILLA))
        r2 = radio * radio
        T = float(TAM_CASILLA)
        for col in range(c0, c1 + 1):
            bx = col * TAM_CASILLA
            ex = x - bx
            if ex < 0.0:
                ex = -ex          # centro a la izquierda de la celda
            elif ex > T:
                ex -= T           # centro a la derecha
            else:
                ex = 0.0          # dentro en X: no aporta distancia
            if ex >= radio:
                continue
            for fila in range(f0, f1 + 1):
                if not self.celda_bloqueada(col, fila):
                    continue
                ey = y - fila * TAM_CASILLA
                if ey < 0.0:
                    ey = -ey
                elif ey > T:
                    ey -= T
                else:
                    ey = 0.0
                if ex * ex + ey * ey < r2:
                    return False
        return True

    def centrar(self, x, y, radio):
        """Lleva el punto al centro de su celda (siempre valido si la celda
        esta libre), para sacar a una unidad que ha quedado encajada."""
        col, fila = self.celda_de(x, y)
        if self.celda_bloqueada(col, fila):
            libre = self._celda_libre_cerca(col, fila)
            if libre is None:
                return x, y
            col, fila = libre
        return self.centro_celda(col, fila)

    def mover(self, x, y, dx, dy, radio):
        # Resolver por ejes permite deslizarse a lo largo de las paredes.
        if self.circulo_libre(x + dx, y, radio):
            x += dx
        if self.circulo_libre(x, y + dy, radio):
            y += dy
        return x, y

    def linea_libre(self, x0, y0, x1, y1):
        pasos = int(max(abs(x1 - x0), abs(y1 - y0)) / 8) + 1
        for i in range(pasos + 1):
            t = i / pasos
            if not self.punto_libre(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
                return False
        return True

    def celdas_libres(self):
        for fila in range(1, self.filas - 1):
            for col in range(1, self.cols - 1):
                if (col, fila) not in self.muros:
                    yield col, fila

    # ------------------------------------------------- camino hacia el objetivo
    def celda_de(self, px, py):
        return int(px // TAM_CASILLA), int(py // TAM_CASILLA)

    def centro_celda(self, col, fila):
        return col * TAM_CASILLA + TAM_CASILLA / 2, fila * TAM_CASILLA + TAM_CASILLA / 2

    def _celda_libre_cerca(self, col, fila, radio=4):
        for r in range(1, radio + 1):
            for dc in range(-r, r + 1):
                for df in range(-r, r + 1):
                    if max(abs(dc), abs(df)) != r:
                        continue
                    destino = (col + dc, fila + df)
                    if not self.celda_bloqueada(*destino):
                        return destino
        return None

    def campo_flujo(self, px, py):
        """Campo de direcciones hacia (px, py).

        BFS desde la celda del objetivo: {celda: celda siguiente en el camino}.
        Permite que unidades grandes rodeen muros en vez de encajarse.
        """
        origen = self.celda_de(px, py)
        if self.celda_bloqueada(*origen):
            cercano = self._celda_libre_cerca(*origen)
            if cercano is None:
                return {}
            origen = cercano

        campo = {origen: None}
        cola = deque([origen])
        while cola:
            col, fila = cola.popleft()
            for dc, df in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                destino = (col + dc, fila + df)
                if destino in campo or self.celda_bloqueada(*destino):
                    continue
                campo[destino] = (col, fila)
                cola.append(destino)
        return campo

    def direccion_campo(self, campo, px, py):
        """Vector unitario hacia la siguiente celda del camino (o el centro)."""
        if not campo:
            return 0.0, 0.0
        celda = self.celda_de(px, py)
        siguiente = campo.get(celda)
        if siguiente is None:
            # La unidad esta dentro de un muro: ir a la celda visitada mas
            # cercana, que es la unica forma de salir de ahi.
            siguiente = self._celda_visitada_mas_cercana(campo, celda)
        if siguiente is None:
            return 0.0, 0.0
        objetivo = self.centro_celda(*siguiente)
        dx = objetivo[0] - px
        dy = objetivo[1] - py
        m = math.hypot(dx, dy)
        if m < 0.0001:
            return 0.0, 0.0
        return dx / m, dy / m

    def _celda_visitada_mas_cercana(self, campo, celda):
        """Celda visitada mas cercana (distancia euclidea), buscando en anillos.

        Antes recorria el campo entero comparando distancias: con ~1100 celdas
        libres son ~1100 iteraciones cada vez que una unidad se mete en un
        muro, y en melee pasaba a cada frame.

        Ahora se expande en anillos de Chebyshev (cuadrados crecientes). Ojo
        con el criterio de parada: los anillos son Chebyshev pero la distancia
        que importa es euclidea, y una celda del anillo 1 puede estar mas lejos
        que otra del anillo 2. Asi que no vale con parar en el primer anillo
        con resultado; hay que seguir mientras el anillo actual (radio r) no
        garantice que nada mas lejos pueda ganar, es decir mientras r^2 <= mejor_d
        (toda celda del anillo r o superior esta a distancia >= r).
        """
        if celda in campo:
            return None
        cc, cf = celda
        mejor = None
        mejor_d = None
        # El limite de anillos tiene que cubrir toda la rejilla: si se corta
        # antes, una celda en una esquina podria quedarse sin candidato y
        # devolver None con el campo lleno de celdas validas.
        limite = max(cc, self.cols - 1 - cc, cf, self.filas - 1 - cf) + 1
        for radio in range(1, limite + 1):
            # Perimetro del cuadrado de lado 2*radio+1, sin repetir el interior
            # que ya se miro en anillos menores. Ojo: esto es un anillo de
            # Chebyshev (las cuatro aristas del cuadrado), NO un rombo: una
            # resta del tipo radio - abs(dc) recorreria solo la diagonal y
            # dejaria sin visitar las esquinas, que son justamente celdas
            # perfectamente validas.
            borde = []
            for dc in range(-radio, radio + 1):
                borde.append((cc + dc, cf - radio))
            for dc in range(-radio, radio + 1):
                borde.append((cc + dc, cf + radio))
            for df in range(-radio + 1, radio):
                borde.append((cc - radio, cf + df))
                borde.append((cc + radio, cf + df))
            for candidato in borde:
                if candidato in campo:
                    d = self._dist2(candidato, celda)
                    if mejor_d is None or d < mejor_d:
                        mejor_d = d
                        mejor = candidato
            # Parada correcta: toda celda de los anillos r o posteriores esta a
            # distancia euclidea >= r. Si ya tenemos mejor y r^2 > mejor_d,
            # ningun anillo posterior puede mejorar lo que ya tenemos.
            #
            # El radio actual ya ha recorrido por completo, asi que la garantia
            # vale para r+1: se necesita r^2 >= mejor_d para poder parar.
            if mejor_d is not None and radio * radio >= mejor_d:
                break
        return mejor

    @staticmethod
    def _dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    def punto_spawn(self, lejos_de, distancia_min=300, radio=0):
        opciones = []
        holgura = max(radio, 10)
        for col, fila in self.celdas_libres():
            px = col * TAM_CASILLA + TAM_CASILLA / 2
            py = fila * TAM_CASILLA + TAM_CASILLA / 2
            d = math.hypot(px - lejos_de[0], py - lejos_de[1])
            if d >= distancia_min and self.circulo_libre(px, py, holgura):
                opciones.append((d, px, py))
        if not opciones:
            # Sin huecos con holgura: vale cualquier celda libre.
            for col, fila in self.celdas_libres():
                px = col * TAM_CASILLA + TAM_CASILLA / 2
                py = fila * TAM_CASILLA + TAM_CASILLA / 2
                d = math.hypot(px - lejos_de[0], py - lejos_de[1])
                if d >= distancia_min:
                    opciones.append((d, px, py))
        if not opciones:
            return TAM_CASILLA * 2, TAM_CASILLA * 2
        # No todos en el rincon mas lejano: elige al azar entre los mas alejados.
        mas_lejos = max(o[0] for o in opciones)
        candidatos = [o for o in opciones if o[0] >= mas_lejos * 0.75]
        _, px, py = self.rng.choice(candidatos)
        return px, py

    # ------------------------------------------------- pintura del escenario
    def _preparar_suelo(self):
        """Pinta el escenario completo una vez en una superficie cacheada."""
        surf = pygame.Surface((self.ancho, self.alto))
        surf.fill(COL_FONDO)
        T = TAM_CASILLA

        # 1) Baldosas del suelo
        # El grano usa su propio RNG, no self.rng: si el horneado del suelo
        # consumiera|del self.rng, cada baldosa de detalle desplazaria la
        # secuencia de spawns y dos arenas con la misma semilla jugarían
        # distinto. self.rng es solo para el gameplay.
        rng_grano = random.Random((self.semilla or 0) ^ 0xA11CE)
        # Cuanto puede apartarse una baldosa de su color base.
        VAR_BALDOSA = 5
        # Puntos de granulado por baldosa.
        GRANO = 7

        def _matiz(base, d):
            return (max(0, min(255, base[0] + d)),
                    max(0, min(255, base[1] + d)),
                    max(0, min(255, base[2] + d)))

        for fila in range(self.filas):
            for col in range(self.cols):
                if (col, fila) in self.muros:
                    continue
                x, y = col * T, fila * T
                alterna = (col + fila) % 2 == 0
                base = COL_SUELO_ALT if alterna else COL_SUELO
                # Variacion por baldosa antes del marco: si se tintase despues,
                # el relleno se comeria la linea de la baldosa y el suelo
                # quedaria como manchas sin retícula.
                surf.fill(_matiz(base, rng_grano.randint(-VAR_BALDOSA, VAR_BALDOSA)),
                          (x, y, T, T))
                pygame.draw.rect(surf, COL_SUELO_LINEA, (x, y, T, T), 1)
                if alterna:
                    # Bisel interior suave en las baldosas claras
                    pygame.draw.line(surf, COL_SUELO_ALT, (x + 1, y + 1), (x + T - 1, y + 1))
                    pygame.draw.line(surf, COL_SUELO_ALT, (x + 1, y + 1), (x + 1, y + T - 1))
                # Granulado fino. Va con margen de 2 px para no pisar el marco,
                # y sobre todo en oscuro, que es como se lee el hormigon.
                for _ in range(GRANO):
                    gx = x + 2 + rng_grano.randrange(T - 4)
                    gy = y + 2 + rng_grano.randrange(T - 4)
                    if rng_grano.random() < 0.82:
                        surf.fill(_matiz(base, -rng_grano.randint(6, 13)), (gx, gy, 1, 1))
                    else:
                        surf.fill(_matiz(base, rng_grano.randint(5, 10)), (gx, gy, 1, 1))

        # 2) Marcas pintadas en el suelo
        for col, fila, v1, v2 in self._decoraciones:
            x, y = col * T, fila * T
            if v1 < 0.10:  # franjas de peligro
                for k in range(-T, T, 10):
                    pygame.draw.line(surf, COL_PELIGRO, (x + k, y + T), (x + k + T, y), 2)
            elif v1 < 0.18:  # rejilla
                for k in range(4, T, 8):
                    pygame.draw.line(surf, COL_REJILLA, (x + 2, y + k), (x + T - 2, y + k))
            elif v1 < 0.26:  # plataforma circular
                pygame.draw.circle(surf, COL_PAD, (x + T // 2, y + T // 2), 11, 1)
                pygame.draw.circle(surf, COL_PAD, (x + T // 2, y + T // 2), 4)
            elif v1 < 0.32 and v2 < 0.5:  # lineas de circulacion
                pygame.draw.line(surf, COL_MARCA, (x + 4, y + 6), (x + T - 4, y + 6), 1)
                pygame.draw.line(surf, COL_MARCA, (x + 4, y + 10), (x + T - 4, y + 10), 1)

        # 3) Sombra proyectada por los muros sobre el suelo
        for col, fila in self.celdas_libres():
            x, y = col * T, fila * T
            if (col, fila - 1) in self.muros:
                for k in range(7):
                    f = 1 - k / 7
                    color = (int(COL_SUELO[0] * f), int(COL_SUELO[1] * f), int(COL_SUELO[2] * f))
                    pygame.draw.line(surf, color, (x, y + k), (x + T, y + k))

        # 4) Muros con cara superior, sombra inferior y contorno
        for (col, fila) in self.muros:
            x, y = col * T, fila * T
            rect = (x, y, T, T)
            pygame.draw.rect(surf, COL_MURO, rect)
            pygame.draw.rect(surf, COL_MURO_TOP, (x, y, T, 9))
            pygame.draw.rect(surf, COL_MURO_SOMBRA, (x, y + T - 6, T, 6))
            pygame.draw.rect(surf, COL_MURO_LINEA, rect, 1)
            # Junta entre baldosas del muro
            pygame.draw.line(surf, COL_MURO_SOMBRA, (x, y + T // 2), (x + T, y + T // 2))

        # 5) Borde exterior de la arena
        pygame.draw.rect(surf, COL_BORDE, (0, 0, self.ancho, self.alto), 4)
        self.suelo = surf

    def dibujar(self, pantalla, cam_x, cam_y, ancho_visor, alto_visor):
        if self.suelo is None:
            self._preparar_suelo()
        # Correspondencia mundo -> pantalla: pantalla = mundo - camara.
        # El destino se calcula siempre con la camara (no con el origen
        # recortado), asi el suelo y las entidades nunca se desfasan, ni
        # siquiera cuando el temblor saca la vista de la arena por un borde.
        cx, cy = int(math.floor(cam_x)), int(math.floor(cam_y))
        sx, sy = max(0, cx), max(0, cy)
        ex = min(self.ancho, cx + ancho_visor + 8)
        ey = min(self.alto, cy + alto_visor + 8)
        if ex > sx and ey > sy:
            pantalla.blit(self.suelo, (sx - cx, sy - cy), (sx, sy, ex - sx, ey - sy))
