# === FUNCIONS DE CREACIÓ D'OBJECTES ===

def create_new_box(self):
    """Creates a new box and adds it to the CSV index."""
    from src.packassist import CreateBoxDialog
    
    # Callback for when a box is created
    def on_box_created(box_data):
        self.metadata.append(box_data)
        self._update_csv_tree()
        self.reload_metadata()
    
    # Show the dialog
    CreateBoxDialog(self.root, callback=on_box_created)

def create_new_object(self):
    """Creates a new object and adds it to the CSV index."""
    from src.packassist import CreateObjectDialog
    
    # Callback for when an object is created
    def on_object_created(object_data):
        self.metadata.append(object_data)
        self._update_csv_tree()
        self.reload_metadata()
    
    # Show the dialog
    CreateObjectDialog(self.root, callback=on_object_created)

def edit_selected_item(self):
    """Edit dimensions of the selected item."""
    from src.packassist import EditDimensionsDialog
    
    # Get selected item
    selection = self.csv_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "No item selected")
        return
    
    # Get selected item data
    item_id = selection[0]
    item_values = self.csv_tree.item(item_id, "values")
    if not item_values:
        return
    
    # Find corresponding metadata entry
    entry = None
    for meta in self.metadata:
        if (meta.get("type") == item_values[0] and 
            meta.get("name") == item_values[1] and 
            meta.get("file_path") == item_values[2]):
            entry = meta
            break
    
    if not entry:
        messagebox.showwarning("Warning", "Could not find metadata for selected item")
        return
    
    # Get dimensions for the selected item
    dimensions = self._get_entry_dimensions(entry.get("file_path"))
    if not dimensions:
        messagebox.showerror("Error", "Could not read dimensions for the selected item")
        return
    
    # Callback for when dimensions are updated
    def on_dimensions_updated(entry, new_dimensions):
        # Refresh metadata and UI
        self.reload_metadata()
    
    # Show the dialog
    EditDimensionsDialog(self.root, entry, dimensions, callback=on_dimensions_updated)
