"""
utils.py - Validaciones y utilidades para el Sistema de Botica
"""

import re
from datetime import datetime

def validar_dni(dni):
    """Valida que el DNI tenga 8 dígitos numéricos."""
    if not dni:
        return True  # Opcional
    if not re.match(r'^\d{8}$', dni):
        raise ValueError("El DNI debe tener exactamente 8 dígitos numéricos.")
    return True

def validar_email(email):
    """Valida formato de email básico."""
    if not email:
        return True
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        raise ValueError("El formato del email no es válido.")
    return True

def validar_fecha(fecha_str):
    """Valida formato YYYY-MM-DD."""
    if not fecha_str:
        return True
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        raise ValueError("La fecha debe tener formato YYYY-MM-DD (ej: 2026-12-31).")

def validar_precio(valor, nombre="Precio"):
    """Valida que el precio sea un número positivo."""
    try:
        v = float(valor)
        if v < 0:
            raise ValueError(f"{nombre} no puede ser negativo.")
        return v
    except ValueError:
        raise ValueError(f"{nombre} debe ser un número válido.")

def validar_stock(valor, nombre="Stock"):
    """Valida que el stock sea un entero no negativo."""
    try:
        v = int(valor)
        if v < 0:
            raise ValueError(f"{nombre} no puede ser negativo.")
        return v
    except ValueError:
        raise ValueError(f"{nombre} debe ser un número entero válido.")

def validar_obligatorio(valor, nombre="Campo"):
    """Valida que un campo no esté vacío."""
    if not valor or not str(valor).strip():
        raise ValueError(f"El campo '{nombre}' es obligatorio.")
    return str(valor).strip()

def formatear_moneda(valor):
    """Formatea un número como soles peruanos."""
    return f"S/ {float(valor):,.2f}"

def confirmar_eliminar(parent, mensaje="¿Está seguro de eliminar este registro?"):
    """Muestra diálogo de confirmación para eliminar."""
    from tkinter import messagebox
    return messagebox.askyesno("⚠️ Confirmar Eliminación", mensaje)