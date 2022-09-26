import curses
stdscr = curses.initscr()
stdscr.keypad(0)
curses.nocbreak()
curses.echo()
curses.endwin()
