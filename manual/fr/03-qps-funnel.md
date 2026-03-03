# Chapitre 3 : Comprendre votre entonnoir QPS

*Public visé : acheteurs média, gestionnaires de campagnes*

Il s'agit de la page d'accueil de Cat-Scan (`/`). Tout commence ici.

## Ce que vous voyez

La page QPS Waste Optimizer affiche votre entonnoir RTB (le parcours de la
demande d'enchère à la dépense) et met en évidence les points de déperdition
du volume.

![Page d'accueil du QPS Waste Optimizer](images/screenshot-qps-home.png)

### L'entonnoir

| Étape | Signification |
|-------|---------------|
| **QPS** | Le nombre maximal de demandes d'enchères par seconde que vous demandez à Google d'envoyer. Google régule le volume réel en fonction du niveau de votre compte, vous recevez donc généralement moins que votre plafond. |
| **Bids (Enchères)** | Combien de ces demandes votre enchérisseur a choisi d'enchérir. Les autres ont été rejetées (inventaire inadapté, pas de création correspondante, prix plancher non atteint). |
| **Wins (Victoires)** | Enchères remportées par votre enchérisseur. Vous ne payez que pour les victoires. |
| **Impressions** | Publicités effectivement diffusées aux utilisateurs après avoir remporté l'enchère. |
| **Clicks (Clics)** | Interactions des utilisateurs avec vos publicités diffusées. |
| **Spend (Dépenses)** | Montant total dépensé pour les impressions remportées. |

L'écart entre chaque étape représente une opportunité d'optimisation. Une chute
importante entre QPS et Bids signifie que votre enchérisseur rejette la majeure
partie de ce que Google envoie — un gaspillage classique que le préciblage peut
corriger.

### Indicateurs clés

- **Taux de victoire (Win rate)** : Wins / Bids. Mesure la compétitivité de vos enchères.
- **CTR** : Clicks / Impressions. Mesure l'attractivité de vos créations.
- **CPM** : Coût pour mille impressions. Ce que vous payez pour la visibilité.
- **Ratio de gaspillage (Waste ratio)** : (QPS - Bids) / QPS. La part du trafic que vous ne pouvez pas exploiter.

### Cartes de configuration de préciblage

Sous l'entonnoir, vous verrez des cartes pour chacune de vos configurations
de préciblage (jusqu'à 10 par siège). Chaque carte affiche :

- **État** : Active ou Suspendue
- **Max QPS** : Le plafond de demandes d'enchères acceptées par cette configuration
- **Formats** : VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE
- **Plateformes** : DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV
- **Zones géographiques** : Cibles géographiques incluses et exclues
- **Formats publicitaires** : Formats inclus (ou tous si non filtrés)

### Contrôles

- **Sélecteur de période** : 7, 14 ou 30 jours de données
- **Filtre de siège** : limiter à un siège acheteur spécifique
- **Basculement de configuration** : accéder au détail d'une configuration de préciblage spécifique

## Comment lire cette page

Commencez par le ratio de gaspillage. S'il dépasse 50 %, vous avez une marge
d'amélioration significative. Regardez ensuite quelles configurations contribuent
le plus au gaspillage. Cliquez sur les analyses par dimension
([Géographie](04-analyzing-waste.md), [Éditeur](04-analyzing-waste.md),
[Format](04-analyzing-waste.md)) pour identifier les sources précises.

## En lien

- [Analyser le gaspillage par dimension](04-analyzing-waste.md) : approfondir
  par zone géographique, éditeur et format
- [Configuration de préciblage](06-pretargeting.md) : agir sur vos constats
