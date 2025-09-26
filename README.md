✈️ Dashboard de Atrasos de Voos no Brasil (2022–2024)

Análise de atrasos de voos no Brasil com visualização interativa.

🔍 Objetivo
-Visualizar KPIs (total de voos, voos atrasados e % de atraso).

-Rankear Top 10 aeroportos por volume de atrasos.

-Comparar companhias × ano (Top 10).

-Observar padrões por dia da semana e período do dia.

-Exibir tendência de aumento de atrasos (2022 → 2024).

-Escopo: somente aeroportos do Brasil (registros de origem fora do país são filtrados).

🧱 Stack

Python 3.9+
Streamlit
Pandas
Seaborn / Matplotlib

🛠️ Instalação
1) Clonar o repositório
git clone https://github.com/<usuario>/<repositorio>.git
cd <repositorio>

2) Dependências

Com requirements.txt:
pip install -r requirements.txt
Ou diretamente:
pip install streamlit pandas seaborn matplotlib

📂 Estrutura
Estrutura
.
├─ tela.py                  # app principal

├─ requirements.txt

├─ dataset/                 # dados de entrada (não versionados)

│  ├─ merge_2022.csv

│  ├─ merge_2023.csv

│  ├─ merge_2024.csv

│  ├─ merge_2025.csv       # opcional

│  ├─ airport-codes.csv    # opcional (nomes de aeroportos)

│  └─ airlines-codes.csv   # opcional (nomes de cias)

└─ docs/                    # opcional (imagens para o README)


▶️ Execução

streamlit run tela.py
A interface abrirá no navegador (ou use a URL exibida no terminal).

📊 Funcionalidades

-KPIs gerais do período filtrado.

-Top 10 aeroportos por atrasos.

-Companhias × ano (Top 10).

-Atrasos por dia da semana (Seg…Dom).

-Atrasos por período do dia (Madrugada / Manhã / Tarde / Noite).

-Tendência de aumento (2022 → 2024): exibe somente aeroportos com evolução consistente de atrasos (2023 ≥ 2022 e 2024 > 2023).

🧪 Troubleshooting

*ModuleNotFoundError (ex.: seaborn)
Instale a dependência:
pip install seaborn

*Streamlit não abre automaticamente
Copie a URL mostrada no terminal e cole no navegador.

*Erro de leitura de CSV
Verifique separador/encoding. O app tenta automaticamente ; ou , e encodings comuns (utf-8, latin1, cp1252).

*Tendência não aparece
Selecione simultaneamente 2022, 2023 e 2024 nos filtros.
