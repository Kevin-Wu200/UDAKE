"""
进度详情模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ProgressStage(str, Enum):
    """进度阶段"""
    DATA_LOADING = "data_loading"
    DATA_VALIDATION = "data_validation"
    VARIOGRAM_FITTING = "variogram_fitting"
    INTERPOLATION = "interpolation"
    CROSS_VALIDATION = "cross_validation"
    RESULT_GENERATION = "result_generation"
    EXPORTING = "exporting"
    COMPLETED = "completed"

class StageInfo(BaseModel):
    """阶段信息"""
    stage: ProgressStage
    stage_name: str = Field(..., description="阶段名称")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="阶段进度百分比")
    status: str = Field(default="pending", description="阶段状态：pending/running/completed/failed")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    duration: Optional[float] = Field(default=None, description="持续时间（秒）")
    message: Optional[str] = Field(default=None, description="阶段消息")

class BlockProgress(BaseModel):
    """分块处理进度"""
    current_block: int = Field(..., description="当前处理的数据块")
    total_blocks: int = Field(..., description="总数据块数量")
    processed_blocks: int = Field(..., description="已处理的数据块数量")
    processing_speed: Optional[float] = Field(default=None, description="处理速度（块/秒）")
    estimated_remaining_time: Optional[float] = Field(default=None, description="预计剩余时间（秒）")

class ProgressDetail(BaseModel):
    """进度详情"""
    task_id: str
    current_stage: Optional[ProgressStage] = Field(default=None, description="当前阶段")
    overall_progress: float = Field(default=0.0, ge=0.0, le=100.0, description="总体进度百分比")
    stages: List[StageInfo] = Field(default_factory=list, description="所有阶段信息")
    block_progress: Optional[BlockProgress] = Field(default=None, description="分块处理进度")
    estimated_total_time: Optional[float] = Field(default=None, description="预计总时间（秒）")
    estimated_remaining_time: Optional[float] = Field(default=None, description="预计剩余时间（秒）")
    elapsed_time: Optional[float] = Field(default=None, description="已用时间（秒）")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class ProgressVisualization(BaseModel):
    """进度可视化数据"""
    task_id: str
    progress_bar: Dict[str, float] = Field(default_factory=dict, description="进度条数据")
    circular_progress: float = Field(default=0.0, ge=0.0, le=100.0, description="环形进度")
    stage_flow: List[Dict[str, Any]] = Field(default_factory=list, description="阶段流程图")
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="时间线")