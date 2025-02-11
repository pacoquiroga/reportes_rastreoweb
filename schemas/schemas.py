from pydantic import BaseModel
from typing import List, Optional
from datetime import date

# Esquema para ReporteEstacionamiento
class ReporteEstacionamientoBase(BaseModel):
    fecha: date
    latitud: float
    longitud: float
    direccion: str
    duracion_seg: int


class ReporteEstacionamientoCreate(ReporteEstacionamientoBase):
    pass


class ReporteEstacionamiento(ReporteEstacionamientoBase):
    estacionamiento_id: int

    class Config:
        orm_mode = True



# Esquema para ReporteActividad
class ReporteActividadBase(BaseModel):
    fecha: date
    horas_actividad: float
    distancia: int


class ReporteActividadCreate(ReporteActividadBase):
    pass


class ReporteActividad(ReporteActividadBase):
    reporte_actividad_id: int

    class Config:
        orm_mode = True




# Esquema para Vehiculo
class VehiculoBase(BaseModel):
    vhc_imei: str
    vhc_bd: str
    vhc_alias: str
    vhc_tipo: str


class VehiculoCreate(VehiculoBase):
    pass


class Vehiculo(VehiculoBase):
    vhc_id: int
    reportes_actividad: List[ReporteActividad] = []
    reportes_estacionamiento: List[ReporteEstacionamiento] = []

    class Config:
        orm_mode = True
