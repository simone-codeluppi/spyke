program ElectroPlate;

uses
  Forms,
  ElectroPlateMain in 'ElectroPlateMain.pas' {EPlateMainForm},
  SurfPublicTypes in '..\Public\SurfPublicTypes.pas',
  ElectrodeTypes in '..\Surf\ElectrodeTypes.pas',
  PolytrodeGUI in '..\SurfBawd\PolytrodeGUI.pas' {PolytrodeGUIForm};

{$R *.RES}

begin
  Application.Initialize;
  Application.CreateForm(TEPlateMainForm, EPlateMainForm);
  Application.Run;
end.

