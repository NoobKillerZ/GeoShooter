"""Post-proceso de la escena: bloom por buffer emisivo.

Por que no es un bloom de frame completo
----------------------------------------
Un bloom clasico baja el frame entero, descarta los pixeles por debajo de un
umbral de luminancia y lo vuelve a sumar. El umbral hay que hacerlo pixel a
pixel, y a 960x640 son 614 400 pixeles: en Python puro eso son varios
milisegundos por frame, y sin numpy no hay atajo.

En vez de eso se mantiene un buffer emisivo: una superficie pequena (un
cuarto de resolucion) donde solo se dibujan halos. Quien brilla (balas,
fogonazos, explosiones, luces) pinta un halo radial aqui; el resto de la
escena no toca el buffer. El buffer se difumina y se suma sobre la pantalla.

Ventajas, mas alla del coste:

- Control total. El suelo y los muros nunca entran, asi que la imagen no se
  lava ni sube de brillo. Solo brillan las fuentes emisivas.
- Las texturas se generan con circulos concentricos, no con un bucle de
  pixels: el difuminado posterior se come el bandeado.

Alfa premultiplicado
--------------------
El buffer no lleva canal alfa: el falloff va dentro del RGB. Un halo es un
disco con RGB constante y alfa decreciente, y si se sumara tal cual, el disco
saliria de color plano con el borde cortado. Premultiplicando (RGB *= alfa)
el gradiente viaja en el color, que es además el espacio correcto para
difuminar. Ademas el blit final va sobre una fuente opaca, que es la via
rapida de pygame.
"""
import pygame


class Bloom:
    """Halos difuminados que se suman sobre la escena ya dibujada.

    Uso tipico por frame::

        bloom.iniciar()          # vacia el buffer
        ... se dibuja el mundo, quien brille llama a bloom.marcar() ...
        bloom.aplicar(pantalla)  # difumina y suma
    """

    def __init__(self, ancho, alto, escala=4, fuerza=0.9, radio_max=52,
                 caida=1.7, pasadas=2):
        self.ancho = int(ancho)
        self.alto = int(alto)
        # A menor escala el buffer es mas pequeno y el difuminado mas barato,
        # pero los halos pierden definicion. 4 es el punto dulce para 960x640.
        self.escala = max(1, int(escala))
        self.fuerza = fuerza
        self.radio_max = radio_max
        self.caida = caida
        self.pasadas = max(0, int(pasadas))

        self.bw = max(2, self.ancho // self.escala)
        self.bh = max(2, self.alto // self.escala)
        self.hw = max(1, self.bw // 2)
        self.hh = max(1, self.bh // 2)
        # Sin SRCALPHA: el buffer acumula RGB premultiplicado.
        self.capa = pygame.Surface((self.bw, self.bh))
        self.difusa = pygame.Surface((self.bw, self.bh))
        self.half = pygame.Surface((self.hw, self.hh))
        # Destino del reescalado final, a tamano completo. Se reutiliza para no
        # crear una superficie de 960x640 en cada frame.
        self.salida = pygame.Surface((self.ancho, self.alto))

        self._texturas = {}
        self._marcas = 0
        self.activo = True
        # Ultimo coste medido, en ms. Lo consulta el watchdog de rendimiento.
        self.coste_ms = 0.0

    # ------------------------------------------------------------- ciclo
    def iniciar(self):
        """Vacia el buffer. Se llama antes de dibujar el mundo."""
        self._marcas = 0
        if self.activo:
            self.capa.fill((0, 0, 0))

    def aplicar(self, pantalla):
        """Difumina el buffer y lo suma sobre la pantalla."""
        if not self.activo or self._marcas == 0:
            self.coste_ms = 0.0
            return
        t0 = pygame.time.get_ticks()

        # Cada ida y vuelta por la mitad es un paso de convolucion gaussiana
        # muy barato a estas dimensiones. Se encadenan de verdad (el resultado
        # de una pasada es la entrada de la siguiente) para que el halo salga
        # ancho de verdad y no sea un simple reescalado.
        fuente = self.capa
        destino = self.difusa
        for _ in range(self.pasadas):
            pygame.transform.smoothscale(fuente, (self.hw, self.hh),
                                         dest_surface=self.half)
            pygame.transform.smoothscale(self.half, (self.bw, self.bh),
                                         dest_surface=destino)
            if destino is not self.difusa:
                self.difusa, destino = destino, self.difusa
                fuente = self.difusa

        pygame.transform.scale(self.difusa, (self.ancho, self.alto),
                               dest_surface=self.salida)
        pantalla.blit(self.salida, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.coste_ms = pygame.time.get_ticks() - t0

    def limpiar_cache(self):
        self._texturas.clear()

    # ------------------------------------------------------------- halos
    def marcar(self, x, y, radio, color, fuerza=1.0):
        """Registra un halo. ``x``, ``y`` y ``radio`` van en pixeles de pantalla."""
        if not self.activo or fuerza <= 0.02:
            return
        bx = x / self.escala
        by = y / self.escala
        br = radio / self.escala
        if br < 0.8:
            return
        if bx < -br or by < -br or bx > self.bw + br or by > self.bh + br:
            return
        # Un halo mas grande que el tope no aporta nada visible y encarece la
        # textura, asi que se recorta.
        if br > self.radio_max:
            br = self.radio_max
        img = self._textura(br, color, fuerza)
        self.capa.blit(img, (int(bx - img.get_width() / 2),
                             int(by - img.get_height() / 2)),
                       special_flags=pygame.BLEND_RGB_ADD)
        self._marcas += 1

    def _textura(self, radio, color, fuerza):
        # Radio cuantizado a 1 px y fuerza a 6 niveles: el buffer acaba
        # difuminado, asi que mas precision no se ve, y las claves se
        # mantienen contadas.
        rq = max(1, int(round(radio)))
        fq = max(1, min(6, int(round(fuerza * 6))))
        clave = (rq, color, fq)
        img = self._texturas.get(clave)
        if img is None:
            img = self._construir(rq, color, fq / 6.0)
            # Cache acotada: se limpia entera antes de crecer sin limite. Es un
            # salto de coste puntual, no una fuga de memoria.
            if len(self._texturas) > 220:
                self._texturas.clear()
            self._texturas[clave] = img
        return img

    def _construir(self, radio, color, fuerza):
        """Halo radial premultiplicado, con circulos concentricos.

        Se dibuja de fuera hacia dentro con mas brillo: el centro queda claro
        y el borde en negro. Como el destino es opaco y el alfa va ya dentro
        del RGB, este disco se puede sumar tal cual. Construirlo con un bucle
        de pixels costaria milisegundos; esto son unas 30 llamadas a circle.
        """
        lado = radio * 2
        surf = pygame.Surface((lado, lado))
        k = min(1.0, fuerza) * self.fuerza
        cr, cg, cb = color
        pasos = max(8, min(48, radio * 2))
        for i in range(pasos, 0, -1):
            f = i / pasos
            r = int(radio * f)
            if r < 1:
                continue
            # (1 - f) es la caida: 1 en el centro, 0 en el borde.
            a = (1.0 - f) ** self.caida * k
            if a <= 0.004:
                continue
            pygame.draw.circle(surf, (int(cr * a), int(cg * a), int(cb * a)),
                               (radio, radio), r)
        return surf
