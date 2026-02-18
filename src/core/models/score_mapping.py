from src.core.models.signal import TradeSignal


class ScoreMapper:
    def __init__(self) -> None:
        self.score_map: dict[TradeSignal, int] = {
            TradeSignal.SHORT_TERM_BUY: 2,
            TradeSignal.LONG_TERM_BUY: 5,
            TradeSignal.SHORT_TERM_SELL: -2,
            TradeSignal.LONG_TERM_SELL: -5,
            TradeSignal.HOLD: 0,
        }
        return

    def map(
        self,
        signal: TradeSignal,
    ) -> float:
        return self.score_map.get(signal, 0)


"""
#############################################################################################################
#                                        Mapping Testing Code                                               #
#############################################################################################################
"""
if __name__ == "__main__":
    mapper = ScoreMapper()
    print(mapper.map(TradeSignal.SHORT_TERM_BUY))
    print(mapper.map(TradeSignal.LONG_TERM_BUY))
    print(mapper.map(TradeSignal.SHORT_TERM_SELL))
    print(mapper.map(TradeSignal.LONG_TERM_SELL))
    print(mapper.map(TradeSignal.HOLD))
    print(mapper.map(TradeSignal(0)) == 0)
    print(mapper.map(TradeSignal(3)) == 0)
    print(mapper.map(TradeSignal(4)) == 0)
    print(mapper.map(TradeSignal(5)) == 0)
    print(mapper.map(TradeSignal(6)) == 0)
    print(mapper.map(TradeSignal(7)) == 0)
    print(mapper.map(TradeSignal(8)) == 0)
    print(mapper.map(TradeSignal(9)) == 0)
    print(mapper.map(TradeSignal(10)) == 0)
    print(mapper.map(TradeSignal(11)) == 0)
    print(mapper.map(TradeSignal(12)) == 0)
    print(mapper.map(TradeSignal(13)) == 0)
    print(mapper.map(TradeSignal(14)) == 0)
    print(mapper.map(TradeSignal(15)) == 0)
    print(mapper.map(TradeSignal(16)) == 0)
    print(mapper.map(TradeSignal(17)) == 0)
    print(mapper.map(TradeSignal(18)) == 0)
    print(mapper.map(TradeSignal(19)) == 0)
    print(mapper.map(TradeSignal(20)) == 0)
    print(mapper.map(TradeSignal(21)) == 0)
    print(mapper.map(TradeSignal(22)) == 0)
    print(mapper.map(TradeSignal(23)) == 0)
    print(mapper.map(TradeSignal(24)) == 0)
    print(mapper.map(TradeSignal(25)) == 0)
    print(mapper.map(TradeSignal(26)) == 0)
    print(mapper.map(TradeSignal(27)) == 0)
    print(mapper.map(TradeSignal(28)) == 0)
    print(mapper.map(TradeSignal(29)) == 0)
