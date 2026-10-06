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
            if l.get("force_etat") == "livree":                  # choix manuel (bouton « Marquer comme livrée »)
                l["statut"] = "livree"
            elif l.get("force_etat") == "encours":               # choix manuel (bouton « Remettre en cours »)
                l["statut"] = "manque" if st in ("STOCK PARTIEL",) else ("ok" if st in ("STOCK OK", "EXPEDIEE") else "inconnu")
            elif st == "EXPEDIEE" or l["livree"]:
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
                         vk=p["vk"], vks=[l["vk"] for l in lignes], designation=p["designation"],
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
    manuel = {}
    for r in con.execute("SELECT groupe, nom, heures FROM affectations"):
        manuel.setdefault(r["groupe"], []).append((r["nom"], r["heures"]))

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

    def partager(total, liste):
        """Heures de chaque personne : celles saisies, le reste réparti à parts égales entre les autres."""
        liste = [(n, h) for n, h in liste if n in charge]
        fixes = sum(h for n, h in liste if h)
        libres = [n for n, h in liste if not h]
        part = max(0.0, total - fixes) / len(libres) if libres else 0.0
        return [(n, h or part) for n, h in liste if (h or part) > 0]

    def fin_de(n, h):
        seg = placer(n, h, auj)
        return seg[-1][0] if seg else None

    # Seules les commandes COMPLÈTES (tout le matériel en stock) peuvent être affectées, et c'est TOI qui
    # choisis le salarié : rien n'est placé automatiquement. Un choix fait pour une commande encore
    # incomplète est conservé et s'appliquera quand elle sera complète.
    a_faire = [c for c in cmds if c["statut"] == "complete" and c["heures"] > 0]
    a_faire.sort(key=lambda c: (c["delai"] or "9999", c["groupe"]))
    taches, options, pretes = [], {}, []
    sans_heures = [c for c in cmds if c["statut"] == "complete" and c["heures"] <= 0]
    en_attente = [dict(groupe=c["groupe"], client=c["client"], cde=c["cde"], vk=c["vk"], designation=c["designation"],
                       delai=c["delai"], heures=round(c["heures"], 2), nb_manque=c["nb_manque"],
                       nb_lignes=len(c["lignes"]), pre_affectee=c["groupe"] in manuel)
                  for c in cmds if c["statut"] == "incomplete"]
    for c in a_faire:
        d = _date(c["delai"])
        # aide : combien de personnes pour tenir le délai ? (les n salariés qui finiraient le plus tôt)
        opts = []
        for k in range(1, min(4, len(emps)) + 1):
            fins = sorted(((fin_de(n, c["heures"] / k), n) for n in emps), key=lambda x: (x[0] is None, x[0]))[:k]
            if any(f is None for f, _ in fins): continue
            fin = max(f for f, _ in fins)
            opts.append(dict(n=k, fin=fin.isoformat(), noms=[n for _, n in fins], ok=bool(d is None or fin <= d)))
        options[c["groupe"]] = opts
        parts = partager(c["heures"], manuel[c["groupe"]]) if c["groupe"] in manuel else []
        placees = []
        for n, h in parts:
            seg = placer(n, h, auj)
            if not seg: continue
            for j, hh in seg: charge[n][j] = charge[n].get(j, 0.0) + hh
            placees.append((n, h, seg))
        fin_cmd = max(seg[-1][0] for _, _, seg in placees) if placees else None
        retard = bool(d and fin_cmd and fin_cmd > d)
        pretes.append(dict(groupe=c["groupe"], client=c["client"], cde=c["cde"], vk=c["vk"], designation=c["designation"],
                           delai=c["delai"], heures_total=round(c["heures"], 2), affectee=bool(placees),
                           affectees=[dict(nom=n, heures=round(h, 2)) for n, h, _ in placees],
                           fin_commande=fin_cmd.isoformat() if fin_cmd else None, retard=retard))
        for n, h, seg in placees:
            taches.append(dict(groupe=c["groupe"], client=c["client"], cde=c["cde"], vk=c["vk"], designation=c["designation"],
                               employe=n, manuel=True, debut=seg[0][0].isoformat(), fin=seg[-1][0].isoformat(),
                               heures=round(h, 2), fixe=any(n == nm and hh_ for nm, hh_ in manuel.get(c["groupe"], [])),
                               heures_total=round(c["heures"], 2), statut=c["statut"], delai=c["delai"],
                               fin_commande=fin_cmd.isoformat(), retard=retard))
    jours = []
    for i in range(nb_jours):
        j = debut + dt.timedelta(days=i)
        jours.append(dict(date=j.isoformat(), we=j.weekday() >= 5, ferie=j in ferie, auj=j == auj))
    etat = {n: {} for n in emps}
    for n in emps:
        for jr in jours:
            t = abs_.get((jr["date"], n))
            etat[n][jr["date"]] = t or ("ferie" if jr["ferie"] else ("we" if jr["we"] else ""))
    return dict(salaries=tous, jours=jours, etat=etat, taches=taches, options=options, pretes=pretes, en_attente=en_attente,
                sans_heures=[dict(groupe=c["groupe"], client=c["client"], vk=c["vk"], designation=c["designation"], delai=c["delai"]) for c in sans_heures],
                charge={n: round(sum(h for j, h in charge[n].items()), 1) for n in emps})
