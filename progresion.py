# -*- coding: utf-8 -*-
"""
progresion.py
=============
Progresion DENTRO de la partida: monedas, nivel y catalogo de mejoras.

Nada de esto se guarda en disco. Es un roguelite puro: al empezar una partida
se crea una `Cartera` nueva con el dinero inicial y sin compras, asi que cada
run se juega desde cero. Los unicos records que sobreviven son los
puntajes, que viven en puntajes.py.

La Cartera guarda dos vias para mejorarse:
  - la tienda en partida, pagando con monedas (`comprar_mejora`,
    `desbloquear_arma`, `desbloquear_habilidad`),
  - las cartas de subida de nivel, que son gratis y aleatorias (`cartas`).
"""

import random

from armas import ARMAS

# ------------------------------------------------------------------ constantes
DINERO_INICIAL = 1500
NIVEL_MAX = 15

# Monedas por baja, segun el tipo de enemigo.
MONEDAS_POR_BAJA = {
    "corredor": 1,
    "tirador": 2,
    "tanque": 4,
    "explosivo": 2,
    "acorazado": 6,
    "mortero": 4,
    "dron": 3,
    "sabueso": 4,
    "acechador": 3,
    "divisorio": 5,
    "germen": 1,
    "jefe": 15,
    "jefe_bastion": 17,
    "jefe_matriarca": 16,
    "jefe_prisma": 18,
}

# XP por baja: es lo que sube el nivel de la partida. Ningun tipo pasa de 60,
# para que un solo jefe no salte dos niveles de golpe.
XP_POR_BAJA = {
    "corredor": 10,
    "tirador": 14,
    "tanque": 24,
    "explosivo": 12,
    "acorazado": 30,
    "mortero": 22,
    "dron": 18,
    "sabueso": 20,
    "acechador": 19,
    "divisorio": 28,
    "germen": 5,
    "jefe": 60,
    "jefe_bastion": 62,
    "jefe_matriarca": 60,
    "jefe_prisma": 64,
}

# Cuantas cartas se ofrecen en cada subida de nivel.
CARTAS_POR_NIVEL = 3


def xp_para_nivel(nivel):
    """XP necesaria para pasar de `nivel` a `nivel + 1` dentro de la partida."""
    return 40 + int(nivel) * 14


def bonificacion_nivel(nivel):
    """Lo que da el nivel de la partida, solo de forma automatica.

    Las cartas dan el resto; esto es el suelo minimo para que subir de nivel
    siempre se note, aunque el catalogo de mejoras ya este todo al tope.
    """
    e = max(0, min(nivel, NIVEL_MAX) - 1)
    return {
        "vida_max": e * 5,
        "velocidad": e * 1.5,
    }


# --------------------------------------------------------------- catalogo
# Mejoras de atributo: se compran con monedas en la tienda o salen como carta
# al subir de nivel. El tope es por partida, asi que nada se acumula entre runs.
MEJORAS = {
    "vida": {
        "nombre": "BLINDAJE",
        "desc": "+20 de vida maxima",
        "icono": "+",
        "color": (96, 240, 126),
        "max": 10,
        "costo": 120,
        "paso": 70,
    },
    "velocidad": {
        "nombre": "IMPULSO",
        "desc": "+14 px/s de velocidad",
        "icono": ">>",
        "color": (255, 190, 70),
        "max": 10,
        "costo": 110,
        "paso": 65,
    },
    "dano": {
        "nombre": "MUNICION PESADA",
        "desc": "+9% de dano",
        "icono": "X",
        "color": (255, 138, 110),
        "max": 10,
        "costo": 150,
        "paso": 90,
    },
    "cadencia": {
        "nombre": "GATILLO",
        "desc": "-5% de intervalo de disparo",
        "icono": "F",
        "color": (120, 200, 255),
        "max": 10,
        "costo": 140,
        "paso": 85,
    },
    "municion": {
        "nombre": "CARGADOR",
        "desc": "+12% de municion",
        "icono": "=",
        "color": (180, 220, 255),
        "max": 10,
        "costo": 100,
        "paso": 60,
    },
    "recarga": {
        "nombre": "RECARGA RAPIDA",
        "desc": "-6% de tiempo de recarga",
        "icono": "R",
        "color": (150, 230, 200),
        "max": 10,
        "costo": 90,
        "paso": 55,
    },
    "escudo": {
        "nombre": "ESCUDO ACTIVO",
        "desc": "+80 frames de escudo",
        "icono": "O",
        "color": (120, 220, 255),
        "max": 8,
        "costo": 150,
        "paso": 95,
    },
    "dash": {
        "nombre": "IMPULSO REACTIVO",
        "desc": "-7 frames de recarga y +1 carga",
        "icono": "D",
        "color": (120, 190, 255),
        "max": 6,
        "costo": 170,
        "paso": 115,
    },
    "regen": {
        "nombre": "NANORREPARACION",
        "desc": "+0.45 de vida por segundo",
        "icono": "H",
        "color": (120, 255, 180),
        "max": 8,
        "costo": 200,
        "paso": 130,
    },
    "critico": {
        "nombre": "PUNTO DEBIL",
        "desc": "+6% de critico (x2.3 de dano)",
        "icono": "!",
        "color": (255, 230, 120),
        "max": 8,
        "costo": 185,
        "paso": 120,
    },
    "vampiro": {
        "nombre": "VAMPIRISMO",
        "desc": "roba 4% del dano como vida",
        "icono": "V",
        "color": (220, 110, 180),
        "max": 5,
        "costo": 260,
        "paso": 170,
    },
    "magnetico": {
        "nombre": "IMAN",
        "desc": "atrae powerups desde mas lejos",
        "icono": "M",
        "color": (250, 210, 90),
        "max": 3,
        "costo": 180,
        "paso": 140,
    },
}

ORDEN_MEJORAS = (
    "vida", "velocidad", "dano", "cadencia",
    "municion", "recarga", "escudo", "dash",
    "regen", "critico", "vampiro", "magnetico",
)

# Habilidades: se desbloquean una sola vez, con monedas en la tienda o como
# carta de nivel. Las de tecla se lanzan durante la partida.
HABILIDADES = {
    "nova": {
        "nombre": "NOVA",
        "desc": "onda expansiva que daña alrededor",
        "icono": "N",
        "tecla": "E",
        "color": (255, 200, 110),
        "costo": 900,
        "radio": 190,
        "danio": 60,
        "enfriamiento": 420,
    },
    "tormenta": {
        "nombre": "TORMENTA",
        "desc": "rafaga de balas en todas direcciones",
        "icono": "T",
        "tecla": "R",
        "color": (150, 220, 255),
        "costo": 1400,
        "balas": 18,
        "danio": 42,
        "enfriamiento": 600,
    },
    "segunda": {
        "nombre": "SEGUNDA VIDA",
        "desc": "reaparece con 50% de vida, 1 vez",
        "icono": "S",
        "tecla": None,
        "color": (140, 255, 190),
        "costo": 1800,
    },
    "sobrecarga": {
        "nombre": "SOBRECARGA",
        "desc": "6 s de +80% dano y +60% cadencia",
        "icono": "B",
        "tecla": "F",
        "color": (255, 130, 90),
        "costo": 2200,
        "duracion": 360,
        "enfriamiento": 780,
    },
}

ORDEN_HABILIDADES = ("nova", "tormenta", "segunda", "sobrecarga")

# Arsenal: todo lo que se puede comprar, menos la pistola inicial. El precio
# y el nombre salen del propio catalogo de armas, aqui va solo la decision de
# cuanto cuesta cada una.
_ARSENAL_PRECIOS = (
    ("escopeta", 600),
    ("rifle", 900),
    ("laser", 1300),
    ("sniper", 700),
    ("discos", 1000),
    ("lanzallamas", 1500),
    ("railgun", 2400),
)

_ARSENAL_DESCRIPCIONES = {
    "escopeta": "abanico de perdigones a corta distancia",
    "rifle": "rafaga rapida de precision",
    "laser": "rayo que atraviesa en linea recta",
    "sniper": "atraviesa 3 enemigos",
    "discos": "rebota 3 veces en los muros",
    "lanzallamas": "cono continuo, sin municion",
    "railgun": "atraviesa toda la linea",
}

ARSENAL = {}
for _clave, _precio in _ARSENAL_PRECIOS:
    _cfg = ARMAS[_clave]
    ARSENAL[_clave] = {
        "nombre": _cfg["nombre"],
        "desc": _ARSENAL_DESCRIPCIONES.get(_clave, ""),
        "icono": _cfg.get("icono", "*"),
        "color": _cfg["color"],
        "costo": _precio,
    }

ORDEN_ARSENAL = tuple(clave for clave, _ in _ARSENAL_PRECIOS)


def estadisticas_vacias():
    """Multiplicadores/valores neutros, la base de todas las mejoras."""
    return {
        "vida_max": 100,
        "velocidad": 270.0,
        "danio": 1.0,
        "cadencia": 1.0,
        "municion": 1.0,
        "recarga": 1.0,
        "escudo_extra": 0,
        "dash_cd": 46,
        "dash_cargas": 1,
        "regen": 0.0,
        "critico": 0.0,
        "critico_mult": 2.3,
        "vampiro": 0.0,
        "magnetico": 0.0,
    }


class Cartera:
    """Dinero, nivel y compras de UNA partida. Se tira al reiniciar."""

    def __init__(self, monedas=DINERO_INICIAL):
        self.monedas = int(monedas)
        self.nivel = 1
        self.xp = 0
        self.mejoras = {clave: 0 for clave in ORDEN_MEJORAS}
        self.armas = []
        self.habilidades = []
        # Subidas de nivel que aun no tienen carta elegida
        self.pendientes = 0

    def reiniciar(self, monedas=DINERO_INICIAL):
        """Deja la cartera como al empezar la partida."""
        self.monedas = int(monedas)
        self.nivel = 1
        self.xp = 0
        self.mejoras = {clave: 0 for clave in ORDEN_MEJORAS}
        self.armas = []
        self.habilidades = []
        self.pendientes = 0
        return self

    # ------------------------------------------------------------------ nivel
    def xp_para_siguiente(self):
        if self.nivel >= NIVEL_MAX:
            return 0
        return xp_para_nivel(self.nivel)

    def progreso_xp(self):
        """Fraccion 0..1 de XP hacia el siguiente nivel."""
        objetivo = self.xp_para_siguiente()
        if objetivo <= 0:
            return 1.0
        return max(0.0, min(1.0, self.xp / objetivo))

    def anadir_xp(self, cantidad):
        """Suma XP y apila cuantas subidas de nivel quedan por elegir carta."""
        if self.nivel >= NIVEL_MAX:
            self.xp = 0
            return 0
        self.xp += max(0, int(cantidad))
        ganados = 0
        while self.nivel < NIVEL_MAX and self.xp >= xp_para_nivel(self.nivel):
            self.xp -= xp_para_nivel(self.nivel)
            self.nivel += 1
            ganados += 1
            self.pendientes += 1
        if self.nivel >= NIVEL_MAX:
            self.xp = 0
        return ganados

    # ---------------------------------------------------------------- monedas
    def anadir_monedas(self, cantidad):
        self.monedas = max(0, self.monedas + int(cantidad))
        return self.monedas

    def puede_pagar(self, costo):
        return self.monedas >= int(costo)

    # ---------------------------------------------------------------- mejoras
    def nivel_mejora(self, clave):
        return self.mejoras.get(clave, 0)

    def mejora_maxima(self, clave):
        return self.mejoras.get(clave, 0) >= MEJORAS[clave]["max"]

    def costo_mejora(self, clave):
        """Coste del siguiente nivel de la mejora, o None si ya esta al tope."""
        cfg = MEJORAS[clave]
        nivel = self.nivel_mejora(clave)
        if nivel >= cfg["max"]:
            return None
        return cfg["costo"] + cfg["paso"] * nivel

    def comprar_mejora(self, clave):
        if clave not in MEJORAS:
            return False
        costo = self.costo_mejora(clave)
        if costo is None or not self.puede_pagar(costo):
            return False
        self.monedas -= costo
        self.mejoras[clave] += 1
        return True

    def subir_mejora(self, clave):
        """Mejora gratis (carta de nivel). No depende de las monedas."""
        if clave not in MEJORAS or self.mejora_maxima(clave):
            return False
        self.mejoras[clave] += 1
        return True

    # ------------------------------------------------------------------ armas
    def arma_desbloqueada(self, clave):
        return clave in self.armas

    def desbloquear_arma(self, clave):
        if clave not in ARSENAL or self.arma_desbloqueada(clave):
            return False
        costo = ARSENAL[clave]["costo"]
        if not self.puede_pagar(costo):
            return False
        self.monedas -= costo
        self.armas.append(clave)
        return True

    def armas_disponibles(self):
        """La pistola siempre; el resto, solo lo comprado en la partida."""
        return ["pistola"] + [a for a in ORDEN_ARSENAL if a in self.armas]

    # ------------------------------------------------------------ habilidades
    def habilidad_activa(self, clave):
        return clave in self.habilidades

    def desbloquear_habilidad(self, clave):
        if clave not in HABILIDADES or self.habilidad_activa(clave):
            return False
        costo = HABILIDADES[clave]["costo"]
        if not self.puede_pagar(costo):
            return False
        self.monedas -= costo
        self.habilidades.append(clave)
        return True

    def desbloquear_habilidad_gratis(self, clave):
        """Habilidad por carta de nivel: no se paga, pero solo una vez."""
        if clave not in HABILIDADES or self.habilidad_activa(clave):
            return False
        self.habilidades.append(clave)
        return True

    # ------------------------------------------------------- cartas de nivel
    def _opciones_disponibles(self):
        """Cosas que todavia se pueden mejorar y no estan al tope."""
        opciones = []
        for clave in ORDEN_MEJORAS:
            if not self.mejora_maxima(clave):
                cfg = MEJORAS[clave]
                opciones.append({
                    "tipo": "mejora", "clave": clave,
                    "nombre": cfg["nombre"], "desc": cfg["desc"],
                    "icono": cfg["icono"], "color": cfg["color"],
                })
        for clave in ORDEN_HABILIDADES:
            if not self.habilidad_activa(clave):
                cfg = HABILIDADES[clave]
                opciones.append({
                    "tipo": "habilidad", "clave": clave,
                    "nombre": cfg["nombre"], "desc": cfg["desc"],
                    "icono": cfg["icono"], "color": cfg["color"],
                })
        return opciones

    def cartas(self, cantidad=CARTAS_POR_NIVEL, rng=None):
        """Cartas aleatorias para la proxima subida de nivel.

        Nunca devuelve una carta repetida. Si el catalogo esta todo al tope,
        devuelve una bonificacion automatica para que el nivel nunca sea
        una pantalla vacia.
        """
        opciones = self._opciones_disponibles()
        generador = rng or random
        if not opciones:
            return [{
                "tipo": "nivel", "clave": "nivel",
                "nombre": "ENTRENAMIENTO",
                "desc": "+5 vida y +1.5 de velocidad",
                "icono": "L", "color": (200, 210, 240),
            }]
        elegidas = generador.sample(opciones, min(cantidad, len(opciones)))
        return elegidas

    def elegir_carta(self, carta):
        """Aplica la carta elegida y descuenta una subida pendiente."""
        if carta is None or self.pendientes <= 0:
            return False
        tipo = carta.get("tipo")
        clave = carta.get("clave")
        if tipo == "mejora":
            ok = self.subir_mejora(clave)
        elif tipo == "habilidad":
            ok = self.desbloquear_habilidad_gratis(clave)
        else:
            ok = True  # la bonificacion automatica no se puede agotar
        if ok:
            self.pendientes -= 1
        return ok

    # ------------------------------------------------------------ estadisticas
    def estadisticas(self):
        """Todos los atributos efectivos, ya combinados."""
        est = estadisticas_vacias()
        base = bonificacion_nivel(self.nivel)
        est["vida_max"] += base["vida_max"]
        est["velocidad"] += base["velocidad"]

        est["vida_max"] += self.nivel_mejora("vida") * 20
        est["velocidad"] += self.nivel_mejora("velocidad") * 14.0
        est["danio"] += self.nivel_mejora("dano") * 0.09
        est["cadencia"] *= 1.0 - self.nivel_mejora("cadencia") * 0.05
        est["municion"] += self.nivel_mejora("municion") * 0.12
        est["recarga"] *= 1.0 - self.nivel_mejora("recarga") * 0.06
        est["escudo_extra"] = self.nivel_mejora("escudo") * 80

        n_dash = self.nivel_mejora("dash")
        est["dash_cd"] = max(10, 46 - n_dash * 7)
        est["dash_cargas"] = 1 + n_dash

        est["regen"] = self.nivel_mejora("regen") * 0.45
        est["critico"] = min(0.75, self.nivel_mejora("critico") * 0.06)
        est["vampiro"] = self.nivel_mejora("vampiro") * 0.04
        est["magnetico"] = self.nivel_mejora("magnetico") * 90.0

        return est

    # ---------------------------------------------------------------- resumen
    def resumen(self):
        """Que se ensea en el game over: la build con la que se ha muerto."""
        return {
            "nivel": self.nivel,
            "monedas": self.monedas,
            "mejoras": sum(self.mejoras.values()),
            "armas": len(self.armas),
            "habilidades": len(self.habilidades),
        }
