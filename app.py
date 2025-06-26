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
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)
cache_por_liga = {}
last_update_por_liga = {}
resultados_globales = []

ODDS_API_KEY = "e95928872759eb91f6e4e02410315072"

sport_key_map = {
    "laliga": "soccer_spain_la_liga",
    "premier": "soccer_epl",
    "ligue1": "soccer_france_ligue_one",
    "seriea": "soccer_italy_serie_a"
}
scraperapi_keys = [
    "b3c1a3296505fb10281d9726aa24dc64",
    "27b74be51de456a4a88d30ac2c42b434",
    "e1b8135327bfc26dd0d832f4d155fed4",
    "fddb1d94a1fa065d6dd9b6997c8cb3c8",
    "231233de113069264752787699504aaf",
    "6585c7b813299af1ce71e54ce9776b84",
    "ad218ecf00d9b705804e71cf6588ab8a"
]

def check_scraperapi_credits(api_key):
    url = f"https://api.scraperapi.com/account?api_key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            limit = data.get("requestLimit", 0)
            used = data.get("requestCount", 0)
            return limit - used
    except Exception as e:
        print(f"❌ Error verificando créditos de {api_key}: {e}")
    return 0

def get_valid_scraperapi_key():
    for key in scraperapi_keys:
        if check_scraperapi_credits(key) > 5:  # Puedes ajustar el umbral
            return key
    return None  # Si ninguna sirve


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

    # Casos especiales conocidos
    if "barcelona" in nombre_limpio and "espanyol" in nombre_limpio:
        return "espanyol"
    if "barcelona" in nombre_limpio:
        return "barcelona"
    if "atletico" in nombre_limpio and "madrid" in nombre_limpio:
        return "atletico madrid"
    if "real madrid" in nombre_limpio:
        return "real madrid"
    if "real sociedad" in nombre_limpio:
        return "real sociedad"
    if "rayo vallecano" in nombre_limpio:
        return "rayo vallecano"
    if "las palmas" in nombre_limpio:
        return "las palmas"
    if "real betis" in nombre_limpio:
        return "betis"
    if "deportivo alaves" in nombre_limpio or "alaves" in nombre_limpio:
        return "alaves"

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
        "sunderland": ["sunderland", "sunderland afc"],
        "burnley": ["burnley", "burnley fc"],
        "leeds united": ["leeds", "leeds united", "leeds united fc"],

        # LaLiga
        "athletic": ["athletic club", "athletic bilbao"],
        "celta vigo": ["celta vigo", "rc celta de vigo"],
        "sevilla": ["sevilla", "sevilla fc"],
        "valencia": ["valencia", "valencia cf"],
        "barcelona": ["fc barcelona", "barcelona"],
        "atletico madrid": ["atletico de madrid", "club atletico de madrid", "atletico madrid"],
        "real madrid": ["real madrid"],
        "real sociedad": ["real sociedad", "real sociedad de futbol"],
        "rayo vallecano": ["rayo vallecano"],
        "las palmas": ["las palmas"],
        "betis": ["real betis", "betis"],
        "alaves": ["deportivo alaves", "alaves"],
        "espanyol": ["espanyol", "rcd espanyol", "rcd espanyol de barcelona"],

        # ligue1
        "paris sg": ["paris sg", "paris saint-germain", "psg"],
        "marseille": ["marseille", "olympique marseille"],
        "lyon": ["lyon", "olympique lyonnais"],
        "monaco": ["monaco", "as monaco"],
        "lille": ["lille", "losc lille"],
        "rennes": ["rennes", "stade rennais", "stade rennais fc"],
        "nantes": ["nantes", "fc nantes"],
        "nice": ["nice", "ogc nice"],
        "toulouse": ["toulouse", "toulouse fc"],
        "montpellier": ["montpellier", "montpellier hsc"],
        "reims": ["reims", "stadede reims", "stade de reims"],
        "strasbourg": ["strasbourg", "rc strasbourg"],
        "brest": ["brest", "stadebrestois", "stadé brestois"],
        "lens": ["lens", "rc lens"],
        "le havre": ["le havre", "le havre ac"],
        "angers": ["angers", "angers sco"],
        "auxerre": ["auxerre", "aj auxerre"],
        "saint-etienne": ["saint-etienne", "saint etienne", "as saint-etienne"]

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


def obtener_odds(liga_sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{liga_sport_key}/odds?regions=eu&markets=h2h&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            print("Error al obtener cuotas:", resp.status_code)
            return {}
        data = resp.json()
        odds_dict = {}
        for event in data:
            home = normalizar_nombre_equipo(event.get("home_team", ""))
            away = normalizar_nombre_equipo(event.get("away_team", ""))
            outcomes = {}
            for bm in event.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") == "h2h":
                        for outcome in market.get("outcomes", []):
                            outcomes[outcome['name'].lower()] = outcome['price']
                if outcomes:
                    break  # Tomamos solo la primera casa de apuestas con datos
            odds_dict[(home, away)] = outcomes
        return odds_dict
    except Exception as e:
        print(f"Error al consultar odds: {e}")
        return {}


def calcular_probabilidades(score_local, score_visit):
    score_local *= 1.05
    diff = score_local - score_visit
    exp_diff = exp(diff / 10)
    exp_inv = exp(-diff / 10)

    prob_local = 100 * exp_diff / (exp_diff + exp_inv + 1)
    prob_visit = 100 * exp_inv / (exp_diff + exp_inv + 1)
    prob_draw = 100 - (prob_local + prob_visit)

    return round(prob_local, 1), round(prob_visit, 1), round(prob_draw, 1)

def obtener_estadisticas_avanzadas(fbref_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }

    api_key = get_valid_scraperapi_key()
    if not api_key:
        print("❌ No hay API keys de ScraperAPI disponibles.")
        return []

    proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url=https://fbref.com/en/comps/{fbref_id}/stats"

    response = requests.get(proxy_url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    def parse_table(table_id, columns):
        # Buscar directamente en el HTML
        table = soup.find("table", id=table_id)
        
        if not table:
            # Buscar en los comentarios si no se encontró directamente
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                if table_id in comment:
                    comment_soup = BeautifulSoup(comment, "html.parser")
                    table = comment_soup.find("table", id=table_id)
                    if table:
                        break
        if not table:
            return table_id, {}

        data = {}
        rows = table.find("tbody").find_all("tr")
        for row in rows:
            if row.get("class") == ["thead"]:
                continue
            team = row.find("th").text.strip()
            stats = {}
            for cell in row.find_all("td"):
                stat = cell.get("data-stat")
                if stat in columns:
                    stats[stat] = cell.text.strip()
            data[team] = stats
        return table_id, data

    tables = [
        ("stats_squads_standard_for", ["possession", "goals", "xg_assist", "npxg", "cards_yellow", "cards_red"]),
        ("stats_squads_passing_for", ["passes_completed"]),
        ("stats_squads_possession_for", ["touches"]),
        ("stats_squads_shooting_for", ["shots_on_target"]),
        ("stats_squads_keeper_adv_for", ["gk_psxg"]),
        ("stats_squads_keeper_for", ["gk_goals_against", "gk_clean_sheets_pct"]),
    ]

    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for table_id, data in executor.map(lambda args: parse_table(*args), tables):
            results[table_id] = data

    standard = results["stats_squads_standard_for"]
    passing = results["stats_squads_passing_for"]
    misc = results["stats_squads_possession_for"]
    shooting = results["stats_squads_shooting_for"]
    keepers_adv = results["stats_squads_keeper_adv_for"]
    keepers = results["stats_squads_keeper_for"]

    equipos = {}
    for team in standard:
        equipos[team] = {
            "team": team,
            "possession": standard[team].get("possession", "0"),
            "goals": standard[team].get("goals", "0"),
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
        and now - last_update_por_liga[liga] < 43200  # 12 horas = 12 * 3600
    ):
        return jsonify(cache_por_liga[liga])

    competition_id = LIGAS[liga]["competition_id"]
    fbref_id = LIGAS[liga]["fbref_id"]
    stats = obtener_estadisticas_avanzadas(fbref_id)
    partidos = obtener_partidos(competition_id)
    odds_liga = obtener_odds(sport_key_map[liga])
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
            odds = odds_liga.get((normalizar_nombre_equipo(home), normalizar_nombre_equipo(away)), {})
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
                    "confidence": round(ventaja, 1) + 4,
                    "odds": odds
                })
            except Exception as e:
                print(f"Error procesando partido {home} vs {away}: {e}")
                continue

    # ✅ Guardar en caché solo si hay resultados
    if resultados:
        cache_por_liga[liga] = resultados
        last_update_por_liga[liga] = now

    return jsonify(resultados)


if __name__ == "__main__":
    app.run(debug=True)