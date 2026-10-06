"""Application tablette : ce que voit et saisit chaque salarié (tâches, temps par étape, retours)."""
import datetime as dt, secrets
from calcul import commandes, gantt, rappels, LIB_PHASE

def maintenant():
    return dt.datetime.now().isoformat(timespec="seconds")

def epoch(iso):
    return dt.datetime.fromisoformat(iso).timestamp()

# ------------------------------------------------------------ connexion
def salaries_tablette(con):
    return [dict(nom=r["nom"], pin=bool(r["pin"])) for r in
            con.execute("SELECT nom, pin FROM employes WHERE parti=0 AND actif=1 ORDER BY ordre")]

def connexion(con, nom, pin):
    r = con.execute("SELECT pin FROM employes WHERE nom=? AND parti=0", (nom,)).fetchone()
    if not r: raise ValueError("Salarié inconnu")
    if r["pin"] and str(pin or "") != str(r["pin"]): raise PermissionError("Code incorrect")
    token = secrets.token_urlsafe(16)
    con.execute("INSERT INTO sessions VALUES (?,?,?)", (token, nom, maintenant())); con.commit()
    return token

def salarie_du_token(con, token):
    r = con.execute("SELECT nom FROM sessions WHERE token=?", (token or "",)).fetchone()
    if not r: raise PermissionError("Session expirée")
    return r["nom"]

# ------------------------------------------------------------ chrono / temps
def _arreter_chrono(con, nom):
    c = con.execute("SELECT * FROM chronos WHERE nom=?", (nom,)).fetchone()
    if not c: return None
    fin = maintenant(); minutes = max(0.0, (epoch(fin) - epoch(c["debut"])) / 60)
    if minutes >= 0.2:                                    # ignore un clic de moins de ~12 s
        con.execute("INSERT INTO temps (groupe, etape, nom, minutes, debut, fin, source, cree) VALUES (?,?,?,?,?,?,?,?)",
                    (c["groupe"], c["etape"], nom, round(minutes, 1), c["debut"], fin, "chrono", fin))
    con.execute("DELETE FROM chronos WHERE nom=?", (nom,))
    return minutes

def chrono(con, nom, action, groupe, etape):
    if action == "start":
        _arreter_chrono(con, nom)                         # un seul chrono à la fois
        con.execute("INSERT OR REPLACE INTO chronos VALUES (?,?,?,?)", (nom, groupe, etape, maintenant()))
        con.execute("INSERT OR REPLACE INTO etats_taches VALUES (?,?,?,?,?)", (groupe, etape, nom, 0, maintenant()))
    elif action == "stop":
        _arreter_chrono(con, nom)
    con.commit()

def ajouter_temps(con, nom, groupe, etape, minutes):
    minutes = float(minutes)
    if not 0 < minutes <= 24 * 60: raise ValueError("Durée incorrecte")
    n = maintenant()
    con.execute("INSERT INTO temps (groupe, etape, nom, minutes, debut, fin, source, cree) VALUES (?,?,?,?,?,?,?,?)",
                (groupe, etape, nom, minutes, None, None, "manuel", n)); con.commit()

def supprimer_temps(con, nom, id_):
    con.execute("DELETE FROM temps WHERE id=? AND nom=?", (id_, nom)); con.commit()

def terminer(con, nom, groupe, etape, termine):
    if termine: _arreter_chrono(con, nom)
    con.execute("INSERT OR REPLACE INTO etats_taches VALUES (?,?,?,?,?)", (groupe, etape, nom, 1 if termine else 0, maintenant())); con.commit()

def retour(con, nom, groupe, etape, type_, texte):
    texte = (texte or "").strip()
    if not texte: raise ValueError("Écris un commentaire")
    if type_ not in ("probleme", "modification", "info"): raise ValueError("Type inconnu")
    con.execute("INSERT INTO retours (groupe, etape, nom, type, texte, cree, traite) VALUES (?,?,?,?,?,?,0)",
                (groupe, etape, nom, type_, texte[:2000], maintenant())); con.commit()

# ------------------------------------------------------------ tâches d'un salarié
def taches_du_salarie(con, nom):
    cmds, _ = commandes(con)
    par = {c["groupe"]: c for c in cmds}
    g = gantt(con, cmds, dt.date.today(), 1)
    minutes, entrees = {}, {}
    for r in con.execute("SELECT * FROM temps WHERE nom=? ORDER BY id", (nom,)):
        k = (r["groupe"], r["etape"]); minutes[k] = minutes.get(k, 0.0) + (r["minutes"] or 0)
        entrees.setdefault(k, []).append(dict(id=r["id"], minutes=r["minutes"], source=r["source"], cree=r["cree"]))
    etats = {(r["groupe"], r["etape"]): bool(r["termine"]) for r in con.execute("SELECT * FROM etats_taches WHERE nom=?", (nom,))}
    rets = {}
    for r in con.execute("SELECT * FROM retours WHERE nom=? ORDER BY id DESC", (nom,)):
        rets.setdefault((r["groupe"], r["etape"]), []).append(dict(id=r["id"], type=r["type"], texte=r["texte"], cree=r["cree"], traite=bool(r["traite"])))
    ch = con.execute("SELECT * FROM chronos WHERE nom=?", (nom,)).fetchone()
    out = []
    for t in g["taches"]:
        if t["employe"] != nom: continue
        c = par[t["groupe"]]; k = (t["groupe"], t["etape"])
        out.append(dict(
            groupe=t["groupe"], etape=t["etape"], etape_lib=LIB_PHASE.get(t["etape"], t["etape"]),
            client=c["client"], vk=c["vk"], cde=c["cde"], designation=c["designation"], delai=c["delai"],
            statut=c["statut"], debut=t["debut"], fin=t["fin"], heures_prevues=t["heures"], heures_commande=t["heures_total"],
            note_excel=next((l["etape"] for l in c["lignes"] if l.get("etape")), None),
            lignes=[dict(vk=l["vk"], nomenc=l["nomenc"], designation=l["designation"], qte=l["qte"]) for l in c["lignes"]],
            minutes=round(minutes.get(k, 0.0), 1), entrees=entrees.get(k, []), termine=etats.get(k, False),
            en_cours=bool(ch and ch["groupe"] == t["groupe"] and ch["etape"] == t["etape"]), retours=rets.get(k, [])))
    out.sort(key=lambda t: (t["termine"], t["debut"], t["delai"] or "9999"))
    return dict(nom=nom, taches=out, serveur_epoch=dt.datetime.now().timestamp(),
                chrono=dict(groupe=ch["groupe"], etape=ch["etape"], debut_epoch=epoch(ch["debut"])) if ch else None)

# ------------------------------------------------------------ côté PC : suivi
def suivi(con):
    cmds, _ = commandes(con); par = {c["groupe"]: c for c in cmds}
    g = gantt(con, cmds, dt.date.today(), 1)
    realise = {}
    for r in con.execute("SELECT groupe, etape, nom, SUM(minutes) m FROM temps GROUP BY groupe, etape, nom"):
        realise[(r["groupe"], r["etape"], r["nom"])] = r["m"] or 0
    etats = {(r["groupe"], r["etape"], r["nom"]): bool(r["termine"]) for r in con.execute("SELECT * FROM etats_taches")}
    enc = {(r["groupe"], r["etape"], r["nom"]) for r in con.execute("SELECT * FROM chronos")}
    lignes, vus = [], set()
    def ajoute(groupe, etape, nom, prevu):
        k = (groupe, etape, nom); vus.add(k); c = par.get(groupe)
        lignes.append(dict(groupe=groupe, client=c["client"] if c else "?", vk=c["vk"] if c else "", designation=c["designation"] if c else "",
                           etape=etape, etape_lib=LIB_PHASE.get(etape, etape), nom=nom, prevu=prevu,
                           realise=round(realise.get(k, 0) / 60, 2), termine=etats.get(k, False), en_cours=k in enc,
                           statut=c["statut"] if c else None))
    for t in g["taches"]: ajoute(t["groupe"], t["etape"], t["employe"], t["heures"])
    for k in realise:
        if k not in vus: ajoute(*k, None)
    rets = []
    for r in con.execute("SELECT * FROM retours ORDER BY traite, id DESC LIMIT 200"):
        c = par.get(r["groupe"])
        rets.append(dict(id=r["id"], groupe=r["groupe"], client=c["client"] if c else "?", vk=c["vk"] if c else "", nom=r["nom"],
                         etape_lib=LIB_PHASE.get(r["etape"], r["etape"]), type=r["type"], texte=r["texte"], cree=r["cree"], traite=bool(r["traite"])))
    return dict(lignes=lignes, retours=rets)

def retours_non_traites(con):
    out = []
    for r in con.execute("SELECT * FROM retours WHERE traite=0 ORDER BY id DESC"):
        out.append(dict(id=r["id"], groupe=r["groupe"], nom=r["nom"], type=r["type"], texte=r["texte"]))
    return out

def export_csv(con):
    lignes = ["Date;Salarié;Client;N° VK;Désignation;Étape;Minutes;Heures;Origine"]
    cmds, _ = commandes(con); par = {c["groupe"]: c for c in cmds}
    for r in con.execute("SELECT * FROM temps ORDER BY id"):
        c = par.get(r["groupe"], {})
        champs = [r["cree"][:16].replace("T", " "), r["nom"].title(), c.get("client") or "", c.get("vk") or "", c.get("designation") or "",
                  LIB_PHASE.get(r["etape"], r["etape"]), str(round(r["minutes"] or 0, 1)).replace(".", ","), str(round((r["minutes"] or 0) / 60, 2)).replace(".", ","), r["source"]]
        lignes.append(";".join(str(x).replace(";", ",").replace("\n", " ") for x in champs))
    return ("\ufeff" + "\n".join(lignes)).encode("utf-8")
