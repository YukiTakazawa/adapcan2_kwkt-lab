import numpy as np
class ringBuffer:
    def __init__(self, length, boolblock):
        self.length = length
        self.queue = np.zeros(length)
        self.head = 0
        self.tail = 0 
        self.num = 0 
        # block for queue full
        self.block = boolblock
        #print(self.block)
    def Accept(self): #check if the queue accept new data
        tmp = (self.tail+1)% self.length
        if self.block and tmp == self.head:
            return False
        else:
            return True
    def Enque(self, x):
        tmp = (self.tail+1)% self.length
        if self.block == True:
            if tmp == self.head:
                print("Que full")
            else:
               self.queue[self.tail]=x
               self.tail = tmp
               self.num = self.num + 1
        else: # non blocking ring buffer
           if self.num < self.length:
             self.num = self.num + 1
           if tmp == self.head:
             self.head = (self.head + 1)%self.length
           self.queue[self.tail] = x
           self.tail = tmp
    def Deque(self):
        if self.tail == self.head:
            print("Que empty")
        else:
            y = self.queue[self.head]
            self.head = (self.head + 1)%self.length
            self.num = self.num - 1
            return y
    def Derivative(self):
        im2 = (self.head - 2)%self.length
        if im2 < 0 :
          im2 = im2 + self.length 
        df = (float(self.queue[self.head]) - float(self.queue[im2]))/2
        #print("{0} {1} {2}".format(df, self.queue[self.head], self.queue[im2]))
        return df 
    def Secder(self): # the second derivative
        im2 = (self.head - 2)%self.length
        if im2 < 0 :
          im2 = im2 + self.length 
        im1 = (self.head - 1)%self.length
        if im1 < 0 :
          im1 = im2 + self.length 
        df = float(self.queue[self.head]) - 2*float(self.queue[im1]) + float(self.queue[im2])
        return df 
    def Average(self):
        sum = 0
        for a in self.queue:
          sum = sum + float(a)
          #print('{0:.2f}'.format(a))
        sum = sum/self.length
        return sum
    def Show(self):
        tmp = self.head
        while tmp!=self.tail:
          print("{0}".format(self.queue[tmp]))
          tmp = (tmp + 1)%self.length
class adapcanKeys:
    def __init__(self, att, phase):
        self.att = att
        self.phase = phase
