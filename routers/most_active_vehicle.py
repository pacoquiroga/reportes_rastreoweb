from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.session import get_db_session
from services.company_service import process_vehicles
from services.company_service import get_company_vehicles_type

router = APIRouter()

@router.get("/reportes/{company_id}")
async def get_vehicle_reports(company_id: int, vhc_tipo: str, start_date: str, end_date: str, reporte: str, db: Session = Depends(lambda: get_db_session("rds_web")())):
    try:
        vehicle_data = await get_company_vehicles_type(39, vhc_tipo, db)
        response = await process_vehicles(vehicle_data, start_date, end_date, reporte)

        return response

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
