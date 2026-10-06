# assistant-virtuel-expo
Application React Native Expo avec agent virtuel animé

## JPV Commandes (planning 2026-2027)

Logiciel local : base SQLite + page web qui liste les commandes par priorité et montre celles qui sont **complètes** (stock suffisant).

1. `pip install openpyxl`
2. `python outils/importer_excel.py "2026 PLANNING COMMANDE.xlsx"` : charge l'Excel dans `data/jpv.db`
3. `python outils/serveur.py` puis ouvrir http://localhost:8000
4. JPV-AGENT met à jour le planning Excel : le serveur le relit automatiquement dès qu'il change (chemin modifiable avec `JPV_PLANNING`). Lecture sur une copie : fonctionne même si l'Excel est ouvert.
5. Le stock est lu automatiquement dans JPV Stock (`donnees/jpv_stock.db`, en lecture seule) : le numéro de commande de JPV Stock = le VK du planning ; `STOCK OK` = ligne prête, `STOCK PARTIEL` = manque, `EXPEDIEE` = livrée. Chemin modifiable avec la variable `JPV_STOCK_DB`.

**Bouton sur le Bureau :** double-cliquer une fois sur `CREER_RACCOURCI_BUREAU.bat`, puis utiliser le bouton « JPV Commandes » (démarre le logiciel et ouvre la page). `LANCER_JPV_COMMANDES_ET_AGENTS.bat` lance en plus le menu JPV-AGENT.
