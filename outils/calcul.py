"""Priorité des commandes. Le statut de chaque ligne vient de JPV Stock (même numéro VK) :
STOCK OK -> ok, STOCK PARTIEL -> manque, EXPEDIEE -> livrée, absent de JPV Stock -> inconnu.
Une commande est COMPLÈTE quand toutes ses lignes sont « ok »."""
import datetime as dt

LIBELLE = {"STOCK OK": "ok", "STOCK PARTIEL": "manque", "EXPEDIEE": "livree"}

def _date(s):
    try: return dt.date.fromisoformat(s)
    except (TypeError, ValueError): return None

def commandes(con):
    stock = {r["vk"]: r["statut"] for r in con.execute("SELECT vk, statut FROM statut_stock")}
    groupes = {}
    for r in con.execute("SELECT * FROM lignes ORDER BY rowid"):
        groupes.setdefault(r["groupe"], []).append(dict(r))
    cmds = []
    for g, lignes in groupes.items():
        for l in lignes:
            st = stock.get(l["vk"])
            if st == "EXPEDIEE" or l["livree"]:
                l["statut"] = "livree"
            else:
                l["statut"] = LIBELLE.get(st, "inconnu")
        delais = [d for d in (_date(l["delai"]) for l in lignes) if d]
        p = lignes[0]
        livree = all(l["statut"] == "livree" for l in lignes)
        manque = sum(l["statut"] in ("manque", "inconnu") for l in lignes)
        d = min(delais) if delais else None
        cmds.append(dict(groupe=g, mois=p["mois"], client=p["client"], cde=p["cde"], type=p["type"],
                         delai=d.isoformat() if d else None, ca=sum(l["ca"] or 0 for l in lignes),
                         livree=livree, nb_manque=manque, lignes=lignes,
                         statut="livree" if livree else ("complete" if not manque else "incomplete"),
                         jours=(d - dt.date.today()).days if d else None))
    cmds.sort(key=lambda c: (c["livree"], c["delai"] or "9999", c["groupe"]))
    return cmds
