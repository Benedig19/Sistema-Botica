import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from models import Producto, Cliente, Venta
from utils import (
    validar_dni, validar_email, validar_fecha, validar_precio, 
    validar_stock, validar_obligatorio, formatear_moneda, confirmar_eliminar
)
from datetime import datetime, date
import os
import shutil
from pathlib import Path

# Importar módulos nuevos (si están disponibles)
try:
    from charts import (
        grafico_ventas_por_mes, grafico_top_productos, 
        grafico_metodo_pago, grafico_inventario_valorizado,
        grafico_ventas_por_usuario
    )
    CHARTS_OK = True
except ImportError:
    CHARTS_OK = False

try:
    from export import exportar_inventario_excel, exportar_ventas_excel, exportar_ventas_pdf
    EXPORT_OK = True
except ImportError:
    EXPORT_OK = False

class BoticaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("💊 Sistema de Ventas - Botica")
        self.root.geometry("1350x800")
        self.root.configure(bg="#e3f2fd")
        
        self.carrito = []
        self.cliente_seleccionado = None
        self.cliente_nombre = "Cliente General"
        self.producto_editando = None
        self.cliente_editando = None
        self.usuario_actual = "Admin"  # Para auditoría
        
        self.crear_estilos()
        self.crear_menu()
        self.crear_pestañas()
        self.crear_barra_estado()
        self.bind_teclas()
        
        # Capturar el cierre de ventana para hacer backup automático
        self.root.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        
        # Iniciar respaldo automático cada 30 minutos (1,800,000 ms)
        self.iniciar_backup_automatico()
        
    def crear_estilos(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", font=('Segoe UI', 10), rowheight=26)
        style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'), background="#1976d2", foreground="white")
        style.map("Treeview.Heading", background=[('active', '#1565c0')])
        style.configure("TButton", font=('Segoe UI', 10), padding=6)
        style.configure("TLabel", font=('Segoe UI', 10))
        style.configure("TEntry", font=('Segoe UI', 10))
        
    def crear_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="🖥️ Pantalla Completa (F11)", command=self.toggle_fullscreen)
        archivo.add_separator()
        archivo.add_command(label="📊 Exportar Inventario a Excel", command=self.exportar_inventario_excel)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.root.quit)
        menubar.add_cascade(label="Archivo", menu=archivo)
        
        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(label="Acerca de", command=self.mostrar_acerca)
        menubar.add_cascade(label="Ayuda", menu=ayuda)
    
    def crear_pestañas(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)
        
        self.tab_venta = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_venta, text="🛒  Punto de Venta")
        self.setup_venta()
        
        self.tab_productos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_productos, text="📦  Productos")
        self.setup_productos()
        
        self.tab_clientes = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_clientes, text="👥  Clientes")
        self.setup_clientes()
        
        self.tab_reportes = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_reportes, text="📊  Reportes")
        self.setup_reportes()
        
        # NUEVA PESTAÑA: Estadísticas
        self.tab_stats = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_stats, text="📈  Estadísticas")
        self.setup_estadisticas()
    
    def crear_barra_estado(self):
        self.barra_estado = ttk.Frame(self.root, relief=tk.SUNKEN)
        self.barra_estado.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status_usuario = ttk.Label(self.barra_estado, text=f"👤 Usuario: {self.usuario_actual}", font=('Segoe UI', 9))
        self.lbl_status_usuario.pack(side=tk.LEFT, padx=10, pady=3)
        
        resumen = Venta.obtener_resumen_hoy()
        self.lbl_status_hoy = ttk.Label(self.barra_estado, 
            text=f"📅 Hoy: {resumen['cantidad']} ventas | Total: {formatear_moneda(resumen['total'])}", 
            font=('Segoe UI', 9))
        self.lbl_status_hoy.pack(side=tk.RIGHT, padx=10, pady=3)
    
    def actualizar_barra_estado(self):
        resumen = Venta.obtener_resumen_hoy()
        self.lbl_status_hoy.config(
            text=f"📅 Hoy: {resumen['cantidad']} ventas | Total: {formatear_moneda(resumen['total'])}"
        )
    
    def bind_teclas(self):
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Escape>', lambda e: self.salir_fullscreen())

    def iniciar_backup_automatico(self, intervalo_ms=1800000):
        """Inicia el respaldo automático cada intervalo_ms milisegundos."""
        # Guardar el id del job para poder cancelarlo si es necesario
        try:
            # Ejecutar una primera vez inmediatamente en hilo de GUI
            self.realizar_backup()
        except Exception:
            # No queremos que un error impida el programado
            pass
        # Programar next
        self._backup_job = self.root.after(intervalo_ms, lambda: self._backup_cycle(intervalo_ms))

    def _backup_cycle(self, intervalo_ms):
        try:
            self.realizar_backup()
        except Exception:
            pass
        self._backup_job = self.root.after(intervalo_ms, lambda: self._backup_cycle(intervalo_ms))

    def realizar_backup(self):
        """Realiza un respaldo simple copiando la base de datos (si existe) a carpeta 'backups'."""
        # Supongamos que la base de datos es un archivo llamado 'botica.db' en el directorio del proyecto
        db_path = Path('botica.db')
        backups_dir = Path('backups')
        try:
            backups_dir.mkdir(parents=True, exist_ok=True)
            if db_path.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                dest = backups_dir / f"botica_backup_{timestamp}.db"
                shutil.copy2(db_path, dest)
        except Exception:
            # Silenciar errores en respaldo automático
            return

    def al_cerrar(self):
        """Maneja el cierre de la aplicación."""
        if messagebox.askokcancel("Salir", "¿Desea salir de la aplicación?"):
            self.root.destroy()
    
    def toggle_fullscreen(self):
        self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen'))
    
    def salir_fullscreen(self):
        self.root.attributes('-fullscreen', False)
    
    # ==================== PUNTO DE VENTA ====================
    def setup_venta(self):
        left_frame = ttk.LabelFrame(self.tab_venta, text=" Búsqueda de Productos ")
        left_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=5, pady=5)
        
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(search_frame, text="Buscar:").pack(side=tk.LEFT, padx=2)
        self.entry_buscar = ttk.Entry(search_frame, width=35, font=('Segoe UI', 11))
        self.entry_buscar.pack(side=tk.LEFT, fill='x', expand=True, padx=2)
        self.entry_buscar.bind('<Return>', lambda e: self.buscar_productos_venta())
        
        ttk.Button(search_frame, text="🔍 Buscar", command=self.buscar_productos_venta).pack(side=tk.LEFT, padx=2)
        
        columns = ('codigo', 'nombre', 'precio', 'stock')
        self.tree_prod_buscar = ttk.Treeview(left_frame, columns=columns, show='headings', height=12)
        self.tree_prod_buscar.heading('codigo', text='Código')
        self.tree_prod_buscar.heading('nombre', text='Nombre')
        self.tree_prod_buscar.heading('precio', text='Precio Venta')
        self.tree_prod_buscar.heading('stock', text='Stock')
        self.tree_prod_buscar.column('codigo', width=80, anchor='center')
        self.tree_prod_buscar.column('nombre', width=200)
        self.tree_prod_buscar.column('precio', width=100, anchor='e')
        self.tree_prod_buscar.column('stock', width=80, anchor='center')
        self.tree_prod_buscar.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.tree_prod_buscar, orient="vertical", command=self.tree_prod_buscar.yview)
        self.tree_prod_buscar.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        self.tree_prod_buscar.bind('<Double-1>', self.agregar_al_carrito)
        ttk.Label(left_frame, text="💡 Doble clic para agregar al carrito", 
                 foreground="gray", font=('Segoe UI', 9, 'italic')).pack(pady=2)
        
        right_frame = ttk.LabelFrame(self.tab_venta, text=" Carrito de Venta ")
        right_frame.pack(side=tk.RIGHT, fill='both', expand=True, padx=5, pady=5)
        
        cliente_frame = ttk.Frame(right_frame)
        cliente_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(cliente_frame, text="👤 Cliente:", font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT)
        self.lbl_cliente = ttk.Label(cliente_frame, text=self.cliente_nombre, font=('Segoe UI', 10))
        self.lbl_cliente.pack(side=tk.LEFT, padx=5)
        ttk.Button(cliente_frame, text="Seleccionar", command=self.seleccionar_cliente).pack(side=tk.RIGHT)
        
        columns = ('nombre', 'cantidad', 'precio', 'subtotal')
        self.tree_carrito = ttk.Treeview(right_frame, columns=columns, show='headings', height=10)
        self.tree_carrito.heading('nombre', text='Producto')
        self.tree_carrito.heading('cantidad', text='Cant.')
        self.tree_carrito.heading('precio', text='P. Unit')
        self.tree_carrito.heading('subtotal', text='Subtotal')
        self.tree_carrito.column('nombre', width=180)
        self.tree_carrito.column('cantidad', width=60, anchor='center')
        self.tree_carrito.column('precio', width=90, anchor='e')
        self.tree_carrito.column('subtotal', width=100, anchor='e')
        self.tree_carrito.pack(fill='both', expand=True, padx=5, pady=5)
        
        total_frame = ttk.Frame(right_frame)
        total_frame.pack(fill='x', padx=5, pady=10)
        ttk.Label(total_frame, text="TOTAL A PAGAR:", font=('Segoe UI', 16, 'bold')).pack(side=tk.LEFT)
        self.lbl_total = ttk.Label(total_frame, text="S/ 0.00", font=('Segoe UI', 18, 'bold'), foreground="#c62828")
        self.lbl_total.pack(side=tk.LEFT, padx=15)
        
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="🗑️ Eliminar Item", command=self.eliminar_item_carrito).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🧹 Limpiar Todo", command=self.limpiar_carrito).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="💰 Procesar Venta", command=self.procesar_venta).pack(side=tk.RIGHT, padx=2)
    
    def buscar_productos_venta(self):
        termino = self.entry_buscar.get().strip()
        if not termino:
            messagebox.showwarning("Búsqueda vacía", "Ingrese un término para buscar.")
            return
        
        for item in self.tree_prod_buscar.get_children():
            self.tree_prod_buscar.delete(item)
        
        productos = Producto.buscar(termino)
        if not productos:
            messagebox.showinfo("Sin resultados", "No se encontraron productos.")
            return
            
        for p in productos:
            self.tree_prod_buscar.insert('', 'end', values=(
                p['codigo'], p['nombre'], f"S/ {p['precio_venta']:.2f}", p['stock']
            ), tags=(str(p['id']),))
    
    def agregar_al_carrito(self, event=None):
        seleccion = self.tree_prod_buscar.selection()
        if not seleccion:
            return
        
        item = self.tree_prod_buscar.item(seleccion[0])
        producto_id = int(item['tags'][0])
        producto = Producto.obtener_por_id(producto_id)
        
        if not producto:
            messagebox.showerror("Error", "No se encontró el producto.")
            return
        
        if producto['stock'] <= 0:
            messagebox.showwarning("Sin stock", f"'{producto['nombre']}' no tiene stock disponible.")
            return
        
        cantidad = simpledialog.askinteger(
            "Cantidad", 
            f"Producto: {producto['nombre']}\nStock disponible: {producto['stock']}\n\nIngrese cantidad:", 
            minvalue=1, 
            maxvalue=producto['stock']
        )
        if not cantidad:
            return
        
        for item in self.carrito:
            if item['producto_id'] == producto_id:
                messagebox.showwarning("Ya agregado", "Este producto ya está en el carrito.\nElimínalo y vuelve a agregar si deseas cambiar la cantidad.")
                return
        
        subtotal = cantidad * producto['precio_venta']
        self.carrito.append({
            'producto_id': producto_id,
            'nombre': producto['nombre'],
            'cantidad': cantidad,
            'precio_unitario': producto['precio_venta'],
            'subtotal': subtotal
        })
        self.actualizar_carrito()
        messagebox.showinfo("Agregado", f"Se agregó {cantidad} unidad(es) de '{producto['nombre']}' al carrito.")
    
    def actualizar_carrito(self):
        for item in self.tree_carrito.get_children():
            self.tree_carrito.delete(item)
        
        total = 0
        for item in self.carrito:
            self.tree_carrito.insert('', 'end', values=(
                item['nombre'], item['cantidad'], 
                f"S/ {item['precio_unitario']:.2f}", 
                f"S/ {item['subtotal']:.2f}"
            ))
            total += item['subtotal']
        
        self.lbl_total.config(text=f"S/ {total:.2f}")
    
    def eliminar_item_carrito(self):
        seleccion = self.tree_carrito.selection()
        if not seleccion:
            messagebox.showwarning("Seleccione", "Seleccione un item del carrito para eliminar.")
            return
        index = self.tree_carrito.index(seleccion[0])
        self.carrito.pop(index)
        self.actualizar_carrito()
    
    def limpiar_carrito(self):
        self.carrito = []
        self.cliente_seleccionado = None
        self.cliente_nombre = "Cliente General"
        self.lbl_cliente.config(text=self.cliente_nombre)
        self.actualizar_carrito()
    
    def seleccionar_cliente(self):
        win = tk.Toplevel(self.root)
        win.title("Seleccionar Cliente")
        win.geometry("450x350")
        win.transient(self.root)
        win.grab_set()
        
        ttk.Label(win, text="Clientes registrados:", font=('Segoe UI', 11, 'bold')).pack(pady=5)
        
        frame_list = ttk.Frame(win)
        frame_list.pack(fill='both', expand=True, padx=10, pady=5)
        
        listbox = tk.Listbox(frame_list, width=50, font=('Segoe UI', 10))
        listbox.pack(side=tk.LEFT, fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_list, orient="vertical", command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        listbox.configure(yscrollcommand=scrollbar.set)
        
        clientes = Cliente.obtener_todos()
        for c in clientes:
            listbox.insert('end', f"{c['dni']} - {c['nombre']}")
        
        def seleccionar():
            sel = listbox.curselection()
            if sel:
                self.cliente_seleccionado = clientes[sel[0]]['id']
                self.cliente_nombre = clientes[sel[0]]['nombre']
                self.lbl_cliente.config(text=self.cliente_nombre)
                win.destroy()
            else:
                messagebox.showwarning("Seleccione", "Elija un cliente de la lista.")
        
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="✅ Seleccionar", command=seleccionar).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="➕ Nuevo Cliente", command=lambda: [win.destroy(), self.abrir_nuevo_cliente()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Cancelar", command=win.destroy).pack(side=tk.LEFT, padx=5)
    
    def abrir_nuevo_cliente(self):
        self.notebook.select(self.tab_clientes)
    
    def procesar_venta(self):
        if not self.carrito:
            messagebox.showwarning("Carrito vacío", "Agregue productos al carrito antes de procesar.")
            return
        
        win = tk.Toplevel(self.root)
        win.title("Confirmar Venta")
        win.geometry("400x280")
        win.transient(self.root)
        win.grab_set()
        
        ttk.Label(win, text="💰 Confirmar Venta", font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        total = sum(item['subtotal'] for item in self.carrito)
        ttk.Label(win, text=f"Total: {formatear_moneda(total)}", font=('Segoe UI', 16), foreground="#c62828").pack(pady=5)
        
        ttk.Label(win, text="Método de Pago:").pack(pady=5)
        metodo_var = tk.StringVar(value="Efectivo")
        combo = ttk.Combobox(win, textvariable=metodo_var, values=["Efectivo", "Tarjeta", "Yape", "Plin", "Transferencia"], state="readonly", width=25)
        combo.pack(pady=5)
        
        ttk.Label(win, text=f"Vendedor: {self.usuario_actual}", font=('Segoe UI', 9, 'italic'), foreground="gray").pack(pady=2)
        
        def confirmar():
            metodo = metodo_var.get()
            if not metodo:
                messagebox.showwarning("Falta dato", "Seleccione un método de pago.")
                return
            
            try:
                Venta.crear(
                    cliente_id=self.cliente_seleccionado,
                    total=total,
                    metodo_pago=metodo,
                    items=self.carrito,
                    usuario=self.usuario_actual
                )
                win.destroy()
                messagebox.showinfo("¡Venta Exitosa!", 
                    f"Venta procesada correctamente.\n\nTotal: {formatear_moneda(total)}\nMétodo: {metodo}\nCliente: {self.cliente_nombre}\nVendedor: {self.usuario_actual}")
                self.limpiar_carrito()
                self.buscar_productos_venta()
                self.actualizar_barra_estado()
            except Exception as e:
                win.destroy()
                messagebox.showerror("Error en Venta", f"No se pudo procesar la venta:\n\n{str(e)}")
        
        ttk.Button(win, text="✅ Confirmar Venta", command=confirmar).pack(pady=15)
        ttk.Button(win, text="❌ Cancelar", command=win.destroy).pack(pady=5)
    
    # ==================== PRODUCTOS ====================
    def setup_productos(self):
        form_frame = ttk.LabelFrame(self.tab_productos, text=" Gestión de Producto ")
        form_frame.pack(fill='x', padx=5, pady=5)
        
        campos = [
            ('Código:', 'codigo'),
            ('Nombre:', 'nombre'),
            ('Descripción:', 'descripcion'),
            ('Categoría:', 'categoria'),
            ('Precio Compra:', 'p_compra'),
            ('Precio Venta:', 'p_venta'),
            ('Stock Inicial:', 'stock'),
            ('Stock Mínimo:', 'stock_min'),
            ('Vencimiento (YYYY-MM-DD):', 'vencimiento'),
            ('Laboratorio:', 'laboratorio')
        ]
        
        self.entries_prod = {}
        for i, (label, key) in enumerate(campos):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(form_frame, text=label).grid(row=row, column=col, padx=5, pady=3, sticky='e')
            entry = ttk.Entry(form_frame, width=35)
            entry.grid(row=row, column=col+1, padx=5, pady=3, sticky='w')
            self.entries_prod[key] = entry
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        self.btn_guardar_prod = ttk.Button(btn_frame, text="💾 Guardar Nuevo", command=self.guardar_producto)
        self.btn_guardar_prod.pack(side=tk.LEFT, padx=5)
        
        self.btn_actualizar_prod = ttk.Button(btn_frame, text="✏️ Actualizar", command=self.actualizar_producto, state='disabled')
        self.btn_actualizar_prod.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="🔄 Limpiar", command=self.limpiar_form_producto).pack(side=tk.LEFT, padx=5)
        
        # Botón exportar Excel
        if EXPORT_OK:
            ttk.Button(btn_frame, text="📊 Exportar a Excel", command=self.exportar_inventario_excel).pack(side=tk.LEFT, padx=20)
        
        list_frame = ttk.LabelFrame(self.tab_productos, text=" Inventario ")
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill='x', padx=5, pady=5)
        self.entry_buscar_prod = ttk.Entry(search_frame, width=40)
        self.entry_buscar_prod.pack(side=tk.LEFT, fill='x', expand=True)
        ttk.Button(search_frame, text="🔍 Buscar", command=self.buscar_productos_tabla).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔄 Mostrar Todos", command=self.cargar_productos).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🗑️ Eliminar Seleccionado", command=self.eliminar_producto).pack(side=tk.LEFT, padx=5)
        
        columns = ('id', 'codigo', 'nombre', 'categoria', 'precio', 'stock', 'minimo', 'vencimiento')
        self.tree_productos = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        self.tree_productos.heading('id', text='ID')
        self.tree_productos.heading('codigo', text='Código')
        self.tree_productos.heading('nombre', text='Nombre')
        self.tree_productos.heading('categoria', text='Categoría')
        self.tree_productos.heading('precio', text='P. Venta')
        self.tree_productos.heading('stock', text='Stock')
        self.tree_productos.heading('minimo', text='Mínimo')
        self.tree_productos.heading('vencimiento', text='Vencimiento')
        self.tree_productos.column('id', width=50, anchor='center')
        self.tree_productos.column('codigo', width=80)
        self.tree_productos.column('nombre', width=200)
        self.tree_productos.column('categoria', width=120)
        self.tree_productos.column('precio', width=90, anchor='e')
        self.tree_productos.column('stock', width=70, anchor='center')
        self.tree_productos.column('minimo', width=70, anchor='center')
        self.tree_productos.column('vencimiento', width=100, anchor='center')
        self.tree_productos.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.tree_productos, orient="vertical", command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        self.tree_productos.bind('<Double-1>', self.cargar_producto_a_editar)
        self.cargar_productos()
    
    def guardar_producto(self):
        try:
            codigo = validar_obligatorio(self.entries_prod['codigo'].get(), "Código")
            nombre = validar_obligatorio(self.entries_prod['nombre'].get(), "Nombre")
            categoria = validar_obligatorio(self.entries_prod['categoria'].get(), "Categoría")
            p_compra = validar_precio(self.entries_prod['p_compra'].get(), "Precio Compra")
            p_venta = validar_precio(self.entries_prod['p_venta'].get(), "Precio Venta")
            stock = validar_stock(self.entries_prod['stock'].get(), "Stock")
            stock_min = validar_stock(self.entries_prod['stock_min'].get(), "Stock Mínimo")
            vencimiento = self.entries_prod['vencimiento'].get().strip()
            laboratorio = self.entries_prod['laboratorio'].get().strip()
            
            if vencimiento:
                validar_fecha(vencimiento)
            
            if p_venta <= p_compra:
                raise ValueError("El precio de venta debe ser mayor al precio de compra.")
            
            Producto.crear(
                codigo=codigo, nombre=nombre, descripcion=self.entries_prod['descripcion'].get().strip(),
                categoria=categoria, precio_compra=p_compra, precio_venta=p_venta,
                stock=stock, stock_minimo=stock_min,
                fecha_vencimiento=vencimiento or None, laboratorio=laboratorio
            )
            messagebox.showinfo("Éxito", "Producto guardado correctamente.")
            self.cargar_productos()
            self.limpiar_form_producto()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def cargar_producto_a_editar(self, event=None):
        seleccion = self.tree_productos.selection()
        if not seleccion:
            return
        
        item = self.tree_productos.item(seleccion[0])
        producto_id = item['values'][0]
        producto = Producto.obtener_por_id(producto_id)
        
        if not producto:
            return
        
        self.producto_editando = producto_id
        
        self.entries_prod['codigo'].delete(0, 'end')
        self.entries_prod['codigo'].insert(0, producto['codigo'])
        self.entries_prod['nombre'].delete(0, 'end')
        self.entries_prod['nombre'].insert(0, producto['nombre'])
        self.entries_prod['descripcion'].delete(0, 'end')
        self.entries_prod['descripcion'].insert(0, producto['descripcion'] or '')
        self.entries_prod['categoria'].delete(0, 'end')
        self.entries_prod['categoria'].insert(0, producto['categoria'] or '')
        self.entries_prod['p_compra'].delete(0, 'end')
        self.entries_prod['p_compra'].insert(0, str(producto['precio_compra']))
        self.entries_prod['p_venta'].delete(0, 'end')
        self.entries_prod['p_venta'].insert(0, str(producto['precio_venta']))
        self.entries_prod['stock'].delete(0, 'end')
        self.entries_prod['stock'].insert(0, str(producto['stock']))
        self.entries_prod['stock_min'].delete(0, 'end')
        self.entries_prod['stock_min'].insert(0, str(producto['stock_minimo']))
        self.entries_prod['vencimiento'].delete(0, 'end')
        self.entries_prod['vencimiento'].insert(0, producto['fecha_vencimiento'] or '')
        self.entries_prod['laboratorio'].delete(0, 'end')
        self.entries_prod['laboratorio'].insert(0, producto['laboratorio'] or '')
        
        self.btn_guardar_prod.config(state='disabled')
        self.btn_actualizar_prod.config(state='normal')
        self.entries_prod['stock'].config(state='disabled')
    
    def actualizar_producto(self):
        if not self.producto_editando:
            return
        
        try:
            codigo = validar_obligatorio(self.entries_prod['codigo'].get(), "Código")
            nombre = validar_obligatorio(self.entries_prod['nombre'].get(), "Nombre")
            categoria = validar_obligatorio(self.entries_prod['categoria'].get(), "Categoría")
            p_compra = validar_precio(self.entries_prod['p_compra'].get(), "Precio Compra")
            p_venta = validar_precio(self.entries_prod['p_venta'].get(), "Precio Venta")
            stock_min = validar_stock(self.entries_prod['stock_min'].get(), "Stock Mínimo")
            vencimiento = self.entries_prod['vencimiento'].get().strip()
            laboratorio = self.entries_prod['laboratorio'].get().strip()
            
            if vencimiento:
                validar_fecha(vencimiento)
            
            if p_venta <= p_compra:
                raise ValueError("El precio de venta debe ser mayor al precio de compra.")
            
            prod_actual = Producto.obtener_por_id(self.producto_editando)
            
            if prod_actual is None:
                raise ValueError("Producto no encontrado.")
            
            Producto.actualizar(
                self.producto_editando, codigo, nombre,
                self.entries_prod['descripcion'].get().strip(),
                categoria, p_compra, p_venta,
                prod_actual['stock'], stock_min,
                vencimiento or None, laboratorio
            )
            messagebox.showinfo("Éxito", "Producto actualizado correctamente.")
            self.cargar_productos()
            self.limpiar_form_producto()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def eliminar_producto(self):
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Seleccione", "Seleccione un producto para eliminar.")
            return
        
        item = self.tree_productos.item(seleccion[0])
        producto_id = item['values'][0]
        nombre = item['values'][2]
        
        if not confirmar_eliminar(self.root, f"¿Eliminar el producto '{nombre}'?\n\nEsta acción no se puede deshacer."):
            return
        
        try:
            Producto.eliminar(producto_id)
            messagebox.showinfo("Eliminado", "Producto eliminado correctamente.")
            self.cargar_productos()
            self.limpiar_form_producto()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def limpiar_form_producto(self):
        self.producto_editando = None
        for e in self.entries_prod.values():
            e.delete(0, 'end')
            e.config(state='normal')
        self.btn_guardar_prod.config(state='normal')
        self.btn_actualizar_prod.config(state='disabled')
    
    def buscar_productos_tabla(self):
        termino = self.entry_buscar_prod.get().strip()
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        
        productos = Producto.buscar(termino) if termino else Producto.obtener_todos()
        for p in productos:
            tag = 'bajo' if p['stock'] <= p['stock_minimo'] else ''
            self.tree_productos.insert('', 'end', values=(
                p['id'], p['codigo'], p['nombre'], p['categoria'],
                f"S/ {p['precio_venta']:.2f}", p['stock'], p['stock_minimo'], p['fecha_vencimiento']
            ), tags=(tag,))
        self.tree_productos.tag_configure('bajo', background='#ffcccc', foreground='#b71c1c')
    
    def cargar_productos(self):
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        
        productos = Producto.obtener_todos()
        for p in productos:
            tag = 'bajo' if p['stock'] <= p['stock_minimo'] else ''
            self.tree_productos.insert('', 'end', values=(
                p['id'], p['codigo'], p['nombre'], p['categoria'],
                f"S/ {p['precio_venta']:.2f}", p['stock'], p['stock_minimo'], p['fecha_vencimiento']
            ), tags=(tag,))
        self.tree_productos.tag_configure('bajo', background='#ffcccc', foreground='#b71c1c')
    
    def exportar_inventario_excel(self):
        if not EXPORT_OK:
            messagebox.showerror("Error", "Instale openpyxl: pip install openpyxl")
            return
        
        ruta = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"Inventario_Botica_{date.today().strftime('%Y%m%d')}"
        )
        if not ruta:
            return
        
        try:
            exportar_inventario_excel(ruta)
            messagebox.showinfo("Éxito", f"Inventario exportado a:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    # ==================== CLIENTES ====================
    def setup_clientes(self):
        form_frame = ttk.LabelFrame(self.tab_clientes, text=" Gestión de Cliente ")
        form_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(form_frame, text="DNI:").grid(row=0, column=0, padx=5, pady=3, sticky='e')
        self.entry_dni = ttk.Entry(form_frame, width=20)
        self.entry_dni.grid(row=0, column=1, padx=5, pady=3, sticky='w')
        
        ttk.Label(form_frame, text="Nombre:").grid(row=0, column=2, padx=5, pady=3, sticky='e')
        self.entry_nombre_cli = ttk.Entry(form_frame, width=35)
        self.entry_nombre_cli.grid(row=0, column=3, padx=5, pady=3, sticky='w')
        
        ttk.Label(form_frame, text="Teléfono:").grid(row=1, column=0, padx=5, pady=3, sticky='e')
        self.entry_tel = ttk.Entry(form_frame, width=20)
        self.entry_tel.grid(row=1, column=1, padx=5, pady=3, sticky='w')
        
        ttk.Label(form_frame, text="Email:").grid(row=1, column=2, padx=5, pady=3, sticky='e')
        self.entry_email = ttk.Entry(form_frame, width=35)
        self.entry_email.grid(row=1, column=3, padx=5, pady=3, sticky='w')
        
        ttk.Label(form_frame, text="Dirección:").grid(row=2, column=0, padx=5, pady=3, sticky='e')
        self.entry_dir = ttk.Entry(form_frame, width=60)
        self.entry_dir.grid(row=2, column=1, columnspan=3, padx=5, pady=3, sticky='we')
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)
        
        self.btn_guardar_cli = ttk.Button(btn_frame, text="💾 Guardar Nuevo", command=self.guardar_cliente)
        self.btn_guardar_cli.pack(side=tk.LEFT, padx=5)
        
        self.btn_actualizar_cli = ttk.Button(btn_frame, text="✏️ Actualizar", command=self.actualizar_cliente, state='disabled')
        self.btn_actualizar_cli.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="🔄 Limpiar", command=self.limpiar_form_cliente).pack(side=tk.LEFT, padx=5)
        
        list_frame = ttk.LabelFrame(self.tab_clientes, text=" Clientes Registrados ")
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tree_clientes = ttk.Treeview(list_frame, columns=('id', 'dni', 'nombre', 'telefono', 'email'), show='headings', height=18)
        self.tree_clientes.heading('id', text='ID')
        self.tree_clientes.heading('dni', text='DNI')
        self.tree_clientes.heading('nombre', text='Nombre')
        self.tree_clientes.heading('telefono', text='Teléfono')
        self.tree_clientes.heading('email', text='Email')
        self.tree_clientes.column('id', width=50, anchor='center')
        self.tree_clientes.column('dni', width=100, anchor='center')
        self.tree_clientes.column('nombre', width=250)
        self.tree_clientes.column('telefono', width=120, anchor='center')
        self.tree_clientes.column('email', width=200)
        self.tree_clientes.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.tree_clientes, orient="vertical", command=self.tree_clientes.yview)
        self.tree_clientes.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        ttk.Button(list_frame, text="🗑️ Eliminar Seleccionado", command=self.eliminar_cliente).pack(pady=5)
        
        self.tree_clientes.bind('<Double-1>', self.cargar_cliente_a_editar)
        self.cargar_clientes()
    
    def guardar_cliente(self):
        try:
            dni = validar_obligatorio(self.entry_dni.get(), "DNI")
            validar_dni(dni)
            nombre = validar_obligatorio(self.entry_nombre_cli.get(), "Nombre")
            telefono = self.entry_tel.get().strip()
            email = self.entry_email.get().strip()
            validar_email(email)
            direccion = self.entry_dir.get().strip()
            
            Cliente.crear(dni=dni, nombre=nombre, telefono=telefono, email=email, direccion=direccion)
            messagebox.showinfo("Éxito", "Cliente registrado correctamente.")
            self.cargar_clientes()
            self.limpiar_form_cliente()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def cargar_cliente_a_editar(self, event=None):
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        cliente = Cliente.obtener_por_id(cliente_id)
        
        if not cliente:
            return
        
        self.cliente_editando = cliente_id
        
        self.entry_dni.delete(0, 'end')
        self.entry_dni.insert(0, cliente['dni'] or '')
        self.entry_nombre_cli.delete(0, 'end')
        self.entry_nombre_cli.insert(0, cliente['nombre'])
        self.entry_tel.delete(0, 'end')
        self.entry_tel.insert(0, cliente['telefono'] or '')
        self.entry_email.delete(0, 'end')
        self.entry_email.insert(0, cliente['email'] or '')
        self.entry_dir.delete(0, 'end')
        self.entry_dir.insert(0, cliente['direccion'] or '')
        
        self.btn_guardar_cli.config(state='disabled')
        self.btn_actualizar_cli.config(state='normal')
    
    def actualizar_cliente(self):
        if not self.cliente_editando:
            return
        
        try:
            dni = validar_obligatorio(self.entry_dni.get(), "DNI")
            validar_dni(dni)
            nombre = validar_obligatorio(self.entry_nombre_cli.get(), "Nombre")
            telefono = self.entry_tel.get().strip()
            email = self.entry_email.get().strip()
            validar_email(email)
            direccion = self.entry_dir.get().strip()
            
            Cliente.actualizar(self.cliente_editando, dni, nombre, telefono, email, direccion)
            messagebox.showinfo("Éxito", "Cliente actualizado correctamente.")
            self.cargar_clientes()
            self.limpiar_form_cliente()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def eliminar_cliente(self):
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            messagebox.showwarning("Seleccione", "Seleccione un cliente para eliminar.")
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        nombre = item['values'][2]
        
        if not confirmar_eliminar(self.root, f"¿Eliminar al cliente '{nombre}'?\n\nEsta acción no se puede deshacer."):
            return
        
        try:
            Cliente.eliminar(cliente_id)
            messagebox.showinfo("Eliminado", "Cliente eliminado correctamente.")
            self.cargar_clientes()
            self.limpiar_form_cliente()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def limpiar_form_cliente(self):
        self.cliente_editando = None
        self.entry_dni.delete(0, 'end')
        self.entry_nombre_cli.delete(0, 'end')
        self.entry_tel.delete(0, 'end')
        self.entry_email.delete(0, 'end')
        self.entry_dir.delete(0, 'end')
        self.btn_guardar_cli.config(state='normal')
        self.btn_actualizar_cli.config(state='disabled')
    
    def cargar_clientes(self):
        for item in self.tree_clientes.get_children():
            self.tree_clientes.delete(item)
        for c in Cliente.obtener_todos():
            self.tree_clientes.insert('', 'end', values=(c['id'], c['dni'], c['nombre'], c['telefono'], c['email']))
    
    # ==================== REPORTES ====================
    def setup_reportes(self):
        filtros = ttk.Frame(self.tab_reportes)
        filtros.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filtros, text="Desde:").pack(side=tk.LEFT, padx=5)
        self.entry_fecha_ini = ttk.Entry(filtros, width=12)
        self.entry_fecha_ini.insert(0, date.today().strftime("%Y-%m-%d"))
        self.entry_fecha_ini.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(filtros, text="Hasta:").pack(side=tk.LEFT, padx=5)
        self.entry_fecha_fin = ttk.Entry(filtros, width=12)
        self.entry_fecha_fin.insert(0, date.today().strftime("%Y-%m-%d"))
        self.entry_fecha_fin.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filtros, text="📋 Consultar Ventas", command=self.consultar_ventas).pack(side=tk.LEFT, padx=10)
        ttk.Button(filtros, text="⚠️ Stock Bajo", command=self.mostrar_stock_bajo).pack(side=tk.LEFT, padx=5)
        
        if EXPORT_OK:
            ttk.Button(filtros, text="📊 Exportar a Excel", command=self.exportar_ventas_excel).pack(side=tk.LEFT, padx=5)
            ttk.Button(filtros, text="📄 Exportar a PDF", command=self.exportar_ventas_pdf).pack(side=tk.LEFT, padx=5)
        
        columns = ('id', 'fecha', 'cliente', 'total', 'metodo', 'usuario')
        self.tree_ventas = ttk.Treeview(self.tab_reportes, columns=columns, show='headings', height=15)
        self.tree_ventas.heading('id', text='ID')
        self.tree_ventas.heading('fecha', text='Fecha')
        self.tree_ventas.heading('cliente', text='Cliente')
        self.tree_ventas.heading('total', text='Total')
        self.tree_ventas.heading('metodo', text='Método Pago')
        self.tree_ventas.heading('usuario', text='Vendedor')
        self.tree_ventas.column('id', width=60, anchor='center')
        self.tree_ventas.column('fecha', width=150)
        self.tree_ventas.column('cliente', width=180)
        self.tree_ventas.column('total', width=100, anchor='e')
        self.tree_ventas.column('metodo', width=120, anchor='center')
        self.tree_ventas.column('usuario', width=100, anchor='center')
        self.tree_ventas.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.tree_ventas, orient="vertical", command=self.tree_ventas.yview)
        self.tree_ventas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        self.tree_ventas.bind('<Double-1>', self.ver_detalle_venta)
        
        ttk.Button(self.tab_reportes, text="❌ Anular Venta Seleccionada", command=self.anular_venta).pack(pady=5)
        
        self.lbl_resumen = ttk.Label(self.tab_reportes, text="Total del período: S/ 0.00 | Ventas: 0", font=('Segoe UI', 12, 'bold'))
        self.lbl_resumen.pack(pady=5)
    
    def consultar_ventas(self):
        for item in self.tree_ventas.get_children():
            self.tree_ventas.delete(item)
        
        try:
            ventas = Venta.obtener_ventas_por_fecha(
                self.entry_fecha_ini.get(),
                self.entry_fecha_fin.get()
            )
        except Exception as e:
            messagebox.showerror("Error", f"Verifique el formato de fecha (YYYY-MM-DD):\n{str(e)}")
            return
        
        total = 0
        cantidad = 0
        for v in ventas:
            cliente = v['cliente_nombre'] or "General"
            self.tree_ventas.insert('', 'end', values=(
                v['id'], v['fecha'], cliente, f"S/ {v['total']:.2f}", v['metodo_pago'], v['usuario'] or 'Admin'
            ))
            total += v['total']
            cantidad += 1
        
        self.lbl_resumen.config(text=f"Total del período: {formatear_moneda(total)} | Ventas: {cantidad}")
    
    def exportar_ventas_excel(self):
        if not EXPORT_OK:
            messagebox.showerror("Error", "Instale openpyxl: pip install openpyxl")
            return
        
        ruta = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"Ventas_{self.entry_fecha_ini.get()}_{self.entry_fecha_fin.get()}"
        )
        if not ruta:
            return
        
        try:
            exportar_ventas_excel(self.entry_fecha_ini.get(), self.entry_fecha_fin.get(), ruta)
            messagebox.showinfo("Éxito", f"Ventas exportadas a Excel:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def exportar_ventas_pdf(self):
        if not EXPORT_OK:
            messagebox.showerror("Error", "Instale reportlab: pip install reportlab")
            return
        
        ruta = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"Reporte_Ventas_{self.entry_fecha_ini.get()}_{self.entry_fecha_fin.get()}"
        )
        if not ruta:
            return
        
        try:
            exportar_ventas_pdf(self.entry_fecha_ini.get(), self.entry_fecha_fin.get(), ruta)
            messagebox.showinfo("Éxito", f"Reporte PDF generado:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def anular_venta(self):
        seleccion = self.tree_ventas.selection()
        if not seleccion:
            messagebox.showwarning("Seleccione", "Seleccione una venta para anular.")
            return
        
        item = self.tree_ventas.item(seleccion[0])
        venta_id = item['values'][0]
        fecha = item['values'][1]
        total = item['values'][3]
        
        if not confirmar_eliminar(self.root, f"¿Anular la venta #{venta_id}?\n\nFecha: {fecha}\nTotal: {total}\n\n⚠️ Esto devolverá el stock al inventario."):
            return
        
        try:
            Venta.anular(venta_id)
            messagebox.showinfo("Anulado", f"Venta #{venta_id} anulada correctamente.\nEl stock fue restaurado.")
            self.consultar_ventas()
            self.actualizar_barra_estado()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def mostrar_stock_bajo(self):
        win = tk.Toplevel(self.root)
        win.title("⚠️ Productos con Stock Bajo")
        win.geometry("650x400")
        win.transient(self.root)
        
        tree = ttk.Treeview(win, columns=('codigo', 'nombre', 'stock', 'minimo', 'faltante'), show='headings', height=15)
        tree.heading('codigo', text='Código')
        tree.heading('nombre', text='Nombre')
        tree.heading('stock', text='Stock Actual')
        tree.heading('minimo', text='Mínimo')
        tree.heading('faltante', text='Faltante')
        tree.column('codigo', width=80, anchor='center')
        tree.column('nombre', width=250)
        tree.column('stock', width=100, anchor='center')
        tree.column('minimo', width=100, anchor='center')
        tree.column('faltante', width=100, anchor='center')
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        for p in Producto.obtener_stock_bajo():
            faltante = p['stock_minimo'] - p['stock']
            tree.insert('', 'end', values=(p['codigo'], p['nombre'], p['stock'], p['stock_minimo'], faltante))
        
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=5)
    
    def ver_detalle_venta(self, event):
        seleccion = self.tree_ventas.selection()
        if not seleccion:
            return
        
        venta_id = self.tree_ventas.item(seleccion[0])['values'][0]
        detalle = Venta.obtener_detalle(venta_id)
        
        win = tk.Toplevel(self.root)
        win.title(f"Detalle de Venta #{venta_id}")
        win.geometry("550x350")
        win.transient(self.root)
        
        tree = ttk.Treeview(win, columns=('producto', 'cantidad', 'precio', 'subtotal'), show='headings', height=12)
        tree.heading('producto', text='Producto')
        tree.heading('cantidad', text='Cant.')
        tree.heading('precio', text='P. Unit')
        tree.heading('subtotal', text='Subtotal')
        tree.column('producto', width=250)
        tree.column('cantidad', width=60, anchor='center')
        tree.column('precio', width=100, anchor='e')
        tree.column('subtotal', width=100, anchor='e')
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        total = 0
        for d in detalle:
            tree.insert('', 'end', values=(
                d['producto_nombre'], d['cantidad'],
                f"S/ {d['precio_unitario']:.2f}", f"S/ {d['subtotal']:.2f}"
            ))
            total += d['subtotal']
        
        ttk.Label(win, text=f"Total de la venta: {formatear_moneda(total)}", font=('Segoe UI', 12, 'bold')).pack(pady=5)
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=5)
    
    # ==================== ESTADÍSTICAS / GRÁFICOS ====================
    def setup_estadisticas(self):
        if not CHARTS_OK:
            ttk.Label(self.tab_stats, text="⚠️ Instale matplotlib para ver gráficos:\npip install matplotlib", 
                     font=('Segoe UI', 14), foreground="red").pack(expand=True)
            return
        
        # Frame de botones
        btn_frame = ttk.Frame(self.tab_stats)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(btn_frame, text="📈 Seleccione un gráfico:", font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Ventas por Mes", command=lambda: grafico_ventas_por_mes(self.canvas_frame)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Top Productos", command=lambda: grafico_top_productos(self.canvas_frame)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Método de Pago", command=lambda: grafico_metodo_pago(self.canvas_frame)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Inventario Valorizado", command=lambda: grafico_inventario_valorizado(self.canvas_frame)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Ventas por Usuario", command=lambda: grafico_ventas_por_usuario(self.canvas_frame)).pack(side=tk.LEFT, padx=3)
        
        # Frame del canvas
        self.canvas_frame = ttk.Frame(self.tab_stats)
        self.canvas_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Mostrar gráfico por defecto
        grafico_ventas_por_mes(self.canvas_frame)
    
    def mostrar_acerca(self):
        messagebox.showinfo("Acerca de", 
            "💊 Sistema de Ventas Botica v3.0\n\n"
            "✅ CRUD completo de Productos y Clientes\n"
            "✅ Punto de Venta con transacciones seguras\n"
            "✅ Reportes con anulación de ventas\n"
            "✅ Gráficos estadísticos en tiempo real\n"
            "✅ Exportación a Excel y PDF\n"
            "✅ Pantalla completa (F11)\n"
            "✅ Auditoría por usuario/vendedor\n\n"
            "Desarrollado en Python + Tkinter + SQLite + Matplotlib + OpenPyXL + ReportLab")