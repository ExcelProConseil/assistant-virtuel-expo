"""Lit les statuts de commandes dans JPV Stock (lecture seule : JPV Stock n'est jamais modifié).
Le numéro de commande de JPV Stock = le numéro VK du planning."""
import os, shutil, sqlite3, tempfile, pathlib

DB_STOCK = os.environ.get("JPV_STOCK_DB", r"C:/Users/cmore/JPV_STOCK/donnees/jpv_stock.db")

def _lire():
    sql = "SELECT numero, statut_stock FROM commandes"
    try:
        c = sqlite3.connect(f"file:{DB_STOCK}?mode=ro", uri=True)
        return c.execute(sql).fetchall()
    except sqlite3.Error:                      # base verrouillée : on lit une copie
        tmp = pathlib.Path(tempfile.mkdtemp()) / "copie.db"
        shutil.copy(DB_STOCK, tmp)
        return sqlite3.connect(tmp).execute(sql).fetchall()

def synchroniser(con):
    """Retourne le nombre de commandes lues, ou None si JPV Stock est introuvable."""
    if not os.path.exists(DB_STOCK):
        return None
    lignes = _lire()
    con.execute("DELETE FROM statut_stock")
    con.executemany("INSERT OR REPLACE INTO statut_stock VALUES (?,?,datetime('now'))",
                    [(str(n).strip(), s) for n, s in lignes])
    con.commit()
    return len(lignes)

if __name__ == "__main__":
    from base import connecter
    print(synchroniser(connecter()), "commandes lues dans JPV Stock")
