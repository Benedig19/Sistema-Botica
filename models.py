from database import get_connection
from datetime import datetime

class Producto:
    @staticmethod
    def crear(codigo, nombre, descripcion, categoria, precio_compra, precio_venta, 
              stock, stock_minimo, fecha_vencimiento, laboratorio):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO productos (codigo, nombre, descripcion, categoria, 
                precio_compra, precio_venta, stock, stock_minimo, fecha_vencimiento, laboratorio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (codigo, nombre, descripcion, categoria, precio_compra, precio_venta,
                  stock, stock_minimo, fecha_vencimiento, laboratorio))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def obtener_todos():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE activo = 1 ORDER BY nombre")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def buscar(termino):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM productos 
            WHERE activo = 1 AND (nombre LIKE ? OR codigo LIKE ? OR categoria LIKE ?)
            ORDER BY nombre
        ''', (f'%{termino}%', f'%{termino}%', f'%{termino}%'))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def obtener_por_id(id_producto):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = ?", (id_producto,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    @staticmethod
    def actualizar(id_producto, codigo, nombre, descripcion, categoria, precio_compra, 
                   precio_venta, stock, stock_minimo, fecha_vencimiento, laboratorio):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE productos SET
                    codigo = ?, nombre = ?, descripcion = ?, categoria = ?,
                    precio_compra = ?, precio_venta = ?, stock = ?, stock_minimo = ?,
                    fecha_vencimiento = ?, laboratorio = ?
                WHERE id = ?
            ''', (codigo, nombre, descripcion, categoria, precio_compra, precio_venta,
                  stock, stock_minimo, fecha_vencimiento, laboratorio, id_producto))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def eliminar(id_producto):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) as total FROM detalle_ventas WHERE producto_id = ?
            ''', (id_producto,))
            if cursor.fetchone()['total'] > 0:
                raise ValueError("No se puede eliminar: este producto tiene ventas registradas.")
            
            cursor.execute("UPDATE productos SET activo = 0 WHERE id = ?", (id_producto,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def actualizar_stock(id_producto, cantidad, conn_externa=None):
        if conn_externa:
            cursor = conn_externa.cursor()
            cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, id_producto))
        else:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, id_producto))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    @staticmethod
    def obtener_stock_bajo():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE stock <= stock_minimo AND activo = 1")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class Cliente:
    @staticmethod
    def crear(dni, nombre, telefono, email, direccion):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO clientes (dni, nombre, telefono, email, direccion)
                VALUES (?, ?, ?, ?, ?)
            ''', (dni, nombre, telefono, email, direccion))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def obtener_todos():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes ORDER BY nombre")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def obtener_por_id(id_cliente):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE id = ?", (id_cliente,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    @staticmethod
    def actualizar(id_cliente, dni, nombre, telefono, email, direccion):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE clientes SET
                    dni = ?, nombre = ?, telefono = ?, email = ?, direccion = ?
                WHERE id = ?
            ''', (dni, nombre, telefono, email, direccion, id_cliente))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def eliminar(id_cliente):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) as total FROM ventas WHERE cliente_id = ?
            ''', (id_cliente,))
            if cursor.fetchone()['total'] > 0:
                raise ValueError("No se puede eliminar: este cliente tiene ventas registradas.")
            
            cursor.execute("DELETE FROM clientes WHERE id = ?", (id_cliente,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()


class Venta:
    @staticmethod
    def crear(cliente_id, total, metodo_pago, items, usuario="Admin"):
        """
        items: lista de diccionarios {producto_id, cantidad, precio_unitario, subtotal}
        usuario: nombre del vendedor que realiza la venta
        """
        conn = get_connection()
        cursor = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT INTO ventas (fecha, cliente_id, total, metodo_pago, usuario)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha, cliente_id, total, metodo_pago, usuario))
            venta_id = cursor.lastrowid
            
            for item in items:
                cursor.execute("SELECT stock FROM productos WHERE id = ?", (item['producto_id'],))
                stock_actual = cursor.fetchone()['stock']
                if stock_actual < item['cantidad']:
                    raise ValueError(f"Stock insuficiente para el producto ID {item['producto_id']}. Disponible: {stock_actual}")
                
                cursor.execute('''
                    INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                ''', (venta_id, item['producto_id'], item['cantidad'], 
                      item['precio_unitario'], item['subtotal']))
                
                Producto.actualizar_stock(item['producto_id'], item['cantidad'], conn_externa=conn)
            
            conn.commit()
            return venta_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def anular(id_venta):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT producto_id, cantidad FROM detalle_ventas WHERE venta_id = ?
            ''', (id_venta,))
            detalles = cursor.fetchall()
            
            for d in detalles:
                cursor.execute('''
                    UPDATE productos SET stock = stock + ? WHERE id = ?
                ''', (d['cantidad'], d['producto_id']))
            
            cursor.execute("DELETE FROM detalle_ventas WHERE venta_id = ?", (id_venta,))
            cursor.execute("DELETE FROM ventas WHERE id = ?", (id_venta,))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def obtener_ventas_por_fecha(fecha_inicio, fecha_fin):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.*, c.nombre as cliente_nombre 
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE DATE(v.fecha) BETWEEN ? AND ?
            ORDER BY v.fecha DESC
        ''', (fecha_inicio, fecha_fin))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def obtener_detalle(venta_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*, p.nombre as producto_nombre 
            FROM detalle_ventas d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.venta_id = ?
        ''', (venta_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ===== ESTADÍSTICAS NUEVAS =====
    @staticmethod
    def obtener_resumen_hoy():
        conn = get_connection()
        cursor = conn.cursor()
        hoy = datetime.now().strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT COUNT(*) as cantidad, COALESCE(SUM(total), 0) as total
            FROM ventas
            WHERE DATE(fecha) = ?
        ''', (hoy,))
        row = cursor.fetchone()
        conn.close()
        return dict(row)
    
    @staticmethod
    def obtener_resumen_mes():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as cantidad, COALESCE(SUM(total), 0) as total
            FROM ventas
            WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
        ''')
        row = cursor.fetchone()
        conn.close()
        return dict(row)