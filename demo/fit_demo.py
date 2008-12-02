"""Fits a sum of Gaussians model to a spike.
Adapted from http://www.scipy.org/Cookbook/FittingData"""

import numpy as np
import scipy.optimize
from scipy.optimize import leastsq, fmin_cobyla
from pylab import figure, plot
import time
import spyke


def g(mu, sigma, x):
    """1-D Gaussian"""
    return np.exp(- ((x-mu)**2 / (2*sigma**2)) )

def dgdmu(mu, sigma, x):
    """Partial of g wrt mu"""
    return (x - mu) / sigma**2 * g(mu, sigma, x)

def dgdsigma(mu, sigma, x):
    """Partial of g wrt sigma"""
    return (x**2 - 2*x*mu + mu**2) / sigma**3 * g(mu, sigma, x)


class LeastSquares(object):
    def __init__(self, p0, x, y):
        self.p0 = p0
        self.x = x
        self.y = y
        self.calc()
        figure()
        plot(x, y, 'k.-')
        p = self.p
        plot(x, p[0]*g(p[1], p[2], x) + p[3]*g(p[4], p[5], x), 'r-')

    def calc(self):
        result = leastsq(self.cost, self.p0, args=(self.x, self.y), Dfun=self.dcost, full_output=True, col_deriv=True)
        self.p, self.cov_p, self.infodict, self.mesg, self.ier = result

    def model(self, p, x):
        """Sum of two Gaussians, returns a vector of y values"""
        return p[0]*g(p[1], p[2], x) + p[3]*g(p[4], p[5], x)

    def cost(self, p, x, y):
        """Distance of each point to the target function"""
        return self.model(p, x) - y # returns a vector of errors, one for each data point

    def dcost(self, p, x, y):
        """Derivative of cost function wrt each parameter, returns Jacobian matrix"""
        # these all have the same length as x
        dfdp0 = g(p[1], p[2], x)
        dfdp1 = p[0]*dgdmu(p[1], p[2], x)
        dfdp2 = p[0]*dgdsigma(p[1], p[2], x)
        dfdp3 = g(p[4], p[5], x)
        dfdp4 = p[3]*dgdmu(p[4], p[5], x)
        dfdp5 = p[3]*dgdsigma(p[4], p[5], x)
        return np.asarray([dfdp0, dfdp1, dfdp2, dfdp3, dfdp4, dfdp5])

"""
Don't forget, need to enforce in the fitting somehow that the two
Gaussians must be of opposite sign. Would also like to be able to enforce
minimum amplitudes for both gaussians, and a range of differences in
their means. Could also put constraints on sigma for each gaussian.
Also, take the abs of sigma when done, since its sign doesn't mean anything

OK, so if you want bounded minimization, you need to use a different algorithm - leastsq
won't do it apparently. Here are some alternatives:

scipy.optimize.fmin_cobyla - constrained optimization by linear approximation
scipy.optimize.fmin_l_bfgs_b -
scipy.optimize.fmin_slsqp - sequential least squares programming
scipy.optimize.fmin_tnc

Then, there's also scikits.openopt, which is associated with scipy somehow

"""

class Cobyla(object):
    """This algorithm doesn't seem to work, although its constraints features
    are promising. Also, it's about 6X slower than leastsq, but that might
    be because it's converging incorrectly"""
    def __init__(self, p0, x, y, min1=50, min2=50, dmurange=(100, 500)):
        self.p0 = p0
        self.x = x
        self.y = y
        self.min1 = min1
        self.min2 = min2
        self.dmurange = dmurange

        #cons = (self.con1, self.con2, self.con3, self.con4)
        self.cons = self.con0
        self.calc()
        figure()
        plot(x, y, 'k.-')
        p = self.p
        plot(x, p[0]*g(p[1], p[2], x) + p[3]*g(p[4], p[5], x), 'r-')

    def calc(self):
        self.p = fmin_cobyla(self.cost, self.p0, self.cons, args=(self.x, self.y), consargs=())

    def model(self, p, x):
        """Sum of two Gaussians, returns a vector of y values"""
        return p[0]*g(p[1], p[2], x) + p[3]*g(p[4], p[5], x)

    def cost(self, p, x, y):
        """Distance of each point to the target function"""
        return self.model(p, x) - y # returns a vector of errors, one for each data point

    def con0(self, p):
        return 0

    def con1(self, p):
        return abs(p[0]) >= self.min1

    def con2(self, p):
        return abs(p[3]) >= self.min2

    def con3(self, p):
        """Amplitudes must be of opposite sign"""
        return np.sign(p[0]) == np.sign(-1 * p[3])

    def con4(self, p):
        """Make sure Gaussians are reasonable spaced, in us"""
        dmu = p[1] - p[4]
        return self.dmurange[0] <= dmu <= self.dmurange[1]

'''
x = np.arange(87)
y = np.array([  0.69486117,   8.16924953,  10.17962551,   6.11466599,
         1.31948435,  -0.14410365,   0.52754396,  -1.19760346,
        -6.5304656 , -12.67904949, -17.30953789, -21.16654778,
       -27.42707253, -35.58847809, -39.90871048, -36.30270767,
       -30.48548698, -28.91375732, -28.71337509, -22.10368347,
       -10.01594257,   0.77593756,   6.38806391,   9.77489376,
        13.51230049,  18.76480675,  24.56304169,  29.13644218,
        29.13644218,  25.91305542,  25.22989464,  31.09949875,
        38.20145798,  39.93480301,  36.9852066 ,  34.95500946,
        34.4129982 ,  32.2089653 ,  28.85248566,  26.9906559 ,
        27.04725838,  26.68888474,  25.23055649,  23.87973785,
        25.07825661,  27.58584404,  27.02534294,  19.5314827 ,
         8.8014183 ,   0.38737282,  -4.01576424,  -7.24346924,
       -10.06681824, -11.75206089, -11.93491077, -13.00849819,
       -17.08987427, -24.19359589, -30.66723061, -32.69648361,
       -29.18977356, -23.64463043, -20.0399704 , -20.32796288,
       -22.92987823, -24.34780502, -21.20810699, -14.53381634,
        -9.78805828, -10.76048088, -14.7164259 , -16.65529442,
       -16.18955612, -16.59147072, -19.17337418, -21.50229836,
       -21.18888855, -17.96524811, -14.06570435, -11.56622982,
       -10.79750252, -10.52579212, -10.45510769, -10.73945427,
       -10.3060379 ,  -7.99611521,  -4.38621092], dtype=np.float32)
'''
#p0 = [-10, 7, 2, 10, 20, 4] # initial parameter guess
#p0 = np.array([-39.75430588,  14.96675971,   3.68428717,  37.4680001 ,  34.34298134,   7.70360098])

sf = spyke.surf.File('/data/ptr11/05 - tr1 - mseq32_20ms.srf')
sf.parse()

t = 368568680 #396729760 #396729820
chani = 1 #2
w = sf.hpstream[t:t+1500] # waveform object
x = w.ts
x = x - x[0]
y = w[chani]

# For LeastSquares, good or bad guesses all converge in the same amount of time:
# this initial guess doesn't work, seems having incorrect amplitude signs messes it up
p0 = [50, 125, 60, -50, 250, 60] # ms and uV
# this one does work
p0 = [-50, 125, 60, 50, 250, 60] # ms and uV
# so does this one, with more accurate means
p0 = [-50, 200, 60, 50, 400, 60] # ms and uV
# so does this one, with wildly innacurate means
p0 = [-50, 50, 200, 50, 600, 40] # ms and uV

ls = LeastSquares(p0, x, y)

t0 = time.clock()
for i in xrange(100):
    ls.calc()

print '%.3f sec' % (time.clock() - t0) # ~2 sec

c = Cobyla(p0, x, y)

t0 = time.clock()
for i in xrange(100):
    c.calc()

print '%.3f sec' % (time.clock() - t0) # ~12 sec



