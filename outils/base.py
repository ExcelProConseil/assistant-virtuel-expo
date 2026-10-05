"""Base SQLite (fichier data/jpv.db) : commandes, statuts JPV Stock, salariés et absences."""
import sqlite3, pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "data" / "jpv.db"
CHAMPS = ["vk", "mois", "ordre", "groupe", "client", "cde", "type", "nomenc", "designation", "qte",
          "date_recep", "date_ar", "delai", "rec_prod", "etape", "depart", "h_unit", "h_reelles",
          "h_tot", "ca_unit", "ca_total", "couleur", "principale", "livree"]
COLONNES = {c: "TEXT" for c in CHAMPS}
COLONNES.update(qte="REAL", ordre="INTEGER", h_unit="REAL", h_reelles="REAL", h_tot="REAL",
                ca_unit="REAL", ca_total="REAL", principale="INTEGER", livree="INTEGER DEFAULT 0")

def connecter():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS lignes (vk TEXT PRIMARY KEY, source TEXT);
    CREATE TABLE IF NOT EXISTS statut_stock (vk TEXT PRIMARY KEY, statut TEXT, maj TEXT);
    CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
    CREATE TABLE IF NOT EXISTS employes (nom TEXT PRIMARY KEY, ordre INTEGER, actif INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS absences (jour TEXT, nom TEXT, type TEXT, PRIMARY KEY (jour, nom));
    CREATE TABLE IF NOT EXISTS affectations (groupe TEXT PRIMARY KEY, nom TEXT);
    """)
    existantes = {r[1] for r in con.execute("PRAGMA table_info(lignes)")}
    for c, t in COLONNES.items():                     # ajoute les colonnes manquantes (anciennes bases)
        if c not in existantes and c != "vk":
            con.execute(f"ALTER TABLE lignes ADD COLUMN {c} {t}")
    con.commit()
    return con

def upsert_lignes(con, lignes, source):
    """Ajoute ou met à jour les lignes (clé = numéro VK). L'état « livrée » saisi à la main est conservé."""
    for l in lignes:
        d = {k: l.get(k) for k in CHAMPS}
        d["source"] = source
        d["livree"] = d["livree"] or 0
        con.execute(f"INSERT INTO lignes ({','.join(d)}) VALUES ({','.join('?'*len(d))}) "
                    "ON CONFLICT(vk) DO UPDATE SET " + ",".join(f"{k}=excluded.{k}" for k in d if k not in ("vk", "livree")),
                    list(d.values()))
    con.commit()

def remplacer_lignes_excel(con, lignes):
    """Synchronise avec l'Excel : met à jour, ajoute, et retire les lignes qui n'y sont plus."""
    vks = [l["vk"] for l in lignes]
    upsert_lignes(con, lignes, source="excel")
    con.execute("DELETE FROM lignes WHERE source='excel' AND vk NOT IN (%s)" % ",".join("?" * len(vks)), vks)
    con.commit()

def remplacer_salaries(con, employes, absences):
    """employes : [(nom, ordre)], absences : [(jour, nom, type)]. L'option « actif » est conservée."""
    for nom, ordre in employes:
        con.execute("INSERT INTO employes (nom, ordre) VALUES (?,?) ON CONFLICT(nom) DO UPDATE SET ordre=excluded.ordre", (nom, ordre))
    con.execute("DELETE FROM absences")
    con.executemany("INSERT OR REPLACE INTO absences VALUES (?,?,?)", absences)
    con.commit()
