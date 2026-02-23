# Implementation Plan — PackAssist v0.0.3

Pla d'implementació derivat del TODO.md. Organitzat en 7 fases seqüencials.  
Cada fase és autocontinguda i desplegable independentment.  
Última actualització: 2026-02-13

---

## Fase 1 — Neteja: safety factor + displayCount coherent  ✅ COMPLETADA

### 1.1 Eliminar safety factor
- [x] Esborrar `DEFAULT_SAFETY_FACTOR` a `calculator.js`
- [x] Eliminar bloc d'aplicació (stability slack) que sobreescrivia el millor resultat
- [x] Treure lectura de `safetyFactor` a `main.js` dins `getInputValues()`
- [x] Netejar referències residuals a `createSummary()`

### 1.2 Unificar `displayCount`
- [x] Crear `state.displayCount` centralitzat a `main.js`
- [x] Mode optimitzat: fixar a `drawnCount`
- [x] Gravetat (optimitzat): actualitzar `state.displayCount` i `state.lastResults.pieceCount`
- [x] Mode bulk: `state.displayCount = status.inside`
- [x] Limitar `lastPlacement.positions` a `displayCount` elements

---

## Fase 2 — Volum real i selector de material  ✅ COMPLETADA

### 2.1 Propagació de `meshVolume`
- [x] `state.lastResults.meshVolume` arriba a `generatePDF()`
- [x] Etiquetar "volum estimat" vs "volum real" al report

### 2.2 Selector de material a la UI
- [x] `<select id="material-selector">` a `index.html` (Alumini, Acer, Plàstic, Personalitzat)
- [x] Càlcul de pes per peça i total basat en densitat × volum real
- [x] Dades propagades a `state.lastResults` i PDF

### 2.4 Pes material al limitador de pes
- [x] Quan un material està seleccionat, el pes per peça es calcula **abans** de `calcularEmpaquetatge()` i sobreescriu `values.objWeight`.
- [x] El camp de pes a la UI s'actualitza automàticament (tant al calcular com en canviar material/densitat/sòlid-buit/gruix).
- [x] `updateWeightFromMaterial()` centralitza el càlcul: es crida en canviar material, densitat, sòlid/buit, gruix, i en carregar STL (upload o historial).
- [x] Mode bulk (`updateSimulationStatus`) també sobreescriu `values.objWeight` amb pes per material.
- [x] Si material = "No estimar pes", es manté el pes manual introduït per l'usuari.

### 2.3 Unitats teòriques màximes
- [x] `Math.floor(volBox / volReal)` mostrat a UI i report

---

## Fase 3 — Async + cancel·lació + guia STL  ✅ COMPLETADA

### 3.1 Versió async de heightmap
- [x] `requestAnimationFrame` yields dins el bucle
- [x] `abortSignal.aborted` a cada iteració
- [x] Progrés amb fases: "Preparant geometria", "Provant orientacions", "Col·locant peces X/N"
- [x] Cronòmetre visible a la barra de progrés + console.time al log

### 3.2 Cancel·lació end-to-end
- [x] `handleCalculate()` fa abort si ja n'hi ha un d'actiu
- [x] Al catch d'`AbortError`: netejar escena + restaurar UI

### 3.3 Guia per STL complexes
- [x] `VERTEX_THRESHOLD = 50000`
- [x] Missatge informatiu amb botó al simplificador

### 3.4 STL simplificada persistent
- [x] `toBinarySTL()` exporta geometria simplificada a ArrayBuffer
- [x] L'historial es sobreescriu amb la versió simplificada en aplicar
- [x] Nom actualitzat a `_simpXpct.stl`

### 3.5 Progrés i UX
- [x] Barra de progrés redistribuïda: 1-5% setup, 6-70% orientacions, 70-95% placement
- [x] Emojis decoratius eliminats (conservant ⚠️)
- [x] PDF: eliminada 3a pàgina en blanc

---

## Fase 4 — Densitat heightmap + InstancedMesh  ← EN CURS

### 4.1 Corregir maxDraw com a cap de placement  ✅
- [x] **`maxDraw` ja no limita el nombre de peces col·locades**.
  - `maxTry` adaptatiu: `Math.ceil(boxVolume / pieceBBoxVolume * 1.2)` (cap a 2000).
  - `maxDraw` és només el cap de renderització (InstancedMesh pre-allotja `effectiveMaxTry`).
  - `main.js` calcula `maxTry` i el passa separadament a `scene.js`.
  - `scene.js` (sync + async) accepten `maxTry` param, computen `effectiveMaxTry` internament.
- [x] **Eliminat BVH collision system**: triangle-triangle checks causaven resultats inconsistents.
  - Heightmap sol ja prevé overlap vertical (cada peça es col·loca sobre la màxima alçada del footprint).
  - Sense BVH: determinístic, independent de topologia de malla, sense collision-skip budget.
  - Resultats consistents entre STL original i simplificada (mateixa peça → mateix compte ±1).
- [x] **Log de diagnòstic**: al final del placement, `console.log` amb placed i effectiveMaxTry.
- [x] **Orientacio estable per gravetat (mode optimitzat)**:
  - `main.js`: drop fisic amb Rapier per obtenir la pose estable.
  - Cerca de yaw cada 30 graus sobre la base de gravetat.
  - Elimina dependència de normals/export orientation.
  - Precomputació en carregar/simplificar/carregar historial; reutilització al càlcul (sense tornar a simular cada vegada).
  - Mostreig de múltiples bases estables (multi-drop) per evitar quedar-se amb una sola orientació pobre.
  - Línia de temps visible a l'estat STL (`Orientació: X ms (N bases)`).
  - Diagnòstic de malla tancada/fuites (boundary/non-manifold edges) per validar fiabilitat de pes per volum.

### 4.2 InstancedMesh a la ruta sync
- [ ] Substituir creació de `THREE.Mesh` individuals a `addPackedSTLHeightMap()` per `InstancedMesh`.
- [ ] Reusar el patró de la versió async (ja implementat).

### 4.3 InstancedMesh per mode bulk
- [ ] Pre-crear InstancedMesh amb `maxCount` estimat a `dropPiece()`
- [ ] Incrementar `instancedMesh.count` en lloc de crear `THREE.Mesh`
- [ ] Sincronitzar matrius des dels `RigidBody` al `step()`

---

## Fase 5 — Algorisme Skyline-based layering

### 5.1 Nou algorisme de packing
- [ ] Substituir heurística grid a `calcularEmpaquetatge()` per skyline
- [ ] Heightmap 2D discretitzat (resolució ~1mm)
- [ ] Per cada peça: generar footprint 2D → escanejar skyline → col·locar a alçada mínima
- [ ] Provar 6 permutacions d'eixos (cuboid) o orientacions STL
- [ ] Output: array de `{position, orientation, layerIndex}`

### 5.2 Base estable per defecte
- [ ] `alignToStableBase()` abans de generar orientacions
- [ ] 4 variants yaw (0°/90°/180°/270°) respecte a la base alineada

---

## Fase 6 — Simulació física millorada

### 6.1 Gravetat mode optimitzat
- [ ] `dropLiftY = 0` (no aixecar peces)
- [ ] `lockAllRotations()` durant caiguda; alliberar al contacte estable
- [ ] Vibració 5-6s amb fases desfasades
- [ ] Massa real: `density = pieceWeight / volReal`
- [ ] Damping: `linearDamping: 2.0, angularDamping: 5.0`

### 6.2 Densitat mode bulk
- [ ] Drop en capes organitzades: grid de files×columnes
- [ ] 3 cicles de refill + lid press intermedi
- [ ] Vibració desfasada per paret
- [ ] Criteri saturació: `volOcupat / volTeòric > 0.95`

---

## Fase 7 — Servidor unificat + XAMPP

### 7.1 Crear `api_server.py` (Flask)
- [ ] `POST /api/simplify` — lògica de `mesh_server.py`
- [ ] `GET /api/health`, `GET /api/library`, `POST /api/upload`, `DELETE /api/delete`
- [ ] `POST /api/report` — PDF via `pdf_generator.py`

### 7.2 XAMPP Apache reverse proxy
- [ ] `mod_proxy` + `ProxyPass /api/ http://127.0.0.1:8787/api/`

### 7.3 URLs relatives al frontend
- [ ] `mesh-simplifier.js`: `MESH_SERVER = ''` (relatiu)

### 7.4 Infraestructura
- [ ] `requirements.txt`, `start_server.bat`, documentació README

---

## Decisions preses

| Decisió | Elecció | Motiu |
|---------|---------|-------|
| Async vs Web Worker | Millorar async actual | Menys complexitat, Three.js al main thread |
| Backend | Flask rere Apache reverse proxy | CGI inviable per PyMeshLab cold start |
| Skyline resolució | 1mm | Suficient per mm; ≤4M cel·les per caixes 2000mm |
| Angular damping gravetat | 5.0 (actual) | Més estable que 3.0 |
| maxDraw vs maxTry | Separats | maxDraw = render cap, maxTry = volume estimate |
| Orientacio STL (optimitzat) | Gravetat + yaw only | Mes estable i coherent per peces exportades a angles aleatoris |

## Verificació per fase

| Fase | Validació | Estat |
|------|-----------|-------|
| 1 | `displayCount` coincideix a UI, escena 3D, gravetat i PDF. Cap referència a safety factor. | ✅ |
| 2 | STL + alumini → pes estimat a UI i PDF. Volum real vs bounding box etiquetat. | ✅ |
| 3 | STL >50k tri → missatge amb simplificador. Cancel → escena neta. Progrés amb fases + crono. STL simplificada persistent. PDF 2 pàgines. | ✅ |
| 4 | maxTry adaptatiu ✅, caixes plenes fins dalt, InstancedMesh a sync + bulk. | ⏳ |
| 5 | Caixa 600×400×300, peça 100×80×50 → més peces que grid. Cap superposició. | |
| 6 | Gravetat: no s'eleven, cauen suau, vibren. Bulk: drops en files, 3 refills. | |
| 7 | `http://localhost/api/health` → OK. Upload/llistat/eliminació STL funciona. | |
