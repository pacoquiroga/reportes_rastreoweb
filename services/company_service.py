import asyncio
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.ubicacion_flota import ubicacion_flota
from services.vehicle_activity import most_active_vehicle

async def get_company_vehicles_type(company_id: int, vhc_tipo, db: Session):
    try:
        query = """
        SELECT 
            rvc.id as compania, 
            rvc.cmp_name, 
            concat('rds_', rvv.vhc_name, '_db') as bd,
            rvv.vhc_alias,
            rvv.vhc_imei,
            rvv.vhc_tipo
        FROM rds_vts_companies rvc 
        INNER JOIN rds_vts_clients rvc2 ON rvc.id = rvc2.cmp_id
        INNER JOIN rds_vts_vehicles rvv ON rvv.user_id = rvc2.usr_id 
        WHERE rvc.id = :company_id AND rvv.vhc_tipo = :vhc_tipo
        """
        result = await asyncio.to_thread(
            db.execute,
            text(query),
            {"company_id": company_id, "vhc_tipo": vhc_tipo}
        )
        return [dict(row._mapping) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()  # Asegúrate de cerrar la conexión



async def get_company_vehicles(company_id: int, db: Session):
    try:
        query = """
        SELECT 
            rvc.id as compania, 
            rvc.cmp_name, 
            concat('rds_', rvv.vhc_name, '_db') as bd,
            rvv.vhc_alias,
            rvv.vhc_imei,
            rvv.vhc_tipo
        FROM rds_vts_companies rvc 
        INNER JOIN rds_vts_clients rvc2 ON rvc.id = rvc2.cmp_id
        INNER JOIN rds_vts_vehicles rvv ON rvv.user_id = rvc2.usr_id 
        WHERE rvc.id = :company_id
        
        """
        result = await asyncio.to_thread(
            db.execute,
            text(query),
            {"company_id": company_id}
        )        

        answer = [dict(row._mapping) for row in result]
        return answer
    finally:
        await asyncio.to_thread(db.close)

    

async def process_vehicle_data(vehicle_data, start_date, end_date, reporte):
    """
    Procesa una lista de vehículos de forma asincrónica y secuencial.
    """
    results = []

    for vehicle in vehicle_data:
        if reporte == "most_active_vehicle":
            result = await most_active_vehicle(vehicle, start_date, end_date)
        elif reporte == "ralenti":
            print("ralenti")
            continue
        elif reporte == "ubicacion_flota":
            result = await ubicacion_flota(vehicle, start_date, end_date)
        else:
            raise HTTPException(status_code=400, detail="El valor del reporte no es válido")

        results.append(result)

    if reporte == "most_active_vehicle":
        # Ordenar directamente por horas totales de actividad
        sorted_results = sorted(
            results, 
            key=lambda x: float(x.get("total_activity_hours", "0")), 
            reverse=True
        )
        return sorted_results

    return results


async def process_vehicles(vehicle_data, start_date, end_date, reporte):
    try:
        if not vehicle_data:
            raise HTTPException(status_code=400, detail="El payload debe incluir el campo 'data'")

        results = await process_vehicle_data(vehicle_data, start_date, end_date, reporte)

        # Si el reporte es "ubicacion_flota", construir una respuesta personalizada
        if reporte == "ubicacion_flota":
            return {
                "message": "Procesamiento completado con éxito",
                "tipo_reporte": reporte,
                "results": results
            }

        return {
            "message": "Procesamiento completado con éxito",
            "tipo_reporte": reporte,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
