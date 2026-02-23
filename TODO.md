# TODO (PackAssist)

Llista de coses a polir. Prioritzat per impacte a UX/correctesa.  
Última actualització: 2026-02-13

---

## Prioritat ALTA — Correctesa i estabilitat del sistema

### Responsivitat (evitar "not responding")
- [ ] **Web Worker per mode optimitzat**: moure el bucle pesat de `addPackedSTLHeightMap()` a un worker dedicat (`web/js/workers/packing-worker.js`). Mantenir Three.js al main thread.
- [x] **Cancel·lació explícita**: botó "Cancel" al costat de la barra de progrés. Usar `AbortController` end-to-end; `worker.terminate()` al cancel·lar.
- [ ] **InstancedMesh per a altes quantitats**:
  - Mode optimitzat: `THREE.InstancedMesh` en lloc de clonar `THREE.Mesh` per cada peça.
  - Mode a granel: un `InstancedMesh` per tipus de peça (cuboid/STL); actualització de matrius en lots (≤1k/frame) a `physics-world.js`.
- [x] **Guia per STL complexes**: detectar triangle count >50k a càrrega; mostrar missatge amb enllaç al simplificador existent (cap auto-simplificació silenciosa).

### Densitat (STL heightmap) — caixes mig buides
- [x] **Millorar densitat real en heightmap**: eliminat sistema BVH que causava col·lisions falses.
  - Eliminat BVH collision check (causava resultats inconsistents entre simplificacions).
  - Heightmap pur: determinístic, sense dependència de topologia de malla.
  - `maxTry` adaptatiu (volum caixa / volum peça × 1.2, cap 2000).
  - Caixes grans ja no donen menys peces que caixes petites.

### Algoritme d'empaquetatge (mode optimitzat) — densitat real
- [x] **Eliminar safety factor**: esborrar tota la lògica de safety factor (ja no és útil; era només per proves).
- [ ] **Millorar aprofitament vertical**:
  - Actualment deixa 20%+ d'espai lliure a la part superior o resultats absurds (8 peces en caixa de 150).
  - Substituir heurística actual per **Skyline-based layering** amb footprint real (polígon 2D offset per gap).
  - Validació d'estabilitat amb **LBCP** (Load-Bearable Convex Polygon) per evitar revalidació global.
- [x] **Orientacio estable per defecte (gravetat + yaw)**:
  - Drop fisic amb Rapier per trobar la pose estable.
  - Provar yaw cada 30 graus sobre la base estable.
  - Evitar que les peces quedin perpendiculars o flotant per export angles.
  - Precomputar orientacio en càrrega/simplificació/historial per accelerar càlculs repetits.
  - Mostrejar múltiples bases estables i avaluar-les al càlcul (no dependre d'una sola base).

### Volum real de la peça STL
- [x] Calcular volum real amb tetraedres signats (`computeMeshVolume(geometry)` a `mesh-utils.js`).
- [x] Usar volum real per:
  - "Unitats teòriques màximes" → `Math.floor(volBox / volReal)`.
  - Eficiència volumètrica → `(count × volReal) / volBox × 100`.
  - Pes estimat → `volReal × densitat_material`.
- [x] Afegir selector de material (alumini 2700, acer 7850, plàstic 1200 kg/m³) a la UI.
- [x] Propagar dades al `report-generator.js` (PDF).
- [x] **Limitador de pes usa pes per material**: quan es selecciona un material, el pes per peça es calcula de `densitat × volum` i s'usa al limitador (`calcularEmpaquetatge`), no només per display.
- [x] **Actualització en viu del pes**: canviar material/densitat/sòlid-buit/gruix recalcula el camp de pes automàticament.

### Coherència del recompte
- [x] Una sola font de veritat (`displayCount`) per:
  - Resultats mostrats a la UI.
  - Peces renderitzades (`lastPlacement.positions` limitat a `displayCount`).
  - Simulació de gravetat.
  - Informe PDF.

---

## Prioritat ALTA — Simulació física

### Gravetat (mode optimitzat)
- [ ] **No aixecar peces**: `dropLiftY = 0` (mantenir posicions del grid).
- [ ] **Bloquejar rotacions inicials**: `lockRotations = true` durant caiguda; alliberar només després de contacte estable.
- [ ] **Vibració + settling**: 5–6s de vibració desfasada (parets amb fases diferents) després de la caiguda.
- [ ] **Massa real**: `density = pieceWeight / volReal` per al RigidBody.
- [ ] **Damping alt**: `linearDamping: 2.0`, `angularDamping: 3.0` per evitar rebots.

### Densitat mode a granel
- [ ] **Drop en capes organitzades**: no una a una; files senceres amb spacing.
- [ ] **Múltiples cicles de refill** (2–3 en lloc d'1).
- [ ] **Lid press intermedi**: compactació suau després de cada cicle.
- [ ] **Vibració desfasada**: parets amb offsets independents (`phaseX`, `phaseY`, `phaseZ` diferents).
- [ ] **Criteri de saturació millorat**: basar-se en % de volum ocupat vs. teòric, no només en `maxStagnantDrops`.

---

## Prioritat MITJANA

### Simplificació de malla
- [x] Permetre ratios <1% al slider (fins a 0.1%).
- [x] **Desar la STL simplificada quan s'aplica**: si l'usuari aplica simplificació, la STL guardada a l'historial passa a ser la versió simplificada (no l'original pesada).
- [ ] Integrar `mesh_server.py` al `server.py` principal com a ruta `/api/simplify` (evitar systemd/nginx addicional).
- [ ] Documentar instal·lació de PyMeshLab al README.

### Algoritme d'empaquetatge
- [ ] **Orientacions mixtes dins la mateixa caixa**: permetre barrejar variants (ex: algunes 0°, altres 90°) per omplir buits residuals.
- [ ] **Cachejar geometria**: BVH, variants yaw i footprint offset per evitar recàlculs redundants.

### Informes PDF
- [ ] Corregir volum usat (bounding box → volum real).
- [ ] Verificar que el count al PDF coincideixi amb `displayCount`.
- [ ] Validar que les captures isomètriques reflecteixin l'estat final renderitzat.
- [x] Evitar pàgina extra en blanc (3a pàgina) al PDF.

---

## Prioritat BAIXA

### UX
- [x] Barra de progrés amb fases clares: "Preparant geometria", "Provant orientacions", "Col·locant peces" (sense salt inicial irreal).
- [x] Temps de càlcul: mostrar cronòmetre al progrés i log de temps a consola.
- [x] Eliminar emojis decoratius de resultats (mantenir només avisos/errors com ⚠️).
- [x] Admin: afegit panell de comprovació de pes (sòlida/buida, densitat, gruix paret, quantitat).
- [x] Afegit check de malla tancada/fuites (watertight, boundary edges, non-manifold) a admin i estat STL.
- [ ] Missatges d'error útils: "STL massa complexa: simplifica-la abans", "Cap peça cap a la caixa".
- [ ] Historial: desar orientació final i `displayCount` real.

### Qualitat de codi
- [ ] Proves de regressió per:
  - Coherència de `displayCount` (UI/render/gravetat/PDF).
  - Neteja d'estat al cancel·lar (worker, escena).
  - No superposicions ni sobresortides en mode optimitzat.

### Update README.md
- [ ] Actualitzar el readme quan es fan canvis