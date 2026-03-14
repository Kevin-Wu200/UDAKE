#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDAKE macOS 应用构建脚本

此脚本用于构建 UDAKE 的 macOS 应用程序。
构建产物将存储在 dist/release/ 目录下。

使用方法:
    python3 dist/build_macOS.py
"""

import os
import sys
import shutil
import subprocess
import json
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional

# ANSI 颜色代码
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


def print_colored(message: str, color: str = Colors.NC) -> None:
    """打印带颜色的消息"""
    print(f"{color}{message}{Colors.NC}")


def run_command(command: list, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """
    运行命令并返回结果

    Args:
        command: 命令列表
        cwd: 工作目录
        check: 是否检查返回码

    Returns:
        subprocess.CompletedProcess
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print_colored(f"命令执行失败: {' '.join(command)}", Colors.RED)
        print_colored(f"错误输出: {e.stderr}", Colors.RED)
        raise


def check_command_exists(command: str) -> bool:
    """检查命令是否存在"""
    try:
        run_command(['which', command], check=False)
        return True
    except subprocess.CalledProcessError:
        return False


def setup_directories(project_root: Path) -> dict:
    """
    设置构建目录结构

    Args:
        project_root: 项目根目录

    Returns:
        包含所有路径的字典
    """
    dist_dir = project_root / 'dist'
    build_dir = dist_dir / 'build'
    release_dir = dist_dir / 'release'
    logs_dir = dist_dir / 'logs'
    tmp_dir = dist_dir / 'tmp'

    # 创建必要的目录
    directories = {
        'build_frontend': build_dir / 'frontend',
        'build_backend': build_dir / 'backend',
        'release': release_dir,
        'logs': logs_dir,
        'tmp': tmp_dir,
        'iconset': tmp_dir / 'UDAKE.iconset',
    }

    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return {
        'project_root': project_root,
        'dist_dir': dist_dir,
        'build_dir': build_dir,
        'release_dir': release_dir,
        'logs_dir': logs_dir,
        'tmp_dir': tmp_dir,
        **directories
    }


def clean_build(paths: dict) -> None:
    """清理旧的构建产物"""
    print_colored("\n[1/6] 清理旧的构建产物...", Colors.YELLOW)

    # 清理 build 目录
    for item in paths['build_dir'].iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 清理 release 目录
    for item in paths['release_dir'].iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print_colored("✓ 清理完成", Colors.GREEN)


def prepare_logo(paths: dict) -> None:
    """准备logo文件"""
    print_colored("\n准备logo文件...", Colors.YELLOW)

    # 检查logo文件位置
    logo_source = paths['dist_dir'] / 'logo' / 'logo.png'
    logo_dest = paths['dist_dir'] / 'logo.png'

    if logo_source.exists():
        # 如果logo在logo目录中，复制到dist根目录
        if logo_dest.exists():
            logo_dest.unlink()
        shutil.copy2(logo_source, logo_dest)
        print_colored(f"✓ Logo文件已准备: {logo_dest}", Colors.GREEN)
    elif logo_dest.exists():
        # 如果logo已经在正确位置
        print_colored(f"✓ Logo文件已存在: {logo_dest}", Colors.GREEN)
    else:
        print_colored("✗ Logo文件不存在", Colors.RED)
        print_colored("  请确保以下位置之一存在logo文件:", Colors.YELLOW)
        print_colored(f"  - {logo_source}", Colors.YELLOW)
        print_colored(f"  - {logo_dest}", Colors.YELLOW)
        sys.exit(1)


def build_frontend(paths: dict) -> None:
    """构建前端"""
    print_colored("\n[2/6] 构建前端...", Colors.YELLOW)

    frontend_dir = paths['project_root'] / 'frontend'
    build_frontend_dir = paths['build_frontend']

    if not frontend_dir.exists():
        print_colored("✗ 前端目录不存在", Colors.RED)
        sys.exit(1)

    # 清理目标目录
    if build_frontend_dir.exists():
        shutil.rmtree(build_frontend_dir)
    build_frontend_dir.mkdir(parents=True, exist_ok=True)

    # 复制前端文件
    for item in frontend_dir.iterdir():
        dest = build_frontend_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as e:
            print_colored(f"✗ 复制文件失败: {item.name} - {str(e)}", Colors.RED)
            sys.exit(1)

    print_colored("✓ 前端文件已复制", Colors.GREEN)


def build_backend(paths: dict) -> None:
    """构建后端"""
    print_colored("\n[3/6] 构建后端...", Colors.YELLOW)

    backend_dir = paths['project_root'] / 'backend'
    build_backend_dir = paths['build_backend']
    requirements_file = paths['project_root'] / 'requirements.txt'

    if not backend_dir.exists():
        print_colored("✗ 后端目录不存在", Colors.RED)
        sys.exit(1)

    # 清理目标目录
    if build_backend_dir.exists():
        shutil.rmtree(build_backend_dir)
    build_backend_dir.mkdir(parents=True, exist_ok=True)

    # 复制后端代码
    for item in backend_dir.iterdir():
        # 跳过隐藏文件和目录
        if item.name.startswith('.'):
            continue

        dest = build_backend_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as e:
            print_colored(f"✗ 复制文件失败: {item.name} - {str(e)}", Colors.RED)
            sys.exit(1)

    # 检查 Python 环境
    if requirements_file.exists():
        print_colored("检查 Python 依赖...", Colors.YELLOW)
        try:
            run_command(['pip3', '--version'])
            print_colored("✓ Python 环境正常", Colors.GREEN)
        except subprocess.CalledProcessError:
            print_colored("✗ pip3 未安装", Colors.RED)
            sys.exit(1)

    print_colored("✓ 后端文件已复制", Colors.GREEN)


def generate_app_icon(paths: dict) -> None:
    """生成应用图标"""
    print_colored("\n[4/6] 生成应用图标...", Colors.YELLOW)

    logo_path = paths['dist_dir'] / 'logo.png'
    iconset_dir = paths['iconset']
    icns_path = paths['dist_dir'] / 'UDAKE.icns'

    if not logo_path.exists():
        print_colored(f"✗ 图标源文件不存在: {logo_path}", Colors.RED)
        sys.exit(1)

    # 清理旧的 iconset
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir(parents=True)

    # 图标尺寸配置
    icon_sizes = [
        (16, 'icon_16x16.png'),
        (32, 'icon_16x16@2x.png'),
        (32, 'icon_32x32.png'),
        (64, 'icon_32x32@2x.png'),
        (128, 'icon_128x128.png'),
        (256, 'icon_128x128@2x.png'),
        (256, 'icon_256x256.png'),
        (512, 'icon_256x256@2x.png'),
        (512, 'icon_512x512.png'),
        (1024, 'icon_512x512@2x.png'),
    ]

    # 生成各种尺寸的图标
    print_colored("生成多尺寸图标...", Colors.YELLOW)
    for size, filename in icon_sizes:
        output_path = iconset_dir / filename
        try:
            run_command([
                'sips',
                '-z', str(size), str(size),
                str(logo_path),
                '--out', str(output_path)
            ], check=False)
        except subprocess.CalledProcessError:
            print_colored(f"✗ 生成 {size}x{size} 图标失败", Colors.RED)
            sys.exit(1)

    # 转换为 icns
    print_colored("转换为 .icns 格式...", Colors.YELLOW)
    try:
        run_command([
            'iconutil',
            '-c', 'icns',
            str(iconset_dir),
            '-o', str(icns_path)
        ])
    except subprocess.CalledProcessError:
        print_colored("✗ 图标生成失败", Colors.RED)
        sys.exit(1)

    if icns_path.exists():
        print_colored(f"✓ 图标生成成功: {icns_path}", Colors.GREEN)
        # 清理临时文件
        shutil.rmtree(iconset_dir)
    else:
        print_colored("✗ 图标生成失败", Colors.RED)
        sys.exit(1)


def install_electron_dependencies(paths: dict) -> None:
    """安装 Electron 依赖"""
    print_colored("\n[5/6] 安装 Electron 依赖...", Colors.YELLOW)

    package_json = paths['dist_dir'] / 'package.json'

    if not package_json.exists():
        print_colored("✗ package.json 不存在", Colors.RED)
        sys.exit(1)

    # 检查 npm
    if not check_command_exists('npm'):
        print_colored("✗ npm 未安装，请先安装 Node.js", Colors.RED)
        sys.exit(1)

    # 配置代理（如果需要）
    env = os.environ.copy()
    if 'HTTP_PROXY' in env or 'HTTPS_PROXY' in env:
        print_colored("检测到代理设置", Colors.YELLOW)
        if 'HTTP_PROXY' in env:
            print_colored(f"  HTTP_PROXY: {env['HTTP_PROXY']}", Colors.YELLOW)
        if 'HTTPS_PROXY' in env:
            print_colored(f"  HTTPS_PROXY: {env['HTTPS_PROXY']}", Colors.YELLOW)

    # 安装依赖
    print_colored("安装依赖包...", Colors.YELLOW)
    try:
        run_command(['npm', 'install', '--silent'], cwd=paths['dist_dir'], env=env)
        print_colored("✓ 依赖安装完成", Colors.GREEN)
    except subprocess.CalledProcessError:
        print_colored("✗ 依赖安装失败", Colors.RED)
        sys.exit(1)


def build_electron_app(paths: dict) -> None:
    """构建 Electron 应用"""
    print_colored("\n[6/6] 构建 Electron 应用...", Colors.YELLOW)

    try:
        run_command(['npm', 'run', 'build:mac'], cwd=paths['dist_dir'])
    except subprocess.CalledProcessError:
        print_colored("✗ Electron 应用构建失败", Colors.RED)
        sys.exit(1)

    # 查找生成的 .app 文件
    mac_dir = paths['release_dir'] / 'mac'
    if mac_dir.exists():
        app_files = list(mac_dir.glob('*.app'))
        if app_files:
            app_path = app_files[0]
            # 移动到 release 根目录
            dest_path = paths['release_dir'] / 'UDAKE.app'
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.move(str(app_path), str(dest_path))
            # 清理 mac 子目录
            shutil.rmtree(mac_dir)
            print_colored(f"✓ 应用构建成功: {dest_path}", Colors.GREEN)
        else:
            print_colored("✗ 未找到生成的 .app 文件", Colors.RED)
            sys.exit(1)
    else:
        print_colored("✗ 构建失败", Colors.RED)
        sys.exit(1)


def generate_build_info(paths: dict) -> None:
    """生成构建信息"""
    print_colored("\n生成构建信息...", Colors.YELLOW)

    # 读取版本号
    package_json = paths['dist_dir'] / 'package.json'
    version = "1.0.0"
    if package_json.exists():
        with open(package_json, 'r', encoding='utf-8') as f:
            pkg_data = json.load(f)
            version = pkg_data.get('version', '1.0.0')

    build_info = {
        "app_name": "UDAKE",
        "version": version,
        "build_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": "macOS",
        "architecture": "universal",
        "minimum_os": "12.0",
        "bundle_id": "com.udake.kriging"
    }

    build_info_path = paths['release_dir'] / 'build_info.json'
    with open(build_info_path, 'w', encoding='utf-8') as f:
        json.dump(build_info, f, indent=2, ensure_ascii=False)

    print_colored("✓ 构建信息已生成", Colors.GREEN)


def print_summary(paths: dict) -> None:
    """打印构建总结"""
    app_path = paths['release_dir'] / 'UDAKE.app'
    icns_path = paths['dist_dir'] / 'UDAKE.icns'
    build_info_path = paths['release_dir'] / 'build_info.json'

    print_colored("\n" + "━" * 50, Colors.GREEN)
    print_colored("  构建完成！", Colors.GREEN)
    print_colored("━" * 50, Colors.GREEN)
    print_colored(f"\n应用位置: {app_path}", Colors.GREEN)
    print_colored(f"图标文件: {icns_path}", Colors.GREEN)
    print_colored(f"构建信息: {build_info_path}", Colors.GREEN)
    print_colored("\n运行应用:", Colors.GREEN)
    print_colored(f'  open "{app_path}"', Colors.YELLOW)
    print_colored("\n或直接双击 UDAKE.app 启动\n", Colors.YELLOW)


def main():
    """主函数"""
    # 检查操作系统
    if platform.system() != 'Darwin':
        print_colored("此脚本仅适用于 macOS", Colors.RED)
        sys.exit(1)

    # 获取项目根目录
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.GREEN)
    print_colored("  UDAKE macOS 应用构建脚本", Colors.GREEN)
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.GREEN)
    print_colored(f"\n项目根目录: {project_root}", Colors.YELLOW)

    # 设置目录结构
    paths = setup_directories(project_root)

    # 执行构建步骤
    clean_build(paths)
    prepare_logo(paths)
    build_frontend(paths)
    build_backend(paths)
    generate_app_icon(paths)
    install_electron_dependencies(paths)
    build_electron_app(paths)
    generate_build_info(paths)

    # 打印总结
    print_summary(paths)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n构建被用户中断", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n✗ 构建失败: {str(e)}", Colors.RED)
        sys.exit(1)
