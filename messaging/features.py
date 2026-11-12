"""Reactions and slash commands."""

import random
import re


REACTIONS = ["👍", "❤️", "😂", "🔥", "😮", "😢"]

EIGHT_BALL = [
    "It is certain.", "Without a doubt.", "Yes, definitely.", "Most likely.",
    "Signs point to yes.", "Ask again later.", "Cannot predict now.",
    "Don't count on it.", "My sources say no.", "Very doubtful.",
]

DICE = re.compile(r"^(\d{1,2})?d(\d{1,4})$", re.IGNORECASE)


def apply_command(username, body):
    """Turn '/roll 2d6' style messages into their result.

    Anything that isn't a known, valid command is returned unchanged, so
    typing '/whatever' just posts it as written. Results are generated on the
    server so nobody can fake a roll.
    """

    if not body.startswith("/"):
        return body

    parts = body.split(None, 1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command == "/roll":

        spec = arg.split()[0] if arg else "d6"

        if spec.isdigit():
            spec = f"d{spec}"

        match = DICE.match(spec)

        if not match:
            return body

        count = int(match.group(1) or 1)
        sides = int(match.group(2))

        if count < 1 or count > 20 or sides < 2:
            return body

        rolls = [random.randint(1, sides) for _ in range(count)]

        detail = (
            f" ({' + '.join(str(r) for r in rolls)})" if count > 1 else ""
        )

        return f"🎲 {username} rolled {count}d{sides}: {sum(rolls)}{detail}"

    if command == "/flip":

        return f"🪙 {username} flipped a coin: {random.choice(['Heads', 'Tails'])}"

    if command == "/8ball":

        answer = random.choice(EIGHT_BALL)

        if arg:
            return f"🎱 {arg} → {answer}"

        return f"🎱 {username} shakes the 8-ball: {answer}"

    if command == "/choose":

        separator = "|" if "|" in arg else ","

        options = [o.strip() for o in arg.split(separator) if o.strip()][:10]

        if len(options) < 2:
            return body

        return (
            f"🤔 {username} asked me to choose: {random.choice(options)} "
            f"(from: {', '.join(options)})"
        )

    if command == "/shrug":

        return f"{arg} ¯\\_(ツ)_/¯".strip()

    if command == "/me":

        if not arg:
            return body

        return f"* {username} {arg}"

    return body
