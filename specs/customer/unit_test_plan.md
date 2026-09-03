Plan de Pruebas para: 2. Validations & Constraints (Modelo Customer)
Tipo de Prueba: Test Unitario

### Happy Paths (Flujos Felices)

- **[ID_HP_001] - Validación exitosa de formato RIF**
    
    - **Descripción:** Validar que el componente acepta un número de identificación fiscal que cumple con la estructura regular definida.
        
    - **Entrada / Estímulo:** Un valor de RIF con un prefijo válido (V, E, J, G, P, o C) seguido exactamente por una cadena de entre 8 y 9 dígitos (ej. "J12345678").
        
    - **Resultado Esperado:** La validación de campo es exitosa y el dato es aceptado sin arrojar excepciones.
        
- **[ID_HP_002] - Validación exitosa de formato de número telefónico**
    
    - **Descripción:** Validar que el componente acepta un número telefónico con la longitud correcta y un código de área estructurado.
        
    - **Entrada / Estímulo:** Un número de teléfono que contiene entre 10 y 11 dígitos numéricos con un código de área funcional.
        
    - **Resultado Esperado:** La validación de campo es exitosa y el teléfono se asimila correctamente.
        
- **[ID_HP_003] - Consistencia entre prefijo RIF y Tipo de Contribuyente**
    
    - **Descripción:** Validar la lógica de negocio cruzada ejecutada al procesar el modelo de forma íntegra.
        
    - **Entrada / Estímulo:** Un RIF estructuralmente válido cuyo prefijo es legal y lógicamente coherente con el tipo de contribuyente asignado (ej. Tipo `ORDINARY` o `SPECIAL` asociado a un prefijo coherente).
        
    - **Resultado Esperado:** El método de limpieza global del modelo finaliza exitosamente sin disparar errores de inconsistencia.
        
- **[ID_HP_004] - Persistencia exitosa de campos obligatorios**
    
    - **Descripción:** Validar que las restricciones de la base de datos permiten la creación del registro cuando los datos mínimos requeridos poseen valores de texto válidos.
        
    - **Entrada / Estímulo:** Instanciación del modelo con valores alfanuméricos válidos y no vacíos para `rif`, `name` y `fiscal_address`, `phone_number`, `taxpayer_type`.
        
    - **Resultado Esperado:** El registro se guarda exitosamente en la base de datos sin disparar las restricciones de chequeo de contenido.
        

### Edge Cases (Casos Borde y Manejo de Errores)

- **[ID_EC_001] - RIF con prefijo no soportado**
    
    - **Descripción:** Forzar el validador de expresión regular del RIF ingresando un carácter de prefijo no contemplado en la regla de negocio.
        
    - **Entrada / Estímulo:** RIF comenzando con una letra diferente a las permitidas, seguido de una longitud numérica válida (ej. "Z12345678").
        
    - **Resultado Esperado:** El validador de nivel de campo rechaza la entrada y emite una excepción de validación.
        
- **[ID_EC_002] - RIF con longitud numérica fuera del límite inferior**
    
    - **Descripción:** Forzar el límite inferior de la expresión regular numérica del RIF.
        
    - **Entrada / Estímulo:** RIF con un prefijo válido pero con 7 dígitos numéricos o menos (ej. "J1234567").
        
    - **Resultado Esperado:** El validador de nivel de campo rechaza la entrada por no cumplir el mínimo de 8 dígitos esperados.
        
- **[ID_EC_003] - RIF con longitud numérica fuera del límite superior**
    
    - **Descripción:** Forzar el límite superior de la expresión regular numérica del RIF.
        
    - **Entrada / Estímulo:** RIF con un prefijo válido pero con 10 dígitos numéricos o más (ej. "V1234567890").
        
    - **Resultado Esperado:** El validador de nivel de campo rechaza la entrada por exceder el máximo de 9 dígitos esperados.
        
- **[ID_EC_004] - Teléfono con longitud inferior al mínimo permitido**
    
    - **Descripción:** Forzar el validador de expresión regular del teléfono con un valor numérico corto.
        
    - **Entrada / Estímulo:** Cadena numérica de 9 dígitos.
        
    - **Resultado Esperado:** El validador de nivel de campo rechaza la entrada por no cumplir el requisito mínimo de 10 dígitos.
        
- **[ID_EC_005] - Teléfono con longitud superior al máximo permitido**
    
    - **Descripción:** Forzar el validador de expresión regular del teléfono con un valor numérico extendido.
        
    - **Entrada / Estímulo:** Cadena numérica de 12 dígitos.
        
    - **Resultado Esperado:** El validador de nivel de campo rechaza la entrada por superar el requisito máximo de 11 dígitos.
        
- **[ID_EC_006] - Inconsistencia fiscal cruzada (RIF vs Tipo de Contribuyente)**
    
    - **Descripción:** Disparar la regla de negocio principal de limpieza y validación cruzada simulando un escenario fiscalmente incoherente.
        
    - **Entrada / Estímulo:** Un `rif` válido acompañado de un `taxpayer_type` que no guarda correspondencia legal con dicho prefijo.
        
    - **Resultado Esperado:** El método de validación central es interrumpido y dispara explícitamente una excepción estructurada en formato de diccionario: `{"rif": "Inconsistencia tributaria: El prefijo del RIF no corresponde con el Tipo de Contribuyente seleccionado."}`.
        
- **[ID_EC_007] - Violación de unicidad de RIF (Duplicidad)**
    
    - **Descripción:** Evaluar el comportamiento de las restricciones relacionales frente a colisiones de datos.
        
    - **Entrada / Estímulo:** Intento de persistir un cliente enviando un número de `rif` que ya pertenece a un registro activo en el sistema.
        
    - **Resultado Esperado:** La restricción de unicidad de la base de datos bloquea la operación y retorna la excepción y/o mensaje esperado: "Ya existe un registro activo con este número de RIF en la base de datos.".
        
- **[ID_EC_008] - Campo obligatorio RIF vacío o en blanco**
    
    - **Descripción:** Evaluar las restricciones de base de datos diseñadas para evitar inserciones de campos primarios nulos o compuestos solo de espacios.
        
    - **Entrada / Estímulo:** Asignación de un string vacío (`""`) o un string con múltiples espacios (`" "`) al atributo `rif`.
        
    - **Resultado Esperado:** La restricción de verificación (Check Constraint) rechaza la operación en la capa de persistencia con el mensaje: "Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios.".
        
- **[ID_EC_009] - Campo obligatorio Razón Social (Name) vacío o en blanco**
    
    - **Descripción:** Forzar la restricción de contenido del nombre del cliente en el modelo.
        
    - **Entrada / Estímulo:** Asignación de un string vacío (`""`) o espacios en blanco al atributo `name`.
        
    - **Resultado Esperado:** Bloqueo de la persistencia por Check Constraint, arrojando el mensaje: "Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios.".
        
- **[ID_EC_010] - Campo obligatorio Dirección Fiscal vacía o en blanco**
    
    - **Descripción:** Forzar la restricción de contenido de la dirección en el modelo.
        
    - **Entrada / Estímulo:** Asignación de un string vacío (`""`) o un espacio en blanco al atributo `fiscal_address`.
        
    - **Resultado Esperado:** Bloqueo de la persistencia mediante Check Constraint, emitiendo el error de campo obligatorio: "Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios.".
        
- **[ID_EC_011] - Valores `null` o indefinidos directos en campos restringidos**
    
    - **Descripción:** Evaluar el comportamiento del componente al recibir directamente un tipo de dato nulo (ej. `None` o `null`) saltándose una potencial inicialización predeterminada.
        
    - **Entrada / Estímulo:** Inyección directa de un valor nulo absoluto en campos que poseen validadores o restricciones (ej. en `rif`, `name`, `fiscal_address`).
        
    - **Resultado Esperado:** Una interrupción temprana por error de tipado o el rechazo inmediato por parte de la base de datos al violar explícitamente las reglas de no-nulo o las Check Constraints estipuladas.

