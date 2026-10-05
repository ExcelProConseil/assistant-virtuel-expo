"""Importe le planning Excel (un onglet par mois) dans la base SQLite des commandes."""
import sys, re, datetime as dt
import openpyxl
from base import connecter, upsert_lignes

COLS = dict(type="A", recep="B", ar="C", client="D", vk="E", cde="F", nomenc="G", qte="H",
            delai="I", rec_prod="J", designation="K", etape="L", depart="O",
            h_devis="P", ca="S")

def val(ws, col, r):
    v = ws[f"{col}{r}"].value
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, str):
        v = v.strip().replace("\xa0", " ")
        return v or None
    return v

def num(v):
    return v if isinstance(v, (int, float)) else None

def lire(chemin):
    wb = openpyxl.load_workbook(chemin, data_only=True)
    lignes = []
    for ws in wb:
        if ws["B1"].value != "DATE RECEP CDE":      # ignore l'onglet CP / planning employés
            continue
        client = cde = type_ = None
        groupe = 0
        for r in range(3, ws.max_row + 1):
            vk, nomenc = val(ws, "E", r), val(ws, "G", r)
            if not vk or not nomenc or not isinstance(val(ws, "H", r), (int, float)):
                continue
            if val(ws, "D", r):                      # nouvelle commande (ligne principale)
                client, cde, groupe = val(ws, "D", r), val(ws, "F", r), groupe + 1
                type_ = val(ws, "A", r) or None
            elif val(ws, "A", r):
                type_ = val(ws, "A", r)
            lignes.append(dict(
                vk=str(vk), mois=ws.title, groupe=f"{ws.title}-{groupe}",
                client=client, cde=str(cde) if cde else None, type=type_,
                nomenc=str(nomenc), designation=val(ws, "K", r), qte=val(ws, "H", r),
                date_recep=val(ws, "B", r), date_ar=val(ws, "C", r),
                delai=val(ws, "I", r) if not isinstance(val(ws, "I", r), (int, float)) else None,
                rec_prod=str(val(ws, "J", r)) if val(ws, "J", r) is not None else None,
                depart=val(ws, "O", r), heures=num(val(ws, "P", r)), ca=num(val(ws, "S", r)),
                principale=1 if val(ws, "D", r) else 0, livree=1 if deja_passe(ws.title) else 0))
    return lignes

MOIS = {"JANV":1,"FEV":2,"MAR":3,"AVRIL":4,"MAI":5,"JUIN":6,"JUIL":7,"AOUT":8,"SEPT":9,"OCT":10,"NOV":11,"DEC":12}

def deja_passe(onglet):
    """Onglet 'OCT26' -> True si le mois est antérieur au mois en cours."""
    m = re.match(r"([A-Za-z]+)(\d\d)", onglet)
    n = next((v for k, v in MOIS.items() if m.group(1).upper().startswith(k)), None)
    auj = dt.date.today()
    return (2000 + int(m.group(2)), n) < (auj.year, auj.month)

if __name__ == "__main__":
    chemin = sys.argv[1]
    lignes = lire(chemin)
    con = connecter()
    upsert_lignes(con, lignes, source="excel")
    print(f"{len(lignes)} lignes importées")
