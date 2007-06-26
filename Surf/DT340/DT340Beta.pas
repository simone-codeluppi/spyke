unit DT340Beta;

interface

uses
  Windows, Messages, SysUtils, Classes, Graphics, Controls, Forms, Dialogs,
  StdCtrls, OleCtrls, DTxPascal, DTAcq32Lib_TLB;

type
  TForm1 = class(TForm)
    CT: TDTAcq32;
    Button1: TButton;
    Label1: TLabel;
    Button2: TButton;
    DIN: TDTAcq32;
    DIN2: TDTAcq32;
    Button3: TButton;
    Label2: TLabel;
    Label4: TLabel;
    Label3: TLabel;
    Label5: TLabel;
    procedure Button1Click(Sender: TObject);
    procedure CTSSEventDone(Sender: TObject; var lStatus: Integer);
    procedure Button2Click(Sender: TObject);
    procedure DINSSEventDone(Sender: TObject; var lStatus: Integer);
    procedure Button3Click(Sender: TObject);
  private
    { Private declarations }
  public
    { Public declarations }
  end;

var
  Form1: TForm1;
  i,j : integer;
  InputBuffer : array of byte;
  Stim_table : array [0..1000] of single;
  StatusBuffer : array of byte;
implementation

{$R *.DFM}

procedure TForm1.Button1Click(Sender: TObject);
begin
   Form1.DoubleBuffered:= true; //reduce flicker
   Button1.Tag:= not(Button1.Tag);
   CT.Board:= CT.BoardList[2];
   CT.SubSysType:= OLSS_CT;
   CT.SubSysElement:= 8;

   CT.ClockSource := OL_CLK_INTERNAL;
   CT.CTMode:= OL_CTMODE_RATE;//Multiple interrupts
   CT.GateType:= OL_GATE_NONE;//Software gate
   CT.Frequency:= 10;  //10Hz, interrupt every 1/10th second

   if Button1.Tag = -1 then
   begin
     Button1.Caption:= 'Stop Timer';
     CT.Config;
     CT.Start;
   end else
   begin
     Button1.Caption:= 'Start Timer';
     CT.Reset;
   end;
end;

procedure TForm1.CTSSEventDone(Sender: TObject; var lStatus: Integer);
begin
  Inc(i);
  Label1.Caption:= IntToStr(i div 10)+':'+IntToStr(i mod 10);
end;

procedure TForm1.Button2Click(Sender: TObject);
begin
  DIN.Board:= 'DT340';//DIN.BoardList[2];
  DIN.SubSysType:= OLSS_DIN;
  DIN.SubSysElement:= 3; //DT340 port D...
  DIN.Resolution:= 8; //...AOB6 port C
  DIN.DataFlow:= OL_DF_CONTINUOUS; //continuous, interrupt driven
//  DIN.Trigger:= OL_TRG_SOFT; //software triggered
  DIN.Config;
  DIN.Start;
  Button2.Caption:= 'DIN running';

  DIN2.Board:= 'DT340';//DIN.BoardList[2];
  DIN2.SubSysType:= OLSS_DIN;
  DIN2.SubSysElement:= 0; //DT340 ports A, B and C...
  DIN2.Resolution:= 24; //...AOB6 ports A and B
  DIN2.DataFlow:= OL_DF_SINGLEVALUE; //get single value
  DIN2.Config;
  SetLength(InputBuffer, 10000);
  SetLength(StatusBuffer, 10000);
  j:=0;
  i:=-2;
end;

procedure TForm1.DINSSEventDone(Sender: TObject; var lStatus: Integer);
var InputSVal : integer;
begin
  InputSVal:= (DIN2.GetSingleValue(0, 1.0)and $FFFF00) shr 8; //mask LSB that is N/C
  Inc(j);
  if (j mod 2) = 0 then exit; //skips every 2nd interrupt (ie. ignore falling edge of data strobe bit)
  //Label3.Caption:= Inttostr(j);
  //StatusBuffer[j]:= lStatus; //port A
  Inc (i,2);
  InputBuffer[i]:= InputSVal and $00FF; //port B
  InputBuffer[i+1]:= (InputSVal and $FF00) shr 8; //port C
end;

procedure TForm1.Button3Click(Sender: TObject);
var k : integer;
  RealPtr : ^Single;
  RealTemp : Single;
  MYCRC, NICKCRC : Word;
  CRCPtr : ^Word;
begin
  SetLength(InputBuffer, i);
  Label3.Caption:= Label3.Caption + inttostr(InputBuffer[4]);
  Label5.Caption:= Label5.Caption + inttostr(j);
   for k:= 4 to 19 do //filename up to 16 char long
    if InputBuffer[k] = 0 then break //null terminated
      else Label2.Caption:= Label2.Caption + Chr(InputBuffer[k]);
//?possible to replace preceeding code with some generic Delphi nul-term string command?

  CRCPtr := @(InputBuffer[Length(InputBuffer)-2]);
  NICKCRC:= CRCPtr^;
  MYCRC:= 0;
  for k:= 0 to Length(InputBuffer) - 1 do
    MYCRC:= MYCRC + InputBuffer[k];
  Showmessage('My CRC = ' + IntToStr(MYCRC)
            + '; Nick''s CRC = ' +  IntToStr(NICKCRC));
  k:= 20;

  {while k < (19 + j) do
  begin
    RealPtr := @InputBuffer[k];
    RealTemp := RealPtr^;
    Label4.Caption:= Label4.Caption
      + floattostr(RealTemp) + ', ';
    Inc (k,4);
  end;}
end;

end.