"""信号生成器模型"""


class SignalGenerator:
    """信号生成器 - 定义信号类型和参数"""
    
    # 支持的信号类型
    TYPE_SINE = 'sine'
    TYPE_NOISE = 'noise'
    TYPE_IMPULSE = 'impulse'
    TYPE_SAWTOOTH = 'sawtooth'
    TYPE_SQUARE = 'square'
    
    VALID_TYPES = [TYPE_SINE, TYPE_NOISE, TYPE_IMPULSE, TYPE_SAWTOOTH, TYPE_SQUARE]
    
    def __init__(self, id, type, parameters):
        """
        Args:
            id: 生成器唯一标识
            type: 信号类型 ('sine', 'noise', 'impulse', etc.)
            parameters: 参数字典，如 {'frequency': 10, 'amplitude': 5}
        """
        self.id = id
        self.type = type
        self.parameters = parameters
        
    def __repr__(self):
        return f"SignalGenerator({self.id}, type={self.type})"
