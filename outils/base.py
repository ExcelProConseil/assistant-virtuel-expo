"""Base SQLite (fichier data/jpv.db) : commandes, statuts JPV Stock, salariés et absences."""
import sqlite3, pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "data" / "jpv.db"
# réglages appliqués une seule fois aux salariés connus (modifiables ensuite dans l'onglet Salariés)
DEFAUTS_SALARIES = {"BENJAMIN BRAULT": dict(parti=1), "LEO MILLET": dict(parti=1),
                    "MAEL LONGUET": dict(h_semaine=35, apprenti=1)}
CHAMPS = ["vk", "mois", "ordre", "groupe", "client", "cde", "type", "nomenc", "designation", "qte",
          "date_recep", "date_ar", "delai", "rec_prod", "etape", "depart", "h_unit", "h_reelles",
          "h_tot", "ca_unit", "ca_total", "couleur", "principale", "livree", "et_u", "et_a", "et_c"]
COLONNES = {c: "TEXT" for c in CHAMPS}
COLONNES.update(et_u="INTEGER", et_a="INTEGER", et_c="INTEGER", qte="REAL", ordre="INTEGER", h_unit="REAL", h_reelles="REAL", h_tot="REAL",
                ca_unit="REAL", ca_total="REAL", principale="INTEGER", livree="INTEGER DEFAULT 0")

def connecter():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS lignes (vk TEXT PRIMARY KEY, source TEXT);
    CREATE TABLE IF NOT EXISTS statut_stock (vk TEXT PRIMARY KEY, statut TEXT, maj TEXT);
    CREATE TABLE IF NOT EXISTS statuts (groupe TEXT PRIMARY KEY, statut TEXT);   -- statut choisi à la main
    CREATE TABLE IF NOT EXISTS demarrages (groupe TEXT PRIMARY KEY, jour TEXT);   -- date de début choisie à la main
    CREATE TABLE IF NOT EXISTS etapes (groupe TEXT, etape TEXT, fait INTEGER, PRIMARY KEY (groupe, etape));   -- étapes cochées à la main
    -- Application tablette : temps réalisés, chrono en cours, étapes terminées, retours des salariés
    CREATE TABLE IF NOT EXISTS temps (id INTEGER PRIMARY KEY AUTOINCREMENT, groupe TEXT, etape TEXT, nom TEXT, minutes REAL, debut TEXT, fin TEXT, source TEXT, cree TEXT);
    CREATE TABLE IF NOT EXISTS chronos (nom TEXT PRIMARY KEY, groupe TEXT, etape TEXT, debut TEXT);
    CREATE TABLE IF NOT EXISTS etats_taches (groupe TEXT, etape TEXT, nom TEXT, termine INTEGER, maj TEXT, PRIMARY KEY (groupe, etape, nom));
    CREATE TABLE IF NOT EXISTS retours (id INTEGER PRIMARY KEY AUTOINCREMENT, groupe TEXT, etape TEXT, nom TEXT, type TEXT, texte TEXT, cree TEXT, traite INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, nom TEXT, cree TEXT);
    CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
    CREATE TABLE IF NOT EXISTS employes (nom TEXT PRIMARY KEY, ordre INTEGER, actif INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS periodes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, debut TEXT, fin TEXT, type TEXT);   -- CFA, absences saisies à la main
    CREATE TABLE IF NOT EXISTS absences (jour TEXT, nom TEXT, type TEXT, PRIMARY KEY (jour, nom));
    CREATE TABLE IF NOT EXISTS affectations (groupe TEXT, etape TEXT DEFAULT 'toute', nom TEXT, heures REAL, PRIMARY KEY (groupe, etape, nom));
    """)
    existantes = {r[1] for r in con.execute("PRAGMA table_info(lignes)")}
    for c, t in COLONNES.items():                     # ajoute les colonnes manquantes (anciennes bases)
        if c not in existantes and c != "vk":
            con.execute(f"ALTER TABLE lignes ADD COLUMN {c} {t}")
    cols_e = {r[1] for r in con.execute("PRAGMA table_info(employes)")}
    for c, t in (("h_semaine", "REAL DEFAULT 39"), ("apprenti", "INTEGER DEFAULT 0"), ("parti", "INTEGER DEFAULT 0"), ("pin", "TEXT")):
        if c not in cols_e:
            con.execute(f"ALTER TABLE employes ADD COLUMN {c} {t}")
    if not con.execute("SELECT 1 FROM meta WHERE cle='salaries_v2'").fetchone():            # réglages de départ, une seule fois
        for nom, d in DEFAUTS_SALARIES.items():
            for k, v in d.items():
                con.execute(f"UPDATE employes SET {k}=? WHERE nom=?", (v, nom))
        con.execute("INSERT INTO meta VALUES ('salaries_v2', '1')")
    if "etape" not in {r[1] for r in con.execute("PRAGMA table_info(affectations)")}:   # anciennes versions : sans étape
        cols = {r[1] for r in con.execute("PRAGMA table_info(affectations)")}
        h = "heures" if "heures" in cols else "NULL"
        con.executescript(f"""ALTER TABLE affectations RENAME TO affectations_old;
          CREATE TABLE affectations (groupe TEXT, etape TEXT DEFAULT 'toute', nom TEXT, heures REAL, PRIMARY KEY (groupe, etape, nom));
          INSERT INTO affectations (groupe, etape, nom, heures) SELECT groupe, 'toute', nom, {h} FROM affectations_old;
          DROP TABLE affectations_old;""")
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
    """employes : [(nom, ordre)], absences : [(jour, nom, type)]. Les réglages (actif, heures, parti…) sont conservés."""
    for nom, ordre in employes:
        d = DEFAUTS_SALARIES.get(nom, {})
        con.execute("INSERT INTO employes (nom, ordre, h_semaine, apprenti, parti) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(nom) DO UPDATE SET ordre=excluded.ordre",
                    (nom, ordre, d.get("h_semaine", 39), d.get("apprenti", 0), d.get("parti", 0)))
    con.execute("DELETE FROM absences")
    con.executemany("INSERT OR REPLACE INTO absences VALUES (?,?,?)", absences)
    con.commit()
