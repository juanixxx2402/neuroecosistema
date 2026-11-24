from dataclasses import dataclass
import random


ANCHO_MUNDO = 20
ALTO_MUNDO = 20

# Cada acción indica cuánto cambia la posición.
MOVIMIENTOS = (
    (0, -1),   # Arriba
    (0, 1),    # Abajo
    (-1, 0),   # Izquierda
    (1, 0),    # Derecha
    (0, 0),    # Quedarse quieto
)

NOMBRES_ACCIONES = (
    "Arriba",
    "Abajo",
    "Izquierda",
    "Derecha",
    "Quieto",
)


@dataclass
class Agente:
    identificador: int
    especie: str
    x: int
    y: int
    energia: float = 100.0
    edad: int = 0
    alimentos: int = 0
    capturas: int = 0
    ultima_accion: int = 4

    @property
    def posicion(self):
        return self.x, self.y


class Ecosistema:
    def __init__(
        self,
        semilla=42,
        cantidad_presas=12,
        cantidad_depredadores=2,
        cantidad_plantas=35,
        max_turnos=500,
    ):
        capacidad = ANCHO_MUNDO * ALTO_MUNDO

        if min(
            cantidad_presas,
            cantidad_depredadores,
            cantidad_plantas,
        ) < 0:
            raise ValueError("Las cantidades no pueden ser negativas.")

        if cantidad_presas + cantidad_depredadores + cantidad_plantas > capacidad:
            raise ValueError("Las cantidades superan el espacio disponible.")

        if max_turnos < 1:
            raise ValueError("El máximo de turnos debe ser positivo.")

        self.semilla = semilla
        self.azar = random.Random(semilla)
        self.max_turnos = max_turnos
        self.turno = 0

        self.cantidad_inicial_presas = cantidad_presas
        self.cantidad_inicial_depredadores = cantidad_depredadores
        self.objetivo_plantas = cantidad_plantas

        self.alimento_consumido = 0
        self.capturas = 0
        self.muertes_por_hambre = 0
        self.primer_turno_captura = None

        # Conservamos los agentes muertos para calcular métricas.
        self.presas_muertas = []
        self.depredadores_muertos = []

        posiciones = [
            (x, y)
            for y in range(ALTO_MUNDO)
            for x in range(ANCHO_MUNDO)
        ]
        self.azar.shuffle(posiciones)

        self.presas = []
        for identificador in range(cantidad_presas):
            x, y = posiciones.pop()
            self.presas.append(
                Agente(identificador, "presa", x, y)
            )

        self.depredadores = []
        for identificador in range(cantidad_depredadores):
            x, y = posiciones.pop()
            self.depredadores.append(
                Agente(identificador, "depredador", x, y)
            )

        self.plantas = {
            posiciones.pop()
            for _ in range(cantidad_plantas)
        }

    @property
    def terminado(self):
        return (
            self.turno >= self.max_turnos
            or not self.presas
            or not self.depredadores
        )

    @staticmethod
    def distancia(posicion_a, posicion_b):
        """Distancia Manhattan entre dos casillas."""
        return (
            abs(posicion_a[0] - posicion_b[0])
            + abs(posicion_a[1] - posicion_b[1])
        )

    @staticmethod
    def dentro_del_mundo(x, y):
        return 0 <= x < ANCHO_MUNDO and 0 <= y < ALTO_MUNDO

    def posicion_resultante(self, agente, accion):
        dx, dy = MOVIMIENTOS[accion]
        x = agente.x + dx
        y = agente.y + dy

        if self.dentro_del_mundo(x, y):
            return x, y

        return agente.posicion

    def acciones_validas(self, agente):
        acciones = []

        for accion, (dx, dy) in enumerate(MOVIMIENTOS):
            if self.dentro_del_mundo(
                agente.x + dx,
                agente.y + dy,
            ):
                acciones.append(accion)

        return acciones

    def planta_mas_cercana(self, agente):
        if not self.plantas:
            return None

        # El desempate por coordenadas hace reproducible la selección.
        return min(
            self.plantas,
            key=lambda posicion: (
                self.distancia(agente.posicion, posicion),
                posicion[0],
                posicion[1],
            ),
        )

    def enemigo_mas_cercano(self, agente):
        enemigos = (
            self.depredadores
            if agente.especie == "presa"
            else self.presas
        )

        if not enemigos:
            return None

        return min(
            enemigos,
            key=lambda enemigo: (
                self.distancia(
                    agente.posicion,
                    enemigo.posicion,
                ),
                enemigo.identificador,
            ),
        )

    def accion_profesor(self, agente):
        """Selecciona una acción usando reglas para cada especie."""
        acciones = self.acciones_validas(agente)
        enemigo = self.enemigo_mas_cercano(agente)

        if agente.especie == "depredador":
            if enemigo is None:
                return 4

            return min(
                acciones,
                key=lambda accion: self.distancia(
                    self.posicion_resultante(agente, accion),
                    enemigo.posicion,
                ),
            )

        planta = self.planta_mas_cercana(agente)

        if (
            enemigo is not None
            and self.distancia(
                agente.posicion,
                enemigo.posicion,
            ) <= 4
        ):
            # Primero busca alejarse del depredador.
            # Si hay empate, prefiere acercarse a una planta.
            return max(
                acciones,
                key=lambda accion: (
                    self.distancia(
                        self.posicion_resultante(agente, accion),
                        enemigo.posicion,
                    ),
                    -self.distancia(
                        self.posicion_resultante(agente, accion),
                        planta,
                    ) if planta is not None else 0,
                ),
            )

        if planta is not None:
            return min(
                acciones,
                key=lambda accion: self.distancia(
                    self.posicion_resultante(agente, accion),
                    planta,
                ),
            )

        return 4

    def mover(self, agente, accion):
        if accion not in range(len(MOVIMIENTOS)):
            raise ValueError(f"Acción inválida: {accion}")

        agente.x, agente.y = self.posicion_resultante(
            agente,
            accion,
        )
        agente.ultima_accion = accion
        agente.edad += 1

        costo = 0.5 if accion == 4 else 1.0
        agente.energia = max(0.0, agente.energia - costo)

    def alimentar_presas(self):
        for presa in self.presas:
            if presa.posicion in self.plantas:
                self.plantas.remove(presa.posicion)
                presa.energia = min(
                    100.0,
                    presa.energia + 25.0,
                )
                presa.alimentos += 1
                self.alimento_consumido += 1

    def resolver_capturas(self, posiciones_anteriores):
        capturadas = set()

        for depredador in self.depredadores:
            for presa in self.presas:
                if presa.identificador in capturadas:
                    continue

                misma_casilla = (
                    depredador.posicion == presa.posicion
                )

                # También hay captura cuando intercambian casillas.
                cruce = (
                    posiciones_anteriores[
                        ("depredador", depredador.identificador)
                    ] == presa.posicion
                    and posiciones_anteriores[
                        ("presa", presa.identificador)
                    ] == depredador.posicion
                )

                if misma_casilla or cruce:
                    capturadas.add(presa.identificador)
                    depredador.capturas += 1
                    depredador.energia = min(
                        100.0,
                        depredador.energia + 40.0,
                    )
                    self.capturas += 1

                    if self.primer_turno_captura is None:
                        self.primer_turno_captura = self.turno

                    # Máximo una presa por depredador en cada turno.
                    break

        self.presas_muertas.extend(
            presa
            for presa in self.presas
            if presa.identificador in capturadas
        )
        self.presas = [
            presa
            for presa in self.presas
            if presa.identificador not in capturadas
        ]

    def retirar_agentes_sin_energia(self):
        presas_sin_energia = [
            presa
            for presa in self.presas
            if presa.energia <= 0
        ]
        depredadores_sin_energia = [
            depredador
            for depredador in self.depredadores
            if depredador.energia <= 0
        ]

        self.muertes_por_hambre += (
            len(presas_sin_energia)
            + len(depredadores_sin_energia)
        )

        self.presas_muertas.extend(presas_sin_energia)
        self.depredadores_muertos.extend(
            depredadores_sin_energia
        )

        self.presas = [
            presa
            for presa in self.presas
            if presa.energia > 0
        ]
        self.depredadores = [
            depredador
            for depredador in self.depredadores
            if depredador.energia > 0
        ]

    def regenerar_plantas(self):
        """Cada cinco turnos aparece como máximo una planta."""
        if (
            self.turno % 5 != 0
            or len(self.plantas) >= self.objetivo_plantas
        ):
            return

        ocupadas = self.plantas | {
            agente.posicion
            for agente in self.presas + self.depredadores
        }

        disponibles = [
            (x, y)
            for y in range(ALTO_MUNDO)
            for x in range(ANCHO_MUNDO)
            if (x, y) not in ocupadas
        ]

        if disponibles:
            self.plantas.add(self.azar.choice(disponibles))

    def paso(self, controlador_presas=None, controlador_depredadores=None):
        """
        Avanza un turno.

        Un controlador recibe (ecosistema, agente) y devuelve
        un número de acción entre 0 y 4.
        """
        if self.terminado:
            return

        agentes = self.presas + self.depredadores

        posiciones_anteriores = {
            (agente.especie, agente.identificador): agente.posicion
            for agente in agentes
        }

        # Todas las decisiones se toman antes de mover agentes.
        decisiones = []

        for agente in agentes:
            controlador = (
                controlador_presas
                if agente.especie == "presa"
                else controlador_depredadores
            )

            accion = (
                self.accion_profesor(agente)
                if controlador is None
                else controlador(self, agente)
            )

            if accion not in range(len(MOVIMIENTOS)):
                raise ValueError(f"Acción inválida: {accion}")

            decisiones.append((agente, accion))

        self.turno += 1

        for agente, accion in decisiones:
            self.mover(agente, accion)

        self.resolver_capturas(posiciones_anteriores)
        self.alimentar_presas()
        self.retirar_agentes_sin_energia()
        self.regenerar_plantas()

    def estadisticas(self):
        todas_las_presas = self.presas + self.presas_muertas

        supervivencia_media = (
            sum(presa.edad for presa in todas_las_presas)
            / len(todas_las_presas)
            if todas_las_presas
            else 0.0
        )

        return {
            "semilla": self.semilla,
            "turno": self.turno,
            "presas_vivas": len(self.presas),
            "depredadores_vivos": len(self.depredadores),
            "plantas": len(self.plantas),
            "alimento_consumido": self.alimento_consumido,
            "capturas": self.capturas,
            "muertes_por_hambre": self.muertes_por_hambre,
            "supervivencia_media_turnos": supervivencia_media,
            "primer_turno_captura": self.primer_turno_captura,
        }