#!/usr/bin/python3
# 
#
from email.mime import base
from socket import PACKET_LOOPBACK
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
import numpy as np
import sklearn
from sklearn.linear_model import LinearRegression
import math
from decimal import Decimal, ROUND_HALF_UP

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
  global PHASETUNE
  global ATTTUNE
  global DEBUG
  
  stdscr = curses.initscr()
  stdscr.border(0) 
  curses.savetty()
  datawin = createRecwin(stdscr, 3, 50, 2, 5)
  cntwin =  createRecwin(stdscr, 20, 80, 6, 5)
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
  PHASETUNE = adapcanconf['phasetune']
  ATTTUNE = adapcanconf['atttune']
  DEBUG = adapcanconf['debug']
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
          attCnt(saml, ch, adpkeys[ch], cntwin)
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
          phaseCnt(saml, ch, adpkeys[ch], cntwin)
        elif (chr(x)=='s'):
          writeConf(adpkeys)
        elif (chr(x)=='w'):
          spiWrite(saml, cntwin, stdscr)
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
          autoTune(saml, ch, adpkeys[ch], cntwin, stdscr, pw)
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

def autoTune(mcu, ch, adpKey, cntwin, stdscr, pw):   # 自動制御メソッド
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
      c = c + "\n\tCh={0}, Att={1:.1f} dB, Phase={2:.1f} deg".format(chname, adpKey.att/2, float(adpKey.phase)/4096*360)
      title = 'Attenuator/Phase values'
      cntwin.addstr(0,0,title, curses.color_pair(2))
      cntwin.addstr(1,0,c)
      cntwin.addstr(5,0,'options', curses.color_pair(2))
      cntwin.addstr(6,0,'\tAVERAGING:'+AVERAGING+"\n")
      cntwin.addstr(8,0,'Select Search Mode', curses.color_pair(2))
      cntwin.addstr(10,0,"\tf:Full search\n\ts:Step track\n\tx:Exit = ", curses.color_pair(1))
      cntwin.refresh()
      x = cntwin.getch()
      if(chr(x) == 'f'):
        fullSearch(mcu, ch, adpKey, cntwin)
      if(chr(x) == 's'):
        stepTrack(mcu, ch, adpKey, cntwin)
      elif(chr(x) == 'x'):
        break
        seth.stop()
        curses.nocbreak()
        #stdscr.keypad(False)
        curses.echo()
        curses.endwin()
      else:
        cntwin.addstr(0,0,'either a or p')
        stdscr.refresh()
        cntwin.refresh()
  except(KeyboardInterrupt, EOFError):
    pass



def fullSearch(mcu, ch, adpKey, cntwin):
  # 初期化設定(phase, attをともに0からスタート)
  adpKey.phase = 0
  adpKey.att = 0
  
  cntwin.erase()
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: 0 step_att: 0 total_step: 0" %((adpKey.att/2), adpKey.phase))
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(3)
  
  # Pointの基準点basePointをphase, attをともに0で初期化とpvの取得
  basePoint = adapcanKeys(0, 0)
  debug = DebugFile()
  param = TrackParam()
  debug.set(adpKey, basePoint, param)
  
  if PHASETUNE == "True":
    autoTune_phase(mcu, ch, adpKey, basePoint, cntwin, debug, param)
    # cntwin.addstr(5,5,str(time_phase))
  elif PHASETUNE == "False":
    minphase = 0
  else:
    cntwin.erase()
    cntwin.addstr(9,5, "全探索を開始")
    cntwin.addstr(10,5, "phaseの自動調整をスキップしました")
    time.sleep(2)
    cntwin.refresh()
  time.sleep(1)
  if ATTTUNE == "True":
    autoTune_att(mcu, ch, adpKey, basePoint, cntwin, debug, param)
    # cntwin.addstr(6,5,str(time_att))
  elif ATTTUNE == "False":
    minatt = 0
  else:
    cntwin.erase()
    cntwin.addstr(9,5, "全探索を開始")
    cntwin.addstr(10,5, "phaseの自動調整を終了しました")
    cntwin.addstr(11,5, "attの自動調整をスキップしました")
    time.sleep(2)
    cntwin.refresh()
  time.sleep(1)
  cntwin.erase()
  cntwin.addstr(12,5,"自動制御を終了\n\tAttを %3.1f, Phaseを %4dに調整しました\n\t Qを押してください" %(basePoint.att/2, basePoint.phase))
  cntwin.refresh()
  
  # auto_Tuneの実行結果を出力(デバッグ用)
  if DEBUG == "True":
    debug.output("fullSearch")
  
  x = cntwin.getch()
  if chr(x) == 'q':
    return



def autoTune_phase(mcu, ch, adpKey, basePoint, cntwin, debug, param):
  cntwin.erase()
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: 0 step_att: 0 total_step: 0" %((basePoint.att/2), adpKey.phase))
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.addstr(10,5,"phaseの自動調整を開始")
  cntwin.refresh()
  """
  # 最小phase探索の検証用のexcel出力リスト
  iterationList = list(range(32))   # 0 ~ 32のイテレーションリストを作成
  phaseList = []
  dcpowerList = []
  cvList = []
  pvList = []
  minphaseList = []
  # デバッグ用のリスト追加
  phaseList.append(adpKey.phase)
  dcpowerList.append(pv)
  cvList.append('0')
  pvList.append(pv)
  minphaseList.append(minphase)
  """
  
  for i in range(31):
    if adpKey.phase + 130 > 4095:
      adpKey.phase = 0
    else:
      adpKey.phase = min(4095,adpKey.phase + 130)
    
    cntwin.erase()
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.addstr(9,5, "全探索を開始")
    cntwin.addstr(10,5,"phaseの自動調整を開始")
    cntwin.refresh()
    
    # 位相を動かす
    th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
    th.start()
    cntwin.refresh()
    th.join()
    time.sleep(1)
    param.get_dcpower("phase")
    debug.set(adpKey, basePoint, param)
    
    if param.cv < param.pv:
      param.pv = param.cv
      basePoint.phase = adpKey.phase
  # 最小のphase値を設定する
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.addstr(10,5,"phaseの自動調整を終了")
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
  th.start()
  th.join()
  time.sleep(1)
  """
  # 最小のphase値探索の検証用
  t = time.time()
  dt = datetime.datetime.fromtimestamp(t)
  debug_phase = pd.DataFrame([iterationList, phaseList, dcpowerList, cvList, pvList, minphaseList], 
                             index=['iteration', 'phase', 'DC power', 'cv', 'pv', 'minphase'])
  """
  return



def autoTune_att(mcu, ch, adpKey, basePoint, cntwin, debug, param):
  # 初期化設定
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((adpKey.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.addstr(10,5,"phaseの自動調整を終了")
  cntwin.addstr(11,5,"attの自動調整を開始")
  cntwin.refresh()
  
  for i in range(63):
    if adpKey.att > 62:
      adpKey.att = 0
    else:
      adpKey.att = min(63,adpKey.att + 1)
    
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((adpKey.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.addstr(9,5, "全探索を開始")
    cntwin.addstr(10,5,"phaseの自動調整を終了")
    cntwin.addstr(11,5,"attの自動調整を開始")
    cntwin.refresh()
    
    # attを調整
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, basePoint.phase,))
    th.start()
    cntwin.refresh()
    th.join()
    time.sleep(1)
    param.get_dcpower("att")
    debug.set(adpKey, basePoint, param)
    
    if param.cv < param.pv:
      param.pv = param.cv
      basePoint.att = adpKey.att
  # 最小のatt値を設定する
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.addstr(10,5,"phaseの自動調整を終了")
  cntwin.addstr(11,5,"attの自動調整を終了")
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(1)
  return



def stepTrack(mcu, ch, adpKey, cntwin):
  # 初期化設定(phase, attともに0からスタート)
  adpKey.phase = 0
  adpKey.att = 0
  threshold = -25.0
  
  cntwin.erase()
  cntwin.addstr(9,5, "step track制御を開始")
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: 0 step_att: 0 total_step: 0" %((adpKey.att/2), adpKey.phase))
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(3)
  
  # Pointの基準点basePointをphase, attをともに0で初期化し, pvを取得
  basePoint = adapcanKeys(0, 0)
  debug = DebugFile()
  param = TrackParam()
  debug.set(adpKey, basePoint, param)
  
  while True:
    # phase調整
    step_phase_tune(mcu, ch, adpKey, basePoint, cntwin, debug, param)
    if param.att_end == "False":
      # att調整
      step_att_tune(mcu, ch, adpKey, basePoint, cntwin, debug, param)
    elif param.att_end == "True":
      pass
    else :
      cntwin.erase()
      cntwin.addstr(15,0,"\tatt_endに有効なパラメータが設定されていません", curses.color_pair(3))
      cntwin.refresh()
      time.sleep(10)
      return
    
    if threshold >= param.pv:
      cntwin.erase()
      cntwin.addstr(9,5,"stepTrack制御を終了\n\tPhaseを %4d, Attを %3.1fに調整しました\n\ttotal_step: %d\n\tQを押してください\n\t" %(basePoint.phase, basePoint.att/2, param.total_step), curses.color_pair(1))
      cntwin.addstr(15,5,"thresholdに到達しました", curses.color_pair(3))
      cntwin.refresh()
      break
    elif param.total_step >= 300:
      cntwin.addstr(9,5,"stepTrack制御を終了\n\tPhaseを %4d, Attを %3.1fに調整しました\n\ttotal_step: %d\n\tQを押してください\n\t" %(basePoint.phase, basePoint.att/2, param.total_step), curses.color_pair(1))
      cntwin.addstr(15,5,"total_stepが300を超えました", curses.color_pair(3))
      cntwin.refresh()
      break
  
  th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
  th.start()
  th.join()
  time.sleep(1)
  param.get_dcpower("phase")
  debug.set(adpKey, basePoint, param)
  # auto_Tuneの実行結果を出力(デバッグ用)
  if DEBUG == "True":
    debug.output("stepTrack")
  elif DEBUG == "False":
    pass
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\tDebugオプションに有効な文字列が与えられていません", curses.color_pair(3))
    cntwin.refresh()
    time.sleep(10)
  x = cntwin.getch()
  if chr(x) == 'q':
    return



def step_phase_tune(mcu, ch, adpKey, basePoint, cntwin, debug, param):
  step_LinearRegression(mcu, ch, adpKey, basePoint, cntwin, debug, param)
  if param.direction == "increase":
    index = len(param.increase_delta_List)
    increase_delta_List = param.increase_delta_List[index-5:index]
    if np.sign(min(increase_delta_List)) == -1:  # 最小値がマイナスの符号なら最小値の更新があったと考えられる
      # リスト内の最小値のインデックスから，basePointからのシフト量を足して更新する
      if basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1) > 4095:
        basePoint.phase = basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1) - 4095
        adpKey.phase = basePoint.phase
      else :
        basePoint.phase = min(4095, basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1))
        adpKey.phase = basePoint.phase
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
      cntwin.addstr(11,5, "phaseの最小値探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.get_dcpower("phase")
      debug.set(adpKey, basePoint, param)
      param.phase_flag = "True"
      
    elif np.sign(min(increase_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      adpKey.phase = 4095 - adpKey.phase  # increase側へ調整するため，phase値をdecrease側から反転させる
      for i in range(11):
      #while True:
      #  if adpKey.phase == basePoint.phase:
      #   break
        if adpKey.phase + 130 > 4095:
          adpKey.phase = 0
        else :
          adpKey.phase = min(4095, adpKey.phase + 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
        cntwin.addstr(11,5, "phaseの最小値探索を開始")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        param.get_dcpower("phase")
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
          param.phase_flag = "True"
          break
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(3))
      cntwin.refresh()
      time.sleep(10)
      return
      
    
    
    # さらに最小値が続くかの探索ループ(極小値探索)
    if param.phase_flag == "True":
      param.phase_flag = "False"
      while True:
        #if adpKey.phase == basePoint.phase:
        #  break
        if adpKey.phase + 130 > 4095:
          adpKey.phase = 0
        else :
          adpKey.phase = min(4095, adpKey.phase + 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
        cntwin.addstr(11,5, "phaseの最小値探索を終了")
        cntwin.addstr(12,5, "phaseの極小値探索を開始")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        param.get_dcpower("phase")
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
        elif param.cv >= param.pv :
          if adpKey.phase - 130 < 0:
            adpKey.phase = 4095
          else :
            adpKey.phase = max(0,adpKey.phase-130)
          cntwin.erase()
          cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
          cntwin.addstr(11,5, "phaseの最小値探索を終了")
          cntwin.addstr(12,5, "phaseの極小値探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
          cntwin.refresh()
          th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
          th.start()
          th.join()
          time.sleep(1)
          break
  
  elif param.direction == "decrease":  # increase側と同様に
    index = len(param.decrease_delta_List)
    decrease_delta_List = param.decrease_delta_List[index-5:index]
    if np.sign(min(decrease_delta_List)) == -1:  # 最小値がマイナスの符号なら最小値の更新があったと考えられる
      # リスト内の最小値のインデックスから，basePointからのシフト量を求めてbasePointを更新する
      if basePoint.phase - 130*(decrease_delta_List.index(min(decrease_delta_List))+1) < 0:
        basePoint.phase = 4095 - 130*(decrease_delta_List.index(min(decrease_delta_List))+1)
        adpKey.phase = basePoint.phase
      else :
        basePoint.phase = max(0, basePoint.phase - 130*(decrease_delta_List.index(min(decrease_delta_List))+1))
        adpKey.phase = basePoint.phase
      cntwin.erase()
      cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
      cntwin.addstr(11,5, "phaseの最小値探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.get_dcpower("phase")
      debug.set(adpKey, basePoint, param)
      param.phase_flag = "True"
    elif np.sign(min(decrease_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      for i in range(11):
      #while True:
      #  if adpKey.phase == basePoint.phase:
      #    break
        if adpKey.phase - 130 < 0:
          adpKey.phase = 4095
        else :
          adpKey.phase = max(0, adpKey.phase - 130)
        cntwin.erase()
        cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
        cntwin.addstr(11,5, "phaseの最小値探索を開始")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        param.get_dcpower("phase")
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
          param.phase_flag = "True"
          break
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(3))
      cntwin.refresh()
      time.sleep(10)
      return
      
      
    if param.phase_flag == "True":
      param.phase_flag = "False"
    # さらに最小値が続くかの探索ループ
      while True:
      #  if adpKey.phase == basePoint.phase:
      #    break
        if adpKey.phase - 130 < 0:
          adpKey.phase = 4095
        else :
          adpKey.phase = max(0, adpKey.phase - 130)
        cntwin.erase()
        cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
        cntwin.addstr(11,5, "phaseの最小値探索を終了")
        cntwin.addstr(12,5, "phaseの極小値探索を開始")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch,basePoint.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        param.get_dcpower("phase")
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
        elif param.cv >= param.pv :
          if adpKey.phase + 130 > 4095:
            adpKey.phase = 0
          else :
            adpKey.phase = max(0,adpKey.phase+130)
          cntwin.erase()
          cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを終了")
          cntwin.addstr(11,5, "phaseの最小値探索を終了")
          cntwin.addstr(12,5, "phaseの極小値探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
          cntwin.refresh()
          th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
          th.start()
          th.join()
          time.sleep(1)
          break
        
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\tphaseの前後値差分の比較にエラーが発生しています", curses.color_pair(3))
    cntwin.refresh()
    time.sleep(10)
    return
  adpKey.phase = basePoint.phase  # phase調整後にphaseシフト量をbasePointのphaseで更新する



def step_att_tune(mcu, ch, adpKey, basePoint, cntwin, debug, param):
  param.linear_model = "None"
  adpKey.att = basePoint.att
  while True:
    if adpKey.att + 1 > 62:
      param.att_end = "True"
      param.debug_flag = "Off"
      break
    else :
      adpKey.att = min(63, adpKey.att + 1)
    cntwin.erase()
    cntwin.addstr(9,5, "step track制御を開始")
    cntwin.addstr(10,5, "attの極小値探索を開始")
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((adpKey.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.refresh()
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, basePoint.phase,))
    th.start()
    th.join()
    time.sleep(1)
    param.get_dcpower("att")
    debug.set(adpKey, basePoint, param)
    if param.cv < param.pv :
      param.pv = param.cv
      basePoint.att = adpKey.att
      param.debug_flag = "On"
      break
  
  while True:
    if adpKey.att + 1 > 62:
      param.att_end = "True"
      param.debug_flag = "Off"
      break
    else :
      adpKey.att = min(63, adpKey.att + 1)
    cntwin.erase()
    cntwin.addstr(10,5, "attの極小値探索を開始")
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((adpKey.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.refresh()
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, basePoint.phase,))
    th.start()
    th.join()
    time.sleep(1)
    param.get_dcpower("att")
    debug.set(adpKey, basePoint, param)
    if param.cv < param.pv :
      param.pv = param.cv
      basePoint.att = adpKey.att
    elif param.cv >= param.pv :
      adpKey.att = max(0,adpKey.att-1)
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "attの最小値探索を終了")
      cntwin.addstr(11,5, "attの極小値探索を終了")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((adpKey.att/2), basePoint.phase, param.step_phase, param.step_att, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, basePoint.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.debug_flag = "Off"
      break

  """
  if param.direction == "increase":
    index = len(param.increase_delta_List)
    increase_delta_List = param.increase_delta_List[index-5:index]
    if np.sign(min(param.increase_delta_List)) == -1:  # 最小値がマイナスの符号なら最小値の更新があったと考えられる
      # リスト内の最小値のインデックスから，att = 0からのシフト量を求めてbasePointを更新する
      if basePoint.att + (param.increase_delta_List.index(min(param.increase_delta_List))+1) > 62:
        basePoint.att = basePoint.att + (param.increase_delta_List.index(min(param.increase_delta_List))+1) - 62
        param.step_att = basePoint.att
        adpKey.att = basePoint.att
      else :
        basePoint.att = min(63, basePoint.att + (param.increase_delta_List.index(min(param.increase_delta_List))+1))
        param.step_att = param.increase_delta_List.index(min(param.increase_delta_List))+1
        adpKey.att = basePoint.att
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "attの初期探索を終了")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(increase_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      param.flag = "True"

    elif np.sign(min(param.increase_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      for i in range(11):
      #while True:
        if adpKey.att + 1 > 62:
          param.step_att = 0
          adpKey.att = 0
        else :
          param.step_att += 1
          adpKey.att = min(63, adpKey.att + 1)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "attの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          param.cv = float(pwa)
        else:
          param.cv = float(pw)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.att = adpKey.att
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          param.flag = "True"
          break
        param.delta_calc()
        debug.set(adpKey, basePoint, param)
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
      
    
    # さらに最小値が続くかの探索ループ(極小値探索)
    if param.flag == "True":
      param.flag = "False"
      while True:
        if adpKey.att + 1 > 62:
          param.step_att = 0
          adpKey.att = 0
        else :
          param.step_att += 1
          adpKey.att = min(63, adpKey.att + 1)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "attの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          param.cv = float(pwa)
        else:
          param.cv = float(pw)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.att = adpKey.att
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
        elif param.cv >= param.pv :
          if adpKey.att - 1 < 0:
            param.step_att = 0
            adpKey.att = 63
          else :
            param.step_att -= 1
            adpKey.phase = max(0,adpKey.att-1)
          cntwin.erase()
          cntwin.addstr(9,5, "step track制御を開始")
          cntwin.addstr(10,5, "attの初期探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
          cntwin.refresh()
          th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
          th.start()
          th.join()
          time.sleep(1)
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          break
          
  elif param.direction == "decrease":  # 同様に
    index = len(param.decrease_delta_List)
    decrease_delta_List = param.decrease_delta_List[index-5:index]
    if np.sign(min(decrease_delta_List)) == -1:  # 最小値がマイナスの符号なら最小値の更新があったと考えられる
      # リスト内の最小値のインデックスから，att = 0からのシフト量を求めてbasePointを更新する
      if basePoint.att - (decrease_delta_List.index(min(decrease_delta_List))+1) < 0:
        basePoint.att = 63 - (decrease_delta_List.index(min(decrease_delta_List))+1)
        adpKey.att = basePoint.att
      else :
        basePoint.att = max(0, basePoint.att - (decrease_delta_List.index(min(decrease_delta_List))+1))
        adpKey.att = basePoint.att
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "attの初期探索を終了")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(decrease_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      param.flag = "True"

    elif np.sign(min(decrease_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      for i in range(11):
      #while True:
        if adpKey.att - 1 < 0:
          param.step_att = 0
          adpKey.att = 63
        else :
          param.step_att += 1
          adpKey.att = max(0, adpKey.att - 1)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "attの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          param.cv = float(pwa)
        else:
          param.cv = float(pw)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.att = adpKey.att
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          param.flag = "True"
          break
        param.delta_calc()
        debug.set(adpKey, basePoint, param)
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
      
    if param.flag == "True":
      param.flag = "False"
    # さらに最小値が続くかの探索ループ
      while True:
        if adpKey.att - 1 < 0:
          param.step_att = 0
          adpKey.att = 63
        else :
          param.step_att += 1
          adpKey.att = max(0, adpKey.att - 1)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "attの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
        cntwin.refresh()
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          param.cv = float(pwa)
        else:
          param.cv = float(pw)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.att = adpKey.att
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
        elif param.cv >= param.pv :
          if adpKey.att + 1 > 62:
            param.step_att = 0
            adpKey.att = 0
          else :
            param.step_att -= 1
            adpKey.att = max(0,adpKey.att-1)
          cntwin.erase()
          cntwin.addstr(9,5, "step track制御を開始")
          cntwin.addstr(10,5, "attの初期探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
          cntwin.refresh()
          th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
          th.start()
          th.join()
          time.sleep(1)
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          break
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\tphaseの前後値差分の比較にエラーが発生しています", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
    return
  """



def step_LinearRegression(mcu, ch, adpKey, basePoint, cntwin, debug, param):  # 最小値設定のbasePointを渡し，basePointから±nstep動かす
  param.delta_List_init()  # 線形回帰モデル作成のためのdelta_List[10]の初期化
  param.direction = "None"
  param.linear_model = "None"
  # phaseの探索
  for i in range(1,6):
    # +方向にstep調整
    if basePoint.phase + 130*i > 4095:
      adpKey.phase = basePoint.phase + 130*i -4095
    else :
      adpKey.phase = min(4095, basePoint.phase+130*i)
    cntwin.erase()
    cntwin.addstr(9,5, "step track制御を開始")
    cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを開始")
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.refresh()
    th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
    th.start()
    th.join()
    time.sleep(1)
    param.get_dcpower("phase")
    param.increase_delta_append()
    debug.set(adpKey, basePoint, param)
    # -方向にstep調整
    if basePoint.phase - 130*i < 0:
      adpKey.phase = 4095 - basePoint.phase - 130*i
    else :
      adpKey.phase = max(0, basePoint.phase - 130*i)
    cntwin.erase()
    cntwin.addstr(9,5, "step track制御を開始")
    cntwin.addstr(10,5, "phaseの調整方向アルゴリズムを開始")
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d step_att: %d total_step: %d" %((basePoint.att/2), adpKey.phase, param.step_phase, param.step_att, param.total_step))
    cntwin.refresh()
    th = threading.Thread(target=mcu.senddata, args=(ch, basePoint.att, adpKey.phase,))
    th.start()
    th.join()
    time.sleep(1)
    param.get_dcpower("phase")
    param.decrease_delta_append()
    debug.set(adpKey, basePoint, param)
  linear_model = LinearRegression()
  param.decrease_delta_List.reverse()
  linear_model_List = param.decrease_delta_List + param.increase_delta_List
  linear_model.fit(pd.DataFrame(range(1,11)), pd.DataFrame(linear_model_List))
  param.linear_model_output(linear_model.coef_)
  param.decrease_delta_List.reverse()
  if np.sign(linear_model.coef_) == 1:
    param.direction = "decrease"
    return
  elif np.sign(linear_model.coef_) == -1:
    param.direction = "increase"
    return
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\t回帰直線でエラー", curses.color_pair(3))
    cntwin.refresh()
    time.sleep(10)
    return


"""
  # attの探索
  elif setting == "att":
    for i in range(1,6):
      param.step_att_incre()
      # +方向にstep調整
      if basePoint.att + i > 62:
        adpKey.att = basePoint.att + i - 62
      else :
        adpKey.att = min(63, basePoint.att + i)
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "attの初期探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      if AVERAGING == "True":
        param.cv = float(pwa)
      else:
        param.cv = float(pw)
      param.delta_calc()
      param.increase_delta_append()
      debug.set(adpKey, basePoint, param)
      param.step_phase_incre()
      # -方向にstep調整
      if basePoint.att - i < 0:
        adpKey.att = 62 - basePoint.att - i
      else :
        adpKey.att = max(0, 62 - basePoint.att - i)
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "attの初期探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d total_step: %d" %((adpKey.att/2), adpKey.phase, param.step_phase, param.total_step))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      if AVERAGING == "True":
        param.cv = float(pwa)
      else:
        param.cv = float(pw)
      param.delta_calc()
      param.decrease_delta_append()
      debug.set(adpKey, basePoint, param)

    linear_model = LinearRegression()
    linear_model_List = param.decrease_delta_List + param.increase_delta_List
    linear_model.fit(pd.DataFrame(range(1,11)), pd.DataFrame(linear_model_List))
    param.linear_model_output(linear_model.coef_)
    if np.sign(linear_model.coef_) == 1:
      param.direction = "decrease"
      return
    elif np.sign(linear_model.coef_) == -1:
      param.direction = "increase"
      return
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\t初期探索でエラー", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
"""


class DebugFile:
  def __init__(self):
    self.total_step = []
    self.step_phase = []
    self.step_att = []
    self.phase = []
    self.phase_degree = []
    self.att = []
    self.direction = []
    self.basePoint_phase = []
    self.basePoint_phase_degree = []
    self.basePoint_att = []
    self.cv = []
    self.pv = []
    self.delta = []
    self.linear_model = []
    self.init_pv_delta_List = []
    self.debug_flag_List = []
    self.phase_flag_List = []
    self.att_end_List = []
  
  def set(self, adpKey, basePoint, param):
    self.total_step.append(param.total_step)
    self.step_phase.append(param.step_phase)
    self.step_att.append(param.step_att)
    self.direction.append(param.direction)
    self.phase.append(adpKey.phase)
    self.phase_degree.append(float(Decimal(adpKey.phase/130*11.4).quantize(Decimal('0'), rounding=ROUND_HALF_UP)))
    self.att.append(adpKey.att/2)
    self.basePoint_phase.append(basePoint.phase)
    self.basePoint_phase_degree.append(float(Decimal(basePoint.phase/130*11.4).quantize(Decimal('0'), rounding=ROUND_HALF_UP)))
    self.basePoint_att.append(basePoint.att)
    self.cv.append(param.cv)
    self.pv.append(param.pv)
    self.delta.append(param.delta)
    self.linear_model.append(param.linear_model)
    self.init_pv_delta_List.append(param.init_pv_delta)
    self.debug_flag_List.append(param.debug_flag)
    self.phase_flag_List.append(param.phase_flag)
    self.att_end_List.append(param.att_end)
    
  def output(self, setting):
    t = time.time()
    dt = datetime.datetime.fromtimestamp(t)
    debug_File = pd.DataFrame([self.total_step, self.step_phase, self.step_att, self.phase, self.phase_degree, self.att, 
                               self.basePoint_phase, self.basePoint_phase_degree, self.basePoint_att, self.cv, self.pv, self.delta, self.direction, 
                               self.linear_model, self.init_pv_delta_List, self.debug_flag_List, self.phase_flag_List, self.att_end_List], index=['total_step', 
                              'step_phase', 'step_att', 'phase', 'phase_degree', 'att', 'basePoint.phase', 'basePoint.phase_degree', 'basePoint.att', 
                              'current value(CV)', 'previous value(PV)', 'delta value', 'direction', 'linear_model', 
                              'init_pvとの差分', 'Debug_flag', 'phase_flag', 'att_end'])
    # 最小のDC power値探索の検証excelを出力
    if setting == "fullSearch":
      debug_File.to_excel('fullSearch_Debug'+ str(dt) +'.xlsx')
    elif setting == "stepTrack":
      debug_File.to_excel('stepTrack_Debug'+ str(dt) +'.xlsx')
    
class TrackParam:
  def __init__(self):
    self.cv = 0.0
    self.pv = 0.0
    self.direction = "None"  # phaseの調整方向のパラメータ「increase or decrease」
    self.total_step = 0
    self.step_phase = 0
    self.step_att = 0
    self.delta = 0.0
    self.linear_model = "None"  # 回帰直線の初期化
    self.flag = "None"  # 
    self.increase_delta_List = []
    self.decrease_delta_List = []
    self.phase_flag = "False"
    self.att_end = "False"
    self.init_pv_delta = 0.0
    if AVERAGING == "True":
      self.init_pv = float(pwa)
      self.pv = self.init_pv
    else:
      self.init_pv = float(pw)
      self.pv = self.init_pv
    self.debug_flag = "None"
    self.phase_flag = "None"  
    self.att_end = "False"  # 初期値はFalse
    
  def increase_delta_append(self):
    self.increase_delta_List.append(self.delta)
    
  def decrease_delta_append(self):
    self.decrease_delta_List.append(self.delta)
  
  def delta_List_init(self):
    self.increase_delta_List = []
    self.decrease_delta_List = []
  
  # 回帰直線の傾きを代入
  def linear_model_output(self, coef):
    self.linear_model = str(coef)
  
  # DC powerの取得と差分の計測，そしてステップ数のインクリメントを行う
  def get_dcpower(self, setting):
    if AVERAGING == "True":
      self.cv = float(pwa)
    else:
      self.cv = float(pw)
    self.delta = self.cv - self.pv
    self.init_pv_delta = self.cv - self.init_pv
    if setting == "phase":
      self.step_phase += 1
    elif setting == "att":
      self.step_att += 1
    else :
      self.step_phase = -999
      self.step_att = -999
    self.total_step = self.step_phase + self.step_att



if __name__ == '__main__':
    main()
