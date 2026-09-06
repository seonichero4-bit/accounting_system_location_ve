Plan de Pruebas para: Especificación de Vistas, Especificación del Formulario (SalesRecordForm), definidos en el fichero "Especificacion_tecnica_modelo_SalesRecord.md" 
Tipo de Prueba: Test de Integracion

### Happy Paths (Flujos Felices)

[ID_HP_001] - Inyección de contexto de inquilino y procesamiento en vista de creación Descripción: Validar que la vista de creación extraiga las instancias de perfil y período fiscal desde la petición del usuario, las desempaquete adecuadamente y las inyecte al formulario, configurándolas como campos ocultos/deshabilitados y guardando la transacción asociada al inquilino activo. Entrada / Estímulo: Petición POST a la vista de creación con un objeto diferido (`SimpleLazyObject`) en el perfil fiscal del usuario y datos válidos de formulario. Resultado Esperado: La vista procesa el perfil fiscal con la utilidad de desempaquetado (`unwrap_lazy_object`), el formulario asigna los campos bloqueados a la instancia sin permitir manipulación del usuario y el registro se guarda correctamente.

[ID_HP_002] - Filtrado de QuerySet por inquilino en campos de Clave Foránea del formulario Descripción: Verificar que al inicializar el formulario dentro de la vista, las opciones seleccionables de facturas afectadas y clientes queden acotadas únicamente a los registros del inquilino autenticado. Entrada / Estímulo: Petición GET/POST a la vista que renderiza el formulario inyectando el perfil fiscal del inquilino. Resultado Esperado: Los campos de relación (`affected_invoice` y `client`) en el formulario filtran sus conjuntos de datos (`queryset`), mostrando únicamente entidades pertenecientes a dicho perfil fiscal.

[ID_HP_003] - Flujo completo de edición de registro en estado Preliminar mediante Vista de Actualización Descripción: Comprobar el ciclo de vida de la vista de edición al consultar un registro existente en estado preliminar, acotado por la consulta del inquilino actual, vinculando la instancia al formulario y guardando los cambios. Entrada / Estímulo: Petición GET y posterior POST a la vista de actualización enviando modificaciones válidas sobre un registro en estado "PRELIMINARY" asignado al inquilino. Resultado Esperado: La vista restringe la consulta al inquilino mediante el mixin de alcance (`RequestScopedQuerySetMixin`), vincula los datos existentes al formulario y persiste exitosamente las modificaciones.

### Edge Cases (Casos Borde y Manejo de Errores)


[ID_EC_001] - Intento de selección de cliente o factura afectada perteneciente a otro inquilino

- **Descripción**: Evaluar la resistencia de la capa del formulario ante intentos de vinculación con datos que no corresponden al inquilino activo.
    
- **Entrada / Estímulo**: Petición POST enviando en el cuerpo del formulario los identificadores de un `client` o de una `affected_invoice` válidos en el sistema pero pertenecientes a un perfil fiscal distinto.
    
- **Resultado Esperado**: El formulario invalida la entrada debido a que los identificadores enviados no forman parte del conjunto de datos filtrado (`queryset`) para el inquilino en la inicialización.
    

[ID_EC_002] - Aislamiento de consulta por inquilino en Vista de Actualización

- **Descripción**: Validar que un usuario no pueda consultar ni modificar un registro perteneciente a otro inquilino mediante el identificador en la ruta de la vista.
    
- **Entrada / Estímulo**: Petición HTTP a la vista de edición especificando la clave primaria de un registro existente cuyo perfil fiscal pertenece a un inquilino diferente.
    
- **Resultado Esperado**: El mixin de consulta acotada por petición (`RequestScopedQuerySetMixin`) restringe el acceso retornando una respuesta de recurso no encontrado (404 / queryset vacío).
    

[ID_EC_003] - Alteración del payload POST en campos de inquilino deshabilitados

- **Descripción**: Probar la resistencia del formulario contra la manipulación de valores en campos deshabilitados u ocultos enviados desde el cliente.
    
- **Entrada / Estímulo**: Enviar una petición POST incluyendo en el cuerpo valores alterados o maliciosos para los campos `fiscal_profile` y `fiscal_period`.
    
- **Resultado Esperado**: El formulario ignora los valores alterados procedentes de la petición HTTP por estar configurados como deshabilitados/bloqueados, manteniendo intactas las instancias seguras inyectadas directamente por el servidor.

[ID_EC_004] - Captura de excepción de inmutabilidad en guardado y mapeo a errores globales 
- Descripción: Validar el manejo en la vista cuando la persistencia del modelo rechaza la modificación por estatus inmutable (`PROCESSED` o `ANNULLED_PROCESSED`). 
	
- Entrada / Estímulo: Petición POST a la vista de actualización intentando modificar un registro cuyo estatus en la base de datos se encuentra cerrado. 
	
- Resultado Esperado: El método de guardado del modelo eleva la excepción de validación, la vista la captura y ejecuta la adición del error global (asociado a `non_field_errors`) con el mensaje: "No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'.".