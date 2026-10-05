"""Priorité des commandes : une commande est COMPLÈTE si toutes ses lignes sont couvertes par le stock.
Le stock est réparti commande par commande, dans l'ordre d'urgence (délai le plus proche d'abord)."""
import datetime as dt

def _date(s):
    try: return dt.date.fromisoformat(s)
    except (TypeError, ValueError): return None

def commandes(con):
    stock = {r["reference"].upper(): r["quantite"] for r in con.execute("SELECT reference, quantite FROM stock")}
    groupes = {}
    for r in con.execute("SELECT * FROM lignes ORDER BY rowid"):
        groupes.setdefault(r["groupe"], []).append(dict(r))
    cmds = []
    for g, lignes in groupes.items():
        p = lignes[0]
        delais = [d for d in (_date(l["delai"]) for l in lignes) if d]
        cmds.append(dict(groupe=g, mois=p["mois"], client=p["client"], cde=p["cde"], type=p["type"],
                         delai=min(delais).isoformat() if delais else None,
                         livree=all(l["livree"] for l in lignes),
                         ca=sum(l["ca"] or 0 for l in lignes), lignes=lignes))
    # ordre d'urgence : délai le plus proche, les sans-délai à la fin
    cmds.sort(key=lambda c: (c["livree"], c["delai"] or "9999", c["groupe"]))
    reste = dict(stock)
    for c in cmds:
        manque = connu = 0
        for l in c["lignes"]:
            ref = (l["nomenc"] or "").upper()
            if c["livree"]:
                l["statut"] = "livree"; continue
            if ref not in reste:
                l["statut"] = "inconnu"; manque += 1; continue
            if reste[ref] >= (l["qte"] or 0):
                l["statut"] = "ok"; l["en_stock"] = reste[ref]; reste[ref] -= l["qte"] or 0
            else:
                l["statut"] = "manque"; l["en_stock"] = reste[ref]; manque += 1
        c["statut"] = "livree" if c["livree"] else ("complete" if not manque else "incomplete")
        c["nb_manque"] = manque
        d = _date(c["delai"])
        c["jours"] = (d - dt.date.today()).days if d else None
    return cmds
