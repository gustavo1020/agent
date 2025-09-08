from google.adk.agents import Agent
import psycopg2
import psycopg2.extras
from typing import Optional
import decimal
import datetime
import requests

# Conexión a Postgres (el host será "db" porque así lo definimos en docker-compose)
def get_connection():
    return psycopg2.connect(
        dbname="finanzas",
        user="postgres",
        password="postgres",
        host="db",
        port="5432"
    )

# ---------------- TOOLS ---------------- #

def add_transaction(tipo: str, monto: float, fecha: str, descripcion: str, contraparte: Optional[str] = None) -> dict:
    """
    Agrega una transacción a la base de datos.
    
    Args:
        tipo (str): ingreso, gasto o prestamo.
        monto (float): cantidad de dinero.
        fecha (str): fecha en formato YYYY-MM-DD.
        descripcion (str): contexto de la operación.
        contraparte (str, optional): persona o entidad relacionada.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO transacciones (tipo, monto, fecha, descripcion, contraparte)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """,
            (tipo, monto, fecha, descripcion, contraparte)
        )
        
        transaction_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Transacción de {tipo} registrada exitosamente",
            "transaction_id": transaction_id,
            "monto": monto,
            "fecha": fecha
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_balance() -> dict:
    """Devuelve el balance actual (ingresos - gastos - préstamos)."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END) -
                SUM(CASE WHEN tipo IN ('gasto','prestamo') THEN monto ELSE 0 END) AS balance
            FROM transacciones;
            """
        )
        balance = cur.fetchone()["balance"] or 0
        cur.close()
        conn.close()
        return {"status": "success", "balance": balance}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


    
def list_transactions(limit: int = 10) -> dict:
    """
    Lista las últimas transacciones.
    
    Si limit es 0 o mayor a 100, devuelve hasta 100 transacciones.
    Además, imprime cada transacción por consola.
    """
    if limit <= 0 or limit > 100:
        limit = 100

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM transacciones ORDER BY fecha DESC, id DESC LIMIT %s;",
            (limit,)
        )
        rows = cur.fetchall()
        print("[DEBUG] New consulta:")
        
        # Convertir Decimal a float y date a string
        for row in rows:
            for k, v in row.items():
                if isinstance(v, decimal.Decimal):
                    row[k] = float(v)
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    row[k] = v.isoformat()
            # Imprimir cada transacción en consola
            print("[DEBUG] Transacción:", row)

        cur.close()
        conn.close()
        return {"status": "success", "transactions": rows}

    except Exception as e:
        print("[ERROR] list_transactions:", e)
        return {"status": "error", "error_message": str(e)}
    


# Tool para obtener la fecha actual
def get_today_date() -> dict:
    """
    Devuelve la fecha de hoy en formato YYYY-MM-DD
    """
    today = datetime.datetime.now().date()
    return {
        "status": "success",
        "today": today.isoformat()
    }

# ---------------- FUNCIONES DE TASAS DE CAMBIO ---------------- #

def update_exchange_rate(moneda_origen: str, tasa: float, moneda_destino: str = "USD") -> dict:
    """
    Actualiza la tasa de cambio de una moneda a USD (o otra moneda).
    
    Args:
        moneda_origen (str): Moneda de origen (ej: 'BOB', 'EUR')
        tasa (float): Tasa de cambio (cuántos USD vale 1 unidad de la moneda origen)
        moneda_destino (str): Moneda destino (por defecto USD)
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO tasas_cambio (moneda_origen, moneda_destino, tasa, fecha_actualizacion)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (moneda_origen, moneda_destino)
            DO UPDATE SET tasa = EXCLUDED.tasa, fecha_actualizacion = NOW()
            RETURNING id;
            """,
            (moneda_origen.upper(), moneda_destino.upper(), tasa)
        )
        
        rate_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "message": f"Tasa {moneda_origen}/{moneda_destino} actualizada: {tasa}",
            "rate_id": rate_id
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_exchange_rate(moneda_origen: str, moneda_destino: str = "USD") -> dict:
    """
    Obtiene la tasa de cambio actual.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute(
            """
            SELECT tasa, fecha_actualizacion 
            FROM tasas_cambio 
            WHERE moneda_origen = %s AND moneda_destino = %s;
            """,
            (moneda_origen.upper(), moneda_destino.upper())
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return {
                "status": "success",
                "tasa": float(result["tasa"]),
                "fecha_actualizacion": result["fecha_actualizacion"].isoformat()
            }
        else:
            return {
                "status": "error",
                "error_message": f"No se encontró tasa para {moneda_origen}/{moneda_destino}"
            }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def convert_to_usd(monto: float, moneda: str) -> dict:
    """
    Convierte un monto en cualquier moneda a USD.
    """
    if moneda.upper() == "USD":
        return {
            "status": "success",
            "monto_original": monto,
            "monto_usd": monto,
            "tasa_usada": 1.0
        }
    
    rate_result = get_exchange_rate(moneda, "USD")
    if rate_result["status"] == "error":
        return rate_result
    
    tasa = rate_result["tasa"]
    monto_usd = monto * tasa
    
    return {
        "status": "success",
        "monto_original": monto,
        "monto_usd": round(monto_usd, 2),
        "tasa_usada": tasa
    }

def get_current_exchange_rate_from_api(moneda: str, fecha: Optional[str] = None) -> dict:
    """
    Obtiene la cotización actual de una moneda desde una API externa.
    
    Args:
        moneda (str): Moneda a consultar (ej: 'BOB', 'EUR')
        fecha (str): Fecha específica en formato YYYY-MM-DD (opcional)
    """
    try:
        # Normalizar moneda: 'pesos' = 'ARS'
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        
        # Para Argentina (ARS) - pesos argentinos
        if moneda.upper() == "ARS":
            # Simulamos una cotización para ARS (puedes reemplazar con API real)
            cotizacion = 1362.33  # 1 USD = 1362.33 ARS aproximadamente
            return {
                "status": "success",
                "moneda": "ARS",
                "cotizacion_usd": 1 / cotizacion,  # Cuántos USD vale 1 ARS
                "cotizacion_original": cotizacion,  # Cuántos ARS vale 1 USD
                "fecha": fecha or datetime.datetime.now().date().isoformat(),
                "fuente": "Cotización Argentina (simulado)"
            }
        
        # Para Bolivia (BOB) - usando API del Banco Central de Bolivia
        if moneda.upper() == "BOB":
            # Simulamos una cotización fija para BOB (puedes reemplazar con API real)
            cotizacion = 6.91  # 1 USD = 6.91 BOB aproximadamente
            return {
                "status": "success",
                "moneda": "BOB",
                "cotizacion_usd": 1 / cotizacion,  # Cuántos USD vale 1 BOB
                "cotizacion_original": cotizacion,  # Cuántos BOB vale 1 USD
                "fecha": fecha or datetime.datetime.now().date().isoformat(),
                "fuente": "Banco Central de Bolivia (simulado)"
            }
        
        # Para otras monedas - usando API gratuita
        try:
            # Usando API gratuita de exchangerate-api.com
            url = f"https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if moneda.upper() in data["rates"]:
                    # El API devuelve: 1 USD = X moneda
                    # Por ejemplo: "ARS": 1362.33 significa 1 USD = 1362.33 ARS
                    usd_to_moneda = data["rates"][moneda.upper()]  # Cuántas unidades de moneda por 1 USD
                    moneda_to_usd = 1 / usd_to_moneda  # Cuántos USD por 1 unidad de moneda
                    
                    return {
                        "status": "success",
                        "moneda": moneda.upper(),
                        "cotizacion_usd": moneda_to_usd,  # Cuántos USD vale 1 unidad de la moneda
                        "cotizacion_original": usd_to_moneda,  # Cuántas unidades de moneda vale 1 USD
                        "fecha": fecha or datetime.datetime.now().date().isoformat(),
                        "fuente": "exchangerate-api.com",
                        "api_response_sample": f"1 USD = {usd_to_moneda} {moneda.upper()}"
                    }
                else:
                    return {
                        "status": "error",
                        "error_message": f"Moneda {moneda} no encontrada en la API"
                    }
            else:
                return {
                    "status": "error",
                    "error_message": f"Error en API: {response.status_code}"
                }
        
        except requests.RequestException as e:
            # Si falla la API, usar valores por defecto o pedir al usuario
            return {
                "status": "error",
                "error_message": f"No se pudo conectar a la API de cotizaciones: {str(e)}",
                "sugerencia": "Por favor proporciona la tasa de cambio manualmente"
            }
            
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def save_exchange_rate_from_api(moneda: str, fecha: Optional[str] = None) -> dict:
    """
    Obtiene y guarda automáticamente la cotización de una moneda.
    """
    try:
        # Obtener cotización de la API
        api_result = get_current_exchange_rate_from_api(moneda, fecha)
        
        if api_result["status"] == "success":
            # Guardar en la base de datos
            save_result = update_exchange_rate(
                moneda, 
                api_result["cotizacion_usd"], 
                "USD"
            )
            
            if save_result["status"] == "success":
                return {
                    "status": "success",
                    "message": f"Cotización de {moneda} obtenida y guardada automáticamente",
                    "cotizacion": api_result["cotizacion_usd"],
                    "fecha": api_result["fecha"],
                    "fuente": api_result["fuente"]
                }
            else:
                return save_result
        else:
            return api_result
            
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ---------------- FUNCIONES DE PRÉSTAMOS ---------------- #

def add_loan(monto_total: float, moneda: str, persona: str, fecha_prestamo: str,
            porcentaje_interes: float = 0.0, tiene_intermediario: bool = False, 
            porcentaje_intermediario: float = 0.0, descripcion: Optional[str] = None) -> dict:
    """
    Registra un nuevo préstamo con cotización del día actual.
    
    Cálculo CORREGIDO:
    1. Obtiene cotización automática del DÍA ACTUAL (no de la fecha del préstamo)
    2. Si hay intermediario: porcentaje_intermediario se descuenta del porcentaje_interes
    3. Ganancia neta = monto_total * (porcentaje_interes - porcentaje_intermediario) / 100
    4. Ejemplo: $5000 al 10% con 5% intermediario = $5000 * 5% = $250 ganancia neta
    
    Args:
        monto_total (float): Monto total del préstamo
        moneda (str): Moneda del préstamo ('pesos' = ARS automáticamente)
        persona (str): Persona a quien se prestó
        fecha_prestamo (str): Fecha del préstamo en formato YYYY-MM-DD
        porcentaje_interes (float): Porcentaje de interés total del préstamo
        tiene_intermediario (bool): Si hay intermediario
        porcentaje_intermediario (float): Porcentaje del intermediario (se resta del interés)
        descripcion (str): Descripción adicional
    """
    try:
        # Normalizar moneda: 'pesos' = 'ARS'
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        
        # Validar formato de fecha
        try:
            fecha_obj = datetime.datetime.strptime(fecha_prestamo, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "error_message": "Formato de fecha inválido. Use YYYY-MM-DD (ej: 2025-09-05)"
            }
        
        # Obtener cotización automática del DÍA ACTUAL (no de la fecha del préstamo)
        cotizacion_resultado = None
        cotizacion_momento = None
        fecha_cotizacion = datetime.datetime.now().date().isoformat()
        
        if moneda.upper() != "USD":
            # Intentar obtener cotización automática del día de hoy
            api_result = get_current_exchange_rate_from_api(moneda, fecha_cotizacion)
            if api_result["status"] == "success":
                cotizacion_momento = api_result["cotizacion_usd"]
                cotizacion_resultado = api_result
                # Guardar la cotización en la base de datos
                update_exchange_rate(moneda, cotizacion_momento, "USD")
            else:
                # Si falla la API, verificar si ya existe en la BD
                existing_rate = get_exchange_rate(moneda, "USD")
                if existing_rate["status"] == "success":
                    cotizacion_momento = existing_rate["tasa"]
                    cotizacion_resultado = {
                        "status": "warning",
                        "message": "No se pudo obtener cotización automática, usando tasa guardada",
                        "cotizacion_usd": cotizacion_momento,
                        "fuente": "Base de datos local"
                    }
                else:
                    return {
                        "status": "error",
                        "error_message": f"No se pudo obtener cotización para {moneda}. {api_result.get('error_message', 'Error desconocido')}",
                        "sugerencia": "Por favor, actualiza la tasa de cambio manualmente primero"
                    }
        else:
            cotizacion_momento = 1.0  # USD a USD
        
        # CÁLCULO CORREGIDO: intermediario se resta del porcentaje de interés
        porcentaje_neto = porcentaje_interes
        if tiene_intermediario:
            porcentaje_neto = porcentaje_interes - porcentaje_intermediario
        
        # Ganancia neta final
        ganancia_neta = monto_total * (porcentaje_neto / 100)
        
        # Monto del intermediario (sobre el monto total, no sobre los intereses)
        monto_intermediario = monto_total * (porcentaje_intermediario / 100) if tiene_intermediario else 0
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO prestamos (monto_total, moneda, persona, porcentaje_interes,
                                 tiene_intermediario, porcentaje_intermediario, 
                                 monto_intermediario, monto_en_mano, fecha_prestamo, 
                                 cotizacion_momento, descripcion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """,
            (monto_total, moneda.upper(), persona, porcentaje_interes, tiene_intermediario,
             porcentaje_intermediario, monto_intermediario, ganancia_neta, fecha_obj, 
             cotizacion_momento, descripcion)
        )
        
        loan_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        result = {
            "status": "success",
            "message": f"Préstamo registrado exitosamente",
            "loan_id": loan_id,
            "fecha_prestamo": fecha_prestamo,
            "fecha_cotizacion": fecha_cotizacion,
            "monto_prestado": monto_total,
            "porcentaje_interes_total": porcentaje_interes,
            "porcentaje_intermediario": porcentaje_intermediario,
            "porcentaje_neto_tuyo": porcentaje_neto,
            "monto_intermediario": monto_intermediario,
            "ganancia_neta_tuya": ganancia_neta,
            "moneda": moneda.upper(),
            "cotizacion_momento": cotizacion_momento,
            "persona": persona,
            "calculo_detalle": {
                "explicacion": f"Préstamo: {monto_total} {moneda}",
                "interes_total": f"{porcentaje_interes}% sobre {monto_total} = {monto_total * (porcentaje_interes / 100)} {moneda}",
                "descuento_intermediario": f"Intermediario: {porcentaje_intermediario}% del monto total = {monto_intermediario} {moneda}" if tiene_intermediario else "Sin intermediario",
                "porcentaje_neto": f"Tu porcentaje neto: {porcentaje_neto}% (era {porcentaje_interes}% - {porcentaje_intermediario}% intermediario)",
                "ganancia_final": f"Tu ganancia: {monto_total} × {porcentaje_neto}% = {ganancia_neta} {moneda}",
                "cotizacion": f"Cotización del {fecha_cotizacion}: 1 {moneda} = {cotizacion_momento} USD" if cotizacion_momento else "No disponible"
            }
        }
        
        # Añadir información de cotización si está disponible
        if cotizacion_resultado:
            result["cotizacion_info"] = cotizacion_resultado
            
        return result
        
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def list_loans(estado: str = "activo") -> dict:
    """
    Lista todos los préstamos activos o finalizados con conversiones de moneda al momento de consulta.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if estado == "todos":
            cur.execute("SELECT * FROM prestamos ORDER BY fecha_prestamo DESC;")
        else:
            cur.execute("SELECT * FROM prestamos WHERE estado = %s ORDER BY fecha_prestamo DESC;", (estado,))
        
        loans = cur.fetchall()
        cur.close()
        conn.close()
        
        loans_with_conversions = []
        
        # Totales por moneda original
        totales_por_moneda = {}
        
        # Totales convertidos a USD y ARS
        total_prestado_usd = 0
        total_en_mano_usd = 0
        total_prestado_ars = 0
        total_en_mano_ars = 0
        
        # Obtener cotización actual para conversiones
        fecha_hoy = datetime.datetime.now().date().isoformat()
        cotizacion_ars = get_current_exchange_rate_from_api("ARS", fecha_hoy)
        ars_por_usd = cotizacion_ars.get("cotizacion_original", 1362.33) if cotizacion_ars["status"] == "success" else 1362.33
        
        for loan in loans:
            # Convertir Decimal a float y date a string
            for k, v in loan.items():
                if isinstance(v, decimal.Decimal):
                    loan[k] = float(v)
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    loan[k] = v.isoformat()
            
            moneda = loan["moneda"]
            monto_total = loan["monto_total"]
            monto_en_mano = loan["monto_en_mano"]
            
            # Acumular por moneda original
            if moneda not in totales_por_moneda:
                totales_por_moneda[moneda] = {
                    "prestado": 0,
                    "en_mano": 0,
                    "cantidad": 0
                }
            
            totales_por_moneda[moneda]["prestado"] += monto_total
            totales_por_moneda[moneda]["en_mano"] += monto_en_mano
            totales_por_moneda[moneda]["cantidad"] += 1
            
            # Convertir a USD y ARS para totales
            if moneda == "USD":
                loan["monto_total_usd"] = monto_total
                loan["monto_en_mano_usd"] = monto_en_mano
                loan["monto_total_ars"] = monto_total * ars_por_usd
                loan["monto_en_mano_ars"] = monto_en_mano * ars_por_usd
                
                total_prestado_usd += monto_total
                total_en_mano_usd += monto_en_mano
                total_prestado_ars += monto_total * ars_por_usd
                total_en_mano_ars += monto_en_mano * ars_por_usd
                
            elif moneda == "ARS":
                loan["monto_total_ars"] = monto_total
                loan["monto_en_mano_ars"] = monto_en_mano
                loan["monto_total_usd"] = monto_total / ars_por_usd
                loan["monto_en_mano_usd"] = monto_en_mano / ars_por_usd
                
                total_prestado_ars += monto_total
                total_en_mano_ars += monto_en_mano
                total_prestado_usd += monto_total / ars_por_usd
                total_en_mano_usd += monto_en_mano / ars_por_usd
            
            # Añadir explicación del cálculo
            ganancia_intereses = monto_total * (loan["porcentaje_interes"] / 100)
            loan["ganancia_intereses"] = ganancia_intereses
            loan["calculo_explicacion"] = {
                "monto_prestado": f"{monto_total:,.2f} {moneda}",
                "ganancia_intereses": f"{ganancia_intereses:,.2f} {moneda} ({loan['porcentaje_interes']}%)",
                "descuento_intermediario": f"{loan['monto_intermediario']:,.2f} {moneda} ({loan['porcentaje_intermediario']}%)" if loan["tiene_intermediario"] else "Sin intermediario",
                "monto_en_mano": f"{monto_en_mano:,.2f} {moneda}"
            }
            
            loans_with_conversions.append(loan)
        
        return {
            "status": "success",
            "prestamos": loans_with_conversions,
            "totales_por_moneda_original": totales_por_moneda,
            "totales_convertidos": {
                "total_prestado_usd": round(total_prestado_usd, 2),
                "total_en_mano_usd": round(total_en_mano_usd, 2),
                "total_prestado_ars": round(total_prestado_ars, 2),
                "total_en_mano_ars": round(total_en_mano_ars, 2)
            },
            "cantidad_prestamos": len(loans_with_conversions),
            "cotizacion_usada": f"1 USD = {ars_por_usd:,.2f} ARS (fecha: {fecha_hoy})",
            "resumen": {
                "explicacion": "Préstamos guardados en moneda original, convertidos al momento de consulta",
                "monedas_disponibles": list(totales_por_moneda.keys())
            }
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def finish_loan(loan_id: int) -> dict:
    """
    Marca un préstamo como finalizado y devuelve las GANANCIAS (monto en mano) al saldo actual.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Obtener datos del préstamo
        cur.execute("SELECT * FROM prestamos WHERE id = %s AND estado = 'activo';", (loan_id,))
        loan = cur.fetchone()
        
        if not loan:
            return {"status": "error", "error_message": f"No se encontró préstamo activo con ID {loan_id}"}
        
        # Convertir el MONTO EN MANO (las ganancias reales) a USD
        monto_en_mano = float(loan["monto_en_mano"])
        conversion = convert_to_usd(monto_en_mano, loan["moneda"])
        monto_en_mano_usd = conversion["monto_usd"] if conversion["status"] == "success" else 0
        
        # Marcar préstamo como finalizado
        cur.execute("UPDATE prestamos SET estado = 'finalizado' WHERE id = %s;", (loan_id,))
        
        # Añadir las GANANCIAS al saldo actual (no el monto total prestado)
        add_to_current_balance_result = add_to_current_balance(
            monto_en_mano, 
            loan["moneda"],
            f"Préstamo finalizado: {loan['persona']} - Ganancia: {monto_en_mano} {loan['moneda']}", 
            "prestamo_finalizado"
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Calcular detalles para mostrar
        monto_total = float(loan["monto_total"])
        ganancia_intereses = monto_total * (float(loan["porcentaje_interes"]) / 100)
        monto_intermediario = float(loan["monto_intermediario"])
        
        return {
            "status": "success",
            "message": f"Préstamo finalizado y ganancias añadidas al saldo",
            "loan_id": loan_id,
            "persona": loan["persona"],
            "monto_prestado": monto_total,
            "ganancia_intereses": ganancia_intereses,
            "descuento_intermediario": monto_intermediario,
            "monto_recuperado": monto_en_mano,
            "moneda": loan["moneda"],
            "monto_recuperado_usd": monto_en_mano_usd,
            "explicacion": f"Se devolvieron {monto_en_mano} {loan['moneda']} (${monto_en_mano_usd} USD) al saldo - esto son tus ganancias reales"
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ---------------- FUNCIONES DE SALDO ACTUAL ---------------- #

def get_current_balance() -> dict:
    """
    Obtiene el saldo actual por moneda y total convertido a USD y ARS.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Obtener saldo por moneda
        cur.execute(
            """
            SELECT moneda, SUM(monto) as total_por_moneda 
            FROM saldo_actual 
            GROUP BY moneda 
            HAVING SUM(monto) != 0
            ORDER BY moneda;
            """
        )
        saldos_por_moneda = cur.fetchall()
        
        # También obtener el total en USD (como antes para compatibilidad)
        cur.execute("SELECT SUM(CASE WHEN moneda = 'USD' THEN monto ELSE 0 END) as total_usd FROM saldo_actual;")
        total_usd_result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        total_usd = float(total_usd_result["total_usd"]) if total_usd_result["total_usd"] else 0
        
        # Convertir Decimal a float
        saldos_detallados = []
        for saldo in saldos_por_moneda:
            saldos_detallados.append({
                "moneda": saldo["moneda"],
                "monto": float(saldo["total_por_moneda"])
            })
        
        return {
            "status": "success",
            "saldo_actual_usd": total_usd,  # Para compatibilidad con código existente
            "saldos_por_moneda": saldos_detallados,
            "detalle": f"Tienes saldo en {len(saldos_detallados)} moneda(s)"
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def add_to_current_balance(monto: float, moneda: str, descripcion: str, tipo_operacion: str) -> dict:
    """
    Añade dinero al saldo actual en la moneda original especificada.
    """
    try:
        # Normalizar moneda
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        moneda = moneda.upper()
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Obtener saldo anterior (solo para el historial, calculado en USD para compatibilidad)
        balance_result = get_current_balance()
        saldo_anterior_usd = balance_result.get("saldo_actual_usd", 0) if balance_result["status"] == "success" else 0
        
        # Añadir al saldo en la moneda original
        cur.execute(
            """
            INSERT INTO saldo_actual (monto, moneda, descripcion, updated_at)
            VALUES (%s, %s, %s, NOW());
            """,
            (monto, moneda, descripcion)
        )
        
        # Convertir el monto a USD para el historial
        if moneda == "USD":
            monto_usd = monto
        else:
            conversion = convert_to_usd(monto, moneda)
            monto_usd = conversion["monto_usd"] if conversion["status"] == "success" else 0
        
        # Calcular nuevo saldo en USD (para el historial)
        saldo_nuevo_usd = saldo_anterior_usd + monto_usd
        
        # Registrar en historial (en USD para compatibilidad)
        cur.execute(
            """
            INSERT INTO historial_saldo (tipo_operacion, monto_operacion, saldo_anterior, 
                                       saldo_nuevo, descripcion)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (tipo_operacion, monto_usd, saldo_anterior_usd, saldo_nuevo_usd, f"{descripcion} ({monto} {moneda})")
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "monto_añadido": monto,
            "moneda_original": moneda,
            "monto_usd_equivalente": monto_usd,
            "saldo_anterior_usd": saldo_anterior_usd,
            "saldo_nuevo_usd": saldo_nuevo_usd,
            "mensaje": f"Añadido {monto} {moneda} al saldo"
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def subtract_from_current_balance(monto: float, moneda: str, descripcion: str, tipo_operacion: str = "gasto") -> dict:
    """
    Resta dinero del saldo actual en la moneda especificada.
    """
    try:
        # Normalizar moneda
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        moneda = moneda.upper()
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Obtener saldo anterior
        balance_result = get_current_balance()
        saldo_anterior_usd = balance_result.get("saldo_actual_usd", 0) if balance_result["status"] == "success" else 0
        
        # Convertir el monto a USD para verificar si hay suficiente saldo
        if moneda == "USD":
            monto_usd = monto
        else:
            conversion = convert_to_usd(monto, moneda)
            if conversion["status"] == "error":
                return conversion
            monto_usd = conversion["monto_usd"]
        
        if saldo_anterior_usd < monto_usd:
            return {
                "status": "error",
                "error_message": f"Saldo insuficiente. Saldo actual: ${saldo_anterior_usd:.2f} USD, Intento de gasto: {monto} {moneda} (${monto_usd:.2f} USD)"
            }
        
        # Restar del saldo en la moneda original
        cur.execute(
            """
            INSERT INTO saldo_actual (monto, moneda, descripcion, updated_at)
            VALUES (%s, %s, %s, NOW());
            """,
            (-monto, moneda, descripcion)
        )
        
        # Calcular nuevo saldo en USD (para el historial)
        saldo_nuevo_usd = saldo_anterior_usd - monto_usd
        
        # Registrar en historial
        cur.execute(
            """
            INSERT INTO historial_saldo (tipo_operacion, monto_operacion, saldo_anterior, 
                                       saldo_nuevo, descripcion)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (tipo_operacion, monto_usd, saldo_anterior_usd, saldo_nuevo_usd, f"{descripcion} ({monto} {moneda})")
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "monto_gastado": monto,
            "moneda_original": moneda,
            "monto_usd_equivalente": monto_usd,
            "saldo_anterior_usd": saldo_anterior_usd,
            "saldo_nuevo_usd": saldo_nuevo_usd,
            "mensaje": f"Restado {monto} {moneda} del saldo"
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def add_expense(monto: float, moneda: str, descripcion: str) -> dict:
    """
    Registra un gasto y lo descuenta del saldo actual en la moneda especificada.
    """
    try:
        # Normalizar moneda
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        
        # Descontar del saldo
        result = subtract_from_current_balance(
            monto, 
            moneda,
            f"Gasto: {descripcion} - {monto} {moneda.upper()}", 
            "gasto"
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": f"Gasto registrado y descontado del saldo",
                "monto_original": monto,
                "moneda": moneda.upper(),
                "monto_usd_equivalente": result.get("monto_usd_equivalente", 0),
                "saldo_anterior_usd": result.get("saldo_anterior_usd", 0),
                "saldo_nuevo_usd": result.get("saldo_nuevo_usd", 0),
                "descripcion": descripcion
            }
        else:
            return result
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def check_for_monthly_money_update() -> dict:
    """
    Verifica si es día 10 del mes y pregunta si hay dinero nuevo.
    """
    try:
        today = datetime.datetime.now()
        if today.day == 10:
            return {
                "status": "success",
                "should_ask": True,
                "message": "Es día 10 del mes. ¿Tienes dinero nuevo este mes para añadir al saldo?"
            }
        else:
            return {
                "status": "success",
                "should_ask": False,
                "message": f"Hoy es día {today.day}. Solo pregunto por dinero nuevo los días 10."
            }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def add_monthly_money(monto: float, moneda: str, descripcion: Optional[str] = None) -> dict:
    """
    Añade dinero nuevo del mes al saldo actual en la moneda especificada.
    """
    try:
        # Normalizar moneda
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        
        desc = descripcion or f"Dinero nuevo del mes - {monto} {moneda.upper()}"
        
        result = add_to_current_balance(monto, moneda, desc, "dinero_nuevo_mes")
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": f"Dinero nuevo del mes añadido al saldo",
                "monto_original": monto,
                "moneda": moneda.upper(),
                "monto_usd_equivalente": result.get("monto_usd_equivalente", 0),
                "saldo_anterior_usd": result.get("saldo_anterior_usd", 0),
                "saldo_nuevo_usd": result.get("saldo_nuevo_usd", 0)
            }
        else:
            return result
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def add_money_to_balance(monto: float, moneda: str, descripcion: Optional[str] = None) -> dict:
    """
    Añade dinero al saldo base en la moneda especificada.
    """
    try:
        # Normalizar moneda
        if moneda.lower() in ['pesos', 'peso', 'ars']:
            moneda = 'ARS'
        
        desc = descripcion or f"Dinero añadido al saldo - {monto} {moneda.upper()}"
        
        result = add_to_current_balance(monto, moneda, desc, "dinero_añadido")
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": f"Dinero añadido exitosamente al saldo base",
                "monto_original": monto,
                "moneda": moneda.upper(),
                "monto_usd_equivalente": result.get("monto_usd_equivalente", 0),
                "descripcion": desc,
                "saldo_actualizado": "Usa get_total_money() para ver el saldo completo"
            }
        else:
            return result
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# ---------------- FUNCIÓN DE RESUMEN TOTAL ---------------- #

def get_total_money() -> dict:
    """
    Calcula el saldo base total mostrando detalle por moneda original y convertido a ARS y USD.
    SALDO BASE = dinero que tienes trabajando + dinero disponible
    """
    try:
        # Obtener préstamos activos
        loans_result = list_loans("activo")
        if loans_result["status"] == "error":
            return loans_result
        
        # Obtener saldo actual detallado por moneda
        balance_result = get_current_balance()
        if balance_result["status"] == "error":
            return balance_result
        
        total_prestado_usd = loans_result.get("totales_convertidos", {}).get("total_prestado_usd", 0)
        saldos_por_moneda = balance_result.get("saldos_por_moneda", [])
        
        # Obtener fecha y cotización actual para ARS
        fecha_hoy = datetime.datetime.now().date().isoformat()
        cotizacion_result = get_current_exchange_rate_from_api("ARS", fecha_hoy)
        
        if cotizacion_result["status"] == "success":
            ars_por_usd = cotizacion_result["cotizacion_original"]  # ej: 1362.33 ARS = 1 USD
            usd_por_ars = cotizacion_result["cotizacion_usd"]       # ej: 1 ARS = 0.000734 USD
            
            # Convertir todo el saldo disponible a ambas monedas
            saldo_total_usd = 0
            saldo_total_ars = 0
            detalle_saldos = []
            
            for saldo in saldos_por_moneda:
                moneda = saldo["moneda"]
                monto = saldo["monto"]
                
                if moneda == "USD":
                    monto_usd = monto
                    monto_ars = monto * ars_por_usd
                elif moneda == "ARS":
                    monto_usd = monto * usd_por_ars
                    monto_ars = monto
                else:
                    # Convertir otras monedas
                    conversion = convert_to_usd(monto, moneda)
                    monto_usd = conversion["monto_usd"] if conversion["status"] == "success" else 0
                    monto_ars = monto_usd * ars_por_usd
                
                saldo_total_usd += monto_usd
                saldo_total_ars += monto_ars
                
                detalle_saldos.append({
                    "moneda_original": moneda,
                    "monto_original": monto,
                    "equivalente_ars": round(monto_ars, 2),
                    "equivalente_usd": round(monto_usd, 2)
                })
            
            # Convertir préstamos a ARS
            total_prestado_ars = total_prestado_usd * ars_por_usd
            
            # Totales generales
            saldo_base_total_usd = total_prestado_usd + saldo_total_usd
            saldo_base_total_ars = total_prestado_ars + saldo_total_ars
            
            return {
                "status": "success",
                "fecha_cotizacion": fecha_hoy,
                "cotizacion": {
                    "ars_por_usd": ars_por_usd,
                    "usd_por_ars": round(usd_por_ars, 6),
                    "detalle": f"1 USD = {ars_por_usd:,.2f} ARS"
                },
                
                # RESUMEN EN PESOS (PRINCIPAL)
                "resumen_ars": {
                    "dinero_prestado_ars": round(total_prestado_ars, 2),
                    "saldo_disponible_ars": round(saldo_total_ars, 2),
                    "saldo_total_ars": round(saldo_base_total_ars, 2),
                    "formato": f"${saldo_base_total_ars:,.0f} ARS"
                },
                
                # RESUMEN EN DÓLARES (SECUNDARIO)
                "resumen_usd": {
                    "dinero_prestado_usd": total_prestado_usd,
                    "saldo_disponible_usd": round(saldo_total_usd, 2),
                    "saldo_total_usd": round(saldo_base_total_usd, 2),
                    "formato": f"${saldo_base_total_usd:,.2f} USD"
                },
                
                # DETALLE POR MONEDA ORIGINAL
                "detalle_saldos_por_moneda": detalle_saldos,
                "cantidad_prestamos_activos": loans_result.get("cantidad_prestamos", 0),
                
                # EXPLICACIÓN
                "explicacion": {
                    "dinero_prestado": f"${total_prestado_ars:,.0f} ARS (${total_prestado_usd:,.2f} USD) prestado trabajando",
                    "saldo_disponible": f"${saldo_total_ars:,.0f} ARS (${saldo_total_usd:,.2f} USD) disponible",
                    "total": f"${saldo_base_total_ars:,.0f} ARS (${saldo_base_total_usd:,.2f} USD) saldo base total",
                    "nota": "Cotización automática del día actual, sin intereses pendientes"
                }
            }
        else:
            # Si falla la cotización, mostrar solo en USD
            saldo_total_usd = sum([s["monto"] for s in saldos_por_moneda if s["moneda"] == "USD"])
            saldo_base_total_usd = total_prestado_usd + saldo_total_usd
            
            return {
                "status": "warning",
                "message": "Cotización ARS no disponible, mostrando solo en USD",
                "fecha": fecha_hoy,
                "resumen_usd": {
                    "dinero_prestado_usd": total_prestado_usd,
                    "saldo_disponible_usd": saldo_total_usd,
                    "saldo_total_usd": round(saldo_base_total_usd, 2)
                },
                "detalle_saldos_por_moneda": saldos_por_moneda,
                "sugerencia": "Para ver en pesos, verifica la conexión a internet para obtener cotización automática"
            }
        
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_balance_history(limit: int = 20) -> dict:
    """
    Obtiene el historial de cambios del saldo.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute(
            """
            SELECT * FROM historial_saldo 
            ORDER BY fecha_operacion DESC 
            LIMIT %s;
            """,
            (limit,)
        )
        
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convertir decimales y fechas
        for record in history:
            for k, v in record.items():
                if isinstance(v, decimal.Decimal):
                    record[k] = float(v)
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    record[k] = v.isoformat()
        
        return {
            "status": "success",
            "historial": history,
            "cantidad_registros": len(history)
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


# ---------------- AGENTE ---------------- #

root_agent = Agent(
    name="finance_agent",
    model="gemini-2.0-flash",
    description="Agente avanzado para gestión financiera personal: préstamos con cotización del día actual, cálculo corregido de intermediarios, saldo base sin intereses automáticos.",
    instruction=(
        "Eres un asistente financiero personal experto con las siguientes reglas CORREGIDAS:\n\n"
        "📊 PRÉSTAMOS (CÁLCULO CORREGIDO):\n"
        "- SIEMPRE pedir fecha específica del préstamo (formato YYYY-MM-DD)\n"
        "- Cotización: usar fecha ACTUAL (hoy), NO la fecha del préstamo\n"
        "- 'pesos' = 'ARS' (Argentina) automáticamente, NO preguntar\n"
        "- INTERMEDIARIO CORREGIDO: si 10% interés y 5% intermediario:\n"
        "  → Tu ganancia neta = 5% (no 10% - 5% de 10%)\n"
        "  → Intermediario se queda con 5% del monto total\n"
        "- Ejemplo: $5000 al 10% con 5% intermediario:\n"
        "  → Ganancia total: $500 (10%)\n"
        "  → Tu ganancia neta: $250 (5%)\n"
        "  → Intermediario: $250 (5% del monto)\n\n"
        "💰 SALDO BASE MULTIMONEDA (CORREGIDO):\n"
        "- Al guardar dinero: mantener moneda original (ARS si es pesos, USD si es dólares)\n"
        "- Al consultar saldo: convertir TODO a ARS y USD automáticamente\n"
        "- Mostrar detalle: qué tienes en cada moneda + totales convertidos\n"
        "- Ejemplo guardado: '$100,000 ARS' + '$500 USD' por separado\n"
        "- Ejemplo consulta: 'Tienes $100,000 ARS + $681,165 ARS (de $500 USD) = $781,165 ARS total'\n"
        "- Cotización automática del día (NO preguntar fecha)\n\n"
        "🌐 COTIZACIÓN AUTOMÁTICA:\n"
        "- Usar cotización del DÍA ACTUAL siempre\n"
        "- 'pesos' → 'ARS' automáticamente\n"
        "- Guardar cotización del momento en cada préstamo\n"
        "- Si falla API, usar tasas guardadas en BD\n\n"
        "📈 SALDO BASE TOTAL (AUTOMÁTICO EN ARS Y USD):\n"
        "- Cuando pregunten 'cuánta plata tengo', mostrar AUTOMÁTICAMENTE:\n"
        "  • PRIMERO EN PESOS: dinero prestado + disponible en ARS\n"
        "  • LUEGO EN DÓLARES: con cotización del día actual\n"
        "  • Obtener fecha y cotización automáticamente (NO preguntar)\n"
        "  • Ejemplo: '$500,000 ARS (prestado) + $100,000 ARS (disponible) = $600,000 ARS'\n"
        "  • Debajo: '$625 USD (prestado) + $125 USD (disponible) = $750 USD (1 USD = 800 ARS)'\n\n"
        "🔚 FINALIZAR PRÉSTAMOS:\n"
        "- Cuando termine un préstamo, devolver solo las ganancias REALES cobradas\n"
        "- El dinero prestado original NO se suma porque ya estaba en el saldo base\n\n"
        "� FLUJO PARA PRÉSTAMOS (CORREGIDO):\n"
        "1. Preguntar: monto, moneda ('pesos' = ARS), persona, fecha específica\n"
        "2. Preguntar: % interés total, si hay intermediario, % intermediario\n"
        "3. Obtener cotización del DÍA ACTUAL (no de la fecha del préstamo)\n"
        "4. Calcular: ganancia neta = (% interés - % intermediario) × monto\n"
        "5. Mostrar desglose completo con cotización actual\n\n"
        "EJEMPLO COMPLETO CORREGIDO:\n"
        "Préstamo: 400,000 pesos al 10% con 5% intermediario el 2025-09-01\n"
        "- Moneda: ARS (automático)\n"
        "- Cotización del 2025-09-05 (hoy): 1 ARS = 0.00125 USD\n"
        "- Monto en USD: 400,000 × 0.00125 = $500 USD\n"
        "- % neto tuyo: 10% - 5% = 5%\n"
        "- Tu ganancia: 400,000 × 5% = 20,000 ARS = $25 USD\n"
        "- Intermediario: 400,000 × 5% = 20,000 ARS = $25 USD\n\n"
        "IMPORTANTE: NO incluir intereses en saldo base hasta que se cobren manualmente."
    ),
    tools=[
        # Herramientas originales
        add_transaction, get_balance, list_transactions, get_today_date,
        # Tasas de cambio y cotizaciones automáticas
        update_exchange_rate, get_exchange_rate, convert_to_usd,
        get_current_exchange_rate_from_api, save_exchange_rate_from_api,
        # Préstamos
        add_loan, list_loans, finish_loan,
        # Saldo actual
        get_current_balance, add_to_current_balance, subtract_from_current_balance,
        add_expense, check_for_monthly_money_update, add_monthly_money, add_money_to_balance,
        # Resumen y historial
        get_total_money, get_balance_history
    ],
)