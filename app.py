import unicodedata
import re
from bs4 import BeautifulSoup
import time
import requests
import difflib
from math import exp
import httpx
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
cache_por_liga = {}
last_update_por_liga = {}
import re
import unicodedata
import difflib

def normalizar_nombre_equipo(nombre):
    nombre_original = nombre.strip()
    nombre = nombre.lower()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))  # quitar tildes
    nombre = re.sub(r'[^\w\s]', '', nombre)  # eliminar símbolos
    nombre = re.sub(r'\s+', ' ', nombre).strip()

    # Limpieza de palabras comunes
    nombre_limpio = re.sub(r'\b(fc|ac|ss|us|as|ud|cd|club|calcio|cfc|bc|milano|s\.a\.d\.|real|atletico|de|balompie|cf|rcd|1909|1913|1919|1907)\b', '', nombre)
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()

    # Diccionario de alias (normalizados)
    alias = {
        "inter": ["fc internazionale milano", "inter milan", "inter"],
        "milan": ["ac milan"],
        "napoli": ["ssc napoli", "napoli"],
        "lazio": ["ss lazio", "lazio"],
        "roma": ["as roma", "roma"],
        "juventus": ["juventus fc", "juventus"],
        "parma": ["parma calcio 1913", "parma"],
        "sassuolo": ["us sassuolo calcio", "sassuolo"],
        "lecce": ["us lecce", "lecce"],
        "empoli": ["empoli fc", "empoli"],
        "sampdoria": ["uc sampdoria", "sampdoria"],
        "bologna": ["bologna fc 1909", "bologna"],
        "torino": ["torino fc", "torino"],
        "udinese": ["udinese calcio", "udinese"],
        "genoa": ["genoa cfc", "genoa"],
        "verona": ["hellas verona fc", "verona"],
        "salernitana": ["us salernitana 1919", "salernitana"],
        "cagliari": ["cagliari calcio", "cagliari"],
        "frosinone": ["frosinone calcio", "frosinone"],
        "monza": ["monza"],
        "atalanta": ["atalanta bc", "atalanta"],
        "fiorentina": ["acf fiorentina", "fiorentina"],
        "venezia": ["venezia"],
        "como": ["como 1907", "como"],
        "cremonese": ["us cremonese", "cremonese"],
        "pisa": ["ac pisa 1909", "pisa"],
            # Premier League (2024-2025)
        "arsenal": ["arsenal", "arsenal fc"],
        "aston villa": ["aston villa", "aston villa fc"],
        "bournemouth": ["bournemouth", "afc bournemouth"],
        "brentford": ["brentford", "brentford fc"],
        "brighton": ["brighton", "brighton & hove albion", "brighton hove albion", "brighton & hove albion fc"],
        "chelsea": ["chelsea", "chelsea fc"],
        "crystal palace": ["crystal palace", "crystal palace fc"],
        "everton": ["everton", "everton fc"],
        "fulham": ["fulham", "fulham fc"],
        "ipswich": ["ipswich", "ipswich town", "ipswich town fc"],
        "leicester": ["leicester", "leicester city", "leicester city fc"],
        "liverpool": ["liverpool", "liverpool fc"],
        "manchester city": ["manchester city", "manchester city fc"],
        "manchester united": ["manchester united", "manchester utd", "manchester united fc"],
        "newcastle": ["newcastle", "newcastle united", "newcastle utd", "newcastle united fc"],
        "nottingham forest": ["nottingham forest", "nottham forest", "nottingham forest fc"],
        "southampton": ["southampton", "southampton fc"],
        "tottenham": ["tottenham", "tottenham hotspur", "tottenham hotspur fc"],
        "west ham": ["west ham", "west ham united", "west ham united fc"],
        "wolves": ["wolves", "wolverhampton wanderers", "wolverhampton wanderers fc"],

        # LaLiga
        "barcelona": ["fc barcelona", "barcelona"],
        "atletico madrid": ["atletico de madrid", "club atletico de madrid", "atletico madrid"],
        "real madrid": ["real madrid"],
        "real sociedad": ["real sociedad"],
        "rayo vallecano": ["rayo vallecano"],
        "las palmas": ["las palmas"],
        "betis": ["real betis", "betis"],
        "alaves": ["deportivo alaves", "alaves"],
        "espanyol": ["espanyol"]
    }

    # Crear un dict de variantes normalizadas → clave oficial
    variantes_a_clave = {
        re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', unicodedata.normalize('NFKD', var.lower()))).strip(): clave
        for clave, variantes in alias.items()
        for var in variantes
    }

    # Intento de coincidencia exacta
    if nombre in variantes_a_clave:
        return variantes_a_clave[nombre]
    if nombre_limpio in variantes_a_clave:
        return variantes_a_clave[nombre_limpio]

    # Fuzzy matching
    posibles = list(variantes_a_clave.keys())
    coincidencias = difflib.get_close_matches(nombre, posibles, n=1, cutoff=0.8)
    if not coincidencias:
        coincidencias = difflib.get_close_matches(nombre_limpio, posibles, n=1, cutoff=0.8)

    if coincidencias:
        return variantes_a_clave[coincidencias[0]]

    # Si todo falla
    print(f"❌ No se pudo emparejar: {nombre_original} → normalizado: {nombre_limpio}")
    return nombre_limpio





def calcular_probabilidades(score_local, score_visit):
    score_local_ajustado = score_local * 1.07
    total = score_local_ajustado + score_visit
    diff = abs(score_local_ajustado - score_visit) / total if total > 0 else 0
    base_empate = 5
    prob_empate = 30 * exp(-base_empate * diff)
    resto_prob = 100 - prob_empate
    if score_local_ajustado > score_visit:
        prob_victoria_local = resto_prob * (0.5 + diff/2)
        prob_victoria_visit = resto_prob - prob_victoria_local
    else:
        prob_victoria_visit = resto_prob * (0.5 + diff/2)
        prob_victoria_local = resto_prob - prob_victoria_visit
    prob_victoria_local = max(0, min(100, prob_victoria_local))
    prob_victoria_visit = max(0, min(100, prob_victoria_visit))
    prob_empate = max(0, min(100, prob_empate))
    total_prob = prob_victoria_local + prob_victoria_visit + prob_empate
    if total_prob > 0:
        prob_victoria_local = round(prob_victoria_local * 100 / total_prob, 1)
        prob_victoria_visit = round(prob_victoria_visit * 100 / total_prob, 1)
        prob_empate = round(prob_empate * 100 / total_prob, 1)
    return prob_victoria_local, prob_victoria_visit, prob_empate

def obtener_estadisticas_avanzadas(fbref_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }

    proxy_url = f"http://api.scraperapi.com?api_key=ad218ecf00d9b705804e71cf6588ab8a&url=https://fbref.com/en/comps/{fbref_id}/stats"

    response = requests.get(proxy_url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    def parse_table(table_id, columns):
        table = soup.find("table", id=table_id)
        if not table:
            print(f"❌ No se encontró la tabla: {table_id}")
            return {}
        data = {}
        for row in table.tbody.find_all("tr"):
            if row.get("class") == ["thead"]:
                continue
            team = row.find("th").text.strip()
            stats = {}
            for cell in row.find_all("td"):
                stat = cell.get("data-stat")
                if stat in columns:
                    stats[stat] = cell.text.strip()
            data[team] = stats
        return data

    standard = parse_table("stats_squads_standard_for", ["possession", "goals", "xg", "xg_assist", "npxg", "cards_yellow", "cards_red"])
    passing = parse_table("stats_squads_passing_for", ["passes_completed"])
    misc = parse_table("stats_squads_possession_for", ["touches"])
    shooting = parse_table("stats_squads_shooting_for", ["shots_on_target"])
    keepers_adv = parse_table("stats_squads_keeper_adv_for", ["gk_psxg"])
    keepers = parse_table("stats_squads_keeper_for", ["gk_goals_against", "gk_clean_sheets_pct"])

    equipos = {}
    for team in standard:
        equipos[team] = {
            "team": team,
            "possession": standard[team].get("possession", "0"),
            "goals": standard[team].get("goals", "0"),
            "xg": standard[team].get("xg", "0"),
            "xag": standard[team].get("xg_assist", "0"),
            "npxg": standard[team].get("npxg", "0"),
            "yellow_cards": standard[team].get("cards_yellow", "0"),
            "red_cards": standard[team].get("cards_red", "0"),
            "passes_completed": passing.get(team, {}).get("passes_completed", "0"),
            "touches": misc.get(team, {}).get("touches", "0"),
            "shots_on_target": shooting.get(team, {}).get("shots_on_target", "0"),
            "gk_psxg": keepers_adv.get(team, {}).get("gk_psxg", "0"),
            "gk_goals_against": keepers.get(team, {}).get("gk_goals_against", "0"),
            "gk_clean_sheets_pct": keepers.get(team, {}).get("gk_clean_sheets_pct", "0"),
        }

    return list(equipos.values())

def parse_percent(val):
    return float(val.replace('%', '')) if '%' in val else float(val)

def parse_number(val):
    try:
        return float(val.replace(',', ''))
    except:
        return 0.0

def obtener_partidos(competition_id):
    API_KEY = '8f766e7e5acb40b78ab66e96222e7755'
    url = f'https://api.football-data.org/v4/competitions/{competition_id}/matches?status=SCHEDULED'
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error al consultar la API:", response.status_code, response.text)
        return []
    return response.json().get('matches', [])

def buscar_equipo(nombre, equipos_dict):
    nombre_norm = normalizar_nombre_equipo(nombre)
    
    if nombre_norm in equipos_dict:
        return equipos_dict[nombre_norm]

    # Fuzzy matching sobre claves ya normalizadas
    coincidencias = difflib.get_close_matches(nombre_norm, equipos_dict.keys(), n=1, cutoff=0.7)
    if coincidencias:
        return equipos_dict[coincidencias[0]]

    print(f"⚠️ No se pudo emparejar: {nombre} → normalizado: {nombre_norm}")
    return None


def calcular_score(team):
    score = 0
    score += parse_number(team['npxg']) * 0.25
    score += parse_number(team['xag']) * 0.15
    score += parse_number(team['shots_on_target']) * 0.10
    score += parse_number(team['goals']) * 0.10
    score += parse_number(team['xg']) * 0.05
    score += parse_percent(team['possession']) * 0.20
    score += parse_number(team['passes_completed']) / 1000 * 0.10
    score += parse_number(team['touches']) / 1000 * 0.05
    score -= parse_number(team.get('gk_psxg', '0')) * 0.20 
    score -= parse_number(team.get('gk_goals_against', '0')) * 0.30
    score += parse_percent(team.get('gk_clean_sheets_pct', '0')) * 0.20
    score -= parse_number(team['yellow_cards']) * 0.05
    score -= parse_number(team['red_cards']) * 0.05
    score += 100
    return score


LIGAS = {
    "laliga": {
        "competition_id": 2014,
        "fbref_id": "12",
    },
    "premier": {
        "competition_id": 2021,
        "fbref_id": "9",
    },
    "ligue1": {
        "competition_id": 2015,
        "fbref_id": "13",
    },
    "seriea": {
        "competition_id": 2019,
        "fbref_id": "11",
    }
}

from datetime import datetime, timedelta, timezone

def this_week(fecha_iso):
    try:
        date = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
        today = datetime.now(timezone.utc)

        begining_week = today - timedelta(days=today.weekday())  # lunes
        ending_week = begining_week + timedelta(days=6, hours=23, minutes=59, seconds=59)  # domingo

        return begining_week <= date <= ending_week
    except Exception as e:
        print("Error al convertir fecha:", e)
        return False



@app.route("/predicciones/<liga>")
def predicciones(liga):
    global cache_por_liga, last_update_por_liga
    now = time.time()

    liga = liga.lower()
    if liga not in LIGAS:
        return jsonify({"error": "Liga no válida"}), 400

    if (
        liga in cache_por_liga
        and liga in last_update_por_liga
        and now - last_update_por_liga[liga] < 3600
    ):
        return jsonify(cache_por_liga[liga])

    competition_id = LIGAS[liga]["competition_id"]
    fbref_id = LIGAS[liga]["fbref_id"]
    stats = obtener_estadisticas_avanzadas(fbref_id)
    partidos = obtener_partidos(competition_id)
    resultados = []

    if stats and partidos:
        equipos_dict = {
            normalizar_nombre_equipo(team['team']): team
            for team in stats
        }

        for match in partidos:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            fecha = match['utcDate']
            # ✅ Filtrar solo partidos de esta semana
            #if not this_week(fecha):
            #    continue

            equipo_local = buscar_equipo(home, equipos_dict)
            equipo_visitante = buscar_equipo(away, equipos_dict)

            if not equipo_local or not equipo_visitante:
                continue

            try:
                score_local = calcular_score(equipo_local)
                score_visit = calcular_score(equipo_visitante)
                prob_local, prob_visit, prob_empate = calcular_probabilidades(score_local, score_visit)
                ventaja = abs(score_local - score_visit) / max(score_local, score_visit) * 100

                prediccion = "Empate"
                if prob_local > max(prob_visit, prob_empate):
                    prediccion = home
                elif prob_visit > max(prob_local, prob_empate):
                    prediccion = away

                resultados.append({
                    "date": fecha,
                    "home": home,
                    "away": away,
                    "scoreHome": round(score_local, 2),
                    "scoreAway": round(score_visit, 2),
                    "prediction": prediccion,
                    "probabilities": {
                        "homeWin": prob_local,
                        "awayWin": prob_visit,
                        "draw": prob_empate
                    },
                    "confidence": round(ventaja, 1)
                })
            except Exception as e:
                print(f"Error procesando partido {home} vs {away}: {e}")
                continue

    # ✅ Guardar en caché solo esa liga
    cache_por_liga[liga] = resultados
    last_update_por_liga[liga] = now
    return jsonify(resultados)


if __name__ == "__main__":
    app.run(debug=True)
