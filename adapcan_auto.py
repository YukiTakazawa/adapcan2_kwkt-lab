#!/usr/bin/python3
# 
#
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
  cntwin.erase()
  cntwin.addstr(9,5, "全探索を開始")
  cntwin.refresh()
  if PHASETUNE == "True":
    autoTune_phase(mcu, ch, adpKey, cntwin)
    # cntwin.addstr(5,5,str(time_phase))
  else:
    cntwin.addstr(10,5, "phaseの自動調整をスキップしました")
    cntwin.refresh()
  time.sleep(1)
  if ATTTUNE == "True":
    autoTune_att(mcu, ch, adpKey, cntwin)
    # cntwin.addstr(6,5,str(time_att))
  else:
    cntwin.addstr(11,5, "attの自動調整をスキップしました")
    cntwin.refresh()
  time.sleep(1)
  cntwin.addstr(12,5,"自動制御を終了, Phaseを %4d, Attを %3.1fに調整しました\n Qを押してください" %(minphase, minatt/2))
  cntwin.refresh()
  
  # auto_Tuneの実行結果を出力(デバッグ用)
  if DEBUG == "True":
    t = time.time()
    dt = datetime.datetime.fromtimestamp(t)
    
    # 最小のphase値探索の検証excelを出力
    with pd.ExcelWriter('DebugFile'+str(dt)+'.xlsx') as writer:
      if PHASETUNE == "True":
        debug_phase.to_excel(writer, sheet_name='phaseDebug')
      if ATTTUNE == "True":
        debug_att.to_excel(writer, sheet_name='attDebug')
        
  x = cntwin.getch()
  if chr(x) == 'q':
    return



def autoTune_phase(mcu, ch, adpKey, cntwin):
  global minphase
  global debug_phase
  
  # global time_phase
  # 最小phase探索の検証用のexcel出力リスト
  iterationList = list(range(32))   # 0 ~ 32のイテレーションリストを作成
  phaseList = []
  dcpowerList = []
  cvList = []
  pvList = []
  minphaseList = []
  
  # time_sta = time.perf_counter()
  
  # 初期化設定(phase, attともに0からスタート)
  adpKey.phase = 0
  adpKey.att = 0
  
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: 0" %((adpKey.att/2), adpKey.phase))
  cntwin.addstr(10,5,"phaseの自動調整を開始")
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(3)
  
  if AVERAGING == "True":
    pv = pwa   # 現在のphaseとatt設定で最小DC powerを初期化
  else:
    pv = pw
  minphase = adpKey.phase   # 最小のphase値を初期化
  
  # デバッグ用のリスト追加
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
    
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1))
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
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1))
  
  # time_end = time.perf_counter()
  # time_phase = time_end - time_sta
  
  # 最小のphase値探索の検証用
  t = time.time()
  dt = datetime.datetime.fromtimestamp(t)
  debug_phase = pd.DataFrame([iterationList, phaseList, dcpowerList, cvList, pvList, minphaseList], 
                             index=['iteration', 'phase', 'DC power', 'cv', 'pv', 'minphase'])
  
  # 最小のphase値を設定する
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, minphase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(1)
  return



def autoTune_att(mcu, ch, adpKey, cntwin):
  global minatt
  global debug_att
  
  # global time_att
  # 最小phase探索の検証用のexcel出力リスト
  iterationList = list(range(64))   # 0 ~ 32のイテレーションリストを作成
  attList = []
  dcpowerList = []
  cvList = []
  pvList = []
  minattList = []
  
  # time_sta = time.perf_counter()
  
  # 初期化設定
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: 0" %((adpKey.att/2), adpKey.phase))
  cntwin.addstr(11,5,"attの自動調整を開始")
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(3)
  
  if AVERAGING == "True":
    pv = pwa   # 現在のphaseとatt設定で最小DC powerを初期化
  else:
    pv = pw
  minatt = adpKey.att   # 最小のphase値を初期化
  
  # デバッグ用のリスト追加
  attList.append(adpKey.att)
  dcpowerList.append(pv)
  cvList.append('0')
  pvList.append(pv)
  minattList.append(minatt)
  
  for i in range(63):
    if adpKey.att > 62:
      adpKey.att = 0
    else:
      adpKey.att = min(63,adpKey.att + 1)
    
    cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1))
    cntwin.refresh()
    
    # attを調整
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    cntwin.refresh()
    th.join()
    time.sleep(1)
    
    if AVERAGING == "True":
      cv = pwa   # 現在のDC power
    else:
      cv = pw
      
    attList.append(adpKey.att)
    dcpowerList.append(cv)
    cvList.append(cv)
    pvList.append(pv)
    
    if float(cv) < float(pv):
      pv = cv
      minatt = adpKey.att
    minattList.append(minatt)
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: %d" %((adpKey.att/2), adpKey.phase, i+1))
  
  # time_end = time.perf_counter()
  # time_att = time_end - time_sta
  
  # 最小のatt値探索の検証用
  debug_att = pd.DataFrame([iterationList, attList, dcpowerList, cvList, pvList, minattList], 
                             index=['iteration', 'att', 'DC power', 'cv', 'pv', 'minatt'])

  # 最小のatt値を設定する
  th = threading.Thread(target=mcu.senddata, args=(ch, minatt, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(1)
  return



def stepTrack(mcu, ch, adpKey, cntwin):
  # global basePoint  # DC_powerが最小値となるphaseのシフト量とattenuation値を保持
  # global step_phase  # basePointからのphaseの調整step数を保持
  # global step_att  # attの調整step数を保持
  # global direction
  
  # デバッグ用
  # global phase_List
  # global att_List
  # global increase_delta_List
  # global decrease_delta_List
  # global step_phase_List
  # global step_att_List
  # global cv_List
  # global pv_List
  # global basePoint_phase_List
  # global basePoint_att_List
  # global phase_iteration_List
  # global att_iteration_List
  # global direction_List
  
  # basePoint_phase_List = []
  # basePoint_att_List = []
  # cv_List = []
  # pv_List = []
  # phase_List = []
  # att_List = []
  # step_phase_List = []
  # step_att_List = []
  # increase_delta_List = []
  # decrease_delta_List = []
  # delta_List = []
  flag = "None"
  # phase_iteration_List = list(range(32))
  # att_iteration_List = list(range(64))
  # direction_List = []
  
  cntwin.erase()
  cntwin.addstr(9,5, "step track制御を開始")
  cntwin.refresh()
  # 初期化設定(phase, attともに0からスタート)
  adpKey.phase = 0
  adpKey.att = 0
  cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d iteration: 0" %((adpKey.att/2), adpKey.phase))
  cntwin.refresh()
  th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
  th.start()
  cntwin.refresh()
  th.join()
  time.sleep(1)
  # Pointの基準点basePointをphase, attをともに0で初期化
  basePoint = adapcanKeys(0, 0)
  debug = DebugFile()
  param = TrackParam()
  debug.set(adpKey, basePoint, param)
  # 初期化時のDC powerを取得
  if AVERAGING == "True":
    param.pv = float(pwa)
  else:
    param.pv = float(pw)  
  
  
  """
  direction = {}
  direction = directionSearch(mcu, ch, adpKey, cntwin)
  direction = LinearRegression(mcu, ch, adpKey, cntwin)
  if direction[0] == "None":
    # もしNoneなら最小値の更新がなかったため，attの調整だけしてstepTrackを終了する
    pass
  elif direction[0] == "increase":
    while True:
      if basePoint.phase + 130*(direction[1]+1) > 4095:
        adpKey.phase = 0
      else :
        adpKey.phase = min(4095, basePoint.phase+130*(direction(1)+1))
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      if AVERAGING == "True":
        cv = pwa
        phase_dcpower_List.append(cv)
      else:
        cv = pw
        phase_dcpower_List.append(cv)
      if cv-pv >= 0:
        # cvが最小値ではないため，1step戻して最小値の設定にする
        adpKey.phase -= 1
        break
      # pvを更新
      pv = cv
  elif direction[0] == "decrease":
    
  else:
    cntwin.erase()
    cntwin.addstr(10,0,"\tphaseの前後値差分の比較にエラーが発生しています", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
  cntwin.erase()
  cntwin.addstr(9,5,"\tstep track制御を終了")
  """
  
  
  """
  # 初期探索として，step制御をincrease or decreaseのどちらで制御するか決定する
def directionSearch(mcu, ch, adpKey, cntwin):
  for step in range(15):
    # +方向にstep調整
    if basePoint.phase + 130*(step+1) > 4095:
      adpKey.phase = 0
    else :
      adpKey.phase = min(4095, basePoint.phase+130*(step+1))
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    th.join()
    time.sleep(1)
    if AVERAGING == "True":
      cv = pwa
      phase_dcpower_List.append(cv)
    else:
      cv = pw
      phase_dcpower_List.append(cv)
    increase_delta = cv-pv
    # -方向にstep調整
    if basePoint.phase - 130*(step+1) < 0:
      adpKey.phase = 4095
    else :
      adpKey.phase = max(0, basePoint.phase-130*(step+1))
    th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
    th.start()
    th.join()
    time.sleep(1)
    if AVERAGING == "True":
      cv = pwa
      phase_dcpower_List.append(cv)
    else:
      cv = pw
      phase_dcpower_List.append(cv)
    decrease_delta = cv - pv
    # 前step差分と後step差分のどちらかが－符号のときのみ比較する
    if np.sign(increase_delta)==-1 or np.sign(decrease_delta)==-1:
      if increase_delta < decrease_delta:
        pv = phase_dcpower_List[len(phase_dcpower_List-2)]
        return "increase", step+1
      elif increase_delta > decrease_delta:
        pv = phase_dcpower_List[len(phase_dcpower_List-1)]
        return "decrease", step+1
      else:
        return
  return "None"
  """
  
  # phase調整
  step_LinearRegression(mcu, ch, adpKey, basePoint, cntwin, debug, param, "phase")
  if param.direction == "increase":
    index = len(param.increase_delta_List)
    increase_delta_List = param.increase_delta_List[index-5:index]
    if np.sign(min(increase_delta_List)) == -1:  # 最小値がマイナスの符号なら最小値の更新があったと考えられる
      # リスト内の最小値のインデックスから，phase = 0からのシフト量を求めてbasePointを更新する
      if basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1) > 4095:
        basePoint.phase = basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1) - 4095
        param.step_phase = math.floor(basePoint.phase / 130)
        adpKey.phase = basePoint.phase
      else :
        basePoint.phase = min(4095, basePoint.phase + 130*(increase_delta_List.index(min(increase_delta_List))+1))
        param.step_phase = increase_delta_List.index(min(increase_delta_List))+1
        adpKey.phase = basePoint.phase
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "phaseの初期探索を終了")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(increase_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      flag = "True"
      """
      # DC powerの最小値を更新(base)
      if AVERAGING == "True":
        pv = pwa
        phase_dcpower_List.append(pv)
      else:
        pv = pw
        phase_dcpower_List.append(pv)
      """
    elif np.sign(min(increase_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      for i in range(11):
      #while True:
        if adpKey.phase + 130 > 4095:
          param.step_phase = 0
          adpKey.phase = 0
        else :
          param.step_phase += 1
          adpKey.phase = min(4095, adpKey.phase + 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
          flag = "True"
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          break
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
      
    
    # さらに最小値が続くかの探索ループ(極小値探索)
    if flag == "True":
      flag = "False"
      while True:
        if adpKey.phase + 130 > 4095:
          param.step_phase = 0
          adpKey.phase = 0
        else :
          param.step_phase += 1
          adpKey.phase = min(4095, adpKey.phase + 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
        debug.set(adpKey, basePoint, param)
        if param.cv < param.pv :
          param.pv = param.cv
          basePoint.phase = adpKey.phase
        elif param.cv >= param.pv :
          if adpKey.phase - 130 < 0:
            param.step_phase = 0
            adpKey.phase = 4095
          else :
            param.step_phase -= 1
            adpKey.phase = max(0,adpKey.phase-130)
          cntwin.erase()
          cntwin.addstr(9,5, "step track制御を開始")
          cntwin.addstr(10,5, "phaseの初期探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
      # リスト内の最小値のインデックスから，phase = 0からのシフト量を求めてbasePointを更新する
      if basePoint.phase - 130*(decrease_delta_List.index(min(decrease_delta_List))+1) < 0:
        basePoint.phase = 4095 - 130*(decrease_delta_List.index(min(decrease_delta_List))+1)
        adpKey.phase = basePoint.phase
      else :
        basePoint.phase = max(0, basePoint.phase - 130*(decrease_delta_List.index(min(decrease_delta_List))+1))
        adpKey.phase = basePoint.phase
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "phaseの初期探索を終了")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(decrease_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      flag = "True"
      """
      # DC powerの最小値を更新(base)
      if AVERAGING == "True":
        pv = pwa
        phase_dcpower_List.append(pv)
      else:
        pv = pw
        phase_dcpower_List.append(pv)
      """
    elif np.sign(min(decrease_delta_List)) == 1:  # 最小値がプラスの符号なら最小値の更新がなかったため，探索を続ける
      for i in range(11):
      #while True:
        if adpKey.phase - 130 < 0:
          param.step_phase = 0
          adpKey.phase = 4095
        else :
          param.step_phase += 1
          adpKey.phase = max(0, adpKey.phase - 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
          basePoint.phase = adpKey.phase
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
          flag = "True"
          break
        param.delta_calc()
        debug.set(adpKey, basePoint, param)
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
      
    if flag == "True":
      flag = "False"
    # さらに最小値が続くかの探索ループ
      while True:
        if adpKey.phase - 130 < 0:
          param.step_phase = 0
          adpKey.phase = 4095
        else :
          param.step_phase += 1
          adpKey.phase = max(0, adpKey.phase - 130)
        cntwin.erase()
        cntwin.addstr(9,5, "step track制御を開始")
        cntwin.addstr(10,5, "phaseの初期探索を終了")
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
          basePoint.phase = adpKey.phase
          param.delta_calc()
          debug.set(adpKey, basePoint, param)
        elif param.cv >= param.pv :
          if adpKey.phase + 130 > 4095:
            param.step_phase = 0
            adpKey.phase = 0
          else :
            param.step_phase -= 1
            adpKey.phase = max(0,adpKey.phase-130)
          cntwin.erase()
          cntwin.addstr(9,5, "step track制御を開始")
          cntwin.addstr(10,5, "phaseの初期探索を終了")
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
  
  
  
  # att調整
  step_LinearRegression(mcu, ch, adpKey, basePoint, cntwin, debug, param, "att")
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
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(increase_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      flag = "True"
      """
      # DC powerの最小値を更新(base)
      if AVERAGING == "True":
        pv = pwa
        phase_dcpower_List.append(pv)
      else:
        pv = pw
        phase_dcpower_List.append(pv)
      """
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
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
          flag = "True"
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
    if flag == "True":
      flag = "False"
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
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
      cntwin.refresh()
      th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
      th.start()
      th.join()
      time.sleep(1)
      param.pv = min(decrease_delta_List)
      param.cv = param.pv
      param.delta_calc()
      debug.set(adpKey, basePoint, param)
      flag = "True"
      """
      # DC powerの最小値を更新(base)
      if AVERAGING == "True":
        pv = pwa
        phase_dcpower_List.append(pv)
      else:
        pv = pw
        phase_dcpower_List.append(pv)
      """
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
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
          flag = "True"
          break
        param.delta_calc()
        debug.set(adpKey, basePoint, param)
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\tincrease_delta_Listの最小値の符号が取得できません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
      
    if flag == "True":
      flag = "False"
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
        cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
          cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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

  
  
  cntwin.erase()
  cntwin.addstr(9,5,"stepTrack制御を終了, Phaseを %4d, Attを %3.1fに調整しました\n Qを押してください" %(basePoint.phase, basePoint.att/2))
  cntwin.refresh()
  
  # auto_Tuneの実行結果を出力(デバッグ用)
  if DEBUG == "True":
    """
    t = time.time()
    dt = datetime.datetime.fromtimestamp(t)
    debug_File = pd.DataFrame([step_phase_List, step_att_List, phase_List, att_List, basePoint_phase_List, basePoint_att_List, cv_List, pv_List], index=['step_phase', 'step_att', 'phase', 'att', 'basePoint.phase', 'basePoint.att', 'cv', 'pv'])
    # 最小のphase値探索の検証excelを出力
    debug_File.to_excel('stepTrack_Debug'+ str(dt) +'.xlsx')
    """
    debug.output()
  elif DEBUG == "False":
    pass
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\tDebugオプションに有効な文字列が与えられていません", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
  x = cntwin.getch()
  if chr(x) == 'q':
    return



"""
# directionSearchで決めた制御の方向に繰り返し制御する
def stepTrack(mcu, ch, adpKey, cntwin, direction, setting):
  if setting == "phase":
    if direction == "increase":
      for i in range(5):
        if basePoint.phase + 130*(direction(1)+i) > 4095:
          adpKey.phase = 0
        else :
          adpKey.phase = min(4095, basePoint.phase+130*(direction(1)+i))
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          cv = pwa
          phase_dcpower_List.append(cv)
        else:
          cv = pw
          phase_dcpower_List.append(cv)
        if cv-pv >= 0:
          # cvが最小値ではないため，1step戻して最小値の設定にする
          adpKey.phase -= 1
          break
        # pvを更新
        pv = cv
    elif direction == "decrease":
      while True:
        if basePoint.phase - 130*(direction(1)+1) < 0:
          adpKey.phase = 0
        else :
          adpKey.phase = max(0, basePoint.phase-130*(direction(1)+1))
        th = threading.Thread(target=mcu.senddata, args=(ch, adpKey.att, adpKey.phase,))
        th.start()
        th.join()
        time.sleep(1)
        if AVERAGING == "True":
          cv = pwa
          phase_dcpower_List.append(cv)
        else:
          cv = pw
          phase_dcpower_List.append(cv)
        if cv-pv >= 0:
          # cvが最小値ではないため，1step戻して最小値の設定にする
          adpKey.phase += 1
          break
        # pvを更新
        pv = cv
    else:
      cntwin.erase()
      cntwin.addstr(10,0,"\t変数directonにincreaseまたはdecreaseが格納されていません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
  
  elif setting == "att":
    if direction == "increase":
      pass
    elif direction == "decrease":
      pass
    else:
      cntwin.erase()
      cntwin.addstr(10,0,"\t変数directonにincreaseまたはdecreaseが格納されていません", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return
  else:
    cntwin.erase()
    cntwin.addstr(10,0,"\t変数settingにphaseまたはattが格納されていません", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
    return
"""
  
  
def step_LinearRegression(mcu, ch, adpKey, basePoint, cntwin, debug, param, setting):  # 最小値設定のbasePointを渡し，basePointから±nstep動かす
  param.delta_List_init()  # 線形回帰モデル作成のためのdelta_List[5]の初期化
  param.direction = "None"
  param.model_init()
  # phaseの探索
  if setting == "phase":
    for i in range(1,6):
      param.step_phase_incre()
      # +方向にstep調整
      if basePoint.phase + 130*i > 4095:
        adpKey.phase = basePoint.phase + 130*i -4095
      else :
        adpKey.phase = min(4095, basePoint.phase+130*i)
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "phaseの初期探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
      # -方向にstep調整
      param.step_phase_incre()
      if basePoint.phase - 130*i < 0:
        adpKey.phase = 4095 - basePoint.phase - 130*i
      else :
        adpKey.phase = max(0, 4095 - basePoint.phase - 130*i)
      cntwin.erase()
      cntwin.addstr(9,5, "step track制御を開始")
      cntwin.addstr(10,5, "phaseの初期探索を開始")
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_phase: %d" %((adpKey.att/2), adpKey.phase, param.step_phase))
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
    """
    # increaseとdecrease方向それぞれの回帰直線を作成
    increase_model = LinearRegression()
    decrease_model = LinearRegression()
    increase_model.fit(pd.DataFrame(range(1, 6)), pd.DataFrame(param.increase_delta_List))
    decrease_model.fit(pd.DataFrame(range(1, 6)), pd.DataFrame(param.decrease_delta_List))
    param.increase_model_output(increase_model.coef_, increase_model.intercept_)
    param.decrease_model_output(decrease_model.coef_, decrease_model.intercept_)
    # 回帰直線から(i+1)step後に最小値量へ向かっている方向を探す
    increase_slope = increase_model.coef_ * 6 + increase_model.intercept_
    decrease_slope = decrease_model.coef_ * 6 + decrease_model.intercept_
    #debug.set(adpKey, basePoint, param)
    """
    linear_model = LinearRegression()
    linear_model.fit(pd.DataFrame(range(1,11)), pd.DataFrame(param.increase_delta_List.extend(param.decrease_delta_List)))
    param.linear_model_output(linear_model.coef_)
    if np.sign(linear_model.coef_) == 1:
      param.direction = "increase"
      return
    elif np.sign(linear_model.coef_) == -1:
      param.direction = "decrease"
      return
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\t回帰直線でエラー", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return

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
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_att: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
      cntwin.addstr(4,10,"Att: %3.1f dB  Phase: %4d step_att: %d" %((adpKey.att/2), adpKey.phase, param.step_att))
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
    """
    # increaseとdecrease方向それぞれの回帰直線を作成
    increase_model = LinearRegression()
    decrease_model = LinearRegression()
    increase_model.fit(pd.DataFrame(range(1, 6)), pd.DataFrame(param.increase_delta_List))
    decrease_model.fit(pd.DataFrame(range(1, 6)), pd.DataFrame(param.decrease_delta_List))
    param.increase_model_output(increase_model.coef_, increase_model.intercept_)
    param.decrease_model_output(decrease_model.coef_, decrease_model.intercept_)
    # 回帰直線から(i+1)step後に最小値量へ向かっている方向を探す
    increase_slope = increase_model.coef_ * 6 + increase_model.intercept_
    decrease_slope = decrease_model.coef_ *6 + decrease_model.intercept_
    #debug.set(adpKey, basePoint, param)
    """
    linear_model = LinearRegression()
    linear_model.fit(pd.DataFrame(range(1,11)), pd.DataFrame(param.increase_delta_List.extend(param.decrease_delta_List)))
    param.linear_model_output(linear_model.coef_)
    if np.sign(linear_model.coef_) == 1:
      param.direction = "increase"
      return
    elif np.sign(linear_model.coef_) == -1:
      param.direction = "decrease"
      return
    else:
      cntwin.erase()
      cntwin.addstr(15,0,"\t初期探索でエラー", curses.color_pair(1))
      cntwin.refresh()
      time.sleep(10)
      return

  else :
    cntwin.erase()
    cntwin.addstr(15,0,"\tsettingに有効なパラメータが代入されていません", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
    return
  
  

  """
def DebugFile(step_phase, step_att, adpKey, basePoint, cntwin):
  if DEBUG == "True":
    DebugFile.set(step_phase, step_att, adpKey, basePoint)
    # global step_phase_List
    # global step_att_List
    # global phase_List
    # global att_List
    # global basePoint_phase_List
    # global basePoint_att_List
    # global cv_List
    # global pv_List
    step_phase_List.append(step_phase)  # step_phase
    step_att_List.append(step_att)  # step_att
    phase_List.append(adpKey.phase)  # phase
    att_List.append(adpKey.att)  # att
    basePoint_phase_List.append(basePoint.phase)  # basePoint.phase
    basePoint_att_List.append(basePoint.att)  # basePoint.att
    cv_List.append(cv)  # cv
    pv_List.append(pv)  # pv
    
  elif DEBUG == "False":
    pass
  else:
    cntwin.erase()
    cntwin.addstr(15,0,"\tDebugオプションに有効な文字列が与えられていません", curses.color_pair(1))
    cntwin.refresh()
    time.sleep(10)
  """
    
class DebugFile:
  def __init__(self):
    self.total_step = []
    self.step_phase = []
    self.step_att = []
    self.phase = []
    self.att = []
    self.direction = []
    self.basePoint_phase = []
    self.basePoint_att = []
    self.cv = []
    self.pv = []
    self.delta = []
    self.linear_model = []
    # self.increase_model = []
    # self.decrease_model = []
  
  def set(self, adpKey, basePoint, param):
    self.total_step.append(param.step_phase + param.step_att)
    self.step_phase.append(param.step_phase)
    self.step_att.append(param.step_att)
    self.direction.append(param.direction)
    self.phase.append(adpKey.phase)
    self.att.append(adpKey.att)
    self.basePoint_phase.append(basePoint.phase)
    self.basePoint_att.append(basePoint.att)
    self.cv.append(float(param.cv))
    self.pv.append(float(param.pv))
    self.delta.append(float(param.delta))
    self.linear_model.append(param.linear_model)
    # self.increase_model.append(param.increase_model)
    # self.decrease_model.append(param.decrease_model)

  def output(self):
    t = time.time()
    dt = datetime.datetime.fromtimestamp(t)
    debug_File = pd.DataFrame([self.total_step, self.step_phase, self.step_att, self.phase, self.att, self.basePoint_phase, self.basePoint_att, self.cv, self.pv, self.delta, self.direction, self.linear_model], index=['total_step', 'step_phase', 'step_att', 'phase', 'att', 'basePoint.phase', 'basePoint.att', 'current value', 'previous value', 'delta value', 'direction', 'linear_model'])
    # 最小のphase値探索の検証excelを出力
    debug_File.to_excel('stepTrack_Debug'+ str(dt) +'.xlsx')
    
class TrackParam:
  def __init__(self):
    self.cv = 0.0
    self.pv = 0.0
    self.direction = "None"
    self.step_phase = 0
    self.step_att = 0
    self.delta = 0.0
    self.linear_model = "None"
    # self.increase_model = "None"
    # self.decrease_model = "None"
    self.increase_delta_List = []
    self.decrease_delta_List = []
    
  def step_phase_incre(self):
    self.step_phase += 1
    
  def step_att_incre(self):
    self.step_att += 1
    
  def increase_delta_append(self):
    self.increase_delta_List.append(self.increase_delta)
    
  def decrease_delta_append(self):
    self.decrease_delta_List.append(self.decrease_delta)
  
  def delta_calc(self):
    self.delta = self.cv - self.pv
  
  def delta_List_init(self):
    self.increase_delta_List = []
    self.decrease_delta_List = []
  
  def linear_model_output(self, coef):
    self.linear_model = str(coef)
  
  """
  def increase_model_output(self, coef, intercept):
    self.increase_model = str(coef) + "x + (" + str(intercept) + ")"
    
  def decrease_model_output(self, coef, intercept):
    self.decrease_model = str(coef) + "x + (" + str(intercept) + ")"
  """
  
  def model_init(self):
    self.linear_mode = "None"
    # self.increase_model = "None"
    # self.decrease_model = "None"


if __name__ == '__main__':
    main()
