"""Priorité des commandes + planning des salariés (Gantt).

Statut de chaque ligne (lu dans JPV Stock, même numéro VK) :
  STOCK OK -> ok, STOCK PARTIEL -> manque, EXPEDIEE -> livrée, absent de JPV Stock -> inconnu.
Une commande est COMPLÈTE quand toutes ses lignes sont « ok »."""
import datetime as dt

LIBELLE = {"STOCK OK": "ok", "STOCK PARTIEL": "manque", "EXPEDIEE": "livree"}
H_LUN_JEU, H_VEN = 8.5, 5.0          # heures travaillées par jour (comme l'onglet CP : 8,5 h du lundi au jeudi, 5 h le vendredi)

def _date(s):
    try: return dt.date.fromisoformat(s)
    except (TypeError, ValueError): return None

def commandes(con, aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    stock = {r["vk"]: r["statut"] for r in con.execute("SELECT vk, statut FROM statut_stock")}
    groupes, ordre_mois = {}, {}
    for r in con.execute("SELECT * FROM lignes ORDER BY ordre, rowid"):
        groupes.setdefault(r["groupe"], []).append(dict(r))
        ordre_mois.setdefault(r["mois"], len(ordre_mois))
    cmds = []
    for g, lignes in groupes.items():
        for l in lignes:
            st = stock.get(l["vk"])
            if st == "EXPEDIEE" or l["livree"]:
                l["statut"] = "livree"
            else:
                l["statut"] = LIBELLE.get(st, "inconnu")
            l["stock_jpv"] = st
        delais = [d for d in (_date(l["delai"]) for l in lignes) if d]
        p = lignes[0]
        livree = all(l["statut"] == "livree" for l in lignes)
        manque = sum(l["statut"] in ("manque", "inconnu") for l in lignes)
        d = min(delais) if delais else None
        cmds.append(dict(groupe=g, mois=p["mois"], client=p["client"], cde=p["cde"], type=p["type"],
                         delai=d.isoformat() if d else None,
                         ca=sum(l["ca_total"] or 0 for l in lignes),
                         heures=sum(l["h_tot"] or 0 for l in lignes),
                         livree=livree, nb_manque=manque, lignes=lignes,
                         statut="livree" if livree else ("complete" if not manque else "incomplete"),
                         jours=(d - auj).days if d else None))
    cmds.sort(key=lambda c: (c["livree"], c["delai"] or "9999", c["groupe"]))
    return cmds, list(ordre_mois)

# ------------------------------------------------------------------ jours ouvrés
def paques(a):
    g = a % 19; c = a // 100; h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
    i = h - (h // 28) * (1 - (h // 28) * (29 // (h + 1)) * ((21 - g) // 11))
    j = (a + a // 4 + i + 2 - c + c // 4) % 7; l = i - j
    m = 3 + (l + 40) // 44; d = l + 28 - 31 * (m // 4)
    return dt.date(a, m, d)

def feries(annee):
    p = paques(annee); un = dt.timedelta
    return {dt.date(annee, 1, 1), p + un(1), dt.date(annee, 5, 1), dt.date(annee, 5, 8), p + un(39),
            p + un(50), dt.date(annee, 7, 14), dt.date(annee, 8, 15), dt.date(annee, 11, 1),
            dt.date(annee, 11, 11), dt.date(annee, 12, 25)}

def capacite_base(jour, ferie):
    if jour in ferie or jour.weekday() >= 5: return 0.0
    return H_VEN if jour.weekday() == 4 else H_LUN_JEU

# ------------------------------------------------------------------ Gantt
def gantt(con, cmds, debut, nb_jours, aujourdhui=None, horizon=400):
    """Répartit les commandes à produire sur les salariés actifs, dans l'ordre de priorité."""
    auj = aujourdhui or dt.date.today()
    emps = [r["nom"] for r in con.execute("SELECT nom FROM employes WHERE actif=1 ORDER BY ordre")]
    tous = [dict(nom=r["nom"], actif=bool(r["actif"])) for r in con.execute("SELECT nom, actif FROM employes ORDER BY ordre")]
    abs_ = {}
    for r in con.execute("SELECT jour, nom, type FROM absences"):
        abs_[(r["jour"], r["nom"])] = r["type"]
    ferie = set()
    for a in {auj.year - 1, auj.year, auj.year + 1, auj.year + 2}: ferie |= feries(a)
    manuel = {r["groupe"]: r["nom"] for r in con.execute("SELECT groupe, nom FROM affectations")}

    def cap(nom, j):
        if (j.isoformat(), nom) in abs_: return 0.0
        return capacite_base(j, ferie)

    charge = {n: {} for n in emps}
    def placer(nom, heures, depuis):
        """Remplit les jours disponibles à partir de `depuis`. Retourne la liste [(jour, heures)] ou None."""
        reste, j, out = heures, depuis, []
        for _ in range(horizon):
            libre = cap(nom, j) - charge[nom].get(j, 0.0)
            if libre > 1e-9 and reste > 1e-9:
                h = min(libre, reste); out.append((j, h)); reste -= h
                if reste <= 1e-9: return out
            j += dt.timedelta(days=1)
        return None

    a_faire = [c for c in cmds if not c["livree"] and c["heures"] > 0]
    a_faire.sort(key=lambda c: (c["statut"] != "complete", c["delai"] or "9999", c["groupe"]))
    taches, sans_heures = [], [c for c in cmds if not c["livree"] and c["heures"] <= 0]
    for c in a_faire:
        choix = [manuel[c["groupe"]]] if manuel.get(c["groupe"]) in charge else emps
        meilleur = None
        for n in choix:
            seg = placer(n, c["heures"], auj)
            if seg and (meilleur is None or seg[-1][0] < meilleur[1][-1][0]): meilleur = (n, seg)
        if not meilleur: continue
        n, seg = meilleur
        for j, h in seg: charge[n][j] = charge[n].get(j, 0.0) + h
        d = _date(c["delai"])
        taches.append(dict(groupe=c["groupe"], client=c["client"], cde=c["cde"], employe=n,
                           manuel=c["groupe"] in manuel, debut=seg[0][0].isoformat(), fin=seg[-1][0].isoformat(),
                           heures=round(c["heures"], 2), statut=c["statut"], delai=c["delai"],
                           retard=bool(d and seg[-1][0] > d)))
    jours = []
    for i in range(nb_jours):
        j = debut + dt.timedelta(days=i)
        jours.append(dict(date=j.isoformat(), we=j.weekday() >= 5, ferie=j in ferie, auj=j == auj))
    etat = {n: {} for n in emps}
    for n in emps:
        for jr in jours:
            t = abs_.get((jr["date"], n))
            etat[n][jr["date"]] = t or ("ferie" if jr["ferie"] else ("we" if jr["we"] else ""))
    return dict(salaries=tous, jours=jours, etat=etat, taches=taches,
                sans_heures=[dict(groupe=c["groupe"], client=c["client"], delai=c["delai"]) for c in sans_heures],
                charge={n: round(sum(h for j, h in charge[n].items()), 1) for n in emps})
