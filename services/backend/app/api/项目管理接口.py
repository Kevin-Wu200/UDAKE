"""
项目管理接口
提供项目的增删改查功能
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api", tags=["项目管理"])


class Project(BaseModel):
    """项目模型"""
    id: str
    name: str
    description: Optional[str] = None
    sampling_mode: str  # "free" 或 "region"
    created_at: datetime
    updated_at: datetime
    bounds: Optional[dict] = None
    point_count: int = 0


class ProjectCreate(BaseModel):
    """创建项目请求模型"""
    name: str
    description: Optional[str] = None
    sampling_mode: str = "free"
    bounds: Optional[dict] = None


class ProjectUpdate(BaseModel):
    """更新项目请求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    bounds: Optional[dict] = None


class ProjectListResponse(BaseModel):
    """项目列表响应模型"""
    projects: List[Project]
    total: int


class ProjectResponse(BaseModel):
    """项目响应模型"""
    success: bool
    project: Optional[Project] = None
    message: Optional[str] = None


# 内存存储项目数据（实际项目中应该使用数据库）
projects_db = {}
project_counter = 0


@router.get("/projects", response_model=ProjectListResponse)
async def get_projects():
    """
    获取所有项目列表

    返回所有已创建的项目
    """
    return ProjectListResponse(
        projects=list(projects_db.values()),
        total=len(projects_db)
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """
    获取指定项目详情

    Args:
        project_id: 项目ID

    Returns:
        项目详情
    """
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    return ProjectResponse(success=True, project=project)


@router.post("/projects", response_model=ProjectResponse)
async def create_project(project_data: ProjectCreate):
    """
    创建新项目

    Args:
        project_data: 项目数据

    Returns:
        创建的项目信息
    """
    global project_counter
    project_counter += 1
    project_id = f"project_{project_counter}"

    now = datetime.now()
    project = Project(
        id=project_id,
        name=project_data.name,
        description=project_data.description,
        sampling_mode=project_data.sampling_mode,
        created_at=now,
        updated_at=now,
        bounds=project_data.bounds,
        point_count=0
    )

    projects_db[project_id] = project

    return ProjectResponse(
        success=True,
        project=project,
        message=f"项目 '{project_data.name}' 创建成功"
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project_data: ProjectUpdate):
    """
    更新项目信息

    Args:
        project_id: 项目ID
        project_data: 更新的项目数据

    Returns:
        更新后的项目信息
    """
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    # 更新项目信息
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.bounds is not None:
        project.bounds = project_data.bounds

    project.updated_at = datetime.now()

    return ProjectResponse(
        success=True,
        project=project,
        message=f"项目 '{project.name}' 更新成功"
    )


@router.delete("/projects/{project_id}", response_model=ProjectResponse)
async def delete_project(project_id: str):
    """
    删除项目

    Args:
        project_id: 项目ID

    Returns:
        删除结果
    """
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    project_name = project.name
    del projects_db[project_id]

    return ProjectResponse(
        success=True,
        message=f"项目 '{project_name}' 删除成功"
    )