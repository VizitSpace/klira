; Скрипт установщика Klira для Inno Setup 6.3 или новее (бесплатно: https://jrsoftware.org/isdl.php).
; Положите рядом с этим файлом: Klira.exe, WebView2Loader.dll, EULA.txt, THIRD_PARTY_NOTICES.txt,
; PRIVACY.md, on.ico (всё это уже лежит в папке с готовым набором). Откройте файл в Inno Setup
; и нажмите Build → Compile (Ctrl+F9). Готовый Klira_Setup_<версия>.exe появится в подпапке Output.

#define MyAppName "Klira"
#define MyAppVersion "@VERSION@"
#define MyAppPublisher "Олександр Коханчук"
#define MyAppURL "https://github.com/VizitSpace/klira"
#define MyAppExe "Klira.exe"

[Setup]
; Идентификатор программы для Windows. НЕ МЕНЯЙТЕ его в новых версиях: по нему установщик
; понимает, что ставит обновление поверх старой версии.
AppId={{B3C1D6E2-7A54-4F0B-9C28-5E1A4D7F3A91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppCopyright=© 2026 Олександр Коханчук. Все права защищены.
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Установщик Klira
VersionInfoCopyright=© 2026 Олександр Коханчук. Все права защищены.
; Установка только для текущего пользователя: без прав администратора, в %LOCALAPPDATA%\Programs\Klira.
; На странице выбора можно поставить для всех пользователей (тогда Windows спросит разрешение).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=EULA.txt
SetupIconFile=on.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
OutputDir=Output
OutputBaseFilename=Klira_Setup_{#MyAppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
; Если купите сертификат подписи кода, раскомментируйте и настройте (см. ИНСТРУКЦИЯ.txt):
; SignTool=signtool $f

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
russian.DeleteData=Удалить также настройки, словарь и статистику Klira?%n%n%1
ukrainian.DeleteData=Видалити також налаштування, словник і статистику Klira?%n%n%1
english.DeleteData=Also delete Klira's settings, dictionary and statistics?%n%n%1
russian.DesktopIcon=Создать ярлык на рабочем столе
ukrainian.DesktopIcon=Створити ярлик на робочому столі
english.DesktopIcon=Create a desktop shortcut

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: unchecked

[Files]
Source: "Klira.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "WebView2Loader.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "EULA.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Klira сама включает и выключает автозапуск (переключатель в настройках). Здесь только
; убираем эту запись при удалении программы.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Klira"; ValueType: none; Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Klira живёт в трее и без окон: перед обновлением и удалением закрываем её.
procedure StopKlira();
var
  code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#MyAppExe}', '', SW_HIDE, ewWaitUntilTerminated, code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopKlira();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  dataDir: String;
begin
  if CurUninstallStep = usUninstall then
    StopKlira()
  else if CurUninstallStep = usPostUninstall then
  begin
    dataDir := ExpandConstant('{userappdata}\Klira');
    if (not UninstallSilent()) and DirExists(dataDir) then
      if MsgBox(FmtMessage(CustomMessage('DeleteData'), [dataDir]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(dataDir, True, True, True);
        DelTree(ExpandConstant('{localappdata}\Klira'), True, True, True); // кэш окна (WebView2)
      end;
  end;
end;
