import json, re, unicodedata, argparse, time, sys, requests
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import os
from dotenv import load_dotenv
from datetime import datetime


# ---------------- Configurações padrão ----------------
load_dotenv()
LOCAL = os.getenv('ASK_THEME')
print(f'LOCAL: {LOCAL}')

USER_AGENT = "AB-Tecnologia-SP-Distritos/1.0 (contato: seuemail@empresa.com)"  # personalize
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"

DISTRITOS_SP = [
    "Água Rasa","Alto de Pinheiros","Anhanguera","Aricanduva","Artur Alvim","Barra Funda","Bela Vista","Belém",
    "Bom Retiro","Brás","Brasilândia","Butantã","Cachoeirinha","Cambuci","Campo Belo","Campo Grande","Campo Limpo",
    "Cangaíba","Capão Redondo","Carrão","Casa Verde","Cidade Ademar","Cidade Dutra","Cidade Líder","Cidade Tiradentes",
    "Consolação","Cursino","Ermelino Matarazzo","Freguesia do Ó","Grajaú","Guaianases","Ipiranga","Itaim Bibi",
    "Itaim Paulista","Itaquera","Jabaquara","Jaçanã","Jaguara","Jaguaré","Jaraguá","Jardim Ângela","Jardim Helena",
    "Jardim Paulista","Jardim São Luís","José Bonifácio","Lajeado","Lapa","Liberdade","Limão","Mandaqui","Marsilac",
    "Moema","Mooca","Morumbi","Parelheiros","Pari","Parque do Carmo","Pedreira","Penha","Perdizes","Perus","Pinheiros",
    "Pirituba","Ponte Rasa","Raposo Tavares","República","Rio Pequeno","Sacomã","Santa Cecília","Santana","Santo Amaro",
    "São Domingos","São Lucas","São Mateus","São Miguel","São Rafael","Sé","Socorro","Tatuapé","Tremembé","Tucuruvi",
    "Vila Andrade","Vila Curuçá","Vila Formosa","Vila Guilherme","Vila Jacuí","Vila Leopoldina","Vila Maria","Vila Mariana",
    "Vila Matilde","Vila Medeiros","Vila Prudente","Vila Sônia"
]

# Bairro→Distrito (alto-confiável; ajuste conforme sua base)
NEIGHBORHOOD_TO_DISTRITO = {
    # Centro/Sul
    "bosque da saúde": "Saúde",
    "vila clementino": "Vila Mariana",
    "mirandópolis": "Saúde",
    "mirandopolis": "Saúde",
    "paraíso": "Vila Mariana",
    "paraiso": "Vila Mariana",
    "cerqueira césar": "Jardim Paulista",
    "cerqueira cesar": "Jardim Paulista",
    "planalto paulista": "Moema",
    "aclimacao": "Liberdade",
    "aclimação": "Liberdade",
    # Leste
    "mooca": "Mooca",
    "móoca": "Mooca",
    "tatuapé": "Tatuapé",
    "tatuape": "Tatuapé",
    "penha de frança": "Penha",
    "penha de franca": "Penha",
    "vila reg. feijó": "Vila Formosa",
    "vila regente feijó": "Vila Formosa",
    "vila reg. feijo": "Vila Formosa",
    "vila regente feijo": "Vila Formosa",
    "jardim avelino": "Vila Prudente",
    "quarta parada": "Mooca",
    "vila carrão": "Carrão",
    "vila carrao": "Carrão",
    "vila formosa": "Vila Formosa",
    "sapopemba": "Sapopemba",
    # Oeste
    "jardim paulista": "Jardim Paulista",
    "pinheiros": "Pinheiros",
    "itaim bibi": "Itaim Bibi",
    "vila nova conceição": "Itaim Bibi",
    "vila nova conceicao": "Itaim Bibi",
    # Norte
    "tucuruvi": "Tucuruvi",
    "santana": "Santana",
    # Eixos/Aeroportos
    "moreira guimarães": "Moema",
    "moreira guimaraes": "Moema",
}

CIDADES_GRANDE_SP = [
    "santo andré", "sao bernardo do campo", "são bernardo do campo", "são caetano do sul", "sao caetano do sul",
    "osasco", "guarulhos", "diadema", "mauá", "maua", "barueri", "carapicuíba", "carapicuiba", "taboão da serra",
    "taboao da serra", "cotia", "itapecerica da serra", "santana de parnaíba", "santana de parnaiba"
]

# ---------------- Utilidades ----------------

def _norm(s:str)->str:
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

DIST_NORM = { _norm(d): d for d in DISTRITOS_SP }

def _has_city_sao_paulo(addr: str) -> bool:
    a = _norm(addr)
    if "sao paulo" in a or "são paulo" in a:
        return not any(city in a for city in CIDADES_GRANDE_SP)
    return False

def _find_distrito_in_address(address: str):
    addr_norm = _norm(address)
    for d_norm, d_orig in sorted(DIST_NORM.items(), key=lambda x: -len(x[0])):
        pattern = rf"\b{re.escape(d_norm)}\b"
        if re.search(pattern, addr_norm):
            return d_orig
    return None

def _fallback_from_neighborhood(address: str):
    addr_norm = _norm(address)
    for nbh_norm, distrito in NEIGHBORHOOD_TO_DISTRITO.items():
        pattern = rf"\b{re.escape(_norm(nbh_norm))}\b"
        if re.search(pattern, addr_norm):
            return distrito
    return None

def _pick_distrito_from_nominatim(addr: dict):
    for key in ("city_district","suburb","neighbourhood","quarter"):
        val = addr.get(key)
        if not val:
            continue
        n = _norm(val)
        if n in DIST_NORM:
            return DIST_NORM[n], ("alta" if key=="city_district" else "média")
        for dn, original in DIST_NORM.items():
            if re.search(rf"\b{re.escape(dn)}\b", n):
                return original, "média"
    return "Não Identificado", "baixa"

def nominatim_search(address: str, sleep: float):
    import requests, time
    params = {
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "street": address,
        "city": "São Paulo",
        "state": "SP",
        "countrycodes": "br",
    }
    r = requests.get(NOMINATIM_SEARCH, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    js = r.json()
    time.sleep(sleep)
    return js[0] if isinstance(js, list) and js else None

def nominatim_reverse(lat: float, lon: float, sleep: float):
    import requests, time
    params = {"format": "jsonv2", "lat": lat, "lon": lon, "addressdetails": 1}
    r = requests.get(NOMINATIM_REVERSE, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    js = r.json()
    time.sleep(sleep)
    return js

# ----------------- Cache -----------------

def load_cache(path: Path) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(path: Path, cache: dict):
    if path:
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

# ----------------- Main -----------------

def main():
    today = datetime.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-json", help="JSON de entrada com registros", default=f"Bob’s_sao_paulo_20250906_214120.json")
    ap.add_argument("--output-json", default=f"{LOCAL}_saida_unificada_SOT.json")
    ap.add_argument("--output-csv",  default=f"{LOCAL}_saida_unificada_SOT.csv")
    ap.add_argument("--use-nominatim", action="store_true", help="Habilita consultas à API pública Nominatim")
    ap.add_argument("--cache-file", default=f"{LOCAL}_cache_nominatim.json", help="Arquivo de cache (json) p/ respostas do Nominatim")
    ap.add_argument("--sleep", type=float, default=1.1, help="Intervalo entre requests (segundos)")
    args = ap.parse_args()

    data = json.loads(Path(args.input_json).read_text(encoding="utf-8"))

    cache_path = Path(args.cache_file) if args.use_nominatim else None
    cache = load_cache(cache_path) if args.use_nominatim else {}

    total = len(data)
    kept_sp = 0
    resolved = 0
    methods_count = {"original":0, "address":0, "bairro":0, "nominatim_search":0, "nominatim_reverse":0, "nao_identificado":0}

    out = []
    for i, row in enumerate(tqdm(data, desc="Processando registros", unit="reg")):
        address = str(row.get("address") or "")
        lat = row.get("latitude") or row.get("geometry",{}).get("location",{}).get("lat")
        lon = row.get("longitude") or row.get("geometry",{}).get("location",{}).get("lng")

        # 0) Filtrar São Paulo - SP
        if not _has_city_sao_paulo(address):
            if args.use_nominatim and lat is not None and lon is not None:
                key = f"rev:{lat},{lon}"
                js = cache.get(key)
                if js is None:
                    try:
                        js = nominatim_reverse(float(lat), float(lon), args.sleep)
                        cache[key] = js
                    except Exception:
                        js = None
                if js and isinstance(js, dict):
                    city = _norm(js.get("address",{}).get("city") or js.get("address",{}).get("town") or "")
                    state = _norm(js.get("address",{}).get("state") or "")
                    country = _norm(js.get("address",{}).get("country_code") or "")
                    if city == "sao paulo" and (state in ("sp","sao paulo")) and country == "br":
                        pass
                    else:
                        continue
                else:
                    if any(city in _norm(address) for city in CIDADES_GRANDE_SP):
                        continue
                    if "sao paulo" not in _norm(address) and "são paulo" not in _norm(address):
                        continue
            else:
                if any(city in _norm(address) for city in CIDADES_GRANDE_SP):
                    continue
                if "sao paulo" not in _norm(address) and "são paulo" not in _norm(address):
                    continue

        kept_sp += 1

        # 1) Original válido
        prev = row.get("distrito")
        if isinstance(prev, str) and _norm(prev) in DIST_NORM:
            distrito, conf, metodo = DIST_NORM[_norm(prev)], "alta", "original"
        else:
            # 2) Endereço explícito
            distrito = _find_distrito_in_address(address)
            if distrito:
                conf, metodo = "alta", "address"
            else:
                # 3) Bairro→Distrito
                distrito = _fallback_from_neighborhood(address)
                if distrito:
                    conf, metodo = "média", "bairro"
                else:
                    conf, metodo = "baixa", "nao_identificado"

        # 4) Nominatim (opcional), se ainda baixa/média
        if (conf in ("baixa","média")):
            # 4a) search por endereço
            if address.strip():
                key = f"fwd:{_norm(address)}"
                js = cache.get(key)
                if js is None:
                    try:
                        js = nominatim_search(address, args.sleep)
                        cache[key] = js
                    except Exception:
                        js = None
                if js and isinstance(js, dict):
                    distrito_n, conf_n = _pick_distrito_from_nominatim(js.get("address", {}))
                    if distrito_n != "Não Identificado":
                        distrito, conf, metodo = distrito_n, conf_n, "nominatim_search"
            # 4b) reverse por lat/lon
            if (conf in ("baixa","média")) and (lat is not None and lon is not None):
                key = f"rev:{lat},{lon}"
                js = cache.get(key)
                if js is None:
                    try:
                        js = nominatim_reverse(float(lat), float(lon), args.sleep)
                        cache[key] = js
                    except Exception:
                        js = None
                if js and isinstance(js, dict):
                    distrito_n, conf_n = _pick_distrito_from_nominatim(js.get("address", {}))
                    if distrito_n != "Não Identificado":
                        distrito, conf, metodo = distrito_n, conf_n, "nominatim_reverse"

        row["distrito_atualizado"] = distrito
        row["confianca_distrito"] = conf
        row["metodo_distrito"] = metodo

        row["year"] = today.year
        row["month"] = today.month
        row["day"] = today.day
        methods_count[metodo] = methods_count.get(metodo, 0) + 1
        if distrito != "Não Identificado":
            resolved += 1
        out.append(row)

    if args.use_nominatim:
        save_cache(cache_path, cache)

    Path(args.output_json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(out).to_csv(args.output_csv, index=False, encoding="utf-8")

    print(f"Total registros entrada: {total}")
    print(f"Mantidos São Paulo - SP: {kept_sp}")
    print(f"Com distrito resolvido:  {resolved}")
    print("Métodos utilizados:")
    for k, v in methods_count.items():
        print(f"  - {k}: {v}")

if __name__ == "__main__":
    main()
