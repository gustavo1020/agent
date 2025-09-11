#!/usr/bin/env python3
"""
Script principal para ejecutar diferentes agentes según configuración.
"""
import os
import sys
from pathlib import Path

def main():
    """Ejecuta el agente correspondiente según la variable de entorno AGENT_TYPE."""
    agent_type = os.getenv('AGENT_TYPE', 'financial')
    
    print(f"🚀 Iniciando agente: {agent_type}")
    
    if agent_type == 'financial':
        # Importar y ejecutar el agente financiero
        sys.path.append('/app/Asistente_Financiero')
        from Asistente_Financiero.agent import root_agent
        print("💰 Agente Financiero iniciado correctamente")
        
    elif agent_type == 'japanese':
        # Importar y ejecutar el agente japonés
        sys.path.append('/app/Asistente_Japones')
        from Asistente_Japones.agent import root_agent
        print("🎌 Agente de Japonés iniciado correctamente")
        
    else:
        print(f"❌ Tipo de agente no reconocido: {agent_type}")
        print("💡 Tipos disponibles: 'financial', 'japanese'")
        sys.exit(1)

if __name__ == "__main__":
    main()
