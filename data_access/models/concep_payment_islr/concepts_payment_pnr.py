"""Módulo de opciones para retenciones de ISLR a Personas Naturales Residentes."""

from decimal import Decimal
from django.db import models


class IslrPnrChoices(models.IntegerChoices):
    """
    Conceptos de retención de ISLR para Personas Naturales Residentes (PNR).

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
    INTERESES = 6, "Intereses"
    GANANCIAS_JUEGOS_Y_APUESTAS = 7, "Ganancias en Juegos y Apuestas"
    PREMIOS_LOTERIA_Y_HIPODROMOS_ART_62_LISLR = (
        8,
        "Premios Lotería e Hipódromos Art. 62 LISLR",
    )
    PROPIETARIOS_ANIMALES_CARRERAS_PREMIOS = (
        9,
        "Propietarios de Animales de Carreras por Premios Recibidos",
    )
    SERVICIOS = 10, "Servicios"
    ARRENDAMIENTO_BIENES_INMUEBLES = 11, "Arrendamiento Bienes Inmuebles"
    ARRENDAMIENTO_BIENES_MUEBLES = 12, "Arrendamiento Bienes Muebles"
    PAGOS_TARJETAS_CREDITO_O_CONSUMO = (
        13,
        "Pagos de Tarjetas de Crédito o Consumo",
    )
    PAGO_GASOLINA_TARJETA_CREDITO_O_CONSUMO = (
        14,
        "Pago de Gasolina con Tarjeta de Crédito o Consumo",
    )
    FLETES_Y_GASTOS_TRANSPORTE_NACIONAL = (
        15,
        "Fletes y Gastos de Transporte Nacional",
    )
    PAGO_EMP_SEGURO_A_CORREDORES = 16, "Pago de Emp.de Seguro a Corredores"
    PAGO_EMPRESAS_SEGUROS_REPARACION_BIENES = (
        17,
        "Pago de Empresas de Seguros por Reparación de Bienes de sus Asegurados",
    )
    PAGOS_EMPRESAS_SEGURO_CENTROS_SALUD_ATENCION = (
        18,
        (
            "Pagos de Empresas de Seguro a Centros de Salud por Atención de sus"
            " Asegurados"
        ),
    )
    PAGOS_ADQUISICION_FONDOS_COMERCIO = (
        19,
        "Pagos por Adquisición de Fondos de Comercio",
    )
    PUBLICIDAD_Y_PROPAGANDA = 20, "Publicidad y Propaganda"
    ENRIQUECIMIENTOS_ENAJENACION_ACCIONES_BOLSA = (
        21,
        "Enriquecimientos por Enajenación de Acciones en la Bolsa de Valores",
    )
    PAGOS_ENAJENACION_ACCIONES_FUERA_BOLSA = (
        22,
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
            1: "9.1. b",
            2: "9.1.c",
            3: "9.1.d",
            4: "9.2.a",
            5: "9.2.b",
            6: "9.3.c",
            7: "9.9",
            8: "9.9",
            9: "9.10",
            10: "9.11",
            11: "9.12",
            12: "9.13",
            13: "9.14",
            14: "9.14",
            15: "9.15",
            16: "9.16",
            17: "9.17",
            18: "9.17",
            19: "9.18",
            20: "9.19",
            21: "9.20",
            22: "9.21",
        }
        return _mapping[self.value]

    @property
    def code(self) -> str:
        """Retorna el código de concepto oficial asignado por el SENIAT."""
        _mapping: dict[int, str] = {
            1: "002",
            2: "010",
            3: "012",
            4: "014",
            5: "018",
            6: "025",
            7: "041",
            8: "045",
            9: "049",
            10: "053",
            11: "057",
            12: "061",
            13: "065",
            14: "069",
            15: "071",
            16: "073",
            17: "075",
            18: "077",
            19: "079",
            20: "083",
            21: "N/A",
            22: "N/A",
        }
        return _mapping[self.value]

    @property
    def base_imponible(self) -> Decimal:
        """Retorna el porcentaje de base imponible aplicable."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("1.00"),
            2: Decimal("1.00"),
            3: Decimal("1.00"),
            4: Decimal("1.00"),
            5: Decimal("1.00"),
            6: Decimal("1.00"),
            7: Decimal("1.00"),
            8: Decimal("1.00"),
            9: Decimal("1.00"),
            10: Decimal("1.00"),
            11: Decimal("1.00"),
            12: Decimal("1.00"),
            13: Decimal("1.00"),  # Interpretación segura de '**' para base entera
            14: Decimal("1.00"),  # Interpretación segura de '**' para base entera
            15: Decimal("1.00"),
            16: Decimal("1.00"),
            17: Decimal("1.00"),
            18: Decimal("1.00"),
            19: Decimal("1.00"),
            20: Decimal("1.00"),
            21: Decimal("1.00"),
            22: Decimal("1.00"),
        }
        return _mapping[self.value]

    @property
    def percentage(self) -> Decimal:
        """Retorna la tarifa o alícuota de retención del ISLR."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("0.03"),
            2: Decimal("0.03"),
            3: Decimal("0.03"),
            4: Decimal("0.03"),
            5: Decimal("0.03"),
            6: Decimal("0.03"),
            7: Decimal("0.34"),
            8: Decimal("0.16"),
            9: Decimal("0.03"),
            10: Decimal("0.01"),
            11: Decimal("0.03"),
            12: Decimal("0.03"),
            13: Decimal("0.03"),
            14: Decimal("0.01"),
            15: Decimal("0.01"),
            16: Decimal("0.03"),
            17: Decimal("0.03"),
            18: Decimal("0.03"),
            19: Decimal("0.03"),
            20: Decimal("0.03"),
            21: Decimal("0.01"),
            22: Decimal("0.03"),
        }
        return _mapping[self.value]
    
    @property
    def application_subtrahend(self) -> bool:
        """Indica si el concepto de pago aplica o no el sustraendo en bolívares."""
        _mapping: dict[int, bool] = {
            1: True,
            2: True,
            3: True,
            4: True,
            5: True,
            6: True,
            7: False,
            8: False,
            9: True,
            10: True,
            11: True,
            12: True,
            13: False,
            14: False,
            15: True,
            16: True,
            17: True,
            18: True,
            19: True,
            20: True,
            21: False,
            22: True,
        }
        return _mapping[self.value]
    
    @property
    def fixed_factor(self) -> Decimal:
        """Retorna las unidades tributarias mínimas requeridas por ley para aplicar retención."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("83.3334"),
            2: Decimal("83.3334"),
            3: Decimal("83.3334"),
            4: Decimal("83.3334"),
            5: Decimal("83.3334"),
            6: Decimal("83.3334"),
            7: Decimal("0.00"),
            8: Decimal("0.00"),
            9: Decimal("83.3334"),
            10: Decimal("83.3334"),
            11: Decimal("83.3334"),
            12: Decimal("83.3334"),
            13: Decimal("0.00"),
            14: Decimal("0.00"),
            15: Decimal("83.3334"),
            16: Decimal("83.3334"),
            17: Decimal("83.3334"),
            18: Decimal("83.3334"),
            19: Decimal("83.3334"),
            20: Decimal("83.3334"),
            21: Decimal("0.00"),
            22: Decimal("83.3334"),
        }
        return _mapping[self.value]