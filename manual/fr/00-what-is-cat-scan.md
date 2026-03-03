# Chapitre 0 : Qu'est-ce que Cat-Scan ?

*Public visé : tout le monde*

Cat-Scan est une plateforme d'optimisation du QPS pour Google Authorized Buyers.
Elle vous offre une visibilité sur la manière dont l'allocation en
requêtes par seconde de votre enchérisseur est utilisée (et gaspillée), et
fournit les outils nécessaires pour l'améliorer.

![Entonnoir QPS](/docs/qps-funnel.svg)

## Le problème central

Lorsque vous exploitez un siège sur l'exchange Google Authorized Buyers, Google
envoie un flux de demandes d'enchères à votre point d'accès enchérisseur. Ce
flux a un coût : il consomme votre QPS alloué, la capacité de calcul de votre
enchérisseur et votre bande passante réseau.

Mais toutes les demandes d'enchères ne sont pas utiles. Beaucoup arrivent pour
de l'inventaire que vous n'achèteriez jamais : des pays que vous ne ciblez pas,
des éditeurs dont vous n'avez jamais entendu parler, des formats publicitaires
pour lesquels vous n'avez aucune création. Votre enchérisseur doit tout de même
recevoir et rejeter chacune d'entre elles.

Dans une configuration type, **plus de la moitié de votre QPS est du gaspillage.**

## Ce que Cat-Scan fait pour y remédier

Cat-Scan fonctionne en parallèle de votre enchérisseur et fournit trois choses :

### 1. Visibilité

Il reconstruit les rapports de performance à partir des exports CSV de Google
(puisqu'il n'existe pas d'API de reporting) et vous présente l'entonnoir RTB
complet : du QPS brut jusqu'aux enchères, victoires, impressions, clics et
dépenses. Il ventile ces données par zone géographique, éditeur, format
publicitaire, création et configuration de préciblage.

Cela vous permet de répondre à des questions telles que :
- Quels pays consomment du QPS sans générer de victoires ?
- Quels éditeurs ont un QPS élevé mais aucune dépense ?
- Quels formats publicitaires reçoivent du trafic mais n'ont pas de création correspondante ?
- Quelles configurations de préciblage sont performantes et lesquelles ne le sont pas ?

### 2. Contrôle

Google vous accorde 10 configurations de préciblage par siège. Ce sont vos
principaux leviers pour indiquer à Google quel trafic envoyer et lequel filtrer.
Cat-Scan fournit :
- Un éditeur de configuration avec aperçu en mode simulation
- Un historique des modifications avec restauration en un clic
- Des listes d'autorisation/exclusion d'éditeurs par configuration
- Un optimiseur qui note les segments et propose des modifications de configuration

### 3. Sécurité

Chaque modification de préciblage est enregistrée. Vous pouvez prévisualiser
l'impact d'un changement avant de l'appliquer. Si quelque chose se passe mal,
vous pouvez revenir en arrière instantanément. L'optimiseur utilise des profils
de flux de travail (prudent, équilibré, agressif) afin qu'aucune modification
automatisée ne soit mise en production sans validation humaine.

## Concepts clés

Avant de poursuivre, assurez-vous de bien comprendre ces termes :

| Concept | Signification |
|---------|---------------|
| **Siège (Seat)** | Un compte acheteur sur Google Authorized Buyers, identifié par un `buyer_account_id`. Une organisation peut disposer de plusieurs sièges. |
| **QPS** | Queries Per Second (requêtes par seconde) : le débit maximal de demandes d'enchères que vous demandez à Google d'envoyer à votre enchérisseur. Google régule le volume réel en fonction du niveau de votre compte, il est donc essentiel d'utiliser chaque requête efficacement. |
| **Préciblage (Pretargeting)** | Filtres côté serveur qui indiquent à Google quelles demandes d'enchères vous envoyer. Paramètres contrôlés : zones géographiques, formats publicitaires, types de formats, plateformes, types de créations. Vous en disposez de 10 par siège. |
| **Entonnoir RTB** | La progression depuis la réception de la demande d'enchère, l'enchère placée, la victoire en enchère, l'impression servie, le clic, jusqu'à la conversion. Chaque étape présente une déperdition ; Cat-Scan vous montre où elle se produit. |
| **Gaspillage (Waste)** | QPS consommé par des demandes d'enchères que votre enchérisseur ne peut ou ne veut pas exploiter. L'objectif est de réduire le gaspillage sans perdre de trafic à valeur ajoutée. |
| **Config** | Abréviation de configuration de préciblage. Chacune possède un état (active/suspendue), un QPS maximal et des règles d'inclusion/exclusion pour les zones géographiques, les formats, les types de formats et les plateformes. |

## Étapes suivantes

- [Se connecter](01-logging-in.md) : accéder au tableau de bord
- [Naviguer dans le tableau de bord](02-navigating-the-dashboard.md) : se repérer dans l'interface
