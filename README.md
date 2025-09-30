# Local Intelligence Maps [ MBA USP/Esalq ]

Análise espacial e socioeconômica de estabelecimentos comerciais em São Paulo utilizando dados do Google Places API e análise de componentes principais (PCA).

## Descrição

Este projeto coleta, normaliza e analisa dados de estabelecimentos de fast-food (McDonald's, Burger King, Bob's) na cidade de São Paulo, correlacionando métricas do Google Places com variáveis socioeconômicas dos distritos. O objetivo é identificar padrões espaciais de localização através de técnicas de análise multivariada.

## Funcionalidades

- **Coleta de Dados**: Script automatizado para buscar estabelecimentos via Google Places API
- **Normalização**: Pipeline de tratamento e padronização de distritos usando Nominatim (OpenStreetMap)
- **Análise PCA**: Redução de dimensionalidade e identificação de componentes principais
- **Visualização**: Mapas e gráficos para análise espacial e correlação de variáveis

## Estrutura do Projeto

```
local-intelligence-maps/
├── get_google_places.py          # Coleta de dados via Google Places API
├── normalize_data.py              # Normalização e padronização de distritos
├── aplicacao_pca_usp_google.ipynb # Análise PCA e visualizações
├── requirements.txt               # Dependências do projeto
├── .env                          # Variáveis de ambiente (não versionado)
├── base/                         # Dados socioeconômicos base
├── resultados/                   # Outputs gerados
└── imagens/                      # Visualizações exportadas
```

## Tecnologias

- **Python 3.x**
- **Pandas** - Manipulação de dados
- **NumPy** - Computação numérica
- **Factor Analyzer** - Análise PCA
- **Matplotlib/Plotly** - Visualizações
- **Requests** - Requisições HTTP
- **python-dotenv** - Gerenciamento de variáveis de ambiente
- **Loguru** - Sistema de logs

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/local-intelligence-maps.git
cd local-intelligence-maps
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
Crie um arquivo `.env` na raiz do projeto com:
```
GOOGLE_API_KEY=sua_chave_api_google
ASK_THEME=nome_estabelecimento
DISTRITOS_SP=lista_de_distritos_separados_por_virgula
```

## Uso

### 1. Coleta de Dados

```bash
python get_google_places.py
```

Este script:
- Busca estabelecimentos via Google Places API
- Cobre todos os distritos de São Paulo
- Salva resultados em JSON e CSV

### 2. Normalização

```bash
python normalize_data.py \
  --input-json entrada.json \
  --output-json saida.json \
  --output-csv saida.csv \
  --use-nominatim \
  --cache-file cache.json
```

Este script:
- Filtra endereços de São Paulo-SP
- Normaliza nomes de distritos
- Utiliza Nominatim para geocodificação reversa
- Adiciona campos: `distrito_atualizado`, `confianca_distrito`, `metodo_distrito`

### 3. Análise PCA

Execute o notebook Jupyter:
```bash
jupyter notebook aplicacao_pca_usp_google.ipynb
```

O notebook realiza:
- Integração de dados socioeconômicos
- Análise de componentes principais
- Visualizações espaciais e estatísticas
- Exportação de resultados

## Dados de Saída

O projeto gera os seguintes arquivos:

- `*_SOR_*.csv/json` - Dados brutos coletados
- `*_SOT_*.csv/json` - Dados normalizados e tratados
- `dados_unificados_*_socioec_var_metricas.csv` - Dados finais com PCA

## Metodologia

1. **Coleta**: Busca via Google Places API usando Text Search e Nearby Search
2. **Normalização**: Padronização de distritos com validação por coordenadas e endereços
3. **Integração**: Merge com dados socioeconômicos (IDH, renda, população)
4. **PCA**: Redução de dimensionalidade para identificar fatores latentes
5. **Visualização**: Mapas coropléticos e gráficos de correlação

## Limitações

- A API do Google Places tem limites de quota
- Nominatim requer respeito ao rate limit (1 req/s)
- Alguns endereços podem ter distrito "Não Identificado"

## Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## Licença

Este projeto é de código aberto para fins acadêmicos e de pesquisa.

## Contato

Para dúvidas ou sugestões, abra uma issue no repositório.
