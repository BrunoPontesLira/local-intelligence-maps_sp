"""
Script para obter dados de estabelecimentos em São Paulo
usando Google Places API
"""

import os
import requests
import json
import time
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dotenv import load_dotenv
from datetime import datetime
from loguru import logger 

# Carrega variáveis do arquivo .env
load_dotenv()
LOCAL = os.getenv('ASK_THEME')

class DataCollector:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY não encontrada no arquivo .env")
        
        self.base_url = "https://maps.googleapis.com/maps/api/place"
        self.session = requests.Session()
        
        # Coordenadas aproximadas de São Paulo (centro expandido)
        self.sao_paulo_center = {
            'lat': -23.550520,
            'lng': -46.633308
        }
        
        # Raio em metros (50km para cobrir toda a região metropolitana)
        self.radius = 50000
        
        self.results = []
    
    def search_nearby_places(self, location: Dict[str, float], radius: int, 
                           keyword: str = LOCAL, next_page_token: Optional[str] = None) -> Dict:
        """
        Busca lugares próximos usando a API Nearby Search
        """
        url = f"{self.base_url}/nearbysearch/json"
        
        params = {
            'key': self.api_key,
            'location': f"{location['lat']},{location['lng']}",
            'radius': radius,
            'keyword': keyword,
            'type': 'restaurant'
        }
        
        if next_page_token:
            params = {'key': self.api_key, 'pagetoken': next_page_token}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição: {e}")
            return {}
    
    def get_place_details(self, place_id: str, comprehensive: bool = True) -> Dict:
        """
        Obtém detalhes completos de um lugar específico
        
        Args:
            place_id: ID do lugar
            comprehensive: Se True, obtém TODOS os campos disponíveis
        """
        url = f"{self.base_url}/details/json"
        
        if comprehensive:
            # TODOS OS CAMPOS DISPONÍVEIS - dados máximos possíveis
            fields = (
                # BASIC/ESSENTIALS (baixo custo)
                'place_id,name,formatted_address,geometry,types,business_status,'
                'formatted_phone_number,website,opening_hours,plus_code,vicinity,'
                
                # CONTACT (custo médio)
                'international_phone_number,'
                'secondary_opening_hours,website,'
                
                # ATMOSPHERE (custo alto - dados valiosos)
                'rating,user_ratings_total,reviews,price_level,'
                'photos,curbside_pickup,delivery,dine_in,reservable,serves_beer,'
                'serves_breakfast,serves_brunch,serves_dinner,serves_lunch,'
                'serves_vegetarian_food,serves_wine,takeout,'
                
                # ACCESSIBILITY & AMENITIES
                'wheelchair_accessible_entrance'
            )
        else:
            # Campos básicos (custo mínimo)
            fields = (
                'place_id,name,formatted_address,geometry,formatted_phone_number,'
                'website,rating,user_ratings_total,opening_hours,price_level,'
                'business_status,types'
            )
        
        params = {
            'key': self.api_key,
            'place_id': place_id,
            'fields': fields
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get('result', {})
        except requests.exceptions.RequestException as e:
            print(f"Erro ao obter detalhes do lugar {place_id}: {e}")
            return {}
    
    
    def text_search_places(self, query: str) -> Dict:
        """
        Busca usando Text Search API (sem limite de 60 resultados)
        """
        url = f"{self.base_url}/textsearch/json"
        
        params = {
            'key': self.api_key,
            'query': query,
            'type': 'restaurant'
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro na busca por texto: {e}")
            return {}
    
    def validate_sao_paulo_location(self, place: Dict) -> bool:
        """
        Valida se o local está realmente em São Paulo
        Verifica endereço e coordenadas
        """
        address = place.get('formatted_address', '').lower()
        
        # Verificar se contém indicadores de São Paulo
        sp_indicators = [
            'são paulo', 'sao paulo', 'sp, brazil', ', sp ', 
            'sp, brasil', 'são paulo - sp', 'sao paulo - sp'
        ]
        
        address_valid = any(indicator in address for indicator in sp_indicators)
        
        # Verificar coordenadas (rough bounding box de São Paulo)
        geometry = place.get('geometry', {}).get('location', {})
        lat = geometry.get('lat')
        lng = geometry.get('lng')
        
        coords_valid = False
        if lat and lng:
            # Bounding box aproximado da Grande São Paulo
            sp_bounds = {
                'lat_min': -24.0, 'lat_max': -23.2,
                'lng_min': -47.0, 'lng_max': -46.0
            }
            
            coords_valid = (
                sp_bounds['lat_min'] <= lat <= sp_bounds['lat_max'] and
                sp_bounds['lng_min'] <= lng <= sp_bounds['lng_max']
            )
        
        return address_valid or coords_valid
    
    def extract_district_from_address(self, address: str) -> str:
        """
        Extrai o distrito do endereço usando os distritos oficiais de SP
        """
        if not address:
            return 'N/A'
        
        address_lower = address.lower()
        
        # Lista dos distritos para matching
        distritos_env = os.getenv('DISTRITOS_SP', '')
        if distritos_env:
            distritos_oficiais = [d.strip().lower() for d in distritos_env.split(',')]
        else:
            # Fallback com alguns distritos principais
            distritos_oficiais = [
                'centro', 'liberdade', 'sé', 'república', 'bela vista',
                'pinheiros', 'vila madalena', 'moema', 'jardins',
                'itaim bibi', 'vila olímpia', 'santana', 'ipiranga'
            ]
        
        # Buscar distrito no endereço
        for distrito in distritos_oficiais:
            # Variações do nome do distrito
            district_variations = [
                distrito,
                distrito.replace(' ', ''),  # Remove espaços
                distrito.replace('ã', 'a').replace('ç', 'c').replace('é', 'e').replace('á', 'a').replace('í', 'i').replace('ú', 'u').replace('ó', 'o'),  # Remove acentos
            ]
            
            for variation in district_variations:
                if variation in address_lower:
                    # Retorna o nome original (com acentos e formatação correta)
                    if distritos_env:
                        original_district = next((d.strip() for d in distritos_env.split(',') 
                                            if d.strip().lower() == distrito), distrito.title())
                        return original_district
                    return distrito.title()
        
        # Se não encontrou distrito específico, tentar algumas inferências
        region_mapping = {
            'centro': 'Centro',
            'zona sul': 'Campo Belo', 
            'zona norte': 'Santana',
            'zona oeste': 'Pinheiros',
            'zona leste': 'Itaquera',
        }
        
        for region, district in region_mapping.items():
            if region in address_lower:
                return district
        
        return 'Não Identificado'
    
    def collect_all_local(self) -> List[Dict]:
        """
        Coleta todos os dados dos locais em São Paulo usando múltiplas estratégias
        para superar o limite de 60 resultados do Nearby Search
        """
        print(f"Iniciando busca abrangente por {LOCAL} em São Paulo...")
        all_places = {}  # Usar dict para evitar duplicatas por place_id
        
        # ESTRATÉGIA 1: Text Search por Distritos de São Paulo
        print("\n=== ESTRATÉGIA 1: Text Search por Distritos ===")
        
        # Buscar distritos do arquivo .env
        distritos_env = os.getenv('DISTRITOS_SP', '')
        
        if distritos_env:
            # Converter string em lista e limpar espaços
            distritos_list = [distrito.strip() for distrito in distritos_env.split(',')]
            print(f"📍 Carregados {len(distritos_list)} distritos de São Paulo do .env")
        else:
            # Fallback para lista básica se não encontrar no .env
            distritos_list = [
                "Centro São Paulo", "Zona Sul São Paulo", "Zona Norte São Paulo",
                "Zona Oeste São Paulo", "Zona Leste São Paulo", f"{LOCAL} São Paulo"
            ]
            print("⚠️ DISTRITOS_SP não encontrada no .env, usando busca básica")
        
        # Criar queries otimizadas para cada distrito
        text_queries = []
        for distrito in distritos_list:
            # Múltiplas variações para cada distrito
            text_queries.extend([
                f"{LOCAL} {distrito} São Paulo",
                f"{LOCAL} {distrito} São Paulo SP",
            ])
        
        print(f"🔍 Executando {len(text_queries)} buscas específicas por distrito...")
        
        for i, query in enumerate(text_queries, 1):
            print(f"Buscando ({i}/{len(text_queries)}): {query}")
            search_result = self.text_search_places(query)
            
            if 'results' in search_result:
                results_found = 0
                for place in search_result['results']:
                    if place['place_id'] not in all_places:
                        all_places[place['place_id']] = place
                        results_found += 1
                
                print(f"  → {results_found} novos {LOCAL} encontrados")
                
                # Busca páginas adicionais se disponível
                next_page_token = search_result.get('next_page_token')
                page = 2
                
                while next_page_token and page <= 3:  # Limitar a 3 páginas por distrito
                    print(f"    Página {page}...")
                    time.sleep(2)  # Delay obrigatório para next_page_token
                    
                    params = {'key': self.api_key, 'pagetoken': next_page_token}
                    try:
                        response = self.session.get(f"{self.base_url}/textsearch/json", params=params)
                        page_result = response.json()
                        
                        if 'results' in page_result:
                            page_results_found = 0
                            for place in page_result['results']:
                                if place['place_id'] not in all_places:
                                    all_places[place['place_id']] = place
                                    page_results_found += 1
                            
                            if page_results_found > 0:
                                print(f"    → +{page_results_found} {LOCAL} adicionais")
                        
                        next_page_token = page_result.get('next_page_token')
                        page += 1
                    except Exception as e:
                        print(f"    Erro na página {page}: {e}")
                        break
            else:
                print(f"  → Nenhum resultado para {query}")
            
            # Delay entre queries para evitar rate limiting
            time.sleep(0.5)
        
        print(f"\n✅ Text Search por Distritos encontrou {len(all_places)} {LOCAL} únicos")
        
        # ESTRATÉGIA 2: Nearby Search em múltiplas áreas
        print("\n=== ESTRATÉGIA 2: Nearby Search por áreas ===")
        search_areas = [
            {"name": "Centro/Sé", "lat": -23.5505, "lng": -46.6333, "radius": 8000},
            {"name": "Zona Sul", "lat": -23.6094, "lng": -46.6927, "radius": 8000},
            {"name": "Zona Norte", "lat": -23.4858, "lng": -46.6311, "radius": 8000},
            {"name": "Zona Oeste", "lat": -23.5280, "lng": -46.7425, "radius": 8000},
            {"name": "Zona Leste", "lat": -23.5629, "lng": -46.5477, "radius": 8000},
            {"name": "ABC Paulista", "lat": -23.6648, "lng": -46.5348, "radius": 10000},
            {"name": "Guarulhos", "lat": -23.4543, "lng": -46.5339, "radius": 8000},
            {"name": "Osasco", "lat": -23.5329, "lng": -46.7918, "radius": 8000},
        ]
        
        initial_count = len(all_places)
        
        for area in search_areas:
            print(f"Buscando na {area['name']}...")
            
            search_result = self.search_nearby_places(
                {"lat": area["lat"], "lng": area["lng"]}, 
                area["radius"], 
                LOCAL
            )
            
            if 'results' in search_result:
                area_places = search_result['results']
                
                # Busca páginas adicionais (máximo 3 por área)
                next_page_token = search_result.get('next_page_token')
                page = 2
                
                while next_page_token and page <= 3:
                    time.sleep(2)
                    search_result = self.search_nearby_places(
                        {"lat": area["lat"], "lng": area["lng"]}, 
                        area["radius"], 
                        next_page_token=next_page_token
                    )
                    
                    if 'results' in search_result:
                        area_places.extend(search_result['results'])
                    
                    next_page_token = search_result.get('next_page_token')
                    page += 1
                
                # Adiciona apenas locais únicos
                new_places = 0
                for place in area_places:
                    if place['place_id'] not in all_places:
                        all_places[place['place_id']] = place
                        new_places += 1
                
                print(f"  Encontrados {new_places} novos {LOCAL} na {area['name']}")
            
            time.sleep(1)  # Delay entre áreas
        
        nearby_new = len(all_places) - initial_count
        print(f"Nearby Search adicionou {nearby_new} {LOCAL} únicos")
        print(f"\nTOTAL ÚNICO: {len(all_places)} {LOCAL} encontrados")
        
        # Processa detalhes de todos os locais únicos
        print(f"\n=== COLETANDO DETALHES ===")
        local_data = []
        
        for i, (place_id, place) in enumerate(all_places.items(), 1):
            print(f"Processando {i}/{len(all_places)}: {place.get('name', 'N/A')}")
            
            # Obtém detalhes completos
            details = self.get_place_details(place['place_id'])
            
            if details:
                combined_data = {
                        'place_id': place['place_id'],
                        'name': details.get('name', place.get('name', 'N/A')),
                        'address': details.get('formatted_address', 'N/A'),
                        'distrito': self.extract_district_from_address(details.get('formatted_address', '')),
                        'latitude': details.get('geometry', {}).get('location', {}).get('lat', 'N/A'),
                        'longitude': details.get('geometry', {}).get('location', {}).get('lng', 'N/A'),
                        'phone': details.get('formatted_phone_number', 'N/A'),
                        'website': details.get('website', 'N/A'),
                        'rating': details.get('rating', 'N/A'),
                        'total_ratings': details.get('user_ratings_total', 'N/A'),
                        'price_level': details.get('price_level', 'N/A'),
                        'business_status': details.get('business_status', 'N/A'),
                        'is_open_now': place.get('opening_hours', {}).get('open_now', 'N/A'),
                        'types': ', '.join(details.get('types', [])),
                        'opening_hours': self.format_opening_hours(details.get('opening_hours', {})),
                        'photos_count': len(details.get('photos', [])),
                        'reviews_count': len(details.get('reviews', [])),
                        'delivery': details.get('delivery', 'N/A'),
                        'dine_in': details.get('dine_in', 'N/A'),
                        'takeout': details.get('takeout', 'N/A'),
                        'serves_breakfast': details.get('serves_breakfast', 'N/A'),
                        'serves_dinner': details.get('serves_dinner', 'N/A'),
                        'serves_lunch': details.get('serves_lunch', 'N/A'),
                        'wheelchair_accessible_entrance': details.get('wheelchair_accessible_entrance', 'N/A'),
                    }
                
                local_data.append(combined_data)
            
            # Rate limiting
            time.sleep(0.1)
        
        self.results = local_data
        print(f"\n🎉 COLETA CONCLUÍDA! Encontrados {len(local_data)} {LOCAL} em São Paulo")
        print(f"   📍 Busca realizada em {len(distritos_list) if 'distritos_list' in locals() else 'múltiplos'} distritos")
        print(f"   🔍 Cobertura completa da região metropolitana!")
        return local_data
    
    def format_opening_hours(self, opening_hours: Dict) -> str:
        """
        Formata horários de funcionamento
        """
        if not opening_hours or 'weekday_text' not in opening_hours:
            return 'N/A'
        
        return ' | '.join(opening_hours['weekday_text'])
    
    def save_to_csv(self, filename: Optional[str] = None) -> str:
        """
        Salva os resultados em arquivo CSV usando pandas
        """
        if not self.results:
            print("Nenhum dado para salvar. Execute collect_all_local() primeiro.")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{LOCAL}_SOR_{timestamp}.csv"
        
        # Criar DataFrame e salvar com pandas
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"Dados salvos em: {filename}")
        return filename
    
    def save_to_json(self, filename: Optional[str] = None) -> str:
        """
        Salva os resultados em arquivo JSON
        """
        if not self.results:
            print("Nenhum dado para salvar. Execute collect_all_local() primeiro.")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{LOCAL}_SOR_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(self.results, jsonfile, ensure_ascii=False, indent=2)
        
        print(f"Dados salvos em: {filename}")
        return filename
    


def main():
    """
    Função principal
    """
    try:
        collector = DataCollector()
        
        # Coleta os dados
        local_data = collector.collect_all_local()
        json_file = collector.save_to_json()
        csv_file = collector.save_to_csv()
        
        
        if local_data:
            
            print(f"\n📁 ARQUIVOS GERADOS:")
            print(f"  📊 Dataset completo (CSV): {csv_file}")
            print(f"  📊 Dataset completo (JSON): {json_file}")
            
            print(f"\n🗺️ COBERTURA DA BUSCA:")
            if 'DISTRITOS_SP' in os.environ:
                total_distritos = len(os.getenv('DISTRITOS_SP', '').split(','))
                print(f"  📍 Buscou em {total_distritos} distritos de São Paulo")
                print(f"  🔍 Cobertura: Todos os distritos oficiais da cidade")
            else:
                print(f"  📍 Busca básica por áreas (configure DISTRITOS_SP para busca completa)")
            
        else:
            print(f"❌ Nenhum {LOCAL} encontrado.")
            
    except Exception as e:
        logger.exception(f"Erro durante a execução: {e}")


if __name__ == "__main__":
    main()
