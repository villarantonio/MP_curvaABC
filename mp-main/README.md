# Dashboard Executivo


## 📊 Sobre o Projeto

Este é um **Dashboard Executivo** desenvolvido como uma página web interativa para análise de vendas e produtos. O dashboard fornece insights inteligentes baseados em dados de vendas, utilizando análise de curva ABC e inteligência artificial.

## 🚀 Funcionalidades

### 📈 Visualizações
- **Gráfico de Curva ABC**: Visualização interativa da classificação de produtos (A, B, C)
- **Gráfico Temporal**: Evolução das vendas ao longo do tempo
- **Rankings**: Top 10 produtos mais e menos vendidos

### 🔍 Filtros e Interatividade
- **Filtro por Período**: Selecione um intervalo de meses para análise
- **Filtro por Loja**: Visualize dados específicos de cada loja
- **Gráfico ABC Interativo**: Clique nas categorias para filtrar rankings
- **Busca de Insights**: Barra de pesquisa no relatório completo de IA

### 🧠 Inteligência Artificial
- **Relatório Completo de IA**: Análises e diagnósticos automatizados
- **Recomendações de Ação**: Sugestões baseadas em dados para cada produto
- **Classificação ABC Automática**: Categorização automática de produtos por importância

## 🛠️ Tecnologias Utilizadas

- **HTML5**: Estrutura da página
- **CSS3**: Estilização moderna e responsiva
- **JavaScript**: Lógica e interatividade
- **Chart.js 4.4.0**: Biblioteca para criação de gráficos interativos

## 📊 Classificação ABC

O dashboard utiliza a análise de curva ABC para classificar produtos:

- **Categoria A**: Produtos que representam ~80% do faturamento (maior importância)
- **Categoria B**: Produtos que representam ~15% do faturamento (importância média)
- **Categoria C**: Produtos que representam ~5% do faturamento (menor importância)

## 🎨 Interface

A interface foi desenvolvida com foco em:
- Design moderno e limpo
- Responsividade para diferentes tamanhos de tela
- Interatividade intuitiva
- Visualizações claras e informativas

## 📝 Estrutura de Dados

O dashboard espera dados no formato JSON contendo:
- Informações de vendas por loja
- Análises mensais de produtos

## 🔄 Atualizações

Este dashboard é atualizado continuamente com novas funcionalidades e melhorias.
---

## Changelog

### 2025-12-04 — Atualização: `index.html`

- Arquivo atualizado: `index.html` substituído/atualizado no commit mais recente.
- Correções e refatorações de código para melhorar performance e legibilidade.

Principais mudanças visuais e de comportamento:

- **Gráfico ABC:** rótulos simplificados (apenas contagens A/B/C) e tooltip condensado mostrando valor em R$ e percentual — melhora a leitura rápida dos valores.
- **Interatividade do gráfico ABC:** clique agora filtra as listas de ranking de forma mais direta (top 10 mais/menos vendidos) com lógica de filtragem simplificada e botões de "Restaurar" exibidos corretamente.
- **Painel de Insights (IA):** contagem de insights (`insightCount`) atualizada diretamente; cards de insight tiveram ajuste na posição da tag ABC e estilo levemente ajustado para consistência visual.
- **Busca de Insights:** comportamento de filtro simplificado (busca por nome e texto do insight) para respostas mais rápidas; remoção de checagens redundantes.
- **Pequenas melhorias de UI:** simplificação de legendas, ajustes em estilos e visibilidade de botões — nenhum redesign radical, foco em clareza e performance.


## Histórico (commits recentes)

As entradas abaixo foram extraídas do histórico Git do repositório e mostram as alterações mais recentes.

- `6cf5630` — 2025-12-04 — Luccas — Add changelog entry for 2025-12-04 (index.html update)
- `1b54b0c` — 2025-12-04 — Luccas — Add new index.html
- `d24760b` — 2025-12-03 — Luccas — Update README.md
- `5c9cf8f` — 2025-12-03 — Luccas — Atualiza Dashboard Executivo com análise ABC interativa, busca de insights e melhorias
- `4dd003d` — 2025-12-03 — Luccas — Adiciona Dashboard Executivo com análise ABC e insights de IA
- `64a1a43` — 2025-12-01 — Luccas — Delete index
- `1779d8c` — 2025-12-01 — Luccas — Merge pull request #2 from LuccasJose/nuvem-teste1
- `cb79dec` — 2025-12-01 — Luccas — Create index


## Histórico por Versão

O histórico abaixo agrupa as alterações por versão (data/versão aproximada). Se desejar, posso ajustar os números de versão para seguir um esquema semântico (`v0.1.0` etc.) ou criar tags Git correspondentes.

- **v0.1 — 2025-12-01**
	- `cb79dec` — Create index
	- `1779d8c` — Merge pull request #2 from LuccasJose/nuvem-teste1
	- `64a1a43` — Delete index

- **v0.2 — 2025-12-03**
	- `4dd003d` — Adiciona Dashboard Executivo com análise ABC e insights de IA
	- `5c9cf8f` — Atualiza Dashboard Executivo com análise ABC interativa, busca de insights e melhorias
	- `d24760b` — Update README.md

- **v0.3 — 2025-12-04**
	- `1b54b0c` — Add new index.html
	- `6cf5630` — Add changelog entry for 2025-12-04 (index.html update)
	- `b0944ea` — Add history section (recent commits) to README

---

**Desenvolvido para análise estratégica de vendas e produtos**

