#!/usr/bin/env python3
"""
UDAKE Android APK自动构建脚本
用于自动化构建前端项目、同步Android平台和生成签名APK
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path


class APKBuilder:
    def __init__(self):
        # 项目根目录
        self.project_root = Path("/Users/wuchenkai/UDAKE")
        self.android_dir = self.project_root / "android"
        self.frontend_dist = self.project_root / "frontend" / "dist"
        self.logo_source = self.project_root / "dist" / "build_Android" / "logo" / "logo.png"
        self.output_apk = self.project_root / "dist" / "build_Android" / "apk" / "UDAKE.apk"
        
        # Android图标目录和尺寸
        self.icon_sizes = {
            "mipmap-mdpi": 48,
            "mipmap-hdpi": 72,
            "mipmap-xhdpi": 96,
            "mipmap-xxhdpi": 144,
            "mipmap-xxxhdpi": 192
        }
        
    def run_command(self, command, cwd=None, check=True):
        """执行shell命令"""
        print(f"执行命令: {' '.join(command) if isinstance(command, list) else command}")
        result = subprocess.run(
            command,
            cwd=cwd or self.project_root,
            shell=isinstance(command, str),
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
        if check and result.returncode != 0:
            raise RuntimeError(f"命令执行失败: {command}")
            
        return result
    
    def build_frontend(self):
        """构建前端项目"""
        print("\n=== 开始构建前端项目 ===")
        self.run_command("npm run build")
        print("✓ 前端项目构建完成")
    
    def sync_android(self):
        """同步Android平台"""
        print("\n=== 同步Android平台 ===")
        self.run_command("npx cap sync android")
        print("✓ Android平台同步完成")
    
    def update_icons(self):
        """更新Android应用图标"""
        print("\n=== 更新应用图标 ===")
        
        if not self.logo_source.exists():
            print(f"警告: 图标文件不存在: {self.logo_source}")
            return
            
        res_dir = self.android_dir / "app" / "src" / "main" / "res"
        
        for dpi, size in self.icon_sizes.items():
            icon_dir = res_dir / dpi
            
            # 复制并调整图标尺寸
            for icon_type in ["ic_launcher.png", "ic_launcher_round.png"]:
                icon_path = icon_dir / icon_type
                
                # 复制图标
                shutil.copy(self.logo_source, icon_path)
                
                # 使用sips调整尺寸
                self.run_command(
                    f"sips -z {size} {size} {icon_path}",
                    check=False
                )
        
        print("✓ 应用图标更新完成")
    
    def build_apk(self):
        """构建签名APK"""
        print("\n=== 构建签名APK ===")
        
        # 确保输出目录存在
        self.output_apk.parent.mkdir(parents=True, exist_ok=True)
        
        # 构建release APK
        self.run_command(
            "./gradlew assembleRelease",
            cwd=self.android_dir
        )
        
        # 查找生成的未签名APK文件
        unsigned_apk = self.android_dir / "app" / "build" / "outputs" / "apk" / "release" / "app-release-unsigned.apk"
        aligned_apk = self.android_dir / "app" / "build" / "outputs" / "apk" / "release" / "app-release-aligned.apk"
        
        if not unsigned_apk.exists():
            raise RuntimeError(f"未签名APK文件未找到: {unsigned_apk}")
        
        # 使用zipalign对APK进行对齐
        print("正在对APK进行对齐...")
        zipalign_path = "/Users/wuchenkai/Library/Android/sdk/build-tools/36.1.0/zipalign"
        self.run_command(
            f"{zipalign_path} -v -p 4 {unsigned_apk} {aligned_apk}",
            check=False
        )
        
        # 使用jarsigner对APK进行签名
        print("正在对APK进行签名...")
        debug_keystore = self.project_root / "debug.keystore"
        
        # 如果调试密钥不存在，则生成
        if not debug_keystore.exists():
            print("生成调试密钥...")
            self.run_command(
                f'keytool -genkey -v -keystore {debug_keystore} -alias debug -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=Android Debug,O=Android,C=US"',
                check=False
            )
        
        # 对APK进行签名
        self.run_command(
            f'jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA256 -keystore {debug_keystore} -storepass android -keypass android {aligned_apk} debug',
            check=False
        )
        
        # 复制到输出目录
        shutil.copy(aligned_apk, self.output_apk)
        print(f"✓ APK构建完成: {self.output_apk}")
        
        # 显示APK信息
        apk_size = self.output_apk.stat().st_size / (1024 * 1024)  # 转换为MB
        print(f"APK大小: {apk_size:.2f} MB")
    
    def build(self):
        """执行完整的构建流程"""
        try:
            print("=== UDAKE Android APK自动构建开始 ===")
            
            # 1. 构建前端项目
            self.build_frontend()
            
            # 2. 同步Android平台
            self.sync_android()
            
            # 3. 更新应用图标
            self.update_icons()
            
            # 4. 构建签名APK
            self.build_apk()
            
            print("\n=== 构建成功完成 ===")
            print(f"APK文件位置: {self.output_apk}")
            
        except Exception as e:
            print(f"\n=== 构建失败 ===")
            print(f"错误: {e}")
            sys.exit(1)


def main():
    """主函数"""
    builder = APKBuilder()
    builder.build()


if __name__ == "__main__":
    main()