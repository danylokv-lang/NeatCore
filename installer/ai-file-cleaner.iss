; Inno Setup Script for NeatCore
; Build prerequisites:
; 1) Create a Windows executable with PyInstaller
;    Recommended: pyinstaller NeatCore.spec
;    or: pyinstaller --noconsole --name "NeatCore" --icon assets/icon.ico main.py
;    Output will be under dist\NeatCore\NeatCore.exe
; 2) Then compile this script in Inno Setup to produce the installer.

#define MyAppVersion "1.1.0"
#define RootDir AddBackslash(SourcePath) + "..\\"
#define NeatExe AddBackslash(RootDir) + "dist\\NeatCore\\NeatCore.exe"
#define NeatDir AddBackslash(RootDir) + "dist\\NeatCore"
#define OldExe  AddBackslash(RootDir) + "dist\\AI File Cleaner\\AI File Cleaner.exe"
#define OldDir  AddBackslash(RootDir) + "dist\\AI File Cleaner"

[Setup]
AppId={{6C2E5B3A-3B4A-4A3F-9D8A-2C9D0A8F1A11}
AppName=NeatCore
AppVersion={#MyAppVersion}
AppVerName=NeatCore {#MyAppVersion}
AppPublisher=AI Tools
DefaultDirName={pf64}\NeatCore
DefaultGroupName=NeatCore
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=dist-installer
OutputBaseFilename=NeatCore-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
; Paths are relative to this script in installer/ — go up one level
; Use generated icon.ico (built from assets/blue_icon.png via build_icon.py)
SetupIconFile={#RootDir}assets\icon.ico
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
VersionInfoVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Include the entire PyInstaller ONEDIR output (contains _internal/python312.dll)
#if FileExists(NeatExe)
Source: "{#NeatDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
	#if FileExists(OldExe)
	Source: "{#OldDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
	#else
		#error "Build not found. Build with PyInstaller to dist\\NeatCore or dist\\AI File Cleaner"
	#endif
#endif
; Include additional needed files (if any), like themes or assets
Source: "{#RootDir}assets\blue_icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "{#RootDir}assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
; If legacy EXE name is present, shortcuts will still work because only Filename matters
Name: "{group}\NeatCore"; Filename: "{app}\NeatCore.exe"; WorkingDir: "{app}"; Flags: createonlyiffileexists
Name: "{group}\NeatCore"; Filename: "{app}\AI File Cleaner.exe"; WorkingDir: "{app}"; Flags: createonlyiffileexists
Name: "{group}\Uninstall NeatCore"; Filename: "{uninstallexe}"
Name: "{userdesktop}\NeatCore"; Filename: "{app}\NeatCore.exe"; Tasks: desktopicon; Flags: createonlyiffileexists
Name: "{userdesktop}\NeatCore"; Filename: "{app}\AI File Cleaner.exe"; Tasks: desktopicon; Flags: createonlyiffileexists

[Run]
Filename: "{app}\\NeatCore.exe"; Description: "Launch NeatCore"; Flags: nowait postinstall skipifsilent; Check: FileExists(ExpandConstant('{app}\\NeatCore.exe'))
Filename: "{app}\\AI File Cleaner.exe"; Description: "Launch NeatCore"; Flags: nowait postinstall skipifsilent; Check: FileExists(ExpandConstant('{app}\\AI File Cleaner.exe'))

[Registry]
; Set AppUserModelID so Windows taskbar uses the app icon/grouping
Root: HKCU; Subkey: "Software\\Classes\\Applications\\NeatCore.exe\\AppUserModelId"; ValueType: string; ValueName: ""; ValueData: "neatcore.app"
