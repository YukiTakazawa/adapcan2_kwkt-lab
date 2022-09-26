#!/usr/bin/env python
import sys
import termios
import contextlib


@contextlib.contextmanager
def raw_mode(file):
    old_attrs = termios.tcgetattr(file.fileno())
    new_attrs = old_attrs[:]
    new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
    try:
       termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
       yield
    finally:
       termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

def main():
    print('exit with ^C or ^D')
    count = 0 
    prev = ''
    with raw_mode(sys.stdin):
       try:
         while True:
            ch = sys.stdin.read(1)
            if not ch or ch == chr(4):
               break
            if prev == 'a' and ch == 'a':
                sys.stdout.write("\x1b[2D")
                print("%d" % count)
                sys.stdout.write("\x1b[1A")
                count = count + 1
            else:
                count = 0
            prev = ch
       except (KeyboardInterrupt, EOFError):
          pass
if __name__ == '__main__':
   main()
