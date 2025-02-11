from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.reportesDB import get_db
from backend.session import get_db_session
import pandas as pd

from models.models import Vehiculo
from services.company_service import get_company_vehicles, get_company_vehicles_type

router = APIRouter()

@router.post("/tipo_vehiculo")
def create_tipo_vehiculo(file: UploadFile = File(...), db: Session = Depends(lambda: get_db_session("rds_web")())):
    
    
    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel")
    
    try: 
        df = pd.read_excel(file.file)

        expected_columns = ["IMEI", "PLACA", "CLASE", "TIPO"]
        if not all(col in df.columns for col in expected_columns):
            raise HTTPException(status_code=400, detail="El archivo debe contener las columnas IMEI, PLACA, CLASE y TIPO")
        
        not_found_imeis = []

        for index, row in df.iterrows():
            imei = str(row["IMEI"]).strip()
            tipo = str(row["TIPO"]).strip()

            result = db.execute(
                text("""
                UPDATE rds_vts_vehicles
                SET vhc_tipo = :tipo
                WHERE vhc_imei = :imei
                """),
                {"tipo": tipo, "imei": imei}
            )

            if result.rowcount == 0:
                not_found_imeis.append(imei)

        db.commit()

        if not_found_imeis:
            return {"detail": "Algunos IMEIs no se encontraron.", "not_found_imeis": not_found_imeis}
        return {"detail": "Los datos se han actualizado correctamente"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")



@router.post("/cargar_vehiculos", response_model=None)
async def cargar_vehiculos(
    main_db: Session = Depends(get_db), 
    rds_db: Session = Depends(lambda: get_db_session("rds_web")()),):

    vehicle_data = await get_company_vehicles(39, rds_db)

    for vehicle in vehicle_data:
        new_vehicle = Vehiculo(
            vhc_imei=vehicle["vhc_imei"],
            vhc_bd=vehicle["bd"],
            vhc_alias=vehicle["vhc_alias"],
            vhc_tipo=vehicle["vhc_tipo"]
        )
        
        # Verifica si el vehículo ya existe (evita duplicados)
        existing_vehicle = main_db.query(Vehiculo).filter(Vehiculo.vhc_imei == new_vehicle.vhc_imei).first()
        if not existing_vehicle:
            # Añade el nuevo vehículo a la sesión
            main_db.add(new_vehicle)
        else:
            print(f"Vehículo con IMEI {new_vehicle.vhc_imei} ya existe en la base de datos.")

    # Confirma los cambios en la base de datos
    main_db.commit()
    
    return {"message": "Vehículos cargados correctamente."}