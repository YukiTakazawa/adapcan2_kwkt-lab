#!/usr/bin/python3
# 
#
import sys
import time
import spidev
import termios
import contextlib
import threading
import os
import re
import serial
import select
import curses
#import spi
from saml21 import Saml21
from ringBuffer import ringBuffer
from ringBuffer import adapcanKeys
import RPi.GPIO as GPIO
from curses.textpad import Textbox, rectangle
import json
#import excel
import pandas as pd
import datetime

# after the execution of main retrieve the original stty 
@contextlib.contextmanager
def raw_mode(file):
    old_attrs = termios.tcgetattr(file.fileno())
    new_attrs = old_attrs[:]
    new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
    #new_attrs[3] = new_attrs[3] & ~(termios.ICANON)
    try:
       termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
       yield
    finally:
       termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)
       os.system("stty sane")

def serialGet(ser, datawin):
  global AVERAGING
  global pwa
  global pw
  c1 = "Ch="+"0"+" DC power=" + "--" + " dBm"
  c2 = "Ch="+"1"+" DC power=" + "--" + " dBm"
  rb1 = ringBuffer(10, False)
  rb2 = ringBuffer(10, False)
  while 1:
  # select(readports, writeports, exceptions, timeout(omittable))
    rd,_,_ = select.select([ser], [], [])
    # data is five bytes + LF and CR
    rx_data = ser.readline()
    #print(rx_data)
    if len(rx_data) > 7:
      if rx_data[-1] == 10:
        ch = chr(rx_data[0])
        try:
          pw = rx_data[1:-1].decode().rstrip()
          #print(pwa)

        # in case there is misalignment of data
          if rx_data[0] != 0 and pw!=None:
            if ch == "0":
              pwa = '{0:.2f}'.format(rb1.Average())
              rb1.Enque(float(pw))
            else: 
              pwa = '{0:.2f}'.format(rb2.Average())
              rb2.Enque(float(pw))
            if AVERAGING == "True":
              c = "Ch="+ch +" DC power=" + pwa + " dBm"
            else: 
              c = "Ch="+ch +" DC power=" + pw + " dBm"
            if ch == "0":
              c1 = c 
            else: 
              c2 = c 
       #av = "Num entry=" + str(rb.num)
            datawin.erase()
            datawin.addstr(0, 0, 'Latest measurement', curses.color_pair(2)) 
            datawin.addstr(1, 5, c1)
            datawin.addstr(2, 5, c2)
        except:
            pass
    #datawin.addstr(0,20, av)
        datawin.refresh()
    #print("{0}",format(c))

def main():
# open window
  global AVERAGING
  stdscr = curses.initscr()
  stdscr.border(0) 
  curses.savetty()
  datawin = createRecwin(stdscr, 3, 50, 2, 5)
  cntwin =  createRecwin(stdscr, 20, 50, 6, 5)
  curses.start_color()
  curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
  curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
  curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_RED)
  title ="ADAPCAN"
  stdscr.addstr(0, 2, title, curses.color_pair(3))
  stdscr.refresh()
  curses.cbreak()
# ringBuffer 
# serial port definition and listener
  ser = serial.Serial("/dev/serial0", baudrate = 9600, parity=serial.PARITY_NONE, stopbits = serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)
### SAML configuration 
  saml = Saml21(spidev.SpiDev(0,0),  8, 5000)
### saved data retrieval
  confname = "adapcan.conf"
  pw = 1 # power toggle 1=on
  ch = 0
  adpkeys = []
  adpkeys.append(adapcanKeys(0, 0))
  adpkeys.append(adapcanKeys(0, 0))
  if os.path.exists(confname):
    with open(confname, 'r', newline='\n') as f:
       try:
         for i in range(0,2):
           conf = f.readline() 
           conf = conf.strip()
           split_conf = re.split('[: ,]', conf)
           #print(split_conf)
           adpkeys[i].att = float(split_conf[1])
           adpkeys[i].phase = int(split_conf[3])
       except:
         pass
  attphase=''
  for i in range(0, 2):
    attphase = attphase+"{0} {1} read from file¥n".format(adpkeys[i].att, adpkeys[i].phase)
  # init values
  for i in range(0,2):
    saml.senddata(i, adpkeys[i].att, adpkeys[i].phase) # set att. level of att. #3
  CONFFILE = 'adapcan.json'
  if os.path.exists(CONFFILE):
    with open(CONFFILE, 'r') as f: 
        adapcanconf = json.load(f)
  else: 
    print('missing adapcan.conf\n')
    sys.exit()
  AVERAGING = adapcanconf['averaging']
  # print(AVERAGING)
  # sys.exit()
  cntwin.addstr(0, 0, attphase)
  cntwin.refresh()
  seth = threading.Thread(target=serialGet, args=(ser,datawin,)) 
  seth.setDaemon(True)
  seth.start() 
  with raw_mode(sys.stdin):
    try: 
      while True:
        cntwin.erase()
        if pw == 1:
            pwname = 'ON'
        else:
            pwname = 'OFF'
        if ch == 1:
            chname = '1'
        else:
            chname = '0'
        c = "Pw="+pwname + "\tCh="+chname
        for i in range(0, 2): 
          c = c + "\n\tCh={0}, Att={1:.1f} dB, Phase={2:.1f} deg".format(i, adpkeys[i].att/2, float(adpkeys[i].phase)/4096*360)
        title = 'Attenuator/Phase values'
        cntwin.addstr(0,0,title, curses.color_pair(2))
        cntwin.addstr(1,0,c)
        cntwin.addstr(5,0,'options', curses.color_pair(2))
        cntwin.addstr(6,0,'\tAVERAGING:'+AVERAGING+"\n")
        cntwin.addstr(8,0,'Select command', curses.color_pair(2))
        cntwin.addstr(10,0,"\tz:Amplifire toggle\n\tc:Channel toggle\n\ta:Attenuator adjust\n\tp:Phase shift adjust\n\tw:SPI write\n\tr:SPI read\n\ts:Save current values\n\tt:Auto tune\n\tx:Exit = ", curses.color_pair(1))
        cntwin.refresh()
        x = cntwin.getch()
        stdscr.refresh()
        if (chr(x) == 'a'):
          attCnt(saml, ch, adpkeys[ch], cntwin);
        elif (chr(x)=='z'):
          if pw == 1:
            saml.powerSwitch(int(0))  
            pw = 0
          else: 
            saml.powerSwitch(int(1))
            pw = 1 
        elif (chr(x)=='c'):
          if ch == 1:
              ch = 0 
          else:
              ch = 1
        elif (chr(x)=='p'):
          phaseCnt(saml, ch, adpkeys[ch], cntwin);  
        elif (chr(x)=='s'):
          writeConf(adpkeys);  
        elif (chr(x)=='w'):
          spiWrite(saml, cntwin, stdscr);  
        elif (chr(x)=='x'):
          saml.powerSwitch(int(0))
          del cntwin
          del datawin
          break
          seth.stop()
          curses.nocbreak()
          #stdscr.keypad(False)
          curses.echo()
          curses.endwin()
        elif (chr(x)=='t'):
          autoTune(saml, ch, adpkeys[ch], cntwin);
        else:
          cntwin.addstr(0,0,'either a or p')
          stdscr.refresh()
          cntwin.refresh()
    except(KeyboardInterrupt, EOFError):
      pass 

def togglePA(mcu, pw, scr):
  title ="ADAPCAN"
  if pw == 1:
    mcu.powerSwitch(int(0))
    scr.addstr(0, 2, title, A_REVERSE)
  else:
    mcu.powerSwitch(int(1))
    scr.addstr(0, 2, title, curses.color_pair(3))
  scr.refresh()

def createRecwin(scr,sx, sy, px, py):
  newwin = curses.newwin(sx, sy, px, py)
  rectangle = (scr, px-1, py-1, px+sx+1, py+sy+1)
  scr.refresh()
  return newwin

def spiWrite(mcu, cntwin, scr):
  message ="Input and Ctl+G"
  cntwin.addstr(12,1, message)
  cntwin.refresh()
  meswin = curses.newwin(2, 20, 20, 5)
  rectangle = (scr, 19,4,23,26)
  scr.refresh()
  curses.noecho()
  box = Textbox(meswin)
  box.edit()
  senddata = box.gather()
  address = bytes(senddata[0], 'utf8')
  data = bytes(senddata[1:3], 'utf8')
  # scr.refresh
  th = threading.Thread(target=mcu.writeData, args=(address, data,))
  th.start()
  th.join()

def attCnt(mcu, ch, adpKey, cntwin):
  while True:
    attString ="Att: %3.1f dB  "% (adpKey.att/2)
    #cntwin.erase()
    cntwin.addstr(4,10,attString)
    cntwin.refresh()
    x = cntwin.getch()
    if chr(x) == '1':
      if adpKey.att > 62 : 
          adpKey.att = 0
      else :
          adpKey.att = min(63, adpKey.att + 1)
    elif chr(x) == '0':
          # rotate the setting
      if adpKey.att < 1:
          adpKey.att = 63
      else: 
         adpKey.att = max(0, adpKey.att - 1)
    elif chr(x) == 'q':
      return 
    else:
      inperr="1:plus, 0:mns or q"
      cntwin.addstr(4, 30, inperr, curses.A_REVERSE) 
      cntwin.refresh()
      # print("\tinput either 1, 0 or q")
    # atts.set_att(att) # set att. level of att. #3
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    cntwin.refresh()
    th.join()

def phaseCnt(mcu, ch, adpKey, cntwin):
  while True:
    phasecmd = "Phase: %4d "%adpKey.phase
    # cntwin.erase()
    cntwin.addstr(4,10,phasecmd) 
    cntwin.refresh()
    x = cntwin.getch()
    if chr(x) == '1':
      if adpKey.phase + 130 > 4095 :
        adpKey.phase = 0 
      else :
        adpKey.phase = min(4095, adpKey.phase+130); 
    elif chr(x) == '0':
      if adpKey.phase - 130 < 0 :
        adpKey.phase = 4095
      else : 
        adpKey.phase = max(0, adpKey.phase-130); 
    elif chr(x) == 'q':
      return 
    else:
        inperr="1:plus, 0:mns or q"
        cntwin.addstr(4, 30, inperr, curses.A_REVERSE) 
        cntwin.refresh()
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    th.join()

def writeConf(adpKeys):
    with open('adapcan.conf', mode='w', newline='\n') as f:
        for i in range(0, 2): 
          f.write('att:{0} phase:{1}\n'.format(adpKeys[i].att, adpKeys[i].phase))
        f.close 

def autoTune(mcu, ch, adpKey, cntwin):   # 自動制御メソッド
  global cv
  global pv
  global minphase
  global iterationList
  global phaseList
  global dcpowerList
  global cvList
  global pvList
  global minphaseList
  # プログラム検証用のexcel出力リスト
  iterationList = list(range(32))   # 0 ~ 32のイテレーションリストを作成
  phaseList = []
  dcpowerList = []
  # プログラムデバッグ用の出力リスト
  cvList = []
  pvList = []
  minphaseList = []
  
  attphaseString = "Att: %3.1f dB  Phase: %4d iteration: 0" %((adpKey.att/2), adpKey.phase)
  cntwin.addstr(4,10,attphaseString)
  startString = "phaseの自動調整を開始"
  cntwin.addstr(9,5,startString)
  cntwin.refresh()
  
  # 初期化設定
  if AVERAGING == "True":
    pv = pwa   # 現在のphaseとatt設定で最小DC powerを初期化
  else:
    pv = pw
  minphase = adpKey.phase   # 最小のphase値を初期化
  
  phaseList.append(adpKey.phase)
  dcpowerList.append(pv)
  cvList.append('0')
  pvList.append(pv)
  minphaseList.append(minphase)

  
  for i in range(31):
    if adpKey.phase + 130 > 4095:
      adpKey.phase = 0
    else:
      adpKey.phase = min(4095,adpKey.phase + 130)
    
    attphaseString = "Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1)
    cntwin.addstr(4,10,attphaseString)
    cntwin.refresh()
    
    # 位相を動かす
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    cntwin.refresh()
    th.join()
    time.sleep(1)
    
    if AVERAGING == "True":
      cv = pwa   # 現在のDC power
    else:
      cv = pw
      
    phaseList.append(adpKey.phase)
    dcpowerList.append(cv)
    cvList.append(cv)
    pvList.append(pv)
    
    if float(cv) < float(pv):
      pv = cv
      minphase = adpKey.phase
    minphaseList.append(minphase)
  attphaseString = "Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1)
  cntwin.addstr(4,10,attphaseString)

  t = time.time()
  dt = datetime.datetime.fromtimestamp(t)
  # debug用のexcelを出力
  debug = pd.DataFrame([iterationList, cvList, pvList, phaseList, minphaseList], index=['iteration','cv', 'pv', 'phase', 'minphase'])
  debug.to_excel('/home/kait/Documents/adapcan2_kwkt-lab/debug'+str(dt)+'.xlsx')
  # 最小のphase値探索の検証excelを出力
  df = pd.DataFrame([iterationList, phaseList, dcpowerList], index=['iteration', 'phase', 'DC power'])
  df.to_excel('/home/kait/Documents/adapcan2_kwkt-lab/autoTune'+str(dt)+'.xlsx')
  endString = "phaseの自動調整を終了, 最小値: %4d qを押してください" %(minphase)
  cntwin.addstr(9,30,endString)
  cntwin.refresh()
  x = cntwin.getch()
  if chr(x) == 'q':
    return

if __name__ == '__main__':
    main()
