"""Serveur local JPV Commandes :  python serveur.py   puis ouvrir http://localhost:8000
  GET  /api/commandes              -> commandes + priorité
  POST /api/agent/commandes        -> JPV-AGENT envoie ses commandes (liste JSON de lignes)
  (le statut du stock est lu automatiquement dans JPV Stock, en lecture seule)
  GET  /api/gantt?debut=AAAA-MM-JJ&jours=56 -> planning des salariés
  POST /api/affectation / /api/employe -> choix du salarié d'une commande / salarié inclus ou non
  POST /api/livree                 -> {groupe, livree:true|false}
"""
import json, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from base import connecter, upsert_lignes
from calcul import commandes, gantt
import datetime as dt, urllib.parse
from sync_stock import synchroniser
from importer_excel import reimporter_si_modifie

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
            return self._send(200, {"stock_charge": n > 0, "erreur": erreur, "mois": mois, "commandes": cmds})
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
            if self.path == "/api/affectation":      # {groupe, repartition:[{nom, heures|null}]} ; liste vide = automatique
                d = json.loads(corps)
                con.execute("DELETE FROM affectations WHERE groupe=?", (d["groupe"],))
                for r in d.get("repartition", []):
                    con.execute("INSERT OR REPLACE INTO affectations VALUES (?,?,?)", (d["groupe"], r["nom"], r.get("heures") or None))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/employe":
                d = json.loads(corps)
                con.execute("UPDATE employes SET actif=? WHERE nom=?", (1 if d["actif"] else 0, d["nom"]))
                con.commit(); return self._send(200, {"ok": True})
            if self.path == "/api/livree":
                d = json.loads(corps)
                con.execute("UPDATE lignes SET livree=? WHERE groupe=?", (1 if d["livree"] else 0, d["groupe"]))
                con.commit(); return self._send(200, {"ok": True})
        except Exception as e:
            return self._send(400, {"erreur": str(e)})
        self._send(404, {"erreur": "introuvable"})

if __name__ == "__main__":
    print("JPV Commandes sur http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
