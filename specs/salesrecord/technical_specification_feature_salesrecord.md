
## 1. Especificación del Modelo de Base de Datos (`SalesRecord`)

El modelo debe llamarse `SalesRecord` y heredar de la clase base abstracta `FiscalModuleAbstractModel` para garantizar un estricto aislamiento de datos entre inquilinos (_tenants_).

### 1.1 Clases de Enumeración

El modelo debe definir las siguientes clases internas de enumeración basadas en `models.TextChoices`:

- `DocumentType`: `INVOICE` (Factura), `CREDIT_NOTE` (Nota de Crédito), `DEBIT_NOTE` (Nota de Débito).
    
- `TransactionType`: `01_REGISTER` (01 Registro), `02_COMPLEMENT` (02 Complemento), `03_ANNULMENT` (03 Anulación), `04_ADJUSTMENT` (04 Ajuste).
    
- `SaleType`: `INTERNAL` (Interna), `EXPORT` (Exportación).
    
- `RecordStatus`: `PRELIMINARY` (Preliminar), `ANNULLED` (Anulado), `PROCESSED` (Procesado), `ANNULLED_PROCESSED` (Anulado_Procesado). El valor por defecto debe ser `PRELIMINARY`.
    

### 1.2 Atributos del Modelo

Los atributos deben agruparse y nombrarse en inglés, implementando el mapeo correspondiente a la legislación fiscal venezolana:

**Identificación**

- `fiscal_period` (`DateField`)
    
- `document_date` (`DateField`): Fecha Doc. (Artículos 76 al 78 Regla. LIVA).
    
- `invoice_number` (`CharField`): N° Factura / 1er Comprob. (Artículos 76 al 78 Regla. LIVA).
    
- `last_receipt_number` (`CharField`): N° Último Comprob. Día (Artículos 76 al 78 Regla. LIVA).
    
- `document_number` (`CharField`): N° Documento (Artículos 76 al 78 Regla. LIVA).
    
- `control_number` (`CharField`): N° Control (Artículos 76 al 78 Regla. LIVA).
    
- `document_type` (`CharField`, utiliza `DocumentType`): Tipo de Documento (Artículos 76 al 78 Regla. LIVA).
    
- `transaction_type` (`CharField`, utiliza `TransactionType`): Tipo de Transacción (Artículos 76 al 78 Regla. LIVA).
    
- `sale_type` (`CharField`, utiliza `SaleType`): Tipo de Venta (Artículos 76 al 78 Regla. LIVA).
    
- `fiscal_printer_number` (`CharField`): N° Máq. Fiscal (Artículos 76 al 78 Regla. LIVA).
    
- `z_report_number` (`CharField`): N° Reporte Z (Artículos 76 al 78 Regla. LIVA).
    
- `record_status` (`CharField`, utiliza `RecordStatus`, por defecto `PRELIMINARY`, blank=True): Estado del Registro (Artículos 76 al 78 Regla. LIVA).
    

**Relaciones**

- `affected_invoice` (`ForeignKey` hacia `self`): N° Factura Afectada (Artículos 76 al 78 Regla. LIVA).
    
- `client` (`ForeignKey` hacia el modelo de cliente): Cliente (Artículos 76 al 78 Regla. LIVA).
    

**Montos Consolidados y Exenciones**

- `total_sales_inc_vat` (`DecimalField`): Total Ventas inc. IVA (Artículos 76 al 78 Regla. LIVA).
    
- `exempt_internal_sales` (`DecimalField`): Ventas Internas Exentas (Artículos 76 al 78 Regla. LIVA).
    
- `exonerated_internal_sales` (`DecimalField`): Ventas Internas Exoneradas (Artículos 76 al 78 Regla. LIVA).
    
- `non_subject_internal_sales` (`DecimalField`): Ventas Internas No sujetas (Artículos 76 al 78 Regla. LIVA).
    

**Desglose de Impuestos (Ventas Gravadas por Alícuota)**

- `general_tax_base_16` (`DecimalField`): Base Imp. General (16%) (Artículos 76 al 78 Regla. LIVA).
    
- `general_tax_debit_16` (`DecimalField`): Débito Fiscal (16%) (Artículos 76 al 78 Regla. LIVA).
    
- `reduced_tax_base_8` (`DecimalField`): Base Imp. Reducida (8%) (Artículos 76 al 78 Regla. LIVA).
    
- `reduced_tax_debit_8` (`DecimalField`): Débito Fiscal (8%) (Artículos 76 al 78 Regla. LIVA).
    
- `additional_tax_base_31` (`DecimalField`): Base Imp. General mas Adicional (31%) (Artículos 76 al 78 Regla. LIVA).
    
- `additional_tax_debit_31` (`DecimalField`): Débito Fiscal (31%) (Artículos 76 al 78 Regla. LIVA).
    

**IGTF (Agentes de percepción - Contribuyentes Especiales)**

- `igtf_tax_base` (`DecimalField`): Base Imponible I.G.T.F. (SNAT/2022/000013).
    
- `igtf_tax_amount` (`DecimalField`): I.G.T.F. 3% (SNAT/2022/000013).
    

**Comercio Exterior (Operaciones de Comercio Exterior)**

- `fob_export_value` (`DecimalField`): Valor FOB Exportación (Artículos 76 al 78 Regla. LIVA).
    

### 1.3 Restricciones de Base de Datos (`Meta`)

- **UniqueConstraints:**
    
    - `unique_issued_document`: Campos `(fiscal_profile, control_number, document_type)` para evitar la duplicación de secuencias. **Mensaje de error:** `"Ya existe un documento registrado con este N° de Control y Tipo de Documento para el perfil fiscal actual."`
        
    - `unique_z_report`: Campos `(fiscal_profile, fiscal_printer_number, z_report_number, invoice_number, last_receipt_number)` para evitar registrar dos veces el mismo Reporte Z. **Mensaje de error:** `"Este N° de Reporte Z ya fue registrado previamente para la máquina fiscal especificada."`
        
- **CheckConstraints:**
    
    - `positive_amounts`: Garantizar que `total_sales_inc_vat` y todas las bases imponibles sean >= 0.00. **Mensaje de error:** `"El monto total de la venta y las bases imponibles deben ser mayores o iguales a 0.00."`
        
    - `valid_receipt_sequence`: Garantizar que `last_receipt_number` >= `invoice_number` (actuando como primer comprobante). **Mensaje de error:** `"El número del último comprobante del día no puede ser menor al número del primer comprobante."`
        
    - `zero_amount_on_annulment`: Si `transaction_type` es '03', la suma global de montos debe ser estrictamente igual a 0.00. **Mensaje de error:** `"Las transacciones registradas como anulación requieren que la suma global de sus montos sea 0.00."`
        

## 2. Validaciones y Restricciones

### 2.1 Sanitización a Nivel de Campo

- **Números de Control y Factura:** Rellenar con ceros a la izquierda (_padding_) o eliminar espacios en blanco para estandarizar las búsquedas.
    
- **Validadores de Formato:** `control_number` requiere una expresión regular de formato de imprenta exacto, y los comprobantes de retención deben cumplir el formato SENIAT `AAAAMM + 10 dígitos`.
    
- **Límites:** `MinValueValidator(0.00)` en todos los campos de base imponible, débitos fiscales y montos exentos.
    

### 2.2 Lógica de Negocio en `clean()` y Mapeo de Mensajes al Formulario

El método `clean()` consolida las violaciones en un diccionario `errors_dict` que se eleva mediante `ValidationError(errors_dict)`, mapeando automáticamente cada mensaje al campo correspondiente del formulario (`form.errors`):

#### Validaciones por Origen de Operación

- **Grupo A: Documentación Fiscal Interna**
    
    - _Condición de Activación:_ Esta lógica se activa cuando el campo `document_type` no está vacío ni es nulo (`document_type` presente).
        
    - _Coherencia de Campos Excluyentes en Documentación Interna:_
        
        - _Regla:_ Cuando se define un `document_type`, los campos `invoice_number`, `last_receipt_number`, `fiscal_printer_number` y `z_report_number` deben estar vacíos. Si alguno contiene un valor previo, la validación debe fallar lanzando una excepción.
            
        - _Campos afectados:_ `invoice_number`, `last_receipt_number`, `fiscal_printer_number`, `z_report_number`.
            
        - _Mensaje emitido:_ `"Los campos de impresora fiscal (N° de factura/comprobante, N° de último comprobante, N° de máquina fiscal y N° de reporte Z) deben estar vacíos al registrar documentación fiscal interna."`
            
    - _Exclusión de Factura Afectada para Facturas Regulares (`INVOICE`):_
        
        - _Regla:_ Si el valor de `document_type` es `"INVOICE"`, el campo `affected_invoice` debe estar totalmente vacío. Si contiene un valor previo, la validación debe lanzar una excepción.
            
        - _Campo afectado:_ `affected_invoice`.
            
        - _Mensaje emitido:_ `"Las facturas de tipo 'INVOICE' no deben incluir referencia a una factura afectada."`
            
    - _Documentos Afectados para Notas de Crédito y Débito (`CREDIT_NOTE` / `DEBIT_NOTE`):_
        
        - _Regla:_ Si `document_type` es `CREDIT_NOTE` o `DEBIT_NOTE`, se requiere obligatoriamente especificar el campo `affected_invoice`. Si este campo no está presente o está vacío, se debe lanzar una excepción.
            
        - _Campo afectado:_ `affected_invoice`.
            
        - _Mensaje emitido:_ `"Las Notas de Crédito y Débito requieren especificar el N° de factura afectada, N° de control afectado y su fecha original."`
            
    - _Campos Obligatorios de Documentación Interna:_
        
        - _Regla:_ Los campos `document_number` y `control_number` son requeridos obligatoriamente, por lo que deben contener valores válidos (no vacíos ni `None`).
            
        - _Campos afectados:_ `document_number`, `control_number`.
            
        - _Mensajes emitidos:_
            
            - Para `document_number`: `"El número de documento es requerido y debe ser un valor válido."`
                
            - Para `control_number`: `"El número de control es requerido y debe ser un valor válido."`
                
- **Grupo B: Registro de Impresora Fiscal (Datos Impresos)**
    
    - _Condición de Activación:_ Esta lógica se activa cuando al menos uno de los siguientes campos tiene un valor asignado (no vacío ni nulo): `invoice_number`, `fiscal_printer_number` o `z_report_number`.
        
    - _Coherencia de Campos Excluyentes en Impresora Fiscal:_
        
        - _Regla:_ Cuando se activa el registro por máquina fiscal, los campos `document_type`, `document_number`, `control_number` y `affected_invoice` deben estar completamente vacíos. Si alguno contiene un valor, la validación lanza una excepción.
            
        - _Campos afectados:_ `document_type`, `document_number`, `control_number`, `affected_invoice`.
            
        - _Mensaje emitido:_ `"Los campos de documentación interna (tipo de documento, N° de documento, N° de control y factura afectada) deben estar vacíos cuando se registra una operación de impresora fiscal."`
            
    - _Campos Requeridos por Dependencia Conjunta en Impresora Fiscal:_
        
        - _Regla:_ Se exige dependencia conjunta de datos. Los tres campos (`invoice_number`, `fiscal_printer_number` y `z_report_number`) deben estar presentes y contener valores válidos simultáneamente (no vacíos ni `None`).
            
        - _Campos afectados:_ `invoice_number`, `fiscal_printer_number`, `z_report_number`.
            
        - _Mensaje emitido:_ `"El registro de impresora fiscal requiere que el N° de factura/comprobante, el N° de máquina fiscal y el N° de reporte Z estén presentes simultáneamente."`
            

#### Validaciones Generales de Negocio

- **Restricción de Inmutabilidad Fiscal**
    
    - _Regla:_ Si el registro ya existe en la base de datos (`self.pk`) y su estatus almacenado es `PROCESSED` o `ANNULLED_PROCESSED`, se interrumpe la persistencia.
        
    - _Campo afectado:_ Error global del formulario vía `non_field_errors`.
        
    - _Mensaje emitido:_ `"No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'."`
		
- **Ecuación Contable del Total**
    
    - _Regla:_ `total_sales_inc_vat` debe ser igual a la suma de `exempt_internal_sales` + `exonerated_internal_sales` + `non_subject_internal_sales` + `fob_export_value` + (Bases Imponibles + Débitos Fiscales).
        
    - _Campo afectado:_ `total_sales_inc_vat`
        
    - _Mensaje emitido:_ `"El total de ventas incluido IVA no coincide con la suma de las ventas exentas, exoneradas, no sujetas, valor FOB y bases imponibles con sus débitos fiscales."`
        
- **Cálculo Débito Fiscal General (16%)**
    
    - _Regla:_ Si `general_tax_base_16 > 0`, `general_tax_debit_16` debe ser exactamente igual al 16% de la base (tolerancia ±0.01).
        
    - _Campo afectado:_ `general_tax_debit_16`
        
    - _Mensaje emitido:_ `"El débito fiscal (16%) no coincide con el 16% de la base imponible general indicada."`
        
- **Cálculo Débito Fiscal Reducido (8%)**
    
    - _Regla:_ Si `reduced_tax_base_8 > 0`, `reduced_tax_debit_8` debe ser exactamente igual al 8% de la base (tolerancia ±0.01).
        
    - _Campo afectado:_ `reduced_tax_debit_8`
        
    - _Mensaje emitido:_ `"El débito fiscal (8%) no coincide con el 8% de la base imponible reducida indicada."`
        
- **Cálculo Débito Fiscal Adicional (31%)**
    
    - _Regla:_ Si `additional_tax_base_31 > 0`, `additional_tax_debit_31` debe ser exactamente igual al 31% de la base (tolerancia ±0.01).
        
    - _Campo afectado:_ `additional_tax_debit_31`
        
    - _Mensaje emitido:_ `"El débito fiscal (31%) no coincide con el 31% de la base imponible adicional indicada."`
        
- **Consistencia de Débito Fiscal en Cero**
    
    - _Regla:_ Si una base imponible es 0.00 o nula, su débito fiscal asociado debe ser estrictamente 0.00.
        
    - _Campos afectados:_ Campo de débito fiscal de la alícuota correspondiente (`general_tax_debit_16`, `reduced_tax_debit_8`, o `additional_tax_debit_31`).
        
    - _Mensaje emitido:_ `"El débito fiscal debe ser exactamente 0.00 cuando la base imponible asociada sea igual a 0.00 o nula."`
        
- **Anulación de Documentos**
    
    - _Regla:_ Si `transaction_type == '03_ANNULMENT'` o `record_status == 'ANNULLED'`, la razón social/cliente debe ser "ANULADO" y todos los montos deben ser 0.00.
        
    - _Campo afectado:_ `transaction_type` / `record_status`
        
    - _Mensaje emitido:_ `"Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."`
        
- **Cálculo de IGTF Percibido (3%)**
    
    - _Regla:_ Si `igtf_tax_base > 0.00`, `igtf_tax_amount` debe corresponder exactamente al 3% (tolerancia ±0.01). Si la base es 0.00, el monto debe ser 0.00.
        
    - _Campo afectado:_ `igtf_tax_amount`
        
    - _Mensaje emitido:_ `"El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."`
        
- **Restricción de Fecha Futura**
    
    - _Regla:_ `document_date` no puede ser posterior a `timezone.now().date()`.
        
    - _Campo afectado:_ `document_date`
        
    - _Mensaje emitido:_ `"La fecha del documento no puede ser posterior a la fecha actual del sistema."`
        
- **Consistencia por Tipo de Venta y Valor FOB**
    
    - _Regla:_ Si `sale_type == 'EXPORT'`, `fob_export_value` debe ser > 0.00 y las ventas internas deben ser 0.00. Si `sale_type == 'INTERNAL'`, `fob_export_value` debe ser 0.00 o nulo.
        
    - _Campos afectados:_ `sale_type` / `fob_export_value`
        
    - _Mensajes emitidos:_
        
        - Para exportación inválida: `"Para operaciones de exportación, el valor FOB debe ser mayor a 0.00 y los campos de ventas internas deben ser 0.00."`
            
        - Para venta interna con FOB: `"Para operaciones de ventas internas, el valor FOB de exportación debe ser 0.00 o nulo."`
            

### 2.3 Persistencia y Normalización de Datos en `save()`

El proceso de almacenamiento y sanitización previo a la persistencia en el método `save()` evalúa la instancia previa y aplica las siguientes reglas de asignación y normalización automática:

- **Persistencia de Estatus para Anulaciones**
    
    - _Regla:_ Los registros con `transaction_type == '03_ANNULMENT'` se deben persistir obligatoriamente con `record_status = 'ANNULLED'`.
        
- **Normalización de Documentación Fiscal Interna (Grupo A)**
    
    - _Regla:_ Si se procesa un registro del Grupo A (`document_type` presente), los campos `invoice_number`, `last_receipt_number`, `fiscal_printer_number` y `z_report_number` se persisten obligatoriamente como `None`. Adicionalmente, si `document_type` es `"INVOICE"`, el campo `affected_invoice` se persiste obligatoriamente como `None`.
        
    - _Campos afectados:_ `invoice_number`, `last_receipt_number`, `fiscal_printer_number`, `z_report_number`, `affected_invoice`.
        
- **Normalización de Registro de Impresora Fiscal (Grupo B)**
    
    - _Regla:_ Si se procesa un registro del Grupo B, los campos `document_type`, `document_number`, `control_number` y `affected_invoice` se persisten obligatoriamente como `None`.
        
    - _Campos afectados:_ `document_type`, `document_number`, `control_number`, `affected_invoice`.
        

## 3. Especificación del Formulario (`SalesRecordForm`)

Implementar un `ModelForm` de Django vinculado a `SalesRecord`.

- **Inicialización (`__init__`):** Extraer los elementos `fiscal_profile` y `fiscal_period` inyectados desde las vistas a través de los argumentos (`kwargs`).
	
- **Asignacion "initial" e "instance"**: Asignar directamente los elementos `fiscal_profile` y `fiscal_period` al diccionario "initial" y la "instance" (update) a sus respectivos campos.
    
- **Filtrado de ForeignKey:** Utilizar el `fiscal_profile` extraído para filtrar las relaciones de clave foránea y asegurar el aislamiento de inquilinos:
    
    Python
    
    ```
    self.fields['affected_invoice'].queryset = SalesRecord.objects.filter(fiscal_profile=fiscal_profile)
    self.fields['client'].queryset = Customer.objects.filter(fiscal_profile=fiscal_profile)
    ```
    
- **Bloqueo de Campos y Renderizado:** No renderizar visualmente `fiscal_profile` y `fiscal_period`. Configurar sus widgets como `HiddenInput()` y `disabled=True`, asignando directamente a la instancia del formulario los valores desempaquetados de la petición para que permanezcan locked a modificaciones y queden estructuralmente excluidos de manipulación por parte del usuario.
    

## 4. Especificación de Vistas

Las vistas (`SalesRecordCreateView`, `SalesRecordUpdateView` y el resto de vistas del CRUD) deben implementar Vistas Genéricas basadas en clases (CBVs de Django puro, sin DRF).

- **Aislamiento de Queryset:** Heredar de `RequestScopedQuerySetMixin` para garantizar que el queryset base esté estrictamente acotado por la petición del inquilino (_tenant_) actual.
    
- **Inyección de Argumentos (`get_form_kwargs`):** Extraer `fiscal_profile` y `fiscal_period` desde `self.request`. Utilizar la función de utilidad `unwrap_lazy_object()` para procesar posibles instancias de `SimpleLazyObject` antes de pasarlas en los argumentos del formulario:
    
    Python
    
    ```
    kwargs['fiscal_profile'] = unwrap_lazy_object(self.request.fiscal_profile)
    ```
    
## 5. Especificación de Plantillas (Templates)

Implementar una plantilla HTML simple e independiente (sin utilizar `{% extends %}`).

- **Renderizado del Formulario:** Iterar sobre los campos visibles del formulario.
    
- **Renderizado de Errores:** Renderizar explícitamente `{{ form.non_field_errors }}` en la parte superior del formulario para los fallos globales de lógica de negocio (por ejemplo, fallos en la Ecuación Contable del Total o la Restricción de Inmutabilidad Fiscal). Iterar sobre cada campo individual para renderizar `{{ field.errors }}` inmediatamente adyacente a su entrada correspondiente, satisfaciendo el mapeo granular de excepciones a nivel de campo requerido por las validaciones.