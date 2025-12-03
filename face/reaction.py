# reaction.py
import random

FACE_EXPRESSIONS = {
    "neutral": {
        "eyes": "normal",
        "eyebrows": "normal", 
        "mouth": "neutral"
    },
    "happy": {
        "eyes": "happy",
        "eyebrows": "relaxed",
        "mouth": "smile"
    },
    "laughing": {
        "eyes": "closed",
        "eyebrows": "raised",
        "mouth": "laugh"
    },
    "surprised": {
        "eyes": "wide",
        "eyebrows": "raised",
        "mouth": "open"
    },
    "angry": {
        "eyes": "angry",
        "eyebrows": "angry",
        "mouth": "frown"
    },
    "sad": {
        "eyes": "sad",
        "eyebrows": "worried",
        "mouth": "sad"
    },
    "winking": {
        "eyes": "wink",
        "eyebrows": "raised",
        "mouth": "smirk"
    },
    "sleepy": {
        "eyes": "sleepy",
        "eyebrows": "relaxed",
        "mouth": "neutral"
    }
}

def get_random_expression():
    return random.choice(list(FACE_EXPRESSIONS.keys()))

def get_expression_data(expression_name):
    return FACE_EXPRESSIONS.get(expression_name, FACE_EXPRESSIONS["neutral"])