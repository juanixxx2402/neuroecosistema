"""Interfaz de NeuroEcosistema. Ejecutar junto a ecosistema.py y red_neuronal.py."""
from pathlib import Path
import json
import math
import random

import pygame

from ecosistema import Ecosistema, ANCHO_MUNDO, ALTO_MUNDO, NOMBRES_ACCIONES
from red_neuronal import RedNeuronal, crear_controlador, observar

BASE = Path(__file__).resolve().parent
VENTANA = (1180, 800)
TABLERO = pygame.Rect(28, 138, 600, 600)
FONDO = (242, 245, 239)
TINTA = (35, 57, 48)
SUAVE = (106, 124, 113)
VERDE = (48, 111, 83)
MAPAS = (
    dict(nombre="Pradera", detalle="Alimento distribuido por todo el terreno", plantas=35, depredadores=2, suelo=(218, 232, 195)),
    dict(nombre="Bosque", detalle="Plantas concentradas en cuatro claros", plantas=35, depredadores=2, suelo=(188, 215, 181)),
    dict(nombre="Oasis", detalle="Alimento escaso alrededor del centro", plantas=8, depredadores=2, suelo=(235, 221, 185)),
    dict(nombre="Territorio de caza", detalle="Más depredadores y alimento disperso", plantas=35, depredadores=5, suelo=(214, 224, 199)),
)
MODOS = ("Red entrenada", "Red inicial", "Profesor")
CAMPO_SEMILLA = pygame.Rect(716, 22, 145, 36)


def piedras_del_mapa(mapa):
    """Obstáculos fijos por mapa, con pasos entre todas las zonas libres."""
    if mapa == 0:
        grupos = ((4, 4, 2, 2), (13, 3, 3, 2), (8, 9, 2, 3),
                  (3, 14, 3, 2), (14, 14, 2, 3))
    elif mapa == 1:
        grupos = ((9, 2, 2, 5), (9, 12, 2, 6),
                  (2, 9, 5, 2), (13, 9, 5, 2))
    elif mapa == 2:
        grupos = ((6, 6, 3, 1), (11, 6, 3, 1),
                  (6, 13, 3, 1), (11, 13, 3, 1),
                  (6, 8, 1, 4), (13, 8, 1, 4))
    else:
        grupos = ((4, 2, 1, 5), (4, 10, 1, 6),
                  (9, 5, 1, 6), (14, 2, 1, 5), (14, 10, 1, 6),
                  (7, 15, 5, 1))
    return {(x, y) for inicio_x, inicio_y, ancho, alto in grupos
            for x in range(inicio_x, inicio_x + ancho)
            for y in range(inicio_y, inicio_y + alto)}


class MundoVisual(Ecosistema):
    """Añade piedras y distribuciones de alimento a las reglas del simulador."""
    def __init__(self, mapa, semilla):
        self.mapa = mapa
        self.piedras = piedras_del_mapa(mapa)
        ficha = MAPAS[mapa]
        super().__init__(semilla=semilla, cantidad_presas=12,
                         cantidad_depredadores=ficha['depredadores'],
                         cantidad_plantas=ficha['plantas'])
        self.plantas.clear()
        # El constructor base reparte agentes sin conocer las piedras.
        # Reubicamos únicamente aquellos que quedaron sobre un obstáculo.
        agentes = self.presas + self.depredadores
        ocupadas = {agente.posicion for agente in agentes}
        libres = [(x, y) for y in range(ALTO_MUNDO) for x in range(ANCHO_MUNDO)
                  if self.dentro_del_mundo(x, y) and (x, y) not in ocupadas]
        azar_posiciones = random.Random(semilla + 70000)
        azar_posiciones.shuffle(libres)
        for agente in agentes:
            if agente.posicion in self.piedras:
                agente.x, agente.y = libres.pop()
        self.azar_alimento = random.Random(semilla + 50000)
        for _ in range(self.objetivo_plantas):
            self.agregar_planta()

    def dentro_del_mundo(self, x, y):
        # Movimiento, acciones válidas y observar() consultan este método.
        # Así el bloqueo se aplica también a las decisiones de las redes.
        return super().dentro_del_mundo(x, y) and (x, y) not in self.piedras

    def agregar_planta(self):
        ocupadas = self.piedras | self.plantas | {
            a.posicion for a in self.presas + self.depredadores
        }
        libres = [(x, y) for y in range(ALTO_MUNDO) for x in range(ANCHO_MUNDO)
                  if (x, y) not in ocupadas]
        if not libres:
            return
        pesos = []
        for x, y in libres:
            if self.mapa == 1:
                distancia = min(abs(x-cx) + abs(y-cy)
                                for cx, cy in ((4, 4), (15, 4), (4, 15), (15, 15)))
                peso = math.exp(-distancia / 1.8)
            elif self.mapa == 2:
                distancia = abs(x-9.5) + abs(y-9.5)
                peso = math.exp(-distancia / 2.0)
            else:
                peso = 1.0
            pesos.append(peso)
        self.plantas.add(self.azar_alimento.choices(libres, weights=pesos, k=1)[0])

    def regenerar_plantas(self):
        if self.turno % 5 == 0 and len(self.plantas) < self.objetivo_plantas:
            self.agregar_planta()


def texto(superficie, contenido, posicion, tamano=18, color=TINTA, negrita=False):
    fuente = pygame.font.SysFont('segoeui', tamano, bold=negrita)
    superficie.blit(fuente.render(str(contenido), True, color), posicion)


def conejo(superficie, centro):
    x, y = centro
    pygame.draw.ellipse(superficie, (103, 124, 97), (x-9, y+6, 19, 6))
    pygame.draw.ellipse(superficie, (251, 250, 240), (x-9, y-5, 18, 18))
    pygame.draw.ellipse(superficie, (251, 250, 240), (x-7, y-15, 6, 16))
    pygame.draw.ellipse(superficie, (251, 250, 240), (x+1, y-15, 6, 16))
    pygame.draw.ellipse(superficie, (228, 171, 166), (x-5, y-12, 2, 9))
    pygame.draw.ellipse(superficie, (228, 171, 166), (x+3, y-12, 2, 9))
    pygame.draw.circle(superficie, TINTA, (x-4, y+1), 2)
    pygame.draw.circle(superficie, TINTA, (x+4, y+1), 2)
    pygame.draw.circle(superficie, (222, 146, 140), (x, y+5), 2)


def zorro(superficie, centro):
    x, y = centro
    pygame.draw.ellipse(superficie, (103, 124, 97), (x-11, y+7, 22, 6))
    pygame.draw.polygon(superficie, (191, 92, 46), [(x-11,y-13),(x-10,y+3),(x,y+12),(x+10,y+3),(x+11,y-13),(x+3,y-7),(x-3,y-7)])
    pygame.draw.polygon(superficie, (91, 59, 49), [(x-9,y-10),(x-8,y-4),(x-5,y-6)])
    pygame.draw.polygon(superficie, (91, 59, 49), [(x+9,y-10),(x+8,y-4),(x+5,y-6)])
    pygame.draw.polygon(superficie, (255, 235, 200), [(x-10,y+1),(x-2,y+3),(x,y+10)])
    pygame.draw.polygon(superficie, (255, 235, 200), [(x+10,y+1),(x+2,y+3),(x,y+10)])
    pygame.draw.circle(superficie, TINTA, (x-4, y-1), 2)
    pygame.draw.circle(superficie, TINTA, (x+4, y-1), 2)
    pygame.draw.circle(superficie, TINTA, (x, y+7), 2)


def piedra(superficie, centro):
    x, y = centro
    pygame.draw.ellipse(superficie, (111, 119, 101), (x-13, y+5, 27, 9))
    contorno = [(x-13, y+5), (x-11, y-5), (x-5, y-12),
                (x+6, y-11), (x+13, y-3), (x+12, y+8), (x+3, y+12)]
    pygame.draw.polygon(superficie, (126, 137, 137), contorno)
    pygame.draw.polygon(superficie, (168, 178, 173),
                        [(x-11, y-5), (x-5, y-12), (x+6, y-11), (x+3, y-1), (x-5, y+3)])
    pygame.draw.polygon(superficie, (100, 112, 115),
                        [(x+3, y-1), (x+6, y-11), (x+13, y-3), (x+12, y+8), (x+3, y+12)])
    pygame.draw.polygon(superficie, (95, 109, 105), contorno, width=1)


class Aplicacion:
    def __init__(self):
        self.pantalla = pygame.display.set_mode(VENTANA)
        pygame.display.set_caption('NeuroEcosistema · Laboratorio de comportamiento')
        self.redes = {}
        for especie in ('presa', 'depredador'):
            for estado in ('entrenado', 'inicial'):
                ruta = BASE / 'modelos' / f'{especie}_{estado}.npz'
                if not ruta.exists():
                    raise FileNotFoundError(f'Falta {ruta}. Ejecuta entrenar.py primero.')
                self.redes[especie, estado] = RedNeuronal.cargar(ruta)
        self.mapa = 0
        self.modo = 0
        self.semilla = 42
        self.velocidad = 6
        self.rutas = True
        self.botones = []
        self.editando_semilla = False
        self.texto_semilla = str(self.semilla)
        self.mensaje_semilla = ''
        self.metricas = self.cargar_metricas()
        self.reiniciar()

    def cargar_metricas(self):
        ruta = BASE / 'resultados' / 'resumen_entrenamiento.json'
        try:
            with ruta.open(encoding='utf-8') as archivo:
                resumen = json.load(archivo)
            if not isinstance(resumen, list):
                return {}
            metricas = {}
            for fila in resumen:
                if not isinstance(fila, dict):
                    continue
                especie = fila.get('especie')
                if especie not in ('presa', 'depredador'):
                    continue
                for estado, sufijo in (('inicial', 'inicial'), ('entrenado', 'final')):
                    perdida = fila.get(f'perdida_validacion_{sufijo}')
                    exactitud = fila.get(f'exactitud_validacion_{sufijo}')
                    if (type(perdida) in (int, float)
                            and type(exactitud) in (int, float)
                            and math.isfinite(perdida) and perdida >= 0
                            and math.isfinite(exactitud) and 0 <= exactitud <= 1):
                        metricas[especie, estado] = (perdida, exactitud)
            return metricas
        except (OSError, ValueError):
            return {}

    def aplicar_semilla(self):
        if not self.texto_semilla or not self.texto_semilla.isascii() or not self.texto_semilla.isdigit():
            self.mensaje_semilla = 'Escribe un entero positivo o cero.'
            return
        self.semilla = int(self.texto_semilla)
        self.editando_semilla = False
        pygame.key.stop_text_input()
        self.mensaje_semilla = ''
        self.reiniciar()

    def tecla_semilla(self, evento):
        if evento.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.aplicar_semilla()
        elif evento.key == pygame.K_ESCAPE:
            self.texto_semilla = str(self.semilla)
            self.editando_semilla = False
            self.mensaje_semilla = ''
            pygame.key.stop_text_input()
        elif evento.key == pygame.K_BACKSPACE:
            self.texto_semilla = self.texto_semilla[:-1]
        elif evento.key == pygame.K_a and evento.mod & pygame.KMOD_CTRL:
            self.texto_semilla = ''

    def reiniciar(self):
        self.mundo = MundoVisual(self.mapa, self.semilla)
        self.pausa = True
        self.acumulado = 0.0
        self.seleccionado = None
        self.rastros = {}
        self.serie = [(len(self.mundo.presas), len(self.mundo.depredadores))]
        self.texto_semilla = str(self.semilla)
        if self.modo == 2:
            self.controladores = (None, None)
        else:
            estado = ('entrenado', 'inicial')[self.modo]
            self.controladores = tuple(crear_controlador(self.redes[e, estado])
                                       for e in ('presa', 'depredador'))

    def paso(self):
        if self.mundo.terminado:
            return
        for a in self.mundo.presas + self.mundo.depredadores:
            clave = (a.especie, a.identificador)
            rastro = self.rastros.setdefault(clave, [])
            rastro.append(a.posicion)
            del rastro[:-24]
        self.mundo.paso(*self.controladores)
        self.serie.append((len(self.mundo.presas), len(self.mundo.depredadores)))
        if self.seleccionado not in self.mundo.presas + self.mundo.depredadores:
            self.seleccionado = None

    def centro(self, posicion):
        x, y = posicion
        return TABLERO.x + x*30 + 15, TABLERO.y + y*30 + 15

    def boton(self, etiqueta, rectangulo, accion, activo=False):
        rectangulo = pygame.Rect(rectangulo)
        pygame.draw.rect(self.pantalla, VERDE if activo else (226, 233, 223), rectangulo, border_radius=9)
        texto(self.pantalla, etiqueta, (rectangulo.x+12, rectangulo.y+9), 16,
              (255, 255, 255) if activo else TINTA, True)
        self.botones.append((rectangulo, accion))

    def tablero(self):
        ficha = MAPAS[self.mapa]
        pygame.draw.rect(self.pantalla, ficha['suelo'], TABLERO, border_radius=12)
        # Textura fija e independiente de la semilla del episodio.
        azar = random.Random(99 + self.mapa)
        for _ in range(240):
            x = azar.randrange(TABLERO.x+8, TABLERO.right-8)
            y = azar.randrange(TABLERO.y+8, TABLERO.bottom-8)
            color = tuple(max(0, c-12) for c in ficha['suelo'])
            pygame.draw.line(self.pantalla, color, (x,y), (x+2,y-3))
        for posicion in sorted(self.mundo.piedras):
            piedra(self.pantalla, self.centro(posicion))
        for x, y in sorted(self.mundo.plantas):
            cx, cy = self.centro((x,y))
            pygame.draw.line(self.pantalla, VERDE, (cx,cy+6), (cx,cy-3), 2)
            pygame.draw.ellipse(self.pantalla, (62,135,75), (cx-8,cy-5,9,6))
            pygame.draw.ellipse(self.pantalla, (90,160,83), (cx,cy-8,9,6))
        if self.rutas and self.seleccionado is not None:
            a = self.seleccionado
            ruta = self.rastros.get((a.especie,a.identificador), []) + [a.posicion]
            if len(ruta) > 1:
                pygame.draw.lines(self.pantalla, (202,164,55), False, [self.centro(p) for p in ruta], 3)
        for a in self.mundo.presas:
            conejo(self.pantalla, self.centro(a.posicion))
        for a in self.mundo.depredadores:
            zorro(self.pantalla, self.centro(a.posicion))
        if self.seleccionado is not None:
            pygame.draw.circle(self.pantalla, (244,190,55), self.centro(self.seleccionado.posicion), 16, 2)

    def panel(self):
        s = self.pantalla
        pygame.draw.rect(s, (255,255,251), (650,138,502,600), border_radius=14)
        texto(s, 'Estado del ecosistema', (672,154), 21, negrita=True)
        for i, (nombre, valor, color) in enumerate((
            ('Presas', len(self.mundo.presas), VERDE),
            ('Depredadores', len(self.mundo.depredadores), (186,90,48)),
            ('Plantas', len(self.mundo.plantas), (111,142,61)),
        )):
            x = 672 + i*156
            texto(s, nombre, (x,191), 16, SUAVE)
            texto(s, valor, (x,212), 30, color, True)
        texto(s, f'Alimento consumido  {self.mundo.alimento_consumido}     Capturas  {self.mundo.capturas}', (672,255), 17)
        texto(s, f'Turno {self.mundo.turno} / {self.mundo.max_turnos}     Semilla {self.semilla}', (672,282), 17, SUAVE)
        texto(s, 'Población durante el episodio', (672,314), 17, negrita=True)
        grafico = pygame.Rect(680,342,444,48)
        pygame.draw.line(s, (218,226,215), grafico.bottomleft, grafico.bottomright)
        if len(self.serie) > 1:
            for especie, color in ((0,VERDE),(1,(186,90,48))):
                puntos = [(grafico.x+i/(len(self.serie)-1)*grafico.width,
                           grafico.bottom-valores[especie]/12*grafico.height)
                          for i,valores in enumerate(self.serie)]
                pygame.draw.lines(s, color, False, puntos, 2)
        self.panel_metricas()
        texto(s, 'Agente seleccionado', (672,535), 19, negrita=True)
        a = self.seleccionado
        if a is None:
            texto(s, 'Haz clic sobre un conejo o un zorro.', (672,575), 17, SUAVE)
            texto(s, 'Verás su energía, recorrido y decisiones.', (672,602), 17, SUAVE)
        else:
            texto(s, f'{a.especie.capitalize()} #{a.identificador}    Energía {a.energia:.1f}    Edad {a.edad}', (672,568), 17)
            if self.modo == 2:
                accion = self.mundo.accion_profesor(a)
                texto(s, f'Próxima acción del profesor: {NOMBRES_ACCIONES[accion]}', (672,605), 17)
            else:
                estado = ('entrenado','inicial')[self.modo]
                probabilidades = self.redes[a.especie,estado].probabilidades(observar(self.mundo,a))[0]
                for i, (nombre, probabilidad) in enumerate(zip(NOMBRES_ACCIONES, probabilidades)):
                    y = 597+i*22
                    texto(s, nombre, (672,y), 15)
                    pygame.draw.rect(s, (233,238,229), (765,y+5,270,11), border_radius=5)
                    pygame.draw.rect(s, VERDE, (765,y+5,round(270*float(probabilidad)),11), border_radius=5)
                    texto(s, f'{probabilidad:.0%}', (1050,y), 15)
                texto(s, 'Probabilidades para la próxima decisión', (672,714), 14, SUAVE)

    def panel_metricas(self):
        s = self.pantalla
        pygame.draw.line(s, (225,232,221), (672,401), (1128,401))
        texto(s, 'Evaluación guardada · validación', (672,410), 18, negrita=True)
        if self.modo == 2:
            texto(s, 'Profesor de reglas seleccionado.', (672,445), 17)
            texto(s, 'Pérdida y precisión neuronal: no aplica.', (672,473), 16, SUAVE)
            return
        estado = ('entrenado', 'inicial')[self.modo]
        texto(s, 'Especie', (672,442), 15, SUAVE)
        texto(s, 'Pérdida', (830,442), 15, SUAVE)
        texto(s, 'Precisión', (996,442), 15, SUAVE)
        for i, especie in enumerate(('presa', 'depredador')):
            y = 465 + i*24
            valores = self.metricas.get((especie, estado))
            texto(s, especie.capitalize(), (672,y), 16)
            perdida, exactitud = ('—', '—') if valores is None else (f'{valores[0]:.4f}', f'{valores[1]:.2%}')
            texto(s, perdida, (830,y), 16, VERDE)
            texto(s, exactitud, (996,y), 16, VERDE)
        if all((especie, estado) in self.metricas for especie in ('presa', 'depredador')):
            nota = 'Precisión = acciones que coinciden con el profesor.'
        else:
            nota = 'Revisa resultados/resumen_entrenamiento.json.'
        texto(s, nota, (672,516), 14, SUAVE)

    def dibujar(self):
        self.pantalla.fill(FONDO)
        self.botones.clear()
        texto(self.pantalla, 'NeuroEcosistema', (28,20), 30, negrita=True)
        texto(self.pantalla, 'Laboratorio de comportamiento', (341,32), 18, SUAVE)
        texto(self.pantalla, 'Semilla', (650,31), 16, SUAVE)
        pygame.draw.rect(self.pantalla, (255,255,251), CAMPO_SEMILLA, border_radius=7)
        pygame.draw.rect(self.pantalla, VERDE if self.editando_semilla else (198,210,195), CAMPO_SEMILLA, width=2, border_radius=7)
        valor = self.texto_semilla + ('|' if self.editando_semilla and pygame.time.get_ticks() % 1000 < 500 else '')
        texto(self.pantalla, valor, (CAMPO_SEMILLA.x+10,CAMPO_SEMILLA.y+8), 16)
        self.boton('Aplicar', (870,22,110,36), ('aplicar_semilla',None))
        if self.mensaje_semilla:
            texto(self.pantalla, self.mensaje_semilla, (650,60), 13, (177,70,49))
        estado = 'Finalizado' if self.mundo.terminado else ('En pausa' if self.pausa else 'En ejecución')
        texto(self.pantalla, estado, (1010,32), 17, VERDE, True)
        for i, ficha in enumerate(MAPAS):
            self.boton(f'{i+1}  {ficha["nombre"]}', (28+i*282,80,270,40), ('mapa',i), self.mapa==i)
        self.tablero()
        self.panel()
        texto(self.pantalla, f"{MAPAS[self.mapa]['detalle']} · {len(self.mundo.piedras)} piedras", (28,744), 14, SUAVE)
        self.boton('Continuar' if self.pausa else 'Pausar', (28,766,120,32), ('pausa',None), True)
        self.boton('Un turno', (158,766,110,32), ('paso',None))
        self.boton('Reiniciar', (278,766,110,32), ('reiniciar',None))
        self.boton('Otra semilla', (398,766,135,32), ('semilla',None))
        self.boton(MODOS[self.modo], (658,766,165,32), ('modo',None))
        texto(self.pantalla, f'{self.velocidad} t/s   ↑ ↓', (843,773), 15)
        texto(self.pantalla, 'Espacio · pausa   Esc · salir', (975,773), 13, SUAVE)

    def actuar(self, accion, valor=None):
        if accion == 'pausa':
            self.pausa = not self.pausa
            self.acumulado = 0.0
        elif accion == 'paso':
            self.pausa = True
            self.paso()
        elif accion == 'reiniciar':
            self.reiniciar()
        elif accion == 'semilla':
            self.semilla += 1
            self.reiniciar()
        elif accion == 'aplicar_semilla':
            self.aplicar_semilla()
        elif accion == 'mapa':
            self.mapa = valor
            self.reiniciar()
        elif accion == 'modo':
            self.modo = (self.modo+1) % len(MODOS)
            self.reiniciar()

    def ejecutar(self):
        reloj = pygame.time.Clock()
        activo = True
        self.dibujar()
        while activo:
            segundos = min(reloj.tick(60)/1000, 0.25)
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    activo = False
                elif evento.type == pygame.TEXTINPUT and self.editando_semilla:
                    if evento.text.isascii() and evento.text.isdigit():
                        self.texto_semilla = (self.texto_semilla + evento.text)[:12]
                        self.mensaje_semilla = ''
                elif evento.type == pygame.KEYDOWN:
                    if self.editando_semilla:
                        self.tecla_semilla(evento)
                    elif evento.key == pygame.K_ESCAPE:
                        activo = False
                    elif evento.key == pygame.K_SPACE:
                        self.actuar('pausa')
                    elif evento.key == pygame.K_n:
                        self.actuar('paso')
                    elif evento.key == pygame.K_r:
                        self.actuar('reiniciar')
                    elif evento.key == pygame.K_s:
                        self.actuar('semilla')
                    elif evento.key == pygame.K_m:
                        self.actuar('modo')
                    elif evento.key == pygame.K_UP:
                        self.velocidad = min(30,self.velocidad+1)
                    elif evento.key == pygame.K_DOWN:
                        self.velocidad = max(1,self.velocidad-1)
                    elif evento.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):
                        self.actuar('mapa',evento.key-pygame.K_1)
                elif evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                    if CAMPO_SEMILLA.collidepoint(evento.pos):
                        self.editando_semilla = True
                        self.pausa = True
                        self.acumulado = 0.0
                        self.texto_semilla = ''
                        pygame.key.start_text_input()
                        pygame.key.set_text_input_rect(CAMPO_SEMILLA)
                        continue
                    self.editando_semilla = False
                    pygame.key.stop_text_input()
                    for rectangulo, (accion, valor) in self.botones:
                        if rectangulo.collidepoint(evento.pos):
                            self.actuar(accion,valor)
                            break
                    else:
                        if TABLERO.collidepoint(evento.pos):
                            celda = ((evento.pos[0]-TABLERO.x)//30,(evento.pos[1]-TABLERO.y)//30)
                            self.seleccionado = next((a for a in self.mundo.presas+self.mundo.depredadores
                                                      if a.posicion==celda),None)
            if not self.pausa and not self.mundo.terminado:
                self.acumulado += segundos
                while self.acumulado >= 1/self.velocidad and not self.mundo.terminado:
                    self.paso()
                    self.acumulado -= 1/self.velocidad
            self.dibujar()
            pygame.display.flip()


def main():
    pygame.init()
    try:
        Aplicacion().ejecutar()
    finally:
        pygame.quit()


if __name__ == '__main__':
    main()
