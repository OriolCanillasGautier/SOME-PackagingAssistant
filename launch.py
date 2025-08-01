#!/usr/bin/env python3
"""
PackAssist Launcher GUI - Interfície gràfica per iniciar l'aplicació
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import threading

class PackAssistLauncher:
    """Launcher GUI per PackAssist"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PackAssist - Empaquetament Intel·ligent")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Configurar icona i estil
        self.setup_styles()
        self.create_widgets()
        self.check_environment()
        
    def setup_styles(self):
        """Configura l'estil de la interfície"""
        style = ttk.Style()
        
        # Configurar tema modern
        try:
            style.theme_use('clam')
        except:
            pass
            
        # Colors moderns
        self.root.configure(bg='#f0f0f0')
        
        # Estils personalitzats
        style.configure('Title.TLabel', 
                       font=('Arial', 16, 'bold'),
                       background='#f0f0f0',
                       foreground='#2c3e50')
        
        style.configure('Subtitle.TLabel',
                       font=('Arial', 10),
                       background='#f0f0f0',
                       foreground='#7f8c8d')
        
        style.configure('Option.TButton',
                       font=('Arial', 10),
                       padding=(10, 8))
        
    def create_widgets(self):
        """Crea tots els widgets de la interfície"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Títol
        title_label = ttk.Label(main_frame, 
                               text="🚀 PackAssist - Empaquetament Intel·ligent",
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # Subtítol amb estat
        self.status_label = ttk.Label(main_frame,
                                     text="Inicialitzant...",
                                     style='Subtitle.TLabel')
        self.status_label.grid(row=1, column=0, columnspan=2, pady=(0, 20))
        
        # Separador
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        # Descripció
        desc_label = ttk.Label(main_frame,
                              text="Selecciona l'aplicació que vols obrir:",
                              font=('Arial', 11))
        desc_label.grid(row=3, column=0, columnspan=2, pady=(0, 15))
        
        # Botons de les aplicacions
        self.create_app_buttons(main_frame)
        
        # Separador inferior
        separator2 = ttk.Separator(main_frame, orient='horizontal')
        separator2.grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(20, 15))
        
        # Botó de sortida
        exit_btn = ttk.Button(main_frame,
                             text="❌ Sortir",
                             command=self.exit_app,
                             style='Option.TButton')
        exit_btn.grid(row=11, column=0, columnspan=2, pady=(0, 10))
        
        # Configurar grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
    def create_app_buttons(self, parent):
        """Crea els botons de les aplicacions"""
        
        # Fila 0: Aplicacions principals
        gui_btn = ttk.Button(parent,
                            text="🚀 PackAssist GUI\n(Interfície Completa - RECOMANAT)",
                            command=lambda: self.launch_app("packassist_gui.py", "PackAssist GUI"),
                            style='Option.TButton',
                            width=30)
        gui_btn.grid(row=4, column=0, padx=(0, 10), pady=5, sticky=(tk.W, tk.E))
        
        simple_btn = ttk.Button(parent,
                               text="🎯 Aplicació Simple\n(2 Pestanyes)",
                               command=lambda: self.launch_app("packassist_simple.py", "Aplicació Simple"),
                               style='Option.TButton',
                               width=30)
        simple_btn.grid(row=4, column=1, padx=(10, 0), pady=5, sticky=(tk.W, tk.E))
        
        # Fila 1: Simplificadors GUI
        stl_advanced_btn = ttk.Button(parent,
                                     text="🔧 Simplificador STL Avançat\n(GUI amb 3 Pestanyes)",
                                     command=lambda: self.launch_app("actiu/tools/mesh_simplifiers/advanced_stl_simplifier.py", "Simplificador STL Avançat"),
                                     style='Option.TButton')
        stl_advanced_btn.grid(row=5, column=0, padx=(0, 10), pady=5, sticky=(tk.W, tk.E))
        
        # Fila 2: Eines avançades
        ultra_fast_btn = ttk.Button(parent,
                                   text="⚡ Simplificador Ultra Ràpid\n(Terminal Multi-algoritme)",
                                   command=lambda: self.launch_app("actiu/tools/mesh_simplifiers/ultra_fast_mesh_simplifier.py", "Simplificador Ultra Ràpid"),
                                   style='Option.TButton')
        ultra_fast_btn.grid(row=5, column=1, padx=(10, 0), pady=5, sticky=(tk.W, tk.E))
        
        simple_mesh_btn = ttk.Button(parent,
                                    text="🔧 Simplificador Simple\n(Terminal Bàsic)",
                                    command=lambda: self.launch_app("actiu/tools/mesh_simplifiers/mesh_simplifier_simple.py", "Simplificador Simple"),
                                    style='Option.TButton')
        simple_mesh_btn.grid(row=6, column=0, padx=(0, 10), pady=5, sticky=(tk.W, tk.E))
        
        # Fila 3: Testing
        test_btn = ttk.Button(parent,
                             text="🧪 Proves de Simplificació\n(Testing Avançat)",
                             command=lambda: self.launch_app("actiu/tests/test_mesh_simplification.py", "Proves de Simplificació"),
                             style='Option.TButton')
        test_btn.grid(row=6, column=1, padx=(10, 0), pady=5, sticky=(tk.W, tk.E))
        
        # Informació addicional
        info_frame = ttk.Frame(parent)
        info_frame.grid(row=7, column=0, columnspan=2, pady=(15, 0))
        
        info_label = ttk.Label(info_frame,
                              text="💡 Recomanació: Comença amb PackAssist GUI per funcionalitat completa",
                              font=('Arial', 9, 'italic'),
                              foreground='#3498db')
        info_label.pack()
        
    def check_environment(self):
        """Comprova l'entorn i actualitza l'estat"""
        def check():
            # Verificar entorn virtual
            venv_python = Path("packassist_env") / "Scripts" / "python.exe"
            
            if venv_python.exists():
                status = "✅ Entorn virtual detectat i llest"
                self.python_cmd = str(venv_python)
            else:
                status = "⚠️ Utilitzant Python del sistema"
                self.python_cmd = "python"
            
            # Actualitzar UI en el thread principal
            self.root.after(0, lambda: self.status_label.config(text=status))
        
        # Executar comprovació en thread separat
        threading.Thread(target=check, daemon=True).start()
        
    def launch_app(self, app_path, app_name):
        """Llança una aplicació"""
        def launch():
            try:
                self.status_label.config(text=f"🚀 Iniciant {app_name}...")
                self.root.update()
                
                # Executar l'aplicació
                result = subprocess.run([self.python_cmd, app_path], 
                                      capture_output=False,
                                      text=True)
                
                # Actualitzar estat
                if result.returncode == 0:
                    self.root.after(0, lambda: self.status_label.config(text=f"✅ {app_name} executat correctament"))
                else:
                    self.root.after(0, lambda: self.status_label.config(text=f"⚠️ {app_name} ha acabat amb errors"))
                    
            except Exception as e:
                error_msg = f"❌ Error llançant {app_name}: {str(e)}"
                self.root.after(0, lambda: self.status_label.config(text=error_msg))
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        
        # Executar en thread separat per no bloquejar la UI
        threading.Thread(target=launch, daemon=True).start()
    
    def exit_app(self):
        """Surt de l'aplicació"""
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Executa el launcher"""
        # Centrar finestra
        self.root.eval('tk::PlaceWindow . center')
        
        # Mostrar finestra
        self.root.mainloop()

def main():
    """Punt d'entrada principal"""
    try:
        launcher = PackAssistLauncher()
        launcher.run()
    except Exception as e:
        # Fallback a launcher de terminal si la GUI falla
        import traceback
        print(f"❌ Error iniciant GUI launcher: {e}")
        print("Traceback:", traceback.format_exc())
        print("\n🔄 Tornant a launcher de terminal...")
        
        # Importar i executar launcher original
        import launch_terminal
        launch_terminal.main()

if __name__ == "__main__":
    main()
