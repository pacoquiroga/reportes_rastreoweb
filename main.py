from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import company_router, tipo_vehiculo, most_active_vehicle

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

app.include_router(company_router.router, tags=["company"])
app.include_router(tipo_vehiculo.router, tags=["tipo_vehiculo"])
app.include_router(most_active_vehicle.router, tags=["most_active_vehicle"])
