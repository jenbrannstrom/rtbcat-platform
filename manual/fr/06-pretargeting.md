# Chapitre 6 : Configuration du pretargeting

*Public : acheteurs media, responsables de campagne*

Les configurations de pretargeting sont votre principal levier pour controler ce que Google envoie a votre bidder. Ce chapitre explique comment les gerer en toute securite dans Cat-Scan.

## Ce que controle une configuration de pretargeting

Chaque configuration est un ensemble de regles qui indique a Google : "envoyez-moi uniquement les demandes d'encheres correspondant a ces criteres." Vous disposez de **10 configurations par seat**.

| Champ | Ce qu'il filtre |
|-------|----------------|
| **Etat** | Actif (recoit du trafic) ou Suspendu (en pause). |
| **QPS max** | Limite superieure de requetes par seconde acceptees par cette configuration. |
| **Zones geo (incluses)** | Pays, regions ou villes dont vous souhaitez recevoir du trafic. |
| **Zones geo (exclues)** | Zones geographiques a bloquer meme si elles correspondent aux inclusions. |
| **Tailles (incluses)** | Formats publicitaires a accepter (ex. : 300x250, 728x90). |
| **Formats** | Types de creatives : VIDEO, DISPLAY_IMAGE, DISPLAY_HTML, NATIVE. |
| **Plateformes** | Types d'appareils : DESKTOP, MOBILE_APP, MOBILE_WEB, CONNECTED_TV. |
| **Editeurs** | Listes d'autorisation/blocage pour des domaines ou applications d'editeurs specifiques. |

## Lire une fiche de configuration

Sur la page d'accueil et dans les parametres, chaque configuration apparait sous forme de fiche indiquant son etat actuel.

![Fiches de configuration de pretargeting montrant les etats actif et en pause](images/screenshot-pretargeting-configs.png)

Points cles a observer :

- **Actif + QPS max eleve + zones geo larges** = cette configuration capte beaucoup de trafic. Si elle presente egalement un taux de gaspillage eleve, c'est votre principale cible d'optimisation.
- **Suspendu** = ne recoit pas de trafic. Utile pour preparer des modifications avant de les activer.
- **Tailles incluses : (toutes)** = accepte toutes les tailles publicitaires envoyees par Google. Pour du display a taille fixe, c'est presque certainement du gaspillage.

## Effectuer des modifications

### Le flux de travail avec simulation

1. Accedez a la configuration que vous souhaitez modifier (page d'accueil ou
   `/settings/system`).
2. Selectionnez un champ a modifier (ex. : zones geo exclues, tailles incluses).
3. Saisissez vos nouvelles valeurs.
4. Cliquez sur **Apercu** (simulation). Cat-Scan vous montre exactement ce qui
   changera sans l'appliquer.
5. Si l'apercu est correct, cliquez sur **Appliquer**.
6. La modification est enregistree dans l'historique avec un horodatage et votre
   identite.

### Editeur d'autorisation/blocage des editeurs

Pour le blocage au niveau des editeurs, Cat-Scan propose un editeur dedie par configuration. Vous pouvez :
- Rechercher des editeurs par nom de domaine
- Bloquer des domaines ou applications individuels
- Autoriser des domaines specifiques qui prennent le pas sur des blocages plus larges
- Appliquer des modifications en masse

C'est nettement plus simple que de gerer les editeurs via l'interface Authorized Buyers.

## Historique des modifications (`/history`)

Chaque modification de pretargeting est enregistree dans une chronologie accessible via `/history`.

![Chronologie de l'historique des modifications avec filtres et export](images/screenshot-change-history.png)

Pour chaque entree, vous voyez :
- **Quand** : horodatage de la modification
- **Qui** : l'utilisateur qui l'a effectuee
- **Quoi** : nom du champ, ancienne valeur, nouvelle valeur
- **Type** : le type de modification (ajout, suppression, mise a jour)

## Annulation

Si une modification cause des problemes (ex. : augmentation du gaspillage, baisse du taux de gain), vous pouvez l'annuler :

1. Allez sur `/history`.
2. Trouvez la modification que vous souhaitez annuler.
3. Cliquez sur **Apercu de l'annulation**. Cela affiche une simulation du retour
   a l'etat precedent.
4. Ajoutez eventuellement une raison pour l'annulation.
5. Cliquez sur **Confirmer l'annulation**.

L'annulation elle-meme est enregistree comme une nouvelle entree dans l'historique, ce qui vous garantit une piste d'audit complete.

## Voir aussi

- [Analyser le gaspillage par dimension](04-analyzing-waste.md) : identifier ce qu'il faut modifier
- [L'optimiseur](07-optimizer.md) : suggestions automatisees de modifications de configuration
- Pour les DevOps : les instantanes de configuration sont stockes sous forme d'entites versionnees. Voir
  [Operations de base de donnees](14-database.md).
