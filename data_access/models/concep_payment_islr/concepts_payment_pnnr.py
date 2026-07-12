"""Módulo de opciones para retenciones de ISLR a Personas Naturales No Residentes."""

from decimal import Decimal
from django.db import models


class IslrPnnrChoices(models.IntegerChoices):
    """
    Conceptos de retención de ISLR para Personas Naturales No Residentes (PNNR).

    Mapea la estructura legal de los conceptos de pago con sus respectivos
    atributos como códigos SENIAT, bases imponibles y tarifas porcentuales,
    exponiendo valores decimales listos para operaciones matemáticas confiables.
    """

    HONORARIOS_PROFESIONALES = 1, "Honorarios Profesionales"
    HONORARIOS_PROF_EN_HIPODROMOS = 2, "Honorarios Prof. en Hipódromos"
    HONORARIOS_PROF_EN_CENTROS_DE_SALUD = (
        3,
        "Honorarios Prof. en Centros de Salud",
    )
    COMISIONES_ENAJENACION_INMUEBLES = 4, "Comisiones Enajenación Inmuebles"
    COMISIONES_MERCANTILES_Y_OTRAS = 5, "Comisiones Mercantiles y Otras"
    INTERESES_ART_27_NUM_2_LISLR = 6, "Intereses Art. 27 # 2 L.I.S.L.R."
    INTERESES = 7, "Intereses"
    EXHIBICION_PELICULAS_ART_27_NUM_15_Y_34_LISLR = (
        8,
        "Exhibición de Películas. Art 27 # 15, y 34 LISLR",
    )
    REGALIAS_ART_27_NUM_16_LISLR = 9, "Regalías Art 27 # 16 LISLR"
    ASISTENCIA_TECNICA_ART_27_NUM_16_LISLR = (
        10,
        "Asistencia Técnica Art 27 # 16 LISLR",
    )
    SERVICIOS_TECNOLOGICOS_ART_27_NUM_16_LISLR = (
        11,
        "Servicios Tecnológicos Art 27 # 16 LISLR",
    )
    GANANCIAS_JUEGOS_Y_APUESTAS = 12, "Ganancias en Juegos y Apuestas"
    PREMIOS_LOTERIA_Y_HIPODROMOS_ART_62_LISLR = (
        13,
        "Premios Lotería e Hipódromos Art. 62 LISLR",
    )
    PROPIETARIOS_ANIMALES_CARRERAS_PREMIOS = (
        14,
        "Propietarios de Animales de Carreras por Premios Recibidos",
    )
    SERVICIOS = 15, "Servicios"
    ARRENDAMIENTO_BIENES_INMUEBLES = 16, "Arrendamiento Bienes Inmuebles"
    ARRENDAMIENTO_BIENES_MUEBLES = 17, "Arrendamiento Bienes Muebles"
    PAGOS_TARJETAS_CREDITO_O_CONSUMO = (
        18,
        "Pagos de Tarjetas de Crédito o Consumo",
    )
    PAGOS_ADQUISICION_FONDOS_COMERCIO = (
        19,
        "Pagos por Adquisición de Fondos de Comercio",
    )
    ENRIQUECIMIENTOS_ENAJENACION_ACCIONES_BOLSA = (
        20,
        "Enriquecimientos por Enajenación de Acciones en la Bolsa de Valores",
    )
    PAGOS_ENAJENACION_ACCIONES_FUERA_BOLSA = (
        21,
        "Pagos por Enajenación de Acciones Fuera de la Bolsa de Valores",
    )

    @property
    def title(self) -> str:
        """Retorna el concepto de pago o etiqueta textual."""
        return self.label

    @property
    def numeral_literal(self) -> str:
        """Retorna el numeral o literal correspondiente de la ley."""
        _mapping: dict[int, str] = {
            1: "9.1. a",
            2: "9.1.c",
            3: "9.1.d",
            4: "9.2.a",
            5: "9.2.b",
            6: "9.3. a",
            7: "9.3.c",
            8: "9.6",
            9: "9.7",
            10: "9.7",
            11: "9.7",
            12: "9.9",
            13: "9.9",
            14: "9.10",
            15: "9.11",
            16: "9.12",
            17: "9.13",
            18: "9.14",
            19: "9.18",
            20: "9.20",
            21: "9.21",
        }
        return _mapping[self.value]

    @property
    def code(self) -> str:
        """Retorna el código de concepto oficial asignado por el SENIAT."""
        _mapping: dict[int, str] = {
            1: "003",
            2: "011",
            3: "013",
            4: "015",
            5: "019",
            6: "022",
            7: "026",
            8: "032",
            9: "034",
            10: "036",
            11: "038",
            12: "042",
            13: "046",
            14: "050",
            15: "054",
            16: "058",
            17: "062",
            18: "066",
            19: "080",
            20: "N/A",
            21: "N/A",
        }
        return _mapping[self.value]

    @property
    def base_imponible(self) -> Decimal:
        """Retorna el porcentaje de base imponible aplicable."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("0.90"),
            2: Decimal("0.90"),
            3: Decimal("0.90"),
            4: Decimal("1.00"),
            5: Decimal("1.00"),
            6: Decimal("0.95"),
            7: Decimal("0.95"),
            8: Decimal("0.25"),
            9: Decimal("0.90"),
            10: Decimal("0.30"),
            11: Decimal("0.50"),
            12: Decimal("1.00"),
            13: Decimal("1.00"),
            14: Decimal("1.00"),
            15: Decimal("1.00"),
            16: Decimal("1.00"),
            17: Decimal("1.00"),
            18: Decimal("1.00"),  # Interpretación segura de '**'
            19: Decimal("1.00"),
            20: Decimal("1.00"),
            21: Decimal("1.00"),
        }
        return _mapping[self.value]

    @property
    def percentage(self) -> Decimal:
        """Retorna la tarifa o alícuota de retención del ISLR."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("0.34"),
            2: Decimal("0.34"),
            3: Decimal("0.34"),
            4: Decimal("0.34"),
            5: Decimal("0.34"),
            6: Decimal("0.34"),
            7: Decimal("0.34"),
            8: Decimal("0.34"),
            9: Decimal("0.34"),
            10: Decimal("0.34"),
            11: Decimal("0.34"),
            12: Decimal("0.34"),
            13: Decimal("0.16"),
            14: Decimal("0.34"),
            15: Decimal("0.34"),
            16: Decimal("0.34"),
            17: Decimal("0.34"),
            18: Decimal("0.34"),
            19: Decimal("0.34"),
            20: Decimal("0.01"),
            21: Decimal("0.34"),
        }
        return _mapping[self.value]