"""
参数批量应用接口
"""
from fastapi import APIRouter, HTTPException
from ..schemas.批量处理模型 import (
    ParameterTemplate, ParameterTemplateListResponse,
    ParameterTemplateSaveRequest, ParameterBatchApplyRequest,
    ParameterValidationResult
)
from ..schemas.插值参数模型 import KrigingParameters
from ..services.参数模板服务 import ParameterTemplateService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
parameter_template_service = ParameterTemplateService()


@router.post("/api/parameter-templates", response_model=ParameterTemplate)
async def save_parameter_template(request: ParameterTemplateSaveRequest):
    """
    保存参数模板

    参数说明：
    - name: 模板名称
    - description: 模板描述（可选）
    - industry: 行业类型（可选）
    - parameters: 克里金参数
    """
    try:
        template = parameter_template_service.save_template(request)

        logger.info(f"参数模板已保存: {template.template_id}, 名称: {template.name}")

        return template

    except Exception as e:
        logger.error(f"保存参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存模板失败: {str(e)}")


@router.get("/api/parameter-templates", response_model=ParameterTemplateListResponse)
async def get_all_parameter_templates():
    """
    获取所有参数模板

    返回所有已保存的参数模板列表
    """
    try:
        response = parameter_template_service.get_all_templates()

        return response

    except Exception as e:
        logger.error(f"获取所有参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板失败: {str(e)}")


@router.get("/api/parameter-templates/defaults")
async def get_default_templates():
    """
    获取默认参数模板列表

    返回系统预设的参数模板
    """
    try:
        default_templates = [
            {
                "name": "环境监测模板",
                "description": "适用于环境监测数据",
                "industry": "environment"
            },
            {
                "name": "农业采样模板",
                "description": "适用于农业土壤采样数据",
                "industry": "agriculture"
            },
            {
                "name": "地质勘探模板",
                "description": "适用于地质勘探数据",
                "industry": "geology"
            },
            {
                "name": "水文监测模板",
                "description": "适用于水文监测数据",
                "industry": "hydrology"
            },
            {
                "name": "气象监测模板",
                "description": "适用于气象监测数据",
                "industry": "meteorology"
            }
        ]

        return {
            "default_templates": default_templates,
            "total": len(default_templates)
        }

    except Exception as e:
        logger.error(f"获取默认参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取默认模板失败: {str(e)}")


@router.get("/api/parameter-templates/{template_id}", response_model=ParameterTemplate)
async def get_parameter_template(template_id: str):
    """
    获取指定参数模板

    参数说明：
    - template_id: 模板ID
    """
    try:
        template = parameter_template_service.load_template(template_id)

        if not template:
            raise HTTPException(status_code=404, detail="参数模板不存在")

        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板失败: {str(e)}")


@router.delete("/api/parameter-templates/{template_id}")
async def delete_parameter_template(template_id: str):
    """
    删除参数模板

    参数说明：
    - template_id: 模板ID
    """
    try:
        success = parameter_template_service.delete_template(template_id)

        if not success:
            raise HTTPException(status_code=404, detail="参数模板不存在")

        logger.info(f"参数模板已删除: {template_id}")

        return {
            "status": "success",
            "message": "参数模板已删除"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除模板失败: {str(e)}")


@router.post("/api/parameter-templates/{template_id}/apply")
async def apply_template_to_datasets(
    template_id: str,
    request: ParameterBatchApplyRequest
):
    """
    将参数模板应用到多个数据集

    参数说明：
    - template_id: 模板ID
    - data_ids: 数据ID列表
    - auto_adjust: 是否根据数据自动调整参数
    """
    try:
        # 加载模板
        template = parameter_template_service.load_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="参数模板不存在")

        # 验证参数
        validation = parameter_template_service.validate_parameters(template.parameters)
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"参数验证失败: {', '.join(validation.errors)}"
            )

        # 应用参数到数据集
        applied_parameters = parameter_template_service.apply_parameters_to_datasets(
            parameters=template.parameters,
            individual_parameters=request.individual_parameters,
            data_ids=request.data_ids,
            auto_adjust=request.auto_adjust
        )

        logger.info(f"参数模板已应用到 {len(request.data_ids)} 个数据集")

        return {
            "status": "success",
            "template_id": template_id,
            "template_name": template.name,
            "applied_parameters": {
                data_id: params.model_dump()
                for data_id, params in applied_parameters.items()
            },
            "validation": validation.model_dump()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用参数模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"应用模板失败: {str(e)}")


@router.post("/api/parameters/validate", response_model=ParameterValidationResult)
async def validate_parameters(parameters: KrigingParameters):
    """
    验证参数合理性

    参数说明：
    - parameters: 克里金参数
    """
    try:
        validation = parameter_template_service.validate_parameters(parameters)

        return validation

    except Exception as e:
        logger.error(f"验证参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"验证参数失败: {str(e)}")


@router.post("/api/parameters/apply")
async def apply_parameters_to_datasets(request: ParameterBatchApplyRequest):
    """
    将参数应用到多个数据集

    参数说明：
    - parameters: 统一参数（可选）
    - individual_parameters: 单独参数字典（可选）
    - data_ids: 数据ID列表
    - auto_adjust: 是否根据数据自动调整参数
    """
    try:
        # 验证至少提供了统一参数或单独参数
        if not request.parameters and not request.individual_parameters:
            raise HTTPException(
                status_code=400,
                detail="必须提供统一参数或单独参数"
            )

        # 验证统一参数
        if request.parameters:
            validation = parameter_template_service.validate_parameters(request.parameters)
            if not validation.is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"统一参数验证失败: {', '.join(validation.errors)}"
                )

        # 应用参数到数据集
        applied_parameters = parameter_template_service.apply_parameters_to_datasets(
            parameters=request.parameters,
            individual_parameters=request.individual_parameters,
            data_ids=request.data_ids,
            auto_adjust=request.auto_adjust
        )

        logger.info(f"参数已应用到 {len(request.data_ids)} 个数据集")

        return {
            "status": "success",
            "applied_parameters": {
                data_id: params.model_dump()
                for data_id, params in applied_parameters.items()
            },
            "total_datasets": len(request.data_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"应用参数失败: {str(e)}")


@router.post("/api/parameters/auto-adjust")
async def auto_adjust_parameters(parameters: KrigingParameters, data_id: str):
    """
    根据数据自动调整参数

    参数说明：
    - parameters: 克里金参数
    - data_id: 数据ID
    """
    try:
        adjusted_parameters = parameter_template_service.auto_adjust_parameters(
            parameters,
            data_id
        )

        return {
            "status": "success",
            "original_parameters": parameters.model_dump(),
            "adjusted_parameters": adjusted_parameters.model_dump(),
            "data_id": data_id
        }

    except Exception as e:
        logger.error(f"自动调整参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"自动调整参数失败: {str(e)}")