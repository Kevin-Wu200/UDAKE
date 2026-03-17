import warnings

# 抑制 macOS LibreSSL 与 urllib3 v2 的兼容性警告
warnings.filterwarnings("ignore", message=".*urllib3.*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")
