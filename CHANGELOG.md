# Registre de Canvis - PackAssist

## [2025-08-20] - Refactorització i Implementació de Nous Optimitzadors

### ⚠️ Canvis Importants
- Eliminats optimitzadors antics (optimization.py, bulk_optimizer.py, obb_calculator.py)
- Eliminats fitxers de prova i scripts innecessaris
- Netejada l'estructura del projecte mantenint interfície i funcionalitats
- Creat backup de la carpeta `actiu` com `actiu_backup`
- Afegida carpeta `actiu/src/packassist/optimizers/` per a nous optimitzadors

### ✨ Novetats
- Creat optimitzador de mode normal (`normal_optimizer.py`)
- Implementats algoritmes d'empaquetament: intel·ligent, graella i aleatori
- Afegida verificació de límits i col·lisions
- Implementada separació entre pisos configurable
- Integrat optimitzador de mode normal amb l'aplicació principal
- Creat optimitzador de mode a granel (`bulk_optimizer.py`)
- Implementada simulació física amb PyBullet (opcional)
- Afegit suport per a marge configurable entre peces

### 🛠️ Millores
- Afegida configuració de marge als càlculs d'empaquetament
- Millorada la verificació de posicions vàlides
- Afegits missatges de depuració detallats
- Implementat sistema de fallback quan PyBullet no està disponible
- Afegida configuració de mode de col·lisions

### 📋 Tasques Pendents
- [ ] Provar funcionalitats amb fitxers STL reals
- [ ] Verificar millora en eficiència d'empaquetament
- [ ] Afegir suport per a rotacions i orientacions múltiples

### 📝 Notes de Desenvolupament
- Mantenir compatibilitat amb la interfície existent
- Utilitzar les mateixes signatures de funcions per facilitar la integració
- Implementar verificació de límits i col·lisions
- Afegir suport per a rotacions i orientacions múltiples
- Optimitzar per a rendiment amb malles complexes

---

## Plantilla per a Nous Canvis

### [DATA] - Títol del Canvi

#### ✨ Novetats
- Descripció de les noves funcionalitats

#### 🛠️ Millores
- Descripció de les millores realitzades

#### 🐛 Correccions
- Descripció dels errors corregits

#### 📋 Tasques Pendents
- [ ] Tasca 1
- [ ] Tasca 2