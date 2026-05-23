"""
numpy类型转换工具

将numpy类型递归转换为Python原生类型，解决Pydantic序列化问题。
"""
from datetime import datetime

import numpy as np


def numpy_to_python(value):
    """将numpy类型递归转换为Python原生类型"""
    if isinstance(value, np.bool_):
        return bool(value)
    elif isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, np.datetime64):
        return value.astype(datetime)
    elif isinstance(value, dict):
        return {k: numpy_to_python(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        converted = [numpy_to_python(v) for v in value]
        return type(value)(converted) if isinstance(value, tuple) else converted
    else:
        return value
