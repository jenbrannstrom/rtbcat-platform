# Chapitre 2 : Naviguer dans le tableau de bord

*Public visé : tout le monde*

## Disposition de la barre latérale

La barre latérale est votre outil de navigation principal. Elle peut être
réduite (mode icônes uniquement) ou développée. Votre préférence est mémorisée
d'une session à l'autre.

```
Seat Selector
 ├── QPS Waste Optimizer         /              (home)
 ├── Creatives                   /creatives
 ├── Campaigns                   /campaigns
 ├── Change History              /history
 ├── Import                      /import
 │
 ├── QPS (expandable)
 │   ├── Publisher                /qps/publisher
 │   ├── Geo                     /qps/geo
 │   └── Size                    /qps/size
 │
 ├── Settings (expandable)
 │   ├── Connected Accounts      /settings/accounts
 │   ├── Data Retention          /settings/retention
 │   └── System Status           /settings/system
 │
 ├── Admin (sudo users only)
 │   ├── Users                   /admin/users
 │   ├── Configuration           /admin/configuration
 │   └── Audit Log               /admin/audit-log
 │
 └── Footer: user email, version, docs link
```

Les sections se développent automatiquement lorsque vous y naviguez.

## Utilisateurs restreints

Certains comptes sont marqués comme « restreints » par un administrateur. Les
utilisateurs restreints ne voient que les pages principales : accueil, créations,
campagnes, importation et historique. Les sections d'analyse QPS, de paramètres
et d'administration sont masquées.

## La liste de vérification de configuration

Les nouveaux comptes voient une liste de vérification de configuration à `/setup`
qui guide à travers la configuration initiale :

1. Connecter les comptes acheteurs (téléverser les identifiants GCP, découvrir les sièges)
2. Valider l'intégrité des données (vérifier que les imports CSV arrivent correctement)
3. Enregistrer un modèle d'optimisation (point d'accès BYOM)
4. Valider le point d'accès du modèle (appel de test)
5. Définir le coût d'hébergement de référence (pour les calculs économiques)
6. Connecter une source de conversion (pixel ou webhook)

Le pourcentage d'avancement est suivi. Chaque étape renvoie vers la page de
paramètres correspondante.

## Prise en charge des langues

Cat-Scan prend en charge l'anglais, le néerlandais et le chinois (simplifié).
Le sélecteur de langue se trouve dans la barre latérale. Votre préférence est
enregistrée par utilisateur.

## Étapes suivantes

- Acheteurs média : commencez par [Comprendre votre entonnoir QPS](03-qps-funnel.md)
- DevOps : commencez par [Vue d'ensemble de l'architecture](11-architecture.md)
