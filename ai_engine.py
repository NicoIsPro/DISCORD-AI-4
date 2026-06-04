import os
import random
import re
import time
from dotenv import load_dotenv

# Importando o Transformers
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

load_dotenv()

MODEL_NAME = "microsoft/DialoGPT-small"

print("[SISTEMA] Carregando a IA localmente... (Isso pode levar alguns segundos)")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, padding_side='left')
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
print("[SISTEMA] IA Carregada com sucesso! 🚀")

def engine_status():
    return {
        "status": "ready",
        "engine_type": f"Local Transformers ({MODEL_NAME}) + Anti-Spam",
        "version": "6.1.0_ANTI_SPAM"
    }

# -------------------------
# SISTEMA ANTI-SPAM (TRAVA DE RAM)
# -------------------------
# Guarda quem está fazendo a pergunta no momento
ACTIVE_USERS = set()
# Guarda o tempo da última mensagem (Cooldown)
LAST_MSG_TIME = {}

# -------------------------
# CALL DETECTION
# -------------------------
def _looks_like_call_request(prompt: str) -> bool:
    t = prompt.lower().strip()
    strong_intents = ("me liga agora", "pode me ligar", "liga pra mim agora", "entra na call agora", "chamada de voz agora", "vem call agora", "entra call")
    if any(x in t for x in strong_intents): return True
    weak_keywords = ("call", "ligar", "chamada", "voz", "liga")
    return sum(1 for w in weak_keywords if w in t) >= 2

def _extract_user_message(prompt: str) -> str:
    match = re.search(r"Mensagem:\s*(.+)", prompt, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
        for sep in ("\nResposta:", "\nMemória compacta:", "\nApelido visível:"):
            if sep in text: text = text.split(sep, 1)[0].strip()
        return text
    return prompt

def _extract_display_name(prompt: str) -> str | None:
    match = re.search(r"Apelido visível:\s*(.+)", prompt)
    if match: return match.group(1).strip()
    return None

# -------------------------
# HUMANIZE ULTRA NATURAL
# -------------------------
def _humanize(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:250]
    
    replacements = [
        (r"\bvocê\b", "vc"), (r"\btambém\b", "tbm"), (r"\bagora\b", "agr"),
        (r"\bporque\b", "pq"), (r"\bnão\b", "n"), (r"\bdepois\b", "dps"),
        (r"\bcom certeza\b", "ctz"), (r"\bmesmo\b", "msm"), (r"\birmão\b", "mano"),
        (r"\bamigo\b", "bro"), (r"\bverdade\b", "papo reto"), (r"\btudo bem\b", "suave"),
        (r"\bcomo vai\b", "eae"),
    ]

    for p, r in replacements:
        if random.random() < 0.7:
            text = re.sub(p, r, text, flags=re.IGNORECASE)

    text = text.lower()
    if text.endswith("."): text = text[:-1]
    if random.random() < 0.35:
        text += random.choice([" kkk", " mano", " bro", " slá", " tmj"])
    return text.strip()

# -------------------------
# FALLBACK BÁSICO 
# -------------------------
def _light_reply(clean_text: str) -> str:
    t = clean_text.lower()
    if any(x in t for x in ("oi", "eae", "salve")): return random.choice(["eae bro de boa?", "opa, salve", "fala ai, tudo suave?"])
    if any(x in t for x in ("beleza", "suave", "papo reto")): return random.choice(["papo reto mano", "pode crer", "suave total"])
    if "?" in t: return random.choice(["sei não hein mano, mas posso ver dps", "pior q não sei kkk mas pesquisa ai", "boiei agr"])
    return random.choice(["papo reto", "entendi foi tudo kkk", "pode crer mano", "boto fé"])

def _call_excuse(name: str) -> str:
    name = name.split()[0]
    return random.choice([f"boa {name}, n consigo entrar em call agr, tô sem fone kkk", f"consigo entrar em call agr não bro, dps a gnt se fala suave?"])

# -------------------------
# MAIN GENERATION (TRANSFORMERS + ANTI-SPAM)
# -------------------------
def generate_reply(prompt: str, display_name: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt: return "manda algo ai pô"

    user_text = _extract_user_message(prompt)
    name = display_name or _extract_display_name(prompt) or "mano"
    user_key = name.lower()

    # 1. VERIFICA SE O CARA TÁ SPAMANDO (Flood / Cooldown de 3 segundos)
    current_time = time.time()
    if user_key in LAST_MSG_TIME and (current_time - LAST_MSG_TIME[user_key] < 3):
        return random.choice([
            f"calma ai {name}, tá spammando pq kkk",
            "pqp vai devagar mano kkk",
            f"perai {name} n precisa spamar, um seg",
            "calma calabreso kkkk"
        ])
    LAST_MSG_TIME[user_key] = current_time

    # 2. VERIFICA SE O BOT JÁ ESTÁ PENSANDO EM UMA RESPOSTA DELE
    if user_key in ACTIVE_USERS:
        return random.choice([
            f"perai mano, tô terminando de ler a outra que vc mandou kkk",
            "segura ai bro, tô pensando aqui ainda",
            "uma coisa de cada vez mano kkk"
        ])

    # Se passou pelo anti-spam, bloqueia o usuário até terminar
    ACTIVE_USERS.add(user_key)

    try:
        if _looks_like_call_request(user_text):
            return _call_excuse(name)

        # Prepara o texto para a IA local
        new_user_input_ids = tokenizer.encode(user_text + tokenizer.eos_token, return_tensors='pt')
        
        # Gera a resposta
        chat_history_ids = model.generate(
            new_user_input_ids, 
            max_length=60, 
            pad_token_id=tokenizer.eos_token_id,
            temperature=0.85,
            do_sample=True,
            top_k=50
        )
        
        output = tokenizer.decode(chat_history_ids[:, new_user_input_ids.shape[-1]:][0], skip_special_tokens=True)
        
        if output.strip():
            return _humanize(output.strip())
            
    except Exception as e:
        print(f"[ERRO TRANSFORMERS]: {e}")
    finally:
        # Quando terminar de pensar (ou se der erro), libera o usuário do bloqueio
        if user_key in ACTIVE_USERS:
            ACTIVE_USERS.remove(user_key)

    return _light_reply(user_text)
