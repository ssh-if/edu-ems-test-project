@echo off
chcp 65001 > nul
echo ============================================================
echo   紫薇教育 EMS 接口自动化测试运行脚本 - By 苏绍彰
echo ============================================================
echo.

:: 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.8+ 并添加到 PATH
    pause
    exit /b 1
)

:: 安装依赖
echo [1/4] 检查并安装依赖包 ...
pip install requests pytest pytest-html allure-pytest PyYAML Faker --quiet

:: 创建报告目录
if not exist report mkdir report
if not exist allure-results mkdir allure-results

:: 运行冒烟用例
echo.
echo [2/4] 开始运行 P0 冒烟用例 (--maxfail=3) ...
pytest -m "smoke or p0" --maxfail=3 -v ^
    --html=report/p0_smoke_report.html --self-contained-html ^
    --alluredir=allure-results/p0

set P0_EXIT=%errorlevel%

:: 运行全部用例
echo.
echo [3/4] 运行全量用例 (含接口、权限、安全)  ...
pytest -v ^
    --html=report/full_test_report.html --self-contained-html ^
    --alluredir=allure-results/full ^
    --ignore-glob=performance_test.py

set FULL_EXIT=%errorlevel%

echo.
echo ============================================================
echo   测试完成！
echo   P0 冒烟退出码 = %P0_EXIT%   (0 = 全部通过)
echo   全量用例退出码 = %FULL_EXIT% (0 = 全部通过)
echo.
echo   HTML 报告:
echo     - P0 报告: report\p0_smoke_report.html
echo     - 全量报告: report\full_test_report.html
echo.
echo   如果已安装 Allure，可执行：
echo     allure serve allure-results\full
echo ============================================================
pause
