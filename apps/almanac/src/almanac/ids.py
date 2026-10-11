import secrets

# Crockford base32 строчными: без i, l, o, u — id удобно диктовать и переписывать.
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def new_id(prefix: str) -> str:
    return f"{prefix}_" + "".join(secrets.choice(ALPHABET) for _ in range(8))
