{ (c) 1994-1999 Phil Hetherington, P&M Research Technologies, Inc.}
{ (c) 2000-2003 Tim Blanche, University of British Columbia }
UNIT SurfTypes;
INTERFACE
USES Windows, Messages, SurfPublicTypes; { Graphics }
CONST
  WM_SURF_IN = WM_USER + 100;
  WM_SURF_OUT = WM_USER + 101;

CONST
   SURF_OUT_HANDLE          = 1000;
   SURF_OUT_PROBE           = 1001;
   SURF_OUT_SPIKE           = 1002;
   SURF_OUT_SPIKE_ARRAY     = 1003;
   SURF_OUT_CR              = 1004;
   SURF_OUT_CR_ARRAY        = 1005;
   SURF_OUT_SV              = 1006;
   SURF_OUT_SV_ARRAY        = 1007;
   SURF_OUT_MSG             = 1008;
   SURF_OUT_MSG_ARRAY       = 1009;
   SURF_OUT_SURFEVENT       = 1010;
   SURF_OUT_SURFEVENT_ARRAY = 1011;
   SURF_OUT_FILESTART       = 1012;
   SURF_OUT_FILEEND         = 1013;

   SURF_IN_HANDLE    = 2000;
   SURF_IN_SPIKE     = 2001;
   SURF_IN_CR        = 2002;
   SURF_IN_SV        = 2003;
   SURF_IN_DAC       = 2004;
   SURF_IN_DIO       = 2005;
   SURF_IN_READFILE  = 2006;
   SURF_IN_SAVEFILE  = 2007;

TYPE
{ Surf uses a format similar to DW's uff data file structure.  The major difference is the
  absence of most of the records, and the unification of all spike and continuous records into
  one called the POLYTRODE record.  The POLYTRODE record can have 3 subtypes, the SPIKEEPOCH, SPIKESTREAM,
  and the CONTINUOUS.  Both can have any length waveform.  The SPIKETYPE can have any number of
  channels, but the CONTINUOUSTYPE can have only one channel. In addition there are singlevalue
  records, for the storage of single 2B words, and mesg records, for the storage of 256B ShortStrings}

  SURF_LAYOUT_REC = record { Type for all probe layout records }
    UffType         : CHAR; // Record type 'L' @0
    TimeStamp       : INT64;// Time stamp, 64 bit signed int @10?
    SurfMajor       : BYTE; // SURF major version number @18?
    SurfMinor       : BYTE; // SURF minor version number @19?
    MasterClockFreq : LNG;  // ADC/precision CT master clock frequency (1Mhz for DT3010) // @20
    BaseSampleFreq  : LNG;  // undecimated base sample frequency per channel // @24
    DINAcquired     : Boolean; //true if Stimulus DIN acquired // @28, boolean is 2 bytes long, 1 for True, 0 for False?

    Probe          : SHRT; // probe number @ 30
    ProbeSubType   : CHAR; // =E,S,C for epochspike, spikestream, or continuoustype @ 32
    nchans         : SHRT; // number of channels in the probe
    pts_per_chan   : SHRT; // number of samples per waveform per channel (display)
    pts_per_buffer : LNG;  // {n/a to cat9} total number of samples per file buffer for this probe (redundant with SS_REC.NumSamples)
    trigpt         : SHRT; // pts before trigger
    lockout        : SHRT; // Lockout in pts
    threshold      : SHRT; // A/D board threshold for trigger
    skippts        : SHRT; // A/D sampling decimation factor
    sh_delay_offset: SHRT; // S:H delay offset for first channel of this probe
    sampfreqperchan: LNG;  // A/D sampling frequency specific to this probe (ie. after decimation, if any)
    extgain        : array[0..SURF_MAX_CHANNELS-1] of WORD; // MOVE BACK TO AFTER SHOFFSET WHEN FINISHED WITH CAT 9!!! added May 21'99
    intgain        : SHRT; // A/D board internal gain <--MOVE BELOW extgain after finished with CAT9!!!!!
    chanlist       : TChanList; //v1.0 had chanlist to be an array of 32 ints.  Now it is an array of 64, so delete 32*4=128 bytes from end
    probe_descrip  : ShortString;
    electrode_name : ShortString;
    ProbeWinLayout : TProbeWinLayout; //MOVE BELOW CHANLIST FOR CAT 9 v1.0 had ProbeWinLayout to be 4*32*2=256 bytes, now only 4*4=16 bytes, so add 240 bytes of pad
    pad            : array[0..879 {remove for cat 9!!!-->}- 4{pts_per_buffer} - 2{SHOffset}] of BYTE; {pad for future expansion/modification}
  end;

  SURF_SE_REC    = record // SpikeEpoch record
    UffType      : char;  {1 byte} {SURF_PT_REC_UFFTYPE}
    SubType      : char;  {1 byte} {=E,S,C for spike epoch, continuous spike or other continuous }
    TimeStamp    : INT64; {Cardinal, 64 bit signed int}
    Probe        : shrt;  {2 bytes -- the probe number}
    Cluster      : shrt;  {2 bytes}
    ADCWaveform  : TWaveForm {ADC Waveform type; dynamic array of SHRT (signed 16 bit)}
  end;

  SURF_SS_REC    = record // SpikeStream record
    UffType      : char;    {1 byte} {SURF_PT_REC_UFFTYPE}
    SubType      : char;    {1 byte} {=E,S,C for spike epoch, continuous spike or other continuous }
    TimeStamp    : INT64;   {Cardinal, 64 bit signed int}
    Probe        : shrt;    {2 bytes -- the probe number}
    CRC32        : {u}LNG;  {4 bytes -- PKZIP-compatible CRC}
    NumSamples   : integer; {4 bytes -- the # of samples in this file buffer record}
    ADCWaveform  : TWaveForm{ADC Waveform type; dynamic array of SHRT (signed 16 bit)}
  end;

  SURF_SV_REC = record // Single value record
    UffType   : char; //1 byte -- SURF_SV_REC_UFFTYPE
    SubType   : char; //1 byte -- 'D' digital or 'A' analog
    TimeStamp : INT64;//Cardinal, 64 bit signed int
    SVal      : word; //2 bytes -- 16 bit single value
  end;

  SURF_MSG_REC = record // Message record
    UffType    : char; //1 byte -- SURF_MSG_REC_UFFTYPE
    SubType    : char; //1 byte -- 'U' user or 'S' Surf-generated
    TimeStamp  : INT64; //Cardinal, 64 bit signed int
    DateTime   : TDateTime; //8 bytes -- double
    MsgLength  : integer;//4 bytes -- length of the msg string
    Msg        : string{shortstring - for cat9!!!}; //any length message
  end;

  SURF_DSP_REC = record // Stimulus display header record
    UffType    : char;  //1 byte -- SURF_MSG_REC_UFFTYPE
    TimeStamp  : INT64;  //Cardinal, 64 bit signed int
    DateTime   : TDateTime; //double, 8 bytes
    Header     : TStimulusHeader;
  end;

  TBufDesc = record
    d1,d2,d3,d4,d5 : integer;
  end;

IMPLEMENTATION
END.