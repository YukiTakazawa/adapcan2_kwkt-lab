import numpy as np
from ringBuffer import ringBuffer
class stepTrack:
    def __init__(self, boolPhase, phase, att, deltap, deltaa, resp, resa, rbLength):
        self.phaseCont = boolPhase  #either phase or gain control
        self.phase = phase  #default phase value
        self.att =   att  #default attenuation value  
        self.deltap = deltap 
        self.deltaa = deltaa 
        self.phaseResolution = resp # resolution of phase control
        self.attResolution = resa # resolution of attenuator
        self.current = {"Value":0, "Phase":phase, "att":att} # current combination 
        self.best = {"Value":0, "Phase":phase, "att":att} # best combination 
        self.rb = ringBuffer(rbLength, False)
        self.conv = ringBuffer(rbLength, False)
    def Update(self,dacs,atts,value): #fix the change
        if value < self.best["Value"]:
            self.best["Value"] = value
            self.best["Phase"] = self.phase
            self.best["att"] = self.att
        if self.phaseCont == True:
          phase = self.phase + self.deltap
          if (phase > 4095):
              phase = 100
          elif (phase < 0):
              phase = 4000
          self.phase = phase
          dacs.write(self.phase)
        else:
          att = self.att + self.deltaa
          if (att > 31.5):
              att =10 
          elif (att < 0):
              att = 10
          self.att = att
          atts.set_att(self.att) 
    def Record(self,value):  #register the value
        with open('adapcan.conf', mode='w') as f:
          f.write('att:{0} phase:{1}'.format(self.best["att"], self.best["Phase"]))
          f.close 
    def Values(self,): 
        return self.phase, self.att
    def PhaseCont(boolPhase): 
        self.phase = boolPhase
    def isPhase(self): 
        return self.phaseCont
    def FlipDir(self):
        if (self.phaseCont):
            self.deltap = -self.deltap
        else:
            self.deltaa = -self.deltaa


