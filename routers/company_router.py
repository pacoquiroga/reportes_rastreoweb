from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.session import get_db_session
from services.company_service import get_company_vehicles_type

router = APIRouter()

@router.get("/consulta-compania/{company_id}")
def get_company_vehicles_db(company_id: int, vhc_tipo , db: Session = Depends(lambda: get_db_session("rds_web")())):
    data = get_company_vehicles_type(company_id, vhc_tipo, db)
    return {"data": data}



