from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import relationship
from backend.reportesDB import Base
 

# Modelo Vehiculo
class Vehiculo(Base):
    __tablename__ = "vehiculo"

    vhc_id = Column(Integer, primary_key=True, index=True)
    vhc_imei = Column(String(30), nullable=False)
    vhc_bd = Column(String(50), nullable=False)
    vhc_alias = Column(String(50), nullable=False)
    vhc_tipo = Column(String(45), nullable=False)

    reportes_actividad = relationship("ReporteActividad", back_populates="vehiculo")
    reportes_estacionamiento = relationship("ReporteEstacionamiento", back_populates="vehiculo")


# Modelo ReporteActividad
class ReporteActividad(Base):
    __tablename__ = "reporte_actividad"

    reporte_actividad_id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    horas_actividad = Column(Float, nullable=False)
    distancia = Column(Integer, nullable=False)

    vhc_id = Column(Integer, ForeignKey("vehiculo.vhc_id"))
    vehiculo = relationship("Vehiculo", back_populates="reportes_actividad")


# Modelo ReporteEstacionamiento
class ReporteEstacionamiento(Base):
    __tablename__ = "reporte_estacionamiento"

    estacionamiento_id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    direccion = Column(String(300), nullable=False)
    duracion_seg = Column(Integer, nullable=False)

    vhc_id = Column(Integer, ForeignKey("vehiculo.vhc_id"))
    vehiculo = relationship("Vehiculo", back_populates="reportes_estacionamiento")
