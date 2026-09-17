"""
charts.py - Gráficos estadísticos profesionales
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import io

try:
    import matplotlib
    matplotlib.use('Agg')  # Backend no interactivo para generar imágenes
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_DISPONIBLE = True
except ImportError:
    MATPLOTLIB_DISPONIBLE = False

DB_PATH = Path("botica.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def grafico_ventas_por_mes(canvas_frame):
    """Gráfico de barras: ventas por mes del año actual."""
    if not MATPLOTLIB_DISPONIBLE:
        raise ImportError("Instale matplotlib: pip install matplotlib")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT strftime('%Y-%m', fecha) as mes, SUM(total) as total
        FROM ventas
        WHERE strftime('%Y', fecha) = strftime('%Y', 'now')
        GROUP BY mes
        ORDER BY mes
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    meses = [r['mes'] for r in rows]
    totales = [r['total'] for r in rows]
    
    fig = Figure(figsize=(8, 4.5), dpi=100, facecolor='#f5f5f5')
    ax = fig.add_subplot(111)
    bars = ax.bar(meses, totales, color='#1976d2', edgecolor='#0d47a1', linewidth=1.5)
    ax.set_xlabel('Mes', fontsize=11)
    ax.set_ylabel('Total Ventas (S/)', fontsize=11)
    ax.set_title('Ventas por Mes - Año Actual', fontsize=14, fontweight='bold', color='#1565c0')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Agregar valores encima de barras
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'S/ {height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    
    for widget in canvas_frame.winfo_children():
        widget.destroy()
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

def grafico_top_productos(canvas_frame, top_n=10):
    """Gráfico horizontal: productos más vendidos."""
    if not MATPLOTLIB_DISPONIBLE:
        raise ImportError("Instale matplotlib: pip install matplotlib")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.nombre, SUM(d.cantidad) as cantidad_total
        FROM detalle_ventas d
        JOIN productos p ON d.producto_id = p.id
        GROUP BY p.id
        ORDER BY cantidad_total DESC
        LIMIT ?
    ''', (top_n,))
    rows = cursor.fetchall()
    conn.close()
    
    nombres = [r['nombre'][:20] for r in rows]
    cantidades = [r['cantidad_total'] for r in rows]
    
    fig = Figure(figsize=(8, 4.5), dpi=100, facecolor='#f5f5f5')
    ax = fig.add_subplot(111)
    colors_list = plt.cm.Spectral(range(0, len(nombres) * 20, 20))
    bars = ax.barh(nombres[::-1], cantidades[::-1], color=colors_list[:len(nombres)][::-1], edgecolor='black', linewidth=0.5)
    ax.set_xlabel('Unidades Vendidas', fontsize=11)
    ax.set_title(f'Top {top_n} Productos Más Vendidos', fontsize=14, fontweight='bold', color='#1565c0')
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f'{int(width)}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(3, 0), textcoords="offset points",
                    ha='left', va='center', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    
    for widget in canvas_frame.winfo_children():
        widget.destroy()
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

def grafico_metodo_pago(canvas_frame):
    """Gráfico circular: distribución por método de pago."""
    if not MATPLOTLIB_DISPONIBLE:
        raise ImportError("Instale matplotlib: pip install matplotlib")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT metodo_pago, COUNT(*) as cantidad, SUM(total) as total
        FROM ventas
        GROUP BY metodo_pago
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    metodos = [r['metodo_pago'] for r in rows]
    totales = [r['total'] for r in rows]
    
    fig = Figure(figsize=(7, 4.5), dpi=100, facecolor='#f5f5f5')
    ax = fig.add_subplot(111)
    colors_list = ['#1976d2', '#388e3c', '#f57c00', '#7b1fa2', '#c62828']
    explode = [0.05] * len(metodos)
    
    wedges, texts, autotexts = ax.pie(totales, labels=metodos, autopct='%1.1f%%', 
                                       startangle=90, colors=colors_list[:len(metodos)],
                                       explode=explode, shadow=True, textprops={'fontsize': 10})
    ax.set_title('Ventas por Método de Pago', fontsize=14, fontweight='bold', color='#1565c0')
    
    fig.tight_layout()
    
    for widget in canvas_frame.winfo_children():
        widget.destroy()
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

def grafico_inventario_valorizado(canvas_frame):
    """Gráfico de barras: valor del inventario por categoría."""
    if not MATPLOTLIB_DISPONIBLE:
        raise ImportError("Instale matplotlib: pip install matplotlib")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT categoria, SUM(stock * precio_venta) as valor, SUM(stock) as unidades
        FROM productos
        WHERE activo = 1
        GROUP BY categoria
        ORDER BY valor DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    categorias = [r['categoria'] or 'Sin Categoría' for r in rows]
    valores = [r['valor'] for r in rows]
    
    fig = Figure(figsize=(8, 4.5), dpi=100, facecolor='#f5f5f5')
    ax = fig.add_subplot(111)
    bars = ax.bar(categorias, valores, color='#388e3c', edgecolor='#1b5e20', linewidth=1.5)
    ax.set_xlabel('Categoría', fontsize=11)
    ax.set_ylabel('Valor Inventario (S/)', fontsize=11)
    ax.set_title('Valor del Inventario por Categoría', fontsize=14, fontweight='bold', color='#2e7d32')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'S/ {height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    
    for widget in canvas_frame.winfo_children():
        widget.destroy()
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)

def grafico_ventas_por_usuario(canvas_frame):
    """Gráfico de barras: ventas por usuario/vendedor."""
    if not MATPLOTLIB_DISPONIBLE:
        raise ImportError("Instale matplotlib: pip install matplotlib")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COALESCE(usuario, 'Admin') as usuario, COUNT(*) as cantidad, SUM(total) as total
        FROM ventas
        GROUP BY usuario
        ORDER BY total DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    usuarios = [r['usuario'] for r in rows]
    totales = [r['total'] for r in rows]
    
    fig = Figure(figsize=(8, 4.5), dpi=100, facecolor='#f5f5f5')
    ax = fig.add_subplot(111)
    colors_list = ['#c62828', '#f57c00', '#388e3c', '#1976d2', '#7b1fa2']
    bars = ax.bar(usuarios, totales, color=colors_list[:len(usuarios)], edgecolor='black', linewidth=0.5)
    ax.set_xlabel('Usuario / Vendedor', fontsize=11)
    ax.set_ylabel('Total Ventas (S/)', fontsize=11)
    ax.set_title('Ventas por Usuario', fontsize=14, fontweight='bold', color='#c62828')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'S/ {height:.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    fig.tight_layout()
    
    for widget in canvas_frame.winfo_children():
        widget.destroy()
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)