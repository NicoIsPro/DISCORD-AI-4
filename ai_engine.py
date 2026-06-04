import os
import random
import re
import requests
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/DialoGPT-medium").strip()

# -------------------------
# ENGINE STATUS 
# -------------------------
def engine_status():
    return {
        "status": "ready",
        "engine_type": f"HuggingFace Cloud Anonymous ({MODEL_NAME})",
        "version": "2.3.0_PRO_NATURAL_FIX"
    }

# -------------------------
# CALL DETECTION
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
# UTILS 
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
# HUMANIZE ULTRA NATURAL
# -------------------------
def _trim(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:250]


def _humanize(text: str) -> str:
    text = _trim(text)
    
    replacements = [
        (r"\bvocê\b", "vc"),
        (r"\btambém\b", "tbm"),
        (r"\bagora\b", "agr"),
        (r"\bporque\b", "pq"),
        (r"\bnão\b", "n"),
        (r"\bdepois\b", "dps"),
        (r"\bcom certeza\b", "ctz"),
        (r"\bmesmo\b", "msm"),
        (r"\birmão\b", "mano"),
        (r"\bamigo\b", "bro"),
        (r"\bverdade\b", "papo reto"),
        (r"\btudo bem\b", "suave"),
        (r"\bcomo vai\b", "eae"),
    ]

    for p, r in replacements:
        if random.random() < 0.7:
            text = re.sub(p, r, text, flags=re.IGNORECASE)

    text = text.lower()
    if text.endswith("."):
        text = text[:-1]

    if random.random() < 0.35:
        text += random.choice([" kkk", " mano", " bro", " slá", " dps a gnt ve", " tmj"])

    return text.strip()


# -------------------------
# FALLBACK EM PORTUGUÊS NEUTRO
# Agora lê só o texto limpo, sem bugar com metadados
# -------------------------
def _light_reply(clean_text: str) -> str:
    text = clean_text.lower()
    mood = _detect_mood(text)

    if mood == "greeting":
        return random.choice(["eae bro de boa?", "opa, salve", "fala ai, tudo suave?"])
    
    if mood == "playful":
        return random.choice(["kkkkkk rachei disso", "os cara n cansam né kkk", "tipo isso msm kkk"])
        
    if mood == "happy":
        return random.choice(["é nois mano tmj", "boa boa!", "daora demais"])
        
    if mood == "sad":
        return random.choice(["pô bro, desanima não, o que rolou?", "tenso isso ai dps melhora mano", "forças ai bro"])

    if mood == "angry":
        return random.choice(["calma mano kkk pra que isso", "tá bravo de graça bro kkk relaxa", "relaxa ai pô"])

    if "?" in text:
        return random.choice(["sei não hein mano, mas posso ver dps", "pior q não sei kkk mas pesquisa ai", "boiei agr, dps dou uma olhada"])

    return random.choice(["papo reto", "entendi foi tudo kkk", "pode crer mano", "complicado né msm", "boto fé"])


# -------------------------
# CALL EXCUSE 
# -------------------------
def _call_excuse(name: str | None) -> str:
    name = (name or "mano").split()[0]

    return random.choice([
        f"boa {name}, n consigo entrar em call agr, tô sem fone aqui kkk",
        f"pô {name}, tá barulho aqui agr, melhor falar por texto msm",
        "consigo entrar em call agr não bro, dps a gnt se fala suave?",
    ])


# -------------------------
# MAIN GENERATION
# -------------------------
def generate_reply(prompt: str, display_name: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "manda algo ai pô"

    # Isola puramente a mensagem do usuário
    user_text = _extract_user_message(prompt)
    name = display_name or _extract_display_name(prompt)

    if _looks_like_call_request(user_text):
        return _call_excuse(name)

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
        # AUMENTAMOS O TIMEOUT PARA 15s PRA DAR TEMPO DA IA PENSAR
        response = requests.post(API_URL, json=payload, timeout=15)
        
        if response.status_code == 200:
            res_json = response.json()
            if isinstance(res_json, list) and "generated_text" in res_json[0]:
                out = res_json[0]["generated_text"]
                if out.startswith(user_text):
                    out = out[len(user_text):]
                
                if not out.strip():
                    return _light_reply(user_text)
                    
                return _humanize(out.strip())
                
        elif response.status_code == 503:
            # Se der 503, significa que o servidor da Hugging Face tá carregando o modelo
            return _light_reply(user_text)
            
    except Exception:
        # Se a internet falhar ou esgotar os 15s de espera
        pass

    # Agora o fallback recebe SÓ o user_text, pra não achar interrogação fantasma
    return _light_reply(user_text)
