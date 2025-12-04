# 📦 SOME-PackAssist

**Versió 0.0.2** | Calculadora de Capacitat de Peces amb Visualització 3D i Simulació Física

Aplicació web per calcular quantes peces caben dins d'un contenidor, amb visualització 3D interactiva i simulació física real per al mode a granel.

## 🚀 Característiques

### Mode Optimitzat (🎯)
- Càlcul matemàtic precís de capacitat
- 6 orientacions possibles (amb rotació opcional)
- Límit per pes i volum
- Factor de seguretat ajustable (50-100%)
- Visualització 3D interactiva

### Mode a Granel (🌊)
- Simulació física real amb gravetat (Rapier.js)
- Les peces cauen i s'acomoden naturalment dins la caixa
- Suport per malles STL complexes
- Mode automàtic de detecció de capacitat
- Sistema de vibració per assentar les peces
- Fins a 20 colors configurables per les peces
- Paràmetres configurables:
  - Alçada de caiguda
  - Nombre màxim de peces
  - Interval entre caigudes
  - Rotació aleatòria

### Informes PDF
- Generació d'informes professionals
- Múltiples vistes (isomètrica, frontal, superior, lateral)
- Disponible en català i anglès
- Previsualització abans de descarregar

## 🛠️ Tecnologies

- **Three.js** (r160) - Renderitzat 3D WebGL
- **Rapier.js** (WASM) - Motor de física determinista
- **ES Modules** - Mòduls JavaScript nadius
- **CSS Custom Properties** - Tema clar/fosc automàtic

## 📁 Estructura del Projecte

```
SOME-PackagingAssistant/
├── web/
│   ├── index.html              # Pàgina principal
│   ├── start_server.bat        # Script per iniciar servidor
│   ├── css/
│   │   └── styles.css          # Estils amb tema clar/fosc
│   └── js/
│       ├── main.js             # Controlador principal
│       ├── packing/
│       │   └── calculator.js   # Lògica de càlcul
│       ├── mesh/
│       │   └── mesh-utils.js   # Utilitats STL
│       ├── visualization/
│       │   └── scene.js        # Gestor d'escena Three.js
│       ├── physics/
│       │   └── physics-world.js # Motor de física Rapier.js
│       └── report/
│           └── report-generator.js # Generador d'informes PDF
└── .github/
    └── copilot-instructions.md # Notes per a GitHub Copilot
```

## 🚀 Inici Ràpid

### Producció amb Nginx (Ubuntu)

1. Copia la carpeta `web/` al directori de Nginx:
```bash
sudo cp -r web /var/www/packassist
```

2. Crea la configuració de Nginx (`/etc/nginx/sites-available/packassist`):
```nginx
server {
    listen 5555;
    server_name _;
    
    root /var/www/packassist;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Cache per assets estàtics
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
```

3. Activa el site i reinicia Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/packassist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

4. Obre el navegador a: `http://<IP_DEL_SERVIDOR>:5555`

### Desenvolupament local

```bash
# Amb Python
cd web
python3 -m http.server 5555

# O amb Node.js
npx serve -l 5555 web
```

## 📝 Ús

1. **Selecciona el mode**: Optimitzat (càlcul matemàtic) o A Granel (simulació física)
2. **Introdueix les dimensions** de l'objecte (o carrega un fitxer STL)
3. **Introdueix les dimensions** de la caixa/contenidor
4. **Executa** el càlcul o simulació
5. **Genera l'informe** PDF si cal

## 📋 Notes

- Totes les dimensions són en **mil·límetres (mm)**
- Els fitxers STL s'assumeixen en mm
- El mode a granel utilitza física real, els resultats poden variar entre execucions
- Es recomana un navegador modern amb suport WebGL2

## 🔧 Desenvolupament

L'aplicació utilitza ES Modules i CDN per a les dependències:
- Three.js: https://unpkg.com/three@0.160.0
- Rapier.js: https://cdn.jsdelivr.net/npm/@dimforge/rapier3d-compat@0.12.0

No cal instal·lar res, només servir els fitxers estàtics.

## 📄 Llicència

© 2025 Oriol Canillas

---

**SOME-PackAssist v0.0.2** - Calculadora de Capacitat de Peces

