"""GAN异常检测适配器功能测试脚本"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services/backend'))

import numpy as np
from deep_learning.models.anomaly_detection import GANAnomalyDetector

# 导入GAN适配器
try:
    from app.dl_services.gan_anomaly_explainer import GANAnomalyLimeAdapter, GANAnomalySHAPAdapter
    print("✅ 成功导入GAN适配器")
except ImportError as e:
    print(f"❌ 导入GAN适配器失败: {e}")
    sys.exit(1)


def build_test_data() -> tuple[np.ndarray, np.ndarray]:
    """构建测试数据"""
    coords = np.asarray(
        [
            [120.10, 30.20],
            [120.20, 30.25],
            [120.18, 30.30],
            [120.24, 30.28],
            [120.15, 30.35],
            [120.28, 30.22],
            [120.30, 30.26],
            [120.12, 30.18],
            [120.22, 30.32],
            [120.16, 30.24],
        ],
        dtype=float,
    )
    values = np.asarray([1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98, 1.12, 1.25], dtype=float)
    return coords, values


def build_trained_model() -> tuple[GANAnomalyDetector, np.ndarray, np.ndarray]:
    """构建训练好的GAN模型"""
    coords, values = build_test_data()
    model = GANAnomalyDetector()
    print("🔄 开始训练GAN模型...")
    training_result = model.fit(coords, values)
    print(f"✅ GAN模型训练完成，训练轮数: {training_result.get('epochs', 0)}")
    return model, coords, values


def test_gan_lime_adapter():
    """测试GAN LIME适配器"""
    print("\n" + "="*60)
    print("测试GAN LIME适配器")
    print("="*60)

    try:
        model, coords, values = build_trained_model()
        adapter = GANAnomalyLimeAdapter()

        print("🔄 开始LIME解释...")
        result = adapter.explain(
            model=model,
            coords=coords,
            values=values,
            top_k=3,
            max_explain_nodes=3
        )

        # 验证结果结构
        assert result["summary"]["method"] == "lime", "方法应该为lime"
        assert result["summary"]["explained_nodes"] == 3, "应该解释3个节点"
        assert len(result["batch_explanations"]) == 3, "应该有3个批量解释"
        assert "score_components" in result, "应该包含分数组件"
        assert len(result["score_components"]["combined"]) == len(values), "组合分数数量应该匹配"

        print("✅ LIME适配器测试通过")
        print(f"   - 解释节点数: {result['summary']['explained_nodes']}")
        print(f"   - 特征数量: {result['summary']['num_features']}")
        print(f"   - 平均置信度: {result['summary']['average_confidence']:.4f}")

        # 显示特征重要性
        if result["summary"]["top_features"]:
            print("   - Top特征:")
            for i, feat in enumerate(result["summary"]["top_features"][:3], 1):
                print(f"     {i}. {feat['feature_alias']}: {feat['importance']:.4f}")

        return True

    except Exception as e:
        print(f"❌ LIME适配器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gan_shap_adapter():
    """测试GAN SHAP适配器"""
    print("\n" + "="*60)
    print("测试GAN SHAP适配器")
    print("="*60)

    try:
        model, coords, values = build_trained_model()
        adapter = GANAnomalySHAPAdapter()

        print("🔄 开始SHAP解释...")
        result = adapter.explain(
            model=model,
            coords=coords,
            values=values,
            top_k=3,
            max_explain_nodes=2
        )

        # 验证结果结构
        assert result["summary"]["method"] == "shap", "方法应该为shap"
        assert result["summary"]["explainer"] == "KernelExplainer", "解释器应该为KernelExplainer"
        assert len(result["batch_explanations"]) == 2, "应该有2个批量解释"
        assert "score_components" in result, "应该包含分数组件"

        print("✅ SHAP适配器测试通过")
        print(f"   - 解释节点数: {result['summary']['explained_nodes']}")
        print(f"   - 特征数量: {result['summary']['num_features']}")
        print(f"   - 背景样本数: {result['summary']['background_size']}")
        print(f"   - 平均置信度: {result['summary']['average_confidence']:.4f}")

        # 显示特征重要性
        if result["summary"]["top_features"]:
            print("   - Top特征:")
            for i, feat in enumerate(result["summary"]["top_features"][:3], 1):
                print(f"     {i}. {feat['feature_alias']}: {feat['importance']:.4f}")

        return True

    except Exception as e:
        print(f"❌ SHAP适配器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_mechanism():
    """测试缓存机制"""
    print("\n" + "="*60)
    print("测试缓存机制")
    print("="*60)

    try:
        model, coords, values = build_trained_model()
        adapter = GANAnomalySHAPAdapter()

        print("🔄 第一次SHAP解释...")
        first = adapter.explain(
            model=model,
            coords=coords,
            values=values,
            top_k=3,
            max_explain_nodes=2
        )

        print("🔄 第二次SHAP解释（相同输入）...")
        second = adapter.explain(
            model=model,
            coords=coords,
            values=values,
            top_k=3,
            max_explain_nodes=2
        )

        # 验证缓存命中
        assert second["performance"]["cache_hit"] is True, "第二次应该命中缓存"

        print("✅ 缓存机制测试通过")
        print(f"   - 第一次执行时间: {first['performance']['duration_ms']:.2f}ms")
        print(f"   - 第二次执行时间: {second['performance']['duration_ms']:.2f}ms")
        print(f"   - 缓存命中: {'是' if second['performance']['cache_hit'] else '否'}")

        return True

    except Exception as e:
        print(f"❌ 缓存机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("GAN异常检测适配器功能测试")
    print("="*60)

    results = {
        "LIME适配器": False,
        "SHAP适配器": False,
        "缓存机制": False,
    }

    # 运行测试
    results["LIME适配器"] = test_gan_lime_adapter()
    results["SHAP适配器"] = test_gan_shap_adapter()
    results["缓存机制"] = test_cache_mechanism()

    # 输出总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")

    total_tests = len(results)
    passed_tests = sum(results.values())

    print(f"\n总计: {passed_tests}/{total_tests} 测试通过")

    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！GAN适配器功能正常。")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} 个测试失败。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
