"""GPU加速API接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.gpu_models import (
    GPUComputeResponse,
    GPUConfigUpdateRequest,
    KrigingPredictRequest,
    KrigingSemivariogramRequest,
    LinearSolveRequest,
    MatrixMultiplyRequest,
    MatrixSingleRequest,
    VectorBinaryRequest,
    VectorSingleRequest,
)
from ..services.gpu_service import gpu_service

router = APIRouter()


@router.get("/gpu/health")
async def gpu_health():
    return gpu_service.get_health()


@router.get("/gpu/status")
async def gpu_status():
    return gpu_service.get_status()


@router.get("/gpu/devices")
async def gpu_devices():
    return {"devices": gpu_service.list_devices()}


@router.put("/gpu/config")
async def update_gpu_config(req: GPUConfigUpdateRequest):
    config = gpu_service.update_config(
        enable_gpu=req.enable_gpu,
        auto_switch=req.auto_switch,
        min_size_for_gpu=req.min_size_for_gpu,
    )
    return {"config": config}


@router.get("/gpu/metrics")
async def gpu_metrics():
    return gpu_service.get_metrics()


@router.delete("/gpu/metrics")
async def clear_gpu_metrics():
    return gpu_service.clear_metrics()


@router.get("/gpu/tasks")
async def gpu_tasks(limit: int = 100):
    return {"tasks": gpu_service.list_tasks(limit=limit)}


@router.get("/gpu/tasks/{task_id}")
async def gpu_task_detail(task_id: str):
    task = gpu_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/gpu/compute/matrix/multiply", response_model=GPUComputeResponse)
async def matrix_multiply(req: MatrixMultiplyRequest):
    try:
        return gpu_service.matrix_multiply(req.matrix_a, req.matrix_b, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"矩阵乘法失败: {str(exc)}") from exc


@router.post("/gpu/compute/matrix/inverse", response_model=GPUComputeResponse)
async def matrix_inverse(req: MatrixSingleRequest):
    try:
        return gpu_service.matrix_inverse(req.matrix, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"矩阵求逆失败: {str(exc)}") from exc


@router.post("/gpu/compute/matrix/eigenvalues", response_model=GPUComputeResponse)
async def matrix_eigenvalues(req: MatrixSingleRequest):
    try:
        return gpu_service.matrix_eigenvalues(req.matrix, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"特征值计算失败: {str(exc)}") from exc


@router.post("/gpu/compute/matrix/cholesky", response_model=GPUComputeResponse)
async def matrix_cholesky(req: MatrixSingleRequest):
    try:
        return gpu_service.matrix_cholesky(req.matrix, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cholesky分解失败: {str(exc)}") from exc


@router.post("/gpu/compute/matrix/lu", response_model=GPUComputeResponse)
async def matrix_lu(req: MatrixSingleRequest):
    try:
        return gpu_service.matrix_lu(req.matrix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LU分解失败: {str(exc)}") from exc


@router.post("/gpu/compute/linear/solve", response_model=GPUComputeResponse)
async def linear_solve(req: LinearSolveRequest):
    try:
        return gpu_service.solve_linear(req.matrix_a, req.matrix_b, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"线性求解失败: {str(exc)}") from exc


@router.post("/gpu/compute/vector/dot", response_model=GPUComputeResponse)
async def vector_dot(req: VectorBinaryRequest):
    try:
        return gpu_service.vector_dot(req.vector_a, req.vector_b, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"向量点积失败: {str(exc)}") from exc


@router.post("/gpu/compute/vector/norm", response_model=GPUComputeResponse)
async def vector_norm(req: VectorSingleRequest):
    try:
        return gpu_service.vector_norm(req.vector, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"向量范数失败: {str(exc)}") from exc


@router.post("/gpu/compute/vector/sort", response_model=GPUComputeResponse)
async def vector_sort(req: VectorSingleRequest):
    try:
        return gpu_service.vector_sort(req.vector, prefer_gpu=req.prefer_gpu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"向量排序失败: {str(exc)}") from exc


@router.post("/gpu/kriging/semivariogram")
async def kriging_semivariogram(req: KrigingSemivariogramRequest):
    try:
        return gpu_service.kriging_semivariogram(
            req.points,
            req.values,
            bins=req.bins,
            max_range=req.max_range,
            prefer_gpu=req.prefer_gpu,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"变异函数计算失败: {str(exc)}") from exc


@router.post("/gpu/kriging/predict")
async def kriging_predict(req: KrigingPredictRequest):
    try:
        return gpu_service.kriging_predict(
            sample_points=req.sample_points,
            sample_values=req.sample_values,
            target_points=req.target_points,
            sill=req.sill,
            range_=req.range_,
            nugget=req.nugget,
            prefer_gpu=req.prefer_gpu,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"克里金预测失败: {str(exc)}") from exc
