from typing import List, Dict, Tuple, Generator, Optional
from json_streamer import Parser, ParseState


class YamlParser(Parser):
    """
    Parse partial YAML
    """

    @staticmethod
    def opening_symbols() -> List[chr]:
        return ['{', '[', '"']

    def raw_decode(self, s: str) -> Tuple[Dict, int]:
        try:
            from yaml import safe_load
        except ImportError:
            raise ImportError("You must install PyYAML to use the YamlParser: pip install PyYAML")
        return safe_load(s), -1

    def parse_part(self, part: str) -> Generator[Tuple[ParseState, dict], None, None]:
        for y in super().parse_part(part):
            yield ParseState.UNKNOWN, y[1]


def loads(s: Optional[Generator[chr, None, None]] = None) -> Generator[Tuple[ParseState, dict], Optional[str], None]:
    return YamlParser()(s)
