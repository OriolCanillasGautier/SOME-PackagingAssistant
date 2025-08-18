"""
Sistema de gestió de preferències d'usuari
"""

import json
import os
from typing import Dict, Any

class UserPreferences:
    """Gestiona les preferències d'usuari per la visualització"""
    
    def __init__(self, config_file: str = "packassist_config.json"):
        self.config_file = config_file
        self.defaults = {
            # Opcions visuals
            'show_wireframe': True,
            'show_labels': True,
            'show_axes': True,
            'show_grid': True,
            'show_edges': False,
            
            # Colors i estil
            'color_scheme': 'solid',
            'background_color': 'white',
            'wireframe_color': 'black',
            'window_size': '1200x900',
            
            # Exportació
            'auto_screenshot': False,
            'auto_stl_export': False,
            'auto_json_export': False,
            'auto_csv_export': False
        }
        self.preferences = self.load()
    
    def load(self) -> Dict[str, Any]:
        """Carrega les preferències del fitxer"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_prefs = json.load(f)
                # Combinar amb defaults per tenir sempre totes les claus
                prefs = self.defaults.copy()
                prefs.update(saved_prefs)
                return prefs
        except Exception as e:
            print(f"Error carregant preferències: {e}")
        
        return self.defaults.copy()
    
    def save(self, preferences: Dict[str, Any]):
        """Guarda les preferències al fitxer"""
        try:
            self.preferences.update(preferences)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, indent=2, ensure_ascii=False)
            print(f"✅ Preferències guardades a {self.config_file}")
        except Exception as e:
            print(f"Error guardant preferències: {e}")
    
    def get(self, key: str, default=None):
        """Obté una preferència"""
        return self.preferences.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Obté totes les preferències"""
        return self.preferences.copy()
    
    def reset(self):
        """Restableix les preferències per defecte"""
        self.preferences = self.defaults.copy()
        self.save(self.preferences)
