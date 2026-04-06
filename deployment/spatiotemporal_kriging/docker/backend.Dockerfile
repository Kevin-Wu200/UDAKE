FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/services:/app/services/backend

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

ENV GDAL_CONFIG=/usr/bin/gdal-config \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    PIP_NO_BUILD_ISOLATION=1

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install "setuptools<81" wheel \
    && pip install numpy==1.24.3 scipy==1.11.4 "cython<3" extension-helpers \
    && pip install torch==2.0.1 \
    && pip install --no-build-isolation -r /app/requirements.txt

COPY services/backend /app/services/backend
COPY realtime_interpolation /app/realtime_interpolation
COPY multi_objective_optimization /app/multi_objective_optimization
COPY adaptive_sampling /app/adaptive_sampling
COPY deep_learning /app/deep_learning
COPY ai_extension /app/ai_extension
COPY uncertainty_dashboard /app/uncertainty_dashboard
COPY configs /app/configs
RUN mkdir -p /app/android/app/build/outputs/apk/release

WORKDIR /app/services/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "run.py"]
