# assistant-virtuel-expo
Application React Native Expo avec agent virtuel animé

## JPV Commandes (planning 2026-2027)

Logiciel local : base SQLite + page web qui liste les commandes par priorité et montre celles qui sont **complètes** (stock suffisant).

1. `pip install openpyxl`
2. `python outils/importer_excel.py "2026 PLANNING COMMANDE.xlsx"` : charge l'Excel dans `data/jpv.db`
3. `python outils/serveur.py` puis ouvrir http://localhost:8000
4. JPV-AGENT envoie ses commandes : `POST http://localhost:8000/api/agent/commandes` (liste JSON de lignes, clé `vk`)
5. JPV Stock envoie le stock : `POST http://localhost:8000/api/stock` (JSON `[{reference, quantite}]` ou CSV `reference;quantite`)
