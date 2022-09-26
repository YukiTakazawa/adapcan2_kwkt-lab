import spidev
class Saml21:
    def __init__(self, chip, bpw, speed):
        self.spi = chip 
        self.spi.mode = 0 
        self.spi.bits_per_word = bpw
#        self.spi.max_speed_hz = speed
        self.spi.max_speed_hz = 50000
        self.seq = 0
        self.seqnoSet(self.seq +1)
#        self.writeData(int(1).to_bytes(1,'big'),int(1).to_bytes(2,'big'))  #for debug(SeqNo nocheck)
        self.powerSwitch(int(1))
    def comseq(self, cmd):
        seq = self.seq.to_bytes(1, 'big')
        self.seq = (self.seq + 1)%256
        return (cmd+seq) 
    def powerSwitch(self, sw):
        cmd = int(32).to_bytes(1, 'big') 
        cmd = self.comseq(cmd)
        cmd_bytes = cmd + sw.to_bytes(1, 'big') 
        return self.spi.xfer2(cmd_bytes)
    def writeData(self, address, data):
        cmd = b"\01" 
        cmd = self.comseq(cmd)
        cmd_bytes = cmd + address + data 
        return self.spi.xfer2(cmd_bytes)
    def readData(self, address):
        cmd = b"\02"
        cmd = self.comseq(cmd)
        cmd_bytes = cmd + address.to_bytes(1,'big') 
        buf = self.spi.xfer2(cmd_bytes)
        return buf.to_bytes(2, 'big') 
    def senddata(self, ch, att, phase):
        cmd =  (16 + ch).to_bytes(1, 'big')
        cmd = self.comseq(cmd)
        attbyte = int(att*2).to_bytes(1, 'big')
        phasebyte = int(phase).to_bytes(2, 'big')
        cmd_bytes = cmd + attbyte + phasebyte
        #print("{0}¥n".format(cmd_bytes))
        return self.spi.xfer2(cmd_bytes)
    def seqnoSet(self, seqno):
        cmd = int(48).to_bytes(1, 'big')
        cmd = self.comseq(cmd)
        cmd_bytes = cmd + seqno.to_bytes(1, 'big')
        return self.spi.xfer2(cmd_bytes)

