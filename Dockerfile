# Usar una imagen ligera de Python
FROM python:3.11.3-slim

# Configuración del sistema
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    LANG=es_ES.UTF-8 \
    LANGUAGE=es_ES:es \
    LC_ALL=es_ES.UTF-8

# Instalar paquetes necesarios
RUN apt-get update && apt-get install -y locales tzdata && \
    echo "es_ES.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen es_ES.UTF-8 && \
    ln -sf /usr/share/zoneinfo/America/Guayaquil /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

# Establecer directorio de trabajo
WORKDIR /app

# Copiar solo los requisitos para caché eficiente
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto
EXPOSE 8008

# Ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
