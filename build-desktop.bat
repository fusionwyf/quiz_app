@echo off
setlocal
REM 一键构建桌面安装包：PyInstaller 冻结后端 -> 复制 sidecar -> Tauri NSIS 打包
set TRIPLE=x86_64-pc-windows-msvc

echo [1/3] PyInstaller 冻结后端...
uv run pyinstaller quiz-backend.spec --noconfirm
if errorlevel 1 goto :fail

echo [2/3] 复制 sidecar 二进制（Tauri externalBin 要求带目标三元组后缀）...
if not exist frontend\src-tauri\binaries mkdir frontend\src-tauri\binaries
copy /y dist\quiz-backend.exe frontend\src-tauri\binaries\quiz-backend-%TRIPLE%.exe
if errorlevel 1 goto :fail

echo [3/3] Tauri 构建（前端 + Rust + NSIS 安装包）...
pushd frontend
call npx tauri build
if errorlevel 1 (popd & goto :fail)
popd

echo.
echo 完成！安装包位于 frontend\src-tauri\target\release\bundle\nsis\
endlocal & exit /b 0

:fail
echo 构建失败
endlocal & exit /b 1
