import cadquery as cq
import os
import json
from pathlib import Path
import hashlib
from datetime import datetime

def get_stp_dimensions(file_path):
    """
    Carrega un fitxer STP i retorna les dimensions de la caixa de límits.
    
    Args:
        file_path: Ruta al fitxer STP
        
    Returns:
        Dict amb dimensions o None si hi ha error
    """
    try:
        # Verificar que el fitxer existeix
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"El fitxer {file_path} no existeix")
            
        # Verificar extensió
        if not file_path.lower().endswith(('.stp', '.step')):
            raise ValueError("El fitxer ha de ser un STP/STEP")
            
        # Carregar el fitxer
        shape = cq.importers.importStep(file_path)
        
        # Verificar que s'ha carregat correctament
        if shape is None:
            raise ValueError("No s'ha pogut carregar la geometria del fitxer")
            
        bbox = shape.val().BoundingBox()
        
        # Verificar que les dimensions són vàlides
        if bbox.xlen <= 0 or bbox.ylen <= 0 or bbox.zlen <= 0:
            raise ValueError("Les dimensions del model no són vàlides")
            
        return {
            "length": round(bbox.xlen, 2),
            "width": round(bbox.ylen, 2),
            "height": round(bbox.zlen, 2),
            "volume": round(bbox.xlen * bbox.ylen * bbox.zlen, 2)
        }
        
    except FileNotFoundError as e:
        print(f"❌ Fitxer no trobat: {e}")
        return None
    except ValueError as e:
        print(f"❌ Error de validació: {e}")
        return None
    except Exception as e:
        print(f"❌ Error llegint {file_path}: {e}")
        return None

def validate_stp_file(file_path):
    """
    Valida si un fitxer STP és vàlid sense carregar les dimensions.
    
    Returns:
        bool: True si el fitxer és vàlid
    """
    try:
        return (os.path.exists(file_path) and 
                file_path.lower().endswith(('.stp', '.step')) and
                os.path.getsize(file_path) > 0)
    except:
        return False

def create_object_index(objects_dir, index_file="objects_index.json"):
    """
    Crea un índex de tots els fitxers STP en un directori.
    
    Args:
        objects_dir: Directori que conté els fitxers STP
        index_file: Nom del fitxer d'índex
        
    Returns:
        Dict amb l'índex d'objectes
    """
    objects_dir = Path(objects_dir)
    index_path = objects_dir / index_file
    
    if not objects_dir.exists():
        objects_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Creat directori: {objects_dir}")
    
    index = {
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "objects": {}
    }
    
    print(f"🔍 Escaneant objectes STP a {objects_dir}...")
    
    # Buscar tots els fitxers STP
    stp_files = list(objects_dir.glob("*.stp")) + list(objects_dir.glob("*.step"))
    
    for stp_file in stp_files:
        print(f"   📋 Processant: {stp_file.name}")
        
        # Calcular hash del fitxer per detectar canvis
        file_hash = calculate_file_hash(stp_file)
        
        # Obtenir dimensions
        dimensions = get_stp_dimensions(str(stp_file))
        
        if dimensions:
            object_info = {
                "file_path": str(stp_file),
                "file_name": stp_file.name,
                "file_hash": file_hash,
                "dimensions": dimensions,
                "file_size": stp_file.stat().st_size,
                "last_modified": datetime.fromtimestamp(stp_file.stat().st_mtime).isoformat(),
                "added_to_index": datetime.now().isoformat()
            }
            
            # Usar el nom del fitxer (sense extensió) com a clau
            object_key = stp_file.stem
            index["objects"][object_key] = object_info
            
            print(f"      ✅ {object_key}: {dimensions['length']}×{dimensions['width']}×{dimensions['height']} mm")
        else:
            print(f"      ❌ Error processant {stp_file.name}")
    
    # Guardar índex
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Índex guardat: {index_path}")
    print(f"📊 Total objectes indexats: {len(index['objects'])}")
    
    return index

def load_object_index(objects_dir, index_file="objects_index.json"):
    """
    Carrega l'índex d'objectes existent.
    
    Returns:
        Dict amb l'índex o None si no existeix
    """
    index_path = Path(objects_dir) / index_file
    
    if not index_path.exists():
        return None
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error carregant índex: {e}")
        return None

def update_object_index(objects_dir, index_file="objects_index.json"):
    """
    Actualitza l'índex d'objectes, afegint nous fitxers i eliminant els que ja no existeixen.
    
    Returns:
        Dict amb l'índex actualitzat
    """
    objects_dir = Path(objects_dir)
    existing_index = load_object_index(objects_dir, index_file)
    
    if existing_index is None:
        print("📋 No hi ha índex existent, creant-ne un de nou...")
        return create_object_index(objects_dir, index_file)
    
    print(f"🔄 Actualitzant índex d'objectes...")
    
    # Buscar fitxers STP actuals
    current_files = {}
    stp_files = list(objects_dir.glob("*.stp")) + list(objects_dir.glob("*.step"))
    
    for stp_file in stp_files:
        current_files[stp_file.stem] = stp_file
    
    # Actualitzar índex
    updated_index = {
        "created": existing_index.get("created", datetime.now().isoformat()),
        "updated": datetime.now().isoformat(),
        "objects": {}
    }
    
    # Processar fitxers actuals
    for object_key, stp_file in current_files.items():
        file_hash = calculate_file_hash(stp_file)
        
        # Verificar si el fitxer ha canviat
        if (object_key in existing_index["objects"] and 
            existing_index["objects"][object_key]["file_hash"] == file_hash):
            # Fitxer no ha canviat, mantenir informació existent
            updated_index["objects"][object_key] = existing_index["objects"][object_key]
            print(f"   ↻ {object_key}: Sense canvis")
        else:
            # Fitxer nou o modificat, recalcular dimensions
            print(f"   🔄 {object_key}: {'Nou' if object_key not in existing_index['objects'] else 'Modificat'}")
            
            dimensions = get_stp_dimensions(str(stp_file))
            if dimensions:
                object_info = {
                    "file_path": str(stp_file),
                    "file_name": stp_file.name,
                    "file_hash": file_hash,
                    "dimensions": dimensions,
                    "file_size": stp_file.stat().st_size,
                    "last_modified": datetime.fromtimestamp(stp_file.stat().st_mtime).isoformat(),
                    "added_to_index": existing_index["objects"].get(object_key, {}).get("added_to_index", datetime.now().isoformat()),
                    "updated_in_index": datetime.now().isoformat()
                }
                
                updated_index["objects"][object_key] = object_info
                print(f"      ✅ {dimensions['length']}×{dimensions['width']}×{dimensions['height']} mm")
    
    # Detectar fitxers eliminats
    removed_objects = set(existing_index["objects"].keys()) - set(current_files.keys())
    if removed_objects:
        print(f"   🗑️ Objectes eliminats: {', '.join(removed_objects)}")
    
    # Guardar índex actualitzat
    index_path = objects_dir / index_file
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(updated_index, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Índex actualitzat: {len(updated_index['objects'])} objectes")
    
    return updated_index

def get_indexed_objects(objects_dir, index_file="objects_index.json"):
    """
    Obté la llista d'objectes indexats.
    
    Returns:
        Dict amb objectes disponibles
    """
    index = load_object_index(objects_dir, index_file)
    
    if index is None:
        return {}
    
    return index.get("objects", {})

def calculate_file_hash(file_path):
    """
    Calcula el hash MD5 d'un fitxer per detectar canvis.
    
    Returns:
        str: Hash MD5 del fitxer
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""

def search_objects_by_dimensions(objects_dir, max_length=None, max_width=None, max_height=None, index_file="objects_index.json"):
    """
    Cerca objectes que compleixin certes restriccions de dimensions.
    
    Args:
        objects_dir: Directori d'objectes
        max_length: Longitud màxima (opcional)
        max_width: Amplada màxima (opcional)
        max_height: Altura màxima (opcional)
        
    Returns:
        List amb objectes que compleixen els criteris
    """
    objects = get_indexed_objects(objects_dir, index_file)
    results = []
    
    for obj_key, obj_info in objects.items():
        dims = obj_info["dimensions"]
        
        # Verificar restriccions
        if max_length and dims["length"] > max_length:
            continue
        if max_width and dims["width"] > max_width:
            continue
        if max_height and dims["height"] > max_height:
            continue
        
        results.append({
            "key": obj_key,
            "name": obj_info["file_name"],
            "dimensions": dims,
            "file_path": obj_info["file_path"]
        })
    
    return results