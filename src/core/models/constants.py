'''
# this is the DataCollectorProcessor side.
# EMA and SMA PERIODS
#
'''
MA_WRITE_PERIODS: tuple[int] = (
    5,    # 10 sec
    15,   # 30 sec
    30,   # 60 sec, 1 min
    150,  # 300 sec, 5 min
    300,  # 600 sec, 10 min
    600,  # 1200 sec, 20 min
    900,  # 1800 sec, 30 min
)


'''
# this is the SignalGenerator side
#
'''
MA_READ_PERIODS: tuple[int] = (
    10,    # 10 sec
    30,    # 30 sec
    60,    # 60 sec, 1 min
    300,   # 300 sec, 5 min
    600,   # 600 sec, 10 min
    1200,  # 1200 sec, 20 min
    1800,  # 1800 sec, 30 min
)
