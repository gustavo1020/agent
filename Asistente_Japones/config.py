# Configuración específica para el agente japonés
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

# Configuración de dificultad expandida
EXTENDED_DIFFICULTY = {
    "principiante": ["あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ"],
    "basico": ["あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ", "さ", "し", "す", "せ", "そ"],
    "intermedio": "primeros_30_caracteres",
    "avanzado": "todos_los_caracteres",
    "maestro": "incluye_combinaciones_especiales"
}
