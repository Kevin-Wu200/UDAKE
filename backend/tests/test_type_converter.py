"""
类型转换工具单元测试
"""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from backend.app.utils.type_converter import numpy_to_python


class TestNumpyToPython:
    """测试numpy类型转换"""

    def test_numpy_bool(self):
        assert numpy_to_python(np.bool_(True)) is True
        assert numpy_to_python(np.bool_(False)) is False
        assert isinstance(numpy_to_python(np.bool_(True)), bool)

    def test_numpy_integer(self):
        assert numpy_to_python(np.int64(42)) == 42
        assert isinstance(numpy_to_python(np.int64(42)), int)
        assert numpy_to_python(np.int32(0)) == 0
        assert isinstance(numpy_to_python(np.int32(0)), int)

    def test_numpy_floating(self):
        assert numpy_to_python(np.float64(3.14)) == pytest.approx(3.14)
        assert isinstance(numpy_to_python(np.float64(3.14)), float)
        assert numpy_to_python(np.float32(0.0)) == 0.0
        assert isinstance(numpy_to_python(np.float32(0.0)), float)

    def test_numpy_ndarray(self):
        arr = np.array([1, 2, 3])
        result = numpy_to_python(arr)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_numpy_ndarray_2d(self):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = numpy_to_python(arr)
        assert result == [[1.0, 2.0], [3.0, 4.0]]

    def test_nested_dict(self):
        data = {
            "count": np.int64(10),
            "ratio": np.float64(0.5),
            "flag": np.bool_(True),
            "values": np.array([1, 2, 3])
        }
        result = numpy_to_python(data)
        assert result["count"] == 10
        assert isinstance(result["count"], int)
        assert isinstance(result["ratio"], float)
        assert isinstance(result["flag"], bool)
        assert isinstance(result["values"], list)

    def test_nested_list(self):
        data = [np.int64(1), np.float64(2.0), np.bool_(False)]
        result = numpy_to_python(data)
        assert result == [1, 2.0, False]
        assert isinstance(result[0], int)
        assert isinstance(result[1], float)
        assert isinstance(result[2], bool)

    def test_deeply_nested(self):
        data = {
            "level1": {
                "level2": [
                    {"value": np.float64(1.0), "ok": np.bool_(True)}
                ]
            }
        }
        result = numpy_to_python(data)
        assert isinstance(result["level1"]["level2"][0]["value"], float)
        assert isinstance(result["level1"]["level2"][0]["ok"], bool)

    def test_python_native_passthrough(self):
        assert numpy_to_python(42) == 42
        assert numpy_to_python("hello") == "hello"
        assert numpy_to_python(3.14) == 3.14
        assert numpy_to_python(True) is True
        assert numpy_to_python(None) is None

    def test_tuple_preserved(self):
        data = (np.int64(1), np.int64(2))
        result = numpy_to_python(data)
        assert result == (1, 2)
        assert isinstance(result, tuple)

    def test_comparison_result(self):
        """测试numpy比较运算结果的转换（核心场景）"""
        a = np.float64(0.05)
        b = 0.1
        result = numpy_to_python(a <= b)
        assert result is True
        assert isinstance(result, bool)
