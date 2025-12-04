# 📦 SOME-PackAssist Web

**Versió 0.0.2** | Aplicació web de càlcul de capacitat amb Three.js i Rapier.js

## 🚀 Característiques

### Mode Optimitzat (🎯)
- Càlcul matemàtic precís de capacitat
- 6 orientacions possibles (amb rotació)
- Límit per pes i volum
- Factor de seguretat ajustable (50-100%)
- Visualització 3D interactiva amb peces instanciades

### Mode a Granel (🌊)
- Simulació física real amb gravetat (Rapier.js)
- Les peces cauen i s'acomoden naturalment dins la caixa
- Suport per malles STL complexes
- Mode automàtic de detecció de capacitat
- Sistema de vibració per assentar peces
- Fins a 20 colors configurables
- Paràmetres configurables:
  - Alçada de caiguda
  - Nombre màxim de peces
  - Interval entre caigudes
  - Rotació aleatòria

### Informes PDF
- Generació d'informes professionals
- Múltiples vistes (isomètrica, frontal, superior, lateral)
- Català i anglès
- Previsualització abans de descarregar

## 🛠️ Tecnologies

- **Three.js** (r160) - Renderitzat 3D WebGL
- **Rapier.js** (WASM) - Motor de física determinista
- **ES Modules** - Mòduls JavaScript nadius
- **CSS Custom Properties** - Tema clar/fosc automàtic

## 📁 Estructura

```
web/
├── index.html              # Pàgina principal
├── start_server.bat        # Script per iniciar servidor (Windows)
├── css/
│   └── styles.css          # Estils amb tema clar/fosc
└── js/
    ├── main.js             # Controlador principal
    ├── packing/
    │   └── calculator.js   # Lògica de càlcul
    ├── mesh/
    │   └── mesh-utils.js   # Utilitats STL
    ├── visualization/
    │   └── scene.js        # Gestor d'escena Three.js
    ├── physics/
    │   └── physics-world.js # Motor de física Rapier.js
    └── report/
        └── report-generator.js # Generador d'informes PDF
```

## 🚀 Inici Ràpid

### Producció (Nginx a Ubuntu, port 5555)
```bash
# Copia al directori web de Nginx
sudo cp -r . /var/www/packassist

# Configura Nginx (veure README principal)
# Obre: http://<IP_SERVIDOR>:5555
```

### Desenvolupament local
```bash
python3 -m http.server 5555
```

Obre: http://localhost:5555
- Tema clar/fosc automàtic segons preferències del sistema
- Responsive per mòbil i escriptori

## 🔧 Desenvolupament

### Afegir noves funcionalitats

1. **Nou tipus de càlcul**: Edita `js/packing/calculator.js`
2. **Nova visualització**: Edita `js/visualization/scene.js`
3. **Nova física**: Edita `js/physics/physics-world.js`
4. **Nous controls UI**: Edita `index.html` i `js/main.js`

### Debug

L'objecte global `window.PackAssist` exposa:
- `state` - Estat de l'aplicació
- `elements` - Referències DOM

```javascript
// A la consola del navegador
PackAssist.state.sceneManager.scene.children
PackAssist.state.bulkSimulation.physics.bodies
```

## 📄 Llicència

Mateix projecte PackAssist - Oriol Canillas © 2025
