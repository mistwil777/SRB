# 05 — Modélisation IA

## Le problème central : peu de données, trois objectifs

La modélisation, c'est le cœur du projet. Mais elle pose un problème fondamental :

| Variable cible | Fréquence de mesure | Exemples disponibles en 1 an |
|---------------|--------------------|-----------------------------|
| **Rendement** | À la récolte (1x / saison) | 1 à 3 par variété |
| **Résistance** | Après un épisode de stress | Rare et imprévisible |
| **Goût** | Après dégustation (subjectif) | 1 à 3 par variété |

Avec aussi peu de données, un modèle IA classique apprendrait n'importe quoi — ou rien du tout. C'est pour ça qu'on utilise une **approche hybride** : combiner un modèle physique (qui "connaît" déjà la biologie de la pomme de terre) avec une IA qui apprend les écarts par rapport à ce modèle.

---

## 🌱 LINTUL-POTATO — Le modèle physique

### Ce que c'est

LINTUL-POTATO est un **modèle de simulation de la croissance de la pomme de terre**, développé par des chercheurs en agronomie. "LINTUL" signifie "Light INTerception and UtiLization".

C'est un modèle **mécaniste** : il simule la croissance en appliquant des équations issues de la biologie végétale connue — pas des statistiques.

💡 **Analogie :** C'est comme un simulateur de vol. Il ne "prédit" pas qu'un avion va monter parce qu'il a observé des milliers d'avions monter. Il calcule la portance à partir des lois de la physique (Bernoulli, Newton). Si le moteur pousse et que les ailes ont la bonne forme, il monte — mathématiquement.

### Ce que LINTUL-POTATO simule

Il prend en entrée :
- La **radiation solaire** (nos données lux du BH1750)
- La **température** (nos données DHT22)
- L'**humidité du sol** (notre capteur sol)
- La **variété** de pomme de terre (coefficients biologiques)

Et il prédit :
- La **biomasse totale** (racines + tiges + feuilles + tubercules) en g/m²
- Le **rendement** en tubercules
- Le **stade phénologique** (germination, croissance, sénescence)

### La limite du modèle physique

LINTUL-POTATO a été calibré sur des champs agricoles en conditions "normales". Un balcon en ville, c'est différent :
- Sol en pot (pas de terre agricole)
- Réflexion des murs et des vitres (lux différent du plein champ)
- Variétés ornementales ou anciennes non calibrées

C'est là qu'intervient l'IA : apprendre l'**écart entre la prédiction physique et la réalité observée**.

---

## 🤖 Architecture Multi-Head — Les trois têtes

### Vue d'ensemble

```mermaid
flowchart TD
    subgraph ENTREES["Entrées"]
        E1[Donnees capteurs - series temporelles] ;
        E2[Donnees genetiques - variete] ;
        E3[Prediction LINTUL] ;
    end

    TRUNK[Tronc commun - Feature Extractor] ;

    subgraph TETES["Tetes de prediction"]
        H1[Tete 1 - Rendement - regression] ;
        H2[Tete 2 - Resistance - classification] ;
        H3[Tete 3 - Gout - regression] ;
    end

    E1 --> TRUNK ;
    E2 --> TRUNK ;
    E3 --> TRUNK ;
    TRUNK --> H1 ;
    TRUNK --> H2 ;
    TRUNK --> H3 ;

    H1 -->|en grammes| S1[Rendement estime] ;
    H2 -->|probabilite 0-1| S2[Probabilite de survie au stress] ;
    H3 -->|score 1-10| S3[Score gustatif estime] ;
```

### Le tronc commun (Feature Extractor)

C'est la partie partagée du modèle. Elle prend toutes les données en entrée et les compresse en une **représentation interne** — un vecteur de nombres qui encode "l'état de la plante".

💡 **Analogie :** C'est comme le bilan de santé d'un médecin. Avant de te dire si tu risques un infarctus, un diabète ou une dépression, le médecin collecte toutes tes données (poids, tension, bilan sanguin, mode de vie) et les "digère" mentalement. Ce travail de synthèse, c'est le tronc commun.

### Tête 1 — Rendement (régression)

**Question :** "Combien de grammes de tubercules cette plante va-t-elle produire ?"

- **Type de tâche :** Régression (prédire un nombre)
- **Données d'entraînement :** Mesures des capteurs + rendement réel à la récolte
- **Influence de LINTUL :** La prédiction physique est utilisée comme point de départ, la tête apprend le delta (écart)

### Tête 2 — Résistance (classification)

**Question :** "Cette plante va-t-elle survivre à cet épisode de stress ?"

- **Type de tâche :** Classification binaire (oui/non) ou probabilité (0.0 → 1.0)
- **Données d'entraînement :** Épisodes de stress identifiés (canicule, sécheresse) + observation de la plante après
- **Exemple :** Stress détecté (T° > 30 °C pendant 3 jours) → la plante a-t-elle récupéré ou flétri ?

### Tête 3 — Goût (régression)

**Question :** "Quel score gustatif peut-on attendre de ces tubercules ?"

- **Type de tâche :** Régression (score de 1 à 10)
- **Données d'entraînement :** Notes de dégustation subjectives (texture, sucre, arôme)
- **Défi principal :** Très peu de données — voir section suivante

---

## ⚠️ Le problème du déséquilibre — La donnée Goût est rare

C'est le problème le plus important du projet. Si on entraîne les trois têtes ensemble avec la même importance :
- La tête Rendement disposera de centaines de points (une mesure par capteur toutes les 15 min)
- La tête Goût disposera de 2 à 5 points par an

**Résultat sans précaution :** Le modèle optimise pour Rendement et Résistance, et la tête Goût apprend n'importe quoi.

### Solutions mises en place

**1. Fine-tuning séquentiel**

```
Étape 1 : Entraîner le tronc + Tête Rendement sur toutes les données disponibles
          → Le tronc apprend à "comprendre" les conditions de culture

Étape 2 : Geler le tronc (ne plus le modifier)
          Entraîner uniquement la Tête Goût sur les rares données gustatives
          → La tête Goût "hérite" de la compréhension du tronc sans la corrompre
```

**2. Pondération des pertes (loss weights)**

Lors d'un entraînement conjoint, on donne plus d'importance à l'erreur de la tête Goût :

```python
loss_total = (
    1.0 * loss_rendement
    + 2.0 * loss_resistance
    + 5.0 * loss_gout        # × 5 car données rares
)
```

**3. Data Augmentation pour la tête Goût**

On génère des variantes artificielles des rares observations disponibles :
- Légère variation aléatoire des conditions (±5 % humidité, ±1 °C)
- Interpolation entre deux observations proches
- Bruit gaussien sur les scores de dégustation

---

## 📚 RAG + ChromaDB — La base de connaissances scientifiques

### Ce qu'est le RAG

RAG signifie **Retrieval-Augmented Generation**. C'est une technique qui permet à un système d'IA d'aller chercher de l'information dans une base documentaire avant de répondre.

Dans notre projet, on n'utilise pas le RAG pour "répondre à des questions" mais pour **enrichir les entrées du modèle** avec des connaissances publiées sur la pomme de terre.

💡 **Analogie :** Imagine un médecin qui, avant de te donner un diagnostic, consulte la base de données PubMed pour trouver les articles scientifiques les plus pertinents sur tes symptômes. Le RAG, c'est ce mécanisme de consultation automatique.

### ChromaDB — La bibliothèque vectorielle

ChromaDB est une base de données spécialisée dans le stockage de **vecteurs** (tableaux de nombres). Ces vecteurs représentent le "sens" d'un texte, encodé par un modèle de langage.

```
Article scientifique → Modèle d'encodage → Vecteur de 768 nombres → ChromaDB
```

Quand le modèle cherche des informations sur "effet de la sécheresse sur la qualité des tubercules", ChromaDB trouve les articles dont le **sens** est proche — même s'ils n'utilisent pas exactement ces mots-là.

### Ce que contient notre RAG

- Publications scientifiques sur LINTUL-POTATO
- Articles sur la phénologie de la pomme de terre (stades de croissance)
- Études sur l'effet du stress hydrique sur le goût
- Données variétales (coefficients biologiques par variété)

---

## 🧮 PyTorch — Le moteur du deep learning

### Ce que c'est

PyTorch est la bibliothèque Python de référence pour le deep learning. Elle fournit :
- Les **tenseurs** : des matrices multidimensionnelles optimisées pour le calcul
- La **différentiation automatique** : le calcul automatique des gradients pour l'entraînement
- Des couches de réseaux neuronaux prêtes à l'emploi

💡 **Analogie :** PyTorch, c'est le moteur d'une voiture. On ne le voit pas directement, mais tout le reste (le modèle Multi-Head) tourne grâce à lui. On n'a pas besoin de savoir comment il fonctionne en détail pour conduire — mais il faut savoir qu'il est là et qu'il consomme de la mémoire GPU (ou CPU dans notre cas).

### Sans GPU NVIDIA

Notre modèle Multi-Head sera entraîné sur **CPU**. C'est plus lent, mais :
- Notre dataset sera petit (quelques centaines de points max par variété)
- On n'entraîne qu'une seule fois, pas en continu
- Avec dask pour paralléliser les simulations LINTUL, le CPU i7-1260P à 12 cœurs est suffisant

---

## 🔀 dask — Paralléliser les simulations

### Ce que c'est

Dask est une bibliothèque Python qui permet de paralléliser des calculs sur plusieurs cœurs CPU.

### À quoi ça sert ici ?

Le simulateur LINTUL-POTATO peut être lancé des centaines de fois avec des paramètres différents (pour tester différentes variétés, différentes conditions). Sans parallélisation, ces simulations seraient séquentielles et lentes. Avec dask, on les lance toutes en parallèle sur les 12 cœurs du i7-1260P.

```python
import dask

# Lancer 100 simulations en parallèle
resultats = dask.compute(*[simuler(variete, conditions) for variete in varietes])
```

---

## 🌱 Philosophie : un modèle qui grandit

### Résilience d'abord, richesse ensuite

Le modèle démarre intentionnellement avec peu de capteurs et des données bruitées. Ce n'est pas une contrainte — c'est un choix de conception.

Un modèle entraîné sur des signaux imparfaits apprend à **inférer** plutôt qu'à **lire**. Il développe une compréhension des patterns sous-jacents (stress hydrique, canicule, déficit lumineux) plutôt qu'une dépendance à des mesures précises. C'est ce qui le rend robuste dans le monde réel, où les capteurs tombent en panne, dérivent, ou simplement n'existent pas chez tout le monde.

### La roadmap d'enrichissement

```mermaid
flowchart LR
    P1["Phase 1\nSol + DHT22 + Lux\nfondation bruitee"] -->
    P2["Phase 2\n+ pH\nchimie du sol"] -->
    P3["Phase 3\n+ EC / NPK\nnutriments"] -->
    P4["Phase n\n+ nouvelles varietes\n+ autres sites"] ;
```

À chaque phase, le modèle découvre une nouvelle dimension — sans oublier ce qu'il a appris avant.

### Le problème de l'oubli catastrophique

C'est le principal écueil du continual learning. Quand on ré-entraîne un réseau de neurones sur de nouvelles données, il tend à **écraser les anciens apprentissages** au profit des nouveaux. Un modèle qui a appris à prédire le rendement depuis 3 capteurs peut "oublier" ce savoir en apprenant le pH.

Trois mécanismes de protection sont prévus dans l'architecture :

**1. Entrées optionnelles avec masquage**

Le tronc commun est dimensionné dès le départ pour la liste complète des features possibles. Les features absentes sont masquées à zéro — le modèle apprend à les ignorer proprement.

```python
# Vecteur d'entrée : features connues + features futures masquées
input  = [0.45,  22.1,  58.0,  12450.0,  0.0,  0.0,  0.0,  0.0 ]
mask   = [1,     1,     1,     1,        0,    0,    0,    0   ]
#         sol    T°     HR     lux       pH    EC    NPK_N NPK_P

# Quand le pH est branché : on passe son masque à 1, on fine-tune
```

Cela signifie que le modèle Phase 1 et le modèle Phase 3 partagent exactement la même architecture. On n'a pas à tout reconstruire.

**2. EWC — Elastic Weight Consolidation**

Quand on ajoute une nouvelle source de données, certains poids du réseau sont **protégés** (ceux qui ont le plus contribué aux prédictions passées) et d'autres sont libres de s'adapter. Le modèle garde sa mémoire fondatrice intacte.

💡 **Analogie :** C'est comme apprendre une deuxième langue. Les zones du cerveau qui traitent la grammaire et la logique (le tronc commun) restent intactes. Seul le vocabulaire (les poids spécifiques à la nouvelle langue) change.

**3. Fine-tuning séquentiel par tête**

Lors de l'ajout d'un nouveau capteur, on ne ré-entraîne que les couches d'entrée et éventuellement une tête spécifique. Le tronc est gelé sauf si les nouvelles données apportent une information vraiment nouvelle.

### Ce qu'on prépare dès maintenant dans la config

```yaml
# config/settings.yaml
features:
  active:
    - soil_moisture   # Phase 1
    - temp_air        # Phase 1
    - humidity_air    # Phase 1
    - lux             # Phase 1
  planned:
    - ph              # Phase 2 — quand le capteur sera branché
    - ec              # Phase 3
    - npk_n           # Phase 3
    - npk_p           # Phase 3
    - npk_k           # Phase 3
```

Basculer une feature de `planned` à `active` suffit à l'activer dans le pipeline. Le reste du code n'a pas à changer.

### Tracer l'évolution du modèle dans le temps

À chaque nouvelle phase d'entraînement, on documente dans `data/models/` :

```
data/models/
├── v1_3capteurs_2026-06/       ← fondation
│   ├── trunk.pt
│   ├── head_yield.pt
│   └── metrics.json            ← RMSE, ratio N_taste/N_yield, etc.
├── v2_ph_2026-10/              ← après ajout pH
│   └── ...
```

Cela permet de comparer les performances avant/après chaque enrichissement et de **revenir en arrière** si une nouvelle source de données dégrade les prédictions existantes.
