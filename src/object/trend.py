from enum import IntFlag


class TrendState(IntFlag):
    '''
    - Market Trend Information
    '''
    FLAT = 1  # 1, 횡보
    STRONG_BULLISH = 2  # 10, 급격한 상승장
    BULLISH = 4  # 100, 상승장
    BEARISH = 8  # 1000, 하락장
    STRONG_BEARISH = 16   # 1_0000, 급격한 하락장
