import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def should_warn_language(text: str) -> str | None:
    t = (text or "").lower()

    bad = ["idiota", "otário", "otaria", "burro", "burra", "lixo", "vai se f", "arromb", "imprestável"]
    if any(x in t for x in bad):
        return "Sem ofensa, bora trocar a ideia numa boa 😄"

    if "hackear" in t or "roubar" in t or "invadir" in t:
        return "Não posso ajudar com isso. Posso, sim, ajudar com algo seguro e legal."
    return None


def _normalize(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


KNOWN_NICK_HINTS = {
    "nico": ["Nicolas", "Nicholas"],
    "lolo": ["Lorenzo", "Lorena"],
    "bia": ["Beatriz", "Bianca"],
    "ju": ["Julia", "Júlia", "Juliano"],
    "duda": ["Eduarda", "Eduardo"],
    "gabi": ["Gabriela", "Gabriel"],
    "fer": ["Fernando", "Fernanda"],
    "kadu": ["Carlos Eduardo"],
    "cadu": ["Carlos Eduardo"],
    "gui": ["Guilherme", "Gui"],
    "isa": ["Isabela", "Isadora"],
    "ka": ["Kauã", "Karina", "Kamila"],
    "lari": ["Larissa"],
    "mah": ["Maria", "Mariana", "Maitê"],
    "rafa": ["Rafael", "Rafaela"],
    "vivi": ["Viviane", "Vivian"],
    "mari": ["Mariana", "Maria"],
}


def infer_real_name_hint(display_name: str) -> str | None:
    """
    Tenta inferir um nome "mais real" só quando o apelido parece um diminutivo
    ou apelido clássico. Se for um nick aleatório, devolve None.
    """
    raw = (display_name or "").strip()
    if not raw:
        return None

    first = raw.split()[0]
    clean = re.sub(r"[^a-zA-ZÀ-ÿ]", "", first).lower()

    if not clean:
        return None

    # nicks aleatórios/cheios de números costumam ser impossíveis de adivinhar
    if any(ch.isdigit() for ch in raw):
        return None

    if clean in KNOWN_NICK_HINTS:
        return " ou ".join(KNOWN_NICK_HINTS[clean])

    # alguns padrões curtos comuns
    if clean.startswith("nico"):
        return "Nicolas ou Nicholas"
    if clean.startswith("lolo"):
        return "Lorenzo ou Lorena"
    if clean.startswith("bia"):
        return "Beatriz ou Bianca"
    if clean.startswith("duda"):
        return "Eduarda ou Eduardo"
    if clean.startswith("gabi"):
        return "Gabriela ou Gabriel"
    if clean.startswith("ju"):
        return "Julia, Júlia ou Juliano"
    if clean.startswith("fer"):
        return "Fernando ou Fernanda"

    # só tenta adivinhar quando parece apelido de pessoa de verdade
    if len(clean) <= 5 and clean.isalpha():
        return None

    return None


@dataclass
class UserProfile:
    display_name: str = ""
    likes: str = ""
    dislikes: str = ""
    summary: str = ""
    last_topic: str = ""
    turns: int = 0


class MemoryStore:
    """
    Memória enxuta:
    - um perfil por usuário por servidor
    - sobrescreve resumo em vez de crescer sem parar
    """

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"guilds": {}}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                if "guilds" not in self.data:
                    self.data = {"guilds": {}}
            except Exception:
                self.data = {"guilds": {}}

    def save(self):
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _bucket(self, guild_id: str) -> dict[str, Any]:
        guilds = self.data.setdefault("guilds", {})
        return guilds.setdefault(guild_id, {"users": {}})

    def _user(self, guild_id: str, user_id: str) -> dict[str, Any]:
        guild = self._bucket(guild_id)
        users = guild.setdefault("users", {})
        return users.setdefault(user_id, asdict(UserProfile()))

    def get_profile(self, guild_id: str, user_id: str) -> str:
        user = self._user(guild_id, user_id)
        parts = []
        if user.get("display_name"):
            parts.append(f"nome={user['display_name']}")
        if user.get("likes"):
            parts.append(f"gosta={user['likes']}")
        if user.get("dislikes"):
            parts.append(f"não curte={user['dislikes']}")
        if user.get("last_topic"):
            parts.append(f"assunto={user['last_topic']}")
        if user.get("summary"):
            parts.append(f"resumo={user['summary']}")
        return " | ".join(parts)

    def build_prompt(
        self,
        user_name: str,
        user_text: str,
        profile: str,
        guild_id: str,
        name_hint: str | None = None,
    ) -> str:
        user_text = _normalize(user_text)
        memory_line = profile or "sem memória ainda"
        name_hint_line = name_hint or "não deu pra inferir com confiança"

        return (
            f"Memória compacta: {memory_line}\n"
            f"Apelido visível: {user_name}\n"
            f"Possível nome real do apelido: {name_hint_line}\n"
            f"Contexto do servidor: {guild_id}\n"
            f"Estilo: fala como uma pessoa real do Discord, com português natural e casual.\n"
            f"Use vc, agr, tbm, pq e n às vezes. Não force toda hora.\n"
            f"Quando fizer sentido, chame a pessoa de 'Boa {user_name.split()[0] if user_name else 'amg'}'.\n"
            f"Se a pessoa pedir call, ligação ou atendimento imediato, responde com uma desculpa curta e humana.\n"
            f"Mensagem: {user_text}"
        )

    def update_from_turn(self, guild_id: str, user_id: str, user_text: str, bot_text: str, display_name: str):
        user = self._user(guild_id, user_id)
        user["display_name"] = display_name
        user["turns"] = int(user.get("turns", 0)) + 1

        # salva só o que parece útil
        lower = user_text.lower()
        if any(x in lower for x in ["me chamo", "me chama", "sou o", "eu sou"]):
            user["summary"] = _normalize(user_text)
        elif any(x in lower for x in ["gosto de", "curto", "amo", "prefiro"]):
            user["likes"] = _normalize(user_text)
            user["summary"] = _normalize(user_text)
        elif any(x in lower for x in ["não gosto", "odeio", "não curto"]):
            user["dislikes"] = _normalize(user_text)
            user["summary"] = _normalize(user_text)
        elif len(user_text) <= 60 and any(ch.isalpha() for ch in user_text):
            user["last_topic"] = _normalize(user_text)

        # compacta com o que respondeu, sem crescer demais
        bot_text = _normalize(bot_text)
        if bot_text:
            user["summary"] = self._compress_summary(
                current=user.get("summary", ""),
                new_fact=user_text,
                reply=bot_text,
            )

    def _compress_summary(self, current: str, new_fact: str, reply: str) -> str:
        pieces = [p for p in [current, new_fact, reply] if p]
        joined = " || ".join(pieces)
        joined = joined[:260]
        return joined

    def clean_reply(self, reply: str) -> str:
        reply = _normalize(reply)
        if len(reply) > 500:
            reply = reply[:500].rstrip() + "..."
        return reply
