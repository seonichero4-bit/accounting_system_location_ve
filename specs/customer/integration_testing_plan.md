Plan de Pruebas para: Views (CustomerCreateView & CustomerUpdateView) y Form (CustomerForm) del modelo Customer 
Tipo de Prueba: Test de Integracion

### Happy Paths (Flujos Felices) 

[ID_HP_001] - Creación exitosa de cliente con datos obligatorios válidos y perfil fiscal desenvuelto 
Descripción: Validar la integración completa entre el procesamiento de la vista de creación, la inicialización del formulario con la inyección del perfil fiscal desenvuelto y la persistencia en base de datos al enviar únicamente los campos obligatorios válidos. 
Entrada / Estímulo: Petición de creación mediante método de envío de datos (POST) con el contexto de usuario autenticado asociado a un perfil fiscal activo. Datos: RIF con formato válido ("J-123456789"), Razón Social ("Distribuidora Central C.A."), Dirección Fiscal ("Calle 10, Edificio A"), Teléfono ("02125551234") y Tipo de Contribuyente ("ORDINARY"). 
Resultado Esperado: La vista extrae y desempaqueta el objeto de perfil fiscal perezoso del contexto de la petición, inyectándolo en el formulario. El formulario valida la información sin errores, asigna el perfil fiscal al modelo y persiste el registro en la base de datos. La vista procesa la finalización exitosa y redirecciona a la vista destino correspondiente.
    

[ID_HP_002] - Creación exitosa asociando cuentas contables personalizadas pertenecientes al mismo inquilino 
Descripción: Verificar la correcta filtración y asignación de cuentas contables opcionales (`custom_accounts_receivable` y `custom_income_account`) asociadas a un "ChartOfAccount" del perfil fiscal del inquilino (tenant) activo. 
Entrada / Estímulo: Petición de creación POST incluyendo todos los campos obligatorios válidos más la selección de identificadores de cuenta contable de cobro e ingreso pertenecientes explícitamente al libro contable del perfil fiscal en sesión. 
Resultado Esperado: El formulario valida que las cuentas contables existen dentro del subconjunto de datos (queryset) permitido para ese libro contable. La transacción en base de datos registra exitosamente el cliente con las relaciones de clave foránea contables correctamente vinculadas.

[ID_HP_003] - Actualización exitosa de campos permitidos en un cliente existente del mismo inquilino 
Descripción: Validar la integración de la vista de edición con el formulario para modificar atributos de un cliente preexistente sin alterar la vinculación de su perfil fiscal ni romper las reglas de aislamiento por inquilino. 
Entrada / Estímulo: Petición de edición POST sobre el identificador de un cliente perteneciente al inquilino actual, modificando la dirección fiscal y el teléfono por nuevos valores válidos ("Av. Bolívar, Local 5" y "02125559876"). 
Resultado Esperado: El formulario se inicializa utilizando el perfil fiscal asignado a la instancia existente. Las validaciones resultan exitosas, los campos del cliente son actualizados en la base de datos y no se genera duplicación de registros ni pérdida de relaciones existentes.

### Edge Cases (Casos Borde y Manejo de Errores) 

[ID_EC_001] - Intento de selección de cuentas contables pertenecientes a otro inquilino (Fuga de datos) 
Descripción: Forzar la inyección de identificadores de cuentas contables que existen en la base de datos pero pertenecen al libro contable de un inquilino diferente al del usuario activo. 
Entrada / Estímulo: Petición POST de creación o edición incluyendo identificadores de `custom_accounts_receivable` o `custom_income_account` asociadas a un `ChartOfAccountModel` ajeno. 
Resultado Esperado: El formulario intercepta la selección durante la validación de sus campos relacionales debido al filtrado aplicado en la inicialización según el perfil fiscal. La petición es rechazada con un error de validación de campo ("Seleccione una opción válida"), impidiendo cualquier persistencia o vinculación cruzada en la base de datos.

[ID_EC_002] - Intento de actualización de un cliente perteneciente a otro inquilino Descripción: Evaluar el aislamiento multi-inquilino en la vista de edición al intentar acceder o manipular un registro de cliente creado bajo otro perfil fiscal. 
Entrada / Estímulo: Petición GET o POST hacia el endpoint de la vista de actualización proporcionando la clave primaria de un cliente que pertenece a un inquilino diferente al del usuario que realiza la solicitud. 
Resultado Esperado: La capa de filtrado por inquilino de la vista (`RequestScopedQuerySetMixin`) restringe la consulta al ámbito del usuario actual. Al no encontrar el registro dentro del conjunto de datos permitido, la vista interrumpe el procesamiento lanzando una respuesta de recurso no encontrado (Error 404), garantizando que no existan lecturas ni escrituras no autorizadas.

[ID_EC_003] - Manipulación maliciosa de parámetros ocultos para alterar el perfil fiscal (Tampering) 
Descripción: Verificar la invulnerabilidad del sistema cuando un usuario altera los datos enviados en la petición POST intentando sobreescribir el campo de perfil fiscal. 
Entrada / Estímulo: Petición POST modificada manualmente que incluye dentro del cuerpo de datos un parámetro explicitado para el perfil fiscal (`fiscal_profile`) apuntando a un identificador distinto al asignado en el servidor. 
Resultado Esperado: Dado que el formulario excluye de la entrada directa de datos el campo de perfil fiscal e inyecta la instancia de forma explícita desde la lógica del backend (`get_form_kwargs` o `self.instance`), el parámetro malicioso es ignorado por completo. La entidad se guarda vinculada de manera inalterable al perfil fiscal verificado por la sesión.