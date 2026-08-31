# MP3 Cutter — Especificació inicial

## 1. Objectiu

Crear una aplicació d'escriptori per a Windows extremadament senzilla per editar fitxers MP3.

L'aplicació **no pretén ser un editor d'àudio complet** com Audacity. La seva única finalitat és permetre obrir un MP3, marcar punts de tall i generar diferents fragments del mateix àudio de manera ràpida.

La prioritat és:

1. Simplicitat.
2. Rapidesa.
3. Interfície visual clara.
4. Precisió suficient per a talls de música.
5. Consum reduït de recursos.
6. Poder empaquetar-la com a `.exe` amb PyInstaller.

---

## 2. Tecnologies proposades

- **Python 3.12+**
- **PySide6** per a la interfície gràfica.
- **FFmpeg** per a lectura, conversió i exportació d'àudio.
- **NumPy** per al processament necessari per generar la waveform.
- **Qt Multimedia / QAudioSink** o una alternativa equivalent per a la reproducció.
- **PyInstaller** per generar l'executable de Windows.

Sempre que sigui possible, evitar dependències innecessàries.

### Principi important

FFmpeg hauria de ser el motor d'àudio principal.

No cal implementar manualment la descodificació o codificació MP3.

---

# 3. Funcionalitat principal

## 3.1 Obrir un MP3

Botó principal:

**Obrir MP3**

En seleccionar un fitxer:

- carregar l'àudio;
- obtenir durada;
- generar una representació visual de la waveform;
- mostrar el nom del fitxer;
- preparar-lo per a reproducció i edició.

Formats inicials:

- `.mp3`

Opcionalment es pot preparar l'arquitectura per admetre posteriorment:

- `.wav`
- `.m4a`
- `.ogg`
- `.flac`

Però la primera versió ha d'estar centrada en MP3.

---

# 4. Waveform

La part central de la finestra ha de mostrar una representació visual de l'àudio.

Exemple conceptual:

```text
        ▂▃▅▇████▇▅▃▂       ▂▅█████▇▅▃▂
   ▂▅██████████████▇▅▂▃▅██████████████▇▅
────────────────────────────────────────────
0:00                 2:15                 4:30
```

Característiques:

- visualització horitzontal;
- escala temporal;
- cursor de reproducció;
- marques de tall;
- zona seleccionada visualment;
- possibilitat de fer clic sobre la waveform per situar el cursor.

No cal una waveform d'estudi professional.

Ha de ser **lleugera i ràpida de renderitzar**.

Per fitxers llargs, utilitzar una versió reduïda de les mostres (peak/RMS aggregation) en lloc de dibuixar cada sample.

---

# 5. Reproducció

Controls mínims:

- ▶ Reproduir
- ⏸ Pausar
- ⏹ Aturar

També seria útil:

- cursor de reproducció que avança sobre la waveform;
- temps actual;
- durada total.

Exemple:

```text
00:02:34.250 / 00:05:48.000
```

En clicar sobre la waveform, la reproducció ha de poder saltar directament a aquella posició.

---

# 6. Sistema de talls

Hi ha d'haver dues maneres senzilles de crear fragments.

## 6.1 Selecció inici/final

L'usuari pot definir:

```text
Inici:  00:01:32.000
Final:  00:02:47.000
```

La zona seleccionada queda ressaltada visualment.

Botó:

**Afegir tros**

Això afegeix la selecció a la llista de fragments.

---

## 6.2 Dividir en el cursor

Aquesta hauria de ser una de les funcions principals.

L'usuari situa el cursor en qualsevol punt:

```text
────────────────────●────────────────────
                  02:34
```

I prem:

**Dividir aquí**

El programa crea un tall en aquest punt.

Per exemple:

```text
0:00          1:25          2:48          4:03          5:17
 │─────────────│─────────────│─────────────│─────────────│
      Tros 1        Tros 2        Tros 3        Tros 4
```

Això permet dividir una cançó en molts fragments molt ràpidament.

---

# 7. Llista de fragments

A la part inferior o lateral mostrar els fragments creats.

Exemple:

```text
FRAGMENTS

┌──────────────────────────────────────────────┐
│ 1   00:00 → 01:25       [▶] [✕]             │
│ 2   01:25 → 02:48       [▶] [✕]             │
│ 3   02:48 → 04:03       [▶] [✕]             │
│ 4   04:03 → 05:17       [▶] [✕]             │
└──────────────────────────────────────────────┘
```

Cada fragment hauria de permetre:

- reproduir-lo;
- eliminar-lo;
- seleccionar-lo;
- opcionalment canviar el nom.

---

# 8. Exportació

Botó principal:

**Exportar fragments**

El programa ha de permetre seleccionar una carpeta de destinació.

Els fitxers es poden generar automàticament:

```text
canço_01.mp3
canço_02.mp3
canço_03.mp3
canço_04.mp3
```

Opcionalment:

```text
canço_01.mp3
canço_02.mp3
...
```

amb un patró configurable.

---

# 9. Qualitat d'àudio

Aquesta part és important.

Quan sigui possible, utilitzar **stream copy** amb FFmpeg per evitar recodificar l'MP3:

```text
MP3 original
     │
     ├── fragment 1 ──► MP3
     ├── fragment 2 ──► MP3
     └── fragment 3 ──► MP3
```

Avantatges:

- molt ràpid;
- no hi ha una nova pèrdua de qualitat;
- menor ús de CPU.

Tanmateix, els talls amb `-c copy` poden no ser sample-perfect a causa dels límits dels frames MP3.

Per això es pot contemplar una segona opció:

**Precisió màxima**

que faci re-encode del fragment.

La primera versió pot començar amb stream copy i deixar el mode precís per a una versió posterior si realment és necessari.

---

# 10. Interfície d'usuari

La interfície ha de ser **minimalista**.

No volem:

- mesclador;
- equalitzador;
- efectes;
- compressors;
- plugins;
- pistes múltiples;
- espectrograma;
- gravació;
- eines professionals d'àudio;
- centenars d'opcions.

L'aplicació ha de tenir una funció clara:

> **Obrir → escoltar → marcar talls → exportar**

---

# 11. Disseny proposat

```text
┌──────────────────────────────────────────────────────────────┐
│ MP3 Cutter                                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ [ Obrir MP3 ]     canço.mp3                                 │
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │       ▂▅████▇▅▃     ▂▃▅██████▇▅▃                       │ │
│ │   ▂▅███████████▇▅▂▃▅█████████████▇▅▂                   │ │
│ │──────────────────────●──────────────────────────────────│ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ 00:02:34.250                              00:05:48.000       │
│                                                              │
│ [▶ Reproduir] [⏸ Pausar] [⏹ Aturar]                        │
│                                                              │
│ [✂ Dividir aquí]                                             │
│                                                              │
│ FRAGMENTS                                                    │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 1  00:00 → 01:25                       [▶] [✕]           │ │
│ │ 2  01:25 → 02:48                       [▶] [✕]           │ │
│ │ 3  02:48 → 04:03                       [▶] [✕]           │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│                                  [ EXPORTAR FRAGMENTS ]       │
└──────────────────────────────────────────────────────────────┘
```

El disseny visual concret pot evolucionar, però **la simplicitat ha de ser una prioritat de producte**.

---

# 12. Precisió dels talls

Internament, les posicions s'han de gestionar amb precisió suficient, preferiblement en segons amb decimals o en samples quan sigui necessari.

Exemple:

```text
00:02:34.250
```

No limitar les posicions a segons enters.

A la interfície, però, no cal mostrar una precisió excessiva si no aporta valor.

Es podria mostrar:

```text
02:34.250
```

i permetre introduir manualment el temps si l'usuari vol precisió.

---

# 13. Arrossegar fitxer

Comoditat recomanada:

Permetre **drag & drop** d'un MP3 sobre la finestra.

```text
       ┌──────────────────────────┐
       │                          │
       │    ARROSSEGA UN MP3      │
       │         AQUÍ             │
       │                          │
       └──────────────────────────┘
```

Això hauria de ser equivalent a prémer "Obrir MP3".

---

# 14. Funcionament amb fitxers llargs

L'aplicació ha de funcionar també amb MP3 llargs.

Evitar carregar l'àudio complet descomprimit a memòria si no és necessari.

Especialment per a la waveform:

- extreure una representació reduïda;
- treballar amb blocs;
- mantenir baix el consum de RAM.

La reproducció i l'exportació han de poder funcionar mitjançant FFmpeg sense mantenir tot l'àudio PCM en memòria.

---

# 15. Gestió d'errors

Errors que cal controlar:

- fitxer no vàlid;
- MP3 corrupte;
- FFmpeg no disponible;
- falta d'espai al disc;
- error d'escriptura;
- format no compatible;
- fitxer de destinació ja existent.

Els errors s'han de mostrar amb missatges senzills i comprensibles.

Exemple:

> No s'ha pogut obrir el fitxer MP3.

No mostrar excepcions Python a l'usuari final.

---

# 16. Configuració

La primera versió ha de tenir **molt poca configuració**.

Com a màxim:

- carpeta d'exportació;
- patró de nom dels fragments;
- mode de tall:
  - ràpid (stream copy);
  - precís (re-encode), si s'implementa.

No crear una pantalla de configuració complexa.

---

# 17. Portable / Windows

Objectiu final:

```text
MP3Cutter.exe
```

Idealment l'usuari no hauria d'haver d'instal·lar Python.

Utilitzar:

**PyInstaller**

per crear l'executable.

FFmpeg s'hauria de distribuir amb l'aplicació o integrar-lo de manera que l'usuari no hagi de configurar manualment el PATH.

---

# 18. Arquitectura recomanada

Separar mínimament la lògica:

```text
mp3_cutter/
│
├── main.py
├── ui/
│   ├── main_window.py
│   └── waveform_widget.py
│
├── audio/
│   ├── ffmpeg.py
│   ├── playback.py
│   └── waveform.py
│
├── models/
│   └── segment.py
│
└── resources/
    └── ffmpeg/
```

No cal sobrearquitecturar el projecte.

L'objectiu és que sigui fàcil de mantenir.

---

# 19. Model de dades dels fragments

Cada fragment podria tenir una estructura similar a:

```python
Segment(start=92.000, end=167.250, name="canço_01")
```

La llista completa:

```text
[
    Segment(0, 85),
    Segment(85, 168),
    Segment(168, 243),
    Segment(243, 317)
]
```

A partir d'aquesta informació FFmpeg genera els fitxers finals.

---

# 20. MVP — Primera versió

La primera versió funcional hauria d'incloure NOMÉS:

### Entrada
- Obrir MP3.
- Drag & drop.

### Visualització
- Waveform.
- Durada.
- Cursor.

### Reproducció
- Play.
- Pause.
- Stop.
- Saltar a una posició.

### Edició
- Dividir aquí.
- Crear fragments.
- Eliminar fragments.

### Exportació
- Exportar tots els fragments.
- Noms automàtics.
- Selecció de carpeta.

### Qualitat
- Stream copy sempre que sigui possible.

---

# 21. Funcions per a versions posteriors

No implementar-les inicialment, però deixar l'arquitectura preparada:

- Zoom de waveform.
- Precisió sample-level.
- Re-encode precís.
- Selecció manual inici/final.
- Renombrar fragments.
- Reordenar fragments.
- Exportar només fragments seleccionats.
- Normalització de volum.
- Fade in/out molt bàsic.
- Suport WAV/M4A/OGG/FLAC.
- Guardar/carregar un projecte de talls.

---

# 22. Filosofia del projecte

Aquest punt és especialment important per als desenvolupadors.

**No convertir l'aplicació en un editor d'àudio generalista.**

El valor del programa és precisament que faci molt bé una tasca concreta:

> **Tallar un MP3 en diversos trossos de la manera més ràpida i senzilla possible.**

Si una funcionalitat no és necessària per a aquesta tasca, probablement no s'ha d'afegir.

La interfície ha de permetre que una persona que no sap utilitzar Audacity pugui obrir el programa i començar a tallar una cançó immediatament.

---

# 23. Criteri d'èxit

Considerarem que la primera versió compleix l'objectiu si un usuari pot:

1. Obrir un MP3.
2. Veure'n la waveform.
3. Reproduir-lo.
4. Fer clic on vol tallar.
5. Prémer **Dividir aquí**.
6. Repetir-ho diverses vegades.
7. Veure els fragments resultants.
8. Prémer **Exportar fragments**.
9. Obtenir els MP3 individuals.

Tot això sense haver de configurar res ni entendre conceptes d'edició d'àudio.

---

## Resum : utilitzar el entorn Conda que tenim creat

**Python + PySide6 + FFmpeg + NumPy + PyInstaller**

Una aplicació Windows petita, ràpida i enfocada exclusivament a:

**OBRIR → REPRODUIR → DIVIDIR → EXPORTAR**

La simplicitat no és una limitació accidental: és la característica principal del producte.
