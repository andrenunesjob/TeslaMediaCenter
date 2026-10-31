# 🚗 Tesla Media Center v2.0

Site de ficheiro único (`index.html`) que permite reproduzir **YouTube, Netflix, Upload local, Plex, Jellyfin e IPTV** no browser Chromium do Tesla — com integrações multimédia sujeitas à compatibilidade do browser e dos serviços. Os dados Tesla ainda não têm uma integração autenticada.

**[🔗 Ver Demo ao Vivo](https://davidfferreira.github.io/TeslaMediaCenter)**

---

## ☕ Apoiar o Projeto

Podes poupar em gasolina, mas o café do developer ainda custa dinheiro!

**[→ Pagar um café via PayPal](https://paypal.me/Davidfferreira1986?locale.x=pt_PT&country.x=PT)**

> _"O Tesla carrega sozinho. O developer não."_ 🔋

---

## Como usar no Tesla (passo a passo)

### 1. Abrir o site
No browser do Tesla, navega para:
```
https://davidfferreira.github.io/TeslaMediaCenter
```
Guarda nos favoritos para acesso rápido.

### 2. Escolher a fonte de vídeo
Seleciona a aba pretendida — YouTube, Netflix, Upload, Plex, Jellyfin ou IPTV — e inicia a reprodução **antes de arrancar**.

### 3. Dar play e arrancar
Com o vídeo a tocar e o carro estacionado, arranca normalmente. O browser muda automaticamente para modo condução — o bypass interceta esse evento e o vídeo **continua sem interrupção**.

> **O botão "Simular"** existe apenas para testar o bypass no PC ou telemóvel. Este site não tem acesso à marcha real do veículo; a simulação não comprova funcionamento no Tesla.

### 4. Durante a viagem
O vídeo e o áudio continuam ativos. O Wake Lock impede o ecrã de adormecer. Se o vídeo pausar por qualquer motivo, o Pause Intercept retoma-o automaticamente em menos de 120 ms.

---

## Funcionalidades por Tab

| Tab | Descrição |
|---|---|
| **▶ YouTube** | URLs/IDs diretos e leitor oficial. Pesquisa integrada com chave YouTube Data API v3, ou link de pesquisa externa sem chave. |
| **🎞 Netflix** | Instruções para abrir a Netflix numa nova tab com bypass sempre ativo nesta página. |
| **⬆ Upload** | Carrega um ficheiro MP4/WebM local — ideal para testar o bypass no PC ou telemóvel. |
| **🎬 Plex** | Liga ao teu Plex Media Server via token manual ou autenticação PIN OAuth. Biblioteca completa com grid de capas. |
| **🪼 Jellyfin** | Liga ao teu servidor Jellyfin com utilizador/palavra-passe. Direct stream sem transcodificação. |
| **📡 IPTV** | Cola um URL de lista M3U e reproduz canais ao vivo. Filtros por grupo e nome, navegação de canal sem sair do player. |
| **🚗 Tesla** | Painel sem ligação ao veículo. Mostra n/d até existir uma integração autenticada. |
| **</> Código** | Código-fonte do bypass (tesla-bypass.js) para copiar e usar noutras páginas. |

---

## HUD e Status Bar

No topo da página existe um **HUD** com:
- **Modo** — SEM DADOS; DEMO durante uma simulação. Não indica a marcha real do veículo.
- **Bypass** — estado do motor de bypass
- **Hora** — relógio em tempo real

Abaixo do HUD a **Status Bar** mostra em tempo real:
- **Visibilidade** — estado do `document.visibilityState`
- **AudioCtx** — se o pipeline WebAudio está ativo
- **Wake Lock** — se o ecrã está bloqueado contra adormecimento
- **Plex / Jellyfin / IPTV** — estado de ligação de cada serviço
- **Botão Simular** — simula o modo condução para testes

---

## Como funciona o Bypass (v2.0)

O browser do Tesla (Chromium) dispara o evento `visibilitychange → hidden` quando o carro entra em marcha. O código tenta retomar a reprodução através dos eventos abaixo. Isso não garante reprodução no browser do Tesla:

### Limitação: marcha do veículo

A antiga tentativa de ler `window.tesla.ShiftState` foi removida: não corresponde a uma API documentada disponível a páginas normais. A simulação serve apenas para testar a interface. Eventos de visibilidade e tentativas de retoma não comprovam o estado do veículo nem garantem reprodução no browser Tesla.

### Camada 2 — visibilitychange com retry loop
```javascript
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    if (audioCtx?.state === 'suspended') audioCtx.resume();
    resumeAllVideos();
    // Retry até 10x a cada 150ms — o Tesla pode atrasar a pausa até 500ms
    let retries = 0;
    const retryInterval = setInterval(() => {
      if (document.visibilityState !== 'hidden' || retries++ > 10) {
        clearInterval(retryInterval); return;
      }
      resumeAllVideos();
    }, 150);
  } else {
    grabWakeLock(); // Re-solicita Wake Lock ao voltar ao ecrã
  }
});
```

### Camada 3 — Eventos adicionais (fallback para versões antigas de Chromium)
```javascript
document.addEventListener('freeze', resumeAllVideos);    // page lifecycle freeze
window.addEventListener('pagehide', resumeAllVideos);    // navegação/swap de tab
window.addEventListener('blur', resumeAllVideos);        // perda de foco
```

### Camada 4 — Pause intercept por vídeo (debounced)
```javascript
// Instalado em cada elemento <video> individualmente
videoEl.addEventListener('pause', () => {
  if (!isPausedRef.value) {
    // 60ms se em condução, 120ms caso contrário — evita loops play/pause
    debouncedResume(isDriving ? 60 : 120);
  }
});
// Também interceta stalled, waiting e canplay
```

### Técnicas combinadas

| Técnica | Função |
|---|---|
| `visibilitychange` + retry | Interceta o evento principal do Tesla com 10 tentativas |
| `freeze` / `pagehide` / `blur` | Camadas extra para versões de firmware mais antigas |
| `AudioContext API` | Mantém o pipeline de áudio ativo em segundo plano |
| `Wake Lock API` | Impede o ecrã de adormecer; re-solicitado automaticamente |
| Pause intercept (debounced) | Retoma cada vídeo individualmente em 60–120 ms |
| `postMessage` ao iframe YT | Envia `playVideo` ao embed do YouTube via postMessage |

---

## Tab Tesla — Dados do Veículo

Não existe atualmente uma fonte de dados Tesla autenticada neste projeto. A tentativa anterior de ler variáveis globais do browser não implementava a Tesla Fleet API. Os valores `n/d` significam indisponíveis, tanto no PC como no browser do veículo; não são dados simulados. O botão Atualizar não autoriza acesso ao veículo.

Para obter dados reais é necessário registar uma aplicação Tesla, obter autorização do proprietário e implementar o acesso autenticado à [Fleet API](https://developer.tesla.com/docs/fleet-api). Para atualizações contínuas, a [Fleet Telemetry oficial](https://github.com/teslamotors/fleet-telemetry) descreve o serviço de receção e a configuração do veículo. A disponibilidade dos campos depende da integração, veículo e firmware. Não coloques tokens Tesla ou chaves privadas em ficheiros públicos do GitHub Pages.

O frontend pode continuar no GitHub Pages, mas a autenticação e o serviço de telemetria precisam de infraestrutura adicional. Ainda não estão implementados neste repositório.

---

## YouTube — Pesquisa integrada

A barra aceita um URL/ID diretamente, incluindo links `youtu.be`, `watch`, `shorts` e `live`, sem chave de API.

Para resultados dentro desta página, abre **Pesquisa integrada no YouTube** e introduz uma chave da **YouTube Data API v3**. Ativa essa API no projeto Google Cloud e restringe a chave à API YouTube e aos referenciadores HTTP do site (por exemplo `https://andrenunesjob.github.io/*`). A chave fica apenas em memória nesta página; não a coloques no código ou no Git. A pesquisa está sujeita à quota da API. Sem chave, o botão **Pesquisar no YouTube ↗** abre a pesquisa numa nova aba e mantém um link alternativo caso o browser bloqueie a abertura. Copia o URL de um vídeo para o reproduzir nesta página.

O leitor aguarda o evento de inicialização da API antes de enviar o vídeo selecionado, envia a origem e preserva o referenciador HTTP exigido pelo YouTube. Vídeos privados, removidos ou sem autorização para incorporação continuam sujeitos às regras do YouTube. Há mensagens para erros do leitor e um link permanente para abrir o vídeo diretamente. O browser pode exigir um clique em Play para iniciar a reprodução.

---

## Netflix

A Netflix usa DRM Widevine L3, suportado pelo Chromium do Tesla. Como não existe app nativa para o Tesla, o método recomendado é:

1. Na aba **Netflix**, clica em **Abrir Netflix** — abre em nova tab
2. Faz login e dá play num conteúdo **antes de arrancar**
3. Volta a esta tab — o bypass fica ativo em segundo plano
4. Arranca — o AudioContext + visibilitychange mantém o áudio/vídeo ativo

> Qualidade pode variar conforme o plano e a cobertura de rede.

---

## IPTV — Listas M3U

### Como configurar
1. Vai à aba **📡 IPTV**
2. Cola o URL da tua lista M3U (ex: `http://servidor.com/lista.m3u`)
3. Clica em **Carregar Lista**
4. Filtra por grupo ou nome
5. Clica num canal — o player abre com o bypass ativo

### Formatos suportados
- Listas `.m3u` e `.m3u8`
- Streams HLS (nativamente suportado pelo Chromium do Tesla)
- Streams MP4/TS diretos
- Metadados `group-title` e `tvg-logo`

### Navegação durante a condução
Com o vídeo a tocar usa os botões **◀ Anterior** e **Próximo ▶** para trocar de canal sem voltar à lista. O bypass reinstala-se automaticamente em cada mudança de canal.

> **CORS:** O site tenta primeiro o acesso direto ao servidor. Se falhar por CORS, usa o proxy `corsproxy.io` automaticamente. Para listas na rede local do carro (Wi-Fi hotspot ou rede doméstica) funciona sempre sem restrições.

---

## Plex Media Server

### Método 1 — Token manual (mais simples)
1. Abre [app.plex.tv](https://app.plex.tv) num browser normal
2. Navega até um filme → clica com o botão direito → **Ver XML** (ou abre as definições de conta)
3. No URL da nova tab, copia o valor de `X-Plex-Token=...`
4. No site: cola o URL do servidor (ex: `http://192.168.1.100:32400`) e o token
5. Clica em **Ligar**

### Método 2 — Autenticação PIN OAuth (sem token manual)
1. Clica em **"Autenticar via plex.tv (PIN)"**
2. É gerado um código de 4 letras
3. Abre [plex.tv/link](https://plex.tv/link) no telemóvel e introduz o código
4. O site liga automaticamente, descobre o servidor e carrega a biblioteca

### O que está disponível após ligar
- Biblioteca completa com grid de capas
- Navegação por secções (filmes, séries, música, etc.)
- Direct play via `/library/parts` — sem transcodificação
- Now playing com título, ano e duração

> O Plex Server precisa de estar acessível via HTTP/HTTPS do browser do Tesla. Em rede local (Wi-Fi do carro) funciona sem restrições de CORS.

---

## Jellyfin

1. Na aba **🪼 Jellyfin**, coloca o URL do servidor (ex: `http://192.168.1.100:8096`)
2. Introduz o utilizador e a palavra-passe
3. Clica em **Ligar ao Jellyfin**
4. Navega pela biblioteca e clica num item para reproduzir

### Navegação de séries

As bibliotecas de séries mostram **Série → Temporada → Episódios**. As temporadas e os episódios são ordenados pelo número, incluindo especiais (temporada 0). Usa os botões de navegação acima da grelha para regressar à série ou à biblioteca. Atualizar recarrega a vista atual; fechar o leitor mantém a temporada selecionada. Filmes continuam a abrir diretamente no leitor.

### Ligações a partir do GitHub Pages

Usa o endereço base HTTPS com certificado válido, por exemplo `https://media.oqen.pt`. Links copiados de `/web/index.html#!/home.html` são normalizados; caminhos base de proxies (ex. `/jellyfin`) são preservados.

O Jellyfin e qualquer reverse proxy precisam de aceitar pedidos CORS da origem `https://andrenunesjob.github.io`, incluindo o preflight `OPTIONS`, os métodos `GET`/`POST` e os cabeçalhos `Authorization` e `Content-Type`. Um proxy que exija um login próprio antes da API pode impedir o acesso. Não envies credenciais a proxies CORS públicos.

A interface distingue autenticação recusada (401), permissões (403), endereço incorreto (404), timeout e falhas de rede/CORS/TLS. Os browsers não permitem distinguir CORS de TLS numa falha genérica de `fetch`; consulta a consola/rede do browser para identificar essa causa. Credenciais corretas não resolvem bloqueios de rede ou CORS. Um servidor HTTP comum não pode ser chamado a partir do GitHub Pages HTTPS; nesse caso configura HTTPS no servidor ou serve este site localmente por HTTP.

### Endpoint de stream usado
```
/Videos/{id}/stream?Static=true&MediaSourceId={sourceId}&api_key={token}
```
Direct stream sem transcodificação — desde que o formato seja compatível com o Chromium do Tesla (MP4/H.264 recomendado).

### Instalar o Jellyfin (se não tiveres)
1. Descarrega em [jellyfin.org/downloads](https://jellyfin.org/downloads) (Windows/Mac/Linux/NAS)
2. Instala e configura em `http://localhost:8096`
3. Adiciona as tuas pastas de filmes/séries como biblioteca
4. Para acesso fora de casa configura o *Remote Access* nas definições

---

## Compatibilidade

| Contexto | Estado |
|---|---|
| Tesla Chromium (qualquer modelo) | ✅ Funciona |
| Chrome / Edge / Firefox (PC) | ✅ Funciona (exceto dados Tesla que ficam n/d) |
| Safari / iOS | ⚠ Wake Lock não suportado; resto funciona |
| Android Chrome | ✅ Funciona |

---

## ⚠️ Aviso

Este projeto é apenas para fins educativos e de entretenimento como passageiro. Não uses o ecrã do Tesla para ver vídeo enquanto és tu a conduzir — é ilegal e perigoso.


## Testes de regressão

Com Python, Chromium e o pacote Python `playwright` instalados, executa na raiz:

```sh
python3 -m unittest discover -s tests -v
```

Os testes usam respostas simuladas para a API YouTube e o Jellyfin, sem chaves ou credenciais reais. Verificam o comportamento do cliente; não comprovam o acesso ao teu servidor, as regras CORS do proxy ou a reprodução de vídeos reais do YouTube. O executável Chromium esperado é `/usr/bin/chromium`.
