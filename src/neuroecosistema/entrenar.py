import csv
import json
from pathlib import Path

import numpy as np

from ecosistema import Ecosistema
from red_neuronal import RedNeuronal, observar


CARPETA = Path(__file__).resolve().parent
MODELOS = CARPETA / "modelos"
RESULTADOS = CARPETA / "resultados"

ESCENARIOS = (
    {
        "nombre": "recursos_suficientes",
        "cantidad_presas": 12,
        "cantidad_depredadores": 2,
        "cantidad_plantas": 35,
    },
    {
        "nombre": "escasez",
        "cantidad_presas": 12,
        "cantidad_depredadores": 2,
        "cantidad_plantas": 8,
    },
    {
        "nombre": "mayor_depredacion",
        "cantidad_presas": 12,
        "cantidad_depredadores": 5,
        "cantidad_plantas": 35,
    },
)

SEMILLAS_ENTRENAMIENTO = list(range(100, 148))
SEMILLAS_VALIDACION = list(range(200, 212))

EPOCAS = 120
TASA = 0.05
TAMANO_LOTE = 128
OCULTAS = (32, 16)
MAX_TURNOS_DATOS = 150
PROBABILIDAD_EXPLORACION = 0.20


def guardar_csv(ruta, filas):
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=list(filas[0]),
        )
        escritor.writeheader()
        escritor.writerows(filas)


def generar_datos(semillas):
    datos = {
        "presa": {"x": [], "y": [], "semillas": []},
        "depredador": {"x": [], "y": [], "semillas": []},
    }

    for numero, semilla in enumerate(semillas):
        escenario = ESCENARIOS[numero % len(ESCENARIOS)]

        ecosistema = Ecosistema(
            semilla=semilla,
            cantidad_presas=escenario["cantidad_presas"],
            cantidad_depredadores=escenario["cantidad_depredadores"],
            cantidad_plantas=escenario["cantidad_plantas"],
            max_turnos=MAX_TURNOS_DATOS,
        )

        azar = np.random.default_rng(semilla + 10_000)

        def profesor_con_exploracion(mundo, agente):
            # La exploración permite visitar estados variados.
            # La etiqueta guardada siempre será la acción del profesor.
            if azar.random() < PROBABILIDAD_EXPLORACION:
                return int(azar.choice(mundo.acciones_validas(agente)))

            return mundo.accion_profesor(agente)

        while not ecosistema.terminado:
            for especie, agentes in (
                ("presa", ecosistema.presas),
                ("depredador", ecosistema.depredadores),
            ):
                # Muestreamos hasta dos agentes por especie y turno.
                cantidad = min(2, len(agentes))
                indices = azar.choice(
                    len(agentes),
                    size=cantidad,
                    replace=False,
                )

                for indice in indices:
                    agente = agentes[int(indice)]

                    datos[especie]["x"].append(
                        observar(ecosistema, agente)
                    )
                    datos[especie]["y"].append(
                        ecosistema.accion_profesor(agente)
                    )
                    datos[especie]["semillas"].append(semilla)

            ecosistema.paso(
                profesor_con_exploracion,
                profesor_con_exploracion,
            )

        if (numero + 1) % 12 == 0:
            print(f"  Episodios generados: {numero + 1}/{len(semillas)}")

    for especie in datos:
        datos[especie]["x"] = np.asarray(
            datos[especie]["x"],
            dtype=np.float64,
        )
        datos[especie]["y"] = np.asarray(
            datos[especie]["y"],
            dtype=np.int64,
        )
        datos[especie]["semillas"] = np.asarray(
            datos[especie]["semillas"],
            dtype=np.int64,
        )

    return datos


def entrenar_especie(especie, entrenamiento, validacion):
    x_entrenamiento = entrenamiento["x"]
    y_entrenamiento = entrenamiento["y"]
    x_validacion = validacion["x"]
    y_validacion = validacion["y"]

    red = RedNeuronal(
        entradas=x_entrenamiento.shape[1],
        ocultas=OCULTAS,
        semilla=42,
    )

    print(f"\nEntrenando especie: {especie}")
    print(f"Arquitectura: {red.dimensiones}")
    print(f"Ejemplos de entrenamiento: {len(y_entrenamiento)}")
    print(f"Ejemplos de validación: {len(y_validacion)}")

    red.guardar(MODELOS / f"{especie}_inicial.npz")
    pesos_iniciales = [peso.copy() for peso in red.pesos]

    perdida_inicial, exactitud_inicial = red.evaluar(
        x_validacion,
        y_validacion,
    )

    historial = red.entrenar(
        x_entrenamiento,
        y_entrenamiento,
        epocas=EPOCAS,
        tasa=TASA,
        tamano_lote=TAMANO_LOTE,
        semilla=123,
    )

    perdida_final, exactitud_final = red.evaluar(
        x_validacion,
        y_validacion,
    )

    cambio_pesos = float(
        np.sqrt(
            sum(
                np.sum((final - inicial) ** 2)
                for final, inicial in zip(
                    red.pesos,
                    pesos_iniciales,
                )
            )
        )
    )

    red.guardar(MODELOS / f"{especie}_entrenado.npz")

    guardar_csv(
        RESULTADOS / f"historial_{especie}.csv",
        historial,
    )

    np.savez_compressed(
        RESULTADOS / f"datos_{especie}.npz",
        x_entrenamiento=x_entrenamiento,
        y_entrenamiento=y_entrenamiento,
        semillas_entrenamiento=entrenamiento["semillas"],
        x_validacion=x_validacion,
        y_validacion=y_validacion,
        semillas_validacion=validacion["semillas"],
    )

    print(
        f"Validación antes: {exactitud_inicial:.2%} | "
        f"Después: {exactitud_final:.2%}"
    )
    print(f"Cambio total en los pesos: {cambio_pesos:.6f}")

    return {
        "especie": especie,
        "arquitectura": list(red.dimensiones),
        "ejemplos_entrenamiento": len(y_entrenamiento),
        "ejemplos_validacion": len(y_validacion),
        "perdida_validacion_inicial": perdida_inicial,
        "exactitud_validacion_inicial": exactitud_inicial,
        "perdida_validacion_final": perdida_final,
        "exactitud_validacion_final": exactitud_final,
        "cambio_pesos": cambio_pesos,
    }


def main():
    MODELOS.mkdir(parents=True, exist_ok=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)

    print("Generando datos de entrenamiento...")
    entrenamiento = generar_datos(SEMILLAS_ENTRENAMIENTO)

    print("\nGenerando datos de validación...")
    validacion = generar_datos(SEMILLAS_VALIDACION)

    resumen = []

    for especie in ("presa", "depredador"):
        resumen.append(
            entrenar_especie(
                especie,
                entrenamiento[especie],
                validacion[especie],
            )
        )

    configuracion = {
        "semillas_entrenamiento": SEMILLAS_ENTRENAMIENTO,
        "semillas_validacion": SEMILLAS_VALIDACION,
        "escenarios": ESCENARIOS,
        "epocas": EPOCAS,
        "tasa": TASA,
        "tamano_lote": TAMANO_LOTE,
        "ocultas": OCULTAS,
        "max_turnos_datos": MAX_TURNOS_DATOS,
        "probabilidad_exploracion": PROBABILIDAD_EXPLORACION,
        "semilla_inicializacion_red": 42,
        "semilla_orden_entrenamiento": 123,
    }

    with (RESULTADOS / "configuracion_entrenamiento.json").open(
        "w",
        encoding="utf-8",
    ) as archivo:
        json.dump(configuracion, archivo, indent=2, ensure_ascii=False)

    with (RESULTADOS / "resumen_entrenamiento.json").open(
        "w",
        encoding="utf-8",
    ) as archivo:
        json.dump(resumen, archivo, indent=2, ensure_ascii=False)

    print("\nEntrenamiento terminado.")
    print(f"Modelos guardados en: {MODELOS}")
    print(f"Resultados guardados en: {RESULTADOS}")


if __name__ == "__main__":
    main()