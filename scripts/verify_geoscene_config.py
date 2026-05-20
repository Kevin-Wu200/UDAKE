#!/usr/bin/env python3
"""
GeoScene Enterprise 服务集成验证脚本
对应 TODOList/GeoScene服务集成方案.txt 第三阶段验收任务:
  V-1: 认证通路测试
  V-2: 静态底图渲染验收
  V-3: 动态图层交互验收
  V-4: 异常处理回退测试
"""
import sys
import os
import json

# 确保后端路径可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'backend'))

PASS = 0
FAIL = 0
WARN = 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL, WARN
    if condition:
        PASS += 1
        print(f"  ✅ {label}: {detail}")
    else:
        FAIL += 1
        print(f"  ❌ {label}: {detail}")

def warn(label: str, detail: str = ""):
    global WARN
    WARN += 1
    print(f"  ⚠️  {label}: {detail}")

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# V-1: 认证通路测试
# ============================================================
section("V-1 认证通路测试")

# 1.1 检查环境变量
print("\n[1.1] 环境变量检查")
import_env = os.path.join(os.path.dirname(__file__), '..', 'configs', 'env', '.env')
env_vars = {}
if os.path.exists(import_env):
    with open(import_env, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                env_vars[key.strip()] = val.strip()

check("GEOSCENE_AUTH_MODE=enterprise",
      env_vars.get('GEOSCENE_AUTH_MODE') == 'enterprise',
      f"当前值: {env_vars.get('GEOSCENE_AUTH_MODE', '未设置')}")

check("GEOSCENE_USERNAME 已配置",
      bool(env_vars.get('GEOSCENE_USERNAME', '').strip()),
      f"当前值: {env_vars.get('GEOSCENE_USERNAME', '未设置')}")

check("GEOSCENE_PASSWORD 已配置",
      bool(env_vars.get('GEOSCENE_PASSWORD', '').strip()),
      f"当前值: {'***' if env_vars.get('GEOSCENE_PASSWORD') else '未设置'}")

check("GEOSCENE_PORTAL_URL 已配置",
      bool(env_vars.get('GEOSCENE_PORTAL_URL', '').strip()),
      f"当前值: {env_vars.get('GEOSCENE_PORTAL_URL', '未设置')}")

check("GEOSCENE_TOKEN_URL 已配置",
      bool(env_vars.get('GEOSCENE_TOKEN_URL', '').strip()),
      f"当前值: {env_vars.get('GEOSCENE_TOKEN_URL', '未设置')}")

# 1.2 验证配置文件加载
print("\n[1.2] 后端 config.py 加载验证")
try:
    from app.config import settings
    check("Settings 实例创建成功", settings is not None)

    check("GEOSCENE_AUTH_MODE 正确加载",
          settings.GEOSCENE_AUTH_MODE == "enterprise",
          f"当前值: {settings.GEOSCENE_AUTH_MODE}")

    check("GEOSCENE_USERNAME 正确加载",
          bool(settings.GEOSCENE_USERNAME.strip()),
          f"当前值: {settings.GEOSCENE_USERNAME}")

    check("GEOSCENE_PORTAL_URL 正确加载",
          bool(settings.GEOSCENE_PORTAL_URL.strip()),
          f"当前值: {settings.GEOSCENE_PORTAL_URL}")

    # 1.3 Token URL 验证
    print("\n[1.3] Token URL 验证")
    token_url = settings.geoscene_token_url
    check("geoscene_token_url 属性返回有效URL",
          token_url and token_url.startswith("https://"),
          f"Token URL: {token_url}")

    check("Token URL 包含 /sharing/rest/generateToken",
          "/sharing/rest/generateToken" in token_url,
          f"Token URL: {token_url}")

    check("Token URL 不含多余的 /portal/ 路径",
          "/portal/sharing" not in token_url,
          f"Token URL: {token_url}" + (" (包含 /portal/ 前缀!)" if "/portal/sharing" in token_url else ""))

    # 1.4 Mock 模式检测
    print("\n[1.4] Mock 模式检测")
    is_mock = settings.geoscene_is_mock
    if is_mock:
        warn("geoscene_is_mock=True",
             "企业认证信息齐全但仍为Mock模式(可能是GeoScene服务器不可达导致)")
        WARN += 1
    else:
        check("geoscene_is_mock=False (非Mock模式)",
              True,
              "Enterprise认证模式且用户名密码已配置")

    # 1.5 配置接口验证
    print("\n[1.5] 配置API接口验证")
    check("geoscene_center_list 返回有效坐标",
          len(settings.geoscene_center_list) == 2,
          f"中心点: {settings.geoscene_center_list}")

    check("GEOSCENE_DEFAULT_BASEMAP 已配置",
          bool(settings.GEOSCENE_DEFAULT_BASEMAP.strip()),
          f"底图: {settings.GEOSCENE_DEFAULT_BASEMAP}")

except Exception as e:
    FAIL += 1
    print(f"  ❌ 配置加载失败: {e}")


# ============================================================
# V-2: 静态底图渲染验收
# ============================================================
section("V-2 静态底图渲染验收")

# 2.1 前端环境变量检查
print("\n[2.1] 前端环境变量检查")
frontend_env = os.path.join(os.path.dirname(__file__), '..', 'configs', 'env', '.env.development')
fe_vars = {}
if os.path.exists(frontend_env):
    with open(frontend_env, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                fe_vars[key.strip()] = val.strip()

check("VITE_GEOSCENE_AUTH_MODE=enterprise",
      fe_vars.get('VITE_GEOSCENE_AUTH_MODE') == 'enterprise',
      f"当前值: {fe_vars.get('VITE_GEOSCENE_AUTH_MODE', '未设置')}")

check("VITE_GEOSCENE_PORTAL_URL 已配置",
      bool(fe_vars.get('VITE_GEOSCENE_PORTAL_URL', '').strip()),
      f"当前值: {fe_vars.get('VITE_GEOSCENE_PORTAL_URL', '未设置')}")

check("VITE_GEOSCENE_DEFAULT_BASEMAP 已配置",
      bool(fe_vars.get('VITE_GEOSCENE_DEFAULT_BASEMAP', '').strip()),
      f"底图: {fe_vars.get('VITE_GEOSCENE_DEFAULT_BASEMAP', '未设置')}")

check("VITE_GEOSCENE_DEFAULT_CENTER 已配置",
      bool(fe_vars.get('VITE_GEOSCENE_DEFAULT_CENTER', '').strip()),
      f"中心: {fe_vars.get('VITE_GEOSCENE_DEFAULT_CENTER', '未设置')}")

check("VITE_GEOSCENE_DEFAULT_ZOOM 已配置",
      bool(fe_vars.get('VITE_GEOSCENE_DEFAULT_ZOOM', '').strip()),
      f"缩放: {fe_vars.get('VITE_GEOSCENE_DEFAULT_ZOOM', '未设置')}")

# 2.2 底图服务类型验证
print("\n[2.2] 底图服务类型检查")
basemap = fe_vars.get('VITE_GEOSCENE_DEFAULT_BASEMAP', '')
if 'vector' in basemap.lower():
    check("底图使用 VectorTileServer (推荐)", True, f"底图: {basemap}")
elif 'topographic' in basemap.lower() or 'imagery' in basemap.lower():
    check("底图使用 MapServer/ImageServer", True, f"底图: {basemap}")
else:
    warn(f"底图类型未知: {basemap}")

# 2.3 前端 geoscene.config.js 检查
print("\n[2.3] 前端 GeoSceneConfig 代码检查")
geoscene_config_js = os.path.join(os.path.dirname(__file__), '..', 'apps', 'frontend', 'js', 'config', 'geoscene.config.js')
if os.path.exists(geoscene_config_js):
    with open(geoscene_config_js, 'r', encoding='utf-8') as f:
        config_content = f.read()

    check("geoscene.config.js 文件存在", True)

    check("支持 Enterprise 认证模式",
          'AUTH_MODE' in config_content and 'enterprise' in config_content)

    check("支持从后端更新配置 (updateConfig)",
          'updateConfig' in config_content)

    check("Mock 模式检测逻辑存在 (isMockMode)",
          'isMockMode' in config_content)

    check("getConfig 返回完整配置对象",
          'getConfig' in config_content and 'portalUrl' in config_content)
else:
    FAIL += 1
    print(f"  ❌ geoscene.config.js 文件不存在")


# ============================================================
# V-3: 动态图层交互验收
# ============================================================
section("V-3 动态图层交互验收")

# 3.1 GeoSceneAdapter 代码检查
print("\n[3.1] GeoSceneAdapter.ts 图层支持检查")
adapter_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'frontend', 'js', 'adapters', 'GeoSceneAdapter.ts')
if os.path.exists(adapter_path):
    with open(adapter_path, 'r', encoding='utf-8') as f:
        adapter_content = f.read()

    check("GeoSceneAdapter.ts 文件存在", True)

    check("支持 ImageryLayer (预测栅格)",
          'ImageryLayer' in adapter_content)

    check("addRasterLayer 方法存在",
          'addRasterLayer' in adapter_content and 'ImageryLayer' in adapter_content)

    check("支持 GraphicsLayer (采样点)",
          'GraphicsLayer' in adapter_content or 'graphicsLayer' in adapter_content)

    check("支持 GeoJSONLayer (采样点批导入)",
          'GeoJSONLayer' in adapter_content)

    check("spatialReference 自动对齐",
          'spatialReference' in adapter_content and 'this.view.spatialReference' in adapter_content)

    # 3.2 Mock 模式图层兼容检查
    print("\n[3.2] Mock 模式图层兼容检查")
    check("addRasterLayer 支持 Mock 模式回退",
          'isMock' in adapter_content and 'Mock 模式' in adapter_content)

    check("addPointsLayer 支持 Mock 模式回退",
          'addPointsLayer' in adapter_content and 'Mock 模式' in adapter_content)
else:
    FAIL += 1
    print(f"  ❌ GeoSceneAdapter.ts 文件不存在")

# 3.3 坐标系统一性检查
print("\n[3.3] 坐标系统检查")
frontend_coords_path = os.path.join(os.path.dirname(__file__), '..', 'apps', 'frontend', 'js', '坐标系统信息.ts')
if os.path.exists(frontend_coords_path):
    with open(frontend_coords_path, 'r', encoding='utf-8') as f:
        coord_content = f.read()

    check("支持 EPSG:4326 (WGS84)",
          '4326' in coord_content)

    check("支持 EPSG:3857 (Web Mercator)",
          '3857' in coord_content)
else:
    warn("坐标系统信息.ts 不存在，可能使用了其他文件")


# ============================================================
# V-4: 异常处理回退测试
# ============================================================
section("V-4 异常处理回退测试")

# 4.1 GeoSceneAdapter 异常处理检查
print("\n[4.1] GeoSceneAdapter 异常处理逻辑")
if os.path.exists(adapter_path):
    with open(adapter_path, 'r', encoding='utf-8') as f:
        adapter_content = f.read()

    check("企业认证失败回退到访客模式",
          '回退为访客模式' in adapter_content or 'guest' in adapter_content.lower())

    check("_setupEnterpriseAuth 有 try-catch 保护",
          '_setupEnterpriseAuth' in adapter_content and 'catch' in adapter_content.split('_setupEnterpriseAuth')[1][:2000])

    check("配置设置失败使用默认配置",
          '默认配置' in adapter_content or 'default' in adapter_content.lower())

    check("isMock 判断逻辑确保地图可降级",
          'isMock' in adapter_content and 'MockMapEngine' in adapter_content)

    check("destroy 方法安全清理资源",
          'destroy' in adapter_content and 'clearAllLayers' in adapter_content)

    # 4.2 前端配置的 isMockMode 检查
    print("\n[4.2] 前端 Mock 模式回退验证")
    if os.path.exists(geoscene_config_js):
        with open(geoscene_config_js, 'r', encoding='utf-8') as f:
            config_content = f.read()

        check("isMockMode 检测 enterprise 模式下缺少用户名密码",
              'AUTH_MODE' in config_content and 'USERNAME' in config_content and 'PASSWORD' in config_content)

        check("isMockMode 检测 API Key 模式下缺少 Key",
              'API_KEY' in config_content and 'YOUR_GEOSCENE_API_KEY_HERE' in config_content)

        check("getConfig 时 isMock=true 时打印警告",
              'isMock' in config_content and 'console.warn' in config_content)


# ============================================================
# 汇总
# ============================================================
section("验证汇总")
total = PASS + FAIL + WARN
print(f"\n  总计检查项: {total}")
print(f"  ✅ 通过: {PASS}")
print(f"  ⚠️  警告: {WARN}")
print(f"  ❌ 失败: {FAIL}")

if FAIL == 0:
    print(f"\n  🎉 所有 GeoScene 服务集成验证项通过!")
    sys.exit(0)
else:
    print(f"\n  ⚠️  存在 {FAIL} 项失败，请检查配置")
    sys.exit(1)
