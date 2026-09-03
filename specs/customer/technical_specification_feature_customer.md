## 1. Database Model (`Customer`)

El modelo encargado del registro de clientes heredará del modelo abstracto `FiscalModuleAbstractModel` para garantizar el aislamiento multi-inquilino.

- **Nombre del Modelo:** `Customer`
    
- **Herencia:** `FiscalModuleAbstractModel`.
    
- **Enumeración:** Se implementará la clase `TaxpayerType` heredando de `models.TextChoices` al inicio del modelo con las opciones: `ORDINARY`, `SPECIAL` y `NON_TAXPAYER`.
    
- **Atributos y Mapeo Legal:** Todos los atributos responderán a los requerimientos de identificación del comprador estipulados en los Artículos 76 al 78 del Reglamento de la Ley del Impuesto al Valor Agregado (Regla. LIVA).
    
    - `rif`: `models.CharField`. Validado con expresión regular.
        
    - `name`: `models.CharField`. Representa el Nombre / Razón Social del Comprador.
        
    - `fiscal_address`: `models.TextField`. Representa la Dirección Fiscal.
        
    - `phone_number`: `models.CharField`. Representa el Teléfono.
        
    - `taxpayer_type`: `models.CharField`. Utiliza la enumeración `TaxpayerType` para la verificación de retenciones.
        
    - `custom_accounts_receivable`: `models.ForeignKey` a `AccountModel` (Opcional).
        
    - `custom_income_account`: `models.ForeignKey` a `AccountModel` (Opcional).
        

Python

```
class Customer(FiscalModuleAbstractModel):
    class TaxpayerType(models.TextChoices):
        ORDINARY = "ORDINARY", "Ordinario"
        SPECIAL = "SPECIAL", "Especial"
        NON_TAXPAYER = "NON_TAXPAYER", "No Contribuyente"

    # Articulos 76 al 78 Regla. LIVA: Identificación del Cliente
    rif = models.CharField(max_length=20, validators=[rif_format_validator])
    # ... resto de la implementación
```

## 2. Validations & Constraints

Las validaciones aseguran la integridad fiscal y la coherencia de los datos ingresados en la base de datos PostgreSQL.

- **Validators (Nivel de Campo):**
    
    - El atributo `rif` implementará un `RegexValidator` para admitir únicamente prefijos V, E, J, G, P, C seguidos de 8 a 9 dígitos.
        
    - El atributo `phone_number` implementará un `RegexValidator` para asegurar una longitud de 10 a 11 dígitos y códigos de área válidos.
        
- **Método `clean()`:**
    
    - Verificará la consistencia entre el prefijo del `rif` y el `taxpayer_type`.
        
    - En caso de fallo, se lanzará una excepción `ValidationError` estructurada como un diccionario (`{"rif": "Inconsistencia tributaria: El prefijo del RIF no corresponde con el Tipo de Contribuyente seleccionado."}`) para asignar el error al campo específico en el formulario.
        
- **Restricciones de Base de Datos (`Meta.constraints`):**
    
    - Se implementará un `models.UniqueConstraint` sobre el campo `rif` con el mensaje de error: _"Ya existe un registro activo con este número de RIF en la base de datos."_.
        
    - Se implementarán múltiples `models.CheckConstraint` utilizando `~models.Q(campo="")` para los campos `rif`, `name`, `fiscal_address`, `phone_number` y `taxpayer_type` con el mensaje de error: _"Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."_.
        

## 3. Views (`CustomerCreateView` & `CustomerUpdateView`)

Las vistas genéricas de Django manejarán la lógica de presentación y persistencia, aislando la data por inquilino.

- **Clases Base:** Se utilizarán `CreateView`, `UpdateView` y resto de view del `CRUD` heredando del mixin `RequestScopedQuerySetMixin` para garantizar el filtrado por Tenant.
    
- **Método `get_form_kwargs()` (En Creación):**
    
    - Se sobrescribirá para inyectar el perfil fiscal en el formulario.
        
    - Se extraerá el objeto perezoso del request y se procesará mediante la función `unwrap_lazy_object` para obtener la instancia real de `FiscalProfile`.
        
- **Método `form_valid()`:**
    
    - La ejecución de `form.save()` se envolverá en un bloque `try...except ValidationError`.
        
    - Capturará las excepciones lanzadas por las validaciones de negocio en `clean()` y las restricciones de base de datos (`IntegrityError` o `ValidationError` de los constraints del modelo).
        
    - Las excepciones capturadas se añadirán al formulario mediante `form.add_error()` para re-renderizar la vista con los mensajes correspondientes.
        

Python

```
class CustomerCreateView(RequestScopedQuerySetMixin, CreateView):
    model = Customer
    form_class = CustomerForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Desempaquetado del objeto lazy
        fiscal_profile = unwrap_lazy_object(self.request.fiscal_profile)
        kwargs['fiscal_profile'] = fiscal_profile
        return kwargs
```

## 4. Form (`CustomerForm`)

El formulario actuará como puente para la inyección de dependencias del perfil fiscal y la limitación de los selectores relacionales.

- **Clase Base:** `forms.ModelForm` enlazado al modelo `Customer`.
    
- **Método `__init__()`:**
    
    - Recibirá el argumento `fiscal_profile` desde los `kwargs` (en creación) o desde `self.instance.fiscal_profile` (en actualización).
        
    - Filtrará los querysets de los campos `custom_accounts_receivable` y `custom_income_account` utilizando el "ChartOfAccountModel"asociado al `fiscal_profile.entity` y contenedor de su "AccountModel".
        
    - Asignará la instancia de `fiscal_profile` al campo homónimo en el formulario.
        
    - Para cumplir con el requerimiento de bloqueo y no renderizado: el campo `fiscal_profile` se configurará con `widget=forms.HiddenInput()` y `disabled=True`, o alternativamente, se excluirá en la clase `Meta` (`exclude = ['fiscal_profile']`) y se asignará directamente a `self.instance.fiscal_profile` antes del guardado.
        

Python

```
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = ['fiscal_profile']

    def __init__(self, *args, **kwargs):
        fiscal_profile = kwargs.pop('fiscal_profile', None)
        super().__init__(*args, **kwargs)
        
        if fiscal_profile:
            self.instance.fiscal_profile = fiscal_profile
            # Filtrado de cuentas por el Ledger del Tenant
            self.fields['custom_accounts_receivable'].queryset =
        AccountModel.objects.filter(coa_model=fiscal_profile.entity.default_coa)
```

## 5. Template (`customer_form.html`)

Se implementará una estructura HTML plana enfocada en el renderizado individual de campos y la visualización de las excepciones capturadas desde el backend.

HTML

```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Customer Registry</title>
</head>
<body>
    <h1>Register New Customer</h1>
    
    <!-- Renderizado de errores generales capturados en form_valid() -->
    {% if form.non_field_errors %}
        <div class="error-container">
            {{ form.non_field_errors }}
        </div>
    {% endif %}

    <form method="post">
        {% csrf_token %}
        
        <!-- Renderizado de campo individual con mapeo de errores del clean() -->
        <div>
            <label for="{{ form.rif.id_for_label }}">RIF:</label>
            {{ form.rif }}
            {% if form.rif.errors %}
                <span class="field-error">{{ form.rif.errors }}</span>
            {% endif %}
        </div>

        <div>
            <label for="{{ form.taxpayer_type.id_for_label }}">Taxpayer Type:</label>
            {{ form.taxpayer_type }}
            {% if form.taxpayer_type.errors %}
                <span class="field-error">{{ form.taxpayer_type.errors }}</span>
            {% endif %}
        </div>

        <!-- Renderizado continuo del resto de los campos... -->

        <button type="submit">Save Customer</button>
    </form>
</body>
</html>
```