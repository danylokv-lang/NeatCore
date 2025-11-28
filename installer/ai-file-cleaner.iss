; Inno Setup Script for NeatCore
; Build prerequisites:
; 1) Create a Windows executable with PyInstaller
;    pyinstaller --noconsole --name "NeatCore" --icon assets/app.ico main.py
;    Output will be under dist\NeatCore\NeatCore.exe
; 2) Then compile this script in Inno Setup to produce the installer.

#define RootDir AddBackslash(SourcePath) + "..\\"
#define NeatExe AddBackslash(RootDir) + "dist\\NeatCore\\NeatCore.exe"
#define NeatDir AddBackslash(RootDir) + "dist\\NeatCore"
#define OldExe  AddBackslash(RootDir) + "dist\\AI File Cleaner\\AI File Cleaner.exe"
#define OldDir  AddBackslash(RootDir) + "dist\\AI File Cleaner"

[Setup]
AppId={{6C2E5B3A-3B4A-4A3F-9D8A-2C9D0A8F1A11}
AppName=NeatCore
AppVersion=1.0.0
AppPublisher=AI Tools
DefaultDirName={pf64}\NeatCore
DefaultGroupName=NeatCore
DisableDirPage=no
DisableProgramGroupPage=no
OutputDir=dist-installer
OutputBaseFilename=NeatCore-Setup
Compression=lzma
SolidCompression=yes
; Paths are relative to this script in installer/ — go up one level
; Remove app.ico; optional: set wizard images to PNG
;SetupIconFile is omitted to avoid .ico; Inno will use default
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

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
Source: "{#RootDir}assets\icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

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
