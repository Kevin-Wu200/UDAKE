"""
空间风险报告生成测试
"""
import pytest
import numpy as np
import json
from pathlib import Path
import sys
from datetime import datetime
import tempfile

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from uncertainty_dashboard.空间风险报告生成 import SpatialRiskReporter


@pytest.fixture
def reporter():
    """创建空间风险报告生成器实例"""
    return SpatialRiskReporter()


@pytest.fixture
def sample_prediction():
    """创建示例预测数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 100


@pytest.fixture
def sample_variance():
    """创建示例方差数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 10


@pytest.fixture
def sample_risk_index():
    """创建示例风险指数数据"""
    np.random.seed(42)
    return np.random.rand(10, 10)


@pytest.fixture
def sample_uncertainty_levels():
    """创建示例不确定性等级数据"""
    return {
        "statistics": {
            "very_low": {"count": 20, "percentage": 20.0, "level_code": 0},
            "low": {"count": 30, "percentage": 30.0, "level_code": 1},
            "medium": {"count": 25, "percentage": 25.0, "level_code": 2},
            "high": {"count": 15, "percentage": 15.0, "level_code": 3},
            "very_high": {"count": 10, "percentage": 10.0, "level_code": 4}
        }
    }


@pytest.fixture
def sample_threshold_analysis():
    """创建示例阈值分析数据"""
    return {
        "thresholds": [20.0, 40.0, 60.0, 80.0],
        "recommended_threshold": 40.0,
        "analyses": {
            "threshold_20.0": {"confidence": 0.8, "exceeding_percentage": 30.0},
            "threshold_40.0": {"confidence": 0.9, "exceeding_percentage": 50.0},
            "threshold_60.0": {"confidence": 0.7, "exceeding_percentage": 70.0},
            "threshold_80.0": {"confidence": 0.6, "exceeding_percentage": 85.0}
        }
    }


@pytest.fixture
def sample_metadata():
    """创建示例元数据"""
    return {
        "task_name": "测试任务",
        "created_by": "测试用户",
        "sampling_method": "Kriging",
        "area_size": "100x100m"
    }


@pytest.fixture
def temp_output_dir():
    """创建临时输出目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestSpatialRiskReporter:
    """测试空间风险报告生成器"""

    def test_initialization(self, reporter):
        """测试类初始化"""
        assert reporter is not None
        assert hasattr(reporter, 'generate_risk_report')
        assert hasattr(reporter, 'save_report')

    def test_generate_risk_report(self, reporter, sample_prediction, sample_variance,
                                   sample_risk_index, sample_uncertainty_levels,
                                   sample_threshold_analysis, sample_metadata):
        """测试生成风险报告"""
        task_id = "test_task_001"
        report = reporter.generate_risk_report(
            task_id,
            sample_prediction,
            sample_variance,
            sample_risk_index,
            sample_uncertainty_levels,
            sample_threshold_analysis,
            sample_metadata
        )

        # 验证报告结构
        assert "report_id" in report
        assert "generated_at" in report
        assert "metadata" in report
        assert "executive_summary" in report
        assert "risk_assessment" in report
        assert "threshold_analysis" in report
        assert "spatial_statistics" in report
        assert "recommendations" in report

        # 验证报告ID
        assert report["report_id"] == task_id

        # 验证时间戳格式
        assert isinstance(report["generated_at"], str)
        datetime.fromisoformat(report["generated_at"])  # 验证可以解析

        # 验证元数据
        assert report["metadata"] == sample_metadata

    def test_generate_risk_report_without_metadata(self, reporter, sample_prediction,
                                                     sample_variance, sample_risk_index,
                                                     sample_uncertainty_levels,
                                                     sample_threshold_analysis):
        """测试不提供元数据"""
        task_id = "test_task_002"
        report = reporter.generate_risk_report(
            task_id,
            sample_prediction,
            sample_variance,
            sample_risk_index,
            sample_uncertainty_levels,
            sample_threshold_analysis
        )

        # 元数据应该是空字典
        assert report["metadata"] == {}

    def test_generate_executive_summary(self, reporter, sample_prediction,
                                         sample_variance, sample_risk_index):
        """测试生成执行摘要"""
        summary = reporter._generate_executive_summary(
            sample_prediction, sample_variance, sample_risk_index
        )

        # 验证返回结构
        assert "total_area" in summary
        assert "high_risk_percentage" in summary
        assert "average_uncertainty" in summary
        assert "prediction_range" in summary
        assert "overall_risk_level" in summary

        # 验证数据类型
        assert isinstance(summary["total_area"], int)
        assert isinstance(summary["high_risk_percentage"], float)
        assert isinstance(summary["average_uncertainty"], float)
        assert isinstance(summary["prediction_range"], dict)
        assert isinstance(summary["overall_risk_level"], str)

        # 验证预测范围
        pred_range = summary["prediction_range"]
        assert "min" in pred_range
        assert "max" in pred_range
        assert "mean" in pred_range
        assert pred_range["min"] <= pred_range["mean"] <= pred_range["max"]

        # 验证高风险百分比范围
        assert 0 <= summary["high_risk_percentage"] <= 100

        # 验证风险等级
        assert summary["overall_risk_level"] in ["高风险", "中等风险", "低风险"]

    def test_generate_executive_summary_risk_levels(self, reporter):
        """测试不同风险水平的执行摘要"""
        # 高风险
        risk_index_high = np.ones((10, 10)) * 0.8
        summary_high = reporter._generate_executive_summary(
            np.ones((10, 10)) * 50,
            np.ones((10, 10)) * 1,
            risk_index_high
        )
        assert summary_high["overall_risk_level"] == "高风险"

        # 低风险
        risk_index_low = np.ones((10, 10)) * 0.1
        summary_low = reporter._generate_executive_summary(
            np.ones((10, 10)) * 50,
            np.ones((10, 10)) * 1,
            risk_index_low
        )
        assert summary_low["overall_risk_level"] == "低风险"

    def test_generate_risk_assessment(self, reporter, sample_risk_index,
                                       sample_uncertainty_levels):
        """测试生成风险评估"""
        assessment = reporter._generate_risk_assessment(
            sample_risk_index, sample_uncertainty_levels
        )

        # 验证返回结构
        assert "risk_distribution" in assessment
        assert "uncertainty_levels" in assessment
        assert "risk_hotspots" in assessment

        # 验证风险分布
        risk_dist = assessment["risk_distribution"]
        assert "low" in risk_dist
        assert "medium" in risk_dist
        assert "high" in risk_dist

        # 验证不确定性等级
        assert assessment["uncertainty_levels"] == sample_uncertainty_levels

        # 验证风险热点
        hotspots = assessment["risk_hotspots"]
        assert isinstance(hotspots, list)
        assert len(hotspots) <= 5  # 默认top 5

        # 验证热点格式
        if len(hotspots) > 0:
            hotspot = hotspots[0]
            assert "x_index" in hotspot
            assert "y_index" in hotspot
            assert "risk_value" in hotspot

    def test_generate_spatial_statistics(self, reporter, sample_prediction,
                                          sample_variance):
        """测试生成空间统计信息"""
        stats = reporter._generate_spatial_statistics(sample_prediction, sample_variance)

        # 验证返回结构
        assert "prediction" in stats
        assert "variance" in stats

        # 验证预测统计
        pred_stats = stats["prediction"]
        assert "mean" in pred_stats
        assert "std" in pred_stats
        assert "min" in pred_stats
        assert "max" in pred_stats
        assert "median" in pred_stats
        assert "q25" in pred_stats
        assert "q75" in pred_stats

        # 验证方差统计
        var_stats = stats["variance"]
        assert "mean" in var_stats
        assert "std" in var_stats
        assert "min" in var_stats
        assert "max" in var_stats
        assert "median" in var_stats

        # 验证统计关系
        assert pred_stats["min"] <= pred_stats["median"] <= pred_stats["max"]
        assert pred_stats["q25"] <= pred_stats["median"] <= pred_stats["q75"]
        assert pred_stats["std"] >= 0

    def test_generate_recommendations_high_risk(self, reporter):
        """测试高风险建议"""
        # 创建高风险数据
        risk_index = np.ones((10, 10)) * 0.8  # 80%高风险
        uncertainty_levels = {
            "statistics": {
                "high": {"percentage": 20.0}
            }
        }
        threshold_analysis = {}

        recommendations = reporter._generate_recommendations(
            risk_index, uncertainty_levels, threshold_analysis
        )

        # 验证返回类型
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # 验证建议内容
        text = " ".join(recommendations)
        assert "增加采样" in text or "监测设备" in text

    def test_generate_recommendations_low_risk(self, reporter):
        """测试低风险建议"""
        # 创建低风险数据
        risk_index = np.ones((10, 10)) * 0.1  # 10%高风险
        uncertainty_levels = {
            "statistics": {
                "high": {"percentage": 5.0}
            }
        }
        threshold_analysis = {}

        recommendations = reporter._generate_recommendations(
            risk_index, uncertainty_levels, threshold_analysis
        )

        # 验证返回类型
        assert isinstance(recommendations, list)

        # 如果没有高风险，应该有默认建议
        if len(recommendations) == 1:
            assert "继续监测" in recommendations[0]

    def test_generate_recommendations_high_uncertainty(self, reporter):
        """测试高不确定性建议"""
        risk_index = np.ones((10, 10)) * 0.2
        uncertainty_levels = {
            "statistics": {
                "high": {"percentage": 20.0}  # 高不确定性
            }
        }
        threshold_analysis = {}

        recommendations = reporter._generate_recommendations(
            risk_index, uncertainty_levels, threshold_analysis
        )

        # 应该有关于不确定性的建议
        text = " ".join(recommendations)
        assert "不确定性" in text or "补充采样" in text

    def test_classify_overall_risk(self, reporter):
        """测试整体风险分类"""
        # 高风险
        assert reporter._classify_overall_risk(35) == "高风险"
        assert reporter._classify_overall_risk(30.1) == "高风险"

        # 中等风险
        assert reporter._classify_overall_risk(20) == "中等风险"
        assert reporter._classify_overall_risk(16) == "中等风险"

        # 低风险
        assert reporter._classify_overall_risk(10) == "低风险"
        assert reporter._classify_overall_risk(15) == "低风险"

    def test_classify_overall_risk_boundary(self, reporter):
        """测试边界值"""
        # 30是边界
        assert reporter._classify_overall_risk(30) == "高风险"
        assert reporter._classify_overall_risk(29.9) == "中等风险"

        # 15是边界
        assert reporter._classify_overall_risk(15) == "低风险"
        assert reporter._classify_overall_risk(15.1) == "中等风险"

    def test_identify_risk_hotspots(self, reporter):
        """测试识别风险热点"""
        # 创建已知热点
        risk_index = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.9, 0.5],
            [0.6, 0.7, 0.8]
        ])

        hotspots = reporter._identify_risk_hotspots(risk_index, top_n=3)

        # 验证返回类型
        assert isinstance(hotspots, list)
        assert len(hotspots) == 3

        # 验证热点是按风险值降序排列的
        risk_values = [h["risk_value"] for h in hotspots]
        assert risk_values == sorted(risk_values, reverse=True)

        # 验证最高风险点
        assert hotspots[0]["x_index"] == 1
        assert hotspots[0]["y_index"] == 1
        assert hotspots[0]["risk_value"] == 0.9

    def test_identify_risk_hotspots_custom_top_n(self, reporter):
        """测试自定义热点数量"""
        risk_index = np.random.rand(10, 10)

        for top_n in [1, 3, 5, 10]:
            hotspots = reporter._identify_risk_hotspots(risk_index, top_n=top_n)
            assert len(hotspots) == top_n

    def test_save_report(self, reporter, temp_output_dir):
        """测试保存报告"""
        report = {
            "report_id": "test_001",
            "generated_at": datetime.now().isoformat(),
            "data": "test data"
        }

        output_path = temp_output_dir / "test_report.json"
        reporter.save_report(report, output_path)

        # 验证文件存在
        assert output_path.exists()

        # 验证文件内容
        with open(output_path, 'r', encoding='utf-8') as f:
            saved_report = json.load(f)

        assert saved_report == report

    def test_save_report_creates_directory(self, reporter, temp_output_dir):
        """测试保存报告时创建目录"""
        report = {"test": "data"}
        output_path = temp_output_dir / "subdir" / "nested" / "report.json"

        reporter.save_report(report, output_path)

        # 验证文件和目录都存在
        assert output_path.exists()
        assert output_path.parent.exists()

    def test_save_report_chinese_characters(self, reporter, temp_output_dir):
        """测试保存包含中文的报告"""
        report = {
            "报告ID": "测试报告",
            "数据": "中文内容",
            "列表": ["项目一", "项目二"]
        }

        output_path = temp_output_dir / "chinese_report.json"
        reporter.save_report(report, output_path)

        # 验证文件可以正确读取
        with open(output_path, 'r', encoding='utf-8') as f:
            saved_report = json.load(f)

        assert saved_report == report

    def test_edge_case_empty_arrays(self, reporter):
        """测试空数组"""
        prediction = np.array([])
        variance = np.array([])
        risk_index = np.array([])
        uncertainty_levels = {"statistics": {}}
        threshold_analysis = {}

        with pytest.raises((ValueError, IndexError)):
            reporter._generate_executive_summary(prediction, variance, risk_index)

    def test_edge_case_single_value(self, reporter):
        """测试单一值"""
        prediction = np.array([[50.0]])
        variance = np.array([[1.0]])
        risk_index = np.array([[0.5]])

        summary = reporter._generate_executive_summary(prediction, variance, risk_index)

        assert summary["total_area"] == 1
        assert 0 <= summary["high_risk_percentage"] <= 100