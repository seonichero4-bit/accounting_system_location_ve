"""Módulo de opciones para retenciones de ISLR a Personas Jurídicas No Domiciliadas."""

from decimal import Decimal
from django.db import models


class IslrPjndChoices(models.IntegerChoices):
    """
    Conceptos de retención de ISLR para Personas Jurídicas No Domiciliadas (PJND).

    Mapea los conceptos legales con sus respectivos códigos SENIAT y bases imponibles.
    Debido a la naturaleza mixta de las alícuotas (valores fijos y Tarifa N° 2),
    el porcentaje se expone como una cadena de texto (str) según los requerimientos.
    """

    HONORARIOS_PROFESIONALES = 1, "Honorarios Profesionales"
    COMISIONES_ENAJENACION_INMUEBLES = 2, "Comisiones Enajenación Inmuebles"
    COMISIONES_MERCANTILES_Y_OTRAS = 3, "Comisiones Mercantiles y Otras"
    INTERESES_ART_27_NUM_2_LISLR = 4, "Intereses Art. 27 # 2 L.I.S.L.R."
    INTERESES_ART_52_PARAGRAFO_2_LISLR = (
        5,
        "Intereses Art. 52 Parágrafo 2° L.I.S.L.R.",
    )
    INTERESES = 6, "Intereses"
    AGENCIAS_NOTICIAS_INTERNACIONALES_ART_35_LISLR = (
        7,
        "Agencias de Noticias Internacionales Art. 35 LISLR",
    )
    FLETES_Y_GASTOS_TRANSPORTE_INTERNACIONAL = (
        8,
        (
            "Fletes y Gtos de Transp. Internacional (entre Venezuela y el"
            " Exterior o viceversa). Art. 36 LISLR"
        ),
    )
    FLETES_PAIS_EMPRESAS_INTERNACIONALES_ART_36_LISLR = (
        9,
        "Fletes en el País a Emp. Internacional. Art. 36 LISLR",
    )
    EXHIBICION_PELICULAS_ART_27_NUM_15_Y_34_LISLR = (
        10,
        "Exhibición de Películas. Art 27 # 15, y 34 LISLR",
    )
    REGALIAS_ART_27_NUM_16_LISLR = 11, "Regalías Art 27 # 16 LISLR"
    ASISTENCIA_TECNICA_ART_27_NUM_16_LISLR = (
        12,
        "Asistencia Técnica Art 27 # 16 LISLR",
    )
    SERVICIOS_TECNOLOGICOS_ART_27_NUM_16_LISLR = (
        13,
        "Servicios Tecnológicos Art 27 # 16 LISLR",
    )
    PRIMAS_SEGURO_Y_REASEGURO_ART_27_NUM_18_Y_52_LISLR = (
        14,
        (
            "Primas de Seguro y Reaseg. Art. 27 #18 y Parágrafo 3° Art. 52"
            " LISLR"
        ),
    )
    GANANCIAS_JUEGOS_Y_APUESTAS = 15, "Ganancias en Juegos y Apuestas"
    PREMIOS_LOTERIA_Y_HIPODROMOS_ART_62_LISLR = (
        16,
        "Premios Lotería e Hipódromos Art. 62 LISLR",
    )
    PROPIETARIOS_ANIMALES_CARRERAS_PREMIOS = (
        17,
        "Propietarios de Animales de Carreras por Premios Recibidos",
    )
    SERVICIOS = 18, "Servicios"
    ARRENDAMIENTO_BIENES_INMUEBLES = 19, "Arrendamiento Bienes Inmuebles"
    ARRENDAMIENTO_BIENES_MUEBLES = 20, "Arrendamiento Bienes Muebles"
    PAGOS_TARJETAS_CREDITO_O_CONSUMO = (
        21,
        "Pagos de Tarjetas de Crédito o Consumo",
    )
    PAGOS_ADQUISICION_FONDOS_COMERCIO = (
        22,
        "Pagos por Adquisición de Fondos de Comercio",
    )
    PUBLICIDAD_Y_PROPAGANDA = 23, "Publicidad y Propaganda"
    ENRIQUECIMIENTOS_ENAJENACION_ACCIONES_BOLSA = (
        24,
        "Enriquecimientos por Enajenación de Acciones en la Bolsa de Valores",
    )
    PAGOS_ENAJENACION_ACCIONES_FUERA_BOLSA = (
        25,
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
            2: "9.2.a",
            3: "9.2.b",
            4: "9.3. a",
            5: "9.3.b",
            6: "9.3.c",
            7: "9.4",
            8: "9.5",
            9: "9.5",
            10: "9.6",
            11: "9.7",
            12: "9.7",
            13: "9.7",
            14: "9.8",
            15: "9.9",
            16: "9.9",
            17: "9.10",
            18: "9.11",
            19: "9.12",
            20: "9.13",
            21: "9.14",
            22: "9.18",
            23: "9.19",
            24: "9.20",
            25: "9.21",
        }
        return _mapping[self.value]

    @property
    def code(self) -> str:
        """Retorna el código de concepto oficial asignado por el SENIAT."""
        _mapping: dict[int, str] = {
            1: "005",
            2: "017",
            3: "021",
            4: "023",
            5: "024",
            6: "028",
            7: "029",
            8: "031",
            9: "031",
            10: "033",
            11: "035",
            12: "037",
            13: "039",
            14: "040",
            15: "044",
            16: "048",
            17: "052",
            18: "056",
            19: "060",
            20: "064",
            21: "068",
            22: "082",
            23: "085",
            24: "N/A",
            25: "N/A",
        }
        return _mapping[self.value]

    @property
    def base_imponible(self) -> Decimal:
        """Retorna el porcentaje de base imponible aplicable."""
        _mapping: dict[int, Decimal] = {
            1: Decimal("0.90"),
            2: Decimal("1.00"),
            3: Decimal("1.00"),
            4: Decimal("0.95"),
            5: Decimal("1.00"),
            6: Decimal("0.95"),
            7: Decimal("0.15"),
            8: Decimal("0.05"),
            9: Decimal("0.10"),
            10: Decimal("0.25"),
            11: Decimal("0.90"),
            12: Decimal("0.30"),
            13: Decimal("0.50"),
            14: Decimal("0.30"),  # 30% Ing. Neto normalizado a Decimal
            15: Decimal("1.00"),
            16: Decimal("1.00"),
            17: Decimal("1.00"),
            18: Decimal("1.00"),
            19: Decimal("1.00"),
            20: Decimal("1.00"),
            21: Decimal("1.00"),  # Interpretación segura de '**' para base entera
            22: Decimal("1.00"),
            23: Decimal("1.00"),
            24: Decimal("1.00"),
            25: Decimal("1.00"),
        }
        return _mapping[self.value]

    @property
    def percentage(self) -> str:
        """Retorna la tarifa o alícuota de retención expuesta como str."""
        _mapping: dict[int, str] = {
            1: "TARIFA N° 2",
            2: "0.05",
            3: "0.05",
            4: "TARIFA N° 2",
            5: "0.0495",
            6: "TARIFA N° 2",
            7: "TARIFA N° 2",
            8: "TARIFA N° 2",
            9: "TARIFA N° 2",
            10: "TARIFA N° 2",
            11: "TARIFA N° 2",
            12: "TARIFA N° 2",
            13: "TARIFA N° 2",
            14: "0.10",
            15: "0.34",
            16: "0.16",
            17: "0.05",
            18: "TARIFA N° 2",
            19: "TARIFA N° 2",
            20: "0.05",
            21: "0.05",
            22: "0.05",
            23: "0.05",
            24: "0.01",
            25: "0.05",
        }
        return _mapping[self.value]