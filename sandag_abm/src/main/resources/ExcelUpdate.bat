rem forced to update excel links for auto reporting, YMA, 1/23/2019

@echo on

set PROJECT_DRIVE=%1
set PROJECT_DIRECTORY=%2
set SCENARIOYEAR=%3
set SCENARIOID=%4

@echo path

%PROJECT_DRIVE%
cd %PROJECT_DRIVE%%PROJECT_DIRECTORY%
python %PROJECT_DRIVE%%PROJECT_DIRECTORY%\python\excel_update.py  %PROJECT_DRIVE%%PROJECT_DIRECTORY% %SCENARIOYEAR% %SCENARIOID%
