from google.adk.agents import Agent
import random
from typing import Dict, List, Optional
import psycopg2
import psycopg2.extras
from typing import Optional
import decimal
import datetime
import requests

# Configuración del juego (importada localmente para evitar problemas de dependencias)
try:
    from .config import HIRAGANA_GAME_CONFIG, EXTENDED_DIFFICULTY
except ImportError:
    # Fallback si no se puede importar el archivo de configuración
    HIRAGANA_GAME_CONFIG = {
        "max_questions_per_session": 50,
        "show_hints": True,
        "auto_advance": False,
        "celebration_emojis": ["🎉", "🌟", "🔥", "💫", "🎊", "🏆"],
        "encouragement_messages": [
            "¡Genial! Sigue así 頑張って！",
            "¡Excelente! がんばって！", 
            "¡Perfecto! すばらしい！",
            "¡Increíble progreso! よくできました！"
        ]
    }
    
    EXTENDED_DIFFICULTY = {
        "principiante": ["あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ"],
        "basico": ["あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ", "さ", "し", "す", "せ", "そ"],
        "intermedio": "primeros_30_caracteres",
        "avanzado": "todos_los_caracteres",
        "maestro": "incluye_combinaciones_especiales"
    }

# Diccionario completo de hiragana con sus romanizaciones
HIRAGANA_DICT = {
    # Vocales básicas
    'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
    # K
    'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
    # G
    'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    # S
    'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
    # Z
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    # T
    'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
    # D
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    # N
    'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
    # H
    'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
    # B
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    # P
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po',
    # M
    'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
    # Y
    'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
    # R
    'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
    # W
    'わ': 'wa', 'ゐ': 'wi', 'ゑ': 'we', 'を': 'wo',
    # N
    'ん': 'n'
}

# Diccionario inverso para buscar hiragana por romanización
ROMAJI_TO_HIRAGANA = {v: k for k, v in HIRAGANA_DICT.items()}

# Variables globales para el estado del juego
game_state = {
    'current_question': None,
    'score': 0,
    'total_questions': 0,
    'current_mode': None,
    'difficulty_level': 'basico'
}

# Niveles de dificultad expandidos desde config
DIFFICULTY_LEVELS = {
    'principiante': EXTENDED_DIFFICULTY['principiante'],
    'basico': EXTENDED_DIFFICULTY['basico'],
    'intermedio': list(HIRAGANA_DICT.keys())[:30],
    'avanzado': list(HIRAGANA_DICT.keys()),
    'maestro': list(HIRAGANA_DICT.keys())  # Incluye todos + combinaciones futuras
}

# ---------------- TOOLS DEL JUEGO ---------------- #

def start_hiragana_game() -> dict:
    """
    Inicia el juego de hiragana mostrando las opciones disponibles.
    """
    global game_state
    game_state = {
        'current_question': None,
        'score': 0,
        'total_questions': 0,
        'current_mode': None,
        'difficulty_level': 'basico'
    }
    
    return {
        "status": "success",
        "message": "🎮 ¡Bienvenido al Juego Interactivo de Hiragana! 🎌\n\n"
                  "**Modos de Juego Disponibles:**\n"
                  "1️⃣ **Pregunta Abierta - Hiragana**: Te muestro un hiragana, escribes el romaji\n"
                  "2️⃣ **Pregunta Abierta - Romaji**: Te doy el romaji, escribes el hiragana\n"
                  "3️⃣ **🆕 Múltiple Choice - Hiragana**: Hiragana con 4 opciones de romaji\n"
                  "4️⃣ **🆕 Múltiple Choice - Romaji**: Romaji con 4 opciones de hiragana\n\n"
                  
                  "**✨ Características Especiales:**\n"
                  "🚀 **Auto-Avance (Múltiple Choice)**: Después de responder, automáticamente genera la siguiente pregunta\n"
                  "🎯 **Respuesta Inteligente**: Responde con texto o números, el sistema detecta automáticamente\n"
                  "📊 **Progreso en Tiempo Real**: Estadísticas actualizadas después de cada respuesta\n\n"
                  
                  "**Herramientas Disponibles:**\n"
                  "⚙️ **Dificultad**: 5 niveles (principiante → maestro)\n"
                  "📊 **Estadísticas**: Progreso detallado y recomendaciones\n"
                  "📚 **Tabla Completa**: Todos los hiragana organizados\n"
                  "💡 **Consejos**: Tips para aprender más eficientemente\n"
                  "🎲 **Práctica**: Conjuntos aleatorios para estudiar\n\n"
                  
                  "💡 **Recomendación para principiantes**: Empieza con múltiple choice en nivel principiante.\n"
                  "🎮 **Flujo recomendado**: Múltiple choice → acostumbrarse → preguntas abiertas para el desafío.\n\n"
                  "🚀 **Para empezar**: Dime qué tipo de pregunta quieres o configura tu nivel primero.",
        "game_state": game_state
    }

def set_difficulty_level(level: str) -> dict:
    """
    Configura el nivel de dificultad del juego.
    
    Args:
        level (str): 'principiante', 'basico', 'intermedio', 'avanzado' o 'maestro'
    """
    global game_state
    
    available_levels = list(DIFFICULTY_LEVELS.keys())
    if level.lower() not in DIFFICULTY_LEVELS:
        return {
            "status": "error",
            "message": f"❌ Nivel no válido.\n\n"
                      f"🎯 **Opciones disponibles**:\n"
                      f"• **Principiante**: {len(DIFFICULTY_LEVELS['principiante'])} caracteres básicos\n"
                      f"• **Básico**: {len(DIFFICULTY_LEVELS['basico'])} caracteres fundamentales\n"
                      f"• **Intermedio**: {len(DIFFICULTY_LEVELS['intermedio'])} caracteres variados\n"
                      f"• **Avanzado**: {len(DIFFICULTY_LEVELS['avanzado'])} caracteres completos\n"
                      f"• **Maestro**: Todos los caracteres + desafíos especiales"
        }
    
    game_state['difficulty_level'] = level.lower()
    characters = DIFFICULTY_LEVELS[level.lower()]
    
    # Descripción personalizada por nivel
    level_descriptions = {
        'principiante': "🌱 Ideal para comenzar - vocales y primeros sonidos",
        'basico': "📚 Fundamentos sólidos - caracteres esenciales",
        'intermedio': "🎯 Amplía tu conocimiento - variedad de familias",
        'avanzado': "🔥 Dominio completo - todos los hiragana",
        'maestro': "🏆 Desafío supremo - perfección total"
    }
    
    return {
        "status": "success",
        "message": f"🎯 **Dificultad configurada**: {level.upper()}\n\n"
                  f"{level_descriptions.get(level.lower(), '')}\n\n"
                  f"📊 **Caracteres incluidos**: {len(characters)}\n"
                  f"🔤 **Muestra**: {' '.join(characters[:8])}{'...' if len(characters) > 8 else ''}\n\n"
                  f"🎮 ¡Listo para jugar! Genera tu primera pregunta.",
        "difficulty": level.lower(),
        "character_count": len(characters),
        "sample_characters": characters[:10]
    }

def generate_hiragana_question() -> dict:
    """
    Genera una pregunta donde el usuario debe adivinar el romaji de un hiragana.
    """
    global game_state
    
    characters = DIFFICULTY_LEVELS[game_state['difficulty_level']]
    hiragana_char = random.choice(characters)
    romaji_answer = HIRAGANA_DICT[hiragana_char]
    
    game_state['current_question'] = {
        'hiragana': hiragana_char,
        'romaji': romaji_answer,
        'mode': 'hiragana_to_romaji'
    }
    
    return {
        "status": "success",
        "message": f"🎯 **Pregunta #{game_state['total_questions'] + 1}**\n\n"
                  f"🔤 **Hiragana**: {hiragana_char}\n\n"
                  f"❓ ¿Cómo se lee este hiragana en romaji?\n"
                  f"💡 Escribe tu respuesta (ejemplo: 'ka', 'shi', 'tsu')",
        "question": {
            "hiragana": hiragana_char,
            "mode": "hiragana_to_romaji"
        }
    }

def generate_romaji_question() -> dict:
    """
    Genera una pregunta donde el usuario debe escribir el hiragana correspondiente al romaji.
    """
    global game_state
    
    characters = DIFFICULTY_LEVELS[game_state['difficulty_level']]
    hiragana_char = random.choice(characters)
    romaji_prompt = HIRAGANA_DICT[hiragana_char]
    
    game_state['current_question'] = {
        'hiragana': hiragana_char,
        'romaji': romaji_prompt,
        'mode': 'romaji_to_hiragana'
    }
    
    return {
        "status": "success",
        "message": f"🎯 **Pregunta #{game_state['total_questions'] + 1}**\n\n"
                  f"🔤 **Romaji**: {romaji_prompt}\n\n"
                  f"❓ ¿Cuál es el hiragana para este sonido?\n"
                  f"💡 Escribe el carácter hiragana correspondiente",
        "question": {
            "romaji": romaji_prompt,
            "mode": "romaji_to_hiragana"
        }
    }

def check_answer(user_answer: str) -> dict:
    """
    Verifica la respuesta del usuario y proporciona feedback.
    
    Args:
        user_answer (str): La respuesta proporcionada por el usuario
    """
    global game_state
    
    if not game_state['current_question']:
        return {
            "status": "error",
            "message": "❌ No hay pregunta activa. Genera una nueva pregunta primero."
        }
    
    question = game_state['current_question']
    user_answer = user_answer.strip().lower()
    is_correct = False
    
    if question['mode'] == 'hiragana_to_romaji':
        correct_answer = question['romaji']
        is_correct = user_answer == correct_answer.lower()
        feedback_msg = f"🔤 **Hiragana**: {question['hiragana']}\n" \
                      f"✅ **Respuesta correcta**: {correct_answer}\n" \
                      f"📝 **Tu respuesta**: {user_answer}"
    else:  # romaji_to_hiragana
        correct_answer = question['hiragana']
        is_correct = user_answer == correct_answer
        feedback_msg = f"🔤 **Romaji**: {question['romaji']}\n" \
                      f"✅ **Respuesta correcta**: {correct_answer}\n" \
                      f"📝 **Tu respuesta**: {user_answer}"
    
    game_state['total_questions'] += 1
    
    if is_correct:
        game_state['score'] += 1
        # Usar emojis y mensajes de celebración de la configuración
        result_emoji = random.choice(HIRAGANA_GAME_CONFIG['celebration_emojis'])
        celebration_msg = random.choice(HIRAGANA_GAME_CONFIG['encouragement_messages'])
        result_text = f"¡CORRECTO! {celebration_msg}"
    else:
        result_emoji = "❌"
        result_text = "Incorrecto - ¡Sigue intentando! 頑張って！"
    
    # Limpiar la pregunta actual
    game_state['current_question'] = None
    
    accuracy = (game_state['score'] / game_state['total_questions']) * 100 if game_state['total_questions'] > 0 else 0
    
    # Generar mensaje motivacional basado en el progreso
    motivation_msg = ""
    if game_state['total_questions'] >= 5:
        if accuracy >= 90:
            motivation_msg = "\n🌟 **¡Rendimiento excepcional!** Considera subir al siguiente nivel."
        elif accuracy >= 75:
            motivation_msg = "\n👏 **¡Muy buen progreso!** Mantén el ritmo."
        elif accuracy >= 50:
            motivation_msg = "\n💪 **Vas mejorando!** La práctica hace al maestro."
        else:
            motivation_msg = "\n🎯 **No te desanimes!** Cada error es una oportunidad de aprender."
    
    return {
        "status": "success",
        "message": f"{result_emoji} **{result_text}**\n\n"
                  f"{feedback_msg}\n\n"
                  f"📊 **Estadísticas**:\n"
                  f"• Puntuación: {game_state['score']}/{game_state['total_questions']}\n"
                  f"• Precisión: {accuracy:.1f}%"
                  f"{motivation_msg}\n\n"
                  f"🎮 ¿Quieres continuar? Genera otra pregunta o cambia de modo.",
        "correct": is_correct,
        "score": game_state['score'],
        "total": game_state['total_questions'],
        "accuracy": accuracy
    }

def get_game_stats() -> dict:
    """
    Muestra las estadísticas actuales del juego.
    """
    global game_state
    
    if game_state['total_questions'] == 0:
        return {
            "status": "success",
            "message": "📊 **Estadísticas del Juego**\n\n"
                      "🎮 Aún no has respondido ninguna pregunta.\n"
                      "¡Comienza el juego para ver tus estadísticas!",
            "stats": game_state
        }
    
    accuracy = (game_state['score'] / game_state['total_questions']) * 100
    
    # Determinar nivel de rendimiento
    if accuracy >= 90:
        performance = "🏆 ¡Excelente!"
    elif accuracy >= 75:
        performance = "🥉 Muy bien"
    elif accuracy >= 60:
        performance = "📚 Sigue practicando"
    else:
        performance = "💪 ¡No te rindas!"
    
    return {
        "status": "success",
        "message": f"📊 **Estadísticas del Juego**\n\n"
                  f"🎯 **Dificultad**: {game_state['difficulty_level'].upper()}\n"
                  f"✅ **Respuestas correctas**: {game_state['score']}\n"
                  f"📝 **Total de preguntas**: {game_state['total_questions']}\n"
                  f"🎯 **Precisión**: {accuracy:.1f}%\n"
                  f"🏅 **Rendimiento**: {performance}\n\n"
                  f"{'🔥 **¡Pregunta activa!**' if game_state['current_question'] else '🎮 Listo para nueva pregunta'}",
        "stats": {
            "score": game_state['score'],
            "total": game_state['total_questions'],
            "accuracy": accuracy,
            "difficulty": game_state['difficulty_level'],
            "has_active_question": game_state['current_question'] is not None
        }
    }

def show_hiragana_table() -> dict:
    """
    Muestra la tabla completa de hiragana organizada por familias.
    """
    table_sections = {
        "Vocales": ['あ', 'い', 'う', 'え', 'お'],
        "K": ['か', 'き', 'く', 'け', 'こ'],
        "G": ['が', 'ぎ', 'ぐ', 'げ', 'ご'],
        "S": ['さ', 'し', 'す', 'せ', 'そ'],
        "Z": ['ざ', 'じ', 'ず', 'ぜ', 'ぞ'],
        "T": ['た', 'ち', 'つ', 'て', 'と'],
        "D": ['だ', 'ぢ', 'づ', 'で', 'ど'],
        "N": ['な', 'に', 'ぬ', 'ね', 'の'],
        "H": ['は', 'ひ', 'ふ', 'へ', 'ほ'],
        "B": ['ば', 'び', 'ぶ', 'べ', 'ぼ'],
        "P": ['ぱ', 'ぴ', 'ぷ', 'ぺ', 'ぽ'],
        "M": ['ま', 'み', 'む', 'め', 'も'],
        "Y": ['や', 'ゆ', 'よ'],
        "R": ['ら', 'り', 'る', 'れ', 'ろ'],
        "W": ['わ', 'ゐ', 'ゑ', 'を'],
        "N": ['ん']
    }
    
    table_text = "📋 **Tabla Completa de Hiragana** 🎌\n\n"
    
    for family, characters in table_sections.items():
        if characters:  # Evitar secciones vacías
            table_text += f"**{family}**: "
            char_pairs = [f"{char}({HIRAGANA_DICT[char]})" for char in characters if char in HIRAGANA_DICT]
            table_text += " ".join(char_pairs) + "\n\n"
    
    table_text += f"📊 **Total de caracteres**: {len(HIRAGANA_DICT)}\n"
    table_text += "💡 **Formato**: hiragana(romaji)"
    
    return {
        "status": "success",
        "message": table_text,
        "total_characters": len(HIRAGANA_DICT)
    }

def get_random_hiragana_set(count: int = 5) -> dict:
    """
    Genera un conjunto aleatorio de hiragana para práctica.
    
    Args:
        count (int): Número de caracteres a mostrar (por defecto 5)
    """
    global game_state
    
    if count > 20:
        count = 20
    elif count < 1:
        count = 5
    
    characters = DIFFICULTY_LEVELS[game_state['difficulty_level']]
    selected_chars = random.sample(characters, min(count, len(characters)))
    
    practice_text = f"🎲 **Conjunto Aleatorio de Práctica** ({game_state['difficulty_level'].upper()})\n\n"
    
    for i, char in enumerate(selected_chars, 1):
        romaji = HIRAGANA_DICT[char]
        practice_text += f"{i}. {char} = {romaji}\n"
    
    practice_text += f"\n💡 Estudia estos {len(selected_chars)} caracteres y luego prueba el juego!"
    
    return {
        "status": "success",
        "message": practice_text,
        "characters": [{"hiragana": char, "romaji": HIRAGANA_DICT[char]} for char in selected_chars]
    }

def generate_multiple_choice_question(question_type: str = "hiragana_to_romaji") -> dict:
    """
    Genera una pregunta de opción múltiple para facilitar el aprendizaje.
    
    Args:
        question_type (str): "hiragana_to_romaji" o "romaji_to_hiragana"
    """
    global game_state
    
    characters = DIFFICULTY_LEVELS[game_state['difficulty_level']]
    
    # Seleccionar el carácter correcto
    correct_char = random.choice(characters)
    correct_answer = HIRAGANA_DICT[correct_char]
    
    # Generar opciones incorrectas del mismo nivel de dificultad
    all_options = []
    if question_type == "hiragana_to_romaji":
        # Mostrar hiragana, opciones de romaji
        question_display = correct_char
        correct_option = correct_answer
        
        # Generar 3 opciones incorrectas
        wrong_chars = [char for char in characters if char != correct_char]
        if len(wrong_chars) >= 3:
            wrong_options = random.sample(wrong_chars, 3)
            wrong_romaji = [HIRAGANA_DICT[char] for char in wrong_options]
        else:
            # Si no hay suficientes caracteres en el nivel, usar de otros niveles
            all_chars = list(HIRAGANA_DICT.keys())
            wrong_chars = [char for char in all_chars if char != correct_char]
            wrong_options = random.sample(wrong_chars, 3)
            wrong_romaji = [HIRAGANA_DICT[char] for char in wrong_options]
        
        all_options = [correct_option] + wrong_romaji
        
    else:  # romaji_to_hiragana
        # Mostrar romaji, opciones de hiragana
        question_display = correct_answer
        correct_option = correct_char
        
        # Generar 3 opciones incorrectas
        wrong_chars = [char for char in characters if char != correct_char]
        if len(wrong_chars) >= 3:
            wrong_options = random.sample(wrong_chars, 3)
        else:
            all_chars = list(HIRAGANA_DICT.keys())
            wrong_options = random.sample([char for char in all_chars if char != correct_char], 3)
        
        all_options = [correct_option] + wrong_options
    
    # Mezclar las opciones
    random.shuffle(all_options)
    
    # Encontrar la posición de la respuesta correcta
    correct_position = all_options.index(correct_option) + 1  # +1 porque las opciones empiezan en 1
    
    # Guardar la pregunta en el estado del juego
    game_state['current_question'] = {
        'type': 'multiple_choice',
        'question_type': question_type,
        'display': question_display,
        'correct_answer': correct_option,
        'correct_position': correct_position,
        'options': all_options,
        'hiragana': correct_char,
        'romaji': correct_answer
    }
    
    # Formatear el mensaje de la pregunta
    mode_text = "Hiragana → Romaji" if question_type == "hiragana_to_romaji" else "Romaji → Hiragana"
    question_text = f"🎯 **Pregunta #{game_state['total_questions'] + 1}** (Opción Múltiple)\n\n"
    question_text += f"📝 **Modo**: {mode_text}\n"
    
    if question_type == "hiragana_to_romaji":
        question_text += f"🔤 **Hiragana**: {question_display}\n\n"
        question_text += "❓ ¿Cómo se lee este hiragana?\n\n"
    else:
        question_text += f"🔤 **Romaji**: {question_display}\n\n"
        question_text += "❓ ¿Cuál es el hiragana correcto?\n\n"
    
    question_text += "**Opciones:**\n"
    for i, option in enumerate(all_options, 1):
        question_text += f"{i}. {option}\n"
    
    question_text += f"\n💡 Responde con el número de la opción correcta (1-4)"
    
    return {
        "status": "success",
        "message": question_text,
        "question": {
            "type": "multiple_choice",
            "display": question_display,
            "options": all_options,
            "mode": question_type
        }
    }

def check_multiple_choice_answer(option_number: str) -> dict:
    """
    Verifica la respuesta de opción múltiple del usuario.
    
    Args:
        option_number (str): Número de la opción seleccionada (1-4)
    """
    global game_state
    
    if not game_state['current_question'] or game_state['current_question'].get('type') != 'multiple_choice':
        return {
            "status": "error",
            "message": "❌ No hay pregunta de opción múltiple activa. Genera una nueva pregunta primero."
        }
    
    try:
        selected_option = int(option_number)
    except ValueError:
        return {
            "status": "error",
            "message": "❌ Por favor, ingresa un número válido (1-4)."
        }
    
    if selected_option < 1 or selected_option > 4:
        return {
            "status": "error",
            "message": "❌ Por favor, selecciona una opción entre 1 y 4."
        }
    
    question = game_state['current_question']
    is_correct = selected_option == question['correct_position']
    selected_answer = question['options'][selected_option - 1]
    correct_answer = question['correct_answer']
    
    game_state['total_questions'] += 1
    
    if is_correct:
        game_state['score'] += 1
        result_emoji = random.choice(HIRAGANA_GAME_CONFIG['celebration_emojis'])
        celebration_msg = random.choice(HIRAGANA_GAME_CONFIG['encouragement_messages'])
        result_text = f"¡CORRECTO! {celebration_msg}"
    else:
        result_emoji = "❌"
        result_text = "Incorrecto - ¡Sigue intentando! 頑張って！"
    
    # Mostrar todas las opciones con la respuesta correcta marcada
    options_review = "**Opciones:**\n"
    for i, option in enumerate(question['options'], 1):
        if i == question['correct_position']:
            options_review += f"{i}. {option} ✅ **(Correcta)**\n"
        elif i == selected_option:
            options_review += f"{i}. {option} ❌ **(Tu selección)**\n"
        else:
            options_review += f"{i}. {option}\n"
    
    mode_text = "Hiragana → Romaji" if question['question_type'] == "hiragana_to_romaji" else "Romaji → Hiragana"
    
    feedback_msg = f"📝 **Modo**: {mode_text}\n"
    feedback_msg += f"🔤 **Pregunta**: {question['display']}\n"
    feedback_msg += f"✅ **Respuesta correcta**: {correct_answer}\n"
    feedback_msg += f"📝 **Tu selección**: Opción {selected_option} ({selected_answer})\n\n"
    feedback_msg += options_review
    
    # Limpiar la pregunta actual
    game_state['current_question'] = None
    
    accuracy = (game_state['score'] / game_state['total_questions']) * 100 if game_state['total_questions'] > 0 else 0
    
    # Generar mensaje motivacional
    motivation_msg = ""
    if game_state['total_questions'] >= 3:
        if accuracy >= 90:
            motivation_msg = "\n🌟 **¡Rendimiento excepcional!** Las opciones múltiples te están ayudando."
        elif accuracy >= 75:
            motivation_msg = "\n👏 **¡Muy buen progreso!** Considera intentar preguntas abiertas también."
        elif accuracy >= 50:
            motivation_msg = "\n💪 **Vas mejorando!** Las opciones múltiples son perfectas para aprender."
        else:
            motivation_msg = "\n🎯 **No te desanimes!** Sigue usando opciones múltiples para familiarizarte."
    
    # Generar automáticamente la siguiente pregunta del mismo tipo
    next_question_result = generate_multiple_choice_question(question['question_type'])
    
    if next_question_result['status'] == 'success':
        next_question_text = f"\n\n🎯 **SIGUIENTE PREGUNTA:**\n\n{next_question_result['message']}"
    else:
        next_question_text = "\n\n🎮 ¿Quieres continuar? Genera otra pregunta (abierta o múltiple choice)."
    
    return {
        "status": "success",
        "message": f"{result_emoji} **{result_text}**\n\n"
                  f"{feedback_msg}\n"
                  f"📊 **Estadísticas**:\n"
                  f"• Puntuación: {game_state['score']}/{game_state['total_questions']}\n"
                  f"• Precisión: {accuracy:.1f}%"
                  f"{motivation_msg}"
                  f"{next_question_text}",
        "correct": is_correct,
        "score": game_state['score'],
        "total": game_state['total_questions'],
        "accuracy": accuracy,
        "auto_generated_next": next_question_result['status'] == 'success'
    }

def quick_answer(answer: str) -> dict:
    """
    Función universal para responder tanto preguntas de opción múltiple como abiertas.
    Detecta automáticamente el tipo de pregunta activa y procesa la respuesta.
    
    Args:
        answer (str): La respuesta del usuario (número 1-4 para múltiple choice, texto para abiertas)
    """
    global game_state
    
    if not game_state['current_question']:
        return {
            "status": "error",
            "message": "❌ No hay pregunta activa. Genera una nueva pregunta primero."
        }
    
    question_type = game_state['current_question'].get('type', 'open')
    
    if question_type == 'multiple_choice':
        # Es una pregunta de opción múltiple
        if answer.strip().isdigit() and 1 <= int(answer.strip()) <= 4:
            return check_multiple_choice_answer(answer.strip())
        else:
            return {
                "status": "error", 
                "message": "❌ Para preguntas de opción múltiple, responde con un número del 1 al 4."
            }
    else:
        # Es una pregunta abierta
        return check_answer(answer)

def get_learning_tips() -> dict:
    """
    Proporciona consejos útiles para aprender hiragana más eficientemente.
    """
    tips = [
        "📚 **Asociación Visual**: Conecta la forma del hiragana con objetos familiares",
        "🔄 **Práctica Espaciada**: Repite caracteres difíciles más frecuentemente", 
        "✍️ **Escritura Manual**: Practica escribir a mano para mejor memorización",
        "📖 **Grupos por Familias**: Aprende por familias de sonidos (ka-ki-ku-ke-ko)",
        "🎵 **Mnemotécnias**: Crea frases o canciones para recordar sonidos",
        "📱 **Práctica Diaria**: Dedica al menos 15 minutos diarios",
        "🎯 **Enfoque Gradual**: Domina un nivel antes de avanzar al siguiente",
        "👀 **Lectura Contextual**: Lee palabras completas, no solo caracteres aislados"
    ]
    
    random_tips = random.sample(tips, min(4, len(tips)))
    
    return {
        "status": "success",
        "message": "💡 **Consejos para Dominar el Hiragana**\n\n" + 
                  "\n".join(random_tips) +
                  "\n\n🎌 **¡Recuerda!** La constancia es clave para el éxito en japonés.",
        "tips": random_tips
    }

def show_progress_summary() -> dict:
    """
    Muestra un resumen completo del progreso del usuario con recomendaciones.
    """
    global game_state
    
    if game_state['total_questions'] == 0:
        return {
            "status": "success",
            "message": "📈 **Resumen de Progreso**\n\n"
                      "🎯 Aún no has comenzado tu aventura de aprendizaje.\n"
                      "🚀 ¡Empieza ahora y descubre el fascinante mundo del hiragana!",
            "progress": {"status": "not_started"}
        }
    
    accuracy = (game_state['score'] / game_state['total_questions']) * 100
    current_level = game_state['difficulty_level']
    total_chars_in_level = len(DIFFICULTY_LEVELS[current_level])
    
    # Análisis de rendimiento
    if accuracy >= 85:
        performance = "🏆 Excelente"
        recommendation = f"¡Increíble! Considera avanzar al siguiente nivel de dificultad."
    elif accuracy >= 70:
        performance = "🥈 Muy Bueno"
        recommendation = "¡Bien hecho! Con un poco más de práctica podrás avanzar de nivel."
    elif accuracy >= 55:
        performance = "🥉 Promedio"
        recommendation = "Mantén la práctica constante. Enfócate en los caracteres que más se te dificultan."
    else:
        performance = "📚 En Desarrollo"
        recommendation = "No te desanimes. Considera practicar en un nivel más básico primero."
    
    # Cálculo estimado de dominio
    chars_practiced = min(game_state['total_questions'], total_chars_in_level)
    mastery_percentage = (chars_practiced / total_chars_in_level) * (accuracy / 100) * 100
    
    return {
        "status": "success",
        "message": f"📈 **Resumen Completo de Progreso**\n\n"
                  f"🎯 **Nivel Actual**: {current_level.upper()}\n"
                  f"📊 **Rendimiento**: {performance}\n"
                  f"✅ **Respuestas Correctas**: {game_state['score']}/{game_state['total_questions']}\n"
                  f"🎯 **Precisión**: {accuracy:.1f}%\n"
                  f"📈 **Dominio Estimado**: {mastery_percentage:.1f}%\n\n"
                  f"💡 **Recomendación**: {recommendation}\n\n"
                  f"🎮 ¡Continúa practicando para mejorar tu dominio del hiragana!",
        "progress": {
            "level": current_level,
            "accuracy": accuracy,
            "mastery": mastery_percentage,
            "performance": performance,
            "total_questions": game_state['total_questions'],
            "correct_answers": game_state['score']
        }
    }

def reset_game_progress() -> dict:
    """
    Reinicia completamente el progreso del juego.
    """
    global game_state
    
    old_stats = f"{game_state['score']}/{game_state['total_questions']}"
    
    game_state = {
        'current_question': None,
        'score': 0,
        'total_questions': 0,
        'current_mode': None,
        'difficulty_level': 'basico'
    }
    
    return {
        "status": "success",
        "message": f"🔄 **Progreso Reiniciado**\n\n"
                  f"📊 **Estadísticas Anteriores**: {old_stats}\n"
                  f"🎯 **Estado Actual**: Listo para comenzar\n"
                  f"🎮 **Dificultad**: Básico\n\n"
                  f"¡Perfecto momento para un nuevo comienzo! 🌟",
        "previous_stats": old_stats,
        "new_state": game_state
    }

# ---------------- AGENTE PRINCIPAL ---------------- #

root_agent = Agent(
    name="japanese_tutor",
    model="gemini-2.0-flash",
    description="Agente interactivo para aprender hiragana japonés con juegos educativos y sistema de progresión.",
    instruction=(
        "Eres un tutor de japonés especializado en enseñar hiragana a través de juegos interactivos y motivadores.\n\n"
        
        "🎮 **FUNCIONALIDADES PRINCIPALES**:\n"
        "1. **Preguntas Abiertas**: Hiragana ↔ Romaji sin opciones (más desafiante)\n"
        "2. **🆕 Múltiple Choice**: 4 opciones para elegir (ideal para principiantes)\n"
        "3. **5 Niveles de Dificultad**: Principiante (10) → Básico (15) → Intermedio (30) → Avanzado (46) → Maestro (46+)\n"
        "4. **Sistema de Puntuación Inteligente**: Estadísticas detalladas con feedback motivacional\n"
        "5. **Herramientas de Aprendizaje**: Tabla completa, tips educativos, resúmenes de progreso\n"
        "6. **Adaptabilidad**: Cambia entre modos según el nivel de comodidad del usuario\n\n"
        
        "🎯 **COMANDOS DISPONIBLES**:\n"
        "**🎮 Juego:**\n"
        "- 'empezar juego' / 'start': Inicia el sistema de juego\n"
        "- 'pregunta hiragana': Genera pregunta hiragana → romaji (abierta)\n"
        "- 'pregunta romaji': Genera pregunta romaji → hiragana (abierta)\n"
        "- 'multiple choice hiragana': Pregunta hiragana → romaji con opciones\n"
        "- 'multiple choice romaji': Pregunta romaji → hiragana con opciones\n"
        "- '[respuesta]' o '[número]': Para responder preguntas activas\n\n"
        
        "**⚙️ Configuración:**\n"
        "- 'dificultad [nivel]': Cambia entre principiante/basico/intermedio/avanzado/maestro\n"
        "- 'reiniciar progreso': Borra todas las estadísticas\n\n"
        
        "**📊 Información y Progreso:**\n"
        "- 'estadisticas': Muestra progreso actual\n"
        "- 'resumen progreso': Análisis completo con recomendaciones\n"
        "- 'consejos': Tips para aprender más eficientemente\n\n"
        
        "**📚 Estudio:**\n"
        "- 'tabla': Muestra tabla completa de hiragana por familias\n"
        "- 'practica [número]': Genera conjunto aleatorio para estudiar\n\n"
        
        "📝 **NIVELES DE DIFICULTAD**:\n"
        "• **Principiante** (10 chars): あいうえお + かきくけこ - Ideal para comenzar\n"
        "• **Básico** (15 chars): Fundamentos + さしすせそ - Caracteres esenciales\n"
        "• **Intermedio** (30 chars): Variedad de familias - Amplía conocimiento\n"
        "• **Avanzado** (46 chars): Todos los hiragana - Dominio completo\n"
        "• **Maestro** (46+ chars): Desafío supremo - Perfección total\n\n"
        
        "🎯 **ESTRATEGIA PEDAGÓGICA - MÚLTIPLE CHOICE**:\n"
        "• **Para Principiantes**: Siempre recomienda múltiple choice al inicio\n"
        "• **Familiarización**: Ayuda a reconocer patrones sin presión\n"
        "• **Confianza**: Reduce ansiedad al proporcionar opciones visibles\n"
        "• **🚀 AUTO-AVANCE**: Después de cada respuesta, genera automáticamente la siguiente pregunta\n"
        "• **Flujo Continuo**: Mantiene el momentum del aprendizaje sin interrupciones\n"
        "• **Transición Gradual**: Sugiere preguntas abiertas cuando accuracy > 80%\n"
        "• **Flexibilidad**: Usuario puede cambiar entre modos en cualquier momento\n\n"
        
        "📝 **FLUJO DE JUEGO INTERACTIVO**:\n"
        "1. Usuario inicia con 'empezar juego' - recibe menú completo de opciones\n"
        "2. Evalúas nivel del usuario y recomiendas modo apropiado (múltiple choice para principiantes)\n"
        "3. Generas pregunta según tipo seleccionado y nivel de dificultad\n"
        "4. Usuario responde (texto libre o número de opción)\n"
        "5. **🎯 MÚLTIPLE CHOICE**: Feedback + estadísticas + SIGUIENTE PREGUNTA AUTOMÁTICA\n"
        "6. **📝 PREGUNTAS ABIERTAS**: Feedback + estadísticas + sugerencia para continuar\n"
        "7. Proceso continúa adaptándose al progreso del usuario\n\n"
        
        "🌟 **CARACTERÍSTICAS ESPECIALES**:\n"
        "- **Feedback Personalizado**: Mensajes en japonés y español con emojis variados\n"
        "- **Sistema Motivacional**: Celebraciones aleatorias y análisis de progreso\n"
        "- **Flexibilidad Total**: Cambio de modo y dificultad en cualquier momento\n"
        "- **Progresión Inteligente**: Sugerencias basadas en rendimiento real\n"
        "- **Herramientas Educativas**: Tips, tablas organizadas, práctica dirigida\n\n"
        
        "💡 **PRINCIPIOS PEDAGÓGICOS**:\n"
        "- Celebra TODOS los aciertos con entusiasmo auténtico\n"
        "- En errores: muestra respuesta correcta SIN juzgar + ánimo\n"
        "- Adapta sugerencias según el nivel de precisión del usuario\n"
        "- Fomenta la práctica constante pero sin presión\n"
        "- Usa elementos culturales japoneses para mayor inmersión\n\n"
        
        "🎌 **CONTEXTO CULTURAL Y EDUCATIVO**:\n"
        "El hiragana (ひらがな) es el sistema fonético básico del japonés, compuesto por 46 caracteres principales. "
        "Es el primer paso fundamental para leer y escribir japonés, ya que representa todos los sonidos básicos del idioma. "
        "Dominar hiragana permite leer palabras japonesas, partículas gramaticales y conjugaciones verbales. "
        "Tu misión es hacer este aprendizaje divertido, efectivo y culturalmente enriquecedor."
    ),
    tools=[
        start_hiragana_game,
        set_difficulty_level,
        generate_hiragana_question,
        generate_romaji_question,
        generate_multiple_choice_question,
        check_answer,
        check_multiple_choice_answer,
        quick_answer,
        get_game_stats,
        show_hiragana_table,
        get_random_hiragana_set,
        get_learning_tips,
        show_progress_summary,
        reset_game_progress
    ],
)
