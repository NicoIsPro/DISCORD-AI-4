import os
import random
import re

USE_TRANSFORMERS = os.getenv("USE_TRANSFORMERS", "true").lower() == "true"
MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/DialoGPT-medium").strip() or "microsoft/DialoGPT-medium"
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "80"))

_generator = None
_generator_failed = False

CALL_TRIGGERS = (
    "me liga",
    "pode ligar",
    "chama",
    "pode chamar",
    "atende",
    "atender",
    "chamada",
    "call",
    "voz agora",
    "entra na call",
    "vem pra call",
)

SLANG_GLOSSARY = (
    "vc=você; agr=agora; tbm=também; pq=porque; n=não; "
    "tlgd=tá ligado; pprt=papo reto; slk=expressão de surpresa/impacto; "
    "mds=meu deus; kkk=risada; aura=algo engraçado, absurdo ou com energia boa"
)

DISCORD_CONTEXT = (
    "Discord é um app de comunidade com servidores, canais, DMs, mensagens curtas, "
    "áudio/call e conversa rápida. Fale como alguém acostumado com esse ambiente."
)


def engine_status() -> str:
    if not USE_TRANSFORMERS:
        return "transformers=off fallback=on"
    if _generator is not None:
        return f"transformers=on model={MODEL_NAME} loaded=on"
    if _generator_failed:
        return f"transformers=on model={MODEL_NAME} loaded=failed fallback=on"
    return f"transformers=on model={MODEL_NAME} loaded=lazy"


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


def _looks_like_call_request(prompt: str) -> bool:
    t = prompt.lower()
    return any(trigger in t for trigger in CALL_TRIGGERS)


def _detect_mood(text: str) -> str:
    t = (text or "").lower()

    if any(x in t for x in ("kkk", "kkkk", "haha", "rsrs", "engraç", "aura", "zoeira", "meme")):
        return "playful"
    if any(x in t for x in ("obrigad", "valeu", "boa", "show", "massa", "top", "perfeito")):
        return "happy"
    if any(x in t for x in ("triste", "chatead", "depr", "sozinho", "cansad", "mal", "desanim")):
        return "sad"
    if any(x in t for x in ("raiva", "irrit", "odiei", "odeio", "burro", "idiota", "lixo", "merda", "caraca", "pqp")):
        return "angry"
    if any(x in t for x in ("?", "como", "pq", "por que", "não entendi", "n entendi", "o que", "oq")):
        return "confused"
    if any(x in t for x in ("absur", "doid", "maluco", "pirado", "surreal", "artista", "esquisit", "perturb")):
        return "chaotic"
    if any(x in t for x in ("oi", "eae", "salve", "fala", "boa tarde", "boa noite", "bom dia")):
        return "greeting"
    return "neutral"


def _light_reply(prompt: str) -> str:
    user_text = _extract_user_message(prompt)
    mood = _detect_mood(user_text)
    text = user_text.lower()

    if _looks_like_call_request(prompt):
        return random.choice([
            "n posso atender agr, to no corre 😅",
            "agora n dá, amg. me chama dps 🙏",
            "to ocupado agr, volto já já 😌",
        ])

    if mood == "greeting":
        return random.choice(["Eae 😄", "Opa, fala aí", "Salveee", "Boa, cheguei"])
    if mood == "happy":
        return random.choice(["Boa demais 😎", "Aí simmm", "kkkk boa", "top demais"])
    if mood == "sad":
        return random.choice(["poxa...", "Puts, que vacilo", "tô contigo nessa", "é, aí complica"])
    if mood == "angry":
        return random.choice(["calma aí tbm", "oxe, respira um pouco", "lá vem a treta kkk", "isso aí foi puxado"])
    if mood == "chaotic":
        return random.choice([
            "tu tá meio artista hj hein kk",
            "isso aí tá num nível meio bizarro kkk",
            "mds do céu, aura total",
            "mano... que viagem foi essa",
        ])
    if mood == "confused":
        return random.choice([
            "tlgd, mas me explica melhor",
            "não peguei 100% ainda, manda de novo?",
            "entendi mais ou menos, falta um pedaço",
            "pode detalhar melhor agr?",
        ])

    if any(x in text for x in ("quem é você", "quem é vc", "quem cê é")):
        return "Sou um bot do Discord tentando soar humano 😎"
    if any(x in text for x in ("qual seu nome", "teu nome")):
        return "Pode me chamar de bot mesmo."
    if "obrigad" in text:
        return random.choice(["Tamo junto 😄", "de nadaaa", "claro, amg"])
    if any(x in text for x in ("kk", "haha", "engraçado", "absurdo", "aura")):
        return random.choice(["kkkk aura", "aí sim kkk", "muito aura isso aí"])

    return random.choice([
        "Entendi. Manda mais um pouco que eu acompanho.",
        "Tlgd. Continua aí.",
        "Okok, saquei o clima.",
        "Fechou, segue.",
    ])


def _load_generator():
    global _generator, _generator_failed

    if _generator is not None:
        return _generator

    if not USE_TRANSFORMERS:
        return None

    if _generator_failed:
        return None

    try:
        from transformers import pipeline

        _generator = pipeline(
            "text-generation",
            model=MODEL_NAME,
            device=-1,
        )
        return _generator
    except Exception:
        _generator_failed = True
        return None


def _trim_reply(reply: str) -> str:
    reply = reply.strip()
    reply = re.sub(r"\s+", " ", reply)
    if len(reply) > 500:
        reply = reply[:500].rstrip() + "..."
    return reply


def _opening_from_mood(mood: str, display_name: str | None) -> str | None:
    first_name = (display_name or "").split()[0].strip() or None

    choices = {
        "playful": ["kkkk", "mds", "aí sim", "slk"],
        "happy": ["boa", "aí sim", "top", "nice"],
        "sad": ["poxa", "puts", "caramba"],
        "angry": ["oxe", "mano", "calma"],
        "chaotic": ["mano", "slk", "mds", "aura"],
        "greeting": ["eae", "opa", "salve"],
        "neutral": [None],
        "confused": ["tlgd", "hm", "opa"],
    }.get(mood, [None])

    pick = random.choice(choices)
    if not pick:
        return None

    if first_name and random.random() < 0.35:
        return f"{pick.capitalize()} {first_name}"
    return pick.capitalize()


def _humanize(reply: str, display_name: str | None = None, mood: str = "neutral") -> str:
    reply = _trim_reply(reply)

    replacements = [
        (r"\bvocê\b", "vc"),
        (r"\bvocês\b", "vcs"),
        (r"\btambém\b", "tbm"),
        (r"\btambem\b", "tbm"),
        (r"\bagora\b", "agr"),
        (r"\bporque\b", "pq"),
        (r"\bpor que\b", "pq"),
        (r"\bnão\b", "n"),
        (r"\bNão\b", "N"),
        (r"\bestou\b", "tô"),
        (r"\bEstou\b", "Tô"),
    ]

    for pattern, replacement in replacements:
        if random.random() < 0.45:
            reply = re.sub(pattern, replacement, reply, flags=re.IGNORECASE)

    reply = re.sub(r"\s+", " ", reply).strip()

    opening = _opening_from_mood(mood, display_name)
    if opening and random.random() < 0.6 and reply:
        if not reply.lower().startswith(opening.lower()):
            reply = f"{opening}, {reply[0].lower() + reply[1:]}" if len(reply) > 1 else f"{opening}, {reply}"

    if random.random() < 0.18 and any(x in reply.lower() for x in ("kk", "haha", "rs", "engraç", "absurd", "bizarro")):
        if "aura" not in reply.lower():
            reply = f"{reply} aura"

    if mood == "angry" and random.random() < 0.25:
        suffixes = ["mano", "tlgd?", "sem caô", "sério isso?"]
        if not any(s in reply.lower() for s in suffixes):
            reply = f"{reply} {random.choice(suffixes)}"

    return _trim_reply(reply)


def _call_excuse(display_name: str | None) -> str:
    first = (display_name or "amg").split()[0].strip() or "amg"
    options = [
        f"Boa {first}, n posso atender agr, to no corre 😅",
        f"{first}, agr n dá. me chama dps que eu respondo melhor 🙏",
        f"To ocupado agr, {first}. volto já já 😌",
        f"não consigo atender agr, amg. depois eu apareço",
        f"foi mal {first}, to resolvendo umas paradas aqui",
    ]
    return random.choice(options)


def generate_reply(prompt: str, display_name: str | None = None) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Manda algo aí 😄"

    extracted_user = _extract_user_message(prompt)
    mood = _detect_mood(extracted_user)
    name = display_name or _extract_display_name(prompt)

    if _looks_like_call_request(prompt):
        return _call_excuse(name)

    gen = _load_generator()
    if gen is None:
        return _humanize(_light_reply(prompt), name, mood)

    full_prompt = (
        "Você é uma pessoa real trocando ideia no Discord. "
        "Discord é um app de comunidade com servidores, canais, DMs, call/voz e conversa rápida. "
        "Responda como humano de verdade, com tom natural, casual e variado.\n"
        f"Glossário de gírias e atalhos do papo: {SLANG_GLOSSARY}.\n"
        "Interpretação do clima:\n"
        "- Se a pessoa estiver animada, responda animado também.\n"
        "- Se a pessoa estiver triste, responda com mais cuidado.\n"
        "- Se a pessoa vier irritada, pode devolver com leve irritação/impaciência, mas sem agressão pesada.\n"
        "- Se a pessoa estiver fazendo algo muito absurdo, estranho ou doentio, pode soltar uma brincadeira tipo 'tu tá meio artista hj hein kk'.\n"
        "- Se pedirem ligação, call ou atendimento imediato, diga que não dá agora com uma desculpa curta e humana.\n"
        "- Use gírias de forma natural e não toda hora.\n"
        "- Frases curtas quando a conversa pedir. Textos maiores só quando fizer sentido.\n"
        "- Pode usar 'aura' de vez em quando quando a situação for engraçada ou absurda.\n"
        "- Tenta parecer espontâneo, com pequenas variações de humor.\n"
        f"Clima atual detectado: {mood}\n"
        f"{DISCORD_CONTEXT}\n"
        f"{prompt}\n"
        "Resposta:"
    )

    try:
        out = gen(
            full_prompt,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=0.95,
            top_p=0.93,
            repetition_penalty=1.08,
            num_return_sequences=1,
            pad_token_id=gen.tokenizer.eos_token_id,
        )[0]["generated_text"]
    except Exception:
        return _humanize(_light_reply(prompt), name, mood)

    if out.startswith(full_prompt):
        reply = out[len(full_prompt):]
    else:
        reply = out

    reply = reply.strip()
    for sep in ["\n", "Resposta:", "Usuário:", "Bot:"]:
        if sep in reply:
            reply = reply.split(sep, 1)[0].strip()

    return _humanize(reply, name, mood) or "Putz, travei aqui 😅"
