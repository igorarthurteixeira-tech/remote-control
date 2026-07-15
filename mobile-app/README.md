# Remote Control — App Android (Expo)

App WebView que se conecta ao `server.py` (pasta raiz do repositório) rodando no PC.

## Como funciona a conexão

1. Ao abrir, tenta reconectar no último IP salvo (`AsyncStorage`), com timeout — não fica
   tentando pra sempre se o servidor não responder.
2. Se falhar (ou for a primeira vez), varre a sub-rede local (`discovery.js`) batendo em
   `http://<ip>:5000/ping` até achar o servidor.
3. Se a busca automática não encontrar nada, mostra a tela de configuração: escanear o
   QR Code (gerado em `/qr` pelo servidor) ou digitar o IP manualmente.
4. Uma vez conectado, mostra o `WebView` em `http://<ip>:5000`. Falhas de carregamento têm
   limite de tentativas (`MAX_WEBVIEW_FAILURES` em `App.js`) antes de voltar pra tela de
   configuração — evita o loop infinito de reconexão no IP antigo.

## Rodar localmente

```bash
npm install
npx expo install   # ajusta as versões das libs pro SDK do projeto
npx expo run:android
```

## Build / publicar

Este projeto ainda não está linkado a um projeto EAS. Pra reaproveitar o projeto já
existente na sua conta Expo (`remote-control`, id `dee7498c-641e-452d-9eca-aeb2ef921adf`):

```bash
npx eas init --id dee7498c-641e-452d-9eca-aeb2ef921adf
npx eas build --platform android --profile preview
```
