import os
import random
import re
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/DialoGPT-medium").strip()

# -------------------------
# ENGINE STATUS (Correção do ImportError)
# -------------------------
def engine_status():
    return {
        "status": "ready",
        "engine_type": f"HuggingFace Cloud Anonymous ({MODEL_NAME})",
        "version": "2.0.0_PRO_NATURAL"
    }

# -------------------------
# CALL DETECTION (Seu sistema de Score Robusto)
# -------------------------
def _looks_like_call_request(prompt: str) -> bool:
    t = prompt.lower().strip()

    strong_intents = (
        "me liga agora",
        "pode me ligar",
        "liga pra mim agora",
        "entra na call agora",
        "chamada de voz agora",
        "vem call agora",
        "entra call",
    )

    if any(x in t for x in strong_intents):
        return True

    weak_keywords = ("call", "ligar", "chamada", "voz", "liga")

    score = 0
    for w in weak_keywords:
        if w in t:
            score += 1

    return score >= 2


# -------------------------
# UTILS (Limpeza dos prompts do Discord)
# -------------------------
def _extract_user_message(prompt: str) -> str:
    match = re.search(r"Mensagem:\s*(.+)", prompt, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
        for sep in ("\nResposta:", "\nMemória compacta:", "\nApelido visível:"):
            if sep in text:
                text = text.split(sep, 1)[0].strip()
        return text
    return prompt


def _extract_display_name(prompt: str) -> str | None:
    match = re.search(r"Apelido visível:\s*(.+)", prompt)
    if match:
        return match.group(1).strip()
    match = re.search(r"Usuário:\s*(.+)", prompt)
    if match:
        return match.group(1).strip()
    return None


# -------------------------
# MOOD DETECTION
# -------------------------
def _detect_mood(text: str) -> str:
    t = (text or "").lower()

    if any(x in t for x in ("kkk", "haha", "aura", "zoeira", "meme")):
        return "playful"
    if any(x in t for x in ("obrigad", "valeu", "boa", "top", "obg", "tmj")):
        return "happy"
    if any(x in t for x in ("triste", "cansad", "mal", "bad", "depre")):
        return "sad"
    if any(x in t for x in ("raiva", "idiota", "lixo", "pqp", "porra", "vtnf")):
        return "angry"
    if "?" in t:
        return "confused"
    if any(x in t for x in ("oi", "eae", "salve", "salveee")):
        return "greeting"

    return "neutral"


# -------------------------
# MODO PRO: HUMANIZE ULTRA NATURAL
# -------------------------
def _trim(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:250] # Resposta de Discord tem que ser curta, ninguém lê textão


def _humanize(text: str) -> str:
    text = _trim(text)
    
    # Dicionário de tradução "Robô -> Humano do Discord"
    replacements = [
        (r"\bvocê\b", "vc"),
        (r"\btambém\b", "tbm"),
        (r"\bagora\b", "agr"),
        (r"\bporque\b", "pq"),
        (r"\bnão\b", "n"),
        (r"\bmais\b", "mó"), # dependendo do contexto da frase fixa o tom informal
        (r"\bdepois\b", "dps"),
        (r"\bcom certeza\b", "ctz"),
        (r"\bmesmo\b", "msm"),
        (r"\birmão\b", "mano"),
        (r"\bamigo\b", "parça"),
        (r"\bverdade\b", "papo reto"),
        (r"\btudo bem\b", "suave"),
        (r"\bcomo vai\b", "eae"),
    ]

    # Aplica as abreviações com 70% de chance para parecer real (humanos às vezes digitam certo)
    for p, r in replacements:
        if random.random() < 0.7:
            text = re.sub(p, r, text, flags=re.IGNORECASE)

    # Força tudo para minúsculo e tira pontos finais (ponto final em chat parece grosseria kkk)
    text = text.lower()
    if text.endswith("."):
        text = text[:-1]

    # Adiciona uma risada ou gíria aleatória no final de vez em quando
    if random.random() < 0.35:
        text += random.choice([" kkk", " mano", " slá", " dps vemos", " tmj"])

    return text.strip()


# -------------------------
# FALLBACK EM PORTUGUÊS (Gírias nativas do Discord)
# -------------------------
def _light_reply(prompt: str) -> str:
    text = _extract_user_message(prompt).lower()
    mood = _detect_mood(text)

    if mood == "greeting":
        return random.choice(["eae mano suave?", "opa, salve parça", "fala tu, de boa?"])
    
    if mood == "playful":
        return random.choice(["kkkkkk rachei agora bicho", "os cara n perdoa uma kkk", "mó onda isso aí"])
        
    if mood == "happy":
        return random.choice(["é nois mano tmj", "boa boa!", "top demais entao"])
        
    if mood == "sad":
        return random.choice(["pô mano fica assim n, o que rolou?", "mó bad isso aí parça dps melhora", "forças aí mano"])

    if mood == "angry":
        return random.choice(["calma mano pra q essa agressividade toda kkk", "tá bravo liga pro batman kkk", "relaxa aí po"])

    if "?" in text:
        return random.choice(["sei não hein mano, mas posso tentar ver dps", "pior q não sei kkk mas pesquisa aí", "boiei agr, dps te respondo ctz"])

    return random.choice(["papo reto mano", "entendi foi tudo kkk", "visão mano", "mó fita", "pode crer"])


# -------------------------
# CALL EXCUSE (Desculpas de quem tá no PC)
# -------------------------
def _call_excuse(name: str | None) -> str:
    name = (name or "mano").split()[0]

    return random.choice([
        f"boa {name}, n posso entrar em call agr mano, tô sem microfone kkk",
        f"pô {name}, tá mó barulheira aqui em casa agr, fala por texto msm",
        "consigo call agora não mano, dps a gente vê isso suave?",
    ])


# -------------------------
# MAIN GENERATION
# -------------------------
def generate_reply(prompt: str, display_name: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "manda algo aí pô"

    user_text = _extract_user_message(prompt)
    name = display_name or _extract_display_name(prompt)

    # 1. 🔥 Trava anti-falso-positivo da Call
    if _looks_like_call_request(user_text):
        return _call_excuse(name)

    # 2. Requisição Anônima dos Transformers (Roda na nuvem da Hugging Face)
    API_URL = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
    payload = {
        "inputs": user_text,
        "parameters": {
            "max_new_tokens": 40,
            "temperature": 0.85,
            "do_sample": True
        }
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            res_json = response.json()
            if isinstance(res_json, list) and "generated_text" in res_json[0]:
                out = res_json[0]["generated_text"]
                if out.startswith(user_text):
                    out = out[len(user_text):]
                
                # Se o DialoGPT (inglês) mandar algo em branco, joga pro nosso fallback brabo
                if not out.strip():
                    return _light_reply(prompt)
                    
                return _humanize(out.strip())
                
        elif response.status_code == 503:
            # Se o modelo estiver carregando na nuvem deles, usa nosso fallback de gírias local
            return _light_reply(prompt)
            
    except Exception:
        pass

    # 3. Se a internet falhar ou der timeout, entra o fallback gíria puro
    return _light_reply(prompt)
