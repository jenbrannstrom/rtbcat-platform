# Chapitre 16 : Administration des utilisateurs et des permissions

*Public visé : DevOps, administrateurs système*

## Panneau d'administration (`/admin`)

Le panneau d'administration n'est visible que par les utilisateurs disposant du
drapeau `is_sudo`. Il donne accès à la gestion des utilisateurs, à la
configuration du système et au journal d'audit.

## Gestion des utilisateurs (`/admin/users`)

### Création d'utilisateurs

Deux méthodes :

| Méthode | Quand l'utiliser |
|---------|------------------|
| **Compte local** | Pour les utilisateurs qui se connecteront avec un e-mail et un mot de passe. Vous définissez le mot de passe initial. |
| **Pré-création OAuth** | Pour les utilisateurs qui se connecteront via Google OAuth. La pré-création de l'enregistrement permet d'attribuer les permissions avant leur première connexion. |

Champs : e-mail (obligatoire), nom d'affichage, rôle, méthode d'authentification,
mot de passe (compte local uniquement).

### Rôles et permissions

**Permissions globales** : elles contrôlent ce qu'un utilisateur peut faire à
l'échelle du système :
- Utilisateur standard : accès aux fonctionnalités principales
- Utilisateur restreint : barre latérale limitée (pas de paramètres, d'administration ni de sections QPS)
- Administrateur (`is_sudo`) : accès complet, y compris au panneau d'administration

**Permissions par siège** : elles contrôlent les comptes acheteurs visibles par
un utilisateur :
- Accorder l'accès à des valeurs spécifiques de `buyer_account_id`
- Les niveaux d'accès peuvent varier par siège
- Un utilisateur sans permission de siège ne voit aucune donnée

### Gestion des permissions

1. Accéder à `/admin/users`
2. Sélectionner un utilisateur
3. Sous « Seat Permissions » : accorder ou révoquer l'accès aux sièges acheteurs
4. Sous « Global Permissions » : accorder ou révoquer l'accès au niveau système
5. Les modifications prennent effet au prochain chargement de page de l'utilisateur

### Désactivation d'utilisateurs

La désactivation d'un utilisateur conserve son enregistrement (pour la
traçabilité) mais empêche la connexion. Elle ne supprime ni ses données ni ses
permissions ; l'utilisateur peut être réactivé.

## Comptes de service (`/settings/accounts`)

Les comptes de service représentent les identifiants GCP qui permettent à
Cat-Scan de communiquer avec les API Google.

### Chargement des identifiants

1. Accéder à `/settings/accounts` > onglet API Connection
2. Charger le fichier de clé JSON du compte de service GCP
3. Cat-Scan valide les identifiants et affiche l'état de la connexion

**Note de sécurité :** N'ajoutez la clé JSON du compte de service qu'à la fin
de la configuration pour minimiser le risque d'exposition.

### Ce que les comptes de service activent

- **Découverte des sièges** : trouver les comptes acheteurs associés aux identifiants
- **Synchronisation du pretargeting** : récupérer l'état actuel de la configuration depuis Google
- **Synchronisation des endpoints RTB** : découvrir les endpoints du bidder
- **Collecte des créatifs** : rassembler les métadonnées des créatifs

## Journal d'audit (`/admin/audit-log`)

Chaque action significative est enregistrée :

| Action | Ce qui la déclenche |
|--------|---------------------|
| `login` | Authentification réussie |
| `login_failed` | Tentative d'authentification échouée |
| `login_blocked` | Connexion rejetée (utilisateur désactivé, etc.) |
| `create_user` | Création d'un nouvel utilisateur |
| `update_user` | Modification du profil utilisateur |
| `deactivate_user` | Désactivation d'un utilisateur |
| `reset_password` | Réinitialisation du mot de passe |
| `change_password` | Changement de mot de passe |
| `grant_permission` | Permission accordée |
| `revoke_permission` | Permission révoquée |
| `update_setting` | Paramètre système modifié |
| `create_initial_admin` | Premier administrateur créé lors de la configuration initiale |

Filtres : par utilisateur, type d'action, type de ressource, fenêtre temporelle
(en jours), avec pagination.

## Configuration du système (`/admin/configuration`)

Paramètres globaux clé-valeur qui contrôlent le comportement du système.
Modifiables par les administrateurs. Les modifications sont enregistrées dans
le journal d'audit.

## Ressources connexes

- [Connexion](01-logging-in.md) : l'expérience d'authentification côté utilisateur
- [Vue d'ensemble de l'architecture](11-architecture.md) : détails de la chaîne de confiance d'authentification
