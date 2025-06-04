"""
Dialog Creator for PackAssist
Provides dialogs for creating and editing boxes and objects.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
from datetime import datetime
import uuid
import shutil


class CreateBoxDialog:
    """Dialog for creating a new box."""
    
    def __init__(self, parent, callback=None):
        """Initialize the dialog."""
        self.parent = parent
        self.callback = callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Box")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Box name
        ttk.Label(main_frame, text="Box Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=5)
        
        # Dimensions
        ttk.Label(main_frame, text="Dimensions (mm):").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))
        
        dim_frame = ttk.Frame(main_frame)
        dim_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        labels = ["Length:", "Width:", "Height:"]
        defaults = [1000.0, 800.0, 600.0]
        self.dimension_vars = []
        
        for i, (label, default) in enumerate(zip(labels, defaults)):
            ttk.Label(dim_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(5 if i > 0 else 0, 0))
            var = tk.DoubleVar(value=default)
            self.dimension_vars.append(var)
            ttk.Entry(dim_frame, textvariable=var, width=10).grid(row=i, column=1, sticky=tk.W, padx=(5, 0), pady=(5 if i > 0 else 0, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="Create Box", command=self._create_box).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _create_box(self):
        """Create the box with the given dimensions."""
        name = self.name_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Box name cannot be empty")
            return
        
        try:
            dimensions = [var.get() for var in self.dimension_vars]
            if any(d <= 0 for d in dimensions):
                messagebox.showerror("Error", "All dimensions must be positive")
                return
            
            # Ensure boxes directory exists
            os.makedirs("boxes", exist_ok=True)
            
            # Create virtual box using custom dimensions
            box_id = str(uuid.uuid4())[:8]
            box_filename = f"custom://box/{name}_{dimensions[0]}x{dimensions[1]}x{dimensions[2]}.virtual"
            
            # Save custom dimensions to JSON
            custom_dir = os.path.join("data", "custom")
            os.makedirs(custom_dir, exist_ok=True)
            
            custom_file = os.path.join(custom_dir, "custom_dimensions.json")
            custom_data = {}
            
            # Load existing data if available
            if os.path.exists(custom_file):
                with open(custom_file, "r", encoding="utf-8") as f:
                    try:
                        custom_data = json.load(f)
                    except json.JSONDecodeError:
                        custom_data = {}
            
            # Add new box
            custom_data[box_filename] = {
                "name": name,
                "length": dimensions[0],
                "width": dimensions[1],
                "height": dimensions[2],
                "volume": dimensions[0] * dimensions[1] * dimensions[2],
                "created_at": str(datetime.now())
            }
            
            # Save data
            with open(custom_file, "w", encoding="utf-8") as f:
                json.dump(custom_data, f, indent=2)
            
            # Add to index.csv via callback
            if self.callback:
                self.callback({
                    "type": "box",
                    "name": name,
                    "file_path": box_filename
                })
            
            self.dialog.destroy()
            messagebox.showinfo("Success", f"Box '{name}' created successfully!")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid dimensions. Please enter numeric values.")
        except Exception as e:
            messagebox.showerror("Error", f"Error creating box: {e}")


class CreateObjectDialog:
    """Dialog for creating a new object."""
    
    def __init__(self, parent, callback=None):
        """Initialize the dialog."""
        self.parent = parent
        self.callback = callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Object")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Object name
        ttk.Label(main_frame, text="Object Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=5)
        
        # Creation method
        ttk.Label(main_frame, text="Creation Method:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.method_var = tk.StringVar(value="dimensions")
        
        method_frame = ttk.Frame(main_frame)
        method_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(method_frame, text="Manual Dimensions", 
                        variable=self.method_var, value="dimensions",
                        command=self._toggle_method).pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text="Import STP/STL File", 
                        variable=self.method_var, value="import",
                        command=self._toggle_method).pack(anchor=tk.W)
        
        # Dimensions frame
        self.dim_frame = ttk.LabelFrame(main_frame, text="Object Dimensions (mm)", padding="10")
        self.dim_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        labels = ["Length:", "Width:", "Height:"]
        defaults = [200.0, 150.0, 100.0]
        self.dimension_vars = []
        
        for i, (label, default) in enumerate(zip(labels, defaults)):
            ttk.Label(self.dim_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(5 if i > 0 else 0, 0))
            var = tk.DoubleVar(value=default)
            self.dimension_vars.append(var)
            ttk.Entry(self.dim_frame, textvariable=var, width=10).grid(row=i, column=1, sticky=tk.W, padx=(5, 0), pady=(5 if i > 0 else 0, 0))
        
        # Import frame
        self.import_frame = ttk.LabelFrame(main_frame, text="Import File", padding="10")
        self.import_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.file_path_var = tk.StringVar()
        ttk.Entry(self.import_frame, textvariable=self.file_path_var).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(self.import_frame, text="Browse...", command=self._browse_file).grid(row=0, column=1)
        
        self.file_info_var = tk.StringVar(value="No file selected")
        ttk.Label(self.import_frame, textvariable=self.file_info_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        self.import_frame.grid_remove()  # Hide initially
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(button_frame, text="Create Object", command=self._create_object).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _toggle_method(self):
        """Toggle between manual dimensions and import."""
        method = self.method_var.get()
        if method == "dimensions":
            self.import_frame.grid_remove()
            self.dim_frame.grid()
        else:
            self.dim_frame.grid_remove()
            self.import_frame.grid()
    
    def _browse_file(self):
        """Browse for an STP or STL file."""
        filepath = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("3D Files", "*.stp;*.step;*.stl"), ("STP Files", "*.stp;*.step"), 
                      ("STL Files", "*.stl"), ("All Files", "*.*")]
        )
        if filepath:
            self.file_path_var.set(filepath)
            filename = os.path.basename(filepath)
            size = os.path.getsize(filepath) / 1024  # KB
            self.file_info_var.set(f"File: {filename} ({size:.1f} KB)")
    
    def _create_object(self):
        """Create the object with the given properties."""
        name = self.name_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Object name cannot be empty")
            return
        
        try:
            # Ensure objects directory exists
            os.makedirs("objects", exist_ok=True)
            
            if self.method_var.get() == "dimensions":
                # Create virtual object using dimensions
                dimensions = [var.get() for var in self.dimension_vars]
                if any(d <= 0 for d in dimensions):
                    messagebox.showerror("Error", "All dimensions must be positive")
                    return
                
                object_filename = f"custom://object/{name}_{dimensions[0]}x{dimensions[1]}x{dimensions[2]}.virtual"
                
                # Save custom dimensions to JSON
                custom_dir = os.path.join("data", "custom")
                os.makedirs(custom_dir, exist_ok=True)
                
                custom_file = os.path.join(custom_dir, "custom_dimensions.json")
                custom_data = {}
                
                # Load existing data if available
                if os.path.exists(custom_file):
                    with open(custom_file, "r", encoding="utf-8") as f:
                        try:
                            custom_data = json.load(f)
                        except json.JSONDecodeError:
                            custom_data = {}
                
                # Add new object
                custom_data[object_filename] = {
                    "name": name,
                    "length": dimensions[0],
                    "width": dimensions[1],
                    "height": dimensions[2],
                    "volume": dimensions[0] * dimensions[1] * dimensions[2],
                    "created_at": str(datetime.now())
                }
                
                # Save data
                with open(custom_file, "w", encoding="utf-8") as f:
                    json.dump(custom_data, f, indent=2)
                
                # Add to index.csv via callback
                if self.callback:
                    self.callback({
                        "type": "object",
                        "name": name,
                        "file_path": object_filename
                    })
                
                messagebox.showinfo("Success", f"Object '{name}' created successfully!")
                
            else:
                # Import STP/STL file
                source_path = self.file_path_var.get()
                if not source_path or not os.path.exists(source_path):
                    messagebox.showerror("Error", "Please select a valid file")
                    return
                
                # Copy file to objects directory
                filename = os.path.basename(source_path)
                base_name, ext = os.path.splitext(filename)
                
                # Sanitize name if needed
                sanitized_name = "".join(c for c in name if c.isalnum() or c in "._- ")
                
                # Create target path
                target_path = os.path.join("objects", f"{sanitized_name}{ext}")
                
                # Copy the file
                shutil.copy2(source_path, target_path)
                
                # Add to index.csv via callback
                if self.callback:
                    self.callback({
                        "type": "object",
                        "name": name,
                        "file_path": target_path
                    })
                
                messagebox.showinfo("Success", f"Object '{name}' imported successfully!")
            
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Invalid dimensions. Please enter numeric values.")
        except Exception as e:
            messagebox.showerror("Error", f"Error creating object: {e}")


class EditDimensionsDialog:
    """Dialog for editing object dimensions."""
    
    def __init__(self, parent, entry, dimensions, callback=None):
        """
        Initialize the dialog.
        
        Args:
            parent: The parent widget
            entry: The CSV entry to edit
            dimensions: Current dimensions dict with keys 'length', 'width', 'height'
            callback: Function to call after editing is complete
        """
        self.parent = parent
        self.entry = entry
        self.dimensions = dimensions
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Dimensions: {entry['name']}")
        self.dialog.geometry("400x230")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Object info
        info_frame = ttk.LabelFrame(main_frame, text="Object Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Type: {self.entry['type'].capitalize()}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Name: {self.entry['name']}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"File: {self.entry['file_path']}").pack(anchor=tk.W)
        
        # Dimensions
        dim_frame = ttk.LabelFrame(main_frame, text="Dimensions (mm)", padding="10")
        dim_frame.pack(fill=tk.X)
        
        labels = ["Length:", "Width:", "Height:"]
        keys = ["length", "width", "height"]
        self.dimension_vars = []
        
        for i, (label, key) in enumerate(zip(labels, keys)):
            ttk.Label(dim_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=(5 if i > 0 else 0, 0))
            var = tk.DoubleVar(value=self.dimensions.get(key, 0))
            self.dimension_vars.append(var)
            ttk.Entry(dim_frame, textvariable=var, width=10).grid(row=i, column=1, sticky=tk.W, padx=(5, 0), pady=(5 if i > 0 else 0, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))
        
        ttk.Button(button_frame, text="Save Changes", command=self._save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _save_changes(self):
        """Save the changed dimensions."""
        try:
            dimensions = [var.get() for var in self.dimension_vars]
            if any(d <= 0 for d in dimensions):
                messagebox.showerror("Error", "All dimensions must be positive")
                return
            
            # Update dimensions
            new_dimensions = {
                "length": dimensions[0],
                "width": dimensions[1],
                "height": dimensions[2],
            }
            
            # Check if it's a virtual object
            file_path = self.entry["file_path"]
            if file_path.startswith("custom://"):
                # Update in custom_dimensions.json
                custom_file = os.path.join("data", "custom", "custom_dimensions.json")
                if os.path.exists(custom_file):
                    with open(custom_file, "r", encoding="utf-8") as f:
                        try:
                            custom_data = json.load(f)
                        except json.JSONDecodeError:
                            custom_data = {}
                    
                    if file_path in custom_data:
                        custom_data[file_path].update({
                            "length": dimensions[0],
                            "width": dimensions[1],
                            "height": dimensions[2],
                            "volume": dimensions[0] * dimensions[1] * dimensions[2],
                            "modified_at": str(datetime.now())
                        })
                        
                        with open(custom_file, "w", encoding="utf-8") as f:
                            json.dump(custom_data, f, indent=2)
                    else:
                        messagebox.showerror("Error", f"Object not found in custom dimensions: {file_path}")
                        return
            
            if self.callback:
                self.callback(self.entry, new_dimensions)
            
            self.dialog.destroy()
            messagebox.showinfo("Success", f"Dimensions updated successfully!")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid dimensions. Please enter numeric values.")
        except Exception as e:
            messagebox.showerror("Error", f"Error updating dimensions: {e}")
