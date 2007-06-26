unit diskstream;

interface

uses
  Windows, Messages, SysUtils, Classes, Graphics, Controls, Forms, Dialogs,
  StdCtrls;

type
  TForm3 = class(TForm)
    Button1: TButton;
    Label1: TLabel;
    Label2: TLabel;
    Label3: TLabel;
    Label4: TLabel;
    procedure Button1Click(Sender: TObject);
  private
    { Private declarations }
  public
    { Public declarations }
  end;

var
  Form3: TForm3;

implementation

uses SurfMathLibrary; {for CRC32}

{$R *.DFM}

procedure TForm3.Button1Click(Sender: TObject);
var
  Start: TDateTime;
  ElapsedSeconds: single;

  F : TFileStream;
  i : Integer;
  j : array [0..65535] of byte;
  p : pointer;
  runningCRC : DWord;
  fileCRC32 : Cardinal;
  errorword : Word;
  filebytes : Int64;
begin
  RunningCRC:= $FFFFFFFF; //arbitrary, needed only if you want to match PKZIP
  for i:= 0 to 65536 - 1 do
    j[i]:= random(256);
  p := @j[0];
  F := TFileStream.Create('C:\Desktop\SomeFile.txt', fmCreate);
  Start:=Now;
  try
    F.Seek(0, soFromBeginning); // Vital! Do not forget!
    for i := 0 to 1000 - 1 do
    begin
      F.Write(j, 65536);
      CalcCRC32(p, 65536, runningCRC);
      Label2.Caption:= inttohex(not runningCRC, 8);
      Label2.Update;
    end;
  finally
    ElapsedSeconds:=(now-start)*SecsPerDay;
    Showmessage('Writing speed = '+ floattostr(F.Size / ElapsedSeconds /1000000)
              + 'Mb/sec');
    FileBytes:= F.Size;
    F.Free;
  end;
  Application.ProcessMessages;
  CalcFileCRC32('C:\Desktop\SomeFile.txt', fileCRC32, filebytes, errorword);
  Label3.Caption:= inttohex(not fileCRC32, 8);
  {if fileCRC32 <> runningCRC then Label3.Color:= clRed else}Label3.Color:= clLime;
  if errorword <> 0 then showmessage('Error!');
end;

end.