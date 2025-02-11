import asyncio
from datetime import *
import pandas as pd
from sqlalchemy import text
from backend.reportesDB import get_db
from backend.session import get_db_session
from models.models import ReporteEstacionamiento, Vehiculo
from math import radians, sin, cos, sqrt, atan2
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.sql import text
ImportError
from math import radians, sin, cos, sqrt, atan2


# Funciones auxiliares

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radio de la Tierra en kilómetros
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # Distancia en kilómetros


def agrupar_ubicaciones(resultados_por_dia, margen_tolerancia=0.1):
    agrupadas = []
    for _, ubicacion in resultados_por_dia.iterrows():
        encontrada = False
        for grupo in agrupadas:
            distancia = calcular_distancia(
                ubicacion["latitud_agrupada"],
                ubicacion["longitud_agrupada"],
                grupo["latitud_agrupada"],
                grupo["longitud_agrupada"],
            )
            if distancia <= margen_tolerancia:
                grupo["duracion"] += ubicacion["duracion"]
                if grupo["direccion"] != ubicacion["direccion"]:
                    grupo["direccion"] += f" / {ubicacion['direccion']}"
                encontrada = True
                break
        if not encontrada:
            agrupadas.append(ubicacion.to_dict())
    return agrupadas


# Función principal
async def ubicacion_flota(vehicle, start_date, end_date):
    main_db = next(get_db())
    db_name = vehicle.get("bd")
    vhc_alias = vehicle.get("vhc_alias")
    vhc_imei = vehicle.get("vhc_imei")
    db_session = None

    if not db_name:
        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": "Base de datos no especificada",
            "ubicacion_flota": []
        }

    existing_vehicle = main_db.query(Vehiculo).filter(Vehiculo.vhc_imei == vhc_imei).first()
    if not existing_vehicle:
        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": "Vehiculo no encontrado",
            "ubicacion_flota": []
        }

    vhc_id = existing_vehicle.vhc_id

    try:
        dias_rango = pd.date_range(start=start_date, end=end_date).date
        fecha_actual = date.today()

        registros_existentes = main_db.query(ReporteEstacionamiento.fecha).filter(
            ReporteEstacionamiento.vhc_id == vhc_id,
            ReporteEstacionamiento.fecha.between(start_date, end_date)
        ).distinct().all()

        dias_existentes = {registro.fecha for registro in registros_existentes}
        dias_faltantes = [dia for dia in dias_rango if dia not in dias_existentes]

        resultados_calculados = []
        if dias_faltantes:
            session_factory = get_db_session(db_name)
            db_session = session_factory()
            for dia in dias_faltantes:
                query = text("""
                    SELECT gpsdatetime, iec, speed, ROUND(latitude,4) as latitude, ROUND(longitude,4) as longitude, direccion
                    FROM rds_avl_state
                    WHERE gpsdatetime BETWEEN :start_date AND :end_date;
                """)
                print(f"Ejecutando consulta para el día: {dia}")  # Debugging
                result = await asyncio.to_thread(
                    db_session.execute,
                    query,
                    {"start_date": dia, "end_date": dia + timedelta(days=1)}
                )
                rows = result.mappings().all()

                if rows:
                    print(f"Registros obtenidos para el día {dia}: {len(rows)}")  # Debugging
                    df = await asyncio.to_thread(pd.DataFrame, rows)
                    df["gpsdatetime"] = pd.to_datetime(df["gpsdatetime"])
                    df["fecha"] = df["gpsdatetime"].dt.date
                    df["latitud_agrupada"] = df["latitude"].round(4)
                    df["longitud_agrupada"] = df["longitude"].round(4)

                    df["cambio_ubicacion"] = (
                        (df["direccion"] != df["direccion"].shift()) |
                        (df["fecha"] != df["fecha"].shift())
                    ).astype(int)
                    df["grupo"] = df["cambio_ubicacion"].cumsum()

                    resultados = (
                        df.groupby(["grupo", "fecha"])
                        .agg(
                            estacionamiento_inicio=("gpsdatetime", "min"),
                            estacionamiento_fin=("gpsdatetime", "max"),
                            cantidad_registros=("gpsdatetime", "count"),
                            latitud_agrupada=("latitud_agrupada", "first"),
                            longitud_agrupada=("longitud_agrupada", "first"),
                            direccion=("direccion", "first")
                        )
                        .reset_index(drop=False)
                    )

                    resultados["duracion"] = (resultados["estacionamiento_fin"] - resultados["estacionamiento_inicio"]).dt.total_seconds()
                    resultados = resultados[resultados["duracion"] > 600]

                    resultados_por_dia = (
                        resultados.groupby(["fecha", "direccion"])
                        .agg(
                            cantidad_registros=("cantidad_registros", "sum"),
                            duracion=("duracion", "sum"),
                            latitud_agrupada=("latitud_agrupada", "first"),
                            longitud_agrupada=("longitud_agrupada", "first")
                        )
                        .reset_index()
                    )

                    resultados_por_dia = (
                        resultados_por_dia.sort_values(by=["fecha", "duracion"], ascending=[True, False])
                        .groupby("fecha")
                        .head(6)
                    )

                    resultados_por_dia["duracion_horas"] = resultados_por_dia["duracion"] / 3600

                    resultados_por_dia = pd.DataFrame(agrupar_ubicaciones(resultados_por_dia, margen_tolerancia=0.1))

                    for _, row in resultados_por_dia.iterrows():
                        if row["fecha"] == fecha_actual:
                            resultados_calculados.append(row.to_dict())
                        else:
                            nuevo_reporte = ReporteEstacionamiento(
                                fecha=row["fecha"],
                                latitud=row["latitud_agrupada"],
                                longitud=row["longitud_agrupada"],
                                direccion=row["direccion"],
                                duracion_seg=int(row["duracion"]),
                                vhc_id=vhc_id
                            )
                            main_db.add(nuevo_reporte)
                            resultados_calculados.append(row.to_dict())
                else:
                    print(f"No se encontraron registros GPS para el día {dia}")  # Debugging
                    nuevo_reporte = ReporteEstacionamiento(
                        fecha=dia,
                        latitud=0.0,
                        longitud=0.0,
                        direccion="Sin registros de GPS",
                        duracion_seg=0,
                        vhc_id=vhc_id
                    )
                    main_db.add(nuevo_reporte)

            main_db.commit()

        registros_finales = main_db.query(ReporteEstacionamiento).filter(
            ReporteEstacionamiento.vhc_id == vhc_id,
            ReporteEstacionamiento.fecha.between(start_date, end_date)
        ).all()

        ubicacion_por_fecha = {}
        for registro in registros_finales:
            fecha_str = str(registro.fecha)
            if fecha_str not in ubicacion_por_fecha:
                ubicacion_por_fecha[fecha_str] = []

            ubicacion_por_fecha[fecha_str].append({
                "latitud_agrupada": registro.latitud,
                "longitud_agrupada": registro.longitud,
                "direccion": registro.direccion,
                "duracion": registro.duracion_seg,
                "duracion_horas": registro.duracion_seg / 3600
            })

        # for row in resultados_calculados:
        #     fecha_str = str(row["fecha"])
        #     if fecha_str not in ubicacion_por_fecha:
        #         ubicacion_por_fecha[fecha_str] = []
        #     if row not in ubicacion_por_fecha[fecha_str]:
        #         ubicacion_por_fecha[fecha_str].append({
        #             "latitud_agrupada": row["latitud_agrupada"],
        #             "longitud_agrupada": row["longitud_agrupada"],
        #             "direccion": row["direccion"],
        #             "duracion": row["duracion"],
        #             "duracion_horas": row["duracion_horas"]
        #         })

        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": None,
            "ubicacion_flota": ubicacion_por_fecha
        }

    except Exception as e:
        print(f"Error: {e}")  # Debugging
        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": str(e),
            "ubicacion_flota": []
        }
    finally:
        if db_session:
            print("Cerrando sesión de base de datos")  # Debugging
            await asyncio.to_thread(db_session.close)









# async def ubicacion_flota(vehicle, start_date, end_date):
#     main_db = next(get_db())
#     db_name = vehicle.get("bd")
#     vhc_alias = vehicle.get("vhc_alias")
#     vhc_imei = vehicle.get("vhc_imei")

#     if not db_name:
#         print(f"Base de datos no especificada para el vehículo {vhc_alias}. Saltando...")
#         return {
#             "vhc_alias": vhc_alias,
#             "vhc_imei": vhc_imei,
#             "db_name": db_name,
#             "error": "Base de datos no especificada",
#             "ubicacion_flota": []
#         }

#     # Validar existencia del vehículo
#     existing_vehicle = main_db.query(Vehiculo).filter(Vehiculo.vhc_imei == vhc_imei).first()

#     if not existing_vehicle:
#         return {
#             "vhc_alias": vhc_alias,
#             "vhc_imei": vhc_imei,
#             "db_name": db_name,
#             "error": "Vehiculo no encontrado",
#             "ubicacion_flota": []
#         }
    




#     print(f"Conectando a la base de datos: {db_name} para el vehículo {vhc_alias}")


#     session_factory = get_db_session(db_name)
#     db_session = session_factory()

#     try:
#         query = text("""
#             SELECT gpsdatetime, iec, speed, ROUND(latitude,4) as latitude , ROUND(longitude,4) as longitude , direccion
#             FROM rds_avl_state
#             WHERE gpsdatetime BETWEEN :start_date AND :end_date;
#         """)

#         result = await asyncio.to_thread(
#             db_session.execute,
#             query,
#             {"start_date": start_date, "end_date": end_date}
#         )

#         rows = result.mappings().all()
#         if not rows:
#             raise Exception(f"No se encontraron datos en la base de datos '{db_name}' para las fechas {start_date} a {end_date}")

#         df = await asyncio.to_thread(pd.DataFrame, rows)
#         print("Información cargada")

#         # Convertir gpsdatetime a formato datetime
#         df["gpsdatetime"] = pd.to_datetime(df["gpsdatetime"])
#         print("Columna gpsdatetime convertida a formato datetime.")

#         # Crear la columna fecha
#         df["fecha"] = df["gpsdatetime"].dt.date
#         print("Columna fecha creada exitosamente.")

#         # Validar columnas después de crear `fecha`
#         print(f"Columnas disponibles tras agregar fecha: {df.columns.tolist()}")

#         # Redondear latitud y longitud a 4 decimales
#         df["lat_agrupada"] = df["latitude"].round(4)
#         df["lon_agrupada"] = df["longitude"].round(4)

#         # Validar columnas después de redondear lat/lon
#         print(f"Columnas disponibles tras redondear: {df.columns.tolist()}")

#         # Detectar cambios de ubicación o dirección
#         df["cambio_ubicacion"] = (
#             (df["direccion"] != df["direccion"].shift()) |  # Cambio de dirección
#             (df["fecha"] != df["fecha"].shift())  # Cambio de día
#         ).astype(int)

#         # Crear un identificador de grupo basado en cambios de ubicación
#         df["grupo"] = df["cambio_ubicacion"].cumsum()

#         # Validar columnas tras identificar cambios de ubicación
#         print(f"Columnas disponibles tras crear grupo: {df.columns.tolist()}")

#         # Agrupar por cada lugar de estacionamiento en cada día
#         resultados = (
#             df.groupby(["grupo", "fecha"])
#             .agg(
#                 estacionamiento_inicio=("gpsdatetime", "min"),
#                 estacionamiento_fin=("gpsdatetime", "max"),
#                 cantidad_registros=("gpsdatetime", "count"),
#                 latitud_agrupada=("lat_agrupada", "first"),
#                 longitud_agrupada=("lon_agrupada", "first"),
#                 direccion=("direccion", "first")
#             )
#             .reset_index(drop=False)
#         )

#         # Validar columnas tras el primer agrupamiento
#         print(f"Columnas disponibles tras el primer agrupamiento: {resultados.columns.tolist()}")

#         # Calcular la duración del estacionamiento en segundos y convertir a horas/minutos
#         resultados["duracion"] = (resultados["estacionamiento_fin"] - resultados["estacionamiento_inicio"]).dt.total_seconds()
#         resultados["duracion_horas"] = resultados["duracion"] / 3600

#         # Filtrar para ver solo períodos de estacionamiento relevantes
#         resultados = resultados[resultados["duracion"] > 0]

#         # Agrupar por día y ubicación
#         resultados_por_dia = (
#             resultados.groupby(["fecha", "latitud_agrupada", "longitud_agrupada", "direccion"])
#             .agg(
#                 cantidad_registros=("cantidad_registros", "sum"),
#                 duracion=("duracion", "sum")
#             )
#             .reset_index()
#         )

#         # Validar columnas tras el segundo agrupamiento
#         print(f"Columnas disponibles tras el segundo agrupamiento: {resultados_por_dia.columns.tolist()}")

#         # Calcular duración en horas nuevamente
#         resultados_por_dia["duracion_horas"] = resultados_por_dia["duracion"] / 3600

#         # Ordenar por fecha y duración descendente
#         resultados_por_dia = resultados_por_dia.sort_values(by=["fecha", "duracion"], ascending=[True, False])

#         # Convertir los resultados a formato JSON
#         ubicacion_flota = resultados_por_dia.to_dict(orient="records")

#         # Agrupar por ubicación para sumar la duración total y registros
#         resultados_por_ubicacion = (
#             resultados_por_dia.groupby(["latitud_agrupada", "longitud_agrupada", "direccion"])
#             .agg(
#                 cantidad_registros=("cantidad_registros", "sum"),
#                 duracion=("duracion", "sum"),
#                 duracion_horas=("duracion_horas", "sum")
#             )
#             .reset_index()
#         )

#         # Ordenar por duración descendente
#         resultados_por_ubicacion = resultados_por_ubicacion.sort_values(by="duracion", ascending=False)

#         # Seleccionar los primeros 6 registros
#         top_ubicaciones = resultados_por_ubicacion.head(6)

#         # Convertir los resultados a formato JSON
#         ubicacion_flota = top_ubicaciones.to_dict(orient="records")

#         return {
#             "vhc_alias": vhc_alias,
#             "vhc_imei": vhc_imei,
#             "db_name": db_name,
#             "error": None,
#             "ubicacion_flota": ubicacion_flota
#         }


#     except Exception as e:
#         print(f"Error procesando la base de datos {db_name} para el vehículo {vhc_alias}: {e}")
#         return {
#             "vhc_alias": vhc_alias,
#             "vhc_imei": vhc_imei,	
#             "db_name": db_name,
#             "error": str(e),
#             "ubicacion_flota": []
#         }
#     finally:
#         await asyncio.to_thread(db_session.close)
#         print(f"Conexión cerrada para la base de datos {db_name}")
