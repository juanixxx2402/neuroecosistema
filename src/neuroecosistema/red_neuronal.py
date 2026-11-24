from pathlib import Path

import numpy as np

from ecosistema import ALTO_MUNDO, ANCHO_MUNDO, MOVIMIENTOS


def datos_objetivo(agente, posicion):
    """Devuelve distancia relativa en X, en Y y presencia del objetivo."""
    if posicion is None:
        return [0.0, 0.0, 0.0]

    return [
        (posicion[0] - agente.x) / (ANCHO_MUNDO - 1),
        (posicion[1] - agente.y) / (ALTO_MUNDO - 1),
        1.0,
    ]


def observar(ecosistema, agente):
    """Convierte lo que percibe el agente en entradas numéricas."""
    enemigo = ecosistema.enemigo_mas_cercano(agente)
    posicion_enemigo = (
        enemigo.posicion if enemigo is not None else None
    )

    entradas = [agente.energia / 100.0]

    # Para la presa es una amenaza.
    # Para el depredador es la presa que puede perseguir.
    entradas.extend(datos_objetivo(agente, posicion_enemigo))

    if agente.especie == "presa":
        planta = ecosistema.planta_mas_cercana(agente)
        entradas.extend(datos_objetivo(agente, planta))

    # Una entrada por dirección indica si hay un borde.
    for dx, dy in MOVIMIENTOS[:4]:
        bloqueado = not ecosistema.dentro_del_mundo(
            agente.x + dx,
            agente.y + dy,
        )
        entradas.append(float(bloqueado))

    return np.asarray(entradas, dtype=np.float64)


class RedNeuronal:
    def __init__(
        self,
        entradas,
        ocultas=(32, 16),
        salidas=5,
        semilla=42,
    ):
        if len(ocultas) != 2:
            raise ValueError("La red debe tener dos capas ocultas.")

        dimensiones = (entradas, *ocultas, salidas)

        if any(dimension <= 0 for dimension in dimensiones):
            raise ValueError("Las dimensiones deben ser positivas.")

        self.dimensiones = dimensiones
        azar = np.random.default_rng(semilla)

        self.pesos = []
        self.sesgos = []

        for anterior, siguiente in zip(
            dimensiones[:-1],
            dimensiones[1:],
        ):
            # Inicialización de He.
            peso = azar.normal(
                0.0,
                np.sqrt(2.0 / anterior),
                size=(anterior, siguiente),
            )
            self.pesos.append(peso)
            self.sesgos.append(np.zeros((1, siguiente)))

    def _preparar_entradas(self, entradas):
        datos = np.asarray(entradas, dtype=np.float64)

        if datos.ndim == 1:
            datos = datos.reshape(1, -1)

        if (
            datos.ndim != 2
            or datos.shape[0] == 0
            or datos.shape[1] != self.dimensiones[0]
        ):
            raise ValueError(
                f"Se esperan filas de {self.dimensiones[0]} entradas."
            )

        if not np.isfinite(datos).all():
            raise ValueError("Las entradas deben ser números finitos.")

        return datos

    def _propagar(self, entradas):
        z1 = entradas @ self.pesos[0] + self.sesgos[0]
        a1 = np.maximum(0.0, z1)

        z2 = a1 @ self.pesos[1] + self.sesgos[1]
        a2 = np.maximum(0.0, z2)

        z3 = a2 @ self.pesos[2] + self.sesgos[2]

        # Restar el máximo evita desbordamientos numéricos.
        exponenciales = np.exp(
            z3 - np.max(z3, axis=1, keepdims=True)
        )
        probabilidades = exponenciales / exponenciales.sum(
            axis=1,
            keepdims=True,
        )

        return z1, a1, z2, a2, probabilidades

    def probabilidades(self, entradas):
        datos = self._preparar_entradas(entradas)
        return self._propagar(datos)[-1]

    def predecir(self, entradas):
        return np.argmax(self.probabilidades(entradas), axis=1)

    def evaluar(self, entradas, etiquetas):
        datos = self._preparar_entradas(entradas)
        etiquetas = self._preparar_etiquetas(etiquetas, len(datos))

        probabilidades = self.probabilidades(datos)
        probabilidades_correctas = probabilidades[
            np.arange(len(datos)),
            etiquetas,
        ]

        perdida = -np.mean(
            np.log(np.clip(probabilidades_correctas, 1e-12, 1.0))
        )
        exactitud = np.mean(
            np.argmax(probabilidades, axis=1) == etiquetas
        )

        return float(perdida), float(exactitud)

    def _preparar_etiquetas(self, etiquetas, cantidad):
        etiquetas = np.asarray(etiquetas)

        if (
            etiquetas.shape != (cantidad,)
            or not np.issubdtype(etiquetas.dtype, np.integer)
        ):
            raise ValueError(
                "Debe haber una etiqueta entera por ejemplo."
            )

        if np.any(
            (etiquetas < 0)
            | (etiquetas >= self.dimensiones[-1])
        ):
            raise ValueError("Hay etiquetas fuera del rango de acciones.")

        return etiquetas.astype(np.int64, copy=False)

    def entrenar(
        self,
        entradas,
        etiquetas,
        epocas=100,
        tasa=0.05,
        tamano_lote=128,
        semilla=123,
    ):
        datos = self._preparar_entradas(entradas)
        etiquetas = self._preparar_etiquetas(etiquetas, len(datos))

        if epocas < 1 or tamano_lote < 1:
            raise ValueError("Épocas y tamaño de lote deben ser positivos.")

        if not np.isfinite(tasa) or tasa <= 0:
            raise ValueError("La tasa debe ser positiva y finita.")

        azar = np.random.default_rng(semilla)
        historial = []

        for epoca in range(1, epocas + 1):
            indices = azar.permutation(len(datos))

            for inicio in range(0, len(datos), tamano_lote):
                lote = indices[inicio:inicio + tamano_lote]
                x = datos[lote]
                y = etiquetas[lote]

                z1, a1, z2, a2, probabilidades = self._propagar(x)

                # Gradiente de softmax con entropía cruzada.
                dz3 = probabilidades.copy()
                dz3[np.arange(len(x)), y] -= 1.0
                dz3 /= len(x)

                dw3 = a2.T @ dz3
                db3 = dz3.sum(axis=0, keepdims=True)

                dz2 = (dz3 @ self.pesos[2].T) * (z2 > 0)
                dw2 = a1.T @ dz2
                db2 = dz2.sum(axis=0, keepdims=True)

                dz1 = (dz2 @ self.pesos[1].T) * (z1 > 0)
                dw1 = x.T @ dz1
                db1 = dz1.sum(axis=0, keepdims=True)

                # Todos los gradientes se calculan antes de actualizar.
                for indice, (dw, db) in enumerate(
                    ((dw1, db1), (dw2, db2), (dw3, db3))
                ):
                    self.pesos[indice] -= tasa * dw
                    self.sesgos[indice] -= tasa * db

            perdida, exactitud = self.evaluar(datos, etiquetas)
            historial.append(
                {
                    "epoca": epoca,
                    "perdida": perdida,
                    "exactitud": exactitud,
                }
            )

            if epoca == 1 or epoca % 20 == 0 or epoca == epocas:
                print(
                    f"Época {epoca:4d} | "
                    f"Pérdida {perdida:.4f} | "
                    f"Exactitud {exactitud:.2%}"
                )

        return historial

    def guardar(self, ruta):
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        contenido = {
            "dimensiones": np.asarray(self.dimensiones),
        }

        for indice in range(3):
            contenido[f"peso_{indice}"] = self.pesos[indice]
            contenido[f"sesgo_{indice}"] = self.sesgos[indice]

        # Usar un archivo abierto conserva exactamente la ruta indicada.
        with ruta.open("wb") as archivo:
            np.savez_compressed(archivo, **contenido)

    @classmethod
    def cargar(cls, ruta):
        with np.load(ruta, allow_pickle=False) as contenido:
            dimensiones = tuple(
                int(valor)
                for valor in contenido["dimensiones"]
            )

            if len(dimensiones) != 4:
                raise ValueError("La arquitectura guardada es inválida.")

            red = cls(
                entradas=dimensiones[0],
                ocultas=dimensiones[1:3],
                salidas=dimensiones[3],
            )

            for indice in range(3):
                peso = contenido[f"peso_{indice}"]
                sesgo = contenido[f"sesgo_{indice}"]

                if (
                    peso.shape != red.pesos[indice].shape
                    or sesgo.shape != red.sesgos[indice].shape
                    or not np.isfinite(peso).all()
                    or not np.isfinite(sesgo).all()
                ):
                    raise ValueError("Los parámetros guardados son inválidos.")

                red.pesos[indice] = peso.copy()
                red.sesgos[indice] = sesgo.copy()

        return red


def crear_controlador(red):
    """Adapta la red al controlador que recibe Ecosistema.paso."""
    def controlador(ecosistema, agente):
        entradas = observar(ecosistema, agente)
        return int(red.predecir(entradas)[0])

    return controlador