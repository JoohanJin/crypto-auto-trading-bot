from enum import IntFlag


class TrendState(IntFlag):
    '''
    - Market Trend Information
    '''
    FLAT = 1 << 0  # 1, 횡보
    STRONG_BULLISH = 1 << 1  # 10, 급격한 상승장
    BULLISH = 1 << 2  # 100, 상승장
    BEARISH = 1 << 3  # 1000, 하락장
    STRONG_BEARISH = 1 << 4   # 1_0000, 급격한 하락장
