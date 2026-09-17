from database import init_db
from views import BoticaApp
import tkinter as tk

if __name__ == "__main__":
    # Inicializar base de datos
    init_db()
    
    # Iniciar interfaz
    root = tk.Tk()
    app = BoticaApp(root)
    root.mainloop()