unit PolytrodeGUI;

interface

uses
  Windows, Messages, SysUtils, Classes, Graphics, Controls, Forms, Dialogs,
  ElectrodeTypes, ExtCtrls, ImgList;

const ELECTRODEBORDER = 50;
      XYSCALE = 2.7{1.4};

type
  TPolytrodeGUIForm = class(TForm)
    ilNeuronIcons: TImageList;
    procedure FormMouseMove(Sender: TObject; Shift: TShiftState; X,
                            Y: Integer);
    procedure FormMouseDown(Sender: TObject; Button: TMouseButton;
                            Shift: TShiftState; X, Y: Integer);
    procedure FormMouseUp(Sender: TObject; Button: TMouseButton;
                          Shift: TShiftState; X, Y: Integer);
    procedure FormPaint(Sender: TObject);
    procedure FormCreate(Sender: TObject);
    procedure FormClose(Sender: TObject; var Action: TCloseAction);
    procedure FormKeyDown(Sender: TObject; var Key: Word;
      Shift: TShiftState);
    procedure FormDblClick(Sender: TObject);
  private
    ebm : TBitmap;
    Electrode : TElectrode;
    xoff, yoff : integer;
    StartX, StartY: integer;
    procedure DrawElectrode;
    function  MouseXY2Site(const X, Y : integer;
                             var Site : integer) : boolean;
    procedure SelectSites (const X, Y : integer;
                           var Sites : array of boolean);
    { Private declarations }
  public
    Online : boolean;
    SiteSelected : array [0..63{SURF_MAX_CHANNELS}] of boolean;
    m_iNSitesSelected, LastChanSelect : integer;
    function ChangeSiteColor(Site : ShortInt; Color : TColor = 0{default}) : boolean;
    function CreateElectrode(ElectrodeName : ShortString; IsOnline : boolean = false) : boolean;
    procedure PlotNeuronPosn(XYPosition : TPoint);
    procedure PlotNeuronField(FieldBounds : TRect; XYCentre : TPoint;
                              Color : TColor; PenMode : TPenMode; PenWidth : integer);
    procedure ReduceFlicker(var message:TWMEraseBkgnd); message WM_ERASEBKGND; //stops WM backgnd repaints
    { Public declarations }
  end;

var
  PolytrodeGUIForm: TPolytrodeGUIForm;

implementation

{$R *.DFM}

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormCreate(Sender: TObject);
begin
  ebm:= TBitmap.Create;
  ebm.PixelFormat:= pf24bit;
  ControlStyle:= ControlStyle + [csOpaque]; //reduce flicker
  //DoubleBuffered:= True; unnecessary
end;

{-------------------------------------------------------------------------------}
function TPolytrodeGUIForm.CreateElectrode(ElectrodeName : ShortString;
                                           IsOnline : boolean{default = false}) : boolean;
var maxx,minx,maxy,miny,i : integer;
begin
  Online:= IsOnline; //if true, user cannot move probe about window
  if not GetElectrode(Electrode, ElectrodeName) then
  begin
    CreateElectrode := FALSE;
    ShowMessage(ElectrodeName+' is an unknown electrode');
    Exit;
  end else
  with Electrode do
  begin
    if NumPoints > MAXELECTRODEPOINTS then NumPoints := MAXELECTRODEPOINTS;
    minx := 10000;
    miny := 10000;
    maxx := -10000;
    maxy := -10000;
    {scale probe up/down to size}
    for i:= 0 to NumSites-1 do
    begin
      SiteLoc[i].x:= Round(SiteLoc[i].x / XYSCALE);
      SiteLoc[i].y:= Round(SiteLoc[i].y / XYSCALE);
    end;
    for i:= 0 to NumPoints-1 do
    begin
      Outline[i].x:= Round(Outline[i].x / XYSCALE);
      Outline[i].y:= Round(Outline[i].y / XYSCALE);
    end;
    CenterX:= Round(CenterX / XYSCALE);
    TopLeftSite.x:= Round(TopLeftSite.x / XYSCALE);
    TopLeftSite.y:= Round(TopLeftSite.y / XYSCALE);
    BotRightSite.x:= Round(BotRightSite.x / XYSCALE);
    BotRightSite.y:= Round(BotRightSite.y / XYSCALE);
    SiteSize.x:= Round(SiteSize.x / XYSCALE);
    SiteSize.y:= Round(SiteSize.y / XYSCALE);
    for i := 0 to NumSites-1 do
    begin
      if minx > SiteLoc[i].x then minx := SiteLoc[i].x;
      if miny > SiteLoc[i].y then miny := SiteLoc[i].y;
      if maxx < SiteLoc[i].x then maxx := SiteLoc[i].x;
      if maxy < SiteLoc[i].y then maxy := SiteLoc[i].y;
    end;
    TopLeftSite.x := minx;
    TopLeftSite.y := miny;
    BotRightSite.x := maxx;
    BotRightSite.y := maxy;

    minx := minx - ELECTRODEBORDER;
    miny := miny - ELECTRODEBORDER;
    maxx := maxx + ELECTRODEBORDER;
    maxy := maxy + ELECTRODEBORDER;
    For i := 0 to NumPoints-1 do
    begin
      if minx > Outline[i].x then minx := Outline[i].x;
      if miny > Outline[i].y then miny := Outline[i].y;
      if maxx < Outline[i].x then maxx := Outline[i].x;
      if maxy < Outline[i].y then maxy := Outline[i].y;
    end;
    Created := TRUE;
  end;

  with ebm do
  begin
    Canvas.Font.Name:= 'Small fonts';
    Canvas.Font.Size:= 16{base font size};
    Canvas.Font.Size:= Round(Canvas.Font.Size / XYSCALE);
    if Canvas.Font.Size < 6 then Canvas.Font.Size:= 6; //below 6 becoming illegible
    Width := maxx-minx;
    Height :=maxy-miny;
  end;
  ClientWidth:= ebm.Width;
  if ebm.Height > Screen.Height then ClientHeight:= Screen.Height-50
    else ClientHeight:= ebm.Height;
  xoff:= -minx;
  yoff:= -miny-10;

  m_iNSitesSelected:= 0;
  CreateElectrode:= True;
  DrawElectrode;
end;

{--------------------------------------------------------------------}
procedure TPolytrodeGUIForm.DrawElectrode;
var i : integer;
begin
  with Electrode, ebm.Canvas do
  begin
    Brush.Color := clBlack;
    FillRect(ClientRect); //clear background
    Font.Color  := clDkGray;
    Pen.Color   := clDkGray;
    MoveTo(Outline[0].x+xoff, Outline[0].y+xoff);
    Pen.Color:= RGB(48,64,48);
    for i:= 0 to NumPoints-1 do //draw electrode outline
      LineTo(Outline[i].x+xoff, OutLine[i].y+yoff);
    Brush.Color:= RGB(48,64,48); //next line is a patch to fix 'disappearing shank' bug
    if OutLine[0].y+yoff < 2 then FloodFill(Outline[0].x+xoff+1, 2, RGB(48,64,48),fsborder{fol.fillstyle})
      else FloodFill(Outline[0].x+xoff+1,Outline[0].y+yoff+1,RGB(48,64,48),fsborder{fol.fillstyle});
    for i := 0 to NumSites-1 do //draw electrode sites
    begin
      {if i = MUX2EIB[ActiveChanNumber]-1 then Brush.Color:= GUISiteCol //active site
        else Brush.Color := $005E879B;}
      Brush.Color := RGB(48, 64, 48); //draw site numbers
      TextOut(SiteLoc[i].x+SiteSize.x div 2+xoff, SiteLoc[i].y+yoff,inttostr(i));
      if SiteSelected[i] then Brush.Color:= clLime
        else Brush.Color:= $005E879B;
      case RoundSite of
        True : Ellipse(SiteLoc[i].x-SiteSize.x div 2+xoff,SiteLoc[i].y-SiteSize.y div 2+yoff,
                       SiteLoc[i].x+SiteSize.x div 2+xoff,SiteLoc[i].y+SiteSize.y div 2+yoff);
        False: Framerect(Rect(SiteLoc[i].x-SiteSize.x div 2+xoff,SiteLoc[i].y-SiteSize.y div 2+yoff,
                         SiteLoc[i].x+SiteSize.x div 2+xoff,SiteLoc[i].y+SiteSize.y div 2+yoff));
      end;
    end;
  end{with};
  Paint; //blit ebm to GUIform's canvas
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormMouseDown(Sender: TObject;
  Button: TMouseButton; Shift: TShiftState; X, Y: Integer);
begin
  if ssLeft in Shift then
  begin
    StartX:= X;
    StartY:= Y;
  end else
  if not Online and (ssRight in Shift) then
  begin
    StartX:= X-xoff;
    StartY:= Y-yoff;
    Screen.Cursor := crSizeAll;
  end;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormMouseMove(Sender: TObject;
  Shift: TShiftState; X, Y: Integer);
begin
  if ssLeft in Shift then
  begin
    Screen.Cursor:= crCross;
    Paint; //erase last rectangle
    Canvas.Brush.Style:= bsClear;
    Canvas.Pen.Color:= clWhite;
    Canvas.Rectangle(StartX, StartY, X, Y);
  end else
  if not Online and (ssRight in Shift) then //move electrode about canvas
  begin
    xoff:= X-StartX;
    yoff:= Y-StartY;
    //constrain drag...
    if yoff < -Electrode.BotRightSite.y then yoff:= -Electrode.BotRightSite.y
      else if yoff > ClientHeight - 100 then yoff:= ClientHeight - 100;
    if xoff < ELECTRODEBORDER then xoff:= ELECTRODEBORDER
      else if xoff > ClientWidth-ELECTRODEBORDER then xoff:= ClientWidth-ELECTRODEBORDER;
    DrawElectrode;
  end;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormMouseUp(Sender: TObject;
  Button: TMouseButton; Shift: TShiftState; X, Y: Integer);
begin
  Screen.Cursor:= crArrow; //restore normal pointer
  if Button = mbLeft then
    if MouseXY2Site(X,Y, LastChanSelect) then //select/deselect single site
    begin
      SiteSelected[LastChanSelect]:= not(SiteSelected[LastChanSelect]); //toggle selection
      if SiteSelected[LastChanSelect] then inc(m_iNSitesSelected)
        else dec(m_iNSitesSelected);
      DrawElectrode; {EPlateMainForm.ChanSelect.Value:= SITE2MUX[LastChanSelect+1];}
    end else
    begin //select/deselect multiple sites
      SelectSites(X, Y, SiteSelected);
      DrawElectrode;
    end;
end;

{-------------------------------------------------------------------------------}
function TPolytrodeGUIForm.MouseXY2Site(const X, Y : integer;
                                          var Site : integer) : boolean;
var i : integer;
begin
  with Electrode do
  begin
    for i := 0 to NumSites -1 do
    begin
      if  (X-xoff > (SiteLoc[i].x-Sitesize.x div 2))
      and (X-xoff < (SiteLoc[i].x+Sitesize.x div 2))
      and (Y-yoff > (SiteLoc[i].y-Sitesize.y div 2))
      and (Y-yoff < (SiteLoc[i].y+Sitesize.y div 2)) then
      begin
        Site:= i;
        Result:= True;
        Exit;
      end;
    end;
    Result:= False;
  end;
end;


{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.SelectSites(const X, Y : integer;
                                        var Sites  : array of boolean);
var s, minX, minY, maxX, maxY : integer;
begin
  {get bounds of selection box}
  if X < StartX then
  begin
    minX:= X;
    maxX:= StartX;
  end else
  begin
    minX:= StartX;
    maxX:= X;
  end;
  if Y < StartY then
  begin
    minY:= Y;
    maxY:= StartY;
  end else
  begin
    minY:= StartY;
    maxY:= Y;
  end;
  {check which sites within bounds}
  with Electrode do
  begin
    for s:= 0 to NumSites -1 do
    begin
      if  (SiteLoc[s].x > minX-xoff)
      and (SiteLoc[s].x < maxX-xoff)
      and (SiteLoc[s].y > minY-yoff)
      and (SiteLoc[s].y < maxY-yoff) then
      begin
        SiteSelected[s]:= not(SiteSelected[s]);
        if SiteSelected[s] then inc(m_iNSitesSelected)
          else dec(m_iNSitesSelected);
      end;
     {SiteSelected[s]:= True
      else
        SiteSelected[s]:= False;}
    end;
  end;
end;

{-------------------------------------------------------------------------------}
function TPolytrodeGUIForm.ChangeSiteColor(Site : ShortInt; Color : TColor) : boolean;
begin
  {dec(Site); //zero-based site numbering at this stage
  if site < 0 then
  begin
    Result:= False;
    Exit;
  end;}
  with ebm.Canvas, Electrode do
  begin
    if Color = 0{not specified} then
    begin
      if SiteSelected[site] then Brush.Color:= clLime
        else Brush.Color:= $005E879B;
    end else
      Brush.Color:= Color;
    case RoundSite of
      True  : Ellipse(SiteLoc[site].x-SiteSize.x div 2+xoff,SiteLoc[site].y-SiteSize.y div 2+yoff,
                      SiteLoc[site].x+SiteSize.x div 2+xoff,SiteLoc[site].y+SiteSize.y div 2+yoff);
      False : Framerect(rect(SiteLoc[site].x-SiteSize.x div 2+xoff,SiteLoc[site].y-SiteSize.y div 2+yoff,
                        SiteLoc[site].x+SiteSize.x div 2+xoff,SiteLoc[site].y+SiteSize.y div 2+yoff));
    end;
    {Brush.Color := RGB(48, 64, 48); //draw site lockout
    TextOut(SiteLoc[site].x-SiteSize.x-1+xoff, SiteLoc[site].y+yoff-10,inttostr(lockcnt));}
  end;
  Result:= True;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormPaint(Sender: TObject);
begin
  Canvas.Draw(0, 0, ebm); //repaint electrode onto canvas
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormClose(Sender: TObject;
  var Action: TCloseAction);
begin
  ebm.Free; //free memory for electrode bitmap...
  Action := caFree;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormKeyDown(Sender: TObject; var Key: Word;
  Shift: TShiftState);
var s : integer;
begin
  if ssCtrl in Shift then
  begin
    if Key = Ord('A') then {select all sites}
    begin
      for s:= 0 to Electrode.NumSites -1 do
        SiteSelected[s]:= True;
      m_iNSitesSelected:= Electrode.NumSites;
    end else
    if Key = Ord('D') then {select no sites}
    begin
      for s:= 0 to Electrode.NumSites -1 do
        SiteSelected[s]:= False;
      m_iNSitesSelected:= 0;
    end;
    DrawElectrode;
  end;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.FormDblClick(Sender: TObject);
var s : integer;
begin
  if m_iNSitesSelected = 0 then
  begin //select all sites
    for s:= 0 to Electrode.NumSites -1 do
      SiteSelected[s]:= True;
    m_iNSitesSelected:= Electrode.NumSites;
  end else
  begin //clear all sites...
    for s:= 0 to Electrode.NumSites -1 do
      SiteSelected[s]:= False;
    m_iNSitesSelected:= 0;
  end;
  DrawElectrode;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.PlotNeuronPosn(XYPosition : TPoint);
var w, h : integer;
begin
  with ilNeuronIcons do
  begin
    w:= width div 2;
    h:= height div 2;
    Draw(ebm.Canvas, Round(XYPosition.x / XYSCALE) + xoff - w,
                     Round(XYPosition.y / XYSCALE) + yoff - h, 0);
  end;
end;

{-------------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.PlotNeuronField(FieldBounds : TRect; XYCentre : TPoint;
                                            Color : TColor; PenMode : TPenMode; PenWidth : integer);
begin
  with ebm.Canvas, FieldBounds, XYCentre do
  begin
    Pen.Mode:= PenMode;
    Pen.Width:= PenWidth;
    Brush.Style:= bsClear;
    Pen.Color:= Color;// and $00808080;
    FieldBounds.Top:= Round((Top + y) / XYSCALE) + yoff;
    FieldBounds.Bottom:= Round((Bottom + y) / XYSCALE) + yoff;
    FieldBounds.Left:= Round((Left + x) / XYSCALE) + xoff;
    FieldBounds.Right:= Round((Right + x) / XYSCALE) + xoff;
    Rectangle(FieldBounds);
  end;
end;

{-------------------------------------------------------------------------}
procedure TPolytrodeGUIForm.ReduceFlicker(var message:TWMEraseBkgnd);
begin
  message.result:= 1; //inhibit WM repaints
end;

end.