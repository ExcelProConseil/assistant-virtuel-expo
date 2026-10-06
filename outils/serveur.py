"""Serveur local JPV Commandes :  python serveur.py   puis ouvrir http://localhost:8000
  GET  /api/commandes              -> commandes + priorité
  POST /api/agent/commandes        -> JPV-AGENT envoie ses commandes (liste JSON de lignes)
  (le statut du stock est lu automatiquement dans JPV Stock, en lecture seule)
  GET  /api/gantt?debut=AAAA-MM-JJ&jours=56 -> planning des salariés
  POST /api/affectation / /api/employe -> choix du salarié d'une commande / salarié inclus ou non
  POST /api/demarrage              -> {groupe, jour}  (date de début choisie à la main)
  POST /api/statut                 -> {groupe, statut: complet|fabrication|controle|livree|null}  (statut choisi à la main)
"""
import json, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from base import connecter, upsert_lignes
from calcul import commandes, gantt, rappels
import datetime as dt, urllib.parse
from sync_stock import synchroniser
from importer_excel import reimporter_si_modifie, PLANNING

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/commandes"):
            con = connecter()
            erreur = None
            try: reimporter_si_modifie(con)
            except Exception as e:
                erreur = f"Planning Excel illisible ({e}). Ferme Excel ou lance : python outils/importer_excel.py \"chemin du planning\""
                print("Relecture du planning impossible :", e)
            try: synchroniser(con)
            except Exception as e: print("Sync JPV Stock impossible :", e)
            n = con.execute("SELECT COUNT(*) FROM statut_stock").fetchone()[0]
            cmds, mois = commandes(con)
            lu = con.execute("SELECT valeur FROM meta WHERE cle='planning_lu'").fetchone()
            return self._send(200, {"stock_charge": n > 0, "erreur": erreur, "planning_lu": lu[0] if lu else None, "mois": mois, "commandes": cmds})
        if self.path.startswith("/api/rappels"):
            con = connecter(); cmds, _ = commandes(con)
            g = gantt(con, cmds, dt.date.today(), 1)
            return self._send(200, {"rappels": rappels(cmds, g)})
        if self.path.startswith("/api/salaries"):
            con = connecter()
            sal = [dict(r) for r in con.execute("SELECT nom, actif, h_semaine, apprenti, parti FROM employes ORDER BY ordre")]
            for s_ in sal:
                s_["periodes"] = [dict(r) for r in con.execute("SELECT id, debut, fin, type FROM periodes WHERE nom=? ORDER BY debut", (s_["nom"],))]
            return self._send(200, {"salaries": sal})
        if self.path.startswith("/api/gantt"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            con = connecter()
            debut = dt.date.fromisoformat(q.get("debut", [dt.date.today().isoformat()])[0])
            cmds, _ = commandes(con)
            return self._send(200, gantt(con, cmds, debut, int(q.get("jours", ["56"])[0])))
        f = WEB / ("index.html" if self.path in ("/", "") else self.path.lstrip("/"))
        if f.is_file() and WEB in f.resolve().parents:
            return self._send(200, f.read_bytes(), "text/html" if f.suffix == ".html" else "text/plain")
        self._send(404, {"erreur": "introuvable"})

    def do_POST(self):
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8-sig")
        con = connecter()
        try:
            if self.path == "/api/agent/commandes":
                d = json.loads(corps); d = d["lignes"] if isinstance(d, dict) else d
                upsert_lignes(con, d, source="agent"); return self._send(200, {"ok": len(d)})
            if self.path == "/api/affectation":      # {groupe, lignes:[{etape, nom, heures|null}]} ; liste vide = rien d'affecté
                d = json.loads(corps)
                con.execute("DELETE FROM affectations WHERE groupe=?", (d["groupe"],))
                for r in d.get("lignes", d.get("repartition", [])):
                    if not r.get("nom"): continue
                    con.execute("INSERT OR REPLACE INTO affectations VALUES (?,?,?,?)", (d["groupe"], r.get("etape") or "toute", r["nom"], r.get("heures") or None))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/salarie":          # {nom, actif?, h_semaine?, apprenti?, parti?}
                d = json.loads(corps)
                for k in ("actif", "h_semaine", "apprenti", "parti"):
                    if k in d: con.execute(f"UPDATE employes SET {k}=? WHERE nom=?", (d[k], d["nom"]))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/periode":          # {nom, debut, fin, type: cfa|absence}
                d = json.loads(corps); dt.date.fromisoformat(d["debut"]); dt.date.fromisoformat(d["fin"])
                if d["type"] not in ("cfa", "absence", "cp"): raise ValueError("type inconnu")
                con.execute("INSERT INTO periodes (nom, debut, fin, type) VALUES (?,?,?,?)", (d["nom"], d["debut"], d["fin"], d["type"]))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/periode_supprimer":  # {id}
                con.execute("DELETE FROM periodes WHERE id=?", (json.loads(corps)["id"],)); con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/employe":
                d = json.loads(corps)
                con.execute("UPDATE employes SET actif=? WHERE nom=?", (1 if d["actif"] else 0, d["nom"]))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/demarrage":         # {groupe, jour: "AAAA-MM-JJ" | null}
                d = json.loads(corps)
                if d.get("jour"):
                    dt.date.fromisoformat(d["jour"])
                    con.execute("INSERT OR REPLACE INTO demarrages VALUES (?,?)", (d["groupe"], d["jour"]))
                else:
                    con.execute("DELETE FROM demarrages WHERE groupe=?", (d["groupe"],))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/relire":            # force la relecture de l'Excel maintenant
                try:
                    reimporter_si_modifie(con, force=True); return self._send(200, {"ok": True})
                except Exception as e:
                    return self._send(200, {"ok": False, "erreur": f"{type(e).__name__}: {e}"})
            if self.path == "/api/etape":             # {groupe, etape: usinage|acompte|controle, fait: true|false|null}
                d = json.loads(corps)
                if d["etape"] not in ("usinage", "acompte", "controle"): raise ValueError("étape inconnue")
                if d.get("fait") is None:
                    con.execute("DELETE FROM etapes WHERE groupe=? AND etape=?", (d["groupe"], d["etape"]))
                else:
                    con.execute("INSERT OR REPLACE INTO etapes VALUES (?,?,?)", (d["groupe"], d["etape"], 1 if d["fait"] else 0))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/statut":           # {groupe, statut: complet|fabrication|controle|livree|null}
                d = json.loads(corps)
                if d.get("statut"):
                    if d["statut"] not in ("complet", "fabrication", "controle", "livree"): raise ValueError("statut inconnu")
                    con.execute("INSERT OR REPLACE INTO statuts VALUES (?,?)", (d["groupe"], d["statut"]))
                else:
                    con.execute("DELETE FROM statuts WHERE groupe=?", (d["groupe"],))
                con.commit(); return self._send(200, {"ok": True})
        except Exception as e:
            return self._send(400, {"erreur": str(e)})
        self._send(404, {"erreur": "introuvable"})

if __name__ == "__main__":
    print("JPV Commandes sur http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
