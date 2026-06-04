import os
import random
import re

USE_TRANSFORMERS = os.getenv("USE_TRANSFORMERS", "true").lower() == "true"
MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/DialoGPT-medium").strip() or "microsoft/DialoGPT-medium"
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "80"))

_generator = None
_generator_failed = False


# -------------------------
# CALL DETECTION (FIXADO)
# -------------------------

def _looks_like_call_request(prompt: str) -> bool:
    t = prompt.lower().strip()

    # 🔥 só ativa se for MUITO explícito
    strong_intents = (
        "me liga agora",
        "pode me ligar",
        "liga pra mim agora",
        "entra na call agora",
        "chamada de voz agora",
        "vem call agora",
    )

    if any(x in t for x in strong_intents):
        return True

    # 🔥 detecção fraca com SCORE (evita falso positivo)
    weak_keywords = ("call", "ligar", "chamada", "voz")

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
# MOOD (mantido simples)
# -------------------------

def _detect_mood(text: str) -> str:
    t = (text or "").lower()

    if any(x in t for x in ("kkk", "haha", "aura", "zoeira")):
        return "playful"
    if any(x in t for x in ("obrigad", "valeu", "boa", "top")):
        return "happy"
    if any(x in t for x in ("triste", "cansad", "mal")):
        return "sad"
    if any(x in t for x in ("raiva", "idiota", "lixo", "pqp")):
        return "angry"
    if "?" in t:
        return "confused"
    if any(x in t for x in ("oi", "eae", "salve")):
        return "greeting"

    return "neutral"


# -------------------------
# FALLBACK LIMPO
# -------------------------

def _light_reply(prompt: str) -> str:
    text = _extract_user_message(prompt).lower()

    if _detect_mood(text) == "greeting":
        return random.choice(["Eae 😄", "Opa", "Salve"])

    if "?" in text:
        return "não tenho certeza, mas posso tentar ajudar"

    return "entendi"


# -------------------------
# TRANSFORMERS
# -------------------------

def _load_generator():
    global _generator, _generator_failed

    if _generator:
        return _generator

    if not USE_TRANSFORMERS or _generator_failed:
        return None

    try:
        from transformers import pipeline

        _generator = pipeline(
            "text-generation",
            model=MODEL_NAME,
            device=-1
        )
        return _generator

    except Exception:
        _generator_failed = True
        return None


# -------------------------
# HUMANIZE
# -------------------------

def _trim(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def _humanize(text: str) -> str:
    text = _trim(text)

    replacements = [
        (r"\bvocê\b", "vc"),
        (r"\btambém\b", "tbm"),
        (r"\bagora\b", "agr"),
        (r"\bporque\b", "pq"),
        (r"\bnão\b", "n"),
    ]

    for p, r in replacements:
        if random.random() < 0.4:
            text = re.sub(p, r, text, flags=re.IGNORECASE)

    return _trim(text)


# -------------------------
# CALL EXCUSE
# -------------------------

def _call_excuse(name: str | None) -> str:
    name = (name or "amg").split()[0]

    return random.choice([
        f"Boa {name}, n posso agr 😅",
        f"{name}, to ocupado agora, dps te chamo",
        "não dá agora, depois eu vejo isso",
    ])


# -------------------------
# MAIN
# -------------------------

def generate_reply(prompt: str, display_name: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "manda algo aí"

    user_text = _extract_user_message(prompt)
    mood = _detect_mood(user_text)
    name = display_name or _extract_display_name(prompt)

    # 🔥 CALL DETECTION (segura)
    if _looks_like_call_request(user_text):
        return _call_excuse(name)

    gen = _load_generator()

    # fallback
    if not gen:
        base = _light_reply(prompt)
        return _humanize(base)

    try:
        out = gen(
            prompt,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=0.9,
            top_p=0.9,
        )[0]["generated_text"]

        if out.startswith(prompt):
            out = out[len(prompt):]

        return _humanize(out)

    except Exception:
        return _humanize(_light_reply(prompt))
