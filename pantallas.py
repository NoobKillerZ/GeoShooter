# -*- coding: utf-8 -*-
"""
pantallas.py
============
Pantallas de interfaz del shooter cenital: inicio, tienda, records, pausa y
game over. Cada pantalla expone varios botones; el bucle devuelve el
indice del boton pulsado (-1 si se cierra la ventana o se pulsa ESC).
"""

import math
import random

import pygame

import armas
import iconos
import progresion

COL_PANEL = (16, 17, 24, 210)
COL_PANEL_BORDE = (58, 62, 82)
COL_TITULO = (250, 210, 90)
COL_TEXTO = (228, 234, 246)
COL_TENUE = (138, 146, 168)


class Boton:
    def __init__(self, texto, x, y, ancho, alto, fuente):
        self.texto = texto
        self.rect = pygame.Rect(x, y, ancho, alto)
        self.fuente = fuente
        self.mouse_sobre = False

    def contiene(self, pos):
        return self.rect.collidepoint(pos)

    def dibujar(self, pantalla, t=0.0):
        if self.mouse_sobre:
            # Relleno + halo pulsante
            relleno = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.rect(relleno, (250, 210, 90, 46), relleno.get_rect(), border_radius=12)
            pygame.draw.rect(relleno, (250, 210, 90, 120), relleno.get_rect(), 2, border_radius=12)
            pantalla.blit(relleno, self.rect.topleft)
            color = (255, 238, 190)
        else:
            color = COL_TENUE
        pygame.draw.rect(pantalla, color, self.rect, 2, border_radius=12)
        texto = self.fuente.render(self.texto, True, color)
        pantalla.blit(texto, texto.get_rect(center=self.rect.center))


def _panel(pantalla, rect, alpha=210, borde=COL_PANEL_BORDE):
    sup = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(sup, (COL_PANEL[0], COL_PANEL[1], COL_PANEL[2], alpha),
                     sup.get_rect(), border_radius=14)
    pygame.draw.rect(sup, borde, sup.get_rect(), 1, border_radius=14)
    pantalla.blit(sup, rect.topleft)


def _bucle(pantalla, reloj, botones, dibujar, predibujar=None, indice_escape=-1):
    """Bucle bloqueante de una pantalla. Devuelve el indice del boton."""
    while True:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                return -1
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    return indice_escape
                if evento.key == pygame.K_RETURN and botones:
                    return 0
            if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                for i, boton in enumerate(botones):
                    if boton.contiene(evento.pos):
                        return i

        mouse = pygame.mouse.get_pos()
        for boton in botones:
            boton.mouse_sobre = boton.contiene(mouse)

        if predibujar is not None:
            predibujar()
        dibujar(pantalla)
        pygame.display.flip()
        reloj.tick(60)


class FondoAnimado:
    """Fondo con motas a la deriva y rejilla en scroll: da vida al menu."""

    def __init__(self, ancho, alto, particulas=70):
        self.ancho = ancho
        self.alto = alto
        self.motas = [
            (random.uniform(0, ancho), random.uniform(0, alto),
             random.uniform(0.3, 1.6), random.uniform(0.15, 0.6))
            for _ in range(particulas)
        ]
        self.desplazamiento = 0.0

    def actualizar(self):
        self.desplazamiento = (self.desplazamiento + 0.35) % 48
        for i, (x, y, r, v) in enumerate(self.motas):
            y -= v
            if y < -4:
                y = self.alto + 4
                x = random.uniform(0, self.ancho)
            self.motas[i] = (x, y, r, v)

    def dibujar(self, pantalla, color_fondo=(11, 12, 18), color_linea=(24, 27, 38)):
        pantalla.fill(color_fondo)
        d = int(self.desplazamiento)
        for x in range(-d, self.ancho + 48, 48):
            pygame.draw.line(pantalla, color_linea, (x, 0), (x, self.alto))
        for y in range(-d, self.alto + 48, 48):
            pygame.draw.line(pantalla, color_linea, (0, y), (self.ancho, y))
        for x, y, r, _ in self.motas:
            a = 70 if r > 1.0 else 45
            pygame.draw.circle(pantalla, (color_linea[0] + a, color_linea[1] + a,
                                          color_linea[2] + a + 20), (int(x), int(y)), int(r))
        # Halo central suave
        halo = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        for r in range(300, 0, -12):
            a = int(3 * (1 - r / 300))
            pygame.draw.circle(halo, (70, 90, 140, a), (self.ancho // 2, self.alto // 2 - 40), r)
        pantalla.blit(halo, (0, 0))


CONTROLES = [
    ("WASD / FLECHAS  MOVER", "RATON  APUNTAR"),
    ("CLIC IZQ  DISPARAR", "ESPACIO / CLIC DER  DASH"),
    ("Q / 1-8  CAMBIAR ARMA", "T  TIENDA"),
    ("E NOVA   R TORMENTA", "F SOBRECARGA"),
]
RECORDATORIO = (
    "WASD MOVER     RATON APUNTAR     CLIC DISPARAR",
    "ESPACIO DASH     Q ARMA     T TIENDA     ESC PAUSA",
)

COL_MONEDA = (250, 210, 90)
COL_OK = (120, 240, 150)
COL_CARO = (235, 110, 110)
COL_MAX = (150, 160, 190)


def _barra(p, rect, fraccion, color_fondo, color_relleno):
    """Barra de progreso con el borde redondeado."""
    fraccion = max(0.0, min(1.0, fraccion))
    pygame.draw.rect(p, color_fondo, rect, border_radius=rect.height // 2)
    relleno = int(rect.width * fraccion)
    if relleno > 0:
        pygame.draw.rect(p, color_relleno,
                         pygame.Rect(rect.x, rect.y, relleno, rect.height),
                         border_radius=rect.height // 2)


def _envolver(fuente, texto, ancho_max, max_lineas=3):
    """Parte un texto en lineas que caben en ancho_max."""
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = palabra if not actual else actual + " " + palabra
        if fuente.size(prueba)[0] <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
            if len(lineas) == max_lineas - 1:
                break
    if actual and len(lineas) < max_lineas:
        lineas.append(actual)
    if len(lineas) == max_lineas and palabras:
        # Recorta la ultima linea con puntos suspensivos si se paso.
        while lineas and fuente.size(lineas[-1] + "...")[0] > ancho_max:
            lineas[-1] = lineas[-1][:-1].rstrip()
        texto = " ".join(lineas)
        if texto != texto.rstrip() + "..." and len(texto) < len(" ".join(palabras)):
            lineas[-1] = lineas[-1] + "..."
    return lineas


def _datos_tienda(cartera):
    """Los tres listados de la tienda, resueltos a datos listos para dibujar."""
    mejoras = []
    for clave in progresion.ORDEN_MEJORAS:
        cfg = progresion.MEJORAS[clave]
        nivel = cartera.nivel_mejora(clave)
        coste = cartera.costo_mejora(clave)
        if coste is None:
            estado = "max"
        elif cartera.puede_pagar(coste):
            estado = "ok"
        else:
            estado = "caro"
        mejoras.append({
            "clave": clave, "nombre": cfg["nombre"], "desc": cfg["desc"],
            "icono": cfg["icono"], "color": cfg["color"], "coste": coste,
            "estado": estado, "nivel": nivel, "max": cfg["max"],
            "pie": "NIVEL %d / %d" % (nivel, cfg["max"]),
        })

# La pistola viene de serie; el resto del arsenal se compra con lo que
# ganas en la partida. No hay nada guardado entre partidas.
    arsenal = []
    clave = "pistola"
    cfg = armas.ARMAS[clave]
    arsenal.append({
        "clave": clave, "nombre": cfg["nombre"],
        "desc": "arma inicial", "icono": cfg.get("icono", "*"),
        "color": cfg["color"], "coste": 0, "estado": "comprado",
        "nivel": 1, "max": 1, "pie": "INICIAL",
    })
    for clave in progresion.ORDEN_ARSENAL:
        cfg = progresion.ARSENAL[clave]
        comprada = cartera.arma_desbloqueada(clave)
        if comprada:
            estado = "comprado"
        elif cartera.puede_pagar(cfg["costo"]):
            estado = "ok"
        else:
            estado = "caro"
        arsenal.append({
            "clave": clave, "nombre": cfg["nombre"], "desc": cfg["desc"],
            "icono": cfg["icono"], "color": cfg["color"], "coste": cfg["costo"],
            "estado": estado, "nivel": 1, "max": 1,
            "pie": "DESBLOQUEADO" if comprada else "NUEVO",
        })

    habilidades = []
    for clave in progresion.ORDEN_HABILIDADES:
        cfg = progresion.HABILIDADES[clave]
        activa = cartera.habilidad_activa(clave)
        if activa:
            estado = "comprado"
        elif cartera.puede_pagar(cfg["costo"]):
            estado = "ok"
        else:
            estado = "caro"
        habilidades.append({
            "clave": clave, "nombre": cfg["nombre"], "desc": cfg["desc"],
            "icono": cfg["icono"], "color": cfg["color"], "coste": cfg["costo"],
            "estado": estado, "nivel": 1, "max": 1,
            "pie": "ACTIVA" if activa else ("TECLA " + cfg["tecla"] if cfg["tecla"]
                                            else "PASIVA"),
        })
    return mejoras, arsenal, habilidades


def layout_tienda(ancho, alto):
    """Zonas de la tienda. Se calculan juntas para que nunca se solapen."""
    margen = 40
    pestanas = [
        pygame.Rect(ancho // 2 - 300 + i * 200, 82, 190, 34)
        for i in range(3)
    ]
    # La zona de tarjetas deja margen arriba (cabeceras y pestanas) y abajo
    # (boton volver y ayuda), y se centra en lo que queda.
    zona = pygame.Rect(margen, 132, ancho - margen * 2, alto - 132 - 74)
    columnas = 4
    filas = 3
    hueco = 12
    ancho_tarjeta = (zona.width - hueco * (columnas - 1)) // columnas
    alto_tarjeta = (zona.height - hueco * (filas - 1)) // filas
    return {
        "pestanas": pestanas,
        "zona": zona,
        "columnas": columnas,
        "filas": filas,
        "huesco": hueco,
        "tarjeta": (ancho_tarjeta, alto_tarjeta),
    }


def _color_estado(estado):
    return {"ok": COL_OK, "caro": COL_CARO, "max": COL_MAX,
            "comprado": COL_MONEDA}.get(estado, COL_TENUE)


def pantalla_subida(pantalla, reloj, ancho, alto, juego):
    """Subida de nivel: 3 cartas al azar y eliges una. Gratis, sin monedas."""
    f_titulo = pygame.font.SysFont("consolas", 46, bold=True)
    f_sub = pygame.font.SysFont("consolas", 19)
    f_nombre = pygame.font.SysFont("consolas", 20, bold=True)
    f_desc = pygame.font.SysFont("consolas", 14)
    f_tecla = pygame.font.SysFont("consolas", 15)
    cartas = juego.cartas_nivel()
    sel = [0]
    raton = [pygame.mouse.get_pos()]
    n = max(1, len(cartas))

    # Las cartas se dimensionan para que TODAS quepan siempre, centradas,
    # sea cual sea el numero y el tamano de la ventana. Antes el ancho era
    # fijo (248) y con 3 cartas sobraba margen pero con mas se salian.
    margen_x = 40
    margen_sup = 150
    margen_inf = 60
    hueco = 22
    disponible_x = ancho - margen_x * 2
    disponible_y = alto - margen_sup - margen_inf
    # Ancho maximo por carta, pero sin pasarse de lo que hay disponible.
    ancho_carta = min(248, (disponible_x - (n - 1) * hueco) // n)
    alto_carta = min(268, disponible_y)
    total = n * ancho_carta + (n - 1) * hueco
    x0 = ancho // 2 - total // 2
    y_carta = margen_sup + (disponible_y - alto_carta) // 2

    def rect_carta(i):
        return pygame.Rect(x0 + i * (ancho_carta + hueco), y_carta, ancho_carta, alto_carta)

    def predibujar():
        juego.dibujar()
        velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        velo.fill((6, 7, 12, 200))
        pantalla.blit(velo, (0, 0))

    def dibujar(p):
        t = pygame.time.get_ticks() / 400.0
        mouse = raton[0]
        titulo = f_titulo.render("NIVEL %d" % juego.cartera.nivel, True, (150, 220, 255))
        # El titulo late un poco: es la recompensa del nivel.
        escala = 1.0 + 0.05 * math.sin(t * 2.2)
        if abs(escala - 1.0) > 0.006:
            titulo = pygame.transform.smoothscale(
                titulo,
                (int(titulo.get_width() * escala), int(titulo.get_height() * escala)),
            )
        p.blit(titulo, titulo.get_rect(center=(ancho // 2, 96)))
        sub = f_sub.render("ELIGE UNA MEJORA", True, COL_TENUE)
        p.blit(sub, sub.get_rect(center=(ancho // 2, 128)))

        for i, carta in enumerate(cartas):
            rect = rect_carta(i)
            enfocada = i == sel[0]
            hover = rect.collidepoint(mouse)
            _panel(p, rect, alpha=235 if (hover or enfocada) else 195)
            pygame.draw.rect(p, carta["color"] if enfocada else COL_PANEL_BORDE,
                             rect, 3 if enfocada else 1, border_radius=14)
            # Halo cuando esta enfocada
            if enfocada:
                halo = pygame.Surface((rect.width + 12, rect.height + 12),
                                      pygame.SRCALPHA)
                pygame.draw.rect(halo, (*carta["color"], 40), halo.get_rect(),
                                 border_radius=18)
                p.blit(halo, (rect.x - 6, rect.y - 6))

            pygame.draw.circle(p, (30, 32, 44), (rect.centerx, rect.y + 56), 30)
            pygame.draw.circle(p, carta["color"], (rect.centerx, rect.y + 56), 30, 2)
            img = iconos.obtener(carta["icono"], 56, carta["color"])
            p.blit(img, img.get_rect(center=(rect.centerx, rect.y + 56)))

            etiqueta = "HABILIDAD" if carta["tipo"] == "habilidad" else "MEJORA"
            img_tipo = f_tecla.render(etiqueta, True, COL_TENUE)
            p.blit(img_tipo, img_tipo.get_rect(center=(rect.centerx, rect.y + 100)))

            nombre = f_nombre.render(carta["nombre"], True, COL_TEXTO)
            p.blit(nombre, nombre.get_rect(center=(rect.centerx, rect.y + 128)))

            y = rect.y + 150
            for linea in _envolver(f_desc, carta["desc"], rect.width - 24, 3):
                img_linea = f_desc.render(linea, True, COL_TENUE)
                p.blit(img_linea, img_linea.get_rect(center=(rect.centerx, y)))
                y += 18

            # Tecla de seleccion
            num = f_nombre.render(str(i + 1), True,
                                  COL_TITULO if enfocada else COL_TENUE)
            p.blit(num, num.get_rect(center=(rect.centerx, rect.bottom - 24)))

    # ------------------------------------------------------------------ bucle
    while True:
        raton[0] = pygame.mouse.get_pos()
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                return -1
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    # ESC no puede dejar la subida sin resolver: se aplica la
                    # primera carta, que es tan valida como cualquier otra.
                    if cartas:
                        juego.elegir_carta(cartas[sel[0] % len(cartas)])
                    return 0
                if pygame.K_1 <= evento.key < pygame.K_1 + progresion.CARTAS_POR_NIVEL:
                    i = evento.key - pygame.K_1
                    if i < len(cartas):
                        sel[0] = i
                        juego.elegir_carta(cartas[i])
                        return 0
                elif evento.key in (pygame.K_LEFT, pygame.K_a):
                    sel[0] = (sel[0] - 1) % n
                elif evento.key in (pygame.K_RIGHT, pygame.K_d):
                    sel[0] = (sel[0] + 1) % n
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if cartas:
                        juego.elegir_carta(cartas[sel[0] % len(cartas)])
                    return 0
            elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                for i in range(len(cartas)):
                    if rect_carta(i).collidepoint(evento.pos):
                        sel[0] = i
                        juego.elegir_carta(cartas[i])
                        return 0

        predibujar()
        dibujar(pantalla)
        pygame.display.flip()
        reloj.tick(60)


def pantalla_tienda(pantalla, reloj, ancho, alto, juego):
    """Tienda en partida. El combate queda congelado mientras compras."""
    f_titulo = pygame.font.SysFont("consolas", 40, bold=True)
    f_pest = pygame.font.SysFont("consolas", 19, bold=True)
    f_nombre = pygame.font.SysFont("consolas", 16, bold=True)
    f_desc = pygame.font.SysFont("consolas", 13)
    f_pie = pygame.font.SysFont("consolas", 13)
    f_cifra = pygame.font.SysFont("consolas", 20, bold=True)
    f_ayuda = pygame.font.SysFont("consolas", 15)
    lay = layout_tienda(ancho, alto)
    ancho_tarjeta, alto_tarjeta = lay["tarjeta"]
    boton_volver = Boton("VOLVER", ancho // 2 - 100, alto - 58, 200, 46,
                         pygame.font.SysFont("consolas", 22, bold=True))
    cartera = juego.cartera
    pestana = [0]
    sel = [0]
    aviso = {"texto": "", "color": COL_OK, "t": 0}
    raton = [pygame.mouse.get_pos()]

    def rect_tarjeta(i, total):
        """Rectangulo de la tarjeta i, centrada si sobran huecos."""
        columnas = lay["columnas"]
        filas = lay["filas"]
        por_fila = min(columnas, total)
        columnas_usadas = -(-total // filas) if total % filas else columnas
        if columnas_usadas < columnas:
            ancho_total = columnas_usadas * ancho_tarjeta + (columnas_usadas - 1) * lay["huesco"]
            x0 = lay["zona"].x + (lay["zona"].width - ancho_total) // 2
        else:
            x0 = lay["zona"].x
        fila, col = divmod(i, columnas)
        if total % filas:
            # La ultima fila se centra para que no quede colgando a la izquierda.
            en_ultima = fila == total // filas
            if en_ultima:
                por_fila = total % filas
                ancho_ultima = por_fila * ancho_tarjeta + (por_fila - 1) * lay["huesco"]
                x0 = lay["zona"].x + (lay["zona"].width - ancho_ultima) // 2
        return pygame.Rect(x0 + col * (ancho_tarjeta + lay["huesco"]),
                           lay["zona"].y + fila * (alto_tarjeta + lay["huesco"]),
                           ancho_tarjeta, alto_tarjeta)

    def comprar_seleccion():
        datos = _datos_tienda(cartera)[pestana[0]]
        if not 0 <= sel[0] < len(datos):
            return
        nombre = datos[sel[0]]["nombre"]
        if not juego.comprar(pestana[0], datos[sel[0]]["clave"]):
            return
        aviso["texto"] = "COMPRADO: " + nombre
        aviso["color"] = COL_OK
        aviso["t"] = 150

    def predibujar():
        # Se ve la arena congelada detras, para saber donde estas parado.
        juego.dibujar()
        velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        velo.fill((6, 7, 12, 216))
        pantalla.blit(velo, (0, 0))

    def dibujar(p):
        t = pygame.time.get_ticks() / 400.0
        mouse = raton[0]

        # --- Cabecera
        titulo = f_titulo.render("TIENDA", True, COL_TITULO)
        p.blit(titulo, (40, 26))
        lv = f_nombre.render("NIVEL %d" % cartera.nivel, True, COL_TEXTO)
        p.blit(lv, (40, 62))
        objetivo = cartera.xp_para_siguiente()
        barra = pygame.Rect(40 + lv.get_width() + 12, 64, 190, 8)
        _barra(p, barra, cartera.progreso_xp(), (40, 44, 60), (120, 200, 255))
        if objetivo > 0:
            xp_txt = f_pie.render("%d / %d XP" % (cartera.xp, objetivo), True, COL_TENUE)
            p.blit(xp_txt, (barra.right + 10, 60))
        else:
            p.blit(f_pie.render("MAX", True, COL_MAX), (barra.right + 10, 60))

        monedas = f_cifra.render("%d" % cartera.monedas, True, COL_MONEDA)
        p.blit(monedas, (ancho - 40 - monedas.get_width(), 34))
        p.blit(f_pie.render("MONEDAS", True, COL_TENUE),
               (ancho - 40 - monedas.get_width(), 58))

        # --- Pestanas
        listas = _datos_tienda(cartera)
        for i, texto in enumerate(("MEJORAS", "ARSENAL", "HABILIDADES")):
            rect = lay["pestanas"][i]
            activa = i == pestana[0]
            _panel(p, rect, alpha=215 if activa else 150)
            color = COL_TITULO if activa else COL_TENUE
            img = f_pest.render(texto, True, color)
            p.blit(img, img.get_rect(center=rect.center))
            if activa:
                pygame.draw.rect(p, COL_TITULO, rect, 2, border_radius=8)

        lista = listas[pestana[0]]
        sel[0] = max(0, min(sel[0], len(lista) - 1))

        # --- Tarjetas
        for i, item in enumerate(lista):
            rect = rect_tarjeta(i, len(lista))
            color = _color_estado(item["estado"])
            hover = rect.collidepoint(mouse)
            enfocada = i == sel[0]
            _panel(p, rect, alpha=225 if (hover or enfocada) else 175)
            pygame.draw.rect(p, color if enfocada else COL_PANEL_BORDE,
                             rect, 2 if enfocada else 1, border_radius=10)

            # Icono en un circulo
            centro = (rect.x + 24, rect.y + 24)
            pygame.draw.circle(p, (30, 32, 44), centro, 16)
            pygame.draw.circle(p, item["color"], centro, 16, 2)
            img = iconos.obtener(item["icono"], 30, item["color"])
            p.blit(img, img.get_rect(center=centro))

            nombre = f_nombre.render(item["nombre"], True, COL_TEXTO)
            p.blit(nombre, (rect.x + 46, rect.y + 15))

            y = rect.y + 44
            for linea in _envolver(f_desc, item["desc"], rect.width - 20, 2):
                p.blit(f_desc.render(linea, True, COL_TENUE), (rect.x + 10, y))
                y += 16

            # Pips de nivel (mejoras) o etiqueta de estado
            if item["max"] > 1:
                radio = 3
                paso = 9
                total = (item["max"] - 1) * paso
                for n in range(item["max"]):
                    px = rect.centerx - total // 2 + n * paso
                    llena = n < item["nivel"]
                    pygame.draw.circle(
                        p, item["color"] if llena else (52, 56, 72), (px, rect.bottom - 26),
                        radio if llena else radio - 1,
                    )
            pie = f_pie.render(item["pie"], True, COL_TENUE)
            p.blit(pie, (rect.x + 10, rect.bottom - 34))

            # Coste o estado
            if item["estado"] == "max":
                etiqueta = f_pie.render("AL MAXIMO", True, color)
            elif item["estado"] == "comprado":
                etiqueta = f_pie.render("ADQUIRIDO", True, color)
            else:
                etiqueta = f_cifra.render("%d" % item["coste"], True, color)
            p.blit(etiqueta, etiqueta.get_rect(midright=(rect.right - 12, rect.bottom - 30)))
            if item["estado"] in ("ok", "caro"):
                p.blit(pygame.font.SysFont("consolas", 12).render("$", True, COL_MONEDA),
                       (rect.right - 12 - etiqueta.get_width() - 10, rect.bottom - 38))

        # --- Aviso de compra
        if aviso["t"] > 0:
            aviso["t"] -= 1
            img = f_nombre.render(aviso["texto"], True, aviso["color"])
            img.set_alpha(int(255 * min(1.0, aviso["t"] / 40.0)))
            p.blit(img, img.get_rect(center=(ancho // 2, lay["zona"].bottom + 4)))

        boton_volver.mouse_sobre = boton_volver.contiene(mouse)
        boton_volver.dibujar(p, t)

        ayuda = f_ayuda.render("1/2/3 PESTANA   FLECHAS MOVER   ENTER COMPRAR   T VOLVER",
                               True, COL_TENUE)
        p.blit(ayuda, ayuda.get_rect(center=(ancho // 2, alto - 22)))

    # ------------------------------------------------------------------ bucle
    while True:
        raton[0] = pygame.mouse.get_pos()
        listas = _datos_tienda(cartera)
        lista = listas[pestana[0]]
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                return -1
            if evento.type == pygame.KEYDOWN:
                if evento.key in (pygame.K_ESCAPE, pygame.K_t):
                    return 0
                if evento.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    pestana[0] = evento.key - pygame.K_1
                    sel[0] = 0
                    # La lista se recalcula: si se cambia de pestana y se navega
                    # en el mismo frame, seguiria midiendo la lista anterior.
                    lista = listas[pestana[0]]
                elif evento.key in (pygame.K_LEFT, pygame.K_a):
                    sel[0] = (sel[0] - 1) % max(1, len(lista))
                elif evento.key in (pygame.K_RIGHT, pygame.K_d):
                    sel[0] = (sel[0] + 1) % max(1, len(lista))
                elif evento.key in (pygame.K_UP, pygame.K_w):
                    salto = lay["columnas"]
                    sel[0] = max(0, sel[0] - salto)
                elif evento.key in (pygame.K_DOWN, pygame.K_s):
                    salto = lay["columnas"]
                    sel[0] = min(len(lista) - 1, sel[0] + salto)
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    comprar_seleccion()
            elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                if boton_volver.contiene(evento.pos):
                    return 0
                for i, rect in enumerate(lay["pestanas"]):
                    if rect.collidepoint(evento.pos):
                        pestana[0] = i
                        sel[0] = 0
                        lista = listas[pestana[0]]
                        break
                else:
                    for i in range(len(lista)):
                        if rect_tarjeta(i, len(lista)).collidepoint(evento.pos):
                            sel[0] = i
                            comprar_seleccion()
                            break

        predibujar()
        dibujar(pantalla)
        pygame.display.flip()
        reloj.tick(60)


def layout_inicio(ancho, alto):
    """Zonas del menu. Se calculan juntas para que nunca se solapen."""
    y_titulo = alto // 2 - 196
    y_sub = alto // 2 - 132
    controles = pygame.Rect(ancho // 2 - 300, alto // 2 - 104, 600, 132)
    y_botones = alto // 2 + 56
    separacion = 20
    ancho_boton = 240
    total = 2 * ancho_boton + separacion
    x0 = ancho // 2 - total // 2
    botones = [
        pygame.Rect(x0 + i * (ancho_boton + separacion), y_botones, ancho_boton, 60)
        for i in range(2)
    ]
    posiciones = [
        [(ancho // 2 - 155, controles.y + 26 + i * 25),
         (ancho // 2 + 155, controles.y + 26 + i * 25)]
        for i in range(len(CONTROLES))
    ]
    return {
        "titulo": (ancho // 2, y_titulo),
        "subtitulo": (ancho // 2, y_sub),
        "controles": controles,
        "controles_pos": posiciones,
        "botones": botones,
        "record": (ancho // 2, alto - 40),
    }


def pantalla_inicio(pantalla, reloj, ancho, alto, records=None):
    f_titulo = pygame.font.SysFont("consolas", 78, bold=True)
    f_sub = pygame.font.SysFont("consolas", 21)
    f_ch = pygame.font.SysFont("consolas", 17)
    f_btn = pygame.font.SysFont("consolas", 24, bold=True)
    fondo = FondoAnimado(ancho, alto)
    lay = layout_inicio(ancho, alto)
    y_titulo, y_sub = lay["titulo"][1], lay["subtitulo"][1]
    rect_controles = lay["controles"]
    # Sin tienda en el menu: la tienda se abre dentro de la partida con la T.
    botones = [
        Boton(texto, rect.x, rect.y, rect.w, rect.h, f_btn)
        for texto, rect in zip(("JUGAR", "RECORDS"), lay["botones"])
    ]

    def predibujar():
        fondo.actualizar()
        fondo.dibujar(pantalla)

    def dibujar(p):
        t = pygame.time.get_ticks() / 380.0
        # Titulo con pulso
        titulo = f_titulo.render("ARENA", True, COL_TITULO)
        escala = 1.0 + 0.03 * math.sin(t)
        if abs(escala - 1.0) > 0.004:
            nuevo = pygame.transform.smoothscale(
                titulo, (int(titulo.get_width() * escala), int(titulo.get_height() * escala))
            )
            titulo = nuevo
        p.blit(titulo, titulo.get_rect(center=(ancho // 2, y_titulo)))
        # Subtitulo
        s = f_sub.render("SHOOTER CENITAL  -  CADA PARTIDA EMPIEZA DE CERO",
                         True, COL_TENUE)
        p.blit(s, s.get_rect(center=(ancho // 2, y_sub)))

        # Panel con los controles, en dos columnas
        _panel(p, rect_controles)
        for fila, posiciones in zip(CONTROLES, lay["controles_pos"]):
            for texto, (cx, cy) in zip(fila, posiciones):
                if not texto:
                    continue
                img = f_ch.render(texto, True, COL_TENUE)
                p.blit(img, img.get_rect(center=(cx, cy)))

        for boton in botones:
            boton.dibujar(p, t)

        if records:
            mejor = f_sub.render("MEJOR PUNTAJE: %d" % records[0]["puntaje"], True, COL_TITULO)
            p.blit(mejor, mejor.get_rect(center=(ancho // 2, alto - 40)))

    return _bucle(pantalla, reloj, botones, dibujar, predibujar)


def pantalla_records(pantalla, reloj, ancho, alto, registros=None):
    registros = registros or []
    f_titulo = pygame.font.SysFont("consolas", 44, bold=True)
    f_btn = pygame.font.SysFont("consolas", 24, bold=True)
    f_fila = pygame.font.SysFont("consolas", 22)
    f_num = pygame.font.SysFont("consolas", 24, bold=True)
    fondo = FondoAnimado(ancho, alto, 40)
    botones = [Boton("VOLVER", ancho // 2 - 100, alto - 116, 200, 58, f_btn)]
    medallas = [(250, 210, 90), (205, 210, 225), (206, 152, 100),
                (150, 200, 150), (150, 170, 210)]
    tope = min(len(registros), 5)

    def predibujar():
        fondo.actualizar()
        fondo.dibujar(pantalla)

    def dibujar(p):
        t = f_titulo.render("MEJORES PUNTAJES", True, COL_TITULO)
        p.blit(t, t.get_rect(center=(ancho // 2, 74)))
        if not registros:
            vacio = f_fila.render("(aun no hay records)", True, COL_TENUE)
            p.blit(vacio, vacio.get_rect(center=(ancho // 2, 200)))
        for i, reg in enumerate(registros[:5]):
            fila = pygame.Rect(ancho // 2 - 250, 118 + i * 62, 500, 52)
            _panel(p, fila, alpha=200 if i < tope else 140)
            color = medallas[i] if i < len(medallas) else COL_TENUE
            num = f_num.render("%d" % (i + 1), True, color)
            p.blit(num, num.get_rect(center=(fila.x + 34, fila.centery)))
            puntos = f_num.render(str(reg["puntaje"]), True, COL_TEXTO)
            p.blit(puntos, (fila.x + 70, fila.y + 6))
            p.blit(f_num.render("pts", True, COL_TENUE), (fila.x + 70, fila.y + 28))
            info = f_fila.render("oleada %s   %s" % (reg.get("nivel", "?"), reg.get("fecha", "")),
                                 True, COL_TENUE)
            p.blit(info, info.get_rect(midright=(fila.right - 20, fila.centery)))
        botones[0].dibujar(p, 0.0)

    return _bucle(pantalla, reloj, botones, dibujar, predibujar)


def pantalla_pausa(pantalla, reloj, ancho, alto):
    f_titulo = pygame.font.SysFont("consolas", 58, bold=True)
    f_btn = pygame.font.SysFont("consolas", 26, bold=True)
    f_ch = pygame.font.SysFont("consolas", 18)
    marco = pygame.Rect(ancho // 2 - 340, alto // 2 - 125, 680, 250)
    y = marco.y + 166
    # ESC tambien reanuda el juego.
    botones = [
        Boton("SEGUIR", ancho // 2 - 236, y, 224, 62, f_btn),
        Boton("SALIR", ancho // 2 + 12, y, 224, 62, f_btn),
    ]
    estado = {"t": 0.0}

    def predibujar():
        pantalla.fill((9, 10, 14))
        velo = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        velo.fill((0, 0, 0, 185))
        pantalla.blit(velo, (0, 0))

    def dibujar(p):
        estado["t"] += 1 / 60.0
        t = estado["t"]
        _panel(p, marco, alpha=190)
        pygame.draw.rect(p, (250, 210, 90), marco, 2, border_radius=14)
        titulo = f_titulo.render("PAUSA", True, COL_TITULO)
        p.blit(titulo, titulo.get_rect(center=(ancho // 2, marco.y + 52)))
        for i, linea in enumerate(RECORDATORIO):
            recordatorio = f_ch.render(linea, True, COL_TENUE)
            p.blit(recordatorio, recordatorio.get_rect(center=(ancho // 2, marco.y + 108 + i * 26)))
        for boton in botones:
            boton.dibujar(p, t)

    return _bucle(pantalla, reloj, botones, dibujar, predibujar, indice_escape=0)


def pantalla_game_over(pantalla, reloj, ancho, alto, puntaje=0, oleada=1, record=False,
                       bajas=0, combo=0, build=None):
    f_titulo = pygame.font.SysFont("consolas", 62, bold=True)
    f_btn = pygame.font.SysFont("consolas", 26, bold=True)
    f_ch = pygame.font.SysFont("consolas", 20)
    f_dato = pygame.font.SysFont("consolas", 30, bold=True)
    f_premio = pygame.font.SysFont("consolas", 24, bold=True)
    fondo = FondoAnimado(ancho, alto, 50)
    y = alto // 2 + 92
    botones = [
        Boton("REINTENTAR", ancho // 2 - 236, y, 224, 62, f_btn),
        Boton("MENU", ancho // 2 + 12, y, 224, 62, f_btn),
    ]
    # Nada de esto se guarda: es el resumen de como se ha muerto esta partida.
    build = build or {}

    def predibujar():
        fondo.actualizar()
        fondo.dibujar(pantalla, color_fondo=(15, 8, 11), color_linea=(34, 18, 22))

    def dibujar(p):
        t = pygame.time.get_ticks() / 400.0
        titulo = f_titulo.render("GAME OVER", True, (238, 78, 78))
        p.blit(titulo, titulo.get_rect(center=(ancho // 2, alto // 2 - 178)))

        # Panel con el resumen de la partida
        panel = pygame.Rect(ancho // 2 - 300, alto // 2 - 96, 600, 128)
        _panel(p, panel, alpha=205)
        datos = [("PUNTOS", str(puntaje), COL_TITULO),
                 ("OLEADA", str(oleada), COL_TEXTO),
                 ("BAJAS", str(bajas), COL_TEXTO),
                 ("MEJOR COMBO", str(combo), COL_TEXTO)]
        ancho_celda = panel.width // len(datos)
        for i, (etiqueta, valor, color) in enumerate(datos):
            cx = panel.x + ancho_celda * i + ancho_celda // 2
            img_et = f_ch.render(etiqueta, True, COL_TENUE)
            p.blit(img_et, img_et.get_rect(center=(cx, panel.y + 30)))
            img_v = f_dato.render(valor, True, color)
            p.blit(img_v, img_v.get_rect(center=(cx, panel.y + 72)))

        # La build con la que se ha llegado hasta aqui
        premios = pygame.Rect(ancho // 2 - 300, panel.bottom + 14, 600, 46)
        _panel(p, premios, alpha=190)
        partes = [
            ("NIVEL %d" % build.get("nivel", 1), (150, 220, 255)),
            ("%d MEJORAS" % build.get("mejoras", 0), COL_TEXTO),
            ("%d ARMAS" % build.get("armas", 0), COL_MONEDA),
            ("%d HABILIDADES" % build.get("habilidades", 0), COL_OK),
        ]
        total = len(partes)
        for i, (texto, color) in enumerate(partes):
            cx = premios.x + premios.width // (total * 2) * (2 * i + 1)
            img = f_premio.render(texto, True, color)
            p.blit(img, img.get_rect(center=(cx, premios.centery)))

        # Aviso de record, con pulso
        if record:
            aviso = f_premio.render("NUEVO RECORD", True, COL_TITULO)
            escala = 1.0 + 0.06 * math.sin(t * 2)
            if abs(escala - 1.0) > 0.01:
                aviso = pygame.transform.smoothscale(
                    aviso, (int(aviso.get_width() * escala), int(aviso.get_height() * escala))
                )
            p.blit(aviso, aviso.get_rect(center=(ancho // 2, panel.y - 26)))

        for boton in botones:
            boton.dibujar(p, t)

    return _bucle(pantalla, reloj, botones, dibujar, predibujar, indice_escape=1)
