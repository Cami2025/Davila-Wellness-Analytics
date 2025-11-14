# pipeline_run.py
import os
import re
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# === CONFIGURACIÓN GENERAL ===
SHEET_ID = "1Ly0EsIEFkVnoaDYNjEgTzhWsSrWc1hx4_p7mdQ6zjtM"  # ID del documento en Google Sheets
WORKSHEET_GID = 1915332500                               # gid de la pestaña 'Asistencia'
CREDENTIALS_FILE = "credentials.json"
OUT_DIR = "reports_real"

# Permisos necesarios para usar Sheets y Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------- Helpers ----------
def norm_rut(s: str) -> str:
    """Normaliza RUT: quita puntos/espacios y asegura guion antes del dígito verificador."""
    if pd.isna(s):
        return None
    s = str(s).strip().lower()
    # quitar puntos y espacios
    s = re.sub(r"[.\s]", "", s)
    # normalizar guiones raros
    s = s.replace("–", "-").replace("—", "-")
    # si no tiene guion y tiene largo suficiente, agregar antes del último dígito
    if "-" not in s and len(s) > 1:
        s = s[:-1] + "-" + s[-1]
    return s.upper()


def clean_text(x):
    """Limpia texto básico sin cambiar siglas."""
    if pd.isna(x):
        return None
    x = str(x).strip()
    return x if x else None


def read_sheet(sheet_id: str, gid: int) -> pd.DataFrame:
    """Lee una pestaña de Google Sheets por gid y la devuelve como DataFrame."""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.get_worksheet_by_id(gid)
    data = ws.get_all_records()  # lista de dicts
    return pd.DataFrame(data)


# ---------- MAIN ----------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1) Leer datos crudos desde la pestaña 'Asistencia'
    df = read_sheet(SHEET_ID, WORKSHEET_GID).copy()

    # 2) Renombrar a nombres estándar
    rename = {
        "FECHA": "fecha",
        "RUT": "rut",
        "NOMBRE": "nombre",
        "APELLIDO": "apellido",
        "GÉNERO": "genero",
        "EDIFICIO": "edificio",
        "SECCION": "seccion",
    }
    df = df.rename(columns=rename)

    # Asegurar que todas existan aunque vengan vacías
    for c in ["fecha", "rut", "nombre", "apellido", "genero", "edificio", "seccion"]:
        if c not in df.columns:
            df[c] = pd.NA

    # 3) Parsear fecha (Chile: día primero)
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")

    # 4) Normalizar RUT y textos
    df["rut"] = df["rut"].astype("string").map(norm_rut)
    for c in ["nombre", "apellido", "genero", "edificio", "seccion"]:
        df[c] = df[c].astype("string").map(clean_text)

    # 4bis) Rellenar EDIFICIO y SECCION vacíos con etiquetas claras  🔧 NUEVO
    df["edificio"] = df["edificio"].fillna("SIN EDIFICIO")
    df["seccion"] = df["seccion"].fillna("SIN SECCION")

    # 5) Filtrar filas válidas (fecha y rut no nulos)
    df = df.dropna(subset=["fecha", "rut"]).copy()

    # 6) Eliminar duplicados REALES (misma persona mismo día)
    before = len(df)
    df = df.drop_duplicates(subset=["rut", "fecha"])
    removed = before - len(df)

    # 7) Enriquecer con dimensiones de tiempo
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    df["dia"] = df["fecha"].dt.date

    # 8) Exportar base limpia a CSV
    base_path = os.path.join(OUT_DIR, "asistencia_limpia.csv")
    df.to_csv(base_path, index=False, encoding="utf-8-sig")

    # 9) Resúmenes por edificio / sección / mes
    por_edificio = (
        df.groupby("edificio", dropna=False)
        .agg(
            participaciones=("rut", "count"),
            personas_unicas=("rut", "nunique"),
        )
        .reset_index()
    )
    por_edificio.to_csv(
        os.path.join(OUT_DIR, "por_edificio.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    por_seccion = (
        df.groupby(["edificio", "seccion"], dropna=False)
        .agg(
            participaciones=("rut", "count"),
            personas_unicas=("rut", "nunique"),
        )
        .reset_index()
    )
    por_seccion.to_csv(
        os.path.join(OUT_DIR, "por_seccion.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    tendencia = (
        df.groupby("mes")
        .agg(
            participaciones=("rut", "count"),
            personas_unicas=("rut", "nunique"),
        )
        .reset_index()
        .sort_values("mes")
    )
    tendencia.to_csv(
        os.path.join(OUT_DIR, "tendencia_mensual.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    # 10) KPIs rápidos a JSON
    kpis = {
        "registros_post_limpieza": int(len(df)),
        "duplicados_eliminados": int(removed),
        "personas_unicas_totales": int(df["rut"].nunique()),
    }
    with open(os.path.join(OUT_DIR, "kpis.json"), "w", encoding="utf-8") as f:
        json.dump(kpis, f, ensure_ascii=False, indent=2)

    print("✔ Exportado en carpeta:", OUT_DIR)
    print("KPIs:", kpis)

    # 11) EXPORTAR TAMBIÉN A GOOGLE SHEETS (pestaña Asistencia_Limpia)
    print("\n⏫ Exportando a pestaña 'Asistencia_Limpia' en Google Sheets...")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # Si la hoja no existe, la creamos
    try:
        ws = sh.worksheet("Asistencia_Limpia")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title="Asistencia_Limpia",
            rows=str(len(df) + 10),
            cols=str(len(df.columns) + 5),
        )

    # Preparar una copia SOLO con tipos JSON-serializables (strings / números)
    df_sheet = df.copy()

    # Formatear columnas de fecha a texto (ej: 11/11/2025)
    df_sheet["fecha"] = df_sheet["fecha"].dt.strftime("%d/%m/%Y")
    df_sheet["dia"] = df_sheet["dia"].astype(str)
    df_sheet["anio"] = df_sheet["anio"].astype("Int64").astype(str)  # por si hay NaN
    # "mes" ya es string, pero nos aseguramos:
    df_sheet["mes"] = df_sheet["mes"].astype(str)

    # Rellenar NaN con "" y convertir todo a string para evitar problemas
    df_sheet = df_sheet.fillna("").astype(str)

    # Construir la matriz de datos: primera fila = encabezados
    data = [df_sheet.columns.tolist()] + df_sheet.values.tolist()

    # Limpiar y actualizar la hoja con los datos limpios
    ws.clear()
    ws.update(data)

    print("✅ Datos actualizados en pestaña 'Asistencia_Limpia'.")

if __name__ == "__main__":
    main()

