# 📦 PackAssist Web

Versió web de l'eina de càlcul de capacitat de peces, ara amb **Three.js** per visualització 3D i **Rapier.js** per simulació física en mode a granel.

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
- Paràmetres configurables:
  - Alçada de caiguda
  - Nombre màxim de peces
  - Interval entre caigudes
  - Rotació aleatòria

## 🛠️ Tecnologies

- **Three.js** (r160) - Renderitzat 3D WebGL
- **Rapier.js** (WASM) - Motor de física determinista
- **ES Modules** - Mòduls JavaScript nadius
- **CSS Custom Properties** - Tema clar/fosc automàtic

## 📁 Estructura

```
web/
├── index.html              # Pàgina principal
├── server.php              # Servidor PHP de desenvolupament
├── css/
│   └── styles.css          # Estils amb tema clar/fosc
└── js/
    ├── main.js             # Controlador principal
    ├── packing/
    │   └── calculator.js   # Lògica de càlcul (port de packing_core.py)
    ├── mesh/
    │   └── mesh-utils.js   # Utilitats STL (port de mesh_utils.py)
    ├── visualization/
    │   └── scene.js        # Gestor d'escena Three.js
    └── physics/
        └── physics-world.js # Motor de física Rapier.js
```

## 🏃 Com executar

### Opció 1: PHP (recomanat per desenvolupament)

```bash
cd web
php -S localhost:8080 server.php
```

Obre el navegador a `http://localhost:8080`

### Opció 2: Python

```bash
cd web
python -m http.server 8080
```

### Opció 3: Node.js (amb npx)

```bash
cd web
npx serve .
```

### Opció 4: Directament des del sistema de fitxers

Obre `index.html` directament al navegador (algunes funcionalitats poden no funcionar per restriccions CORS).

## 🎮 Ús

### Mode Optimitzat

1. Introdueix les dimensions de l'objecte (mm) o puja un STL
2. Introdueix les dimensions de la caixa (mm)
3. Configura el pes per unitat i màxim
4. Ajusta el factor de seguretat
5. Fes clic a **CALCULAR CAPACITAT**

### Mode a Granel

1. Canvia al mode "🌊 Mode a Granel"
2. Configura les dimensions de l'objecte i la caixa
3. Ajusta els paràmetres de simulació:
   - **Alçada de caiguda**: Des de quina alçada cauen les peces
   - **Peces màximes**: Quantes peces deixar caure
   - **Interval**: Temps entre cada peça (ms)
   - **Rotació aleatòria**: Si les peces giren en caure
4. Fes clic a **INICIAR SIMULACIÓ**
5. Observa com les peces cauen i s'acomoden per gravetat
6. La simulació s'atura quan totes les peces s'han estabilitzat

## 📝 Notes tècniques

### Física

- El motor Rapier.js utilitza WASM per màxim rendiment
- Les malles STL es converteixen a convex hulls per col·lisions
- La gravetat està escalada per treballar en mm (-981 mm/s²)
- Detecció d'estabilització: 30 frames amb velocitat < 1 mm/s

### Rendiment

- Instanced rendering per peces (mode optimitzat)
- Límit de 500 peces visuals en mode optimitzat
- Límit configurable en mode a granel (per defecte 50)
- Web Workers per càrrega STL asíncrona

### Compatibilitat

- Navegadors moderns amb WebGL2 (Chrome, Firefox, Edge, Safari 15+)
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
