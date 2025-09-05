# Qwen Code - Documentació per a l'Agent IA

## Propòsit
Aquest document proporciona instruccions detallades per a l'agent IA Qwen Code per treballar amb el projecte PackAssist de manera eficient i efectiva.

## Projecte PackAssist
PackAssist és una aplicació 3D de packaging optimization dissenyada per calcular quants objectes caben dins d'una caixa de manera òptima. L'aplicació suporta:
- Importació de models 3D en format STL
- Simplificació de malles
- Configuració de dimensions de caixa
- Càlcul d'empaquetament òptim
- Visualització 3D dels resultats

## Estructura del Projecte
```
SOME-PackagingAssistant/
├── actiu/                 # Codi font actiu
│   └── src/
│       └── packassist/
│           ├── core/       # Nucli del sistema
│           ├── gui/        # Interfície gràfica
│           ├── optimizers/ # Optimitzadors
│           └── utils/     # Utilitats
├── proves/                # Scripts de prova
├── documentacio/          # Documentació
└── stls/                  # Fitxers STL de prova
```

## Instruccions per a l'Agent IA

### 1. Creació de Llista TO DO
Quan identifiquis tasques a realitzar, crea sempre una llista TO DO estructurada:

```
# TO DO LIST - Nom del Component

## PROBLEMES IDENTIFICATS:
1. [ ] Tasca 1 - Descripció breu
2. [ ] Tasca 2 - Descripció breu

## PENDENT DE VERIFICACIÓ:
3. [ ] Tasca 3 - Descripció breu
4. [ ] Tasca 4 - Descripció breu
```

### 2. Treball Progressiu
Treballa les tasques **una per una** en ordre de prioritat:
1. Identifica el problema
2. Analitza el codi existent
3. Implementa la solució
4. Verifica que funciona
5. Marca com a completada

### 3. No Marcar Com a Fet Prematurament
NOMÉS marca una tasca com a completada quan:
- El codi està implementat
- S'ha verificat que funciona
- L'usuari ha confirmat que és correcte

### 4. Mantenir Context
Mantingues sempre el context del projecte i les seves convencions:
- Segueix l'estil de codi existent
- Mantingues la compatibilitat amb components existents
- Utilitza les mateixes biblioteques i tecnologies

## Convencions de Codificació

### Estil de Codi
- Utilitza indentació de 4 espais
- Noms de variables en anglès
- Comentaris en català per a funcions públiques
- Segueix el patró docstring de Google per a documentació

### Nomenclatura de Fitxers
- `snake_case.py` per a fitxers Python
- `PascalCase.py` per a classes principals
- `lowercase_with_underscores` per a funcions

### Importacions
- Ordre: Biblioteques estàndard, biblioteques de tercers, mòduls locals
- Utilitza imports absoluts quan sigui possible

## Flux de Treball Recomanat

### 1. Anàlisi
Abans de fer qualsevol canvi:
```
1. read_file() - Examina el codi existent
2. search_file_content() - Cerca patrons i dependències
3. run_shell_command() - Verifica l'estat actual
```

### 2. Implementació
Quan implementis canvis:
```
1. write_file() - Crea nous fitxers
2. replace() - Modifica fitxers existents
3. run_shell_command() - Prova els canvis
```

### 3. Verificació
Després d'implementar:
```
1. run_shell_command() - Executa proves
2. Demana confirmació a l'usuari
3. Corregeix errors si cal
```

## Biblioteques Clau

### Trimesh
- Processament de malles 3D
- Càlcul de bounding boxes
- Operacions geomètriques

### PyVista
- Visualització 3D
- Representació de malles i escenes

### NumPy
- Càlculs numèrics
- Operacions amb matrius i vectors

### Open3D (Opcional)
- Càlcul d'OBB avançat
- Optimització geomètrica

## Problemes Comuns i Solucions

### ImportError
Quan hi ha errors d'importació:
1. Verifica que el fitxer existeix
2. Comprova el path d'importació
3. Assegura't que el `__init__.py` està correcte

### SyntaxError
Quan hi ha errors de sintaxi:
1. Verifica cometes i caràcters especials
2. Comprova indentació
3. Assegura't que no hi ha caràcters escapats incorrectament

### RuntimeError
Quan hi ha errors d'execució:
1. Verifica que les dependències estan instal·lades
2. Comprova que els paths són correctes
3. Assegura't que les dades d'entrada són vàlides

## Exemple de Sessió de Treball

### Identificació de Problema
```
Usuari: "El visualitzador 3D no funciona"
Agent: Crea una llista TO DO identificant el problema
```

### Anàlisi
```
1. read_file() - Examina els fitxers de visualització
2. search_file_content() - Cerca errors i dependències
3. run_shell_command() - Prova l'aplicació
```

### Implementació
```
1. replace() - Corregeix errors identificats
2. write_file() - Crea scripts de prova
3. run_shell_command() - Verifica els canvis
```

### Verificació
```
1. Demana a l'usuari que provi l'aplicació
2. Corregeix qualsevol error addicional
3. Marca la tasca com a completada
```

## Millors Pràctiques

### Documentació
- Documenta tota funció pública amb docstrings
- Afegeix comentaris per a codi complex
- Mantingues el README actualitzat

### Proves
- Crea scripts de prova per a noves funcionalitats
- Verifica la compatibilitat amb versions anteriors
- Prova amb diferents tipus de fitxers d'entrada

### Seguretat
- No exposis ni commetis secrets
- Verifica paths abans d'utilitzar-los
- Gestiona errors adequadament

## Contacte i Suport
Per a qualsevol dubte o problema:
- Consulta la documentació a `documentacio/`
- Revisa els scripts de prova a `proves/`
- Contacta amb l'equip de desenvolupament

---
*Aquest document està actualitzat per reflectir l'estat actual del projecte i les millors pràctiques recomanades.*