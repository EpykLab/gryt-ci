"""
Code name generator for evolutions.

Generates friendly, memorable names like "whispy-monster-pineapple".
"""
import random


# Adjectives for code names
ADJECTIVES = [
    "autumn", "bold", "brave", "bright", "calm", "clever", "cosmic", "crimson",
    "crystal", "daring", "dashing", "divine", "elegant", "epic", "fancy", "fiery",
    "frosty", "gentle", "golden", "grand", "happy", "humble", "jolly", "kind",
    "lively", "lucky", "magic", "mighty", "misty", "noble", "proud", "quiet",
    "radiant", "rapid", "royal", "rusty", "shiny", "silent", "silver", "smooth",
    "snowy", "solar", "sparkly", "spring", "stellar", "stormy", "summer", "sunny",
    "swift", "tender", "twilight", "vibrant", "violet", "vivid", "wandering", "whispy",
    "wild", "winter", "witty", "zen"
]

# Nouns (animals, objects, nature)
NOUNS = [
    "aurora", "badger", "bear", "bison", "blizzard", "breeze", "cactus", "canyon",
    "castle", "cloud", "comet", "coral", "crater", "crystal", "delta", "dingo",
    "dolphin", "dragon", "eagle", "ember", "falcon", "fennec", "forest", "fox",
    "galaxy", "gecko", "glacier", "hawk", "heron", "horizon", "jaguar", "koala",
    "leopard", "lynx", "meadow", "meteor", "monsoon", "monster", "moon", "mountain",
    "nebula", "ocean", "otter", "owl", "panda", "panther", "phoenix", "pineapple",
    "planet", "quasar", "raven", "reef", "river", "rocket", "salmon", "savanna",
    "serpent", "shadow", "shark", "sparrow", "star", "storm", "summit", "sunrise",
    "sunset", "thunder", "tiger", "tornado", "tsunami", "tundra", "turtle", "typhoon",
    "valley", "volcano", "vortex", "walrus", "waterfall", "whale", "wildfire", "willow",
    "wolf", "zebra"
]


def generate_code_name() -> str:
    """
    Generate a random code name in the format: adjective-adjective-noun

    Examples:
        - whispy-monster-pineapple
        - golden-brave-dragon
        - cosmic-gentle-phoenix

    Returns:
        A randomly generated code name string
    """
    adj1 = random.choice(ADJECTIVES)
    adj2 = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)

    # Ensure the two adjectives are different
    while adj2 == adj1:
        adj2 = random.choice(ADJECTIVES)

    return f"{adj1}-{adj2}-{noun}"


def is_valid_code_name(code_name: str) -> bool:
    """
    Validate that a code name follows the expected format.

    Args:
        code_name: The code name to validate

    Returns:
        True if valid, False otherwise
    """
    if not code_name:
        return False

    parts = code_name.split("-")
    if len(parts) != 3:
        return False

    # Check if all parts are non-empty and alphanumeric
    return all(part and part.isalpha() for part in parts)
