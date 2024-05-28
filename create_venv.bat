@echo Off
color 0A
echo --
echo #####################################
echo Python Environment Deployment Script
echo Developed by @Faizan Ali (sfaizan@ingenero.com)
echo Ingenero Technologies India Pvt. Ltd.
echo #####################################
echo --
echo Checking for Python Installation
where /q py
IF ERRORLEVEL 1 (
ECHO No Python found, installing Python...
python.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0) ELSE (
echo Python already exists at
echo %python%
echo Creating Environment...
mkdir venv
py -m venv venv
echo Environment created, installing dependencies...
echo --
call venv/Scripts/activate.bat
pip --quiet --disable-pip-version-check install -r requirements.txt)
echo Done!
