<div align="center">
  <img src="./static/images/logo.svg" alt="IPTV-API logo"  width="120" height="120"/>
</div>

<h1 align="center">IPTV-API</h1>

<p align="center">
  ⚡️ Ferramenta automática de atualização de fontes IPTV. Coleta, agrega múltiplas fontes, verifica disponibilidade, faz teste de velocidade e gera listas de reprodução (M3U, TXT ou API). Configurações avançadas permitem personalizar os resultados e exportá‑los para vários formatos compatíveis com os players.
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/12327" target="_blank">
    <img src="https://trendshift.io/api/badge/repositories/12327" alt="Guovin/iptv-api | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
  </a>
  <a href="https://trendshift.io/repositories/12327?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-12327" target="_blank" rel="noopener noreferrer">
    <img src="https://trendshift.io/api/badge/trendshift/repositories/12327/weekly" alt="Guovin/iptv-api | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
  </a>
  <a href="https://www.star-history.com/guovin/iptv-api">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=Guovin/iptv-api&type=rank&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=Guovin/iptv-api&type=rank" />
      <img src="https://api.star-history.com/badge?repo=Guovin/iptv-api&type=rank" alt="Star History Rank" style="height: 55px;" height="55" />
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://github.com/Guovin/iptv-api/releases/latest" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/github/v/release/guovin/iptv-api?label=Version" />
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.14-47c219?label=Python" />
  </a>
  <a href="https://github.com/Guovin/iptv-api/releases/latest" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/github/downloads/guovin/iptv-api/total?label=GUI%20Downloads" />
  </a>
  <a href="https://hub.docker.com/repository/docker/guovern/iptv-api">
    <img src="https://img.shields.io/docker/pulls/guovern/iptv-api?label=Docker%20Pulls" />
  </a>
  <a href="https://github.com/Guovin/iptv-api/stargazers">
    <img src="https://img.shields.io/github/stars/guovin/iptv-api?label=Stars" />
  </a>
  <a href="https://github.com/Guovin/iptv-api/fork" target="_blank" rel="noopener noreferrer">
    <img src="https://img.shields.io/github/forks/guovin/iptv-api?label=Forks" />
  </a>
</p>

<div align="center">
  <a href="./README_en.md">English</a> | <a href="./README_zh.md">中文</a>
</div>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/images/desktop-ui-dark.png" />
    <source media="(prefers-color-scheme: light)" srcset="./docs/images/desktop-ui.png" />
    <img src="./docs/images/desktop-ui.png" alt="Interface da versão desktop do IPTV‑API" width="100%"/>
  </picture>
  <details>
    <summary>🌓 Alternar modo de exibição</summary>
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./docs/images/desktop-ui.png" />
      <source media="(prefers-color-scheme: light)" srcset="./docs/images/desktop-ui-dark.png" />
      <img src="./docs/images/desktop-ui-dark.png" alt="Versão alternativa do desktop" width="100%"/>
    </picture>
  </details>
  <sub><strong>GUI para Windows / macOS</strong> – interface intuitiva e uso eficiente</sub>
</div>

<details open>
  <summary><strong>Sumário</strong></summary>
  - [Recursos Principais](#recursos-principais)
  - [Arquitetura e Fluxo de Execução](#arquitetura-e-fluxo-de-execução)
  - [Configurações](#configurações)
  - [Começando Rápido](#começando-rápido)
  - [Documentação](#documentação)
  - [Tutorial Detalhado](#tutorial-detalhado)
  - [Histórico de Atualizações](#historico-de-atualizações)
  - [Patrocinadores](#patrocinadores)
  - [Doação](#doação)
  - [Aviso Legal](#aviso-legal)
  - [Licença](#licença)
</details>

## Recursos Principais

| Recurso | Estado | Descrição |
|:--------|:-----:|:-----------|
| **Modelos Personalizados** | ✅ | Cria menus de canais sob medida |
| **Alias de Canais** | ✅ | Mais de 2.7 k canais e 7.2 k aliases, normaliza nomes automaticamente |
| **Agregação Multi‑fonte** | ✅ | Combina fontes locais e assinaturas (com UA configurável, desativa endereços inválidos) |
| **Transmissão (Streaming)** | ✅ | Melhor desempenho em redes fracas, suporte a reprodução no navegador e transcodificação automática |
| **Interface de Reprodução** | ✅ | Gera URLs de reprodução e metadados para players |
| **EPG** | ✅ | Exibe programação de canais |
| **Logotipos de Canais** | ✅ | Suporta logotipos locais ou de repositórios remotos |
| **Teste de Velocidade** | ✅ | Mede latência, taxa, resolução e taxa de quadros, filtra fontes inválidas em tempo real |
| **Captura de Tela** | ✅ | Captura screenshots automáticos para validar conteúdo, com visualização GUI e atualização em lote |
| **Filtro de Propagandas** | ✅ | Detecta e elimina streams sem sinal ou com anúncios em loop |
| **Filtros Avançados** | ✅ | Filtra por velocidade, resolução, listas blancas/pretas, localização e operadora |
| **Gerenciamento de Resultados** | ✅ | Armazena, registra logs, acompanha canais não correspondidos, fornece estatísticas, congelamento e cache de dados |
| **Tarefas Agendadas** | ✅ | Executa periodicamente via GUI, CLI ou Docker (não interfere em GitHub Actions) |
| **Pausa e Continuação** | ✅ | Permite pausar atualizações e retomar a partir do ponto interrompido |
| **Multiplataforma** | ✅ | Suporte a Windows, macOS, Linux (Docker amd64/arm64/armv7) |
| **Recursos Extras** | ✨ | Veja a seção de [Configurações](#configurações) para detalhes |

## Arquitetura e Fluxo de Execução

A aplicação possui um motor de atualização unificado usado por GUI desktop, linha de comando, Docker e GitHub Actions. Ele lê arquivos de configuração e templates de canais, coleta e normaliza interfaces, realiza testes de velocidade e, por fim, produz listas de reprodução e arquivos auxiliares. Cada modo de execução aciona o motor conforme necessidade e fornece os resultados por meio de arquivos locais ou serviço HTTP interno.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/images/architecture/overview-zh-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="./docs/images/architecture/overview-zh.svg" />
  <img src="./docs/images/architecture/overview-zh.svg" alt="Pontos de entrada, motor de atualização compartilhado e formas de acesso aos resultados" width="100%"/>
</picture>

Os resultados podem ser lidos diretamente pela GUI ou arquivos, ou expostos via serviço HTTP independente. GitHub Actions publica‑os em Pages e Releases. O fluxo de streaming utiliza FFmpeg e o módulo RTMP do Nginx.

## Configurações

> **Nota**
> As opções de configuração estão em `config/config.ini`. Elas podem ser alteradas diretamente no arquivo ou por variáveis de ambiente. Após a modificação, reinicie a aplicação.

> **Dica**
> A qualidade dos resultados depende da fonte e da rede. Ajuste os parâmetros conforme necessário.

<details>
  <summary>Clique para expandir a tabela completa de parâmetros</summary>

| Opção | Descrição | Valor padrão |
|:------|:----------|:------------|
| open_update | Habilita atualização automática | True |
| open_unmatch_category | Cria categoria para canais sem correspondência | False |
| open_empty_category | Cria categoria para canais sem resultados | False |
| open_update_time | Exibe horário da última atualização | True |
| open_url_info | Mostra informações da URL (resolução, protocolo etc.) | False |
| open_epg | Ativa suporte a EPG | True |
| open_subscribe_epg | Extrai EPG de cabeçalhos de assinatura | True |
| open_m3u_result | Gera arquivos M3U com ícones de canal | True |
| output_urls_limit | Número máximo de URLs por canal | 5 |
| update_time_position | Posicionamento da hora da atualização (top/bottom) | top |
| language | Idioma da interface (zh_CN/en) | zh_CN |
| update_mode | Modo de agendamento (interval/time) | interval |
| update_interval | Intervalo em horas entre atualizações (modo interval) | 12 |
| update_times | Horários específicos (modo time, formato HH:MM) | – |
| update_startup | Atualiza ao iniciar a aplicação | True |
| time_zone | Fuso horário usado nas programações | Asia/Shanghai |
| source_file | Caminho para o template de canais | config/demo.txt |
| final_file | Caminho para o arquivo de resultados | output/result.txt |
| open_realtime_write | Escrita em tempo real durante os testes | True |
| open_service | Habilita servidor HTTP de resultados | True |
| service_port | Porta HTTP do serviço | 8080 |
| public_url | URL pública completa (ex.: https://iptv.example.com) | – |
| app_port | Porta interna do Flask (não exposta ao usuário) | 5180 |
| public_scheme | Protocolo público (http/https) – usado quando public_url está vazio | http |
| public_domain | Domínio público (fallback) – usado quando public_url está vazio | 127.0.0.1 |
| cdn_url | URLs de CDN para acelerar arquivos estáticos | – |
| http_proxy | Proxy HTTP para obter fontes e EPG | – |
| open_local | Habilita fontes locais (arquivo local.txt) | True |
| open_subscribe | Habilita fontes de assinatura | True |
| open_auto_disable_source | Desativa automaticamente fontes que falham, marcando com `#` | False |
| open_history | Usa histórico de execuções anteriores para complementação | True |
| open_headers | Usa cabeçalhos presentes em M3U para testes (alguns players não suportam) | True |
| user_agent | User‑Agent global para requisições (sobrescreve se a fonte definir) | – |
| open_speed_test | Ativa teste de velocidade | True |
| speed_test_mode | Modo de teste (quick/full/manual) | quick |
| speed_test_target | Número de URLs rápidas por canal (0 = usar output_urls_limit) | 0 |
| quick_test_target | Alias legível para speed_test_target | 0 |
| open_stream_screenshot | Captura screenshots automáticos das streams | False |
| stream_screenshot_timeout | Timeout (s) para captura de screenshot | 5 |
| stream_screenshot_width | Largura máxima da imagem capturada | 640 |
| open_filter_resolution | Filtra streams abaixo da resolução mínima | True |
| open_filter_speed | Filtra streams abaixo da velocidade mínima | True |
| open_filter_ad | Filtra propagandas e streams vazios | True |
| open_full_speed_test | Testa todas as URLs de um canal (exceto whitelist) | False |
| open_supply | Adiciona interfaces marginalmente adequadas como suplemento | False |
| sort_by | Ordem de classificação das URLs (speed,delay,resolution) | speed |
| min_resolution | Resolução mínima aceita (ex.: 1280x720) | 1280x720 |
| max_resolution | Resolução máxima aceita | 3840x2160 |
| min_speed | Velocidade mínima (MiB/s) | 0.5 |
| resolution_speed_map | Mapeamento de resolução → velocidade mínima | 1280x720:0.2,1920x1080:0.5,3840x2160:1.0 |
| performance_mode | Modo de desempenho (auto/powersave/balance/fast) | auto |
| speed_test_limit | Número máximo de testes simultâneos (0 = automático) | 0 |
| speed_test_timeout | Timeout (s) por teste | 10 |
| speed_test_filter_host | Compartilha resultados entre streams com o mesmo Host | False |
| request_timeout | Timeout para requisições genéricas (s) | 10 |
| ipv6_support | Assume suporte a IPv6 sem teste | False |
| ipv_type | Tipo de IP a gerar (ipv4/ipv6/all) | all |
| ipv_type_prefer | Preferência de IP (ipv4/ipv6/auto) | auto |
| location | Filtra por localização da fonte (lista separada por vírgulas) | – |
| isp | Filtra por operadora da fonte (lista separada por vírgulas) | – |
| origin_type_prefer | Prioriza origem das URLs (local,subscribe,…) | – |
| local_num | Número de URLs locais desejado por canal | 10 |
| subscribe_num | Número de URLs de assinatura desejado por canal | 10 |
| logo_url | URL da base de logotipos de canais | – |
</details>

## Começando Rápido

1. **Instale as dependências** – `pip install -r requirements.txt` (Python 3.14+).
2. **Configure** – copie `config/config.example.ini` para `config/config.ini` e ajuste as opções necessárias.
3. **Execute** – `python main.py` (modo GUI) ou `python -m utils.cli --run` (modo linha de comando).
4. **Docker** – `docker build -t iptv-api . && docker run -p 8080:8080 iptv-api`.

## Documentação

- [Centro de Documentação](./docs/README.md)
- [Tutorial Passo‑a‑Passo](./docs/tutorial.md)
- [Histórico de Alterações](./CHANGELOG.md)

## Patrocinadores

[![Patrocinadores](https://opencollective.com/iptv-api/tiers/sponsor.svg?width=890)](https://opencollective.com/iptv-api)

## Doação

Apoie o desenvolvimento através de doações no **OpenCollective** ou via **PayPal**. Qualquer contribuição ajuda a melhorar a ferramenta.

## Aviso Legal

Esta ferramenta usa streams públicas. Verifique a legislação local antes de utilizá‑la. Os autores não se responsabilizam por uso indevido.

## Licença

Distribuído sob a licença **MIT**. Consulte o arquivo `LICENSE` para detalhes.
