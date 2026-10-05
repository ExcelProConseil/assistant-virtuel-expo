"""Base SQLite des commandes + stock (fichier data/jpv.db)."""
import sqlite3, pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "data" / "jpv.db"
CHAMPS = ["vk", "mois", "groupe", "client", "cde", "type", "nomenc", "designation", "qte",
          "date_recep", "date_ar", "delai", "rec_prod", "depart", "heures", "ca", "principale", "livree"]

def connecter():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS lignes (
      vk TEXT PRIMARY KEY, mois TEXT, groupe TEXT, client TEXT, cde TEXT, type TEXT,
      nomenc TEXT, designation TEXT, qte REAL, date_recep TEXT, date_ar TEXT, delai TEXT,
      rec_prod TEXT, depart TEXT, heures REAL, ca REAL, principale INTEGER, livree INTEGER DEFAULT 0, source TEXT);
    CREATE TABLE IF NOT EXISTS stock (reference TEXT PRIMARY KEY, quantite REAL, maj TEXT);
    """)
    return con

def upsert_lignes(con, lignes, source):
    """Ajoute ou met à jour les lignes (clé = numéro VK). Sert à l'Excel ET à JPV-AGENT."""
    for l in lignes:
        d = {k: l.get(k) for k in CHAMPS}
        d["source"] = source
        d["livree"] = d["livree"] or 0
        con.execute(f"INSERT INTO lignes ({','.join(d)}) VALUES ({','.join('?'*len(d))}) "
                    f"ON CONFLICT(vk) DO UPDATE SET " + ",".join(f"{k}=excluded.{k}" for k in d if k not in ("vk", "livree")),
                    list(d.values()))
    con.commit()

def remplacer_stock(con, items):
    con.execute("DELETE FROM stock")
    for it in items:
        con.execute("INSERT OR REPLACE INTO stock VALUES (?,?,datetime('now'))",
                    (str(it["reference"]).strip(), float(it["quantite"])))
    con.commit()
