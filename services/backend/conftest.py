import warnings
import sys
from pathlib import Path

# 确保无论从哪个工作目录执行 pytest，都能导入仓库根目录下的模块（如 ai_extension）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 抑制 macOS LibreSSL 与 urllib3 v2 的兼容性警告
warnings.filterwarnings("ignore", message=".*urllib3.*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")

# 抑制 starlette 对 multipart 导入兼容层的待弃用提示
warnings.filterwarnings(
    "ignore",
    message=".*import python_multipart.*",
    category=PendingDeprecationWarning,
    module="starlette\\.formparsers"
)
