class Mcp492xDac:
    __BIT = {
        "AB": 15,
        "BUF": 14,
        "GA_": 13,
        "SHDN_": 12,
    }
    __DATA_BITS = 12

    def __init__(self, chip, ab):
        self.chip = chip
        self.ab = ab

    def write(self, data, buf=1, ga_=1, shdn_=1):
        ab = self.ab
        data = max(0, data); 
        data = min(2**(self.__DATA_BITS)-1, data)
        cmd = int(0)
        cmd += ab    << self.__BIT["AB"]
        cmd += buf   << self.__BIT["BUF"]
        cmd += ga_   << self.__BIT["GA_"]
        cmd += shdn_ << self.__BIT["SHDN_"]

        #if (data > 2 ** (self.__DATA_BITS) - 1):
        #    raise ValueError('Data out of range')

        cmd += data
        
        cmd_bytes = cmd.to_bytes(2, 'big')

        return self.chip.xfer(cmd_bytes)

class Mcp492x:
    def __init__(self, bus):
        self.bus = bus
        self.dac = [Mcp492xDac(self, 0), Mcp492xDac(self, 1)]

# MCP4921 is I2C version of MCP492x
class Mcp4921(Mcp492x):
    def __init__(self, bus):
        super().__init__(bus)

    def xfer(self, data):
        raise(NotImplementedError("I2C support is not implemented"))

# MCP4922 is SPI version of MCP492x
class Mcp4922(Mcp492x):
    def __init__(self, bus):
        super().__init__(bus)
        
    def xfer(self, data):
        self.bus.xfer(data)
