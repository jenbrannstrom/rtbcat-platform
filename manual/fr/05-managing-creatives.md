# Chapitre 5 : Gestion des créations

*Public visé : acheteurs média, gestionnaires de campagnes*

## Galerie de créations (`/creatives`)

La galerie affiche toutes les créations associées au siège sélectionné.

![Galerie de créations avec badges de format et niveaux de performance](images/screenshot-creatives.png)

### Ce que vous voyez

Chaque création apparaît sous forme de carte comportant :

- **Miniature** : aperçu généré automatiquement de la publicité (image extraite
  de la vidéo ou capture d'écran display)
- **Badge de format** : VIDEO, DISPLAY_IMAGE, DISPLAY_HTML ou NATIVE
- **Identifiant de création** : l'identifiant de création Authorized Buyers
- **Format canonique** : le format publicitaire principal (ex. : 300x250, 728x90)
- **Niveau de performance** : HIGH, MEDIUM, LOW ou NO_DATA, basé sur le
  classement par percentile de dépenses au sein de votre siège

### Filtrage et recherche

- **Filtre par format** : afficher uniquement Video, Display Image, Display HTML ou Native
- **Filtre par niveau de performance** : isoler les créations très performantes ou peu performantes
- **Recherche** : trouver une création par son identifiant
- **Sélecteur de période** : 7, 14 ou 30 jours de données de performance

### Miniatures

Les miniatures sont générées par lots. Si vous voyez des images de substitution,
utilisez le bouton de génération de miniatures par lots pour mettre en file
d'attente les miniatures manquantes. Le statut s'affiche dans l'interface.

### Détails d'une création

Cliquez sur une création pour ouvrir la fenêtre d'aperçu avec :

- URL de destination et diagnostics (la page d'atterrissage est-elle accessible ?)
- Détection de la langue (détectée automatiquement + option de remplacement manuel)
- Répartition des performances par pays (dans quelles zones géographiques cette création est performante)
- Rapport géo-linguistique (détection des incohérences entre langue et zone géographique)

**La détection d'incohérence linguistique** est une fonctionnalité distinctive :
Cat-Scan peut signaler des cas comme une publicité en espagnol diffusée sur des
marchés arabophones, ou des prix en AED ciblant des utilisateurs en Inde. Cette
fonctionnalité utilise votre fournisseur d'IA configuré (Gemini, Claude ou Grok).

## Regroupement en campagnes (`/campaigns`)

Les campagnes vous permettent d'organiser les créations en groupes logiques.

### Vues

- **Vue en grille** : cartes de campagne avec nombre de créations, dépenses, impressions, clics
- **Vue en liste** : format tableau compact

### Actions

- **Glisser-déposer** : déplacer des créations entre campagnes ou vers le pool non assigné
- **Créer une campagne** : nommer un nouveau groupe et y glisser des créations
- **Regroupement automatique par IA** : laisser Cat-Scan suggérer des regroupements
  basés sur les attributs des créations (format, taille, destination, langue)
- **Supprimer une campagne** : supprime le regroupement (les créations retournent dans le pool non assigné)

### Filtres

- **Trier par** : nom, dépenses, impressions, clics, nombre de créations
- **Filtre par pays** : afficher uniquement les campagnes avec des créations
  diffusées dans une zone géographique spécifique
- **Filtre par problèmes** : mettre en évidence les campagnes présentant des
  problèmes (incohérences, créations peu performantes)

## En lien

- [Analyser le gaspillage par format](04-analyzing-waste.md) : le gaspillage
  par format est directement lié aux créations dont vous disposez
- [Lire vos rapports](10-reading-reports.md) : performance au niveau des campagnes
