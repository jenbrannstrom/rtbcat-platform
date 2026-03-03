# Chapitre 10 : Lire vos rapports

*Public : acheteurs media, responsables de campagne*

Ce chapitre explique les panneaux d'analyse de Cat-Scan et comment interpreter les chiffres.

## Statistiques de depenses

Disponibles sur la page d'accueil et dans les vues detaillees par configuration.

| Metrique | Ce qu'elle vous indique |
|----------|------------------------|
| **Depenses totales** | Depenses brutes sur la periode et le seat selectionnes. |
| **Tendance des depenses** | Periode recente vs. periode precedente. Des depenses en hausse avec des gains stables = inflation des couts. |
| **Depenses par configuration** | Quelle configuration de pretargeting est responsable de quelle part des depenses. Aide a identifier les configurations a optimiser en priorite. |

## Performance des configurations

Montre comment chaque configuration de pretargeting a performe dans le temps.

- **Ventilation quotidienne** : impressions, clics, depenses, taux de gain, CTR
  et CPM par configuration sur la periode selectionnee.
- **Courbes de tendance** : reperer les configurations dont la performance se degrade.
- **Ventilation par champ** : quels champs specifiques (zones geo, tailles, formats) au sein d'une
  configuration sont a l'origine des chiffres.

## Efficacite des endpoints

Affiche l'utilisation du QPS par endpoint de bidder.

- **Ratio d'efficacite** : QPS utile / QPS total. Plus il est proche de 1.0, mieux c'est.
- **Ventilation par endpoint** : si votre bidder dispose de plusieurs endpoints, voyez lesquels
  sont les plus et les moins efficaces.
- Utilisez ceci pour decider si la consolidation des endpoints serait benefique.

## Comparaisons d'instantanes

Apres l'annulation d'une modification de pretargeting (ou l'application d'une nouvelle), le panneau de comparaison d'instantanes affiche :

- **Avant** : etat de la configuration avant la modification
- **Apres** : etat de la configuration apres la modification
- **Delta** : ce qui a exactement change (champs ajoutes/supprimes/modifies)

C'est utile pour l'analyse post-modification : "J'ai exclu 5 zones geo hier, quel a ete l'impact sur mon entonnoir ?"

## Optimisations recommandees

Cat-Scan peut afficher des recommandations generees par IA basees sur vos donnees. Celles-ci suggerent des modifications specifiques de configuration avec un impact estime. Ce sont des suggestions, pas des actions automatiques. C'est toujours vous qui decidez de les appliquer ou non.

## Conseils pour la lecture des rapports

1. **Verifiez toujours le selecteur de periode.** Une vue a 7 jours et une vue a 30 jours peuvent raconter des histoires tres differentes.
2. **Comparez les configurations, ne regardez pas uniquement les totaux.** Une mauvaise configuration peut tirer les chiffres globaux vers le bas alors que les autres configurations performent bien.
3. **Observez les tendances, pas les instantanes.** Les donnees d'une seule journee sont bruitees. Les tendances sur 7 a 14 jours sont plus fiables.
4. **Croisez les dimensions.** Un gaspillage eleve en vue geographique + un gaspillage eleve en vue taille pour la meme configuration = deux opportunites d'optimisation distinctes.

## Voir aussi

- [Comprendre votre entonnoir QPS](03-qps-funnel.md) : la vue synthetique
- [Analyser le gaspillage par dimension](04-analyzing-waste.md) : approfondir
  les sources specifiques de gaspillage
- [Configuration du pretargeting](06-pretargeting.md) : agir sur les constats des rapports
