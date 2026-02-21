import numpy as np
from typing import Any, Dict
from state.state import EmailAnalysisState


def sanitize(state: EmailAnalysisState) -> Dict[str, Any]:
    """
    递归把 numpy 标量 -> python 标量
    """

    def _conv(obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, dict):
            return {k: _conv(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_conv(i) for i in obj]
        return obj

    return _conv(state)
