"""Módulo de opciones para retenciones de ISLR a Personas Jurídicas Domiciliadas."""

from decimal import Decimal
from django.db import models


class IslrPjdChoices(models.IntegerChoices):
    """
    Conceptos de retención de ISLR para Personas Jurídicas Domiciliadas (PJD).

    Mapea la estructura legal de los conceptos de pago con sus respectivos
    atributos como códigos SENIAT, bases imponibles y tarifas porcentuales,
    exponiendo valores decimales listos para operaciones matemáticas confiables.
    """

    HONORARIOS_PROFESIONALES = 1, "Honorarios Profesionales"
    COMISIONES_ENAJENACION_INMUEBLES = 2, "Comisiones Enajenación Inmuebles"
    COMISIONES_MERCANTILES_Y_OTRAS = 3, "Comisiones Mercantiles y Otras"
    INTERESES = 4, "Intereses"
    GANANCIAS_JUEGOS_Y_APUESTAS = 5, "Ganancias en Juegos y Apuestas"
    PREMIOS_LOTERIA_Y_HIPODROMOS_ART_62_LISLR = (
        6,
        "Premios Lotería e Hipódromos Art. 62 LISLR",
    )
    PROPIETARIOS_ANIMALES_CARRERAS_PREMIOS = (
        7,
        "Propietarios de Animales de Carreras por Premios Recibidos",
    )
    SERVICIOS = 8, "Servicios"
    ARRENDAMIENTO_BIENES_INMUEBLES = 9, "Arrendamiento Bienes Inmuebles"
    ARRENDAMIENTO_BIENES_MUEBLES = 10, "Arrendamiento Bienes Muebles"
    PAGOS_TARJETAS_CREDITO_O_CONSUMO = (
        11,
        "Pagos de Tarjetas de Crédito o Consumo",
    )
    PAGO_GASOLINA_TARJETA_CREDITO_O_CONSUMO = (
        12,
        "Pago de Gasolina con Tarjeta de Crédito o Consumo",
    )
    FLETES_Y_GASTOS_TRANSPORTE_NACIONAL = (
        13,
        "Fletes y Gastos de Transporte Nacional",
    )
    PAGO_EMP_SEGURO_A_CORREDORES = 14, "Pago de Emp.de Seguro a Corredores"
    PAGO_EMPRESAS_SEGUROS_REPARACION_BIENES = (
        15,
        "Pago de Empresas de Seguros por Reparación de Bienes de sus Asegurados",
    )
    PAGOS_EMPRESAS_SEGURO_CENTROS_SALUD_ATENCION = (
        16,
        (
            "Pagos de Empresas de Seguro a Centros de Salud por Atención de sus"
            " Asegurados"
        ),
    )
    PAGOS_ADQUISICION_FONDOS_COMERCIO = (
        17,
        "Pagos por Adquisición de Fondos de Comercio",
    )
    PUBLICIDAD_Y_PROPAGANDA = 18, "Publicidad y Propaganda"
    PUBLICIDAD_Y_PROPAGANDA_EMISORAS_RADIO = (
        19,
        "Publicidad y Propaganda Emisoras de Radio",
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
            1: "9.1. b",
            2: "9.2.a",
            3: "9.2.b",
            4: "9.3.c",
            5: "9.9",
            6: "9.9",
            7: "9.10",
            8: "9.11",
            9: "9.12",
            10: "9.13",
            11: "9.14",
            12: "9.14",
            13: "9.15",
            14: "9.16",
            15: "9.17",
            16: "9.17",
            17: "9.18",
            18: "9.19",
            19: "9.19",
            20: "9.20",
            21: "9.21",
        }
        return _mapping[self.value]

    @property
    def code(self) -> str:
        """Retorna el código de concepto oficial asignado por el SENIAT."""
        _mapping: dict[int, str] = {
            1: "004",
            2: "016",
            3: "020",
            4: "027",
            5: "043",
            6: "047",
            7: "051",
            8: "055",
            9: "059",
            10: "063",
            11: "067",
            12: "070",
            13: "072",
            14: "074",
            15: "076",
            16: "077",
            17: "081",
            18: "084",
            19: "086",
            20: "N/A",
            21: "N/A",
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
            11: Decimal("1.00"),  # Normalización de '**' para base completa
            12: Decimal("1.00"),  # Normalización de '**' para base completa
            13: Decimal("1.00"),
            14: Decimal("1.00"),
            15: Decimal("1.00"),
            16: Decimal("1.00"),
            17: Decimal("1.00"),
            18: Decimal("1.00"),
            19: Decimal("1.00"),
            20: Decimal("1.00"),
            21: Decimal("1.00"),
        }
        return _mapping[self.value]

    @property
    def percentage(self) -> Decimal:
        """Retorna la tarifa o alícuota de retención del ISLR."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("0.05"),
            2: Decimal("0.05"),
            3: Decimal("0.05"),
            4: Decimal("0.05"),
            5: Decimal("0.34"),
            6: Decimal("0.16"),
            7: Decimal("0.05"),
            8: Decimal("0.02"),
            9: Decimal("0.05"),
            10: Decimal("0.05"),
            11: Decimal("0.05"),
            12: Decimal("0.01"),
            13: Decimal("0.03"),
            14: Decimal("0.05"),
            15: Decimal("0.05"),
            16: Decimal("0.05"),
            17: Decimal("0.05"),
            18: Decimal("0.05"),
            19: Decimal("0.03"),
            20: Decimal("0.01"),
            21: Decimal("0.05"),
        }
        return _mapping[self.value]