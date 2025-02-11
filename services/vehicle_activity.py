import asyncio
from datetime import *
from sqlalchemy import text
from backend.reportesDB import get_db
from backend.session import get_db_session
import pandas as pd
from models.models import ReporteActividad, Vehiculo

async def most_active_vehicle(vehicle, start_date, end_date):
    main_db = next(get_db())
    db_name = vehicle.get("bd")
    vhc_alias = vehicle.get("vhc_alias")
    vhc_imei = vehicle.get("vhc_imei")

    if not db_name:
        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": "Base de datos no especificada",
            "dias_laborables": [],
            "dias_no_laborables": []
        }

    # Validar existencia del vehículo
    existing_vehicle = main_db.query(Vehiculo).filter(Vehiculo.vhc_imei == vhc_imei).first()

    if not existing_vehicle:
        return {
            "vhc_alias": vhc_alias,
            "vhc_imei": vhc_imei,
            "db_name": db_name,
            "error": "Vehículo no encontrado",
            "dias_laborables": [],
            "dias_no_laborables": []
        }

    start_date_dt = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
    end_date_dt = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')

    start_date = start_date_dt.date()
    end_date = end_date_dt.date()

    registros_actividad = main_db.query(ReporteActividad).filter(
        ReporteActividad.vhc_id == existing_vehicle.vhc_id,
        ReporteActividad.fecha.between(start_date, end_date)
    ).all()

    registros_por_dia = {registro.fecha: registro for registro in registros_actividad}
    all_dates = pd.date_range(start=start_date_dt, end=end_date_dt).date
    dias_faltantes = [dia for dia in all_dates if dia not in registros_por_dia]
    today = datetime.now().date()

    combined_activity = []
    calculated_activity = []

    if dias_faltantes:
        session_factory = get_db_session(db_name)
        db_session = session_factory()

        try:
            query = text("""SELECT gpsdatetime, event, iec, speed, odometer
                             FROM rds_avl_state
                             WHERE gpsdatetime BETWEEN :start_date AND :end_date;""")
            result = await asyncio.to_thread(
                db_session.execute,
                query,
                {"start_date": start_date_dt, "end_date": end_date_dt}
            )
            rows = result.mappings().all()

            if not rows:
                for dia in dias_faltantes:
                    if dia == today:
                        continue  # No guardar el día actual en la base de datos

                    errorReporteActividad = ReporteActividad(
                        vhc_id=existing_vehicle.vhc_id,
                        fecha=dia,
                        horas_actividad=0.0,
                        distancia=0.0
                    )
                    main_db.add(errorReporteActividad)
                    main_db.commit()

                return {
                    "vhc_alias": vhc_alias,
                    "vhc_imei": vhc_imei,
                    "db_name": db_name,
                    "error": "No se encontraron datos en la base de datos específica",
                    "dias_laborables": [],
                    "dias_no_laborables": []
                }

            df = await asyncio.to_thread(pd.DataFrame, [dict(row) for row in rows])

            df["gpsdatetime"] = pd.to_datetime(df["gpsdatetime"])
            df["date"] = df["gpsdatetime"].dt.date

            df = df[df["date"].isin(dias_faltantes)]

            df = df.copy()  # Asegura que df es una copia independiente
            df.loc[:, "activity_change"] = (
                ((df["speed"] > 0) & (df["speed"].shift() == 0) & (df["iec"] == 1)).astype(int) - 
                ((df["speed"] == 0) & (df["speed"].shift() > 0)).astype(int)
            )


            activity_periods = df[df["activity_change"] != 0].copy()
            activity_periods["interval"] = activity_periods["gpsdatetime"].diff().shift(-1)
            activity_intervals = activity_periods[activity_periods["activity_change"] == 1]

            for date, group in activity_intervals.groupby("date"):
                group = group.dropna(subset=["interval"])

                activity_time_seconds = group["interval"].dt.total_seconds().sum()
                distance = group["odometer"].max() - group["odometer"].min() if not group["odometer"].isna().all() else 0
                hours_activity = activity_time_seconds / 3600

                if date == today:
                    calculated_activity.append({
                        "date": date.isoformat(),
                        "activity_hours": f"{hours_activity:.2f}",
                        "total_distance": float(distance),
                    })
                else:
                    calculated_activity.append({
                        "date": date.isoformat(),
                        "activity_hours": f"{hours_activity:.2f}",
                        "total_distance": float(distance),
                    })
                    newReporteActividad = ReporteActividad(
                        vhc_id=existing_vehicle.vhc_id,
                        fecha=date,
                        horas_actividad=hours_activity,
                        distancia=distance
                    )
                    main_db.add(newReporteActividad)
                    main_db.commit()

        finally:
            await asyncio.to_thread(db_session.close)

    calculated_activity_dict = {a["date"]: a for a in calculated_activity}

    for dia in all_dates:
        if dia in registros_por_dia:
            registro = registros_por_dia[dia]
            combined_activity.append({
                "date": dia.isoformat(),
                "activity_hours": f"{registro.horas_actividad:.2f}",
                "total_distance": registro.distancia
            })
        elif dia.isoformat() in calculated_activity_dict:
            combined_activity.append(calculated_activity_dict[dia.isoformat()])
        else:
            combined_activity.append({
                "date": dia.isoformat(),
                "activity_hours": "0.00",
                "total_distance": 0.0
            })
            emptyReporteActividad = ReporteActividad(
                        vhc_id=existing_vehicle.vhc_id,
                        fecha=dia,
                        horas_actividad=0.0,
                        distancia=0.0
                    )
            main_db.add(emptyReporteActividad)
            main_db.commit()

    laborable_days = [day for day in combined_activity if pd.Timestamp(day["date"]).weekday() < 5]
    non_laborable_days = [day for day in combined_activity if pd.Timestamp(day["date"]).weekday() >= 5]

    return {
        "vhc_alias": vhc_alias,
        "vhc_imei": vhc_imei,
        "db_name": db_name,
        "total_activity_hours": f"{sum(float(a['activity_hours']) for a in combined_activity):.2f}",
        "total_distance": sum(a["total_distance"] for a in combined_activity),
        "dias_laborables": laborable_days,
        "dias_no_laborables": non_laborable_days
    }



