# Discord AI Bot v3

Essa versão tenta soar mais humana, mais casual e menos robótica.

## O que faz
- responde em DM
- responde quando for mencionado
- `/ai`
- memória simples por usuário/servidor
- `/join`, `/leave`, `/say`
- evita ofensa e pedido perigoso
- lê o clima da mensagem e ajusta o tom
- pode responder mais animado, mais seco, ou levemente irritado quando a conversa pedir
- dica de nome quando o nick parece apelido de pessoa
- resposta curta e humana quando pedirem call/ligação

## Como a fala ficou
Ela tenta usar:
- `vc` = você
- `agr` = agora
- `tbm` = também
- `pq` = porque
- `n` = não
- `tlgd` = tá ligado
- `pprt` = papo reto
- `slk` = expressão de choque/surpresa

E às vezes solta um `aura` em contexto engraçado ou absurdo, sem exagerar.

Quando o nick parece apelido real, ela tenta chutar algo tipo:
- `Nico -> Nicolas / Nicholas`
- `Lolo -> Lorenzo / Lorena`

Se o nick for muito aleatório, ela não inventa.

## IMPORTANTE sobre o token
Você mandou um token no chat. Esse tipo de segredo deve ser tratado como exposto. O mais seguro é gerar outro token no portal do Discord Developer e usar o novo em `DISCORD_TOKEN`.

Nunca coloque token no código nem envie o arquivo `.env` para o GitHub.

## Como configurar localmente

1. Crie o bot em:
   https://discord.com/developers/applications
2. Ative:
   - `Message Content Intent`
3. Copie o token do bot.
4. Crie o arquivo `.env`:
```env
DISCORD_TOKEN=SEU_TOKEN_NOVO
PREFIX=!
ALLOW_DMS=true
AUTO_REPLY_ALL_CHANNELS=false
USE_TRANSFORMERS=true
MODEL_NAME=microsoft/DialoGPT-medium
MAX_NEW_TOKENS=80
```
5. Instale:
```bash
pip install -r requirements.txt
```
6. Rode:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Como colocar no GitHub

1. Crie um repositório novo.
2. Envie só os arquivos do projeto.
3. Não suba o `.env`.
4. Confira se o `.gitignore` está ignorando:
   - `.env`
   - `memory.json`

Fluxo normal:
```bash
git init
git add .
git commit -m "primeira versao"
git branch -M main
git remote add origin URL_DO_SEU_REPO
git push -u origin main
```

## Como colocar no Render pelo GitHub

1. Suba o projeto no GitHub.
2. No Render, crie um `Web Service` conectado ao repositório.
3. Use:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Em `Environment`, adicione as variáveis:
   - `DISCORD_TOKEN`
   - `PREFIX`
   - `ALLOW_DMS`
   - `AUTO_REPLY_ALL_CHANNELS`
   - `USE_TRANSFORMERS`
   - `MODEL_NAME`
   - `MAX_NEW_TOKENS`

## Sobre Transformers e Render
Se o deploy ficar pesado, o jeito mais estável é deixar:
```env
USE_TRANSFORMERS=false
```
Aí o bot continua rodando e usa o modo leve. Se o servidor aguentar o modelo, pode deixar `true`.

## Sobre voz
O comando `/say` usa `gTTS` e precisa de FFmpeg no ambiente.

## Sobre a memória
A memória fica em `memory.json`:
- salva um resumo curto
- não cresce sem limite
- guarda só pistas úteis

## Sobre call / ligação
O bot não atende chamada de voz como uma pessoa real, mas quando alguém pede call ou atendimento imediato ele responde com uma desculpa curta e natural. Quando a conversa fica muito absurda ou estranha, ele pode até mandar um tipo de 'tu tá meio artista hj hein kk'.
