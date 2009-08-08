"""Core classes and functions used throughout spyke"""

from __future__ import division
from __future__ import with_statement

__authors__ = ['Martin Spacek', 'Reza Lotun']

import cPickle
import gzip
import hashlib
import time
import os

import wx

import numpy as np

# set some numpy options - will these hold for all modules in spyke?
np.set_printoptions(precision=3)
np.set_printoptions(threshold=1000)
np.set_printoptions(edgeitems=5)
np.set_printoptions(linewidth=150)
np.set_printoptions(suppress=True)

from matplotlib.colors import hex2color

from spyke import probes

MU = '\xb5' # greek mu symbol

DEFHIGHPASSSAMPFREQ = 50000 # default (possibly interpolated) high pass sample frequency, in Hz
DEFHIGHPASSSHCORRECT = True
KERNELSIZE = 12 # apparently == number of kernel zero crossings, but that seems to depend on the phase of the kernel, some have one less. Anyway, total number of points in the kernel is this plus 1 (for the middle point) - see Blanche2006
assert KERNELSIZE % 2 == 0 # I think kernel size needs to be even
NCHANSPERBOARD = 32 # TODO: stop hard coding this

MAXLONGLONG = 2**63-1


class WaveForm(object):
    """Just a container for data, timestamps, and channels.
    Sliceable in time, and indexable in channel space"""
    def __init__(self, data=None, ts=None, chans=None):
        self.data = data # in AD, potentially multichannel, depending on shape
        self.ts = ts # timestamps array in us, one for each sample (column) in data
        self.chans = chans # channel ids corresponding to rows in .data. If None, channel ids == data row indices

    def __getitem__(self, key):
        """Make waveform data sliceable in time, and directly indexable by channel id.
        Return a new WaveForm"""
        if type(key) == slice: # slice self in time
            if self.ts == None:
                return WaveForm() # empty WaveForm
            else:
                lo, hi = self.ts.searchsorted([key.start, key.stop])
                data = self.data[:, lo:hi]
                ts = self.ts[lo:hi]
                #if np.asarray(data == self.data).all() and np.asarray(ts == self.ts).all():
                #    return self # no need for a new WaveForm - but new WaveForms aren't expensive, only new data are
                return WaveForm(data=data, ts=ts, chans=self.chans) # return a new WaveForm
        else: # index into self by channel id(s)
            keys = toiter(key)
            chans = np.asarray(self.chans)
            keys = [ key for key in keys if key in chans ] # ignore keys outside of chans while preserving order in keys
            # using a set changes the order within keys
            #keys = list(set(chans).intersection(keys)) # ignore keys outside of chans
            i = [ int(np.where(chan == chans)[0]) for chan in keys ] # list of appropriate indices into the rows of self.data
            # TODO: should probably use .take here for speed:
            data = self.data[i] # grab the appropriate rows of data
            return WaveForm(data=data, ts=self.ts, chans=keys) # return a new WaveForm

    def __len__(self):
        """Number of data points in time"""
        nt = len(self.ts)
        assert nt == self.data.shape[1] # obsessive
        return nt

    def _check_add_sub(self, other):
        """Check a few things before adding or subtracting waveforms"""
        if self.data.shape != other.data.shape:
            raise ValueError("Waveform shapes %r and %r don't match" %
                             (self.data.shape, other.data.shape))
        if self.chans != other.chans:
            raise ValueError("Waveform channel ids %r and %r don't match" %
                             (self.chans, other.chans))

    def __add__(self, other):
        """Return new waveform which is self+other. Keep self's timestamps"""
        self._check_add_sub(other)
        return WaveForm(data=self.data+other.data,
                        ts=self.ts, chans=self.chans)

    def __sub__(self, other):
        """Return new waveform which is self-other. Keep self's timestamps"""
        self._check_add_sub(other)
        return WaveForm(data=self.data-other.data,
                        ts=self.ts, chans=self.chans)
    '''
    def get_padded_data(self, chans):
        """Return self.data corresponding to self.chans,
        padded with zeros for chans that don't exist in self"""
        common = set(self.chans).intersection(chans) # overlapping chans
        dtype = self.data.dtype # self.data corresponds to self.chans
        padded_data = np.zeros((len(chans), len(self.ts)), dtype=dtype) # padded_data corresponds to chans
        chanis = [] # indices into self.chans corresponding to overlapping chans
        commonis = [] # indices into chans corresponding to overlapping chans
        for chan in common:
            chani, = np.where(chan == np.asarray(self.chans))
            commoni, = np.where(chan == np.asarray(chans))
            chanis.append(chani)
            commonis.append(commoni)
        chanis = np.concatenate(chanis)
        commonis = np.concatenate(commonis)
        padded_data[commonis] = self.data[chanis] # for overlapping chans, overwrite the zeros with data
        return padded_data
    '''

class Stream(object):
    """Data stream object - provides convenient stream interface to .srf files.
    Maps from timestamps to record index of stream data to retrieve the
    approriate range of waveform data from disk"""
    def __init__(self, srff, kind='highpass', sampfreq=None, shcorrect=None, endinclusive=False):
        """Takes a sorted temporal (not necessarily evenly-spaced, due to pauses in recording)
        sequence of ContinuousRecords: either HighPassRecords or LowPassMultiChanRecords.
        sampfreq arg is useful for interpolation. Assumes that all HighPassRecords belong
        to the same probe"""
        self.srff = srff
        self.kind = kind
        if kind == 'highpass':
            self.ctsrecords = srff.highpassrecords
        elif kind == 'lowpass':
            self.ctsrecords = srff.lowpassmultichanrecords
        else:
            raise ValueError('Unknown stream kind %r' % kind)
        self.layout = self.ctsrecords[0].layout
        self.intgain = self.layout.intgain
        self.extgain = int(self.layout.extgain[0]) # assume extgain is the same for all chans in this layout
        self.srffname = os.path.basename(self.srff.fname) # filename excluding path
        self.rawsampfreq = self.layout.sampfreqperchan
        self.rawtres = int(round(1 / self.rawsampfreq * 1e6)) # us
        self.nchans = len(self.layout.ADchanlist)
        if kind == 'highpass':
            self.chans = range(self.nchans) # probe chans, as opposed to AD chans, don't know yet of any probe
                                            # type whose chans aren't contiguous from 0 (see probes.py)
            self.sampfreq = sampfreq or DEFHIGHPASSSAMPFREQ # desired sampling frequency
            self.shcorrect = shcorrect or DEFHIGHPASSSHCORRECT
        elif kind == 'lowpass':
            self.chans = self.layout.chans # probe chan values already parsed from LFP probe description
            self.sampfreq = sampfreq or self.rawsampfreq # don't resample by default
            self.shcorrect = shcorrect or False # don't s+h correct by default
        self.endinclusive = endinclusive
        self.rts = np.asarray([ctsrecord.TimeStamp for ctsrecord in self.ctsrecords]) # array of ctsrecord timestamps
        # check whether self.rts values are all equally spaced,
        # indicating there were no pauses in recording. Then, set a flag
        self.contiguous = (np.diff(self.rts, n=2) == 0).all()
        if not self.contiguous:
            print('***NOTE: time gaps exist in recording, probably due to pauses')
        probename = self.layout.electrode_name
        probename = probename.replace(MU, 'u') # replace any 'micro' symbols with 'u'
        probetype = eval('probes.' + probename) # yucky. TODO: switch to a dict with keywords?
        self.probe = probetype() # instantiate it

        self.t0 = self.rts[0] # us, time that recording began, time of first recorded data point
        lastctsrecordnt = int(round(self.ctsrecords[-1].NumSamples / self.probe.nchans)) # nsamples in last record
        self.tend = self.rts[-1] + (lastctsrecordnt-1)*self.rawtres # time of last recorded data point

    def get_sampfreq(self):
        return self._sampfreq

    def set_sampfreq(self, sampfreq):
        """On .sampfreq change, delete .kernels (if set), try to switch
        classes to use a .resample file (if available), and update .tres"""
        self._sampfreq = sampfreq
        try:
            del self.kernels
        except AttributeError:
            pass
        self.try_switch()
        self.tres = int(round(1 / self.sampfreq * 1e6)) # us, for convenience

    sampfreq = property(get_sampfreq, set_sampfreq)

    def get_shcorrect(self):
        return self._shcorrect

    def set_shcorrect(self, shcorrect):
        """On .shcorrect change, deletes .kernels (if set), and try to
        switch classes to use a .resample file (if available)"""
        self._shcorrect = shcorrect
        try:
            del self.kernels
        except AttributeError:
            pass
        self.try_switch()

    shcorrect = property(get_shcorrect, set_shcorrect)

    def __len__(self):
        """Total number of timepoints? Length in time? Interp'd or raw?"""
        raise NotImplementedError

    def __getitem__(self, key):
        """Called when Stream object is indexed into using [] or with a slice object, indicating
        start and end timepoints in us. Returns the corresponding WaveForm object, which has as
        its attribs the 2D multichannel waveform array as well as the timepoints, potentially
        spanning multiple ContinuousRecords"""
        tslice = time.clock()
        # for now, accept only slice objects as keys
        #assert type(key) == slice
        # key.step == -1 indicates we want the returned Waveform reversed in time
        # key.step == None behaves the same as key.step == 1
        if key.step in [None, 1]:
            start, stop = key.start, key.stop
        elif key.step == -1:
            start, stop = key.stop, key.start # reverse start and stop, now start should be < stop
        else:
            raise ValueError('unsupported slice step size: %s' % key.step)

        resample = self.sampfreq != self.rawsampfreq or self.shcorrect == True
        if resample:
            # excess data in us at either end, to eliminate interpolation distortion at our desired start and stop
            xs = KERNELSIZE * self.rawtres
        else:
            xs = 0

        # Find the first and last records corresponding to the slice. If the start of the slice
        # matches a record's timestamp, start with that record. If the end of the slice matches a record's
        # timestamp, end with that record (even though you'll only potentially use the one timepoint from
        # that record, depending on the value of 'endinclusive')"""
        #trts = time.clock()
        lorec, hirec = self.rts.searchsorted([start-xs, stop+xs], side='right') # TODO: this might need to be 'left' for step=-1
        #print('rts.searchsorted() took %.3f sec' % (time.clock()-trts)) # this takes 0 sec

        # We always want to get back at least 1 record (ie records[0:1]). When slicing, we need to do
        # lower bounds checking (don't go less than 0), but not upper bounds checking
        cutrecords = self.ctsrecords[max(lorec-1, 0):max(hirec, 1)]
        recorddatas = []
        tload = time.clock()
        for record in cutrecords:
            try:
                recorddata = record.data
            except AttributeError:
                recorddata = record.load(self.srff.f) # to save time, only load the waveform if it's not already loaded
            recorddatas.append(recorddata)
        nchans, nt = recorddatas[0].shape # assume all are same shape, except maybe last one
        totalnt = nt*(len(recorddatas) - 1) + recorddatas[-1].shape[1] # last one might be shorter than nt
        print('record.load() took %.3f sec' % (time.clock()-tload))

        tcat = time.clock()
        #data = np.concatenate([np.int32(recorddata) for recorddata in recorddatas], axis=1) # slow
        # init as int32 so we have space to rescale and zero, then convert back to int16
        data = np.empty((nchans, totalnt), dtype=np.int32)
        for recordi, recorddata in enumerate(recorddatas):
            i = recordi * nt
            data[:, i:i+nt] = recorddata # no need to check upper out of bounds when slicing
        print('concatenate took %.3f sec' % (time.clock()-tcat))
        tres = self.layout.tres # actual tres of record data may not match self.tres due to interpolation

        # build up waveform timepoints, taking into account any time gaps in
        # between records due to pauses in recording, assumes all records
        # are the same length, except for maybe the last
        # TODO: if self.contiguous, do this the easy way instead!
        ttsbuild = time.clock()
        ts = np.empty(totalnt, dtype=np.int64) # init
        for recordi, (record, recorddata) in enumerate(zip(cutrecords, recorddatas)):
            i = recordi * nt
            tstart = record.TimeStamp
            tend = tstart + min(nt, totalnt-i)*tres # last record may be shorter
            ts[i:i+nt] = np.arange(tstart, tend, tres, dtype=np.int64)
        '''
        # assumes no gaps between records, negligibly faster:
        tstart = cutrecords[0].TimeStamp
        ts = np.arange(tstart, tstart + totalnt*tres, tres, dtype=np.int64)
        '''
        print('ts building took %.3f sec' % (time.clock()-ttsbuild))
        #ttrim = time.clock()
        lo, hi = ts.searchsorted([start-xs, stop+xs])
        data = data[:, lo:hi+self.endinclusive] # .take doesn't seem to be any faster
        ts = ts[lo:hi+self.endinclusive] # .take doesn't seem to be any faster
        #print('record data trimming took %.3f sec' % (time.clock()-ttrim)) # this takes 0 sec

        # reverse data if need be
        if key.step == -1:
            data = data[:, ::key.step]
            ts = ts[::key.step]

        tscaleandoffset = time.clock()
        #data *= 2**(16-12) # scale 12 bit values to use full 16 bit dynamic range, 2**(16-12) == 16
        # bitshift left to scale 12 bit values to use full 16 bit dynamic range, same as * 2**(16-12) == 16
        # this provides more fidelity for interpolation, reduces uV per AD to about 0.02
        data <<= 4
        data -= 2**15 # offset values to center them around 0 AD == 0 V
        # data is still int32 at this point
        print('scaling and offsetting data took %.3f sec' % (time.clock()-tscaleandoffset))
        #print('raw data shape before resample: %r' % (data.shape,))

        # do any resampling if necessary
        if resample:
            tresample = time.clock()
            data, ts = self.resample(data, ts)
            print('resample took %.3f sec' % (time.clock()-tresample))

        # now get rid of any excess
        if xs:
            #txs = time.clock()
            lo, hi = ts.searchsorted([start, stop]) # TODO: is another searchsorted really necessary?
            data = data[:, lo:hi+self.endinclusive]
            ts = ts[lo:hi+self.endinclusive]
            #print('xs took %.3f sec' % (time.clock()-txs)) # this takes 0 sec

        #datamax = data.max()
        #datamin = data.min()
        #print('data max=%d and min=%d' % (datamax, datamin))
        #assert datamax < 2**15 - 1
        #assert datamin > -2**15
        tint16 = time.clock()
        data = np.int16(data) # should be safe to convert back down to int16 now
        print('int16() took %.3f sec' % (time.clock()-tint16))

        #print('data and ts shape after rid of xs: %r, %r' % (data.shape, ts.shape))
        print('Stream slice took %.3f sec' % (time.clock()-tslice))

        # return a WaveForm object
        return WaveForm(data=data, ts=ts, chans=self.chans)
    '''
    def __setstate__(self, d):
        """Restore self on unpickle per usual, but also try switching
        to a .resample file"""
        self.__dict__ = d
        self.try_switch()
    '''
    def AD2uV(self, AD):
        """Convert AD values to float32 uV

        TODO: unsure: does the DT3010 acquire from -10 to 10 V at intgain == 1 and encode that from 0 to 4095?
        Biggest +ve voltage is 10 million uV, biggest +ve rescaled signed int16 AD val is half of 16 bits,
        then divide by internal and external gains"""
        return np.float32(AD) * 10000000 / (2**15 * self.intgain * self.extgain)

    def uV2AD(self, uV):
        """Convert uV to signed rescaled int16 AD values"""
        return np.int16(np.round(uV * (2**15 * self.intgain * self.extgain) / 10000000))

    def resample(self, rawdata, rawts):
        """Return potentially sample-and-hold corrected and Nyquist interpolated
        data and timepoints. See Blanche & Swindale, 2006

        TODO: should interpolation be multithreaded?
        TODO: self.kernels should be deleted when selected chans change, self.nchans should be updated
        """
        #print 'sampfreq, rawsampfreq, shcorrect = (%r, %r, %r)' % (self.sampfreq, self.rawsampfreq, self.shcorrect)
        rawtres = self.rawtres # us
        tres = self.tres # us
        resamplex = int(round(self.sampfreq / self.rawsampfreq)) # resample factor: n output resampled points per input raw point
        assert resamplex >= 1, 'no decimation allowed'
        N = KERNELSIZE

        ADchans = self.layout.ADchanlist
        assert self.nchans == len(self.chans) == len(ADchans) # pretty basic assumption which might change if chans are disabled
        # check if kernels have been generated already
        try:
            self.kernels
        except AttributeError:
            self.kernels = self.get_kernels(ADchans, resamplex, N)

        # convolve the data with each kernel
        nrawts = len(rawts)
        # all the interpolated points have to fit in between the existing raw
        # points, so there's nrawts - 1 of each of the interpolated points:
        #nt = nrawts + (resamplex-1) * (nrawts - 1)
        # the above can be simplified to:
        nt = nrawts*resamplex - (resamplex - 1)
        tstart = rawts[0]
        ts = np.arange(tstart, tstart+tres*nt, tres) # generate interpolated timepoints
        #print 'len(ts) is %r' % len(ts)
        assert len(ts) == nt
        data = np.empty((self.nchans, nt), dtype=np.int32) # resampled data, leave as int32 for convolution, then convert to int16
        #print 'data.shape = %r' % (data.shape,)
        tconvolve = time.clock()
        tconvolvesum = 0
        for ADchani in xrange(len(ADchans)):
            for point, kernel in enumerate(self.kernels[ADchani]):
                """np.convolve(a, v, mode)
                for mode='same', only the K middle values are returned starting at n = (M-1)/2
                where K = len(a)-1 and M = len(v) - 1 and K >= M
                for mode='valid', you get the middle len(a) - len(v) + 1 number of values"""
                tconvolveonce = time.clock()
                row = np.convolve(rawdata[ADchani], kernel, mode='same')
                tconvolvesum += (time.clock()-tconvolveonce)
                #print 'len(rawdata[ADchani]) = %r' % len(rawdata[ADchani])
                #print 'len(kernel) = %r' % len(kernel)
                #print 'len(row): %r' % len(row)
                # interleave by assigning from point to end in steps of resamplex
                ti0 = (resamplex - point) % resamplex # index to start filling data from for this kernel's points
                rowti0 = int(point > 0) # index of first data point to use from convolution result 'row'
                data[ADchani, ti0::resamplex] = row[rowti0:] # discard the first data point from interpolant's convolutions, but not for raw data's convolutions, since interpolated values have to be bounded on both sides by raw values?
        print('convolve loop took %.3f sec' % (time.clock()-tconvolve))
        print('convolve calls took %.3f sec total' % (tconvolvesum))
        tundoscaling = time.clock()
        data >>= 16 # undo kernel scaling, shift 16 bits right in place, same as //= 2**16
        print('undo kernel scaling took %.3f sec total' % (time.clock()-tundoscaling))
        return data, ts

    def get_kernels(self, ADchans, resamplex, N):
        """Generate a different set of kernels for each ADchan to correct each ADchan's s+h delay.

        TODO: when resamplex > 1 and shcorrect == False, you only need resamplex - 1 kernels.
        You don't need a kernel for the original raw data points. Those won't be shifted,
        so you can just interleave appropriately.

        TODO: take DIN channel into account, might need to shift all highpass ADchans
        by 1us, see line 2412 in SurfBawdMain.pas. I think the layout.sh_delay_offset field may tell you
        if and by how much you should take this into account

        WARNING! TODO: not sure if say ADchan 4 will always have a delay of 4us, or only if it's preceded by AD chans
        0, 1, 2 and 3 in the channel gain list - I suspect the latter is the case, but right now I'm coding the former
        """
        i = np.asarray(ADchans) % NCHANSPERBOARD # ordinal position of each chan in the hold queue
        if self.shcorrect:
            dis = 1 * i # per channel delays, us. TODO: stop hard coding 1us delay per ordinal position
        else:
            dis = 0 * i
        ds = dis / self.rawtres # normalized per channel delays
        wh = hamming # window function
        h = np.sinc # sin(pi*t) / pi*t
        kernels = [] # list of list of kernels, indexed by [ADchani][resample point]
        for ADchani in xrange(len(ADchans)):
            d = ds[ADchani] # delay for this chan
            kernelrow = []
            for point in xrange(resamplex): # iterate over resampled points per raw point
                t0 = point/resamplex # some fraction of 1
                tstart = -N/2 - t0 - d
                tend = tstart + (N+1)
                # kernel sample timepoints, all of length N+1, float32s to match voltage data type
                t = np.arange(tstart, tend, 1, dtype=np.float32)
                kernel = wh(t, N) * h(t) # windowed sinc, sums to 1.0, max val is 1.0
                kernel = np.int32(np.round(kernel * 2**16)) # rescale to get values up to 2**16, convert to int32
                kernelrow.append(kernel)
            kernels.append(kernelrow)
        return kernels

    def save_resampled(self, blocksize=5000000):
        """Save contiguous resampled data to temp binary file on disk for quicker
        retrieval later. Do it in blocksize us slices of data at a time,
        final file contents and ordering won't change, but there should be a sweet
        spot for optimal block size to read, resample, and then write"""
        assert self.contiguous, "data in .srf file isn't contiguous, best not to save resampled data to disk, at least for now"
        totalnsamples = int(round((self.tend - self.t0) / self.tres) + 1) # count is 1-based, ie end inclusive
        blocknsamples = int(round(blocksize / self.tres))
        nblocks = int(round(np.ceil(totalnsamples / blocknsamples))) # last block may not be full sized
        print('nblocks == %r' % nblocks)
        fname = self.srff.fname + '.shcorrect=%s.%dkHz.resample' % (self.shcorrect, self.sampfreq // 1000)
        t0 = time.clock()
        f = open(fname, 'wb')
        # for speed, allocate the full file size by writing a NULL byte to the very end:
        f.seek(totalnsamples*self.nchans*2 - 1) # 0-based end of file position
        np.int8(0).tofile(f)
        f.flush() # this seems necessary to get the speedup
        for blocki in xrange(nblocks):
            tstart = blocki*blocksize
            tend = tstart + blocksize # don't need to worry about out of bounds at end when slicing
            wave = self[tstart:tend] # slicing in blocks of time
            print('wave.data.shape == %r' % (wave.data.shape,))
            for chani, chandata in enumerate(wave.data):
                pos = (chani*totalnsamples + blocki*blocknsamples) * 2 # each sample is a 2 byte int16
                f.seek(pos)
                chandata.tofile(f)
        f.close()
        print('saving resampled data to disk with blocksize=%d took %.3f sec' % (blocksize, time.clock()-t0))

    def switch(self, to='resample'):
        """Switch self to be a ResampleFileStream, use .resample file to get waveform data"""
        try:
            self.srff
            self.sampfreq
            self.shcorrect
        except AttributeError: # self isn't fully __init__'d yet
            return
        if to == 'resample':
            self.fname = self.srff.fname + '.shcorrect=%s.%dkHz.resample' % (self.shcorrect, self.sampfreq // 1000)
            self.f = open(self.fname, 'rb') # expect it to exist, otherwise propagate an IOError
            self.__class__ = ResampleFileStream
        elif to == 'normal':
            return

    def try_switch(self):
        """Try switching to using an appropriate .resample file"""
        try:
            self.switch(to='resample')
        except IOError: # matching .resample file doesn't exist
            self.switch(to='normal')


class ResampleFileStream(Stream):
    """A Stream that pulls data from a .resample file, hopefully more quickly than having
    to stitch it together and resample it from a .srf file. The current hpstream __class__
    is modified to be ResampleFileStream as needed when using an existing .resample file
    is possible. You can't just overwrite __getitem__ on the fly, that only works for
    normal methods, not special __ methods. Instead, you have to switch the whole class.

    TODO: control changing of __class__ when shcorrect or sampfreq change - if
    the current combination match an existing .resample file, make __class__ = ResampleFileStream,
    otherwise, set it back to normal Stream. Do this in the set_sampfreq and set_shcorrect methods

    TODO: use the key.step attrib to describe which channels you want returned. Can you do something like
    hpstream[0:1000:[0,1,2,5,6]] ? I think so... That would be much more efficient than loading them all
    and then just picking out the ones you want. Might even be doable in the base Stream class, but then
    you'd have to add args to record.load() to load only specific chans from that record, which might be
    slow enough to negate any speed benefit, but at least it should be possible to make it work
    on both ResampleFileStream and Stream

    """
    def __getitem__(self, key):
        tslice = time.clock()
        if key.step in [None, 1]:
            start, stop = key.start, key.stop
        elif key.step == -1:
            start, stop = key.stop, key.start # reverse start and stop, now start should be < stop
        else:
            raise ValueError('unsupported slice step size: %s' % key.step)

        start = max(start, self.t0) # stay within limits of data in the file
        stop = min(stop, self.tend+self.tres)
        totalnsamples = int(round((self.tend - self.t0) / self.tres) + 1) # in the whole file
        nsamples = int(round((stop - start) / self.tres)) # in the desired slice of data
        data = np.empty((self.nchans, nsamples), dtype=np.int16) # allocate
        starti = (start - self.t0) / self.tres # nsamples offset from start of recording
        for chan in self.chans:
            samplei = starti + chan*totalnsamples
            self.f.seek(samplei*2) # 2 bytes for each int16 sample
            data[chan] = np.fromfile(self.f, dtype=np.int16, count=nsamples)
        ts = np.arange(start, stop, self.tres, dtype=np.int64)
        print('ResampleFileStream slice took %.3f sec' % (time.clock()-tslice))
        return WaveForm(data=data, ts=ts, chans=self.chans)

    def switch(self, to='normal'):
        """Switch self to be a normal Stream, use .srf file to get waveform data"""
        if to == 'normal':
            try:
                self.f.close()
                del self.f
                del self.fname
            except AttributeError:
                pass
            self.__class__ = Stream
        elif to == 'resample':
            pass

    def __getstate__(self):
        """Don't pickle open .resample file on pickle"""
        d = self.__dict__.copy() # copy it cuz we'll be making changes
        del d['f'] # exclude open .resample file
        return d

    def __setstate__(self, d):
        """Restore open .resample file (if available) on unpickle"""
        self.__dict__ = d
        try:
            self.f = open(self.fname, 'rb')
        except IOError:
            self.switch(to='normal')


class SpykeListCtrl(wx.ListCtrl):
    """ListCtrl with a couple of extra methods defined"""
    def GetSelections(self):
        """Return row indices of selected list items.
        wx.ListCtrl lacks something like this as a method"""
        selected_rows = []
        first = self.GetFirstSelected()
        if first == -1: # no more selected rows
            return selected_rows
        selected_rows.append(first)
        last = first
        while True:
            next = self.GetNextSelected(last)
            if next == -1: # no more selected rows
                return selected_rows
            selected_rows.append(next)
            last = next

    def InsertRow(self, row, data):
        """Insert data in list at row position.
        data is a list of strings or numbers, one per column.
        wx.ListCtrl lacks something like this as a method"""
        row = self.InsertStringItem(row, str(data[0])) # inserts data's first column
        for coli, val in enumerate(data[1:]): # insert the rest of data's columns
            self.SetStringItem(row, coli+1, str(val))

    def DeleteItemByData(self, data):
        """Delete first item whose first column matches data"""
        row = self.FindItem(0, str(data)) # start search from row 0
        assert row != -1, "couldn't find data %r in SpykeListCtrl" % str(data)
        success = self.DeleteItem(row) # remove from spike listctrl
        assert success, "couldn't delete data %r from SpykeListCtrl" % str(data)

    def ToggleFocusedItem(self):
        """Toggles selection of focused list item"""
        itemID = self.GetFocusedItem()
        if itemID == -1: # no item focused
            return
        selectedIDs = self.GetSelections()
        if itemID in selectedIDs: # is already selected
            self.Select(itemID, on=0) # deselect it
        else: # isn't selected
            self.Select(itemID, on=1)


class SpykeTreeCtrl(wx.TreeCtrl):
    """TreeCtrl with overridden OnCompareItems().
    Also has a couple of helper functions"""
    def OnCompareItems(self, item1, item2):
        """Compare neurons in tree according to the average
        y0 value of their member spikes, for sorting purposes.
        Called by self.SortChildren

        TODO: sort member spikes by spike times
        """
        obj1 = self.GetItemPyData(item1)
        obj2 = self.GetItemPyData(item2)
        '''
        try:
            self.SiteLoc
        except AttributeError:
            sortframe = self.GetTopLevelParent()
            self.SiteLoc = sortframe.sort.probe.SiteLoc # do this here and not in __init__ due to binding order
        '''
        try: # make sure they're both neurons by checking for .spikes attrib
            obj1.spikes
            obj2.spikes
            y01 = np.asarray([ spike.y0 for spike in obj1.spikes.values() ]).mean()
            y02 = np.asarray([ spike.y0 for spike in obj2.spikes.values() ]).mean()
            '''
            # if we want to use maxchan instead of y0, need to work on neuron's mean waveform
            ycoord1 = self.SiteLoc[obj1.maxchan][1]
            ycoord2 = self.SiteLoc[obj2.maxchan][1]
            return cmp(ycoord1, ycoord2)
            '''
            return cmp(y01, y02)
        except AttributeError:
            raise RuntimeError, "can't yet deal with sorting spikes in tree"

    def GetTreeChildrenPyData(self, itemID):
        """Returns PyData of all children of item in
        order from top to bottom in a list"""
        children = []
        childID, cookie = self.GetFirstChild(itemID)
        while childID:
            child = self.GetItemPyData(childID)
            children.append(child)
            childID, cookie = self.GetNextChild(itemID, cookie)
        return children

    def GetTreeChildren(self, itemID):
        """Returns list of itemIDs of all children of item in
        order from top to bottom of the tree"""
        childrenIDs = []
        childID, cookie = self.GetFirstChild(itemID)
        while childID:
            childrenIDs.append(child)
            childID = self.GetNextChild(itemId, cookie)
        return childrenIDs

    def GetFocusedItem(self):
        """This relies on _focusedItem being set externally by handling
        tree spikes appropriately"""
        return self._focusedItem
    '''
    def GetSelectedItems(self):
        """This relies on _selectedItems being set externally by handling
        tree spikes appropriately. I think this differs from .GetSelections()
        in that the currently focused item isn't incorrectly assumed to
        also be a selected item"""
        return self._selectedItems
    '''
    def ToggleFocusedItem(self):
        """Toggles selection of focused tree item"""
        item = self.GetFocusedItem()
        if item in self.GetSelections(): # already selected
            select = False # deselect
        else: # not selected
            select = True # select it
        self.SelectItem(item, select)
        #print 'SpykeTreeCtrl.ToggleFocusedItem() not implemented yet, use Ctrl+Space instead'

'''
class SetList(set):
    """A set with an append() method like a list"""
    def append(self, item):
        self.add(item)
'''

def get_sha1(fname, blocksize=2**20):
    """Gets the sha1 hash of fname (with full path)"""
    m = hashlib.sha1()
    # automagically clean up after ourselves
    with file(fname, 'rb') as f:
        # continually update hash until EOF
        while True:
            block = f.read(blocksize)
            if not block:
                break
            m.update(block)
    return m.hexdigest()

def intround(n):
    """Round to the nearest integer, return an integer. Works on arrays,
    saves on parentheses, nothing more"""
    if iterable(n): # it's a sequence, return as an int64 array
        return np.int64(np.round(n))
    else: # it's a scalar, return as normal Python int
        return int(round(n))

def iterable(x):
    """Check if the input is iterable, stolen from numpy.iterable()"""
    try:
        iter(x)
        return True
    except:
        return False

def toiter(x):
    """Convert to iterable. If input is iterable, returns it. Otherwise returns it in a list.
    Useful when you want to iterate over a Record (like in a for loop),
    and you don't want to have to do type checking or handle exceptions
    when the Record isn't a sequence"""
    if iterable(x):
        return x
    else:
        return [x]
''' use np.vstack instead
def cvec(x):
    """Return x as a column vector. x must be a scalar or a vector"""
    x = np.asarray(x)
    assert x.squeeze().ndim in [0, 1]
    try:
        nrows = len(x)
    except TypeError: # x is scalar?
        nrows = 1
    x.shape = (nrows, 1)
    return x
'''
def isempty(x):
    """Check if sequence is empty. There really should be a np.isempty function"""
    print("WARNING: not thoroughly tested!!!")
    x = np.asarray(x)
    if np.prod(x.shape) == 0:
        return True
    else:
        return False

def cut(ts, trange):
    """Returns timestamps, where tstart <= timestamps <= tend
    Copied and modified from neuropy rev 149"""
    lo, hi = argcut(ts, trange)
    return ts[lo:hi] # slice it

def argcut(ts, trange):
    """Returns timestamp slice indices, where tstart <= timestamps <= tend
    Copied and modified from neuropy rev 149"""
    tstart, tend = trange[0], trange[1]
    '''
    # this is what we're trying to do:
    return ts[ (ts >= tstart) & (ts <= tend) ]
    ts.searchsorted([tstart, tend]) method does it faster, because it assumes ts are ordered.
    It returns an index where the values would fit in ts. The index is such that
    ts[index-1] < value <= ts[index]. In this formula ts[ts.size]=inf and ts[-1]= -inf
    '''
    lo, hi = ts.searchsorted([tstart, tend]) # returns indices where tstart and tend would fit in ts
    # can probably avoid all this end inclusion code by using the 'side' kwarg, not sure if I want end inclusion anyway
    '''
    if tend == ts[min(hi, len(ts)-1)]: # if tend matches a timestamp (protect from going out of index bounds when checking)
        hi += 1 # inc to include a timestamp if it happens to exactly equal tend. This gives us end inclusion
        hi = min(hi, len(ts)) # limit hi to max slice index (==max value index + 1)
    '''
    return lo, hi

def eucd(coords):
    """Generates Euclidean distance matrix from a
    sequence of n dimensional coordinates. Nice and fast.
    Written by Willi Richert
    Taken from:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/498246
    on 2006/11/11
    """
    coords = np.asarray(coords)
    n, m = coords.shape
    delta = np.zeros((n, n), dtype=np.float64)
    for d in xrange(m):
        data = coords[:, d]
        delta += (data - data[:, np.newaxis]) ** 2
    return np.sqrt(delta)

def revcmp(x, y):
    """Does the reverse of cmp():
    Return negative if y<x, zero if y==x, positive if y>x"""
    return cmp(y, x)

class Gaussian(object):
    """Gaussian function, works with ndarray inputs"""
    def __init__(self, mu, sigma):
        self.mu = mu
        self.sigma = sigma

    def __call__(self, x):
        """Called when self is called as a f'n.
        Don't bother normalizing by 1/(sigma*np.sqrt(2*np.pi)),
        don't care about normalizing the integral,
        just want to make sure that f(0) == 1"""
        return np.exp( -(x-self.mu)**2 / (2*self.sigma**2) )

    def __getitem__(self, x):
        """Called when self is indexed into"""
        return self(x)

def g(x0, sx, x):
    """1-D Gaussian"""
    return np.exp( -(x-x0)**2 / (2*sx**2) )

def g2(x0, y0, sx, sy, x, y):
    """2-D Gaussian"""
    return np.exp( -(x-x0)**2 / (2*sx**2) - (y-y0)**2 / (2*sy**2) )

def g3(x0, y0, z0, sx, sy, sz, x, y, z):
    """3-D Gaussian"""
    return np.exp( -(x-x0)**2 / (2*sx**2) - (y-y0)**2 / (2*sy**2) - (z-z0)**2 / (2*sz**2) )

def Vf(Im, x0, y0, z0, sx, sy, sz, x, y, z):
    """1/r voltage decay function in 2D space
    What to do with the singularity so that the leastsq gets a smooth differentiable f'n?"""
    #if np.any(x == x0) and np.any(y == y0) and np.any(z == z0):
    #    raise ValueError, 'V undefined at singularity'
    return Im / (4*np.pi) / np.sqrt( sx**2 * (x-x0)**2 + sy**2 * (y-y0)**2 + sz**2 * (z-z0)**2)

def dgdmu(mu, sigma, x):
    """Partial of g wrt mu"""
    return (x - mu) / sigma**2 * g(mu, sigma, x)

def dgdsigma(mu, sigma, x):
    """Partial of g wrt sigma"""
    return (x**2 - 2*x*mu + mu**2) / sigma**3 * g(mu, sigma, x)

def dg2dx0(x0, y0, sx, sy, x, y):
    """Partial of g2 wrt x0"""
    return g(y0, sy, y) * dgdmu(x0, sx, x)

def dg2dy0(x0, y0, sx, sy, x, y):
    """Partial of g2 wrt y0"""
    return g(x0, sx, x) * dgdmu(y0, sy, y)

def dg2dsx(x0, y0, sx, sy, x, y):
    """Partial of g2 wrt sx"""
    return g(y0, sy, y) * dgdsigma(x0, sx, x)

def dg2dsy(x0, y0, sx, sy, x, y):
    """Partial of g2 wrt sy"""
    return g(x0, sx, x) * dgdsigma(y0, sy, y)

def RM(theta):
    """Return 2D (2x2) rotation matrix, with theta counterclockwise rotation in radians"""
    return np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])


class Poo(object):
    """Poo function, works with ndarray inputs"""
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    def __call__(self, x):
        """Called when self is called as a f'n"""
        return (1+self.a*x) / (self.b+self.c*x**2)

    def __getitem__(self, x):
        """Called when self is indexed into"""
        return self(x)

def hamming(t, N):
    """Return y values of Hamming window at sample points t"""
    #if N == None:
    #    N = (len(t) - 1) / 2
    return 0.54 - 0.46 * np.cos(np.pi * (2*t + N)/N)

def hex2cmap(hexcolours, alpha=0.0):
    """Convert colours hex string list into a colourmap (RGBA list)"""
    cmap = []
    for c in hexcolours:
        c = hex2color(c) # convert hex string to RGB tuple
        c = list(c) + [alpha] # convert to list, add alpha as 4th channel
        cmap.append(c)
    return cmap
