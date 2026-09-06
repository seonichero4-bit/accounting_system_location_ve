
**Tipo de Prueba:** Test Unitario.

**Objeto de Prueba:** Restricciones del Modelo (`Meta`), Lógica de Negocio (`clean()`) y Persistencia/Normalización (`save()`)

### 1. Happy Paths (Flujos Felices)

#### [ID_HP_001] - Registro exitoso de venta interna estándar (Grupo A)

- **Descripción:** Validación del guardado de un registro de venta interna con alícuota general (16%), verificando la documentación fiscal interna (Grupo A) y el cumplimiento de la ecuación contable.
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, `document_number="0001"`, `control_number="00-000001"`, `sale_type="INTERNAL"`, `document_date=fecha actual`, `general_tax_base_16=100.00`, `general_tax_debit_16=16.00`, `total_sales_inc_vat=116.00`, ventas exentas/exoneradas/no sujetas y FOB en `0.00`. 
    
- **Resultado Esperado:** El objeto pasa la validación sin errores de negocio y se persiste correctamente en el sistema.
    

#### [ID_HP_002] - Registro exitoso de operación de exportación (Grupo A)

- **Descripción:** Confirmación de registro para venta de exportación respetando que el valor FOB alimente el total y que los montos internos permanezcan en cero.
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, `document_number="0002"`, `control_number="00-000002"`, `sale_type="EXPORT"`, `fob_export_value=500.00`, `total_sales_inc_vat=500.00`, todas las ventas internas y bases imponibles en `0.00`.
    
- **Resultado Esperado:** El registro valida exitosamente y se almacena con la coherencia exigida para ventas de exportación.
    

#### [ID_HP_003] - Registro exitoso de nota de crédito vinculada (Grupo A)

- **Descripción:** Creación de una nota de crédito asociando obligatoriamente una factura previa válida.
    
- **Entrada / Estímulo:** `document_type="CREDIT_NOTE"`, `document_number="0003"`, `control_number="00-000003"`, `affected_invoice=instancia previa válida`, `transaction_type="04_ADJUSTMENT"`, montos ajustados según ecuación contable.
    
- **Resultado Esperado:** Validación exitosa confirmando que el vínculo a la factura afectada satisface la regla de negocio del Grupo A.
    

#### [ID_HP_004] - Registro exitoso de transacción anulada

- **Descripción:** Creación de un registro cuyo tipo de transacción indica anulación, cumpliendo cliente "ANULADO" y montos financieros en cero.
    
- **Entrada / Estímulo:** `transaction_type="03_ANNULMENT"`, `client="ANULADO"`, `total_sales_inc_vat=0.00`, todas las bases imponibles, exenciones y débitos fiscales en `0.00`.
    
- **Resultado Esperado:** El registro satisface las restricciones `CheckConstraint` y la lógica de negocio, siendo persistido automáticamente con `record_status='ANNULLED'`.
    

#### [ID_HP_005] - Modificación permitida de registro en estado PRELIMINARY

- **Descripción:** Actualización de datos sobre un registro existente cuyo estado actual permite mutaciones.
    
- **Entrada / Estímulo:** Modificación sobre un registro preexistente con `record_status="PRELIMINARY"`, alterando la fecha del documento a una fecha válida.
    
- **Resultado Esperado:** El método `save()` permite la persistencia y actualiza el objeto sin lanzar excepciones.
    

#### [ID_HP_006] - Registro exitoso emitido mediante Impresora Fiscal (Grupo B)

- **Descripción:** Validación de registro por máquina fiscal asegurando que la secuencia sea válida y los campos del Grupo A estén ausentes.
    
- **Entrada / Estímulo:** `invoice_number="000100"`, `last_receipt_number="000105"`, `fiscal_printer_number="Z1F1234567"`, `z_report_number="0100"`. 
    
- **Resultado Esperado:** La operación es aceptada por la regla del Grupo B y pasa las restricciones de la base de datos.
    

#### [ID_HP_007] - Cálculo exacto del impuesto IGTF con margen de tolerancia

- **Descripción:** Verificación de la alícuota del 3% sobre la base imponible del IGTF respetando la tolerancia de redondeo de 0.01.
    
- **Entrada / Estímulo:** `igtf_tax_base=10.33`, `igtf_tax_amount=0.31` (10.33 * 0.03 = 0.3099, redondeado a 0.31).
    
- **Resultado Esperado:** Se aprueba la validación al estar dentro del margen de error de ±0.01.
    

#### [ID_HP_008] - Sanitización automática de número de control y factura

- **Descripción:** Aplicación de limpieza y padding sobre los campos identificadores antes de la validación.
    
- **Entrada / Estímulo:** `control_number=" 00-12345 "`, `invoice_number=" 456 "`.
    
- **Resultado Esperado:** Los espacios son eliminados/rellenados en la fase de sanitización quedando formateados correctamente.
    

#### [ID_HP_009] - Normalización implícita en save() para Documentación Fiscal Interna (Grupo A) _(Nuevo)_

- **Descripción:** Verificación de que al guardar un registro del Grupo A, se fuerce la asignación de `None` a los campos de impresora fiscal y a `affected_invoice` (si es `INVOICE`).
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, `document_number="0005"`, `control_number="00-000005"`. Invocar `save()`.
    
- **Resultado Esperado:** El método `save()` asigna automáticamente `None` a `invoice_number`, `last_receipt_number`, `fiscal_printer_number`, `z_report_number` y `affected_invoice` previo a la persistencia.
    

#### [ID_HP_010] - Normalización implícita en save() para Impresora Fiscal (Grupo B) _(Nuevo)_

- **Descripción:** Verificación de que al guardar un registro del Grupo B, se fuerce la asignación de `None` a los campos de documentación interna.
    
- **Entrada / Estímulo:** Instancia válida del Grupo B (`invoice_number`, `fiscal_printer_number`, `z_report_number` presentes). Invocar `save()`.
    
- **Resultado Esperado:** El método `save()` asigna automáticamente `None` a `document_type`, `document_number`, `control_number` y `affected_invoice`.
    

### 2. Edge Cases (Casos Borde y Manejo de Errores)

#### [ID_EC_001] - Violación de unicidad de documento emitido (UniqueConstraint)

- **Descripción:** Intento de insertar un documento duplicado para la misma secuencia, perfil fiscal y tipo.
    
- **Entrada / Estímulo:** Inserción de un registro con idéntica combinación de `(fiscal_profile, control_number, document_type)` a uno existente.
    
- **Resultado Esperado:** Falla por restricción de integridad emitiendo el mensaje: _"Ya existe un documento registrado con este N° de Control y Tipo de Documento para el perfil fiscal actual."_
    

#### [ID_EC_002] - Violación de unicidad de Reporte Z (UniqueConstraint) 

- **Descripción:** Intento de registrar dos veces la misma operación de Reporte Z comprobando la tupla completa de 5 campos.
    
- **Entrada / Estímulo:** Registro con combinación idéntica de `(fiscal_profile, fiscal_printer_number, z_report_number, invoice_number, last_receipt_number)` a uno previo.
    
- **Resultado Esperado:** Rechazo por `IntegrityError` o `ValidationError` con el mensaje: _"Este N° de Reporte Z ya fue registrado previamente para la máquina fiscal especificada."_
    

#### [ID_EC_003] - Montos financieros negativos (CheckConstraint / MinValueValidator)

- **Descripción:** Intento de ingresar valores negativos en totales o bases imponibles.
    
- **Entrada / Estímulo:** `total_sales_inc_vat=-50.00` o `general_tax_base_16=-10.00`.
    
- **Resultado Esperado:** Rechazo por `MinValueValidator(0.00)` o `CheckConstraint` con el mensaje: _"Todos los montos (ventas, bases imponibles y exenciones) deben ser mayores o iguales a 0.00."_
    

#### [ID_EC_004] - Secuencia de comprobantes inválida (CheckConstraint)

- **Descripción:** Número de último comprobante del día menor al primer comprobante.
    
- **Entrada / Estímulo:** `invoice_number="000200"`, `last_receipt_number="000199"`.
    
- **Resultado Esperado:** Rechazo por la restricción `valid_receipt_sequence` emitiendo el mensaje: _"El número del último comprobante no puede ser menor al número de factura o primer comprobante."_
    

#### [ID_EC_005] - Suma de montos mayor a cero en transacción de anulación (CheckConstraint / Clean)

- **Descripción:** Registro con tipo de transacción "03" (Anulación) conteniendo importes financieros mayores a 0.00.
    
- **Entrada / Estímulo:** `transaction_type="03_ANNULMENT"`, `total_sales_inc_vat=100.00`.
    
- **Resultado Esperado:** Rechazo por `zero_amount_on_annulment` con el mensaje: _"Las transacciones registradas como anulación requieren que la suma global de sus montos sea 0.00."_ En `clean()`, mensaje asignado a `transaction_type`: _"Para las transacciones de anulación, el monto total de ventas debe ser obligatoriamente 0.00."_
    
#### [ID_EC_006] - Inconsistencia en Ecuación Contable del Total

- **Descripción:** Discrepancia entre `total_sales_inc_vat` y la suma de desgloses.
    
- **Entrada / Estímulo:** `exempt_internal_sales=50.00`, `general_tax_base_16=100.00`, `general_tax_debit_16=16.00` (Suma real = 166.00), pero `total_sales_inc_vat=170.00`.
    
- **Resultado Esperado:** `clean()` lanza `ValidationError` en `total_sales_inc_vat`: _"El total de ventas incluido IVA no coincide con la suma de las ventas exentas, exoneradas, no sujetas, valor FOB y bases imponibles con sus débitos fiscales."_
    

#### [ID_EC_007] - Desviación en la precisión del Débito Fiscal fuera de tolerancia

- **Descripción:** Cálculo de débito fiscal con diferencia superior a 0.01 respecto a la alícuota legal (16%).
    
- **Entrada / Estímulo:** `general_tax_base_16=100.00`, `general_tax_debit_16=16.05`.
    
- **Resultado Esperado:** `ValidationError` asignada a `general_tax_debit_16`: _"El débito fiscal (16%) no coincide con el 16% de la base imponible general indicada."_
    

#### [ID_EC_008] - Débito fiscal presente con base imponible en cero

- **Descripción:** Presencia de valor de débito fiscal cuando la base imponible es 0.00 o nula.
    
- **Entrada / Estímulo:** `reduced_tax_base_8=0.00`, `reduced_tax_debit_8=0.64`.
    
- **Resultado Esperado:** `ValidationError` asignada al campo del débito correspondiente: _"El débito fiscal debe ser exactamente 0.00 cuando la base imponible asociada sea igual a 0.00 o nula."_
    

#### [ID_EC_009] - Omisión de documento afectado en Nota de Crédito/Débito (Grupo A)

- **Descripción:** Creación de Nota de Crédito o Débito sin asignar la referencia a la factura de origen.
    
- **Entrada / Estímulo:** `document_type="CREDIT_NOTE"`, `affected_invoice=None`.
    
- **Resultado Esperado:** `ValidationError` asignada a `affected_invoice`: _"Las Notas de Crédito y Débito requieren especificar el N° de factura afectada, N° de control afectado y su fecha original."_
    

#### [ID_EC_010] - Asignación indebida de documento afectado a Factura regular (Grupo A) 

- **Descripción:** Inclusión de una referencia afectada en una factura regular (`INVOICE`).
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, `affected_invoice=instancia de SalesRecord`.
    
- **Resultado Esperado:** `ValidationError` asignada a `affected_invoice` con el mensaje: _"Las facturas de tipo 'INVOICE' no deben incluir referencia a una factura afectada."_
    

#### [ID_EC_011] - Presencia de campos de impresora fiscal en Documentación Fiscal Interna (Grupo A) _(Nuevo)_

- **Descripción:** Intento de registrar documentación interna especificando simultáneamente algún campo de máquina fiscal.
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, `document_number="0001"`, `control_number="00-000001"`, e `invoice_number="000100"` (o cualquier otro campo de impresora fiscal).
    
- **Resultado Esperado:** `ValidationError` asignada a `invoice_number`, `last_receipt_number`, `fiscal_printer_number` y `z_report_number`: _"Los campos de impresora fiscal (N° de factura/comprobante, N° de último comprobante, N° de máquina fiscal y N° de reporte Z) deben estar vacíos al registrar documentación fiscal interna."_
    

#### [ID_EC_012] - Omisión de campos obligatorios en Documentación Fiscal Interna (Grupo A) _(Nuevo)_

- **Descripción:** Registro del Grupo A omitiendo `document_number` o `control_number`.
    
- **Entrada / Estímulo:** `document_type="INVOICE"`, pero `document_number=""` o `control_number=None`.
    
- **Resultado Esperado:** `ValidationError` asignada al campo faltante emitiendo: _"El número de documento es requerido y debe ser un valor válido."_ o _"El número de control es requerido y debe ser un valor válido."_
    

#### [ID_EC_013] - Presencia de campos de documentación interna en Registro de Impresora Fiscal (Grupo B) _(Nuevo)_

- **Descripción:** Intento de registrar datos por impresora fiscal incluyendo algún campo propio de documentación interna.
    
- **Entrada / Estímulo:** `invoice_number="000100"`, `fiscal_printer_number="Z1F1234567"`, `z_report_number="0100"`, pero asignando `document_type="INVOICE"` o `control_number="00-000001"`.
    
- **Resultado Esperado:** `ValidationError` asignada a `document_type`, `document_number`, `control_number` y `affected_invoice`: _"Los campos de documentación interna (tipo de documento, N° de documento, N° de control y factura afectada) deben estar vacíos cuando se registra una operación de impresora fiscal."_
    

#### [ID_EC_014] - Incompleitud de campos requeridos por dependencia conjunta en Impresora Fiscal (Grupo B) 

- **Descripción:** Omisión de alguno de los tres campos obligatorios del trinomio de máquina fiscal (`invoice_number`, `fiscal_printer_number`, `z_report_number`).
    
- **Entrada / Estímulo:** Asignar `invoice_number="000100"` y `fiscal_printer_number="Z1F1234567"`, pero dejando `z_report_number=None`.
    
- **Resultado Esperado:** `ValidationError` asignada a `invoice_number`, `fiscal_printer_number` y `z_report_number`: _"El registro de impresora fiscal requiere que el N° de factura/comprobante, el N° de máquina fiscal y el N° de reporte Z estén presentes simultáneamente."_
    

#### [ID_EC_015] - Cliente no válido en estado Anulado

- **Descripción:** Transacción o estatus marcado como anulado sin haber registrado la razón social "ANULADO".
    
- **Entrada / Estímulo:** `transaction_type="03_ANNULMENT"`, pero `client="Cliente Regular"`.
    
- **Resultado Esperado:** `ValidationError` asignada a `transaction_type`: _"Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."_
    

#### [ID_EC_016] - Desviación del cálculo del monto IGTF fuera del margen de 0.01

- **Descripción:** Incoherencia matemática entre `igtf_tax_base` e `igtf_tax_amount`.
    
- **Entrada / Estímulo:** `igtf_tax_base=100.00`, `igtf_tax_amount=4.00`.
    
- **Resultado Esperado:** `ValidationError` asignada a `igtf_tax_amount`: _"El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."_
    

#### [ID_EC_017] - Infracción por fecha futura en el documento

- **Descripción:** Intento de registrar un documento con fecha posterior al día actual del sistema.
    
- **Entrada / Estímulo:** `document_date=fecha de mañana`.
    
- **Resultado Esperado:** `ValidationError` asignada a `document_date`: _"La fecha del documento no puede ser posterior a la fecha actual del sistema."_
    

#### [ID_EC_018] - Incoherencia en tipo de venta EXPORT con presencia de ventas internas

- **Descripción:** Operación catalogada como `EXPORT` pero con montos registrados en ventas internas.
    
- **Entrada / Estímulo:** `sale_type="EXPORT"`, `fob_export_value=100.00`, `exempt_internal_sales=10.00`.
    
- **Resultado Esperado:** `ValidationError` asignada a `sale_type / fob_export_value`: _"Para operaciones de exportación, el valor FOB debe ser mayor a 0.00 y los campos de ventas internas deben ser 0.00."_
    

#### [ID_EC_019] - Incoherencia en tipo de venta INTERNAL con valor FOB

- **Descripción:** Operación asignada como `INTERNAL` pero con valor FOB mayor a 0.00.
    
- **Entrada / Estímulo:** `sale_type="INTERNAL"`, `fob_export_value=50.00`.
    
- **Resultado Esperado:** `ValidationError` asignada a `fob_export_value`: _"Para operaciones de ventas internas, el valor FOB de exportación debe ser 0.00 o nulo."_
    

#### [ID_EC_020] - Violación de Inmutabilidad en clean() sobre registro PROCESSED

- **Descripción:** Intento de modificación vía `clean()` sobre un registro consolidado en estado `PROCESSED`.
    
- **Entrada / Estímulo:** Invocar `clean()` sobre una instancia preexistente (`self.pk`) en BD con `record_status="PROCESSED"`.
    
- **Resultado Esperado:** Interrupción de la persistencia y `ValidationError` vía `non_field_errors`: _"No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'."_
    

#### [ID_EC_021] - Violación de Inmutabilidad en clean() sobre registro ANNULLED_PROCESSED

- **Descripción:** Intento de modificación vía `clean()` sobre un registro en estado `ANNULLED_PROCESSED`.
    
- **Entrada / Estímulo:** Invocar `clean()` sobre una instancia preexistente (`self.pk`) en BD con `record_status="ANNULLED_PROCESSED"`.
    
- **Resultado Esperado:** Interrupción de la persistencia y `ValidationError` vía `non_field_errors`: _"No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'."_
    

#### [ID_EC_022] - Formato de número de control o comprobante de retención inválido

- **Descripción:** Envío de cadenas que violan las expresiones regulares de formato de imprenta o SENIAT.
    
- **Entrada / Estímulo:** `control_number="INVALID_FORMAT_123"`.
    
- **Resultado Esperado:** Falla la validación a nivel de campo por la regex configurada.
    

#### [ID_EC_023] - Acumulación masiva de errores en método de validación clean

- **Descripción:** Envío de un objeto con múltiples infracciones simultáneas (ej. Ecuación contable incorrecta, fecha futura y omisión de documento afectado en nota de crédito).
    
- **Entrada / Estímulo:** Objeto que invalida las 3 reglas indicadas al mismo tiempo.
    
- **Resultado Esperado:** El método `clean()` compila todas las fallas en la estructura `errors_dict` asociando cada mensaje a su respectivo campo y lanza una única excepción `ValidationError(errors_dict)`.